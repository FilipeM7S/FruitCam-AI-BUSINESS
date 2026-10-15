import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from record_demo import Server, until

HOOK = """
window.__live = [];
const Native = window.EventSource;
window.EventSource = function (url) {
  const source = new Native(url);
  window.__live.push({ t: Date.now(), type: 'open' });
  for (const name of ['summary', 'status']) source.addEventListener(name, (e) => {
    const body = JSON.parse(e.data);
    window.__live.push(name === 'summary' ? { t: Date.now(), type: name, end: body.end, total: body.total } : { t: Date.now(), type: name });
  });
  return source;
};
"""
SUMMARY = "fetch('/api/line?camera=linha-1&minutes=60&window=1&source=demo').then((r) => r.json()).then((s) => ({ total: s.total, end: s.end }))"
SHOWN = "(() => { const m = (document.querySelector('.kpis .kpi')?.innerText || '').match(/([0-9.]+) frutas/); return m ? Number(m[1].split('.').join('')) : null; })()"
META = "(document.querySelector('.live-meta')?.innerText || '').trim().split(String.fromCharCode(10))[0]"
HEALTH = "fetch('/api/health').then((r) => r.json())"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=90)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="fruitcam_live_"))
    server = Server(work, cameras=("linha-1",))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            problems, polls = [], []
            page.on("pageerror", lambda e: problems.append(str(e)))
            page.on("request", lambda r: polls.append(time.monotonic()) if "/api/line?" in r.url else None)
            page.add_init_script(HOOK)
            page.goto(server.url + "/login")
            page.wait_for_selector("#boot", state="detached")
            page.fill("input[name=username]", "demo")
            page.fill("input[name=password]", server.password)
            page.click("button[type=submit]")
            page.wait_for_url(server.url + "/")
            until(page, "document.querySelector('.live-pill.on') !== null", 90000)
            until(page, "window.__live.some((e) => e.type === 'summary')", 30000)
            opened = time.monotonic()
            before = len(polls)
            print(f"camera online; the page opened the live stream after {before} ordinary requests to /api/line")
            checks, metas, own = [], [], 0
            while time.monotonic() - opened < args.seconds:
                page.wait_for_timeout(10000)
                api = page.evaluate(SUMMARY)
                own += 1
                began = time.monotonic()
                while page.evaluate(SHOWN) != api["total"] and time.monotonic() - began < 8:
                    page.wait_for_timeout(200)
                shown = page.evaluate(SHOWN)
                checks.append((api["total"], shown))
                metas.append(page.evaluate(META))
                print(f"t={time.monotonic() - opened:5.1f} s  API total {api['total']} up to {api['end'][11:16]}  page shows {shown}  ({'equal' if shown == api['total'] else 'different'}, {time.monotonic() - began:.1f} s after asking)  | {metas[-1]}")
            log = page.evaluate("window.__live")
            summaries = [e for e in log if e["type"] == "summary"]
            ends = sorted({e["end"][11:16] for e in summaries})
            health = page.evaluate(HEALTH)
            cam = health["cameras"][0]
            print(f"live stream: {sum(e['type'] == 'open' for e in log)} connection, {sum(e['type'] == 'status' for e in log)} status messages and {len(summaries)} summaries, for the minutes ending {ends}")
            print(f"page equal to the API in {sum(a == b for a, b in checks)} of {len(checks)} checks; requests to /api/line made by the page itself after the stream opened: {len(polls) - before - own}")
            print(f"the line under the video changed in {sum(a != b for a, b in zip(metas, metas[1:]))} of {len(metas) - 1} consecutive checks, without a reload")
            print(f"/api/health: status {health['status']}; aggregates in step {health['aggregates']['in_sync']}; camera {cam['slug']} state {cam['state']}, counted {cam['counted']}, stored {cam['passages']}, queue {cam['backlog_bytes']} B, database busy {cam['db_busy']}, dropped frames {cam['dropped_frames']}")
            print(f"page errors: {problems}")
            browser.close()
    finally:
        server.close()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
