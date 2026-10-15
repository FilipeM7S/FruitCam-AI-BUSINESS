import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_demo import FFMPEG, OUT, PHOTO, ROOT, SIZE, Server, captions, until, visible

NAME = "primeira-analise"
VF = "fps=30,scale=in_range=full:out_range=tv,format=yuv420p"


def login(ctx, server):
    token = ctx.request.get(server.url + "/api/auth/csrf").json()["csrf_token"]
    r = ctx.request.post(server.url + "/api/auth/login", data={"username": "demo", "password": server.password}, headers={"X-CSRFToken": token, "Referer": server.url})
    if not r.ok:
        raise RuntimeError(f"login failed: {r.status}")


def record(browser, server, work):
    ctx = browser.new_context(viewport=SIZE, device_scale_factor=1, locale="pt-BR", color_scheme="dark", reduced_motion="no-preference", record_video_dir=str(work / "raw"), record_video_size=SIZE)
    login(ctx, server)
    page = ctx.new_page()
    t0 = time.time()
    errors, marks, seen = [], [], set()
    page.on("pageerror", lambda e: errors.append(str(e)))

    def mark(text):
        marks.append((time.time() - t0, text))
        seen.update(visible(page))

    def hold(ms):
        page.wait_for_timeout(ms)
        seen.update(visible(page))

    page.goto(server.url + "/inspecao")
    page.wait_for_selector("#boot", state="detached")
    until(page, "[...document.images].every((i) => i.complete || i.loading === 'lazy')")
    page.evaluate("window.scrollTo(0, document.querySelector('.live-strip').getBoundingClientRect().top + scrollY - 76)")
    hold(500)
    mark("Inspeção por foto: escolha a fruta, o setor e a foto. Uma fruta por foto.")
    page.locator(".fruit-card", has_text="Caju").click()
    hold(500)
    page.locator("input[list=sector-list]").press_sequentially("Recepção", delay=80)
    page.locator("input[type=file]").first.set_input_files(str(PHOTO))
    hold(1400)
    mark("A faixa de estado mostra as etapas reais do pedido: envio, análise e conclusão, com o tempo medido.")
    page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
    page.wait_for_selector(".verdict")
    hold(1500)
    result = page.evaluate("({ label: document.querySelector('.verdict-label').textContent.trim(), review: !!document.querySelector('.review-note'), ms: document.querySelector('.live-facts').textContent.trim() })")
    poster_at = time.time() - t0
    mark(f"Resultado: saída real do modelo para esta foto: {result['label'].lower()}" + (". O sistema não decide sozinho: a fruta vai para revisão manual." if result["review"] else "."))
    hold(3200)
    page.click(".annotated-open")
    page.wait_for_selector(".inspect-fields")
    hold(600)
    mark("O inspetor mostra só os campos salvos no banco e o recorte que o modelo recebeu.")
    hold(3400)
    page.keyboard.press("Escape")
    hold(400)
    page.goto(server.url + "/historico")
    page.wait_for_selector(".history-table tbody tr")
    hold(500)
    mark("O registro aparece no Histórico, com filtros, seleção e exportação em CSV.")
    hold(3200)
    end = time.time() - t0
    video = page.video
    ctx.close()
    if errors:
        raise RuntimeError(f"page errors during recording: {errors}")
    return Path(video.path()), marks, end, poster_at, result, seen


def main():
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("frontend/dist is missing: run `npm run build` in frontend/ first")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        server = Server(work)
        try:
            server.warm_up()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="msedge")
                raw, marks, end, poster_at, result, seen = record(browser, server, work)
                browser.close()
        finally:
            server.close()
        start = max(0.0, marks[0][0] - 0.3)
        marks = [(t - start, text) for t, text in marks]
        end -= start
        base = [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(raw)]
        subprocess.run([*base, "-vf", VF, "-c:v", "libvpx-vp9", "-crf", "40", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-an", "-map_metadata", "-1", str(OUT / f"{NAME}.webm")], check=True)
        subprocess.run([*base, "-vf", VF, "-c:v", "libx264", "-crf", "29", "-preset", "veryslow", "-tune", "animation", "-movflags", "+faststart", "-an", "-map_metadata", "-1", str(OUT / f"{NAME}.mp4")], check=True)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{poster_at + 0.9:.3f}", "-i", str(raw), "-frames:v", "1", str(OUT / f"{NAME}-poster.png")], check=True)
    (OUT / f"{NAME}.vtt").write_text(captions(marks, end), encoding="utf-8")
    meta = {
        "width": SIZE["width"],
        "height": SIZE["height"],
        "duration": round(end, 1),
        "alt": "Gravação de tela do app FruitCam_ai: inspeção de uma foto de caju com a faixa de estado, o resultado com a confiança, o inspetor da fruta e o registro aparecendo no Histórico.",
        "posterAlt": "Resultado de uma inspeção por foto: caju com a caixa marcada, o veredito do modelo e o anel de confiança.",
        "caption": f"Gravação do app real em execução ({round(end)} s, sem áudio), feita com Playwright. A foto é real e o resultado é a saída real do modelo.",
        "transcript": [text for _, text in marks],
        "contains": sorted(seen),
        "result": result,
    }
    (OUT / f"{NAME}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for suffix in (".webm", ".mp4", ".vtt", "-poster.png"):
        path = OUT / f"{NAME}{suffix}"
        print(f"{path.name:28s} {path.stat().st_size:9d} B")
    print(f"{meta['duration']} s; model said {result}; third-party assets visible: {meta['contains']}")


if __name__ == "__main__":
    main()
