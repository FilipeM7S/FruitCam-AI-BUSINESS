# FruitCam AI: the web application

This document explains the FruitCam web app. It starts with the basic ideas (what a request, an API, a session, a component, an endpoint are) and ends with the code, file by file. The code itself has no comments; this file is the only place where it is explained.

**Status:** everything below was verified with automated tests, a scripted run of the real server, and a scripted headless Edge browser, all on this Windows machine. It was **not** verified on real phones, in other browsers, in production, or with real field data. See Part 7.

---

## Part 0: what the existing AI and analytics actually provide

I read the source directly. Nothing here is guessed.

### The model (`infer.py`, unchanged)

| Item | Exact fact |
|---|---|
| Load function | `load_model(checkpoint_path, device)` → `(model, classes)`. It calls `torch.load(checkpoint_path, map_location=device)`, builds `train.build_model(len(ckpt["classes"]), pretrained=False)` (a MobileNetV3-Small), loads `ckpt["model_state"]` and calls `model.eval()`. |
| Inference function | `predict(model, classes, image_path, device, img_size=224)` → `(label: str, confidence: float)`. It opens the file **by path**, converts it to RGB, resizes to 224×224, normalizes with ImageNet mean/std, applies softmax, and returns the class with the highest probability and that probability. |
| Labels it outputs | `model.pt` contains `classes = ['nao_podre', 'podre']`. Only two. There is **no** "queimada", "quebrada" or any other deformity class. |
| Output format | One label and one confidence **per image**, not per fruit. |
| Boxes | The model produces no boxes. `Bbox.detect_bbox(image, bg_is_light=True)` returns **one** box `(x0, y0, x1, y1)`: the largest dark region found by an Otsu threshold. It is image processing, not AI. |

Consequences for the app:

- **One verdict per photo.** The request asked for a "verdict good/rotten per fruit" with "detection boxes". The current pipeline cannot do that. The app shows the one box and one verdict the pipeline produces, and the UI says so ("um veredito por foto"). Per-fruit detection needs a detection model, which means retraining; that was out of scope.
- **The deformity type is always "podre".** `deformity_type = label` when rotten. Real uploads therefore always show "Podridão". The demo data contains `queimada` and `quebrada` only because the synthetic generator invents them.

### The analytics (`fruit_analytics.py`, unchanged)

All analytics functions take one **event table**, a pandas DataFrame with columns `timestamp, sector, fruit_type, is_good, deformity_type`, which is exactly what the database stores. The app calls these functions directly:

| Function | Input | Output |
|---|---|---|
| `deformity_counts(events)` → `dominant_deformity(t)` | events | week × type counts; per week: `dominant`, `share`, `n_rotten`, `tie` |
| `sector_proportions(events, period)` | events, `"week"` or `"month"` | period × sector table of rotten proportion (NaN where a sector had < 30 fruits), plus counts |
| `forecast(events, period)` | events | per sector: `status`, `n_periods`, `slope`, `rotten_pred/lo/hi`, `p_more_rotten`, backtest metrics, `target_period` |
| `fruit_counts(events)` | events | n and share per fruit type |
| `growth(events, period)` | events | per period: counts, proportions, `*_count_growth`, `*_prop_growth` (NaN when previous = 0) |
| `recurring_growth(events, period)` | events, `"week"`/`"month"`/`"season"` | per bucket: median good and rotten count growth, plus n |
| `gaussian_fit(props)` | output of `sector_proportions` | per sector: `n, mean, std, shapiro_w, shapiro_p, mass_outside_01, flagged, reason` |
| `counts(events, period)` | events | good and rotten count per period |

### Measured model accuracy

This is the only accuracy figure in this project, and it comes with caveats. I ran `predict` on the image folders that exist on disk:

| Folder | n | Accuracy | Notes |
|---|---|---|---|
| `data_real/train` | 2810 | 100.0% | Almost certainly the training set, so it says nothing about generalization |
| `data_real/val` | 516 | **91.7%** | `nao_podre` recall 95/113 = 84.1%, `podre` recall 378/403 = 93.8% |

`train.py` keeps the checkpoint with the best validation accuracy, so `data_real/val` was probably used to *select* the model. That makes 91.7% optimistic. It is not field accuracy, and it is not broken down by caju, castanha or melão (the folders don't record the fruit type). One of the test images in this project, a `nao_podre` validation crop, is predicted `podre` with 0.725 confidence. That is a real model error, visible in the test output. **The UI never states an accuracy.** It calls the number it shows "confiança do modelo" and says explicitly that confidence is not verified accuracy.

---

## Part 1: the concepts, from simplest to the ones the code relies on

### 1.1 Request and response
A browser and a server talk in **requests** and **responses**. A request says *what* (a URL like `/api/analyze`) and *how* (a **method**: `GET` to read, `POST` to send or create). The response carries a **status code** and a body:

- `200` OK; `201` created
- `400` your input is wrong; `403` you are not allowed; `404` not found; `405` wrong method; `413` file too large; `429` too many attempts
- `500` the server failed

### 1.2 JSON
The text format the server and the page use to exchange data, for example `{"n": 1200, "status": "ok"}`. JSON has `null` but no "NaN", so every missing number is sent as `null` and the page shows it as "indefinido" or "dados insuficientes", never as 0.

### 1.3 API and endpoint
An **API** is the set of URLs a program can call, and each URL is an **endpoint**. Here, `POST /api/analyze` runs the AI on a photo, and `GET /api/stats/growth` returns the growth numbers. The page never touches the database or the model directly; it only calls endpoints.

### 1.4 Session and cookie
HTTP forgets everything between requests. After a correct login, Django creates a **session** (a record on the server) and gives the browser a **cookie** (`sessionid`) holding its random ID. The browser sends the cookie back on every request, so the server knows who is calling. The cookie is `HttpOnly`, which means JavaScript cannot read it, so a script injected into the page cannot steal it.

### 1.5 Password hashing
Passwords are never stored. Django stores a **hash** (PBKDF2-SHA256 with a random salt and many iterations). At login it hashes what you typed and compares. A leaked database does not reveal passwords.

### 1.6 CSRF
A malicious site could make your browser send a `POST` to FruitCam, and the browser would attach your cookie automatically. **CSRF protection** stops this. Every `POST` must also carry a secret token in the `X-CSRFToken` header, which another site cannot read. The page gets the token from `/api/auth/csrf`, and the token changes at login.

### 1.7 Rate limiting
To slow down password guessing, login accepts at most **5 attempts per minute per IP**. The 6th attempt gets `429` with the number of seconds to wait.

### 1.8 Same origin and CORS
An **origin** is scheme + host + port (e.g. `https://fruitcam.example.com`). Browsers block a page from reading responses from a *different* origin unless that server allows it through **CORS** headers. Here Django serves both the page and the API from the **same origin**, so CORS is not needed and none is sent. The safest CORS policy is no CORS policy (verified: a request with a foreign `Origin` gets no `Access-Control-Allow-Origin` header).

### 1.9 Environment variables
Settings that change between machines, especially secrets, live outside the code in **environment variables**. The app refuses to start without `DJANGO_SECRET_KEY`.

### 1.10 Frontend, component, SPA, router, build
- The **frontend** is the code that runs in the browser.
- A **component** is a reusable piece of UI with its own template, logic and style. `StatCard.vue` is one dashboard card; `ChartBox.vue` draws one chart.
- **Vue** updates the page automatically when data changes.
- An **SPA** (single-page application) loads one HTML page once, and JavaScript then switches screens without reloading.
- The **router** maps URLs (`/login`, `/`, `/painel`) to screens and is where "protected routes" are enforced: no session means a redirect to `/login`.
- **Vite** is the **build** tool. It turns the `.vue` and `.js` files into one optimized JS file and one CSS file in `frontend/dist/`. Node.js is needed only for this step; the running app is pure Django.

### 1.11 Chart library
**Chart.js** is the single chart library. The backend sends numbers as JSON, and `charts.js` turns them into Chart.js configurations.

---

## Part 2: architecture

```
 Browser (Vue SPA)                          Django process (one Python process)
 ─────────────────                          ───────────────────────────────────────────────
 /login  ── POST /api/auth/login ─────────▶ views.login_view ─ Django auth (PBKDF2) + throttle
 /       ── POST /api/analyze (photo) ────▶ views.analyze
                                              ├ inference.save_upload  (validate, random name)
                                              ├ inference.run_model ─▶ infer.predict + Bbox.detect_bbox
                                              │                         (model loaded once, at startup)
                                              └ Event row in SQLite
 /painel ── GET /api/stats/<name>?filters ─▶ views.stats_view
                                              ├ stats.load_events  (SQLite → event DataFrame)
                                              └ stats.<name> ─▶ fruit_analytics.<function>
                                                 └ stats.clean (NaN → null)
 static JS/CSS ◀── WhiteNoise serves frontend/dist from the same origin
```

Why each dependency exists:
- **Django + DRF:** your decision. They call `infer.py` and `fruit_analytics.py` in-process.
- **WhiteNoise:** lets Django serve the built frontend itself with DEBUG off, so no second web server is needed for the page and the API to share one origin.
- **vue-router:** protected routes need URL-based navigation guards.
- **Chart.js:** the one chart library.

There is no state-management library and no UI framework.

---

## Part 3: the backend, file by file

All Python lives next to the existing scripts, so `import infer` and `import fruit_analytics` work directly with no path tricks.

### [manage.py](manage.py)
Django's standard command entry point (`runserver`, `migrate`, `test`, plus the two custom commands).

### [fruitcam/settings.py](fruitcam/settings.py)
Every setting is read from environment variables (table in Part 6).

- **Lines 17–23:** startup fails with `ImproperlyConfigured` if `DJANGO_SECRET_KEY` is missing. `DEBUG` defaults to **off**. `HTTPS` defaults to "on unless DEBUG" and drives secure cookies, the SSL redirect and HSTS.
- **Lines 73–87:** cookie and security headers. Session cookie `HttpOnly` + `SameSite=Lax` + `Secure` (under HTTPS); CSRF cookie `HttpOnly` (the page gets its token from JSON, not by reading the cookie); `X-Frame-Options: DENY`; `nosniff`; `Referrer-Policy: same-origin`; HSTS for one year under HTTPS.
- **Lines 89–93:** model path, upload directory, maximum upload size (8 MB) and maximum pixel count (40 MP).
- **`REST_FRAMEWORK`:**
  - **Authentication:** session login only.
  - **Default permission:** `IsAuthenticated`, so every endpoint is protected unless it explicitly opts out.
  - **Rendering:** JSON only (no HTML "browsable API").
  - **Login rate:** `5/min`.
  - **Errors:** a custom exception handler that formats every error the same way.
- Password validators require at least 10 characters and reject common or all-numeric passwords.

### [fruitcam/urls.py](fruitcam/urls.py)
- Maps the seven API routes.
- Unknown `/api/...` paths return JSON 404.
- Every other path returns the SPA's `index.html`, so `/painel` survives a page reload.
- `handler404` and `handler500` are JSON responses, so the client never sees an HTML error page or a stack trace.

### [fruitcam/wsgi.py](fruitcam/wsgi.py)
Builds the WSGI application and then calls `get_model()` once. The model is loaded **when the server starts**, not on the first request and never per request. A test confirms this.

### [core/models.py](core/models.py)
The `Event` table, one row per analyzed photo:

- **Analytics columns:** `timestamp, sector, fruit_type, is_good, deformity_type`, exactly the columns `fruit_analytics` expects.
- **Audit columns:** `confidence`, `user`, `image` (the random file name).
- **`is_demo`:** marks synthetic rows so the stats never mix them with real data unless asked.

### [core/inference.py](core/inference.py)
- **[`get_model()`](core/inference.py#L22):** calls `infer.load_model` once and caches the result for the life of the process (`lru_cache`). It uses CUDA if available, otherwise the CPU.
- **[`save_upload(f)`](core/inference.py#L28):** the upload gate, applied in order:
  1. Size above `MAX_UPLOAD_BYTES` → `file_too_large` (413).
  2. Declared content type not JPEG/PNG/WebP → `unsupported_type`.
  3. Pillow opens the **actual bytes**. If they aren't an image (text, SVG, HTML, truncated or corrupt data) → `invalid_image`. If the real format isn't JPEG/PNG/WebP (e.g. a GIF renamed `.png`) → `unsupported_type`. If width × height exceeds 40 MP → `image_too_large`, checked from the header *before* decoding, which also protects against decompression bombs.
  4. `im.load()` forces a full decode, so truncated files fail here.
  5. `ImageOps.exif_transpose` applies the phone's rotation flag, so the server analyzes the photo the same way up as the browser displays it.
  6. The image is saved as PNG under a **random 32-hex-character name** in `UPLOAD_DIR`. The client's file name is never used, so path traversal (`../../evil.png`) is impossible. Re-encoding also strips anything hidden in the original file. PNG is lossless, so the model sees exactly the decoded pixels.
- **[`run_model(path, image)`](core/inference.py#L49):** calls `infer.predict` and `Bbox.detect_bbox` unchanged, times both with `perf_counter` and reports `inference_ms`. `is_good` is `label in GOOD_LABELS`, and `deformity_type` is the label when rotten.

### [core/stats.py](core/stats.py)
- **[`load_events`](core/stats.py#L14):** filters by source (`real`, `demo` or `all`; default **`real`**), sector and date range. It reads the rows into the event DataFrame and converts timestamps from UTC to `America/Fortaleza`, so weeks and months follow local time. It also reports whether any demo rows were included, which drives the badge.
- **[`clean`](core/stats.py#L31):** converts numpy/pandas values to plain JSON. NaN and ±inf become `null`, never 0.
- **One builder per card**, each calling the analytics function listed in Part 0:
  - **[`forecast`](core/stats.py#L66):** adds a `reliable` flag and reason codes. A forecast is marked unreliable if it lacks the minimum data, has fewer than 20 periods, has no backtest, or does not beat the naive "repeat last period" forecast. The UI never calls a forecast "reliable"; one that passes is labeled "passou nos critérios mínimos (não é garantia de acerto)".
  - **[`gaussian`](core/stats.py#L155):** adds reason codes (`small_n`, `no_variance`, `not_normal`, `outside_01`) and the histogram, fitted curve and Q-Q points for the chart.
- **[`whole_periods`](core/stats.py#L111):** a rule I added after the browser check showed a fake **+2000%** October bar on the demo data (September contained only one day of data). Growth and recurrence now use only periods that the data covers from their first to their last day. For seasons, it also drops season runs that started or ended mid-season. The number of excluded fruits is returned and shown in the UI. Other cards are unaffected, because counts and proportions don't explode on partial periods.

### [core/views.py](core/views.py)
- **[`api_exception_handler`](core/views.py#L36):** every DRF error becomes `{"error": {"code", "detail"}}`. CSRF failures become `csrf_failed`; throttling adds `wait_seconds`.
- **`csrf_failure`, `not_found`, `server_error`:** JSON for errors that happen outside DRF. With DEBUG off, a crash returns `{"error": {"code": "server_error"}}` and nothing else (tested). The traceback goes to the server log only.
- **[`login_view`](core/views.py#L88):** enforces CSRF itself via `SessionAuthentication().enforce_csrf`. The first version used Django's `csrf_protect` decorator, and **the test caught that it did nothing**: DRF marks its views CSRF-exempt and the decorator inherited that flag. The view is throttled and returns `invalid_credentials` (400) for any wrong username or password (it doesn't reveal which one was wrong), then calls Django's `login` and returns the rotated CSRF token.
- **`logout_view`, `me`:** end the session; return the current user.
- **[`analyze`](core/views.py#L124):**
  1. Validates `sector` (whitespace collapsed, lowercased so "Norte" and "norte" don't become two sectors, 1–50 characters), `fruit_type` (`caju|castanha|melao`) and `image`.
  2. Saves the upload.
  3. Runs the model and creates the `Event`.
  4. Returns `event`, `detections` (one item: box, label, is_good, deformity_type, confidence), the image size, `inference_ms` and the model's classes.
- **[`stats_view`](core/views.py#L181):** validates the filters (`period` week/month, `source`, ISO dates; anything else → `invalid_filter`), loads events, returns `{"status": "no_data", "n": 0}` if nothing matches, otherwise the builder's payload plus `demo`.

### [core/management/commands/adduser.py](core/management/commands/adduser.py)
`python manage.py adduser <name>` is the only way to create users (there is no sign-up). It reads the password from `FRUITCAM_NEW_PASSWORD` or prompts for it without echo. It runs Django's password validators and refuses duplicates. To reset a password, use Django's built-in `python manage.py changepassword <name>`.

### [core/management/commands/seed_demo.py](core/management/commands/seed_demo.py)
`python manage.py seed_demo`:
1. Creates or resets the `demo` user (password from `FRUITCAM_DEMO_PASSWORD`, or a random one printed once).
2. **Deletes all previous demo rows** and inserts new ones, so running it twice never duplicates.
3. Generates the data with `demo_events()` from `test_fruit_analytics.py`: 104 weeks, 3 sectors (one Gaussian, one trending, one skewed), 3 fruits, 3 invented deformity types, about 125,000 rows, shifted to end last Sunday.

Every row has `is_demo=True`. Only these rows can ever be demo data.

### [core/tests.py](core/tests.py)
Covered in Part 5.

---

## Part 4: the frontend, file by file (`frontend/`)

- **[src/strings.js](frontend/src/strings.js):** every pt-BR string in the UI, including error messages keyed by the backend's error codes, card titles, one-sentence explanations, and fruit, deformity, season and month names. To translate the app, replace this one file. `fill()` substitutes `{placeholders}`.
- **[src/api.js](frontend/src/api.js):** the single `api()` function every screen uses:
  - sends cookies and the CSRF token;
  - encodes JSON or `FormData`;
  - converts any failure into an error carrying the backend's `code`;
  - after a `csrf_failed` (a stale token), refetches the token and retries once.
- **[src/auth.js](frontend/src/auth.js):** a tiny reactive `auth` object (`user`, `checked`) with `loadUser`, `login` and `logout`. This is the only shared state, which is why there's no state-management library.
- **[src/router.js](frontend/src/router.js):** routes `/login` (public), `/` (analyze) and `/painel` (dashboard). The guard checks the session once and redirects anonymous users to `/login?next=...`. The `next` parameter only accepts local paths, so it can't be abused as an open redirect.
- **[src/format.js](frontend/src/format.js):** pt-BR number, percent and date formatting:
  - `prob()` shows "> 99%" or "< 1%" rather than a falsely certain "100%" or "0%";
  - `confidence()` shows "> 99,9%" rather than "100%".
- **[src/charts.js](frontend/src/charts.js):** registers only the Chart.js parts that are used and builds each chart's configuration from the API payload.
  - **Colors:** good = leaf green `#2f7d4f` and rotten = cashew amber `#d9822b`. Both were checked with a colorblind-safety validator (protan ΔE 10.2, so they stay distinguishable). The amber is 2.85:1 against white, below the 3:1 graphics guideline. That is compensated by text: every chart has a written summary, and every verdict has a label and an icon, never color alone.
  - **Lines and gaps:** the 0% and 50% reference lines are drawn darker, and null growth values appear as gaps (`spanGaps: false`).
- **[src/components/ChartBox.vue](frontend/src/components/ChartBox.vue):** creates and destroys one Chart.js instance. The canvas has `role="img"` and an `aria-label`.
- **[src/components/StatCard.vue](frontend/src/components/StatCard.vue):** the card frame: title, one-sentence explanation, `n = ...`, and the explicit states. Loading shows a skeleton; an error shows the message; `no_data` shows "Sem dados para os filtros escolhidos". Only `ok` or `insufficient_data` render the content.
- **[src/views/LoginView.vue](frontend/src/views/LoginView.vue):** the login form with a busy state and error messages (wrong credentials; too many attempts with the wait time).
- **[src/views/UploadView.vue](frontend/src/views/UploadView.vue):** the main screen.
  - **Inputs:** sector field (with suggestions from existing sectors) and a fruit selector.
  - **Photo:** a drop zone you can click, drag onto, or focus and press Enter/Space. A separate **"Usar câmera"** button uses `capture="environment"`, which opens the rear camera on phones.
  - **States:** a spinner while analyzing.
  - **Result:** the photo with the box drawn as an SVG overlay, which scales exactly with the image. Also the verdict with an icon, confidence with a meter, the defect type when rotten, inference time, and the saved record number. Two notes: confidence is not accuracy, and there is one verdict per photo.
- **[src/views/DashboardView.vue](frontend/src/views/DashboardView.vue):** filters for period (week/month), sector, date range and data source (real / demo / both). Data loads in parallel, and stale responses are discarded when filters change quickly. Cards appear in the requested order:
  - **a. Defects per week:** stacked shares, plus the latest week's dominant type and a tie note.
  - **b. Per-sector forecast:** interval bars and the forecast point. Per sector: the chance of more rotten than good, the 95% interval, and backtest error vs. naive. An **"Não confiável"** tag lists the reasons; insufficient data says "X de 8 períodos mínimos".
  - **c. Fruit received:** horizontal bars and the top fruit (or a tie).
  - **d/e. Growth:** count and proportion growth, the latest value, the gap explanation, and the excluded partial periods.
  - **f. Recurrence:** tabs for week, month and season; a warning when each bar rests on fewer than 2 periods.
  - **g. Gaussian per sector:** mean, std, n, Shapiro W and p, flag reasons, histogram with fitted curve, and Q-Q plot. A flagged sector gets a warm background and an "Ajuste ruim ou não confiável" tag. An unflagged one says "isso não prova que os dados são normais".
  - **h. Overview:** five indicators plus volume per period split into good and rotten.

  The **"Dados de demonstração" badge** appears whenever any card's response includes demo rows. With no real data, a notice points to the demo option.
- **[src/style.css](frontend/src/style.css):** design tokens on `:root`:
  - **Palette:** warm paper background `#f6f4ee`, leaf green primary `#2f6b45`, cashew amber as the single accent (demo badge, warnings).
  - **Typography:** the system font stack, so it works offline at the summit.
  - **Layout:** mobile first, with breakpoints at 640 px (tablet) and 960 px (desktop: two-column cards, wide cards span both).
  - **Accessibility:** 44 px minimum touch targets; visible focus ring; skip link; `prefers-reduced-motion` turns animations off.
  - **Contrast:** every text/background pair was measured at ≥ 4.5:1 (lowest 5.31:1).

---

## Part 5: verification

### 5.1 Backend tests: 27 tests, all passing
Command: `python manage.py test core -v 2`. The full output is in [webapp_test_output.txt](webapp_test_output.txt). The output includes one Python traceback. That is the **server-side log** from the deliberate 500 test, proving the error is logged on the server while the client receives only `{"error": {"code": "server_error"}}`.

| Area | What the test did | Measured result |
|---|---|---|
| Wrong password | wrong password, unknown user | 400 `invalid_credentials` for both; `/me` still 403; correct password → 200 |
| Hashing | inspected the stored password field | starts with `pbkdf2_sha256$`; plaintext absent |
| Protected endpoints | 11 endpoints without login | all 11 → 403 `not_authenticated` |
| Rate limit | 7 wrong attempts, then the right password | `[400×5, 429, 429]`, then 429 `throttled` with `wait_seconds` 57 |
| CSRF | login and analyze without and with the token | without: 403 `csrf_failed` (both); with: login 200, analyze reaches validation (`image_required`); token rotated on login |
| Cookies | flags | `sessionid` HttpOnly + SameSite=Lax; `csrftoken` HttpOnly |
| Settings from environment | subprocess without and with the key | no key → exit 1 `ImproperlyConfigured`; key only → DEBUG False, HTTPS/secure cookies/SSL redirect on, HSTS 31,536,000 s |
| Upload rejections | 13 bad inputs | text as .png, SVG/HTML → `invalid_image`; PNG declared text/plain, real GIF (as .gif or as .png) → `unsupported_type`; truncated PNG and JPEG → `invalid_image`; over the size limit → 413; over the pixel limit → `image_too_large`; missing image, bad fruit, empty or 51-character sector → 400. **0 events and 0 files** left behind |
| File name | uploaded as `../../../evil.png` | stored as a 32-hex `.png` in the upload directory; nothing written outside |
| Valid upload | synthetic image | 201, one detection, `inference_ms` ≈ 39 ms |
| **Endpoint = direct `infer.py`** | 4 images (2 synthetic, 1 real `nao_podre` crop, 1 real `podre` crop) | label, confidence and box identical; worst \|Δconfidence\| = **0.0** (tolerance 1e-6) |
| Model loaded once | 3 requests after clearing the cache | `load_model` called **1** time |
| Loaded at startup | imported `fruitcam.wsgi` | the cache holds the model before any request |
| Persistence | compared the DB row with the response | timestamp, sector, fruit, is_good, deformity, confidence, user, is_demo all equal |
| JSON errors | unknown path, unknown stat, wrong method, bad filters, forced crash | 404 / 404 / 405 / 400 / 500, all JSON; no traceback or internal message in the 500 body |
| Growth, known rate | +10% good, +20% rotten per month | max error 1.3e-4 / 3.9e-4 (integer rounding); endpoint = `fruit_analytics.growth` exactly |
| previous = 0, empty month | Jan 100/0, Feb empty, Mar 50/20, Apr 60/30 | `[null, -1.0, null, 0.2]`, `[null, null, null, 0.5]`, proportion growth for Apr = 1/6 |
| Partial periods | data from 15 Jan to 10 Apr | Jan and Apr excluded (720 fruits); incomplete summer season excluded |
| Dominant deformity | 18 weeks with known truth, one empty week, one tie | 18/18 correct; empty week → `none`, share null; tie flagged |
| Fruit counts | 2500 / 900 / 400; January window | exact; January → melão; empty window → `no_data` |
| Forecast | rising 0.20 + 0.019/week, flat 0.10, short (5 weeks) | rising 0.7691 (truth 0.77, inside the 95% interval), P > 0.99; flat P < 0.01; short → `insufficient_data` with null numbers |
| Small sample | 10 weeks | status ok but `reliable=false`, reason `few_periods` |
| Gaussian | A μ = 0.20, B μ = 0.35, C skewed | means 0.2030 / 0.3465; std within 15% of expected; C flagged (`not_normal`, `outside_01`); 10-week window → all flagged `small_n` |
| Single sector | `sector=A` filter | one sector in Gaussian and forecast, same mean as unfiltered |
| Recurrence | 3-year monthly pattern | month and season medians exact (error ≤ 5.6e-17) |
| No data, demo separation | empty DB; then 2 real + demo rows, seeded twice | all 7 endpoints `no_data`, `demo=false`; real n = 2 / demo n = 634 / all n = 636; badge flag correct; reseeding didn't duplicate |
| `adduser` | strong, duplicate and weak passwords | created and hashed; duplicate refused; weak refused with Django's reasons |

The earlier analytics suite (`python test_fruit_analytics.py`) still passes: **64/64**.

### 5.2 Frontend build
`npm run build` succeeded: 37 modules, `index-*.js` 311.5 kB (111.1 kB gzipped), `index-*.css` 12.2 kB, `npm install` reported 0 vulnerabilities.

### 5.3 Real server, driven over HTTP and in headless Edge
I started `manage.py runserver` with DEBUG off on the seeded demo database (124,988 events) and checked:
- The SPA and its assets are served by WhiteNoise. `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` and `COOP` are present. No CORS header is sent to a foreign origin.
- Login → analyze a real crop (122 ms inference, 169 ms round trip) → all 7 stats endpoints (0.75–1.9 s each on 125k rows) → logout → `/me` 403.
- **Headless Microsoft Edge (Playwright)** at 390 px (phone), 820 px (tablet) and 1366 px (desktop):
  - logged in through the form; analyzed a photo; opened the dashboard on real (empty) and demo data;
  - **0 px horizontal overflow** at all three widths; `capture="environment"` present; 8 cards; demo badge visible;
  - no JavaScript errors (the console only logged the expected 403 from the pre-login session check).
- The rate limit also triggered in the browser run: the 6th login within a minute was refused.
- I looked at the screenshots. That surfaced the +2000% recurrence artifact, overflowing Q-Q charts, an oversized result photo on the phone, a hidden verdict tag and "100%" confidence. All of these were fixed, and the screenshots were retaken.

---

## Part 6: commands

All commands run from the project folder. The PowerShell syntax below is for this Windows machine.

**Install (once)**
```powershell
pip install -r requirements.txt
cd frontend; npm install; npm run build; cd ..
```

**Environment (each new terminal)**
```powershell
$env:DJANGO_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(50))")
$env:DJANGO_HTTPS = "0"
```
`DJANGO_HTTPS=0` is for running locally over plain `http://`. In production, leave it unset.

A new secret key on every terminal logs everyone out, which is harmless. For a stable key, store it once in your user environment variables.

**Database, users, demo data**
```powershell
python manage.py migrate
$env:FRUITCAM_NEW_PASSWORD = "uma-senha-longa-aqui"; python manage.py adduser ana; Remove-Item Env:FRUITCAM_NEW_PASSWORD
$env:FRUITCAM_DEMO_PASSWORD = "outra-senha-longa"; python manage.py seed_demo
```
`seed_demo` takes about 25 s. Run it again any time to reset the demo data. Without `FRUITCAM_DEMO_PASSWORD`, it prints a random password once.

**Tests**
```powershell
python manage.py test core -v 2
python test_fruit_analytics.py
```

**Start the app**
```powershell
python manage.py runserver 127.0.0.1:8000
```
Open http://127.0.0.1:8000, log in, and on the Painel choose **Dados → Demonstração** for the presentation.

**Frontend development with hot reload (optional)**
Run the server above, then `cd frontend; npm run dev` and open http://localhost:5173. Vite forwards `/api` to Django. *This mode was not exercised in my verification; only the built app was.*

**Environment variables**

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | **required** | Signs sessions and CSRF tokens |
| `DJANGO_DEBUG` | `0` | Never `1` in production |
| `DJANGO_HTTPS` | `1` unless DEBUG | Secure cookies, HTTPS redirect, HSTS |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | The domain(s) the app answers to |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | e.g. `https://fruitcam.example.com` |
| `DJANGO_HSTS_SECONDS` | 31536000 under HTTPS | HSTS duration |
| `DJANGO_BEHIND_PROXY` | `0` | Trust `X-Forwarded-Proto` from a reverse proxy |
| `FRUITCAM_NUM_PROXIES` | — | Number of proxies, so the rate limit sees the real client IP |
| `FRUITCAM_DB_PATH` | `db.sqlite3` | SQLite file |
| `FRUITCAM_TIME_ZONE` | `America/Fortaleza` | Timezone for week and month boundaries |
| `FRUITCAM_SESSION_SECONDS` | 43200 | Session length (12 h) |
| `FRUITCAM_MODEL_PATH` | `model.pt` | Checkpoint |
| `FRUITCAM_MODEL_IMG_SIZE` | 224 | Must match training |
| `FRUITCAM_UPLOAD_DIR` | `uploads/` | Where analyzed photos are kept (never served publicly) |
| `FRUITCAM_MAX_UPLOAD_MB` | 8 | Upload size limit |
| `FRUITCAM_MAX_IMAGE_MEGAPIXELS` | 40 | Pixel limit |
| `FRUITCAM_LOGIN_RATE` | `5/min` | Login rate limit |
| `FRUITCAM_STATIC_ROOT` | — | Set in production, then run `python manage.py collectstatic` |
| `FRUITCAM_NEW_PASSWORD` | — | Read by `adduser` |
| `FRUITCAM_DEMO_PASSWORD` | — | Read by `seed_demo` |

`python manage.py check --deploy` with production defaults reports only two warnings: HSTS `includeSubDomains` and `preload`. I left them off on purpose, because they commit every subdomain of your domain to HTTPS-only. Enable them only once you control the domain.

---

## Part 7: what was not verified, and known limitations

**Not verified:**
- **Real browsers and devices.** Only headless Edge on Windows was used. Safari/iOS, Chrome/Android and Firefox were not tested, and neither were screen readers.
- **Real phone camera capture.** `capture="environment"` is present in the HTML, but no phone was used. iPhones may send HEIC; Safari usually converts it to JPEG for uploads, but that was not tested, and HEIC is rejected by the server.
- **Production deployment.** No HTTPS, reverse proxy, real domain or WSGI server (gunicorn/waitress) was set up. `runserver` is for development only.
- **Vite dev mode** (`npm run dev`).
- **Real field data.** No real inspection log exists. Every statistical result shown so far comes from synthetic data. With a few weeks of real data, forecasts show "dados insuficientes" or "não confiável", and Gaussian fits show `small_n`. That is the intended, honest outcome.
- **Model accuracy in the field.** Only the 91.7% on `data_real/val` was measured, with the caveats in Part 0.

**Known limitations:**
- **One verdict and one box per photo.** That is what `infer.py` and `Bbox.py` do. The box comes from a threshold, not from the AI, and assumes a light background.
- **Deformity types:** real uploads can only be "podre" until the model is retrained with more classes.
- **Rate limiting** uses Django's in-memory cache, so it is per process. With several server processes, use a shared cache (e.g. Redis).
- **SQLite** is fine for an MVP. Many simultaneous writers would need PostgreSQL.
- **Stats speed:** each stats request reloads the events from the database (≈ 0.6–0.9 s for 125k rows; up to 1.9 s when 7 run in parallel). That's acceptable now; cache it if data grows by 10×.
- **Upload storage:** photos are stored as lossless PNG. A 12 MP phone photo can become tens of MB (estimated, not measured). Add a retention policy before real use.
- **`node_modules` inside OneDrive:** it has thousands of small files that OneDrive will try to sync (this made `npm install` take over 10 minutes). Consider excluding the folder from sync.

---

## Part 8: changes to existing files

**None.** `infer.py`, `Bbox.py`, `fruit_analytics.py`, `test_fruit_analytics.py`, `train.py`, `records.py`, `visualize.py` and `model.pt` are unchanged. The app imports `load_model`, `predict`, `detect_bbox`, the analytics functions and the synthetic generator `demo_events` as they are.

New files and folders:
- `manage.py`, `requirements.txt`
- `fruitcam/` (`settings.py`, `urls.py`, `wsgi.py`)
- `core/` (`models.py`, `inference.py`, `stats.py`, `views.py`, `apps.py`, `tests.py`, `migrations/0001_initial.py`, `management/commands/adduser.py`, `seed_demo.py`)
- `frontend/` (`package.json`, `package-lock.json`, `vite.config.js`, `index.html`, `public/favicon.svg`, `src/…`, and the generated `dist/` and `node_modules/`)
- `webapp_test_output.txt`, `WEBAPP.md`

Created when you run the app: `db.sqlite3`, `uploads/`.
