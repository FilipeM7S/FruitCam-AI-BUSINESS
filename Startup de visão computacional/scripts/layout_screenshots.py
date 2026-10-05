import argparse
import json
import time
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from record_demo import PHOTO, Server, until

WIDTHS = (360, 768, 1280)
PAGES = (("login", "/login"), ("linha", "/"), ("inspecao", "/inspecao"), ("painel", "/painel"), ("como-funciona", "/como-funciona"), ("creditos", "/creditos"))


def settle(page):
    page.wait_for_load_state("networkidle")
    until(page, "!document.getElementById('boot') && [...document.images].every((i) => i.complete || i.loading === 'lazy')")
    page.wait_for_timeout(600)


def scroll_through(page):
    height = page.evaluate("document.documentElement.scrollHeight")
    for y in range(0, height + 900, 400):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(80)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)


def login(page, server):
    page.goto(server.url + "/login")
    page.fill("input[name=username]", "demo")
    page.fill("input[name=password]", server.password)
    page.click("button[type=submit]")
    page.wait_for_url(server.url + "/")


def shoot(browser, server, out, width):
    ctx = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce", color_scheme="dark", device_scale_factor=1)
    page = ctx.new_page()
    for name, path in PAGES:
        if name == "linha":
            login(page, server)
        page.goto(server.url + path)
        settle(page)
        if name == "linha":
            try:
                until(page, "document.querySelector('.live')?.dataset.online === 'yes'", 60000)
            except TimeoutError:
                status = Path(server.env["FRUITCAM_RUN_DIR"]) / "linha-1" / "status.json"
                age = time.time() - json.loads(status.read_text())["updated"] if status.exists() else None
                print(f"{width}px: camera not shown online after 60 s; worker running {server.workers[0].poll() is None}; status file age {age}; page says {page.evaluate('(document.querySelector(\".live\") || {}).dataset?.online')}", flush=True)
            page.wait_for_timeout(1500)
        if name == "painel":
            page.locator(".filters select").last.select_option("demo")
            until(page, "document.querySelectorAll('canvas').length >= 8", 60000)
            page.wait_for_timeout(1500)
        scroll_through(page)
        page.screenshot(path=str(out / f"{name}-{width}.jpg"), full_page=True, type="jpeg", quality=82)
        if name == "inspecao":
            page.locator(".fruit-card", has_text="Caju").click()
            page.fill("input[list=sector-list]", "Linha 1")
            page.locator("input[type=file]").first.set_input_files(str(PHOTO))
            page.evaluate("document.querySelector('.analyze-grid form').requestSubmit()")
            until(page, "!!document.querySelector('.verdict')", 60000)
            page.wait_for_timeout(800)
            scroll_through(page)
            page.screenshot(path=str(out / f"inspecao-resultado-{width}.jpg"), full_page=True, type="jpeg", quality=82)
    ctx.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    args = parser.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="fruitcam_layout_"))
    server = Server(work, cameras=("linha-1",))
    try:
        server.warm_up()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge")
            for width in WIDTHS:
                shoot(browser, server, out, width)
            browser.close()
    finally:
        server.close()
        shutil.rmtree(work, ignore_errors=True)
    for f in sorted(out.glob("*.jpg")):
        print(f"{f.name:32s} {f.stat().st_size:9d} B")


if __name__ == "__main__":
    main()
