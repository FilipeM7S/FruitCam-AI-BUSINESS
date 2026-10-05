import json
import os
import subprocess
import tempfile
import time

import numpy as np
import pandas as pd
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.core.servers.basehttp import WSGIServer
from django.test.testcases import LiveServerThread, QuietWSGIRequestHandler
from django.test import TestCase, override_settings

import fruit_analytics as FA
from test_fruit_analytics import demo_events, expand, gauss_events, month, trend_events, week

from core.models import Event
from core.tests import PASSWORD, insert, show, strict_json

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
FRONTEND = settings.BASE_DIR / "frontend"
STATS = ["overview", "deformity", "fruits", "growth-good", "growth-rotten", "recurring", "gaussian", "forecast"]


class SerialLiveServerThread(LiveServerThread):
    def _create_server(self, connections_override=None):
        return WSGIServer((self.host, self.port), QuietWSGIRequestHandler, allow_reuse_address=False)


def monthly(rows, seed=0):
    spec = []
    for m, sector, fruit, label, n in rows:
        start, days = month(m)
        spec.append((start, days, sector, fruit, label, n))
    return FA.to_events(expand(spec, np.random.default_rng(seed)))


def deformity_scenario():
    rng = np.random.default_rng(0)
    kinds = ["podre", "queimada", "quebrada"]
    truth, spec = [], []
    for w in range(20):
        if w == 12:
            truth.append("none")
            continue
        top = "tie" if w == 15 else "queimada" if w < 7 else "podre" if w < 14 else "quebrada"
        truth.append(top)
        n = [100, 100, 100] if w == 15 else rng.multinomial(300, [0.6 if k == top else 0.2 for k in kinds])
        spec += [(week(w), 7, "A", "caju", k, c) for k, c in zip(kinds, n)] + [(week(w), 7, "A", "caju", "nao_podre", 700)]
    return FA.to_events(expand(spec, rng)), {"dominant": truth, "empty": [12]}


class ChartDataTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.force_login(get_user_model().objects.create_user("ana", password=PASSWORD))

    def payload(self, name, events, **query):
        Event.objects.all().delete()
        insert(events)
        r = self.client.get(f"/api/stats/{name}", query)
        self.assertEqual(r.status_code, 200)
        return strict_json(r)

    def test_chart_data_matches_ground_truth(self):
        F = {}
        events, truth = deformity_scenario()
        F["deformity"] = {"payload": self.payload("deformity", events), "truth": truth}

        p = self.payload("forecast", trend_events(0))
        rising = next(s for s in p["sectors"] if s["sector"] == "rising")
        show(f"forecast payload: rising history_n = {sorted(set(rising['history_n']))} (expected [1000])")
        self.assertEqual(set(rising["history_n"]), {1000})
        F["forecast"] = {"payload": p, "truth": {"rising_next": 0.77, "line": [0.20 + 0.019 * w for w in range(30)], "n_week": 1000}}

        fruits = monthly([(0, "A", "caju", "nao_podre", 500), (0, "A", "castanha", "nao_podre", 300), (0, "A", "melao", "podre", 900), (1, "A", "caju", "nao_podre", 2000), (1, "A", "castanha", "podre", 100)])
        F["fruits"] = {"payload": self.payload("fruits", fruits), "truth": {"labels": ["caju", "melao", "castanha"], "values": [2500, 900, 400]}}
        F["fruits_tie"] = {"payload": self.payload("fruits", monthly([(0, "A", "caju", "nao_podre", 500), (0, "A", "castanha", "nao_podre", 500), (0, "A", "melao", "podre", 100)]))}

        rate = monthly([r for m in range(12) for r in ((m, "A", "caju", "nao_podre", round(2000 * 1.10 ** m)), (m, "A", "caju", "podre", round(500 * 1.20 ** m)))])
        F["growth"] = {"payload": self.payload("growth", rate, period="month")}
        zero = monthly([(0, "A", "caju", "nao_podre", 100), (2, "A", "caju", "nao_podre", 50), (2, "A", "caju", "podre", 20), (3, "A", "caju", "nao_podre", 60), (3, "A", "caju", "podre", 30)])
        F["growth_zero"] = {"payload": self.payload("growth", zero, period="month"), "truth": {"good_na": [0, 2], "rotten_na": [0, 1, 2]}}

        good_l, rot_l = {1: 1200, 2: 1440, 3: 1728}, {7: 130, 8: 169, 9: 220}
        rows = []
        for m in range(36):
            calendar = month(m)[0].month
            rows += [(m, "A", "caju", "nao_podre", good_l.get(calendar, 1000)), (m, "A", "caju", "podre", rot_l.get(calendar, 100))]
        F["recurring"] = {
            "payload": self.payload("recurring", monthly(rows)),
            "truth": {"month_peak_rotten": "9", "month_peak_rotten_value": 220 / 169 - 1, "month_peak_good": "1", "season_peak_good": "summer", "season_peak_good_value": 4368 / 3000 - 1, "season_peak_rotten": "winter", "season_peak_rotten_value": 519 / 300 - 1},
        }

        n = 200
        eff = lambda mu, sd: float(np.sqrt(sd ** 2 + (mu * (1 - mu) - sd ** 2) / n))
        F["gaussian"] = {"payload": self.payload("gaussian", gauss_events(0, n=n)), "truth": {"A": {"mu": 0.20, "sd_eff": eff(0.20, 0.04)}, "B": {"mu": 0.35, "sd_eff": eff(0.35, 0.06)}}}

        ov = monthly([r for m in range(3) for r in ((m, "A", "caju", "nao_podre", 900), (m, "A", "caju", "podre", 100), (m, "B", "caju", "nao_podre", 700), (m, "B", "caju", "podre", 300))])
        p = self.payload("overview", ov, period="month")
        show(f"overview payload sectors = {p['sectors']}")
        self.assertEqual(p["sectors"], [{"sector": "A", "n": 3000, "rotten_rate": 0.1}, {"sector": "B", "n": 3000, "rotten_rate": 0.3}])
        F["overview"] = {"payload": p, "truth": {"rate": 0.2, "sectors": ["B", "A"], "sector_rates": [0.3, 0.1], "total": 6000}}

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(F, f)
        self.addCleanup(os.remove, f.name)
        run = subprocess.run(["node", "--test", "--test-reporter=spec", "tests/series.test.mjs"], cwd=FRONTEND, env={**os.environ, "FRUITCAM_FIXTURES": f.name}, capture_output=True, text=True, encoding="utf-8")
        print(run.stdout)
        print(run.stderr)
        self.assertEqual(run.returncode, 0)
        self.assertIn("pass 10", run.stdout)


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class DashboardBrowserTests(StaticLiveServerTestCase):
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

    def open(self, reduced=False, width=1366, height=900):
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce" if reduced else "no-preference")
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
        self.settle(page)
        return page

    def settle(self, page):
        deadline = time.time() + 90
        while page.evaluate("document.querySelectorAll('.skeleton, .card.refreshing').length") and time.time() < deadline:
            page.wait_for_timeout(100)

    def scroll_all(self, page):
        height = page.evaluate("document.body.scrollHeight")
        for y in range(0, height + 900, 450):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(70)
        page.wait_for_timeout(1600)

    def chart_area_shot(self, page, selector):
        return page.locator(selector).first.screenshot()

    def test_every_statistic_is_only_charts(self):
        insert(FA.to_events(demo_events(1, 30, 60)))
        page = self.open()
        lazy_before = page.evaluate("document.querySelectorAll('[data-stat=gaussian] .chart-frame.shown').length")
        self.scroll_all(page)
        report = page.evaluate("""() => [...document.querySelectorAll('[data-stat]')].map((c) => {
          const frames = [...c.querySelectorAll('.chart-frame')];
          return {
            stat: c.dataset.stat,
            canvases: c.querySelectorAll('.chart-frame canvas').length,
            tables: c.querySelectorAll('table, dl, ul, ol').length,
            paragraphs: [...c.querySelectorAll('p')].filter((p) => !p.closest('.chart-frame')).length,
            frames: frames.length,
            labelled: frames.filter((f) => f.getAttribute('role') === 'img' && f.tabIndex === 0 && (f.getAttribute('aria-label') || '').length > 20).length,
            overlays: c.querySelectorAll('.overlay').length,
            nBadge: !!c.querySelector('.n-badge'),
            how: !!c.querySelector('.how-btn:not([disabled])'),
            label: (frames[0] && frames[0].getAttribute('aria-label')) || '',
          };
        })""")
        lazy_after = page.evaluate("document.querySelectorAll('[data-stat=gaussian] .chart-frame.shown').length")
        show(f"gaussian charts created before scrolling = {lazy_before}, after scrolling = {lazy_after} (lazy render below the fold)")
        for r in report:
            show(f"{r['stat']:14s} canvases={r['canvases']} frames={r['frames']} labelled={r['labelled']} overlays={r['overlays']} tables/lists={r['tables']} text paragraphs={r['paragraphs']} n-badge={r['nBadge']} how-to={r['how']}")
            show(f"{'':14s} aria-label: {r['label'][:110]}")
        self.assertEqual(lazy_before, 0)
        self.assertEqual(lazy_after, 6)
        self.assertEqual([r["stat"] for r in report], STATS)
        for r in report:
            self.assertGreaterEqual(r["canvases"], 1, r["stat"])
            self.assertEqual(r["tables"], 0, r["stat"])
            self.assertLessEqual(r["paragraphs"], 1, r["stat"])
            self.assertEqual(r["labelled"], r["frames"], r["stat"])
            self.assertGreaterEqual(r["overlays"], 1, r["stat"])
            self.assertTrue(r["nBadge"] and r["how"], r["stat"])
        self.assertEqual(page.evaluate("document.querySelectorAll('main table, main dl').length"), 0)
        self.assertEqual(self.errors, [])

    def test_empty_database_shows_designed_empty_state_in_every_card(self):
        page = self.open()
        report = page.evaluate("""() => [...document.querySelectorAll('[data-stat]')].map((c) => ({ stat: c.dataset.stat, empty: c.querySelectorAll('.chart-empty').length, canvases: c.querySelectorAll('canvas').length, text: (c.querySelector('.chart-empty') || {}).innerText || '' }))""")
        for r in report:
            show(f"{r['stat']:14s} designed empty state={r['empty']} canvases={r['canvases']} text={r['text']!r}")
        self.assertEqual(len(report), 8)
        self.assertTrue(all(r["empty"] == 1 and r["canvases"] == 0 and "Sem dados" in r["text"] for r in report))

    def test_previous_zero_shows_na_markers_never_zero(self):
        insert(monthly([(0, "A", "caju", "nao_podre", 100), (2, "A", "caju", "nao_podre", 50), (2, "A", "caju", "podre", 20), (3, "A", "caju", "nao_podre", 60), (3, "A", "caju", "podre", 30)]))
        page = self.open()
        page.check("input[name=period][value=month]")
        self.settle(page)
        self.scroll_all(page)
        good = page.locator("[data-stat=growth-good] .o-na").all_inner_texts()
        rotten = page.locator("[data-stat=growth-rotten] .o-na").all_inner_texts()
        show(f"growth-good n/a markers={good} growth-rotten n/a markers={rotten}")
        self.assertEqual(good, ["n/d"] * 2)
        self.assertEqual(rotten, ["n/d"] * 3)

    def test_forecast_below_minimum_and_single_sector(self):
        insert(trend_events(0))
        page = self.open()
        page.locator("[data-stat=forecast]").scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        frames = page.evaluate("""() => [...document.querySelectorAll('[data-stat=forecast] .chart-frame')].map((f) => ({ caption: f.querySelector('h3').innerText, canvas: !!f.querySelector('canvas'), empty: (f.querySelector('.chart-empty') || {}).innerText || '', unreliable: !!f.querySelector('.unreliable-tag') }))""")
        for f in frames:
            show(f"forecast frame {f['caption']:8s} canvas={f['canvas']} unreliable-badge={f['unreliable']} empty-state={f['empty']!r}")
        short = next(f for f in frames if f["caption"] == "short")
        self.assertTrue(short["canvas"] and "Dados insuficientes" in short["empty"] and short["unreliable"])
        self.assertTrue(all(f["empty"] == "" for f in frames if f["caption"] != "short"))
        page.select_option("select >> nth=0", "rising")
        self.settle(page)
        page.wait_for_timeout(800)
        counts = page.evaluate("[document.querySelectorAll('[data-stat=forecast] .chart-frame').length, document.querySelectorAll('[data-stat=gaussian] .gauss').length]")
        show(f"sector=rising: forecast charts={counts[0]} gaussian sectors={counts[1]}")
        self.assertEqual(counts, [1, 1])

    def test_failed_normality_check_is_visible(self):
        insert(gauss_events(0, weeks=60, n=150))
        page = self.open()
        self.scroll_all(page)
        sections = page.evaluate("""() => [...document.querySelectorAll('[data-stat=gaussian] .gauss')].map((g) => ({ sector: g.querySelector('h3').innerText, flagged: g.classList.contains('flagged'), stamps: g.querySelectorAll('.o-stamp').length, badge: (g.querySelector('.poor-tag, .small-tag') || {}).innerText || '', mean: (g.querySelector('.overlay strong') || {}).innerText || '' }))""")
        for s in sections:
            show(f"gaussian {s['sector']}: flagged={s['flagged']} poor-fit stamps on charts={s['stamps']} badge={s['badge']!r} first callout={s['mean']!r}")
        c = next(s for s in sections if s["sector"] == "C")
        self.assertTrue(c["flagged"] and c["stamps"] == 2 and c["badge"] == "Ajuste ruim")
        self.assertTrue(all(s["stamps"] == 0 for s in sections if not s["flagged"]))

    def test_reduced_motion_disables_animation(self):
        insert(FA.to_events(demo_events(1, 30, 60)))
        results = {}
        sel = "[data-stat=recurring]"
        for reduced in (False, True):
            page = self.open(reduced=reduced)
            created_before = page.locator(f"{sel} .chart-frame.shown").count()
            page.locator(sel).scroll_into_view_if_needed()
            page.wait_for_selector(f"{sel} .chart-frame.shown")
            a = self.chart_area_shot(page, f"{sel} .chart-area")
            page.wait_for_timeout(1800)
            b = self.chart_area_shot(page, f"{sel} .chart-area")
            styles = page.evaluate("""(sel) => {
              const card = getComputedStyle(document.querySelector(sel));
              const overlay = document.querySelector(sel + ' .overlay');
              const o = overlay ? getComputedStyle(overlay) : null;
              return { motion: document.querySelector(sel + ' .chart-frame').dataset.motion, cardAnimation: card.animationName, overlayTransition: o ? o.transitionDuration : null, overlayDelay: o ? o.transitionDelay : null };
            }""", sel)
            self.assertEqual(created_before, 0)
            results[reduced] = {"changed": a != b, **styles}
            show(f"prefers-reduced-motion={'reduce' if reduced else 'no-preference'}: chart pixels changed between creation and +1.8s = {a != b}; {styles}")
        self.assertTrue(results[False]["changed"])
        self.assertEqual(results[False]["motion"], "on")
        self.assertFalse(results[True]["changed"])
        self.assertEqual(results[True]["motion"], "off")
        self.assertEqual(results[False]["cardAnimation"], "card-in")
        self.assertEqual(results[True]["cardAnimation"], "none")
        self.assertEqual(results[True]["overlayDelay"].split(",")[0].strip(), "0s")

    def test_filter_change_morphs_existing_chart(self):
        insert(FA.to_events(demo_events(1, 30, 60)))
        page = self.open()
        sel = "[data-stat=growth-good]"
        page.locator(sel).scroll_into_view_if_needed()
        page.wait_for_selector(f"{sel} canvas")
        page.wait_for_timeout(1800)
        before = page.get_attribute(f"{sel} .chart-frame", "aria-label")
        page.evaluate(f"document.querySelector('{sel} canvas').__mark = 42")
        page.check("input[name=period][value=month]")
        self.settle(page)
        page.wait_for_timeout(80)
        a = self.chart_area_shot(page, f"{sel} .chart-area")
        page.wait_for_timeout(1500)
        b = self.chart_area_shot(page, f"{sel} .chart-area")
        same = page.evaluate(f"document.querySelector('{sel} canvas').__mark === 42")
        after = page.get_attribute(f"{sel} .chart-frame", "aria-label")
        show(f"same canvas element after period switch = {same}; still animating right after the switch = {a != b}")
        show(f"aria-label before: {before}")
        show(f"aria-label after:  {after}")
        self.assertTrue(same)
        self.assertTrue(a != b)
        self.assertNotEqual(before, after)

    def test_walkthrough_plays_and_is_skippable(self):
        insert(FA.to_events(demo_events(1, 30, 60)))
        for reduced in (False, True):
            page = self.open(reduced=reduced)
            card = page.locator("[data-stat=deformity]")
            page.wait_for_selector("[data-stat=deformity] canvas")
            page.wait_for_timeout(1500)
            card.locator(".how-btn").click()
            first = card.locator(".tour-count").inner_text()
            spot = page.evaluate("document.querySelector('[data-stat=deformity] .tour-spot').getBoundingClientRect().width")
            page.wait_for_timeout(3300)
            auto = card.locator(".tour-count").inner_text()
            for _ in range(4):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(120)
            page.wait_for_timeout(400)
            last = card.locator(".tour-count").inner_text()
            text = card.locator(".tour-bubble p").inner_text()
            page.keyboard.press("Escape")
            closed = card.locator(".tour").count() == 0
            focus = page.evaluate("document.activeElement.classList.contains('how-btn')")
            show(f"reduced={reduced}: opened at {first!r}, spotlight width {spot:.0f}px, after 3.3s {auto!r}, after arrows {last!r} ({text!r}), Esc closed={closed}, focus back on button={focus}")
            self.assertEqual(first.lower(), "passo 1 de 4")
            self.assertGreater(spot, 10)
            self.assertEqual(auto.lower(), "passo 1 de 4" if reduced else "passo 2 de 4")
            self.assertEqual(last.lower(), "passo 4 de 4")
            self.assertTrue(closed and focus)

    def test_demo_and_small_sample_badges(self):
        insert(FA.to_events(demo_events(2, 12, 40)), demo=True)
        page = self.open()
        page.select_option("select >> nth=1", "demo")
        self.settle(page)
        report = page.evaluate("""() => [...document.querySelectorAll('[data-stat]')].map((c) => ({ stat: c.dataset.stat, demo: !!c.querySelector('.demo-tag'), small: c.querySelectorAll('.small-tag, .unreliable-tag, .poor-tag').length }))""")
        page_badge = page.locator(".demo-badge").is_visible()
        for r in report:
            show(f"{r['stat']:14s} demo badge={r['demo']} small/unreliable/poor badges={r['small']}")
        show(f"page-level demo badge visible = {page_badge}")
        self.assertTrue(page_badge and all(r["demo"] for r in report))
        by = {r["stat"]: r["small"] for r in report}
        self.assertGreaterEqual(by["forecast"], 1)
        self.assertGreaterEqual(by["gaussian"], 1)
        self.assertGreaterEqual(by["recurring"], 1)

    def test_legible_at_360px(self):
        insert(FA.to_events(demo_events(1, 30, 60)))
        page = self.open(width=360, height=780)
        self.scroll_all(page)
        info = page.evaluate("""() => ({ overflow: document.documentElement.scrollWidth - window.innerWidth, widest: Math.max(...[...document.querySelectorAll('canvas')].map((c) => c.getBoundingClientRect().right)), canvases: document.querySelectorAll('[data-stat] canvas').length })""")
        show(f"360px: horizontal overflow={info['overflow']}px, rightmost canvas edge={info['widest']:.0f}px, charts rendered={info['canvases']}")
        self.assertEqual(info["overflow"], 0)
        self.assertLessEqual(info["widest"], 360)
        self.assertGreaterEqual(info["canvases"], 14)
        self.assertEqual(self.errors, [])
