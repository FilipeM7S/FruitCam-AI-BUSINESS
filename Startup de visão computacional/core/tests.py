import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import torch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageOps

import fruit_analytics as FA
from belt.classify import GOOD, CropClassifier
from test_fruit_analytics import expand, gauss_events, month, trend_events, week

from core import inference
from core.models import Event

PASSWORD = "Caju-Castanha-2026"
UPLOAD_TMP = Path(tempfile.mkdtemp(prefix="fruitcam_uploads_"))
STATS = ["deformity", "forecast", "fruits", "growth", "recurring", "gaussian", "overview"]
HEX_NAME = re.compile(r"^[0-9a-f]{32}\.png$")


def show(msg):
    print(f"    {msg}")


def reject_constant(c):
    raise ValueError(f"non-standard JSON constant {c}")


def strict_json(response):
    return json.loads(response.content, parse_constant=reject_constant)


def image_bytes(fmt="PNG", size=(320, 240), bg=(245, 243, 236), fg=(70, 45, 25)):
    im = Image.new("RGB", size, bg)
    w, h = size
    ImageDraw.Draw(im).ellipse([w // 4, h // 4, 3 * w // 4, 3 * h // 4], fill=fg)
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


def noise_png(side=200):
    buf = io.BytesIO()
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (side, side, 3), dtype=np.uint8)).save(buf, "PNG")
    return buf.getvalue()


def insert(events, demo=False):
    ts = events["timestamp"].dt.tz_localize(settings.TIME_ZONE)
    Event.objects.bulk_create(
        [
            Event(timestamp=t.to_pydatetime(), sector=s, fruit_type=f, is_good=bool(g), deformity_type=None if pd.isna(d) else d, is_demo=demo)
            for t, s, f, g, d in zip(ts, events["sector"], events["fruit_type"], events["is_good"], events["deformity_type"])
        ],
        batch_size=5000,
    )
    return events


def max_err(got, expected):
    return float(np.nanmax(np.abs(np.array(got, dtype=float) - np.array(expected, dtype=float))))


@override_settings(UPLOAD_DIR=UPLOAD_TMP)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("ana", password=PASSWORD)

    def setUp(self):
        cache.clear()
        shutil.rmtree(UPLOAD_TMP, ignore_errors=True)
        UPLOAD_TMP.mkdir(parents=True)
        self.client.force_login(self.user)

    def post_image(self, data, name="foto.png", content_type="image/png", sector="norte", fruit="caju", client=None):
        payload = {"sector": sector, "fruit_type": fruit}
        if data is not None:
            payload["image"] = SimpleUploadedFile(name, data, content_type=content_type)
        return (client or self.client).post("/api/analyze", payload)

    def stat(self, name, **params):
        r = self.client.get(f"/api/stats/{name}", params)
        self.assertEqual(r.status_code, 200, r.content)
        return strict_json(r)


class AuthTests(Base):
    def login(self, client, password):
        return client.post("/api/auth/login", {"username": "ana", "password": password}, content_type="application/json")

    def test_wrong_password_rejected(self):
        c = Client()
        bad = self.login(c, "wrong-password")
        unknown = c.post("/api/auth/login", {"username": "nobody", "password": PASSWORD}, content_type="application/json")
        me_after_bad = c.get("/api/auth/me").status_code
        good = self.login(c, PASSWORD)
        me_after_good = c.get("/api/auth/me")
        show(f"wrong password -> {bad.status_code} {strict_json(bad)}; unknown user -> {unknown.status_code}; /me after -> {me_after_bad}")
        show(f"right password -> {good.status_code}; /me -> {me_after_good.status_code} {strict_json(me_after_good)}")
        self.assertEqual((bad.status_code, strict_json(bad)["error"]["code"]), (400, "invalid_credentials"))
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(me_after_bad, 403)
        self.assertEqual(good.status_code, 200)
        self.assertEqual(strict_json(me_after_good)["user"]["username"], "ana")

    def test_password_is_hashed(self):
        stored = get_user_model().objects.get(username="ana").password
        show(f"stored password field starts with {stored.split('$')[0]!r}, {stored.count('$')} '$' separators")
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertNotIn(PASSWORD, stored)

    def test_protected_endpoints_without_login(self):
        c = Client()
        targets = [("get", "/api/auth/me"), ("post", "/api/auth/logout"), ("post", "/api/analyze"), ("get", "/api/sectors")]
        targets += [("get", f"/api/stats/{n}") for n in STATS]
        results = [(p, getattr(c, m)(p)) for m, p in targets]
        for p, r in results:
            show(f"{p:24s} -> {r.status_code} {strict_json(r)['error']['code']}")
        self.assertEqual({r.status_code for _, r in results}, {403})
        self.assertEqual({strict_json(r)["error"]["code"] for _, r in results}, {"not_authenticated"})
        self.assertEqual(len(results), 11)

    def test_login_rate_limit(self):
        c = Client()
        codes = [self.login(c, f"wrong-{i}").status_code for i in range(7)]
        blocked = self.login(c, PASSWORD)
        show(f"7 wrong attempts -> {codes}; correct password afterwards -> {blocked.status_code} {strict_json(blocked)}")
        self.assertEqual(codes, [400] * 5 + [429, 429])
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(strict_json(blocked)["error"]["code"], "throttled")
        self.assertGreater(strict_json(blocked)["error"]["wait_seconds"], 0)

    def test_csrf_enforced_and_cookie_flags(self):
        c = Client(enforce_csrf_checks=True)
        no_token = self.login(c, PASSWORD)
        token = strict_json(c.get("/api/auth/csrf"))["csrf_token"]
        ok = c.post("/api/auth/login", {"username": "ana", "password": PASSWORD}, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        new_token = strict_json(ok)["csrf_token"]
        no_token_analyze = c.post("/api/analyze", {})
        with_token_analyze = c.post("/api/analyze", {}, HTTP_X_CSRFTOKEN=new_token)
        session, csrf_cookie = ok.cookies["sessionid"], c.cookies["csrftoken"]
        show(f"login without CSRF token -> {no_token.status_code} {strict_json(no_token)['error']['code']}; with token -> {ok.status_code}")
        show(f"analyze without token -> {no_token_analyze.status_code} {strict_json(no_token_analyze)['error']['code']}; with token -> {with_token_analyze.status_code} {strict_json(with_token_analyze)['error']['code']}")
        show(f"sessionid httponly={session['httponly']} samesite={session['samesite']}; csrftoken httponly={csrf_cookie['httponly']}; token rotated on login={token != new_token}")
        self.assertEqual((no_token.status_code, strict_json(no_token)["error"]["code"]), (403, "csrf_failed"))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual((no_token_analyze.status_code, strict_json(no_token_analyze)["error"]["code"]), (403, "csrf_failed"))
        self.assertEqual(strict_json(with_token_analyze)["error"]["code"], "image_required")
        self.assertTrue(session["httponly"])
        self.assertEqual(session["samesite"], "Lax")
        self.assertTrue(csrf_cookie["httponly"])

    def test_logout(self):
        before = self.client.get("/api/auth/me").status_code
        out = self.client.post("/api/auth/logout").status_code
        after = self.client.get("/api/auth/me").status_code
        show(f"/me before={before} logout={out} /me after={after}")
        self.assertEqual((before, out, after), (200, 200, 403))

    def test_settings_come_from_environment(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "FRUITCAM_"))}
        code = "import fruitcam.settings as s; print(s.DEBUG, s.HTTPS, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS)"
        missing = subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True)
        present = subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env={**env, "DJANGO_SECRET_KEY": "x" * 50}, capture_output=True, text=True)
        show(f"no DJANGO_SECRET_KEY -> exit {missing.returncode}, ImproperlyConfigured in stderr={'ImproperlyConfigured' in missing.stderr}")
        show(f"key set, nothing else -> DEBUG HTTPS session_secure csrf_secure ssl_redirect hsts = {present.stdout.strip()}")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", missing.stderr)
        self.assertEqual(present.stdout.split(), ["False", "True", "True", "True", "True", "31536000"])


class UploadTests(Base):
    def test_valid_image_returns_result(self):
        r = self.post_image(image_bytes())
        body = strict_json(r)
        files = os.listdir(UPLOAD_TMP)
        show(f"status={r.status_code} detections={body['detections']} inference_ms={body['inference_ms']} saved={files}")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(body["detections"]), 1)
        self.assertIn(body["detections"][0]["label"], body["classes"])
        self.assertGreater(body["inference_ms"], 0)
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], HEX_NAME)

    def test_rejected_uploads(self):
        png = image_bytes()
        gif = image_bytes("GIF")
        cases = [
            ("text bytes named .png", b"definitely not an image" * 20, "x.png", "image/png", {}, 400, "invalid_image"),
            ("svg/html declared png", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "x.png", "image/png", {}, 400, "invalid_image"),
            ("png declared text/plain", png, "x.txt", "text/plain", {}, 400, "unsupported_type"),
            ("real gif declared gif", gif, "x.gif", "image/gif", {}, 400, "unsupported_type"),
            ("real gif declared png", gif, "x.png", "image/png", {}, 400, "unsupported_type"),
            ("truncated png", png[: len(png) // 2], "x.png", "image/png", {}, 400, "invalid_image"),
            ("truncated jpeg", image_bytes("JPEG")[:400], "x.jpg", "image/jpeg", {}, 400, "invalid_image"),
            ("oversized file (limit 10 KB)", noise_png(), "x.png", "image/png", {"MAX_UPLOAD_BYTES": 10_000}, 413, "file_too_large"),
            ("too many pixels (limit 10k)", png, "x.png", "image/png", {"MAX_IMAGE_PIXELS": 10_000}, 400, "image_too_large"),
        ]
        for label, data, name, ctype, override, status, code in cases:
            with self.settings(**override):
                r = self.post_image(data, name, ctype)
            show(f"{label:30s} -> {r.status_code} {strict_json(r)['error']['code']}")
            self.assertEqual((r.status_code, strict_json(r)["error"]["code"]), (status, code), label)
        fields = [
            ("no image", None, "norte", "caju", "image_required"),
            ("fruit not allowed", png, "norte", "banana", "invalid_fruit_type"),
            ("empty sector", png, "   ", "caju", "invalid_sector"),
            ("sector > 50 chars", png, "s" * 51, "caju", "invalid_sector"),
        ]
        for label, data, sector, fruit, code in fields:
            r = self.post_image(data, sector=sector, fruit=fruit)
            show(f"{label:30s} -> {r.status_code} {strict_json(r)['error']['code']}")
            self.assertEqual((r.status_code, strict_json(r)["error"]["code"]), (400, code), label)
        show(f"events created: {Event.objects.count()}, files saved: {len(os.listdir(UPLOAD_TMP))}")
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(os.listdir(UPLOAD_TMP), [])

    def test_client_filename_never_used(self):
        r = self.post_image(image_bytes(), name="../../../evil.png")
        files = os.listdir(UPLOAD_TMP)
        escaped = [p for p in (UPLOAD_TMP.parent / "evil.png", settings.BASE_DIR / "evil.png") if p.exists()]
        show(f"status={r.status_code} saved={files} event.image={Event.objects.get().image} files outside upload dir={escaped}")
        self.assertEqual(r.status_code, 201)
        self.assertRegex(files[0], HEX_NAME)
        self.assertEqual(Event.objects.get().image, files[0])
        self.assertEqual(escaped, [])


class InferenceTests(Base):
    def test_endpoint_equals_direct_infer_call(self):
        classifier = CropClassifier(settings.MODEL_PATH, torch.device("cpu"))
        tmp = Path(tempfile.mkdtemp())
        (tmp / "synthetic_dark.png").write_bytes(image_bytes())
        (tmp / "synthetic_light.jpg").write_bytes(image_bytes("JPEG", (400, 300), bg=(30, 30, 30), fg=(220, 200, 90)))
        files = [tmp / "synthetic_dark.png", tmp / "synthetic_light.jpg"]
        files += [sorted((settings.BASE_DIR / "data_real" / "val" / c).glob("*.jpg"))[0] for c in ("nao_podre", "podre")]
        worst = 0.0
        for path in files:
            with Image.open(path) as im:
                direct = inference.classify_photo(classifier, ImageOps.exif_transpose(im).convert("RGB"))
            ctype = "image/png" if path.suffix == ".png" else "image/jpeg"
            body = strict_json(self.post_image(path.read_bytes(), path.name, ctype))
            det = body["detections"][0]
            diff = max(abs(det["probs"][c] - direct["probs"][c]) for c in classifier.classes)
            worst = max(worst, diff)
            show(f"{path.parent.name}/{path.name}: direct=({direct['label']}, {direct['confidence']:.6f}, {direct['box']}) endpoint=({det['label']}, {det['confidence']:.6f}, {det['box']}) review={det['needs_review']} |dprob|={diff:.1e}")
            self.assertEqual(det["label"], direct["label"])
            self.assertEqual(det["box"], direct["box"])
            self.assertEqual(det["needs_review"], direct["needs_review"])
            self.assertLessEqual(diff, 1e-6)
            self.assertAlmostEqual(sum(det["probs"].values()), 1.0, places=5)
            self.assertEqual(body["classes"], ["boa", "baixa_qualidade", "podre"])
        show(f"worst |probability difference| over {len(files)} images = {worst:.1e} (tolerance 1e-6)")
        shutil.rmtree(tmp)

    def test_model_loaded_once(self):
        inference.get_model.cache_clear()
        with mock.patch("core.inference.CropClassifier", wraps=inference.CropClassifier) as spy:
            statuses = [self.post_image(image_bytes()).status_code for _ in range(3)]
        show(f"3 requests -> {statuses}; classifier loads = {spy.call_count}")
        self.assertEqual(statuses, [201] * 3)
        self.assertEqual(spy.call_count, 1)

    def test_wsgi_startup_loads_model(self):
        inference.get_model.cache_clear()
        sys.modules.pop("fruitcam.wsgi", None)
        importlib.import_module("fruitcam.wsgi")
        info = inference.get_model.cache_info()
        show(f"after importing fruitcam.wsgi: get_model cache misses={info.misses} size={info.currsize}")
        self.assertEqual((info.misses, info.currsize), (1, 1))


class PersistenceTests(Base):
    def test_saved_row_matches_response(self):
        r = self.post_image(image_bytes(), sector="  Setor   Norte ", fruit="castanha")
        body = strict_json(r)
        e = Event.objects.get(id=body["event"]["id"])
        det = body["detections"][0]
        row = {"timestamp": timezone.localtime(e.timestamp).isoformat(), "sector": e.sector, "fruit_type": e.fruit_type, "is_good": e.is_good,
               "deformity_type": e.deformity_type, "confidence": e.confidence, "user": e.user.username, "is_demo": e.is_demo}
        show(f"db row  = {row}")
        show(f"response= {body['event']}")
        self.assertEqual({k: body["event"][k] for k in row}, row)
        self.assertEqual(e.sector, "setor norte")
        self.assertEqual((det["is_good"], det["deformity_type"], det["confidence"]), (e.is_good, e.deformity_type, e.confidence))
        self.assertEqual(e.is_good, det["label"] in GOOD)


class ErrorTests(Base):
    def test_json_errors(self):
        cases = [
            ("GET /api/nope", self.client.get("/api/nope"), 404, "not_found"),
            ("GET /api/stats/nope", self.client.get("/api/stats/nope"), 404, "not_found"),
            ("GET /api/analyze", self.client.get("/api/analyze"), 405, "method_not_allowed"),
            ("period=year", self.client.get("/api/stats/growth", {"period": "year"}), 400, "invalid_filter"),
            ("start=31/12/2025", self.client.get("/api/stats/growth", {"start": "31/12/2025"}), 400, "invalid_filter"),
            ("source=fake", self.client.get("/api/stats/growth", {"source": "fake"}), 400, "invalid_filter"),
        ]
        for label, r, status, code in cases:
            show(f"{label:20s} -> {r.status_code} {strict_json(r)['error']['code']}")
            self.assertEqual((r.status_code, strict_json(r)["error"]["code"]), (status, code))

    def test_unhandled_exception_hides_details(self):
        c = Client(raise_request_exception=False)
        c.force_login(self.user)
        with mock.patch("core.views.run_model", side_effect=RuntimeError("internal secret path C:/model")):
            r = self.post_image(image_bytes(), client=c)
        show(f"status={r.status_code} body={r.content.decode()}")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(strict_json(r), {"error": {"code": "server_error"}})
        self.assertNotIn(b"Traceback", r.content)
        self.assertNotIn(b"internal secret", r.content)


class StatsTests(Base):
    def test_growth_known_rate_matches_analytics(self):
        rng = np.random.default_rng(0)
        spec = []
        for m in range(12):
            start, days = month(m)
            spec += [(start, days, "A", "caju", "nao_podre", round(2000 * 1.10 ** m)), (start, days, "A", "caju", "podre", round(500 * 1.20 ** m))]
        events = insert(FA.to_events(expand(spec, rng)))
        b = self.stat("growth", period="month")
        m = np.arange(12)
        rp = 500 * 1.2 ** m / (2000 * 1.1 ** m + 500 * 1.2 ** m)
        errs = {
            "good count growth vs 0.10": max_err(b["good"]["count_growth"][1:], [0.10] * 11),
            "rotten count growth vs 0.20": max_err(b["rotten"]["count_growth"][1:], [0.20] * 11),
            "rotten prop growth vs analytic": max_err(b["rotten"]["prop_growth"][1:], rp[1:] / rp[:-1] - 1),
            "good prop growth vs analytic": max_err(b["good"]["prop_growth"][1:], (1 - rp[1:]) / (1 - rp[:-1]) - 1),
        }
        direct = FA.growth(events, "month")
        same = max_err(b["rotten"]["prop_growth"][1:], direct["rotten_prop_growth"].iloc[1:])
        show(f"n={b['n']} periods={b['n_periods']} max errors: " + ", ".join(f"{k}={v:.1e}" for k, v in errs.items()))
        show(f"endpoint vs direct fruit_analytics.growth: max diff {same:.1e}; first period growth = {b['good']['count_growth'][0]}")
        for v in errs.values():
            self.assertLess(v, 0.003)
        self.assertLess(same, 1e-12)
        self.assertIsNone(b["good"]["count_growth"][0])

    def test_previous_zero_and_empty_period(self):
        rng = np.random.default_rng(0)
        spec = []
        for m, good, rot in [(0, 100, 0), (1, 0, 0), (2, 50, 20), (3, 60, 30)]:
            start, days = month(m)
            spec += [(start, days, "A", "caju", "nao_podre", good), (start, days, "A", "caju", "podre", rot)]
        insert(FA.to_events(expand(spec, rng)))
        b = self.stat("growth", period="month")
        show(f"labels={b['labels']} good={b['good']['count']} rotten={b['rotten']['count']}")
        show(f"good count growth={b['good']['count_growth']} rotten count growth={b['rotten']['count_growth']} rotten prop growth={b['rotten']['prop_growth']}")
        self.assertEqual(b["good"]["count"], [100, 0, 50, 60])
        self.assertEqual(b["rotten"]["count"], [0, 0, 20, 30])
        self.assertEqual(b["good"]["count_growth"], [None, -1.0, None, 0.2])
        self.assertEqual(b["rotten"]["count_growth"][:3], [None, None, None])
        self.assertAlmostEqual(b["rotten"]["count_growth"][3], 0.5, places=12)
        self.assertEqual(b["rotten"]["prop_growth"][:3], [None, None, None])
        self.assertAlmostEqual(b["rotten"]["prop_growth"][3], 1 / 6, places=12)
        self.assertEqual(b["rotten"]["prop"][1], None)

    def test_partial_boundary_periods_excluded(self):
        rng = np.random.default_rng(0)
        spec = [(pd.Timestamp("2024-01-15"), 17, "A", "caju", "nao_podre", 500)]
        for m, good, rot in [(1, 1000, 100), (2, 1100, 110)]:
            start, days = month(m)
            spec += [(start, days, "A", "caju", "nao_podre", good), (start, days, "A", "caju", "podre", rot)]
        spec += [(pd.Timestamp("2024-04-01"), 10, "A", "caju", "nao_podre", 200), (pd.Timestamp("2024-04-01"), 10, "A", "caju", "podre", 20)]
        insert(FA.to_events(expand(spec, rng)))
        g = self.stat("growth", period="month")
        r = self.stat("recurring")
        show(f"data 2024-01-15..2024-04-10: growth labels={g['labels']} good={g['good']['count']} growth={g['good']['count_growth']} n={g['n']} excluded={g['excluded']}")
        show(f"recurring month buckets={r['month']['buckets']} excluded={r['month']['excluded']}; season buckets={r['season']['buckets']} n={r['season']['n']} (summer run Feb-Mar is incomplete)")
        self.assertEqual(g["labels"], ["2024-02", "2024-03"])
        self.assertEqual((g["n"], g["excluded"]), (2310, 720))
        self.assertEqual(g["good"]["count_growth"][0], None)
        self.assertAlmostEqual(g["good"]["count_growth"][1], 0.1, places=12)
        self.assertEqual((r["season"]["buckets"], r["season"]["n"]), ([], 0))

    def test_dominant_deformity_known(self):
        rng = np.random.default_rng(0)
        kinds = ["podre", "queimada", "quebrada"]
        truth, spec = {}, []
        for w in range(20):
            if w == 12:
                truth[w] = "none"
                continue
            top = "tie" if w == 15 else "queimada" if w < 7 else "podre" if w < 14 else "quebrada"
            truth[w] = top
            n = [100, 100, 100] if w == 15 else rng.multinomial(300, [0.6 if k == top else 0.2 for k in kinds])
            spec += [(week(w), 7, "A", "caju", k, c) for k, c in zip(kinds, n)] + [(week(w), 7, "A", "caju", "nao_podre", 700)]
        insert(FA.to_events(expand(spec, rng)))
        b = self.stat("deformity")
        weeks = [w for w, t in truth.items() if t not in ("none", "tie")]
        correct = sum(b["dominant"][w] == truth[w] for w in weeks)
        share_err = max(abs(b["share"][w] - 0.6) for w in weeks)
        show(f"dominant correct {correct}/{len(weeks)}; max |share-0.6|={share_err:.4f}; empty week -> {b['dominant'][12]}, share={b['share'][12]}, n={b['n_rotten'][12]}; tie week tie={b['tie'][15]}")
        self.assertEqual(correct, len(weeks))
        self.assertLess(share_err, 0.10)
        self.assertEqual((b["dominant"][12], b["share"][12], b["n_rotten"][12]), ("none", None, 0))
        self.assertTrue(b["tie"][15])
        self.assertEqual(len(b["weeks"]), 20)

    def test_fruit_counts_and_date_filter(self):
        rng = np.random.default_rng(0)
        (jan, jd), (feb, fd) = month(0), month(1)
        spec = [(jan, jd, "A", "caju", "nao_podre", 500), (jan, jd, "A", "castanha", "nao_podre", 300), (jan, jd, "A", "melao", "podre", 900),
                (feb, fd, "A", "caju", "nao_podre", 2000), (feb, fd, "A", "castanha", "podre", 100)]
        insert(FA.to_events(expand(spec, rng)))
        full = self.stat("fruits")
        jan_only = self.stat("fruits", start="2024-01-01", end="2024-01-31")
        empty = self.stat("fruits", start="2025-01-01", end="2025-01-31")
        show(f"all: {[(i['fruit'], i['n']) for i in full['items']]} top={full['top']}")
        show(f"Jan: {[(i['fruit'], i['n']) for i in jan_only['items']]} top={jan_only['top']}; empty window -> {empty['status']} n={empty['n']}")
        self.assertEqual([(i["fruit"], i["n"]) for i in full["items"]], [("caju", 2500), ("melao", 900), ("castanha", 400)])
        self.assertEqual(full["top"], "caju")
        self.assertEqual((jan_only["top"], jan_only["n"]), ("melao", 1700))
        self.assertEqual((empty["status"], empty["n"]), ("no_data", 0))

    def test_forecast_known_trend(self):
        events = insert(trend_events(0))
        b = self.stat("forecast")
        s = {x["sector"]: x for x in b["sectors"]}
        r, f, short = s["rising"], s["flat"], s["short"]
        direct = FA.forecast(events, "week")
        show(f"rising: pred={r['rotten_pred']:.4f} (truth 0.77) PI=[{r['rotten_lo']:.4f}, {r['rotten_hi']:.4f}] P(rotten>good)={r['p_more_rotten']:.4f} reliable={r['reliable']} bt_mae={r['bt_mae']:.4f} naive={r['bt_naive_mae']:.4f}")
        show(f"flat: pred={f['rotten_pred']:.4f} (truth 0.10) P={f['p_more_rotten']:.2e}; short: status={short['status']} n_periods={short['n_periods']} pred={short['rotten_pred']} P={short['p_more_rotten']} reasons={short['reasons']}")
        show(f"endpoint vs direct fruit_analytics.forecast: |dpred| rising={abs(r['rotten_pred'] - direct.loc['rising', 'rotten_pred']):.1e}")
        self.assertLess(abs(r["rotten_pred"] - 0.77), 0.03)
        self.assertTrue(r["rotten_lo"] <= 0.77 <= r["rotten_hi"])
        self.assertGreater(r["p_more_rotten"], 0.95)
        self.assertTrue(r["reliable"])
        self.assertLess(f["p_more_rotten"], 0.01)
        self.assertEqual((short["status"], short["rotten_pred"], short["p_more_rotten"], short["reliable"]), ("insufficient_data", None, None, False))
        self.assertEqual(short["reasons"], ["insufficient_data"])
        self.assertEqual(short["history"][:25], [None] * 25)
        self.assertLess(abs(r["rotten_pred"] - direct.loc["rising", "rotten_pred"]), 1e-12)

    def test_forecast_small_sample_marked_unreliable(self):
        insert(trend_events(0, weeks=10))
        s = {x["sector"]: x for x in self.stat("forecast")["sectors"]}
        show(f"10 weeks: rising status={s['rising']['status']} reliable={s['rising']['reliable']} reasons={s['rising']['reasons']}")
        self.assertEqual(s["rising"]["status"], "ok")
        self.assertFalse(s["rising"]["reliable"])
        self.assertIn("few_periods", s["rising"]["reasons"])

    def test_gaussian_known_and_single_sector(self):
        n = 200
        events = insert(gauss_events(0, n=n))
        b = self.stat("gaussian")
        s = {x["sector"]: x for x in b["sectors"]}
        for name, mu, sd in (("A", 0.20, 0.04), ("B", 0.35, 0.06)):
            eff = np.sqrt(sd ** 2 + (mu * (1 - mu) - sd ** 2) / n)
            show(f"{name}: mean={s[name]['mean']:.4f} (truth {mu}) std={s[name]['std']:.4f} (expected {eff:.4f}) n={s[name]['n']} shapiro_p={s[name]['shapiro_p']:.3f} flagged={s[name]['flagged']} reasons={s[name]['reasons']}")
            self.assertLess(abs(s[name]["mean"] - mu), 0.01)
            self.assertLess(abs(s[name]["std"] - eff) / eff, 0.15)
        show(f"C (skewed): flagged={s['C']['flagged']} reasons={s['C']['reasons']} mass_outside={s['C']['mass_outside_01']:.3f}")
        self.assertTrue(s["C"]["flagged"])
        self.assertTrue({"not_normal", "outside_01"} <= set(s["C"]["reasons"]))
        for x in s.values():
            self.assertEqual(x["flagged"], bool(x["reasons"]))
            self.assertEqual(len(x["qq"]["theoretical"]), x["n"])
        props, _ = FA.sector_proportions(events, "week")
        self.assertLess(abs(s["A"]["mean"] - FA.gaussian_fit(props).loc["A", "mean"]), 1e-12)
        only_a = self.stat("gaussian", sector="A")
        fc_a = self.stat("forecast", sector="A")
        show(f"sector=A filter: gaussian sectors={[x['sector'] for x in only_a['sectors']]} mean={only_a['sectors'][0]['mean']:.4f}; forecast sectors={[x['sector'] for x in fc_a['sectors']]} status={fc_a['sectors'][0]['status']}")
        self.assertEqual([x["sector"] for x in only_a["sectors"]], ["A"])
        self.assertAlmostEqual(only_a["sectors"][0]["mean"], s["A"]["mean"], places=12)
        self.assertEqual(([x["sector"] for x in fc_a["sectors"]], fc_a["sectors"][0]["status"]), (["A"], "ok"))
        small = self.stat("gaussian", start=str(week(0).date()), end=str((week(10) - pd.Timedelta(days=1)).date()))
        show(f"10-week window: n per sector={[x['n'] for x in small['sectors']]} reasons={[x['reasons'] for x in small['sectors']]}")
        self.assertTrue(all("small_n" in x["reasons"] and x["n"] == 10 for x in small["sectors"]))

    def test_recurring_known_pattern(self):
        rng = np.random.default_rng(0)
        good_l, rot_l = {1: 1200, 2: 1440, 3: 1728}, {7: 130, 8: 169, 9: 220}
        spec = []
        for m in range(36):
            start, days = month(m)
            spec += [(start, days, "A", "caju", "nao_podre", good_l.get(start.month, 1000)), (start, days, "A", "caju", "podre", rot_l.get(start.month, 100))]
        insert(FA.to_events(expand(spec, rng)))
        b = self.stat("recurring")
        mo, se = b["month"], b["season"]
        exp_good = [{1: 0.2, 2: 0.2, 3: 0.2, 4: 1000 / 1728 - 1}.get(k, 0.0) for k in range(1, 13)]
        exp_rot = [{7: 0.3, 8: 0.3, 9: 220 / 169 - 1, 10: 100 / 220 - 1}.get(k, 0.0) for k in range(1, 13)]
        exp_season_good = [4368 / 3000 - 1, 3000 / 4368 - 1, 0.0, 0.0]
        exp_season_rot = [0.0, 0.0, 519 / 300 - 1, 300 / 519 - 1]
        errs = [max_err(mo["good"], exp_good), max_err(mo["rotten"], exp_rot), max_err(se["good"], exp_season_good), max_err(se["rotten"], exp_season_rot)]
        show(f"month buckets={mo['buckets']} max err good/rotten={errs[0]:.1e}/{errs[1]:.1e}; season buckets={se['buckets']} max err={errs[2]:.1e}/{errs[3]:.1e}; week max_n={b['week']['max_n']}")
        self.assertEqual(mo["buckets"], [str(k) for k in range(1, 13)])
        self.assertEqual(se["buckets"], ["summer", "autumn", "winter", "spring"])
        self.assertLess(max(errs), 1e-12)
        self.assertEqual(mo["good_n"][0], 2)

    def test_no_data_and_demo_separation(self):
        empty = {n: self.stat(n) for n in STATS}
        show("no events: " + ", ".join(f"{k}={v['status']}/n={v['n']}/demo={v['demo']}" for k, v in empty.items()))
        self.assertTrue(all(v["status"] == "no_data" and v["n"] == 0 and v["demo"] is False for v in empty.values()))
        self.post_image(image_bytes(), sector="real-sector")
        self.post_image(image_bytes(), sector="real-sector")
        pending = Event.objects.filter(is_demo=False, needs_review=True).count()
        before = self.stat("overview", source="real")
        Event.objects.filter(is_demo=False).update(needs_review=False)
        after = self.stat("overview", source="real")
        show(f"real photos pending review={pending}: overview n before review={before['n']}, after review={after['n']}")
        self.assertEqual(before["n"], 2 - pending)
        self.assertEqual(after["n"], 2)
        call_command("seed_demo", weeks=4, fruits_per_week=50, stdout=io.StringIO())
        n_demo = Event.objects.filter(is_demo=True).count()
        call_command("seed_demo", weeks=4, fruits_per_week=50, stdout=io.StringIO())
        real, demo, both = (self.stat("overview", source=s) for s in ("real", "demo", "all"))
        sectors_real = strict_json(self.client.get("/api/sectors"))["sectors"]
        show(f"real n={real['n']} demo={real['demo']} | demo n={demo['n']} demo={demo['demo']} | all n={both['n']} demo={both['demo']} | demo rows after 2 seeds={Event.objects.filter(is_demo=True).count()} (first seed {n_demo})")
        show(f"sectors?source=real -> {sectors_real}")
        self.assertEqual((real["n"], real["demo"]), (2, False))
        self.assertEqual((demo["n"], demo["demo"]), (n_demo, True))
        self.assertEqual((both["n"], both["demo"]), (n_demo + 2, True))
        self.assertEqual(Event.objects.filter(is_demo=True).count(), n_demo)
        self.assertEqual(sectors_real, ["real-sector"])


class CommandTests(TestCase):
    def test_adduser(self):
        with mock.patch.dict(os.environ, {"FRUITCAM_NEW_PASSWORD": "Melao-Amarelo-77"}):
            call_command("adduser", "joao", stdout=io.StringIO())
            with self.assertRaises(CommandError) as dup:
                call_command("adduser", "joao", stdout=io.StringIO())
        with mock.patch.dict(os.environ, {"FRUITCAM_NEW_PASSWORD": "123"}):
            with self.assertRaises(CommandError) as weak:
                call_command("adduser", "maria", stdout=io.StringIO())
        u = get_user_model().objects.get(username="joao")
        show(f"created joao check_password={u.check_password('Melao-Amarelo-77')} hashed={u.password.startswith('pbkdf2_sha256$')}; duplicate -> {dup.exception}; weak -> {weak.exception}")
        self.assertTrue(u.check_password("Melao-Amarelo-77"))
        self.assertFalse(get_user_model().objects.filter(username="maria").exists())
