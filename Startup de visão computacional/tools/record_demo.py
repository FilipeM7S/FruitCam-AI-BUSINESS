import base64
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
import requests
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "media_src" / "video"
PHOTO = ROOT / "media_src" / "commons" / "caju-vermelho.jpg"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SIZE = {"width": 1280, "height": 720}
FPS = 30
MEDIA = json.loads((ROOT / "frontend" / "src" / "media.json").read_text(encoding="utf-8"))["items"]
VISIBLE = "[...document.querySelectorAll('[data-media], [data-bg]')].filter((f) => { const r = f.getBoundingClientRect(); return r.width > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; }).map((f) => f.dataset.media || f.dataset.bg)"
UPLOADED = "caju-vermelho"


def until(page, js, timeout=30000):
    deadline = time.time() + timeout / 1000
    while not page.evaluate(js):
        if time.time() > deadline:
            raise TimeoutError(js)
        page.wait_for_timeout(100)


def visible(page):
    shown = {MEDIA[v]["asset"] for v in page.evaluate(VISIBLE) if v in MEDIA and MEDIA[v].get("illustrative")}
    if page.evaluate("!!document.querySelector('.dropzone-preview img, .annotated img')"):
        shown.add(UPLOADED)
    return shown


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def django(env, *args, **kwargs):
    return subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, env=env, check=True, capture_output=True, text=True, **kwargs)


class Server:
    def __init__(self, work, cameras=()):
        self.password = secrets.token_urlsafe(12)
        self.env = {
            **os.environ,
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(40),
            "DJANGO_DEBUG": "0",
            "DJANGO_HTTPS": "0",
            "FRUITCAM_DB_PATH": str(work / "db.sqlite3"),
            "FRUITCAM_UPLOAD_DIR": str(work / "uploads"),
            "FRUITCAM_RUN_DIR": str(work / "run"),
            "FRUITCAM_DEMO_PASSWORD": self.password,
            "FRUITCAM_LOGIN_RATE": "100/min",
        }
        django(self.env, "migrate", "--noinput")
        django(self.env, "seed_demo", "--weeks", "40", "--fruits-per-week", "120")
        django(self.env, "seed_line_demo", "--hours", "8")
        self.workers = [subprocess.Popen([sys.executable, "manage.py", "run_camera", slug], cwd=ROOT, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for slug in cameras]
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.proc = subprocess.Popen([sys.executable, "manage.py", "runserver", f"127.0.0.1:{self.port}", "--noreload"], cwd=ROOT, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(120):
            try:
                urllib.request.urlopen(self.url + "/api/auth/csrf", timeout=1)
                return
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("server did not start")

    def warm_up(self):
        session = requests.Session()
        token = session.get(self.url + "/api/auth/csrf").json()["csrf_token"]
        headers = {"X-CSRFToken": token, "Referer": self.url}
        session.post(self.url + "/api/auth/login", json={"username": "demo", "password": self.password}, headers=headers).raise_for_status()
        headers["X-CSRFToken"] = session.cookies["csrftoken"]
        with PHOTO.open("rb") as f:
            session.post(self.url + "/api/analyze", data={"sector": "aquecimento", "fruit_type": "caju"}, files={"image": ("warm.jpg", f, "image/jpeg")}, headers=headers).raise_for_status()
        for name in ("deformity", "forecast", "fruits", "growth", "recurring", "gaussian", "overview"):
            session.get(self.url + f"/api/stats/{name}", params={"source": "demo", "period": "week"}).raise_for_status()
        session.get(self.url + "/api/line", params={"camera": "linha-1", "minutes": 60, "window": 1, "source": "demo"}).raise_for_status()
        django(self.env, "shell", "-c", "from core.models import Event; Event.objects.filter(is_demo=False).delete()")

    def close(self):
        for proc in [*self.workers, self.proc]:
            proc.terminate()
            proc.wait(timeout=20)


class Recorder:
    def __init__(self, page):
        self.page = page
        self.cdp = page.context.new_cdp_session(page)
        self.frames = []
        self.marks = []
        self.seen = set()
        self.cdp.on("Page.screencastFrame", self.on_frame)

    def on_frame(self, params):
        self.frames.append((params["metadata"]["timestamp"], params["data"]))
        self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    def start(self):
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": SIZE["width"], "maxHeight": SIZE["height"], "everyNthFrame": 1})
        self.page.wait_for_timeout(300)
        self.t0 = time.time()

    def mark(self, text):
        self.marks.append((time.time() - self.t0, text))
        self.seen |= visible(self.page)

    def hold(self, ms):
        self.page.wait_for_timeout(ms)
        self.seen |= visible(self.page)

    def stop(self):
        self.hold(400)
        self.cdp.send("Page.stopScreencast")
        self.end = time.time() - self.t0
        before = [data for t, data in self.frames if t < self.t0]
        after = [(t - self.t0, data) for t, data in self.frames if t >= self.t0]
        return ([(0.0, before[-1])] if before else []) + after


def encode(frames, end, work, outputs, crop=None):
    frame_dir = work / "frames"
    shutil.rmtree(frame_dir, ignore_errors=True)
    frame_dir.mkdir()
    lines = []
    for i, (t, data) in enumerate(frames):
        path = frame_dir / f"{i:05d}.jpg"
        path.write_bytes(base64.b64decode(data))
        nxt = frames[i + 1][0] if i + 1 < len(frames) else end
        lines += [f"file '{path.as_posix()}'", f"duration {max(nxt - t, 0.0005):.4f}"]
    lines.append(f"file '{(frame_dir / f'{len(frames) - 1:05d}.jpg').as_posix()}'")
    listing = work / "frames.txt"
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    base = ["-f", "concat", "-safe", "0", "-i", str(listing)]
    vf = f"fps={FPS}" + (f",crop={crop}" if crop else "") + ",scale=in_range=full:out_range=tv,format=yuv420p"
    for path, codec in outputs:
        if codec == "webm":
            args = ["-vf", vf, "-c:v", "libvpx-vp9", "-crf", "40", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]
        elif codec == "mp4":
            args = ["-vf", vf, "-c:v", "libx264", "-crf", "29", "-preset", "veryslow", "-tune", "animation", "-movflags", "+faststart"]
        else:
            args = ["-vf", f"fps=12{',crop=' + crop if crop else ''},scale=960:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=sierra2_4a"]
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", *base, *args, "-an", "-map_metadata", "-1", str(path)], check=True)


def stamp(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:06.3f}"


def captions(marks, end):
    cues = ["WEBVTT", ""]
    for i, (t, text) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else end
        cues += [f"{stamp(t)} --> {stamp(stop)}", text, ""]
    return "\n".join(cues)


def glide(page, selector, offset=76, steps=40):
    target = page.evaluate(f"document.querySelector('{selector}').getBoundingClientRect().top + window.scrollY - {offset}")
    origin = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        page.evaluate(f"window.scrollTo(0, {origin + (target - origin) * i / steps})")
        page.wait_for_timeout(30)


def demo(browser, server, work):
    ctx = browser.new_context(viewport=SIZE, device_scale_factor=1, locale="pt-BR", color_scheme="dark", reduced_motion="no-preference")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server.url + "/login")
    page.wait_for_selector("#boot", state="detached")
    until(page, "[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(1200)
    rec = Recorder(page)
    rec.start()
    stills, still_assets = {}, {}
    rec.mark("Login do FruitCam_ai. Ao fundo, vídeo ilustrativo de uma esteira de seleção (USDA, domínio público).")
    rec.hold(1600)
    page.locator("input[name=username]").press_sequentially("demo", delay=90)
    page.locator("input[name=password]").press_sequentially(server.password, delay=40)
    rec.hold(300)
    page.click("button[type=submit]")
    page.wait_for_url(server.url + "/")
    page.wait_for_selector(".hero")
    rec.mark("Página Linha: a câmera fixa sobre a esteira conta e classifica cada fruta. Ao fundo, a simulação processada pelo mesmo código.")
    rec.hold(2600)
    stills["1-linha"] = page.screenshot()
    still_assets["1-linha"] = sorted(visible(page))
    rec.mark("Linha ao vivo: quadro da câmera simulada, frutas por minuto e porcentagem de cada classe com intervalo de confiança. Dados sintéticos.")
    glide(page, "#linha")
    until(page, "!!document.querySelector('.kpi') && !!document.querySelector('.live-frame img')", 30000)
    rec.hold(3800)
    stills["2-monitor"] = page.screenshot()
    still_assets["2-monitor"] = sorted(visible(page))
    poster = page.screenshot(type="png")
    poster_assets = sorted(visible(page))
    rec.mark("Carta de controle da % de podres, alarmes e aceite de cada lote pelo intervalo de confiança.")
    glide(page, ".monitor-charts")
    rec.hold(3600)
    rec.mark("Como a câmera funciona: separa a fruta da esteira, segue a fruta entre quadros, classifica com IA e conta uma vez na linha tracejada.")
    glide(page, "#camera")
    rec.hold(3600)
    stills["3-camera"] = page.screenshot()
    still_assets["3-camera"] = sorted(visible(page))
    rec.mark("O botão ? abre o guia do usuário em qualquer página.")
    page.click(".help-fab")
    rec.hold(2600)
    page.keyboard.press("Escape")
    rec.hold(400)
    rec.mark("Inspeção por foto: uma foto real de caju (Wilfredor, CC0) passa pelo mesmo classificador de três classes.")
    page.click("nav.nav >> text=Inspeção")
    page.wait_for_selector(".fruit-card")
    page.locator(".fruit-card", has_text="Caju").click()
    page.locator("input[list=sector-list]").press_sequentially("Linha 1", delay=80)
    page.locator("input[type=file]").first.set_input_files(str(PHOTO))
    page.wait_for_selector(".dropzone-preview img")
    glide(page, ".analyze-grid", steps=20)
    page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
    page.wait_for_selector(".verdict")
    rec.hold(1200)
    result = page.evaluate("({ label: document.querySelector('.verdict-label').textContent.trim(), confidence: document.querySelector('.facts dd').textContent.trim(), review: !!document.querySelector('.review-note') })")
    rec.mark(f"Saída real do modelo: {result['label'].lower()}, confiança {result['confidence']}" + (", sem confiança suficiente para decidir sozinho: vai para revisão manual." if result["review"] else ".") + (" Este caju parece são: é um erro real do modelo. A foto não segue o guia (fruta entre folhas, sem fundo claro)." if result["label"] != "Boa" else " A foto tem folhas ao fundo, diferente da esteira."))
    rec.hold(3600)
    stills["4-inspecao"] = page.screenshot()
    still_assets["4-inspecao"] = sorted(visible(page))
    frames = rec.stop()
    ctx.close()
    if errors:
        raise RuntimeError(f"page errors during recording: {errors}")
    encode(frames, rec.end, work, [(OUT / "demo.webm", "webm"), (OUT / "demo.mp4", "mp4")])
    (OUT / "demo-poster.png").write_bytes(poster)
    (OUT / "demo.vtt").write_text(captions(rec.marks, rec.end), encoding="utf-8")
    story = OUT / "storyboard"
    shutil.rmtree(story, ignore_errors=True)
    story.mkdir()
    for name, png in stills.items():
        (story / f"{name}.png").write_bytes(png)
    meta = {
        "width": SIZE["width"],
        "height": SIZE["height"],
        "duration": round(rec.end, 1),
        "alt": "Gravação de tela do app FruitCam_ai: login, página da linha com a explicação da câmera, monitor ao vivo de uma câmera simulada com indicadores e gráficos, o guia do usuário e a inspeção de uma foto de caju.",
        "posterAlt": "Monitor da linha: quadro da câmera simulada com caixas coloridas nas frutas e indicadores de frutas por minuto e porcentagem de cada classe.",
        "caption": f"Gravação do app real em execução ({round(rec.end)} s, sem áudio). A câmera e os dados da linha são simulados e sintéticos; a foto da inspeção é real (CC0) e o resultado é a saída real do modelo.",
        "transcript": [text for _, text in rec.marks],
        "credit": "Gravação de tela do app FruitCam_ai (tools/record_demo.py). A interface gravada exibe fotos de terceiros da Wikimedia Commons, que mantêm suas licenças; autores e licenças na página Créditos.",
        "contains": sorted(rec.seen),
        "stills": still_assets,
        "poster": poster_assets,
        "result": result,
    }
    (OUT / "demo.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def hero_shots(browser, server):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, locale="pt-BR", color_scheme="dark", reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(server.url + "/login")
    page.wait_for_selector("#boot", state="detached")
    page.fill("input[name=username]", "demo")
    page.fill("input[name=password]", server.password)
    page.click("button[type=submit]")
    page.wait_for_url(server.url + "/")
    page.goto(server.url + "/inspecao")
    page.wait_for_selector(".fruit-card")
    page.locator(".fruit-card", has_text="Caju").click()
    page.fill("input[list=sector-list]", "Norte")
    page.locator("input[type=file]").first.set_input_files(str(PHOTO))
    page.wait_for_selector(".dropzone-preview img")
    page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
    page.wait_for_selector(".verdict")
    page.evaluate("window.scrollTo(0, document.querySelector('.analyze-grid').getBoundingClientRect().top + window.scrollY - 76)")
    page.wait_for_timeout(600)
    hero = OUT / "hero"
    shutil.rmtree(hero, ignore_errors=True)
    hero.mkdir()
    page.screenshot(path=hero / "app-resultado.png")
    shown = {"app-resultado.png": sorted(visible(page))}
    page.goto(server.url + "/")
    page.wait_for_selector(".hero")
    page.evaluate("document.getElementById('linha').scrollIntoView()")
    page.evaluate("window.scrollBy(0, -76)")
    until(page, "!!document.querySelector('.kpi') && !!document.querySelector('.live-frame img') && document.querySelector('.live-frame img').complete", 30000)
    page.wait_for_timeout(2500)
    page.screenshot(path=hero / "app-linha.png")
    shown["app-linha.png"] = sorted(visible(page))
    (hero / "hero.json").write_text(json.dumps(shown, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ctx.close()


def pipeline(browser, server, work):
    ctx = browser.new_context(viewport=SIZE, device_scale_factor=1, locale="pt-BR", color_scheme="dark", reduced_motion="no-preference")
    page = ctx.new_page()
    page.goto(server.url + "/como-funciona")
    page.wait_for_selector("#boot", state="detached")
    fig = page.locator(".pipeline")
    fig.scroll_into_view_if_needed()
    until(page, "document.querySelector('.pipeline').dataset.state === 'done'", 20000)
    page.evaluate("window.scrollBy(0, document.querySelector('.pipeline').getBoundingClientRect().top - 40)")
    page.wait_for_timeout(400)
    box = fig.bounding_box()
    rec = Recorder(page)
    rec.start()
    page.click(".pipe-replay")
    until(page, "document.querySelector('.pipeline').dataset.state === 'done'", 20000)
    rec.hold(1800)
    frames = rec.stop()
    ctx.close()
    w, h = int(box["width"]) // 2 * 2, int(box["height"]) // 2 * 2
    crop = f"{w}:{h}:{int(box['x'])}:{int(box['y'])}"
    encode(frames, rec.end, work, [(OUT / "pipeline.mp4", "mp4"), (OUT / "pipeline.gif", "gif")], crop=crop)
    return {"width": w, "height": h, "duration": round(rec.end, 1)}


def main():
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("frontend/dist is missing: run `npm run build` in frontend/ first")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        server = Server(work, cameras=("linha-1",))
        try:
            server.warm_up()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="msedge")
                meta = demo(browser, server, work)
                pipe = pipeline(browser, server, work)
                hero_shots(browser, server)
                browser.close()
        finally:
            server.close()
    for name in ("demo.webm", "demo.mp4", "demo-poster.png", "demo.vtt", "pipeline.mp4", "pipeline.gif"):
        print(f"{name:18s} {(OUT / name).stat().st_size:9d} B")
    print(f"demo {meta['duration']} s, model said {meta['result']}; pipeline clip {pipe}")
    with Image.open(OUT / "demo-poster.png") as im:
        print("poster", im.size)


if __name__ == "__main__":
    main()
