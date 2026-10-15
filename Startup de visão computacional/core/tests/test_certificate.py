import hashlib
import io
import json
import re
import subprocess
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfReader

from analytics import fruit_analytics as FA
from belt import stats as BS
from analytics.test_fruit_analytics import demo_events

from core import certificate_data
from core import certificate_pdf
from core.certificate_pdf import certificate_number, fingerprint_layers, qr_payload
from core.certificate_text import AI_ERRORS, DECLARATIONS, T
from core.models import Event
from core.tests.test_dashboard import SerialLiveServerThread, monthly
from core.tests.test_api import PASSWORD, insert, show, strict_json

FRONTEND = settings.BASE_DIR / "frontend"
STATS = ["deformity", "forecast", "fruits", "growth", "recurring", "gaussian", "overview"]
DISPOSITION = re.compile(r'^attachment; filename="certificado-fruitcam-(FC-\d{8}-[0-9A-F]{8})\.pdf"$')


def squash(text):
    return re.sub(r"\s+", "", text)


def read_pdf(content):
    reader = PdfReader(io.BytesIO(content))
    return reader, [p.extract_text() or "" for p in reader.pages]


def outline_titles(reader):
    out = []

    def walk(items):
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                out.append(item.title)

    walk(reader.outline)
    return out


def known_months():
    return monthly([r for m in range(12) for r in ((m, "A", "caju", "nao_podre", 900), (m, "A", "caju", "podre", 100), (m, "B", "castanha", "nao_podre", 700), (m, "B", "castanha", "podre", 300))])


def declarations():
    return [DECLARATIONS["honesty"], DECLARATIONS["confidence"], DECLARATIONS["limits"], DECLARATIONS["dataIssue"], *DECLARATIONS["verified"], *DECLARATIONS["notVerified"], *(f"{x['title']}: {x['text']}" for x in DECLARATIONS["pending"])]


class CertificateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.force_login(get_user_model().objects.create_user("ana", password=PASSWORD))

    def get(self, **query):
        return self.client.get("/api/certificate", query)

    def test_requires_login_valid_filters_and_data(self):
        bad = [self.get(**q) for q in ({"period": "day"}, {"source": "x"}, {"start": "2026-13-01"})]
        empty = self.get()
        self.client.logout()
        anonymous = self.get()
        show(f"bad filters -> {[(r.status_code, strict_json(r)['error']['code']) for r in bad]}; empty database -> {empty.status_code} {strict_json(empty)['error']['code']}; without login -> {anonymous.status_code} {strict_json(anonymous)['error']['code']}")
        self.assertEqual([(r.status_code, strict_json(r)["error"]["code"]) for r in bad], [(400, "invalid_filter")] * 3)
        self.assertEqual((empty.status_code, strict_json(empty)["error"]["code"]), (404, "no_data"))
        self.assertEqual((anonymous.status_code, strict_json(anonymous)["error"]["code"]), (403, "not_authenticated"))

    def test_certificate_contents_with_known_data(self):
        insert(known_months())
        started = time.perf_counter()
        r = self.get(period="month", source="real")
        elapsed = time.perf_counter() - started
        self.assertEqual(r.status_code, 200)
        number = DISPOSITION.match(r["Content-Disposition"]).group(1)
        reader, pages = read_pdf(r.content)
        flat = squash("".join(pages))
        no_ai = [i + 1 for i, p in enumerate(pages) if squash(AI_ERRORS) not in squash(p)]
        missing = [d[:50] for d in declarations() if squash(d) not in flat]
        titles = outline_titles(reader)
        sections = [s for k, s in T["sections"].items() if k != "annex_b" and not any(s in title for title in titles)]
        figures = sum(len(p.images) for p in reader.pages) - 2 - (len(pages) - 1)
        facts = {
            "24.000 frutas": "24.000" in flat,
            "taxa 20,0% com IC": squash("20,0%") in flat and squash("IC 95% (Wilson): 19,5% a 20,5%") in flat,
            "setor B 30,0%": squash("B12.0003.60030,0%") in flat,
            "setor A 10,0%": squash("A12.0001.20010,0%") in flat,
            "empate de frutas": squash("Fruta mais recebidaempate") in flat,
            "número no cabeçalho": squash(f"Nº {number}") in squash(pages[1]),
        }
        show(f"{len(r.content) / 1e6:.2f} MB, {len(pages)} pages in {elapsed:.1f} s; number {number}; title '{reader.metadata.title}', author '{reader.metadata.author}'")
        show(f"pages without the AI statement: {no_ai}; declarations missing: {missing}; sections missing from the PDF outline: {sections}; annex B (no camera data) present: {any(T['sections']['annex_b'] in x for x in titles)}; chart images: {figures}; known facts found: {facts}")
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r["X-Certificate-Number"], number)
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertEqual(reader.metadata.title, f"{T['title']} {number}")
        self.assertEqual(reader.metadata.author, T["brand"])
        self.assertIn(squash(AI_ERRORS), squash(pages[0]))
        self.assertEqual(no_ai, [])
        self.assertEqual(missing, [])
        self.assertEqual(sections, [])
        self.assertFalse(any(T["sections"]["annex_b"] in x for x in titles))
        self.assertGreaterEqual(figures, 10)
        self.assertTrue(all(facts.values()), facts)
        self.assertNotIn(squash(T["watermark"]), flat)

    def test_identity_fonts_qr_rosette_and_numbered_sections(self):
        insert(known_months())
        r = self.get(period="month", source="real")
        reader, pages = read_pdf(r.content)
        fonts = {str(f.get_object().get("/BaseFont")).split("+")[-1] for p in reader.pages for f in p.get("/Resources", {}).get("/Font", {}).values()}
        data = certificate_data.collect("month", "real", None, None, None)
        number = r["X-Certificate-Number"]
        payload = qr_payload(data, number, timezone.localtime().replace(tzinfo=None))
        layers = fingerprint_layers(data["fingerprint"])
        other = fingerprint_layers(hashlib.sha256(b"outro").hexdigest())
        titles = [t for t in outline_titles(reader) if t[0].isdigit()]
        show(f"embedded fonts {sorted(fonts)}; QR payload {len(payload)} chars, ascii {payload.isascii()}; rosette layers {layers} vs another fingerprint {other}; numbered sections {titles}")
        if certificate_pdf.BRANDED:
            self.assertTrue({"FrauncesDisplay-SemiBold-FruitCam", "Inter-Regular-FruitCam", "JetBrainsMono-Regular-FruitCam"} <= fonts)
        self.assertTrue(payload.isascii())
        self.assertIn(number, payload)
        self.assertIn(data["fingerprint"], payload)
        self.assertEqual(layers, fingerprint_layers(data["fingerprint"]))
        self.assertNotEqual(layers, other)
        self.assertEqual([t.split(". ")[0] for t in titles], [str(i) for i in range(1, len(titles) + 1)])
        self.assertEqual(titles[0], f"1. {T['sections']['scope']}")
        self.assertIn(squash(T["kpi"]["rate"].upper()), squash("".join(pages)))

    def test_dashboard_numbers_equal_the_api(self):
        insert(known_months())
        insert(FA.to_events(demo_events(2, 20, 40)), demo=True)
        checked = 0
        for query in ({"period": "week", "source": "real"}, {"period": "month", "source": "all"}, {"period": "month", "source": "real", "sector": "B", "start": "2024-03-01", "end": "2024-08-31"}):
            body = certificate_data.collect(query["period"], query["source"], query.get("sector"), *self.bounds(query))
            for name in STATS:
                api = strict_json(self.client.get(f"/api/stats/{name}", query))
                for k in ("period", "source", "sector", "demo"):
                    api.pop(k, None)
                self.assertEqual(body["dashboard"][name], api, (query, name))
                checked += 1
        show(f"{checked} certificate payloads compared with /api/stats responses for the same filters: all identical")

    def bounds(self, q):
        tz = timezone.get_current_timezone()
        start = datetime.fromisoformat(q["start"]).replace(tzinfo=tz) if "start" in q else None
        end = (datetime.fromisoformat(q["end"]) + timedelta(days=1)).replace(tzinfo=tz) if "end" in q else None
        return start, end

    def test_fingerprint_is_deterministic_and_tracks_the_data(self):
        insert(known_months())
        a = certificate_data.collect("month", "real", None, None, None)["fingerprint"]
        b = certificate_data.collect("month", "real", None, None, None)["fingerprint"]
        Event.objects.create(sector="A", fruit_type="caju", is_good=False, deformity_type="podre")
        c = certificate_data.collect("month", "real", None, None, None)["fingerprint"]
        issued = timezone.localtime()
        numbers = {certificate_number(a, issued, "ana"), certificate_number(a, issued + timedelta(seconds=1), "ana"), certificate_number(a, issued, "bia")}
        show(f"same data -> {a[:16]}… twice; one more fruit -> {c[:16]}…; 3 issues of the same data -> {len(numbers)} distinct numbers")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(numbers), 3)

    def test_demo_data_is_watermarked_on_every_page(self):
        insert(known_months())
        insert(FA.to_events(demo_events(1, 30, 60)), demo=True)
        demo = read_pdf(self.get(source="demo").content)[1]
        real = read_pdf(self.get(source="real").content)[1]
        mark = squash(T["watermark"])
        without = [i + 1 for i, p in enumerate(demo) if mark not in squash(p)]
        show(f"demo: {len(demo)} pages, watermark missing on {without}; cover notice {squash(T['demo_cover']) in squash(demo[0])}; real: watermark on {sum(mark in squash(p) for p in real)} of {len(real)} pages")
        self.assertEqual(without, [])
        self.assertIn(squash(T["demo_cover"]), squash(demo[0]))
        self.assertEqual(sum(mark in squash(p) for p in real), 0)

    def test_line_section_counts_lots_and_alarms(self):
        call_command("seed_line_demo", hours=8, stdout=io.StringIO())
        body = certificate_data.collect("week", "demo", None, None, None)
        c = next(x for x in body["line"] if x["camera"]["slug"] == "linha-1")
        stored = Event.objects.filter(source="camera", camera="linha-1", is_demo=True)
        mismatched = []
        for lot in c["lots"]:
            rows = stored.filter(lot=lot["lot"])
            k = rows.filter(label="podre", needs_review=False).count()
            n = rows.filter(needs_review=False).count()
            if (lot["rotten"]["ci95"], lot["verdict"]) != (BS.wilson(k, n), BS.lot_verdict(k, n, c["max_rotten"])):
                mismatched.append(lot["lot"])
        verdicts = {lot["lot"][-2:]: lot["verdict"] for lot in c["lots"]}
        alarms = sorted({a["index"] for a in c["p_chart"]["alarms"] if a["rule"] == "acima_do_limite"})
        lot3 = next(lot for lot in c["lots"] if lot["lot"].endswith("03"))
        width = timedelta(minutes=c["window_minutes"])
        inside = all(datetime.fromisoformat(lot3["first"]) < datetime.fromisoformat(c["windows"][i]["start"]) + width and datetime.fromisoformat(c["windows"][i]["start"]) <= datetime.fromisoformat(lot3["last"]) for i in alarms)
        flat = squash("".join(read_pdf(self.get(source="demo").content)[1]))
        show(f"linha-1: {c['n']} fruits (database {stored.count()}), {len(c['windows'])} windows of {c['window_minutes']} min; lots {verdicts}; lots recomputed independently and different: {mismatched}; alarm windows {alarms} all overlap lot 3 ({lot3['first'][11:16]}–{lot3['last'][11:16]}): {inside}")
        self.assertEqual(c["n"], stored.count())
        self.assertEqual(c["total"], stored.count())
        self.assertLessEqual(len(c["windows"]), certificate_data.MAX_LINE_WINDOWS)
        self.assertEqual(mismatched, [])
        self.assertEqual(verdicts["03"], "reprovado")
        self.assertTrue(all(v == "aprovado" for k, v in verdicts.items() if k != "03"))
        self.assertTrue(alarms and inside)
        self.assertIn(squash(lot3["lot"]), flat)
        self.assertIn(squash(T["line"]["verdicts"]["reprovado"]), flat)

    def test_declarations_match_the_website_text(self):
        script = "import { t } from './src/strings.js'; console.log(JSON.stringify({ honesty: t.footer.honesty, confidence: t.upload.confidenceNote, limits: t.how.limits, dataIssue: t.how.dataIssue, verified: t.how.verified, notVerified: t.how.notVerified, pending: t.how.pending }))"
        run = subprocess.run(["node", "--input-type=module", "-e", script], cwd=FRONTEND, capture_output=True, text=True, encoding="utf-8")
        site = json.loads(run.stdout)
        different = [k for k in DECLARATIONS if DECLARATIONS[k] != site.get(k)]
        show(f"{len(DECLARATIONS)} declaration groups compared with frontend/src/strings.js; different: {different}")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(different, [])


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CertificateBrowserTests(StaticLiveServerTestCase):
    server_thread_class = SerialLiveServerThread

    @classmethod
    def setUpClass(cls):
        if not (settings.FRONTEND_DIST / "index.html").exists():
            raise RuntimeError("frontend/dist is missing: run `npm run build` in frontend/ first")
        super().setUpClass()
        from playwright.sync_api import sync_playwright

        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel="msedge")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user("ana", password=PASSWORD)
        self.errors = []

    def open(self, width=1366):
        ctx = self.browser.new_context(viewport={"width": width, "height": 900}, accept_downloads=True)
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(self.live_server_url + "/login")
        page.fill("input[name=username]", "ana")
        page.fill("input[name=password]", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url(self.live_server_url + "/")
        page.goto(self.live_server_url + "/painel")
        page.wait_for_selector("[data-stat]")
        deadline = time.time() + 90
        while page.evaluate("document.querySelectorAll('.skeleton, .card.refreshing').length") and time.time() < deadline:
            page.wait_for_timeout(100)
        return page

    def test_button_downloads_the_certificate(self):
        insert(known_months())
        page = self.open(width=390)
        button = page.locator(".cert-btn")
        label = button.inner_text()
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        with page.expect_download(timeout=120000) as info:
            button.click()
            page.wait_for_selector(".cert-btn[aria-busy=true]", timeout=5000)
            busy = button.inner_text()
        download = info.value
        content = open(download.path(), "rb").read()
        page.wait_for_selector(".cert-btn:not([aria-busy=true])")
        status = page.locator("[role=status]").all_inner_texts()
        show(f"button '{label}' -> while busy '{busy}'; downloaded '{download.suggested_filename}' ({len(content)} B, starts {content[:5]}); status text {status[-1:]}; horizontal overflow at 390 px: {overflow} px; JS errors {self.errors}")
        self.assertEqual(label, "Baixar certificado (PDF)")
        self.assertEqual(busy, "Gerando certificado…")
        self.assertRegex(download.suggested_filename, r"^certificado-fruitcam-FC-\d{8}-[0-9A-F]{8}\.pdf$")
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertIn(download.suggested_filename, " ".join(status))
        self.assertLessEqual(overflow, 0)
        self.assertEqual(self.errors, [])

    def test_button_explains_when_there_is_nothing_to_certify(self):
        page = self.open()
        page.click(".cert-btn")
        alert = page.wait_for_selector(".cert-msg[role=alert]", timeout=30000).inner_text()
        show(f"empty database -> alert '{alert}'")
        self.assertEqual(alert, "Não há registros nos filtros escolhidos para emitir o certificado.")
