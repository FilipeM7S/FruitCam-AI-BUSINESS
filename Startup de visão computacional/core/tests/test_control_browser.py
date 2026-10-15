import io
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import LiveServerTestCase, override_settings
from django.utils import timezone

from core.models import Event
from core.tests.test_dashboard import SerialLiveServerThread
from core.tests.test_media import NET, NOT_RUNNING, WATCH, Direct
from core.tests.test_api import PASSWORD, show

ROOT = settings.BASE_DIR
AXE = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
PHOTO = ROOT / "assets" / "media_src" / "commons" / "caju-vermelho.jpg"
ROUTES = {"/": "Linha de inspeção", "/inspecao": "Inspeção por foto", "/painel": "Painel estatístico", "/historico": "Histórico", "/como-funciona": "Como funciona", "/creditos": "Créditos e licenças"}
LABELS = {"/": "Linha", "/inspecao": "Inspeção por foto", "/painel": "Painel", "/historico": "Histórico", "/como-funciona": "Como funciona", "/creditos": "Créditos e licenças"}
FIELDS = ["label", "confidence", "deformity_type", "timestamp", "sector", "fruit_type", "lot", "camera", "track_id", "size_mm", "needs_review", "decided_by", "model_version", "source", "user", "id"]
CLASSES = {"boa": "Boa", "baixa_qualidade": "Baixa qualidade", "podre": "Podre"}
FRUITS = {"caju": "Caju", "castanha": "Castanha", "melao": "Melão"}
ROWS = "[...document.querySelectorAll('.inspect-fields [data-field]')].map((d) => [d.dataset.field, d.querySelector('dd').innerText.trim()])"


def number(text):
    return float(text.replace(".", "").replace(",", ".").replace("%", "").replace("mm", "").strip())


def shown_value(e, field):
    v = getattr(e, field) if field not in ("user",) else (e.user.username if e.user else None)
    if v is None or v == "":
        return None
    if field == "label":
        return CLASSES.get(v, v)
    if field == "timestamp":
        return timezone.localtime(v).strftime("%d/%m/%Y, %H:%M:%S")
    if field == "fruit_type":
        return FRUITS[v]
    if field == "needs_review":
        return "sim" if v else "não"
    if field == "source":
        return {"foto": "foto", "camera": "câmera"}[v]
    if field == "id":
        return f"#{v}"
    if field == "deformity_type":
        return {"podre": "Podre", "baixa_qualidade": "Baixa qualidade", "queimada": "Queimada", "quebrada": "Quebrada"}.get(v, v)
    return v


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, UPLOAD_DIR=Path(tempfile.mkdtemp(prefix="fruitcam_control_test_")))
class ControlBrowserTests(LiveServerTestCase):
    server_thread_class = SerialLiveServerThread
    static_handler = Direct

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
        call_command("seed_demo", "--weeks", "20", "--fruits-per-week", "40", stdout=io.StringIO())
        call_command("seed_line_demo", "--hours", "2", stdout=io.StringIO())

    def open(self, width=1280, height=900, reduced=False, theme=None, motion=None, bypass_csp=False):
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce" if reduced else "no-preference", color_scheme="dark", timezone_id=settings.TIME_ZONE, bypass_csp=bypass_csp)
        ctx.add_init_script(WATCH)
        ctx.add_init_script(NET % "false")
        if theme:
            ctx.add_init_script(f"try {{ localStorage.setItem('fruitcam-theme', '{theme}'); }} catch (e) {{}}")
        if motion:
            ctx.add_init_script(f"try {{ localStorage.setItem('fruitcam-motion', '{motion}'); }} catch (e) {{}}")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.problems = []
        page.on("pageerror", lambda e: page.problems.append(str(e)))
        page.on("console", lambda m: page.problems.append(m.text) if m.type == "error" and not m.location.get("url", "").endswith("/api/auth/me") else None)
        return page

    def until(self, page, js, timeout=40):
        deadline = time.time() + timeout
        while not page.evaluate(js):
            self.assertLess(time.time(), deadline, js)
            page.wait_for_timeout(80)

    def settle(self, page):
        page.wait_for_load_state("networkidle")
        self.until(page, "!document.getElementById('boot') && [...document.images].every((i) => i.complete || i.loading === 'lazy')")

    def login(self, page):
        page.goto(self.live_server_url + "/login")
        page.fill("input[name=username]", "ana")
        page.fill("input[name=password]", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url(self.live_server_url + "/")
        self.settle(page)

    def analyze(self, page):
        page.goto(self.live_server_url + "/inspecao")
        self.settle(page)
        page.locator(".fruit-card", has_text="Caju").click()
        page.fill("input[list=sector-list]", "Norte")
        page.locator("input[type=file]").first.set_input_files(str(PHOTO))
        page.wait_for_selector(".dropzone-preview img")
        phases = []
        with page.expect_response("**/api/analyze") as resp:
            page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
            for _ in range(400):
                phase = page.evaluate("document.querySelector('.live-strip').dataset.phase")
                if not phases or phases[-1] != phase:
                    phases.append(phase)
                if phase == "concluido":
                    break
                page.wait_for_timeout(15)
        body = resp.value.json()
        page.wait_for_selector(".verdict")
        page.wait_for_timeout(1300)
        return body, phases

    def scroll_through(self, page):
        height = page.evaluate("document.documentElement.scrollHeight")
        for y in range(0, height + 900, 400):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(60)

    def test_command_bar_opens_navigates_selects_and_closes_by_keyboard(self):
        page = self.open()
        self.login(page)
        visits = []
        for path, title in ROUTES.items():
            page.keyboard.press("Control+k")
            page.wait_for_selector(".cmd-input")
            focused = page.evaluate("document.activeElement.classList.contains('cmd-input')")
            page.keyboard.type(LABELS[path])
            self.until(page, "document.querySelectorAll('.cmd-item').length > 0")
            items = page.evaluate("[...document.querySelectorAll('.cmd-item')].map((i) => i.innerText.replace(/\\s+/g, ' ').trim())")
            target = next(i for i, text in enumerate(items) if text.endswith(LABELS[path]) and text.upper().startswith("PÁGINAS"))
            for _ in range(target):
                page.keyboard.press("ArrowDown")
            active = page.evaluate("document.querySelector('.cmd-item.active').innerText.replace(/\\s+/g, ' ').trim()")
            page.keyboard.press("Enter")
            page.wait_for_url(lambda url, path=path: urlsplit(url).path == path)
            self.until(page, f"document.querySelector('main h1')?.innerText.trim() === {title!r}")
            visits.append((path, focused, target, active, page.evaluate("!!document.querySelector('.command-bar')")))
        page.keyboard.press("Control+k")
        page.wait_for_selector(".cmd-input")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        closed = page.evaluate("!document.querySelector('.command-bar')")
        lot = Event.objects.exclude(lot="").values_list("lot", flat=True).first()
        page.keyboard.press("Control+k")
        page.keyboard.type(lot)
        self.until(page, "document.querySelectorAll('.cmd-item').length > 0")
        page.keyboard.press("Enter")
        page.wait_for_selector(".replay-counts")
        replay_title = page.inner_text(".sheet-head h2")
        page.keyboard.press("Escape")
        event = Event.objects.order_by("id").first()
        page.keyboard.press("Control+k")
        page.keyboard.type(f"#{event.id}")
        self.until(page, "document.querySelectorAll('.cmd-item').length > 0")
        page.keyboard.press("Enter")
        page.wait_for_selector(".inspect-fields")
        opened = page.inner_text(".sheet-head h2")
        hint = page.evaluate("[document.querySelector('.cmd-btn').getAttribute('aria-keyshortcuts'), document.querySelector('.cmd-kbd').innerText]")
        for row in visits:
            show(f"command bar: {row[0]:15s} input focused {row[1]}, {row[2]} arrow presses, active '{row[3]}', still open after Enter {row[4]}")
        show(f"Esc closes {closed}; '{lot}' -> '{replay_title}'; '#{event.id}' -> '{opened}'; visible hint {hint}; page errors {page.problems}")
        self.assertTrue(all(v[1] and not v[4] and v[3].endswith(LABELS[v[0]]) for v in visits))
        self.assertTrue(closed)
        self.assertIn(lot, replay_title)
        self.assertEqual(opened, f"Fruta #{event.id}")
        self.assertEqual(hint[0], "Control+K Meta+K")
        self.assertEqual(page.problems, [])

    def test_fruit_inspector_shows_only_stored_fields_and_matches_the_row(self):
        page = self.open()
        self.login(page)
        body, _ = self.analyze(page)
        page.click(".annotated-open")
        page.wait_for_selector(".inspect-fields")
        self.until(page, "document.querySelector('.inspect-fields [data-field=model_version]')")
        fresh = dict(page.evaluate(ROWS))
        probs = page.evaluate("[...document.querySelectorAll('.sheet .prob-row')].map((r) => [r.querySelector('.prob-name').innerText, r.querySelector('.prob-value').innerText])")
        crop = page.evaluate("(() => { const c = document.querySelector('.inspect-shot canvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let lit = 0; for (let i = 0; i < d.length; i += 4) lit += d[i] + d[i + 1] + d[i + 2] > 0; return [c.width, c.height, lit]; })()")
        page.keyboard.press("Escape")
        checked = [("foto", body["event"]["id"], fresh)]
        for kind in ("camera",):
            page.goto(self.live_server_url + f"/historico?source=all&kind={kind}")
            page.wait_for_selector(".history-table tbody tr")
            first = page.locator(".history-table tbody .row-open").first
            pk = int(first.inner_text().strip().lstrip("#"))
            first.click()
            self.until(page, f"document.querySelector('.inspect-fields [data-field=id] dd')?.innerText === '#{pk}'")
            checked.append((kind, pk, dict(page.evaluate(ROWS))))
            page.keyboard.press("Escape")
        for kind, pk, rows in checked:
            e = Event.objects.select_related("user").get(pk=pk)
            expected = {f: shown_value(e, f) for f in FIELDS}
            expected = {f: v for f, v in expected.items() if v is not None}
            show(f"inspector {kind} #{pk}: fields shown {list(rows)}")
            self.assertEqual(set(rows), set(expected), kind)
            for f, v in expected.items():
                if f == "confidence":
                    self.assertAlmostEqual(number(rows[f]), e.confidence * 100, delta=0.051)
                elif f == "size_mm":
                    self.assertAlmostEqual(number(rows[f]), e.size_mm, delta=0.051)
                else:
                    self.assertEqual(rows[f], str(v), f"{kind} {f}")
        det = body["detections"][0]
        show(f"fresh photo: crop canvas {crop[0]}x{crop[1]} with {crop[2]} painted pixels; probabilities shown {probs} vs response {det['probs']}")
        self.assertEqual(crop[:2], [224, 224])
        self.assertGreater(crop[2], 224 * 224 * 0.9)
        for name, text in probs:
            key = next(k for k, v in CLASSES.items() if v == name)
            self.assertAlmostEqual(number(text), det["probs"][key] * 100, delta=0.051)
        self.assertEqual(page.problems, [])

    def test_live_strip_counters_and_ring_reach_the_real_values(self):
        page = self.open()
        self.login(page)
        body, phases = self.analyze(page)
        det = body["detections"][0]
        facts = page.inner_text(".live-facts")
        shown = page.evaluate("({ conf: document.querySelector('.facts dd').childNodes[0].textContent.trim(), ms: document.querySelectorAll('.facts dd')[1].innerText, ring: document.querySelector('.verdict .ring').getAttribute('aria-label'), turn: getComputedStyle(document.querySelector('.verdict .ring-right svg')).transform })")
        show(f"phases {phases}; strip '{facts}'; response inference_ms {body['inference_ms']} confidence {det['confidence']:.4f}; counters {shown}")
        self.assertEqual([p for p in phases if p in ("enviando", "analisando", "concluido")][-1], "concluido")
        self.assertLess(phases.index("enviando"), phases.index("concluido"))
        self.assertAlmostEqual(number(re.search(r"Inferência ([\d.,]+) ms", facts).group(1)), body["inference_ms"], delta=0.051)
        self.assertAlmostEqual(number(shown["conf"]), det["confidence"] * 100, delta=0.051)
        self.assertAlmostEqual(number(shown["ms"].replace(" ms", "")), body["inference_ms"], delta=0.051)
        self.assertIn("Confiança do modelo", shown["ring"])
        self.assertEqual(page.problems, [])

    def test_what_if_counts_equal_an_independent_recomputation(self):
        page = self.open()
        self.login(page)
        page.goto(self.live_server_url + "/painel?source=demo")
        page.locator("#sec-whatif").scroll_into_view_if_needed()
        self.until(page, "!!document.querySelector('.whatif-table')", 60)
        rows = []
        for thr in ("0.5", "0.57", "0.8", "0.93", "1"):
            page.locator(".whatif-slider input").fill(thr)
            page.wait_for_timeout(500)
            got = dict(page.evaluate("[...document.querySelectorAll('.whatif-table tbody tr')].map((r) => [r.dataset.class, [Number(r.querySelector('.whatif-sim-n').dataset.value), r.querySelector('.whatif-sim-n').innerText, r.querySelector('.whatif-stored').innerText]])"))
            t = float(thr)
            qs = Event.objects.filter(is_demo=True, confidence__isnull=False)
            expected = {c: qs.filter(label=c, confidence__gte=t).count() for c in CLASSES}
            expected["revisar"] = qs.filter(confidence__lt=t).count()
            stored = {c: qs.filter(label=c, needs_review=False).count() for c in CLASSES}
            stored["revisar"] = qs.filter(needs_review=True).count()
            rows.append((thr, got, expected))
            for c, n in expected.items():
                self.assertEqual(got[c][0], n, f"{thr} {c}")
                self.assertTrue(got[c][1].startswith(f"{n:,}".replace(",", ".")), f"{thr} {c} {got[c][1]}")
                self.assertTrue(got[c][2].startswith(f"{stored[c]:,}".replace(",", ".")), f"stored {c}")
        labels = page.evaluate("[document.querySelector('.whatif .chip[data-state=simulacao]')?.innerText, document.querySelector('.whatif-sim').innerText, document.querySelector('.whatif-real').innerText, document.querySelector('.whatif-value').innerText]")
        missing = Event.objects.filter(is_demo=True, confidence__isnull=True).count()
        for thr, got, expected in rows:
            show(f"what-if {thr:5s} page {{{', '.join(f'{c}: {v[0]}' for c, v in got.items())}}} = ORM {expected}")
        show(f"labels {labels}; events without confidence (outside the simulation) {missing}")
        self.assertEqual(labels[0].lower(), "simulação")
        self.assertIn("Simulação sobre dados salvos", labels[1])
        self.assertIn("nenhum", labels[2])
        self.assertIn(f"{missing:,}".replace(",", "."), page.inner_text(".whatif"))
        self.assertEqual(page.problems, [])

    def test_lot_replay_ends_at_the_static_lot_totals(self):
        page = self.open()
        self.login(page)
        self.until(page, "document.querySelectorAll('.lots tbody tr').length > 0", 60)
        rows = page.evaluate("[...document.querySelectorAll('.lots tbody tr')].map((r) => [r.querySelector('th').childNodes[0].textContent.trim(), r.querySelectorAll('td')[0].innerText, r.querySelectorAll('td')[1].innerText.split(' ')[0], r.querySelectorAll('td')[2].innerText])")
        checked = []
        for i, (lot, n, rotten, poor) in enumerate(rows[:3]):
            page.locator(".lot-replay").nth(i).click()
            page.wait_for_selector(".replay-counts")
            mid = page.evaluate("Number(document.querySelector('.replay-scrub input').max)")
            page.locator(".replay-scrub input").fill(str(mid // 2))
            half = page.evaluate("[...document.querySelectorAll('.replay-counts strong')].map((s) => s.innerText)")
            page.locator(".replay-scrub input").fill(str(mid))
            page.wait_for_timeout(200)
            end = dict(page.evaluate("[...document.querySelectorAll('.replay-counts li')].map((l) => [l.dataset.cat, Number(l.querySelector('strong').innerText.replace(/\\./g, ''))])"))
            share = page.inner_text(".replay-share")
            decided = end["boa"] + end["baixa_qualidade"] + end["podre"]
            checked.append((lot, n, rotten, poor, end, share, half))
            self.assertEqual(sum(end.values()), int(n.replace(".", "")), lot)
            self.assertEqual(share, rotten, lot)
            self.assertAlmostEqual(end["baixa_qualidade"] / decided * 100, number(poor), delta=0.051)
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        for row in checked:
            show(f"replay {row[0]}: table n {row[1]}, podres {row[2]}, baixa {row[3]} | replay at half {row[6]}, at end {row[4]}, podres {row[5]}")
        self.assertGreaterEqual(len(checked), 1)
        self.assertEqual(page.problems, [])

    def test_drill_down_lists_the_fruits_behind_the_bar(self):
        page = self.open()
        self.login(page)
        page.goto(self.live_server_url + "/painel?source=demo")
        box = page.locator("[data-stat=fruits] canvas").first
        box.scroll_into_view_if_needed()
        self.until(page, "!!document.querySelector('[data-stat=fruits] .chart-frame.shown')", 60)
        page.wait_for_timeout(1200)
        bb = box.bounding_box()
        hit = None
        for fy in (0.1, 0.18, 0.26, 0.34, 0.42, 0.5, 0.58, 0.66):
            for fx in (0.4, 0.55):
                page.mouse.move(bb["x"] + bb["width"] * fx, bb["y"] + bb["height"] * fy)
                page.wait_for_timeout(120)
                if page.evaluate("getComputedStyle(document.querySelector('[data-stat=fruits] canvas')).cursor") == "pointer":
                    hit = (fx, fy)
                    break
            if hit:
                break
        self.assertIsNotNone(hit)
        page.mouse.click(bb["x"] + bb["width"] * hit[0], bb["y"] + bb["height"] * hit[1])
        page.wait_for_selector(".drill .hint")
        title = page.inner_text(".sheet-head h2")
        total = page.inner_text(".drill .hint")
        fruit = next(k for k, v in FRUITS.items() if title.endswith(v))
        expected = Event.objects.filter(is_demo=True, fruit_type=fruit, needs_review=False).count()
        line = page.evaluate("(() => { const l = document.querySelector('.drill-line'); return l && !l.hidden && l.getBoundingClientRect().width; })()")
        show(f"drill on '{title}': '{total}'; ORM count {expected}; connector drawn {bool(line)}")
        self.assertTrue(total.startswith(f"{expected:,}".replace(",", ".")))
        self.assertTrue(line)
        self.assertEqual(page.problems, [])

    def test_every_number_can_be_traced(self):
        page = self.open()
        self.login(page)
        self.until(page, "document.querySelectorAll('.kpi-value').length > 0", 60)
        found = {}
        for path, selector in (("/", ".kpi-value"), ("/painel?source=demo", "[data-stat] > .badges .n-badge"), ("/painel?source=demo", ".whatif-sim-n"), ("/historico?source=all", ".history-total")):
            page.goto(self.live_server_url + path)
            self.until(page, f"document.querySelectorAll({selector!r}).length > 0 && [...document.querySelectorAll({selector!r})].every((e) => e.dataset.trace)", 60)
            el = page.locator(selector).first
            el.focus()
            tip = page.evaluate("(() => { const t = document.getElementById('trace-tip'); return t && !t.hidden ? [t.innerText, document.activeElement.getAttribute('aria-describedby')] : null; })()")
            found[f"{path} {selector}"] = (page.evaluate(f"document.querySelectorAll({selector!r}).length"), tip)
        for k, (n, tip) in found.items():
            show(f"trace {k}: {n} elements; focus shows {tip}")
        for n, tip in found.values():
            self.assertTrue(tip and tip[0].startswith("Fonte:") and tip[1] == "trace-tip")
        self.assertEqual(page.problems, [])

    def test_both_themes_pass_axe_and_pick_the_matching_logo(self):
        results, logos = [], {}
        for theme in ("dark", "light"):
            page = self.open(theme=theme, bypass_csp=True)
            for path in ["/login", "/", "/inspecao", "/painel?source=demo", "/historico?source=all", "/historico", "/como-funciona", "/creditos"]:
                if path == "/":
                    self.login(page)
                page.goto(self.live_server_url + path)
                self.settle(page)
                self.scroll_through(page)
                for _ in range(60):
                    if not page.evaluate("(() => { const el = document.querySelector('[data-state=playing]'); el?.scrollIntoView({ block: 'center' }); return !!el; })()"):
                        break
                    page.wait_for_timeout(300)
                page.add_script_tag(path=str(AXE))
                found = page.evaluate("""async () => { const r = await axe.run(document, { resultTypes: ['violations'] }); return r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0] && v.nodes[0].target.join(' ') })); }""")
                results.append((theme, path, found))
            read = """() => { const img = document.querySelector('.topbar img'); const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; const g = c.getContext('2d'); g.drawImage(img, 0, 0); const p = g.getImageData(2, 2, 1, 1).data; return { variant: img.dataset.variant, corner: `rgb(${p[0]}, ${p[1]}, ${p[2]})`, bar: getComputedStyle(document.querySelector('.topbar')).backgroundColor, footer: document.querySelector('.site-footer img').dataset.variant, html: document.documentElement.dataset.theme || 'dark' }; }"""
            logos[theme] = page.evaluate(read)
        page = self.open()
        self.login(page)
        page.click(".topbar-tools .icon-btn >> nth=0")
        page.wait_for_timeout(200)
        toggled = page.evaluate("[document.documentElement.dataset.theme, localStorage.getItem('fruitcam-theme'), document.querySelector('.topbar img').dataset.variant]")
        page.reload()
        self.settle(page)
        kept = page.evaluate("document.documentElement.dataset.theme")
        bad = [(th, p, v) for th, p, f in results for v in f if v["impact"] in ("serious", "critical")]
        for th, p, f in results:
            show(f"axe {th:5s} {p:24s} " + (", ".join(f"{v['id']} ({v['impact']}, {v['nodes']})" for v in f) or "no violations"))
        show(f"logos {logos}; toggle -> {toggled}; after reload {kept}")
        self.assertEqual(bad, [])
        self.assertEqual((logos["dark"]["variant"], logos["light"]["variant"]), ("on-dark", "on-light"))
        self.assertTrue(all(l["corner"] == l["bar"] and l["footer"] == "on-dark" for l in logos.values()))
        self.assertEqual(toggled, ["light", "light", "on-light"])
        self.assertEqual(kept, "light")

    def test_reduce_motion_toggle_stops_animation_and_shows_posters(self):
        report = []
        page = self.open(motion="reduced")
        page.goto(self.live_server_url + "/login")
        self.settle(page)
        report.append(("/login", page.evaluate(NOT_RUNNING), page.evaluate("document.querySelectorAll('video').length")))
        self.login(page)
        for path in ("/", "/inspecao", "/painel?source=demo", "/historico", "/como-funciona"):
            page.goto(self.live_server_url + path)
            self.settle(page)
            self.scroll_through(page)
            report.append((path, page.evaluate(NOT_RUNNING), page.evaluate("document.querySelectorAll('video').length")))
        live = self.open()
        self.login(live)
        self.until(live, "!!document.querySelector('[data-bg] video')")
        before = live.evaluate("[document.querySelectorAll('video').length, document.querySelector('[data-bg]').dataset.mode]")
        live.click(".motion-btn")
        live.wait_for_timeout(400)
        after = live.evaluate("[document.querySelectorAll('video').length, document.querySelector('[data-bg]').dataset.mode, document.documentElement.dataset.motion, document.querySelector('.motion-btn').getAttribute('aria-pressed')]")
        running = live.evaluate(NOT_RUNNING)
        for row in report:
            show(f"toggle on {row[0]:22s} running animations {row[1]}, <video> {row[2]}")
        show(f"live toggle on /: before {before}; after {after}; running animations after {running}")
        self.assertTrue(all(r[1] == [] and r[2] == 0 for r in report))
        self.assertEqual(before[1], "video")
        self.assertEqual(after, [0, "poster", "reduced", "true"])
        self.assertEqual(running, [])

    def test_videos_have_posters_captions_transcripts_and_keyboard_controls(self):
        page = self.open()
        self.login(page)
        rows = []
        for path in ("/historico", "/como-funciona"):
            page.goto(self.live_server_url + path)
            self.settle(page)
            fig = page.locator("[data-video]").first
            fig.scroll_into_view_if_needed()
            self.until(page, "!!document.querySelector('[data-video] video[poster]')")
            toggle = page.locator("[data-video] .video-toggle").first
            toggle.focus()
            self.until(page, "document.querySelector('[data-video] video').currentTime > 0.2", 20)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
            info = page.evaluate("(() => { const f = document.querySelector('[data-video]'); const v = f.querySelector('video'); return { id: f.dataset.video, poster: v.getAttribute('poster'), muted: v.muted, track: !!v.querySelector('track[kind=captions]'), transcript: f.querySelectorAll('.transcript li').length, paused: v.paused, pressed: f.querySelector('.video-toggle').getAttribute('aria-pressed'), badge: f.querySelector('.illustrative').textContent.trim() }; })()")
            rows.append((path, info))
        page.goto(self.live_server_url + "/")
        self.settle(page)
        bg = page.locator(".bg-toggle")
        bg.focus()
        self.until(page, "!document.querySelector('[data-bg] video').paused", 20)
        page.keyboard.press("Space")
        page.wait_for_timeout(300)
        background = page.evaluate("[document.querySelector('[data-bg] video').paused, document.querySelector('.bg-toggle').getAttribute('aria-pressed'), document.querySelector('.bg-toggle').getAttribute('aria-label')]")
        alts = {}
        for path in ("/login", "/", "/inspecao", "/painel?source=demo", "/historico", "/como-funciona", "/creditos"):
            page.goto(self.live_server_url + path)
            self.settle(page)
            self.scroll_through(page)
            alts[path] = page.evaluate("[document.images.length, [...document.images].filter((i) => !(i.getAttribute('alt') || '').trim()).map((i) => i.src)]")
        for path, info in rows:
            show(f"video on {path}: {info}")
        show(f"background video after Space on its pause button: paused {background[0]}, aria-pressed {background[1]}, label '{background[2]}'")
        for path, (n, missing) in alts.items():
            show(f"images on {path:22s} {n:3d}, without alt text {missing}")
        for _, info in rows:
            self.assertTrue(info["poster"] and info["muted"] and info["track"] and info["transcript"] >= 3)
            self.assertTrue(info["paused"])
            self.assertEqual(info["pressed"], "false")
        self.assertEqual(rows[0][1]["badge"], "Gravação do app real · foto real")
        self.assertEqual(background[:2], [True, "true"])
        self.assertTrue(all(not missing for _, missing in alts.values()))
        self.assertEqual(page.problems, [])

    def test_history_and_panels_fit_360px(self):
        page = self.open(width=360, height=780)
        self.login(page)
        rows = []
        page.goto(self.live_server_url + "/historico?source=all")
        page.wait_for_selector(".history-table tbody tr")
        rows.append(("historico", page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")))
        page.locator(".history-table tbody input[type=checkbox]").nth(0).check()
        page.locator(".history-table tbody input[type=checkbox]").nth(1).check()
        summary = page.inner_text(".history-selected")
        with page.expect_download() as dl:
            page.click("text=Exportar CSV")
        csv = Path(dl.value.path()).read_text(encoding="utf-8-sig").splitlines()
        page.locator(".history-table tbody .row-open").first.click()
        page.wait_for_selector(".inspect-fields")
        rows.append(("inspetor", page.evaluate("[document.documentElement.scrollWidth - document.documentElement.clientWidth, Math.round(document.querySelector('.sheet').getBoundingClientRect().width)]")))
        page.keyboard.press("Escape")
        page.keyboard.press("Control+k")
        page.wait_for_selector(".cmd-input")
        rows.append(("comandos", page.evaluate("[document.documentElement.scrollWidth - document.documentElement.clientWidth, Math.round(document.querySelector('.cmd-box').getBoundingClientRect().right)]")))
        page.keyboard.press("Escape")
        show(f"360px: {rows}; selection '{summary}'; CSV {len(csv)} lines, header {csv[0][:60]}…")
        self.assertEqual(rows[0][1], 0)
        self.assertEqual(rows[1][1][0], 0)
        self.assertLessEqual(rows[1][1][1], 360)
        self.assertEqual(rows[2][1][0], 0)
        self.assertLessEqual(rows[2][1][1], 360)
        self.assertEqual(len(csv), 3)
        self.assertTrue(csv[0].startswith("id;timestamp;sector"))
        self.assertIn("2 selecionados", summary)
