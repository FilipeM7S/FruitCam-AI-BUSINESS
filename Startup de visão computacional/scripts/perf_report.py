import argparse
import json
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from record_demo import Server, until

PAGES = (("/inspecao", ".fruit-card"), ("/painel?source=demo", "[data-stat=overview] canvas"))
RUNS = 3
NETWORK = {"offline": False, "latency": 150, "downloadThroughput": 1.6 * 1024 * 1024 / 8, "uploadThroughput": 750 * 1024 / 8}
OBSERVE = """
window.__perf = { lcp: 0, cls: 0, long: [], fcp: 0 };
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__perf.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__perf.cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__perf.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true });
new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__perf.fcp = e.startTime; }).observe({ type: 'paint', buffered: true });
"""
READ = """() => {
  const p = window.__perf;
  const tbt = p.long.filter(([s]) => s >= p.fcp).reduce((s, [, d]) => s + Math.max(0, d - 50), 0);
  const res = [performance.getEntriesByType('navigation')[0], ...performance.getEntriesByType('resource')];
  const kinds = {};
  for (const e of res) { const k = e.initiatorType === 'navigation' ? 'html' : /\\.js$/.test(e.name) ? 'js' : /\\.css$/.test(e.name) ? 'css' : /\\.(avif|webp|jpe?g|png|svg)/.test(e.name) ? 'image' : /\\.woff2$/.test(e.name) ? 'font' : /\\/api\\//.test(e.name) ? 'api' : 'other'; kinds[k] = (kinds[k] || 0) + e.transferSize; }
  return { fcp: p.fcp, lcp: p.lcp, cls: p.cls, tbt, longTasks: p.long.length, bytes: res.reduce((s, e) => s + e.transferSize, 0), kinds, requests: res.length };
}"""


def measure(browser, server, cookies, path, ready):
    ctx = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion="no-preference", color_scheme="dark")
    ctx.add_cookies(cookies)
    ctx.add_init_script(OBSERVE)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    cdp.send("Network.emulateNetworkConditions", NETWORK)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    page.goto(server.url + path, wait_until="load", timeout=120000)
    page.wait_for_selector(ready, timeout=120000)
    page.wait_for_load_state("networkidle", timeout=120000)
    page.wait_for_timeout(2500)
    until(page, "!document.getElementById('boot')", 60000)
    result = page.evaluate(READ)
    ctx.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    args = parser.parse_args()
    out = ROOT / args.out
    work = Path(tempfile.mkdtemp(prefix="fruitcam_perf_"))
    server = Server(work)
    rows = {}
    try:
        server.warm_up()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge")
            boot = browser.new_context()
            page = boot.new_page()
            page.goto(server.url + "/login")
            page.fill("input[name=username]", "demo")
            page.fill("input[name=password]", server.password)
            page.click("button[type=submit]")
            page.wait_for_url(server.url + "/")
            cookies = boot.cookies()
            boot.close()
            for path, ready in PAGES:
                runs = [measure(browser, server, cookies, path, ready) for _ in range(RUNS)]
                rows[path] = {"runs": runs, "median": {k: statistics.median(r[k] for r in runs) for k in ("fcp", "lcp", "cls", "tbt", "longTasks", "bytes", "requests")}, "kinds": runs[0]["kinds"]}
            browser.close()
    finally:
        server.close()
        shutil.rmtree(work, ignore_errors=True)
    out.write_text(json.dumps({"method": {"viewport": "360x780 @2x, mobile, touch", "cpu_slowdown": 4, "network": "latency 150 ms, 1.6 Mbit/s down, 750 kbit/s up", "cache": "disabled", "runs": RUNS, "browser": "Microsoft Edge (Playwright channel msedge), headless"}, "pages": rows}, indent=1) + "\n", encoding="utf-8")
    for path, r in rows.items():
        m = r["median"]
        print(f"{path:22s} FCP {m['fcp']:7.0f} ms  LCP {m['lcp']:7.0f} ms  CLS {m['cls']:.3f}  TBT {m['tbt']:6.0f} ms  long tasks {m['longTasks']:.0f}  {m['bytes'] / 1024:7.1f} KB in {m['requests']:.0f} requests  {json.dumps({k: round(v / 1024, 1) for k, v in r['kinds'].items()})}")


if __name__ == "__main__":
    main()
