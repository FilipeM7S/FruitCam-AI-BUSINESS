import io
import re
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import LiveServerTestCase, SimpleTestCase, override_settings
from PIL import Image

from core.test_dashboard import SerialLiveServerThread
from core.test_media import NET, NOT_RUNNING, WATCH, Direct
from core.tests import PASSWORD, show

ROOT = settings.BASE_DIR
CSS = (ROOT / "frontend" / "src" / "style.css").read_text(encoding="utf-8")
AXE = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
PHOTO = ROOT / "media_src" / "commons" / "caju-vermelho.jpg"
AFTER = ROOT / "docs" / "layout" / "after"
ROUTES = ["/", "/inspecao", "/painel", "/como-funciona", "/creditos"]
PAGES = ["/login", *ROUTES]
SHOTS = ["login", "linha", "inspecao", "inspecao-resultado", "painel", "como-funciona", "creditos"]
WIDTHS = (360, 768, 1280)
TITLES = {"/": "Linha de inspeção", "/inspecao": "Inspeção por foto", "/painel": "Painel estatístico", "/como-funciona": "Como funciona", "/creditos": "Créditos e licenças"}
STATS = {"overview": "sec-overview", "deformity": "sec-now", "fruits": "sec-now", "growth-good": "sec-trends", "growth-rotten": "sec-trends", "recurring": "sec-trends", "gaussian": "sec-distributions", "forecast": "sec-forecast"}
SCALE = [2, 4, 6, 8, 12, 16, 20, 24, 32, 48, 64]
RECT = "(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; }"


class LayoutTokenTests(SimpleTestCase):
    def test_spacing_and_widths_come_from_tokens(self):
        start = CSS.index(":root {")
        root = CSS[start:CSS.index("}", start)]
        scale = [int(v) for _, v in sorted(((int(k), v) for k, v in re.findall(r"--space-(\d+):\s*(\d+)px;", root)))]
        names = set(re.findall(r"--([a-z0-9-]+):", root))
        raw_spacing = re.findall(r"^\s*(?:padding|margin|gap|row-gap|column-gap)(?:-[a-z-]+)?\s*:[^;]*\d+px[^;]*;", CSS, re.M)
        content_widths = re.findall(r"max-width:\s*(\d+)px", CSS)
        show(f"spacing scale {scale}; layout tokens present: {sorted(n for n in names if not n.startswith(('space-', 'surface', 'primary', 'good', 'poor', 'rotten', 'review', 'accent', 'warn', 'danger', 'border', 'bg', 'text', 'muted', 'link', 'focus', 'brand', 'on-', 'font', 'radius', 'shadow')))}")
        show(f"spacing declarations with raw px: {len(raw_spacing)}; remaining px max-widths: {content_widths}")
        self.assertEqual(scale, SCALE)
        self.assertTrue({"content-max", "form-max", "thumb", "topbar-h", "bottombar-h", "rail-w", "sidebar-w", "nav-w", "page-x", "card-pad", "gap", "section-gap", "cols", "hairline"} <= names)
        self.assertEqual(raw_spacing, [])
        self.assertEqual(content_widths, [])
        for selector, prop, token in ((".page", "max-width", "var(--content-max)"), (".page", "padding", "var(--page-x)"), (".card", "padding", "var(--card-pad)"), (".cards", "gap", "var(--gap)"), (".grid-12", "gap", "var(--gap)"), (".section", "margin-top", "var(--section-gap)")):
            block = re.search(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", CSS).group(1)
            self.assertIn(token, re.search(rf"(?m)^\s*{prop}:\s*([^;]+);", block).group(1), f"{selector} {prop}")

    def test_only_the_four_breakpoints_are_used(self):
        queries = re.findall(r"@media\s*([^{]+)\{", CSS)
        widths = sorted({int(w) for q in queries for w in re.findall(r"min-width:\s*(\d+)px", q)})
        other = [q.strip() for q in queries if "min-width" not in q]
        show(f"min-width breakpoints {widths}; other media queries {other}")
        self.assertEqual(widths, [768, 1024, 1280])
        self.assertEqual(sorted(other), ["(prefers-reduced-motion: reduce)", "print"])
        self.assertFalse(re.search(r"max-width:\s*\d+px\)", "".join(queries)))

    def test_screenshots_exist_for_every_page_and_width(self):
        found = {}
        for name in SHOTS:
            for width in WIDTHS:
                path = AFTER / f"{name}-{width}.jpg"
                found[path.name] = Image.open(path).size if path.exists() else None
        show(f"{sum(1 for v in found.values() if v)} of {len(found)} screenshots in docs/layout/after; widths {sorted({v[0] for v in found.values() if v})}")
        self.assertTrue(all(found.values()), [k for k, v in found.items() if not v])
        self.assertTrue(all(v[0] == int(k.rsplit("-", 1)[1][:-4]) for k, v in found.items()))


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, UPLOAD_DIR=Path(tempfile.mkdtemp(prefix="fruitcam_layout_test_")))
class LayoutBrowserTests(LiveServerTestCase):
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
        call_command("seed_demo", "--weeks", "30", "--fruits-per-week", "60", stdout=io.StringIO())
        call_command("seed_line_demo", "--hours", "2", stdout=io.StringIO())

    def open(self, width, height=900, reduced=True, bypass_csp=False):
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce" if reduced else "no-preference", color_scheme="dark", bypass_csp=bypass_csp)
        ctx.add_init_script(WATCH)
        ctx.add_init_script(NET % "false")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.problems = []
        page.on("pageerror", lambda e: page.problems.append(str(e)))
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
        page.wait_for_selector(".hero")
        self.settle(page)

    def scroll_through(self, page):
        height = page.evaluate("document.documentElement.scrollHeight")
        for y in range(0, height + 900, 400):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(60)

    def demo_dashboard(self, page):
        page.goto(self.live_server_url + "/painel")
        page.wait_for_selector("[data-stat]")
        page.select_option("select >> nth=1", "demo")
        self.until(page, "!document.querySelector('.skeleton, .card.refreshing') && document.querySelectorAll('[data-stat] .demo-tag').length >= 8", 90)
        self.scroll_through(page)
        self.until(page, "[...document.querySelectorAll('[data-stat]')].every((c) => c.querySelector('canvas') || c.querySelector('.chart-empty, .empty'))", 60)
        page.evaluate("window.scrollTo(0, 0)")

    def test_no_horizontal_overflow_on_any_page(self):
        rows = []
        for width in WIDTHS:
            page = self.open(width)
            for path in PAGES:
                if path == "/":
                    self.login(page)
                page.goto(self.live_server_url + path)
                self.settle(page)
                self.scroll_through(page)
                m = page.evaluate("({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth })")
                rows.append((width, path, m))
        for width, path, m in rows:
            show(f"{width:5d}px {path:15s} scrollWidth {m['scroll']} clientWidth {m['client']}")
        for width, path, m in rows:
            self.assertLessEqual(m["scroll"], m["client"], f"{width} {path}")

    def test_every_route_is_reachable_from_the_navigation(self):
        modes = {}
        for width in (360, 1024, 1280):
            page = self.open(width)
            self.login(page)
            nav = page.evaluate(RECT, "nav.nav")
            hrefs = page.evaluate("[...document.querySelectorAll('nav.nav a')].map((a) => new URL(a.href).pathname)")
            visited = []
            for i, href in enumerate(hrefs):
                link = page.locator("nav.nav a").nth(i)
                link.click()
                page.wait_for_url(self.live_server_url + href)
                self.until(page, f"document.querySelector('main h1')?.innerText.trim() === {TITLES[href]!r}")
                state = page.evaluate("(i) => { const a = document.querySelectorAll('nav.nav a')[i]; const r = a.getBoundingClientRect(); return { current: a.getAttribute('aria-current'), inView: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, h1: document.querySelector('main h1').innerText.trim() }; }", i)
                visited.append((href, state))
            labels = page.evaluate("[...document.querySelectorAll('.nav-group-label')].filter((l) => l.offsetParent).map((l) => l.textContent.trim())")
            modes[width] = {"nav": nav, "hrefs": hrefs, "visited": visited, "labels": labels, "inner": page.evaluate("[innerWidth, innerHeight]")}
        for width, m in modes.items():
            show(f"{width}px nav box left {m['nav']['left']:.0f} top {m['nav']['top']:.0f} width {m['nav']['width']:.0f} height {m['nav']['height']:.0f}; group labels {m['labels']}")
            for href, st in m["visited"]:
                show(f"   {href:15s} aria-current={st['current']} link in view={st['inView']} h1={st['h1']!r}")
        for width, m in modes.items():
            self.assertEqual(sorted(m["hrefs"]), sorted(ROUTES))
            self.assertTrue(all(st["current"] == "page" and st["inView"] and st["h1"] == TITLES[href] for href, st in m["visited"]), width)
        self.assertAlmostEqual(modes[360]["nav"]["bottom"], modes[360]["inner"][1], delta=1)
        self.assertAlmostEqual(modes[360]["nav"]["width"], 360, delta=1)
        self.assertAlmostEqual(modes[1024]["nav"]["width"], 88, delta=1)
        self.assertAlmostEqual(modes[1280]["nav"]["width"], 232, delta=1)
        self.assertEqual(modes[1280]["labels"], ["Operação", "Análise", "Sobre"])
        self.assertEqual(modes[360]["labels"], [])

    def test_skip_link_and_visible_focus_order(self):
        page = self.open(1280)
        self.login(page)
        page.goto(self.live_server_url + "/painel")
        self.settle(page)
        page.evaluate("document.activeElement.blur(); window.scrollTo(0, 0)")
        order = []
        for _ in range(9):
            page.keyboard.press("Tab")
            order.append(page.evaluate("(() => { const e = document.activeElement; const s = getComputedStyle(e); return { tag: e.tagName.toLowerCase(), cls: e.className && e.className.baseVal === undefined ? e.className : '', text: (e.innerText || '').trim().split('\\n')[0], outline: parseFloat(s.outlineWidth) || 0, visible: e.matches(':focus-visible') }; })()"))
        for _ in range(len(order) - 1):
            page.keyboard.press("Shift+Tab")
        skip = page.evaluate("document.activeElement.className")
        page.keyboard.press("Enter")
        main = page.evaluate("document.activeElement.id")
        for o in order:
            show(f"   {o['tag']:6s} {o['cls'][:28]:28s} {o['text'][:28]:28s} outline {o['outline']}px focus-visible {o['visible']}")
        show(f"Shift+Tab back to start -> {skip!r}; Enter on it -> focus on #{main}")
        self.assertEqual(order[0]["cls"], "skip")
        self.assertIn("brand", order[1]["cls"].split())
        self.assertIn("Sair", order[2]["text"])
        self.assertEqual([o["text"] for o in order[3:8]], ["Linha", "Inspeção por foto", "Painel", "Como funciona", "Créditos e licenças"])
        self.assertTrue(all(o["visible"] and o["outline"] > 0 for o in order))
        self.assertEqual(skip, "skip")
        self.assertEqual(main, "main")

    def test_dashboard_sections_cards_and_honesty_states(self):
        report = {}
        for width in (1280, 360):
            page = self.open(width)
            self.login(page)
            self.demo_dashboard(page)
            cards = page.evaluate("""() => [...document.querySelectorAll('[data-stat]')].map((c) => { const r = c.getBoundingClientRect(); return { stat: c.dataset.stat, section: c.closest('section.section').getAttribute('aria-labelledby'), left: r.left, top: r.top + scrollY, right: r.right, bottom: r.bottom + scrollY, width: r.width, canvases: [...c.querySelectorAll('canvas')].filter((v) => v.width > 0 && v.height > 0).length, empties: [...c.querySelectorAll('.chart-empty')].map((e) => e.innerText.trim()).filter(Boolean).length, demo: !!c.querySelector('.demo-tag'), n: c.querySelectorAll('.n-badge').length, warn: c.querySelectorAll('.small-tag, .unreliable-tag, .poor-tag').length }; })""")
            headings = page.evaluate("[...document.querySelectorAll('section.section > .section-head h2')].map((h) => h.innerText.trim())")
            grid = page.evaluate(RECT, "section.section .cards")
            badge = page.locator(".demo-badge").is_visible()
            page.evaluate("window.scrollTo(0, 2400)")
            page.wait_for_timeout(300)
            bar = page.evaluate(RECT, ".filter-bar")
            more = page.evaluate(RECT, ".filter-more")
            report[width] = {"cards": {c["stat"]: c for c in cards}, "headings": headings, "grid": grid, "badge": badge, "bar": bar, "more": more, "problems": page.problems}
        for width, r in report.items():
            show(f"{width}px sections {r['headings']}; page demo badge visible {r['badge']}; after scrolling 2400px: filter bar top {r['bar']['top']:.0f}px, more-filters top {r['more']['top']:.0f}px")
            for stat, c in r["cards"].items():
                show(f"   {stat:14s} section {c['section']:18s} x {c['left']:6.0f}-{c['right']:6.0f} y {c['top']:6.0f} canvases {c['canvases']:2d} empty states {c['empties']} demo {c['demo']} n-badges {c['n']} warnings {c['warn']}")
        for width, r in report.items():
            self.assertEqual(set(r["cards"]), set(STATS))
            self.assertEqual(r["headings"], ["Visão geral", "Qualidade agora", "Tendências", "Distribuições", "Previsão"])
            self.assertTrue(r["badge"])
            self.assertEqual(r["problems"], [])
            for stat, c in r["cards"].items():
                self.assertEqual(c["section"], STATS[stat])
                self.assertGreaterEqual(c["canvases"], 1, f"{width} {stat}")
                self.assertTrue(c["demo"], f"{width} {stat}")
                self.assertLessEqual(c["right"], width)
            self.assertGreaterEqual(r["cards"]["forecast"]["n"], 1)
            self.assertGreaterEqual(r["cards"]["gaussian"]["n"], 1)
            self.assertAlmostEqual(r["bar"]["top"], 68, delta=2)
            self.assertLess(r["more"]["bottom"], 0)
        wide = report[1280]["cards"]
        self.assertAlmostEqual(wide["deformity"]["top"], wide["fruits"]["top"], delta=2)
        self.assertGreater(wide["fruits"]["left"], wide["deformity"]["right"])
        self.assertAlmostEqual(wide["growth-good"]["top"], wide["growth-rotten"]["top"], delta=2)
        self.assertGreater(wide["growth-rotten"]["left"], wide["growth-good"]["right"])
        self.assertAlmostEqual(wide["overview"]["width"], report[1280]["grid"]["width"], delta=2)
        self.assertGreater(wide["recurring"]["top"], wide["growth-good"]["bottom"])
        narrow = report[360]["cards"]
        self.assertGreater(narrow["growth-rotten"]["top"], narrow["growth-good"]["bottom"])
        self.assertGreater(narrow["fruits"]["top"], narrow["deformity"]["bottom"])

    def test_inspection_result_beside_the_image_on_desktop_and_below_on_mobile(self):
        shapes = {}
        for width in (1280, 360):
            page = self.open(width)
            self.login(page)
            page.goto(self.live_server_url + "/inspecao")
            page.wait_for_selector(".fruit-card")
            page.locator(".fruit-card", has_text="Caju").click()
            page.fill("input[list=sector-list]", "Norte")
            page.locator("input[type=file]").first.set_input_files(str(PHOTO))
            page.wait_for_selector(".dropzone-preview img")
            page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
            page.wait_for_selector(".verdict")
            page.wait_for_timeout(600)
            shapes[width] = {"image": page.evaluate(RECT, ".analyze-grid .annotated"), "result": page.evaluate(RECT, ".analyze-grid .result"), "inside_form": page.evaluate("!!document.querySelector('.analyze-grid form .annotated')")}
        for width, s in shapes.items():
            show(f"{width}px image x {s['image']['left']:.0f}-{s['image']['right']:.0f} y {s['image']['top']:.0f}-{s['image']['bottom']:.0f}; result panel x {s['result']['left']:.0f}-{s['result']['right']:.0f} y {s['result']['top']:.0f}-{s['result']['bottom']:.0f}; image inside the photo card {s['inside_form']}")
        desk, mob = shapes[1280], shapes[360]
        self.assertTrue(desk["inside_form"] and mob["inside_form"])
        self.assertGreater(desk["result"]["left"], desk["image"]["right"])
        self.assertLess(desk["result"]["top"], desk["image"]["bottom"])
        self.assertGreater(mob["result"]["top"], mob["image"]["bottom"])

    def test_every_page_uses_the_page_header_pattern(self):
        rows = []
        for width in (360, 1280):
            page = self.open(width)
            self.login(page)
            for path in ROUTES:
                page.goto(self.live_server_url + path)
                self.settle(page)
                if path == "/painel":
                    page.select_option("select >> nth=1", "demo")
                    self.until(page, "!!document.querySelector('.demo-badge')", 60)
                info = page.evaluate("""() => { const h = document.querySelector('main header.page-head'); if (!h) return null; const r = h.getBoundingClientRect(); const a = h.querySelector('.page-head-actions'); const ar = a && a.getBoundingClientRect(); return { h1: !!h.querySelector('.page-head-text h1'), lead: !!h.querySelector('.page-head-text .lead'), first: document.querySelector('main header') === h, actions: a ? { right: r.right - ar.right, top: ar.top - r.top, below: ar.top >= h.querySelector('.page-head-text').getBoundingClientRect().bottom - 1 } : null }; }""")
                rows.append((width, path, info))
        for width, path, info in rows:
            show(f"{width}px {path:15s} {info}")
        for width, path, info in rows:
            self.assertTrue(info and info["h1"] and info["lead"] and info["first"], f"{width} {path}")
        for path in ("/", "/painel"):
            wide = next(info for w, p, info in rows if w == 1280 and p == path)
            narrow = next(info for w, p, info in rows if w == 360 and p == path)
            self.assertLess(wide["actions"]["right"], 40, path)
            self.assertFalse(wide["actions"]["below"], path)
            self.assertTrue(narrow["actions"]["below"], path)

    def test_axe_finds_no_serious_or_critical_issues(self):
        results = []
        for width in (1280, 360):
            page = self.open(width, bypass_csp=True)
            for path in PAGES:
                if path == "/":
                    self.login(page)
                page.goto(self.live_server_url + path)
                self.settle(page)
                if path == "/painel":
                    page.select_option("select >> nth=1", "demo")
                    self.until(page, "!document.querySelector('.skeleton, .card.refreshing')", 60)
                self.scroll_through(page)
                page.add_script_tag(path=str(AXE))
                found = page.evaluate("""async () => { const r = await axe.run(document, { resultTypes: ['violations'] }); return { version: axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0] && v.nodes[0].target.join(' ') })) }; }""")
                results.append((width, path, found))
        version = results[0][2]["version"]
        bad = [(w, p, v) for w, p, f in results for v in f["violations"] if v["impact"] in ("serious", "critical")]
        for w, p, f in results:
            show(f"axe {version} {w}px {p:15s} violations: " + (", ".join(f"{v['id']} ({v['impact']}, {v['nodes']})" for v in f["violations"]) or "none"))
        self.assertEqual(bad, [])

    def test_reduced_motion_keeps_every_page_still(self):
        page = self.open(1280, reduced=True)
        report = []
        page.goto(self.live_server_url + "/login")
        self.settle(page)
        report.append(("/login", page.evaluate(NOT_RUNNING)))
        self.login(page)
        for path in ROUTES:
            page.goto(self.live_server_url + path)
            self.settle(page)
            self.scroll_through(page)
            report.append((path, page.evaluate(NOT_RUNNING), page.evaluate("document.querySelectorAll('video').length")))
        for row in report:
            show(f"reduced motion {row[0]:15s} running animations {row[1]}" + (f", <video> elements {row[2]}" if len(row) > 2 else ""))
        self.assertTrue(all(row[1] == [] for row in report))
        self.assertTrue(all(row[2] == 0 for row in report[1:]))
