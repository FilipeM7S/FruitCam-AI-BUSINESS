import io
from datetime import timedelta

import pandas as pd
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.test import Client
from django.utils import timezone
from PIL import Image

from belt.classify import CropClassifier
from core import showcase as SC
from core.cameras import cameras
from core.models import Event
from core.tests.test_api import Base, image_bytes, show, strict_json

ENDPOINTS = ["/api/events", "/api/events/thresholds", "/api/events/1", "/api/events/1/image"]
ROW_KEYS = {"id", "timestamp", "sector", "fruit_type", "is_good", "deformity_type", "confidence", "user", "is_demo", "source", "camera", "lot", "track_id", "label", "size_mm", "needs_review", "decided_by", "model_version", "image"}
TRICKY = [0.0, 0.07, 0.29, 0.29999999999999999, 0.3, 0.57, 0.5700000000000001, 0.58, 0.999, 1.0, None]


def make(label, conf, review=False, demo=False, **extra):
    return Event(timestamp=extra.pop("timestamp", timezone.now()), sector=extra.pop("sector", "norte"), fruit_type=extra.pop("fruit_type", "caju"), is_good=label == "boa",
                 deformity_type=None if label == "boa" else label, confidence=conf, label=label, needs_review=review, is_demo=demo, **extra)


class ControlEndpointTests(Base):
    def get(self, path, **params):
        r = self.client.get(path, params)
        return r.status_code, strict_json(r) if r["Content-Type"].startswith("application/json") else r

    def test_endpoints_require_login(self):
        c = Client()
        codes = {p: (c.get(p).status_code, strict_json(c.get(p))["error"]["code"]) for p in ENDPOINTS}
        show(f"anonymous: {codes}")
        self.assertEqual(set(codes.values()), {(403, "not_authenticated")})

    def test_invalid_filters_are_rejected(self):
        bad = [{"source": "x"}, {"kind": "video"}, {"label": "revisar"}, {"review": "maybe"}, {"fruit_type": "uva"}, {"start": "2026-13-01"}, {"since": "ontem"},
               {"size": 0}, {"size": 501}, {"lot": "L1", "size": 20001}, {"page": 0}, {"order": "up"}, {"shape": "csv"}, {"sector": "x" * 51}, {"size": "dez"}]
        codes = [(p, self.get("/api/events", **p)) for p in bad]
        hist = [self.get("/api/events/thresholds", **p) for p in bad[:7]]
        show(f"{len(codes)} invalid list queries -> {sorted({c for _, (c, _) in codes})}; {len(hist)} invalid threshold queries -> {sorted({c for c, _ in hist})}")
        for p, (code, body) in codes:
            self.assertEqual((code, body["error"]["code"]), (400, "invalid_filter"), p)
        self.assertEqual({(c, b["error"]["code"]) for c, b in hist}, {(400, "invalid_filter")})
        self.assertEqual(self.get("/api/events", lot="L1", size=20000)[0], 200)

    def test_list_filters_and_pages_match_the_database(self):
        now = timezone.now()
        rows = [make(["boa", "baixa_qualidade", "podre"][i % 3], 0.4 + (i % 6) / 10, review=i % 5 == 0, demo=i % 2 == 0, timestamp=now - timedelta(hours=i),
                     sector=["norte", "sul"][i % 2], fruit_type=["caju", "castanha", "melao"][i % 3], source=["foto", "camera"][i % 4 == 0], lot="L1-01" if i % 4 == 0 else "") for i in range(120)]
        Event.objects.bulk_create(rows)
        cases = [{}, {"source": "demo"}, {"source": "all"}, {"source": "all", "label": "podre"}, {"source": "all", "review": "yes"}, {"source": "all", "kind": "camera", "lot": "L1-01"},
                 {"source": "all", "fruit_type": "melao", "sector": "sul"}, {"source": "all", "start": (now - timedelta(days=2)).date().isoformat(), "end": now.date().isoformat()}]
        out = []
        for p in cases:
            code, body = self.get("/api/events", **p, size=500)
            self.assertEqual(code, 200)
            qs = Event.objects.all() if p.get("source") == "all" else Event.objects.filter(is_demo=p.get("source") == "demo")
            for k, f in (("label", "label"), ("kind", "source"), ("lot", "lot"), ("fruit_type", "fruit_type"), ("sector", "sector")):
                if k in p:
                    qs = qs.filter(**{f: p[k]})
            if "review" in p:
                qs = qs.filter(needs_review=True)
            if "start" in p:
                lo = timezone.make_aware(pd.Timestamp(p["start"]).to_pydatetime())
                hi = timezone.make_aware((pd.Timestamp(p["end"]) + pd.Timedelta(days=1)).to_pydatetime())
                qs = qs.filter(timestamp__gte=lo, timestamp__lt=hi)
            expected = list(qs.order_by("-timestamp", "-id").values_list("id", flat=True))
            out.append(f"{p or 'default'} {body['total']}")
            self.assertEqual(body["total"], len(expected))
            self.assertEqual([e["id"] for e in body["events"]], expected)
        pages = [e["id"] for page in (1, 2, 3) for e in self.get("/api/events", source="all", size=50, page=page)[1]["events"]]
        self.assertEqual(pages, list(Event.objects.order_by("-timestamp", "-id").values_list("id", flat=True)))
        asc = self.get("/api/events", source="all", order="asc", size=500)[1]["events"]
        self.assertEqual([e["id"] for e in asc], list(Event.objects.order_by("timestamp", "id").values_list("id", flat=True)))
        show("totals " + "; ".join(out) + "; 3 pages of 50 = full order; asc order ok")

    def test_inspector_detail_matches_the_stored_row_and_shows_only_stored_fields(self):
        r = self.post_image(image_bytes())
        self.assertEqual(r.status_code, 201)
        made = strict_json(r)
        code, body = self.get(f"/api/events/{made['event']['id']}")
        e = Event.objects.get(pk=made["event"]["id"])
        got = body["event"]
        show(f"detail keys {sorted(got)}; label {got['label']} confidence {got['confidence']:.4f} review {got['needs_review']} model {got['model_version']} image {got['image']}")
        self.assertEqual(code, 200)
        self.assertEqual(set(got), ROW_KEYS)
        for k in ROW_KEYS - {"timestamp", "user", "image"}:
            self.assertEqual(got[k], getattr(e, k), k)
        self.assertEqual(got["timestamp"], timezone.localtime(e.timestamp).isoformat())
        self.assertEqual(got["user"], "ana")
        self.assertTrue(got["image"])
        self.assertFalse({"box", "probs", "crop"} & set(got))
        self.assertEqual(self.get("/api/events/999999")[0], 404)

    def test_stored_photo_thumbnail_only_for_its_uploader(self):
        made = strict_json(self.post_image(image_bytes(size=(1200, 900))))
        pk = made["event"]["id"]
        r = self.client.get(f"/api/events/{pk}/image")
        im = Image.open(io.BytesIO(r.content))
        other = Client()
        other.force_login(get_user_model().objects.create_user("bruno", password="Outra-Senha-2026"))
        stranger = other.get(f"/api/events/{pk}/image")
        demo = Event.objects.create(sector="norte", fruit_type="caju", is_good=True, is_demo=True)
        missing = Event.objects.create(sector="norte", fruit_type="caju", is_good=True, image="0" * 32 + ".png", user=self.user)
        hostile = Event.objects.create(sector="norte", fruit_type="caju", is_good=True, image="../../settings.py", user=self.user)
        codes = [self.client.get(f"/api/events/{x.pk}/image").status_code for x in (demo, missing, hostile)]
        show(f"owner {r.status_code} {r['Content-Type']} {im.size} cache '{r['Cache-Control']}'; other user {stranger.status_code}; demo/missing/hostile name {codes}; other user's detail image flag {strict_json(other.get(f'/api/events/{pk}'))['event']['image']}")
        self.assertEqual((r.status_code, r["Content-Type"], im.format), (200, "image/jpeg", "JPEG"))
        self.assertEqual(max(im.size), 320)
        self.assertEqual(r["Cache-Control"], "private, no-store")
        self.assertEqual(stranger.status_code, 404)
        self.assertEqual(codes, [404, 404, 404])
        self.assertFalse(strict_json(other.get(f"/api/events/{pk}"))["event"]["image"])

    def test_threshold_histograms_give_exact_counts_at_every_slider_step(self):
        rows = [make(label, c, review=i % 3 == 0, demo=True, track_id=i) for i, (label, c) in enumerate((l, c) for l in ("boa", "baixa_qualidade", "podre") for c in TRICKY)]
        rows += [make("podre", (k * 37 % 1000) / 1000, demo=True) for k in range(400)]
        Event.objects.bulk_create(rows)
        code, body = self.get("/api/events/thresholds", source="demo")
        self.assertEqual(code, 200)
        mismatches = 0
        for label, h in body["classes"].items():
            qs = Event.objects.filter(is_demo=True, label=label, confidence__isnull=False)
            self.assertEqual(h["n"], qs.count())
            self.assertEqual(h["stored_review"], qs.filter(needs_review=True).count())
            for j in range(body["steps"] + 1):
                if sum(h["bins"][:j]) != qs.filter(confidence__lt=j / 100).count():
                    mismatches += 1
        reference = CropClassifier(settings.MODEL_PATH)
        show(f"classes {sorted(body['classes'])}; n {[h['n'] for h in body['classes'].values()]}; no confidence {body['no_confidence']} of {body['total']}; 101 thresholds x {len(body['classes'])} classes, mismatches {mismatches}; model {body['model']}")
        self.assertEqual(mismatches, 0)
        self.assertEqual(body["no_confidence"], 3)
        self.assertEqual(body["total"], len(rows))
        self.assertTrue(body["demo"])
        self.assertEqual(body["model"], {"version": reference.version, "reject_below": reference.reject_below})

    def test_lot_replay_columns_end_at_the_line_page_totals(self):
        cam = next(c for c in cameras() if c["slug"] == "linha-1")
        now = timezone.localtime().replace(second=0, microsecond=0, tzinfo=None)
        line = SC.line_events([cam], pd.Timestamp(now) - pd.Timedelta(hours=3), pd.Timestamp(now), 7)
        ts = line["timestamp"].dt.tz_localize(settings.TIME_ZONE)
        Event.objects.bulk_create([
            Event(timestamp=t.to_pydatetime(), sector=cam["line"], fruit_type="caju", is_good=label == "boa", deformity_type=None if label == "boa" else label, confidence=conf,
                  is_demo=True, source="camera", camera="linha-1", lot=lot, label=label, size_mm=size, needs_review=review)
            for t, label, review, lot, size, conf in zip(ts, line["label"], line["needs_review"], line["lot"], line["size_mm"], line["confidence"])
        ], batch_size=5000)
        summary = strict_json(self.client.get("/api/line", {"camera": "linha-1", "minutes": 240, "window": 5, "source": "demo"}))
        checked = []
        for lot in summary["lots"]:
            code, body = self.get("/api/events", source="demo", kind="camera", camera="linha-1", lot=lot["lot"], since=summary["start"], until=summary["end"], order="asc", shape="columns", size=20000)
            self.assertEqual(code, 200)
            col = body["columns"]
            self.assertEqual(col["timestamp"], sorted(col["timestamp"]))
            totals = {"boa": 0, "baixa_qualidade": 0, "podre": 0, "revisar": 0}
            for label, review in zip(col["label"], col["needs_review"]):
                totals["revisar" if review else label] += 1
            checked.append(f"{lot['lot']} n={body['total']} {totals}")
            self.assertEqual(body["total"], lot["n"])
            self.assertEqual(totals, lot["counts"])
        listed = {r["lot"]: r for r in self.get("/api/events", source="demo", kind="camera", shape="lots")[1]["lots"]}
        for lot, n in Event.objects.filter(is_demo=True).exclude(lot="").values_list("lot").annotate(n=Count("id")):
            self.assertEqual(listed[lot]["n"], n)
            self.assertTrue(listed[lot]["demo"])
        show("lots replayed to the line-page totals: " + "; ".join(checked) + f"; lot list for the command bar: {sorted(listed)}")
        self.assertGreaterEqual(len(checked), 2)
