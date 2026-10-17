"""Browser test: landing page -> API -> pipeline -> fake Gemini, all in one process.

    pip install playwright && playwright install chromium
    python tests/test_ui.py
"""
import io
import json
import os
import sys
import threading
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fake_gemini  # noqa: E402

fake = ThreadingHTTPServer(("127.0.0.1", 0), fake_gemini.H)
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ["CITEFORGE_GEMINI_BASE"] = f"http://127.0.0.1:{fake.server_address[1]}"
os.environ["GEMINI_API_KEY"] = "test-key"

import server  # noqa: E402

server.JOBS_DIR.mkdir(exist_ok=True)
app = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
threading.Thread(target=app.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{app.server_address[1]}"

from playwright.sync_api import sync_playwright  # noqa: E402

results = {}
errors = []
XSS = "home battery <img src=x onerror=window.__pwned=1> lifespan"

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text else None)  # Google Fonts: no network in CI
    page.goto(BASE + "/")
    page.wait_for_function("document.getElementById('lgo') && !document.getElementById('lgo').disabled", timeout=8000)
    results["backend detected, run button enabled"] = True

    page.click("nav a.btn.p")                                    # "Try the demo" -> arena popup
    page.wait_for_selector("#modal:not([hidden]) #lf", timeout=5000)
    results["live runner visible inside popup"] = page.is_visible("#modal #lt")

    page.fill("#lt", XSS)
    page.fill("#lu", "https://user.github.io/geo/")
    page.click("#lgo")
    page.wait_for_selector("#lres:not([hidden])", timeout=120000)
    txt = page.inner_text("#lres")
    results["results rendered"] = "facts supported" in txt.lower() and "key facts and what the evidence says" in txt.lower()
    results["verdict chips"] = page.locator("#lres .chip.ok").count() >= 5 and page.locator("#lres .chip.mid").count() >= 1
    results["citation tile shows a live ratio"] = "/ 6" in page.inner_text("#lres .ltiles")
    results["audit passed shown"] = "Passed" in txt
    results["no injected element from topic/LLM"] = page.evaluate("window.__pwned") is None and page.locator("#lres img, #lres script").count() == 0
    results["button re-enabled"] = page.is_enabled("#lgo")

    href = page.get_attribute("#lres .lacts a.g", "href")
    zhref = page.get_attribute("#lres .lacts a.p", "href")
    r = urllib.request.urlopen(BASE + href)
    csp = r.headers.get("Content-Security-Policy", "")
    results["preview served with locked-down CSP"] = "default-src 'none'" in csp and b"<h1>" in r.read()
    names = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(BASE + zhref).read())).namelist()
    results["zip has site files"] = {"docs/index.html", "docs/llms.txt", "docs/robots.txt"} <= set(names)

    page.keyboard.press("Escape")
    page.wait_for_selector("#modal", state="hidden")
    results["studio updated"] = "Home battery lifespan: what the evidence says" in page.inner_text(".studio .art h3") \
        and page.inner_text(".studio .sbar span:nth-child(2)").lower() == "live workspace"
    kp = page.inner_text(".kpis").lower().replace("\n", "")
    results["KPIs are live numbers"] = "citation coverage" in kp and "fact support" in kp and "88%" in kp
    results["verdict panel"] = "supported" in page.inner_text(".dgrid .panel:nth-child(2)").lower()
    results["fine print updated"] = "live results from your latest run" in page.inner_text(".dark .fine").lower()
    page.screenshot(path=str(ROOT / "tests" / "shot_testing.png"), clip=None, full_page=False)
    page.click("nav a.btn.p")
    page.wait_for_selector("#modal:not([hidden]) #lres")
    page.screenshot(path=str(ROOT / "tests" / "shot_results.png"))
    results["results survive reopening popup"] = page.is_visible("#modal #lres")
    page.keyboard.press("Escape")

    # simulation still works
    page.click("nav a.btn.p"); page.wait_for_selector("#modal:not([hidden]) #chips button")
    page.click("#modal #chips button >> nth=0")
    page.wait_for_function("document.getElementById('an').textContent.length > 20", timeout=8000)
    results["simulation untouched"] = True
    b.close()

# bad input is rejected by the API
def post(body):
    req = urllib.request.Request(BASE + "/api/jobs", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req).status
    except urllib.error.HTTPError as e:
        return e.code

results["API rejects short topic / javascript: url"] = post({"topic": "a"}) == 400 and post({"topic": "valid topic", "url": "javascript:alert(1)"}) == 400
req = urllib.request.Request(BASE + "/../server.py")
try:
    code = urllib.request.urlopen(BASE + "/..%2fserver.py").status
except urllib.error.HTTPError as e:
    code = e.code
results["no path traversal"] = code == 404
results["no console/page errors"] = not errors

for k, v in results.items():
    print(("PASS " if v else "FAIL ") + k)
if errors:
    print("ERRORS:", errors[:5])
sys.exit(0 if all(results.values()) else 1)
