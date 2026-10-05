import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import LiveServerTestCase, SimpleTestCase, TestCase, override_settings
from PIL import Image

from core.test_dashboard import SerialLiveServerThread
from core.tests import PASSWORD, show

ROOT = settings.BASE_DIR
SRC = ROOT / "frontend" / "src"
PUBLIC = ROOT / "frontend" / "public"
DIST = settings.FRONTEND_DIST
PHOTO = ROOT / "media_src" / "commons" / "caju-vermelho.jpg"
MEDIA = json.loads((SRC / "media.json").read_text(encoding="utf-8"))["items"]
FIGURES = json.loads((SRC / "figures.json").read_text(encoding="utf-8"))
LICENSES = json.loads((SRC / "licenses.json").read_text(encoding="utf-8"))
BRAND = json.loads((SRC / "brand.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "brand" / "rules.json").read_text(encoding="utf-8"))
SOURCES = json.loads((ROOT / "media_src" / "sources.json").read_text(encoding="utf-8"))
CAPTIONS = json.loads((ROOT / "figures" / "captions.json").read_text(encoding="utf-8"))
DEMO = json.loads((ROOT / "media_src" / "video" / "demo.json").read_text(encoding="utf-8"))
ALLOWED = re.compile(r"^(CC0|Public domain|CC BY(-SA)? [0-9.]+)$")
TYPES = {".avif": "image/avif", ".webp": "image/webp", ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml", ".webm": "video/webm", ".mp4": "video/mp4", ".vtt": "text/vtt", ".ico": "image/x-icon", ".js": "text/javascript", ".css": "text/css", ".webmanifest": "application/manifest+json"}
COMPRESSIBLE = {".js", ".css", ".svg", ".webmanifest"}
IMMUTABLE = re.compile(settings.WHITENOISE_IMMUTABLE_FILE_TEST)
BUDGET_KB = {"/login": 900, "/": 550, "/inspecao": 190, "/painel": 210, "/como-funciona": 450, "/creditos": 125}
FULL_HOW_BUDGET_KB = 2300
NOT_RUNNING = "new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(document.getAnimations().filter((a) => a.playState === 'running').map((a) => a.animationName || (a.effect && a.effect.target && a.effect.target.className) || 'waapi')))))"
WEIGH = "[performance.getEntriesByType('navigation')[0], ...performance.getEntriesByType('resource')].reduce((s, e) => s + e.transferSize, 0)"
WATCH = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
"""
NET = "(() => { const c = { effectiveType: '4g', saveData: %s, downlink: 10, rtt: 50, addEventListener() {}, removeEventListener() {} }; Object.defineProperty(Navigator.prototype, 'connection', { configurable: true, get: () => c }); })()"


def referenced():
    paths = set()
    for item in MEDIA.values():
        if item.get("kind") == "video":
            paths |= {item["webm"], item["mp4"], item["captions"], item["posterSrc"]}
            continue
        if item.get("kind") == "background":
            paths |= {item["webm"], item["mp4"], item["posterSrc"]}
            continue
        paths.add(item["fallback"])
        for widths in item["sources"].values():
            paths |= {rel for _, rel in widths}
    for item in FIGURES["items"].values():
        paths |= {item["svg"], item["png"], item["web"]}
    for key in ("lockupOnLight", "lockupOnDark", "icon"):
        paths |= {BRAND[key]["src"], BRAND[key]["png"], *(r["src"] for r in BRAND[key]["renditions"])}
    paths |= {f"brand/{name}" for name in BRAND["derived"]} | {BRAND["og"]["src"], "manifest.webmanifest"}
    manifest = json.loads((PUBLIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    paths |= {icon["src"].removeprefix("/static/") for icon in manifest["icons"]}
    html = (DIST / "index.html").read_text(encoding="utf-8")
    paths |= set(re.findall(r'(?:href|src)="/static/([^"]+)"', html))
    for css in (DIST / "assets").glob("*.css"):
        paths |= set(re.findall(r"url\(/static/([^)]+)\)", css.read_text(encoding="utf-8")))
    return sorted(paths)


def visible_assets_have_credits(page):
    return page.evaluate("""(media) => [...document.querySelectorAll('[data-media], [data-bg]')].map((f) => [f, f.dataset.media || f.dataset.bg]).filter(([f, id]) => media[id] && media[id].illustrative && !(f.dataset.media && f.closest('[data-bg]'))).map(([f, id]) => {
      const asset = media[id].asset;
      const scope = f.querySelector('.illustrative') ? f : f.closest('fieldset, .guide, .video-figure, section');
      return { id, badge: !!(scope && scope.querySelector('.illustrative')), link: !!(scope && scope.querySelector(`a[href$="#${asset}"]`)) };
    })""", MEDIA)


class Direct:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        return self.application(environ, start_response)


class MediaManifestTests(SimpleTestCase):
    def test_every_published_file_has_a_license_entry_and_no_orphans(self):
        third = {e["id"]: e for e in LICENSES["third_party"]}
        first = {e["id"]: e for e in LICENSES["first_party"]}
        listed = {f for e in LICENSES["third_party"] + LICENSES["first_party"] for f in e["files"]}
        on_disk = {p.relative_to(PUBLIC).as_posix() for d in ("media", "figures", "brand") for p in (PUBLIC / d).rglob("*") if p.is_file()} | {"manifest.webmanifest"}
        show(f"files on disk under media/, figures/, brand/ + manifest: {len(on_disk)}; listed in licenses.json: {len(listed)}")
        show(f"third-party photos: {len(third)} -> " + ", ".join(f"{k} ({v['license']})" for k, v in third.items()))
        show(f"first-party entries: {sorted(first)}")
        self.assertEqual(sorted(on_disk - listed), [], "files without a license entry")
        self.assertEqual(sorted(listed - on_disk), [], "license entries pointing to missing files")
        for key, entry in third.items():
            with self.subTest(asset=key):
                self.assertIn(key, SOURCES)
                self.assertRegex(entry["license"], ALLOWED)
                for field in ("author", "license_url", "source_url", "file_url", "retrieved", "attribution_text", "modifications"):
                    self.assertTrue(entry[field], field)
                self.assertTrue(entry["source_url"].startswith("https://commons.wikimedia.org/wiki/File:"))
                self.assertTrue(entry["used_in"])
                self.assertIn(entry["license"], entry["attribution_text"])
                self.assertRegex(SOURCES[key]["original_sha1"], r"^[0-9a-f]{40}$")
                if SOURCES[key].get("kind") != "video":
                    with Image.open(ROOT / SOURCES[key]["master"]) as im:
                        self.assertLessEqual(max(im.size), 2560)
                        self.assertEqual(len(im.getexif()), 0, "master keeps EXIF metadata")
        shown = {i["asset"] for i in MEDIA.values() if i.get("illustrative")} | set(DEMO["contains"]) | {a for f in FIGURES["items"].values() for a in f["assets"]}
        shown |= {a for v in DEMO["stills"].values() for a in v} | set(DEMO["poster"])
        show(f"third-party assets visible anywhere (app, figures, video, stills): {sorted(shown)}")
        self.assertEqual(sorted(shown - set(third)), [])
        self.assertEqual(sorted(set(third) - shown), [], "licensed but unused")

    def test_alt_text_captions_and_data_labels(self):
        for key, item in MEDIA.items():
            with self.subTest(media=key):
                self.assertGreaterEqual(len(item["alt"]), 25)
                self.assertNotRegex(item["alt"], r"\.(jpg|png|webp|avif)\b")
                self.assertTrue(item["alt"][0].isupper())
                if item.get("illustrative"):
                    self.assertRegex(item["credit"], r"^(Foto|Vídeo): .+ · (CC0|domínio público|CC BY(-SA)? [0-9.]+) · Wikimedia Commons$")
        words = {"synthetic": "sintéticos", "example": "não são métrica", "schematic": "sem dados", "test": "desempenho em esteira real não avaliado", "simulation": "não é medição em esteira real"}
        for key, fig in FIGURES["items"].items():
            with self.subTest(figure=key):
                self.assertIn(words[fig["label"]], fig["caption"].lower())
                self.assertGreaterEqual(len(fig["alt"]), 60)
        video = MEDIA["demo"]
        cues = (PUBLIC / video["captions"]).read_text(encoding="utf-8").strip().split("\n\n")
        show(f"video: {video['width']}x{video['height']}, {len(cues) - 1} caption cues, {len(video['transcript'])} transcript lines, poster {video['posterSrc']}")
        self.assertEqual(cues[0], "WEBVTT")
        self.assertEqual(len(cues) - 1, len(video["transcript"]))
        self.assertTrue(video["alt"] and video["caption"])

    def test_brand_rules_have_one_source_and_every_logo_use_respects_them(self):
        self.assertEqual(BRAND["rules"], {"clearSpace": RULES["clearSpace"], "minInkHeightPx": RULES["minInkHeightPx"]})
        uses = []
        for vue in SRC.rglob("*.vue"):
            for tag in re.findall(r"<BrandLogo\b[^>]*>", vue.read_text(encoding="utf-8")):
                height = int(re.search(r':height="(\d+)"', tag).group(1)) if ":height=" in tag else 40
                kind = re.search(r'kind="(\w+)"', tag).group(1) if "kind=" in tag else "lockup"
                on = re.search(r'\bon="(\w+)"', tag).group(1) if " on=" in tag else "auto"
                surfaces = ["light", "dark"] if on == "auto" else [on]
                for surface in surfaces:
                    asset = BRAND["icon"] if kind == "icon" else BRAND["lockupOnDark" if surface == "dark" else "lockupOnLight"]
                    ink = height if kind == "icon" else height * asset["inkHeight"] / asset["height"]
                    uses.append((vue.name, kind, surface, height, round(ink, 1)))
                    self.assertGreaterEqual(ink, RULES["minInkHeightPx"][kind], f"{vue.name} {tag}")
        for u in uses:
            show(f"{u[0]:22s} {u[1]:6s} on {u[2]:5s} height {u[3]:3d}px -> ink {u[4]}px (min {RULES['minInkHeightPx'][u[1]]})")
        for key in ("lockupOnLight", "lockupOnDark"):
            bg = np.array([int(BRAND[key]["background"][i:i + 2], 16) for i in (1, 3, 5)])
            for rel in [BRAND[key]["src"], BRAND[key]["png"], *(r["src"] for r in BRAND[key]["renditions"])]:
                a = np.asarray(Image.open(PUBLIC / rel).convert("RGB")).astype(int)
                border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
                self.assertEqual(int(np.abs(border - bg).max()), 0, rel)
                ys, xs = np.nonzero(np.abs(a - bg).max(axis=2) > BRAND[key]["inkThreshold"])
                ink = ys.max() - ys.min() + 1
                margin = min(ys.min(), a.shape[0] - 1 - ys.max(), xs.min(), a.shape[1] - 1 - xs.max())
                show(f"{rel:32s} {a.shape[1]}x{a.shape[0]}  visible ink height {ink}px  smallest margin {margin}px  required {RULES['clearSpace'] * ink:.1f}px")
                self.assertGreaterEqual(margin + 1, RULES["clearSpace"] * ink, f"{rel}: clear space")
        show("every logo plate and rendition: border is exactly the page color and the visible ink keeps the clear space")

    def test_figures_regenerate_identically_and_carry_data_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = time.perf_counter()
            run = subprocess.run([sys.executable, str(ROOT / "figures" / "make_figures.py"), tmp], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            show(f"regenerated 6 figures in {time.perf_counter() - start:.0f} s")
            for name, fig in FIGURES["items"].items():
                fresh = np.asarray(Image.open(Path(tmp) / f"{name}.png").convert("RGB")).astype(float)
                kept = np.asarray(Image.open(ROOT / "figures" / "out" / f"{name}.png").convert("RGB")).astype(float)
                self.assertEqual(fresh.shape, kept.shape)
                diff = np.abs(fresh - kept)
                same = float((diff.max(axis=2) == 0).mean())
                svg = (Path(tmp) / f"{name}.svg").read_text(encoding="utf-8")
                labels = sorted(set(re.findall(r'id="(\w+)-label"', svg)))
                show(f"{name:26s} {fresh.shape[1]}x{fresh.shape[0]} px  mean |diff| {diff.mean() / 255:.5f}  identical pixels {same:.4%}  svg label {labels}")
                self.assertLess(diff.mean() / 255, 0.001)
                self.assertGreater(same, 0.999)
                self.assertEqual(labels, [CAPTIONS[name]["label"]])
                for ext in ("svg", "png", "web"):
                    published = PUBLIC / fig[ext]
                    digest = hashlib.sha256(published.read_bytes()).hexdigest()[:10]
                    self.assertIn(f".{digest}.", published.name)
                self.assertEqual((PUBLIC / fig["svg"]).read_bytes(), (ROOT / "figures" / "out" / f"{name}.svg").read_bytes())


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class StaticDeliveryTests(TestCase):
    def test_every_referenced_asset_is_served_with_type_compression_and_cache_policy(self):
        paths = referenced()
        stats = {}
        for rel in paths:
            ext = Path(rel).suffix
            response = self.client.get(f"/static/{rel}", HTTP_ACCEPT_ENCODING="br, gzip")
            body = b"".join(response.streaming_content) if response.streaming else response.content
            response.close()
            raw = (DIST / rel).stat().st_size
            with self.subTest(path=rel):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith(TYPES[ext]), response["Content-Type"])
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                cache = response["Cache-Control"]
                if IMMUTABLE.match(f"/static/{rel}"):
                    self.assertIn("immutable", cache)
                    self.assertGreaterEqual(int(re.search(r"max-age=(\d+)", cache).group(1)), 31536000)
                else:
                    self.assertNotIn("immutable", cache)
                if ext in COMPRESSIBLE and raw >= 1024:
                    self.assertEqual(response.get("Content-Encoding"), "br")
            s = stats.setdefault(ext, [0, 0, 0, 0])
            s[0] += 1
            s[1] += raw
            s[2] += len(body)
            s[3] += int("immutable" in response["Cache-Control"])
        for ext, (n, raw, sent, immutable) in sorted(stats.items()):
            show(f"{ext:13s} {n:3d} files  on disk {raw / 1024:8.1f} KB  sent {sent / 1024:8.1f} KB  immutable {immutable}/{n}")
        show(f"{len(paths)} referenced static files checked")

    def test_html_has_csp_social_preview_icons_and_boot_splash(self):
        response = self.client.get("/login")
        html = response.content.decode()
        policy = dict(part.strip().split(" ", 1) for part in response["Content-Security-Policy"].split(";") if part.strip())
        show("CSP: " + response["Content-Security-Policy"])
        self.assertEqual(policy, {
            "default-src": "'self'", "script-src": "'self'", "style-src": "'self'", "img-src": "'self' data: blob:",
            "media-src": "'self'", "font-src": "'self'", "connect-src": "'self'", "manifest-src": "'self'",
            "worker-src": "'none'", "object-src": "'none'", "base-uri": "'self'", "form-action": "'self'", "frame-ancestors": "'none'",
        })
        self.assertNotIn("unsafe", response["Content-Security-Policy"])
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)[^>]*>")
        self.assertNotRegex(html, r"<style|\sstyle=")
        og = re.search(r'<meta property="og:image" content="([^"]+)"', html).group(1)
        show(f"og:image -> {og}")
        self.assertEqual(og, "http://testserver/static/brand/og-image.png")
        for needle in ('<meta name="theme-color" content="#14231e"', '<meta name="color-scheme" content="dark"', '<link rel="manifest" href="/static/manifest.webmanifest"', '<link rel="apple-touch-icon" href="/static/brand/apple-touch-icon.png"', 'id="boot"'):
            self.assertIn(needle, html)
        icon = self.client.get("/favicon.ico")
        self.assertEqual((icon.status_code, icon["Location"]), (301, "/static/brand/favicon.ico"))
        manifest = json.loads(b"".join(self.client.get("/static/manifest.webmanifest").streaming_content))
        show(f"manifest: {manifest['name']}, icons {[i['sizes'] + ' ' + i['purpose'] for i in manifest['icons']]}")
        with Image.open(PUBLIC / "brand" / "icon-maskable-512.png") as im:
            self.assertEqual(im.getpixel((0, 0))[3], 255)
        with Image.open(PUBLIC / "brand" / "icon-512.png") as im:
            self.assertEqual(im.getpixel((0, 0))[3], 0)


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, UPLOAD_DIR=Path(tempfile.mkdtemp(prefix="fruitcam_media_test_")))
class MediaBrowserTests(LiveServerTestCase):
    server_thread_class = SerialLiveServerThread
    static_handler = Direct

    @classmethod
    def setUpClass(cls):
        if not (DIST / "index.html").exists():
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

    def context(self, width=1366, height=860, reduced=False, scheme="dark", save_data=False):
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce" if reduced else "no-preference", color_scheme=scheme)
        ctx.add_init_script(WATCH)
        ctx.add_init_script(NET % ("true" if save_data else "false"))
        self.addCleanup(ctx.close)
        return ctx

    def page(self, ctx):
        page = ctx.new_page()
        page.problems = []
        page.on("pageerror", lambda e: page.problems.append(f"pageerror {e}"))
        page.on("console", lambda m: page.problems.append(f"console {m.text}") if m.type == "error" and not m.location.get("url", "").endswith("/api/auth/me") else None)
        return page

    def until(self, page, js, timeout=30):
        deadline = time.time() + timeout
        while not page.evaluate(js):
            self.assertLess(time.time(), deadline, js)
            page.wait_for_timeout(80)

    def login(self, page):
        page.goto(self.live_server_url + "/login")
        page.fill("input[name=username]", "ana")
        page.fill("input[name=password]", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url(self.live_server_url + "/")
        page.wait_for_selector(".hero")

    def inspect(self, page):
        page.goto(self.live_server_url + "/inspecao")
        page.wait_for_selector(".guide")

    def settle(self, page):
        self.until(page, "!document.getElementById('boot') && [...document.images].every((i) => i.complete || i.loading === 'lazy')")

    def loaded(self, page):
        self.scroll_through(page)
        page.wait_for_load_state("networkidle")
        self.until(page, "[...document.images].every((i) => i.complete)")

    def analyze(self, page, hold=None):
        page.locator(".fruit-card", has_text="Caju").click()
        page.fill("input[list=sector-list]", "Norte")
        page.locator("input[type=file]").first.set_input_files(str(PHOTO))
        page.wait_for_selector(".dropzone-preview img")
        held = []
        if hold:
            page.route("**/api/analyze", lambda route: held.append(route))
        page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
        if hold:
            self.until(page, "!!document.querySelector('.scan-line')")
            hold()
            while not held:
                page.wait_for_timeout(50)
            held[0].continue_()
            page.unroute("**/api/analyze")
        page.wait_for_selector(".verdict")

    def scroll_through(self, page):
        height = page.evaluate("document.body.scrollHeight")
        for y in range(0, height + 900, 450):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(60)

    def test_pages_have_no_csp_violations_errors_or_missing_credits(self):
        ctx = self.context()
        page = self.page(ctx)
        visited = []
        page.goto(self.live_server_url + "/login")
        self.settle(page)
        visited.append(("/login", visible_assets_have_credits(page)))
        self.login(page)
        self.settle(page)
        self.loaded(page)
        visited.append(("/", visible_assets_have_credits(page)))
        self.inspect(page)
        self.settle(page)
        visited.append(("/inspecao", visible_assets_have_credits(page)))
        self.analyze(page)
        for path in ("/painel", "/como-funciona", "/creditos"):
            page.goto(self.live_server_url + path)
            self.settle(page)
            self.loaded(page)
            visited.append((path, visible_assets_have_credits(page)))
        csp = page.evaluate("window.__csp")
        for path, checks in visited:
            show(f"{path:15s} illustrative photos on page: {len(checks)}; with 'Imagem ilustrativa' badge: {sum(c['badge'] for c in checks)}; with credit link: {sum(c['link'] for c in checks)}")
            for c in checks:
                self.assertTrue(c["badge"] and c["link"], f"{path} {c}")
        show(f"CSP violations: {csp}; page errors/console errors: {page.problems}")
        self.assertEqual(csp, [])
        self.assertEqual(page.problems, [])
        self.assertEqual(page.evaluate("window.__csp"), [])

    def test_logo_is_the_dark_variant_and_blends_with_the_bar(self):
        ctx = self.context()
        page = self.page(ctx)
        self.login(page)
        self.settle(page)
        read = """(sel) => { const img = document.querySelector(sel); const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; const g = c.getContext('2d'); g.drawImage(img, 0, 0); const p = g.getImageData(2, 2, 1, 1).data; const bar = img.closest('.topbar, .site-footer'); return { variant: img.dataset.variant, src: img.currentSrc.split('/').pop(), corner: `rgb(${p[0]}, ${p[1]}, ${p[2]})`, bar: getComputedStyle(bar).backgroundColor }; }"""
        top = page.evaluate(read, ".topbar img")
        foot = page.evaluate(read, ".site-footer img")
        page_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        show(f"top bar: logo {top['variant']} ({top['src']}), corner {top['corner']} vs bar {top['bar']}; footer: {foot['variant']} corner {foot['corner']} vs {foot['bar']}; page {page_bg}")
        self.assertEqual((top["variant"], foot["variant"]), ("on-dark", "on-dark"))
        self.assertEqual(top["corner"], top["bar"])
        self.assertEqual(foot["corner"], foot["bar"])
        self.assertEqual(page_bg, "rgb(20, 35, 30)")

    def test_user_guide_opens_from_the_question_mark_and_keyboard(self):
        ctx = self.context()
        page = self.page(ctx)
        self.login(page)
        self.settle(page)
        fab = page.evaluate("(() => { const b = document.querySelector('.help-fab'); const r = b.getBoundingClientRect(); return { text: b.textContent.trim(), label: b.getAttribute('aria-label'), w: r.width, right: innerWidth - r.right, bottom: innerHeight - r.bottom, fixed: getComputedStyle(b).position }; })()")
        page.click(".help-fab")
        opened = page.evaluate("({ open: document.querySelector('dialog.help').open, modal: document.querySelector('dialog.help').matches(':modal'), focusInside: document.querySelector('dialog.help').contains(document.activeElement), sections: document.querySelectorAll('.help-section').length, title: document.getElementById('help-title').textContent })")
        where = "(id) => { const body = document.querySelector('.help-body'); const box = body.getBoundingClientRect(); const h = document.querySelector(`#${id} h3`).getBoundingClientRect(); return { scrolled: body.scrollTop > 0, top: Math.round(h.top - box.top), visible: h.top >= box.top && h.bottom <= box.bottom, focus: document.activeElement.closest('.help-section')?.id }; }"
        middle = page.evaluate("document.querySelectorAll('.help-section')[4].id")
        page.click(".help-toc a >> nth=4")
        jumped_middle = page.evaluate(where, middle)
        page.click(".help-toc a >> nth=8")
        jumped = page.evaluate(where, "help-limites")
        page.keyboard.press("Escape")
        closed = page.evaluate("({ open: document.querySelector('dialog.help').open, focusBack: document.activeElement === document.querySelector('.help-fab') })")
        page.keyboard.press("Shift+Slash")
        by_key = page.evaluate("document.querySelector('dialog.help').open")
        page.keyboard.press("Escape")
        page.goto(self.live_server_url + "/inspecao")
        page.wait_for_selector(".guide")
        page.click("input[list=sector-list]")
        page.keyboard.type("a?b")
        typed = page.evaluate("({ open: document.querySelector('dialog.help').open, value: document.querySelector('input[list=sector-list]').value })")
        for name, v in (("button", fab), ("opened", opened), ("jump to section 5", jumped_middle), ("jump to last", jumped), ("Esc", closed), ("key ?", by_key), ("typing in a field", typed)):
            show(f"{name:18s} {v}")
        self.assertEqual((fab["text"], fab["fixed"]), ("?", "fixed"))
        self.assertGreaterEqual(fab["w"], 48)
        self.assertTrue(fab["label"])
        self.assertEqual((opened["open"], opened["modal"], opened["focusInside"], opened["sections"]), (True, True, True, 9))
        self.assertTrue(jumped_middle["scrolled"] and jumped_middle["visible"])
        self.assertLess(abs(jumped_middle["top"]), 60)
        self.assertEqual(jumped_middle["focus"], middle)
        self.assertTrue(jumped["scrolled"] and jumped["visible"])
        self.assertEqual(jumped["focus"], "help-limites")
        self.assertEqual(closed, {"open": False, "focusBack": True})
        self.assertTrue(by_key)
        self.assertEqual(typed, {"open": False, "value": "a?b"})

    def test_reduced_motion_is_fully_static(self):
        ctx = self.context(reduced=True)
        page = self.page(ctx)
        report = []
        page.goto(self.live_server_url + "/login")
        self.settle(page)
        report.append(("/login", page.evaluate(NOT_RUNNING)))
        self.login(page)
        self.settle(page)
        line = page.evaluate("({ bg: [...document.querySelectorAll('[data-bg]')].map((b) => b.dataset.mode), videos: document.querySelectorAll('video').length })")
        report.append(("/ (linha)", page.evaluate(NOT_RUNNING)))
        self.inspect(page)
        self.analyze(page, hold=lambda: report.append(("/inspecao analyzing", page.evaluate(NOT_RUNNING))))
        page.wait_for_timeout(300)
        report.append(("/inspecao result", page.evaluate(NOT_RUNNING)))
        page.goto(self.live_server_url + "/como-funciona")
        self.settle(page)
        state = page.evaluate("({ pipeline: document.querySelector('.pipeline').dataset.state, hidden: document.querySelectorAll('.reveal:not(.revealed)').length, videos: document.querySelectorAll('video').length, mode: document.querySelector('[data-video]').dataset.mode })")
        report.append(("/como-funciona", page.evaluate(NOT_RUNNING)))
        self.loaded(page)
        same = []
        for selector in (".how-head", ".pipeline", ".figure-list", ".video-figure"):
            page.evaluate(f"window.scrollTo(0, document.querySelector('{selector}').getBoundingClientRect().top + window.scrollY - 90)")
            page.wait_for_timeout(150)
            first = page.screenshot()
            page.wait_for_timeout(700)
            same.append((selector, first == page.screenshot()))
        for path, running in report:
            show(f"reduced motion {path:20s} running animations: {running}")
        show(f"reduced motion /como-funciona: pipeline={state['pipeline']}, unrevealed blocks={state['hidden']}, <video> elements={state['videos']}, video mode={state['mode']}")
        show(f"reduced motion /como-funciona: viewport screenshots 0.7 s apart identical: {same}")
        show(f"reduced motion /: background media modes {line['bg']}, <video> elements {line['videos']}")
        self.assertEqual(line, {"bg": ["poster"], "videos": 0})
        self.assertTrue(all(running == [] for _, running in report))
        self.assertEqual(state, {"pipeline": "done", "hidden": 0, "videos": 0, "mode": "poster"})
        self.assertTrue(all(ok for _, ok in same))

    def test_save_data_shows_posters_instead_of_videos(self):
        ctx = self.context(save_data=True)
        page = self.page(ctx)
        page.goto(self.live_server_url + "/login")
        self.settle(page)
        login = page.evaluate("({ bg: [...document.querySelectorAll('[data-bg]')].map((b) => b.dataset.mode), videos: document.querySelectorAll('video').length })")
        self.login(page)
        self.settle(page)
        line = page.evaluate("({ bg: [...document.querySelectorAll('[data-bg]')].map((b) => b.dataset.mode), videos: document.querySelectorAll('video').length })")
        page.goto(self.live_server_url + "/como-funciona")
        self.settle(page)
        how = page.evaluate("({ mode: document.querySelector('[data-video]').dataset.mode, videos: document.querySelectorAll('video').length })")
        media = [e for e in page.evaluate("performance.getEntriesByType('resource').map((e) => e.name)") if e.endswith((".webm", ".mp4"))]
        show(f"Save-Data: /login {login}, / {line}, /como-funciona {how}, video files requested {media}")
        self.assertEqual(login, {"bg": ["poster"], "videos": 0})
        self.assertEqual(line, {"bg": ["poster"], "videos": 0})
        self.assertEqual(how, {"mode": "poster", "videos": 0})
        self.assertEqual(media, [])

    def test_scan_line_boxes_meter_pipeline_and_video_animate_when_allowed(self):
        ctx = self.context()
        page = self.page(ctx)
        self.login(page)
        self.settle(page)
        self.until(page, "!document.querySelector('[data-bg] video').paused")
        seen = {"hero_video": page.evaluate("(() => { const v = document.querySelector('[data-bg] video'); return { paused: v.paused, muted: v.muted, loop: v.loop, src: v.currentSrc.split('/').pop() }; })()")}
        page.locator(".cam-diagram").scroll_into_view_if_needed()
        seen["diagram"] = sorted({a.get("name") for a in page.evaluate("document.querySelector('.cam-diagram').getAnimations({ subtree: true }).filter((a) => a.playState === 'running').map((a) => ({ name: a.animationName }))")})
        self.inspect(page)
        self.analyze(page, hold=lambda: seen.update(scan=page.evaluate("document.querySelector('.scan-line').getAnimations().map((a) => [a.animationName, a.playState])"), skeleton=page.evaluate("document.querySelectorAll('.sk-result > span').length")))
        seen["result"] = page.evaluate("['.annotated .box', '.verdict', '.meter span'].map((s) => [s, document.querySelector(s).getAnimations().map((a) => a.animationName)])")
        seen["box_delay"] = page.evaluate("getComputedStyle(document.querySelector('.annotated .box')).animationDelay")
        seen["probs"] = page.evaluate("document.querySelectorAll('.prob-row .prob-bar span').length")
        page.goto(self.live_server_url + "/como-funciona")
        self.settle(page)
        page.locator(".pipeline").scroll_into_view_if_needed()
        self.until(page, "document.querySelector('.pipeline').getAnimations({ subtree: true }).some((a) => a.playState === 'running')")
        seen["pipeline_running"] = page.evaluate("document.querySelector('.pipeline').getAnimations({ subtree: true }).filter((a) => a.playState === 'running').length")
        self.until(page, "document.querySelector('.pipeline').dataset.state === 'done'", 15)
        video = page.locator("video")
        seen["preload"] = video.get_attribute("preload")
        seen["poster_before"] = page.evaluate("document.querySelector('video').getAttribute('poster')")
        video.scroll_into_view_if_needed()
        self.until(page, "!document.querySelector('video').paused && document.querySelector('video').currentTime > 0.3", 20)
        track = page.evaluate("(() => { const t = document.querySelector('video').textTracks[0]; return { mode: t.mode, lang: t.language, cues: t.cues ? t.cues.length : 0 }; })()")
        page.evaluate("window.scrollTo(0, 0)")
        self.until(page, "document.querySelector('video').paused")
        seen["track"] = track
        for k, v in seen.items():
            show(f"{k:16s} {v}")
        self.assertEqual((seen["hero_video"]["paused"], seen["hero_video"]["muted"], seen["hero_video"]["loop"]), (False, True, True))
        self.assertEqual(seen["diagram"], ["cam-move", "cam-tag", "cam-track"])
        self.assertEqual(seen["scan"], [["scan", "running"]])
        self.assertEqual(seen["skeleton"], 4)
        self.assertEqual(seen["result"], [[".annotated .box", ["box-in"]], [".verdict", ["pop"]], [".meter span", ["meter-in"]]])
        self.assertEqual(seen["probs"], 3)
        self.assertEqual(seen["box_delay"], "0.15s")
        self.assertGreaterEqual(seen["pipeline_running"], 1)
        self.assertEqual((seen["preload"], seen["poster_before"]), ("none", None))
        self.assertEqual((track["mode"], track["lang"]), ("showing", "pt-BR"))
        self.assertEqual(track["cues"], len(MEDIA["demo"]["transcript"]))

    def test_360px_layout_and_page_weight_budgets(self):
        cookies = None
        rows = []
        for width in (360, 1366):
            for path in BUDGET_KB:
                ctx = self.context(width=width, height=780)
                if path not in ("/login", "/como-funciona", "/creditos"):
                    if cookies is None:
                        boot = self.context(width=width)
                        p = self.page(boot)
                        self.login(p)
                        cookies = boot.cookies()
                    ctx.add_cookies(cookies)
                page = self.page(ctx)
                page.goto(self.live_server_url + path)
                page.wait_for_load_state("networkidle")
                self.settle(page)
                page.wait_for_timeout(1500)
                page.wait_for_load_state("networkidle")
                weight = page.evaluate(WEIGH)
                layout = page.evaluate("({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, unsized: [...document.images].filter((i) => !i.getAttribute('width') || !i.getAttribute('height')).length, nav: [...document.querySelectorAll('.nav a')].every((a) => a.getBoundingClientRect().right <= innerWidth) })")
                rows.append((width, path, weight / 1024, layout))
                if path == "/como-funciona":
                    self.loaded(page)
                    page.locator("video").scroll_into_view_if_needed()
                    self.until(page, "document.querySelector('video').currentTime > 0.3", 20)
                    page.wait_for_load_state("networkidle")
                    rows.append((width, "/como-funciona (tudo, com vídeo)", page.evaluate(WEIGH) / 1024, layout))
        for width, path, kb, layout in rows:
            budget = FULL_HOW_BUDGET_KB if "tudo" in path else BUDGET_KB[path]
            show(f"{width:5d}px {path:34s} {kb:7.1f} KB transferred (budget {budget} KB)  horizontal overflow {layout['overflow']}px  images without width/height {layout['unsized']}  nav fits {layout['nav']}")
            self.assertLessEqual(kb, budget, f"{width} {path}")
            self.assertEqual(layout["overflow"], 0, f"{width} {path}")
            self.assertEqual(layout["unsized"], 0, f"{width} {path}")
            self.assertTrue(layout["nav"], f"{width} {path}")
