import io
from unittest import mock

import numpy as np
import pandas as pd
from django.core.management import call_command
from django.db.models import Count
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from belt import stats as BS

from core import showcase as SC
from core import stats as ST
from core.cameras import cameras
from core.certificate_data import align
from core.models import Event
from core.tests.test_api import show

MONDAY = pd.Timestamp("2026-10-05")
LINE_START, LINE_END = pd.Timestamp("2026-10-05 08:00"), pd.Timestamp("2026-10-05 16:00")


class ShowcaseBehaviourTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.painel = SC.painel_events(MONDAY, 156, 7)
        cls.line = SC.line_events(cameras(), LINE_START, LINE_END, 7)
        cams = {c["slug"]: c for c in cameras()}
        decided = cls.line[~cls.line["needs_review"]]
        cls.events = pd.concat([cls.painel, pd.DataFrame({
            "timestamp": decided["timestamp"], "sector": decided["camera"].map(lambda s: cams[s]["line"]), "fruit_type": "caju",
            "is_good": decided["label"] == "boa", "deformity_type": decided["label"].where(decided["label"] != "boa"),
        })], ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)

    def test_painel_sectors_show_every_forecast_and_gaussian_state(self):
        fc = {s["sector"]: s for s in ST.forecast(self.events, "week")["sectors"]}
        ga = {s["sector"]: s for s in ST.gaussian(self.events, "week")["sectors"]}
        show("forecast: " + "; ".join(f"{k} {v['status']} reliable={v['reliable']} {v['reasons']}" for k, v in fc.items()))
        show("gaussian: " + "; ".join(f"{k} n={v['n']} {v['reasons'] or 'sem sinal'}" for k, v in ga.items()))
        self.assertTrue(fc["norte"]["reliable"])
        self.assertTrue(fc["sul"]["reliable"] and fc["sul"]["p_more_rotten"] > 0.99)
        self.assertIn("not_better_than_naive", fc["leste"]["reasons"])
        self.assertIn("not_better_than_naive", fc["controle"]["reasons"])
        self.assertEqual((fc["oeste"]["status"], fc["oeste"]["reasons"][0]), ("ok", "few_periods"))
        self.assertEqual(fc["vale"]["status"], "ok")
        self.assertIn("no_backtest", fc["vale"]["reasons"])
        self.assertEqual({fc[k]["status"] for k in ("linha 1", "linha 2")}, {"ok"})
        self.assertTrue(all(ga[k]["n"] >= 150 and "small_n" not in ga[k]["reasons"] for k in ("linha 1", "linha 2")))
        self.assertTrue(all(sum(1 for v in fc[k]["history_n"] if v and v >= 30) >= 150 for k in ("linha 1", "linha 2")))
        self.assertEqual(ga["norte"]["reasons"], [])
        self.assertIn("not_normal", ga["sul"]["reasons"])
        self.assertTrue({"not_normal", "outside_01"} <= set(ga["serra"]["reasons"]))
        self.assertIn("small_n", ga["oeste"]["reasons"])
        self.assertIn("no_variance", ga["controle"]["reasons"])

    def test_painel_calendar_shows_ties_gaps_partials_and_seasons(self):
        d = ST.deformity(self.events, "week")
        g = ST.growth(self.events, "week")
        r = ST.recurring(self.events, "week")
        ties = [w for w, t in zip(d["weeks"], d["tie"]) if t]
        empty = [w for w, n in zip(d["weeks"], d["n_rotten"]) if n == 0]
        dominant = {k for k in d["dominant"] if k != "none"}
        na = [l for l, v in zip(g["labels"], g["good"]["count_growth"]) if v is None or v != v]
        months = dict(zip(r["month"]["buckets"], r["month"]["good"]))
        show(f"ties {ties}; empty week {empty}; dominant types {sorted(dominant)}; growth n/d at {na}; excluded {g['excluded']}; month medians of good growth {({k: round(v, 3) for k, v in months.items()})}")
        self.assertTrue(ties)
        self.assertEqual(len(empty), 1)
        self.assertEqual(dominant, set(SC.DEFECTS))
        self.assertIn(g["labels"][g["labels"].index(empty[0]) + 1], na)
        self.assertGreater(g["excluded"], 0)
        self.assertGreaterEqual(r["month"]["max_n"], 2)
        self.assertGreater(min(months[k] for k in ("8", "9")), 0.2)
        self.assertLess(max(months[k] for k in ("1", "2")), -0.1)

    def test_painel_fruits_are_sorted_with_a_confidence(self):
        label, conf = SC.sorting(self.painel, 7)
        kind = self.painel["deformity_type"]
        unseen = kind.isin(SC.UNSEEN).to_numpy()
        review_at = lambda mask, thr: float((conf[mask] < thr).mean())
        show(f"classes {pd.Series(label).value_counts().to_dict()}; median confidence known {np.median(conf[~unseen]):.3f} vs queimada/quebrada {np.median(conf[unseen]):.3f}; sent to review at 0.80: known {review_at(~unseen, 0.8):.1%}, queimada/quebrada {review_at(unseen, 0.8):.1%}")
        self.assertEqual(set(label), {"boa", "baixa_qualidade", "podre"})
        self.assertTrue(((label == "boa") == self.painel["is_good"].to_numpy()).all())
        self.assertTrue((label[kind.eq("podre").to_numpy()] == "podre").all())
        self.assertTrue(((conf >= 0.34) & (conf <= 1)).all())
        self.assertGreater(np.median(conf[~unseen]) - np.median(conf[unseen]), 0.2)
        self.assertGreater(review_at(unseen, 0.8), 3 * review_at(~unseen, 0.8))
        again = SC.sorting(self.painel, 7)
        self.assertTrue((again[0] == label).all() and (again[1] == conf).all())

    def test_line_shows_every_lot_and_alarm_state(self):
        out = {}
        for cam in cameras():
            df = self.line[self.line["camera"] == cam["slug"]]
            lo = align(df["timestamp"].min(), 5)
            s = BS.summary(df, lo, lo + pd.Timedelta(minutes=5) * int(np.ceil((LINE_END - lo) / pd.Timedelta(minutes=5))), 5, cam["max_rotten_share"])
            out[cam["slug"]] = {
                "verdicts": [l["verdict"] for l in s["lots"]],
                "rules": {a["rule"] for a in s["p_chart"]["alarms"]},
                "empty": sum(w["n"] == 0 for w in s["windows"]),
                "review": s["review_share"],
            }
        show(" | ".join(f"{k}: lots {v['verdicts']}, alarms {sorted(v['rules'])}, empty windows {v['empty']}, review {v['review']:.3f}" for k, v in out.items()))
        one, two = out["linha-1"], out["linha-2"]
        self.assertEqual(one["verdicts"].count("reprovado"), 1)
        self.assertIn("inconclusivo", one["verdicts"])
        self.assertIn("acima_do_limite", one["rules"])
        self.assertGreaterEqual(one["empty"], 3)
        self.assertIn("sequencia_acima_da_mediana", two["rules"])
        self.assertIn("inconclusivo", two["verdicts"])
        self.assertGreater(two["review"], one["review"])


class SeedShowcaseCommandTests(TestCase):
    def test_replaces_demo_rows_and_keeps_real_ones(self):
        Event.objects.create(sector="real", fruit_type="caju", is_good=True)
        Event.objects.create(sector="demo-antigo", fruit_type="caju", is_good=True, is_demo=True)
        frozen = timezone.now()
        with mock.patch("django.utils.timezone.now", return_value=frozen):
            call_command("seed_showcase", weeks=30, line_hours=1, stdout=io.StringIO())
            first = Event.objects.filter(is_demo=True).count()
            call_command("seed_showcase", weeks=30, line_hours=1, stdout=io.StringIO())
        demo = Event.objects.filter(is_demo=True)
        sources = dict(demo.values_list("source").annotate(n=Count("id")))
        show(f"demo rows {first} then {demo.count()} after reseeding; sources {sources}; sectors {sorted(set(demo.values_list('sector', flat=True)))}; real rows {Event.objects.filter(is_demo=False).count()}")
        self.assertEqual(demo.count(), first)
        self.assertFalse(demo.filter(sector="demo-antigo").exists())
        self.assertEqual(list(Event.objects.filter(is_demo=False).values_list("sector", flat=True)), ["real"])
        self.assertEqual(set(demo.values_list("decided_by", flat=True)), {"simulacao"})
        self.assertFalse(demo.filter(confidence__isnull=True).exists())
        self.assertFalse(demo.filter(label="").exists())
        self.assertGreater(sources.get("camera", 0), 0)
        self.assertGreater(sources.get("foto", 0), 0)
        self.assertTrue({"norte", "sul", "serra", "leste", "controle", "oeste", "vale"} <= set(demo.values_list("sector", flat=True)))
