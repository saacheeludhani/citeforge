"""End-to-end test of the pipeline against the fake Gemini endpoint (no key, no network).

    python tests/test_pipeline.py
"""
import json
import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fake_gemini  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), fake_gemini.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["CITEFORGE_GEMINI_BASE"] = f"http://127.0.0.1:{srv.server_address[1]}"
os.environ["GEMINI_API_KEY"] = "test-key"

import citeforge as cf  # noqa: E402

out = Path(tempfile.mkdtemp()) / "site"
events = []
res = cf.pipeline("home battery lifespan", url="https://user.github.io/geo/", rounds=2, sample=4,
                  max_claims=8, out=out, progress=lambda s, m, p: events.append((s, p)))

m = res["metrics"]
print(json.dumps(m, indent=1))
print("notes:", res["notes"])
print("audit:", res["audit"])
print("history:", res["history"])

checks = {
    "mode LIVE": res["mode"] == "LIVE",
    "stages reported": {"queries", "page", "verify", "edit", "audit", "arena", "publish", "done"} <= {e[0] for e in events},
    "contradicted fact removed from page": not any("exactly 40 years" in k for k in res["page"]["key_facts"]),
    "editor round fixed contradiction (round1 6/8 -> round2 7/8 supported)": res["history"][0]["supported"] == 6 and res["history"][1]["supported"] == 7,
    "claims verified": m["claims_total"] >= 7 and m["supported"] >= 5,
    "invented source URL dropped": all(ev["source_url"] != "https://totally-invented.example/x"
                                       for c in res["claims"] for ev in c["evidence"]),
    "grounded URL kept": any(ev["source_url"] == "https://energy.gov/guide" for c in res["claims"] for ev in c["evidence"]),
    "audit passed": res["audit"]["passed"],
    "citation test ran + matched Gemini title-as-domain": m["citations_tested"] == 4 and 0 < m["citation_hits"] < 4,
    "site files": {"index.html", "robots.txt", "sitemap.xml", "llms.txt"} <= set(res["files"]),
    "json serialisable": bool(json.dumps(res)),
}
html = (out / "index.html").read_text()
checks["badge rendered"] = "[Check: supported by retrieved sources" in html
checks["no script besides json-ld"] = html.count("<script") == 1
# scenario 2: a single round means the editor never runs -> the final guard must still strip the contradicted fact
res2 = cf.pipeline("home battery lifespan", rounds=1, sample=0, out=Path(tempfile.mkdtemp()) / "site2")
checks["guard strips contradicted fact when editor does not run"] = (
    res2["metrics"]["removed"] == 1 and not any("exactly 40 years" in k for k in res2["page"]["key_facts"])
    and any("removed" in n for n in res2["notes"]) and res2["metrics"]["citation_rate"] is None)
# scenario 3: no key -> offline skeleton, clearly flagged, never claims verification
os.environ["GEMINI_API_KEY"] = ""
res3 = cf.pipeline("home battery lifespan", rounds=2, out=Path(tempfile.mkdtemp()) / "site3", llm=cf.LLM())
checks["offline mode flagged, audit blocks placeholders"] = (
    res3["mode"] == "OFFLINE" and not res3["audit"]["passed"] and res3["metrics"]["claims_total"] == 0
    and any("Offline" in n for n in res3["notes"]))
bad = [k for k, v in checks.items() if not v]
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
sys.exit(1 if bad else 0)
