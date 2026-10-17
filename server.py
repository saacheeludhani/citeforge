#!/usr/bin/env python3
"""
CiteForge web server: connects the landing page (web/) to the pipeline (citeforge.py).
Standard library only.

    python server.py                 # http://127.0.0.1:8000
    PORT=9000 python server.py

API
  GET  /api/health                  -> {ok, mode, provider, model, reason}
  POST /api/jobs                    -> 202 {job_id}   body: {topic, url?, rounds?, sample?, max_claims?}
  GET  /api/jobs/<id>               -> {status, stage, message, percent, log[], result?, error?}
  GET  /api/jobs/<id>/page.html     -> the generated page (sandboxed by CSP, for preview)
  GET  /api/jobs/<id>/site.zip      -> index.html, robots.txt, sitemap.xml, llms.txt, .nojekyll
Everything else is served from web/.
"""
from __future__ import annotations

import io
import json
import mimetypes
import os
import re
import secrets
import threading
import time
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import citeforge as cf

ROOT = Path(__file__).resolve().parent
WEB = ROOT
JOBS_DIR = ROOT / "jobs"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
MAX_BODY = 8 * 1024
MAX_JOBS_KEPT = 30
ALLOW_ORIGIN = os.environ.get("CITEFORGE_CORS", "")      # e.g. http://127.0.0.1:5500 if the page is served elsewhere

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
RUN_SLOT = threading.Semaphore(1)   # one pipeline at a time: protects the API quota and the shared out dirs
ID_RE = re.compile(r"^[0-9a-f]{16}$")


# ------------------------------------------------------------------ jobs
def _public(job: dict) -> dict:
    keys = ("id", "status", "stage", "message", "percent", "log", "error", "result", "created")
    return {k: job[k] for k in keys if k in job}


def _update(job: dict, stage: str, message: str, percent=None) -> None:
    with JOBS_LOCK:
        job["stage"], job["message"] = stage, message
        if percent is not None:
            job["percent"] = percent
        job["log"].append({"t": round(time.time() - job["created"], 1), "stage": stage, "message": message})
        job["log"] = job["log"][-60:]


def _worker(job: dict, params: dict) -> None:
    _update(job, "queued", "Waiting for the previous run to finish", 0)
    with RUN_SLOT:
        job["status"] = "running"
        try:
            cf.load_env()
            result = cf.pipeline(
                params["topic"], url=params["url"], rounds=params["rounds"], sample=params["sample"],
                max_claims=params["max_claims"], out=JOBS_DIR / job["id"] / "site",
                progress=lambda st, msg, pct: _update(job, st, msg, pct))
            (JOBS_DIR / job["id"] / "result.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8")
            with JOBS_LOCK:
                job["result"], job["status"] = result, "done"
        except Exception as exc:                                    # surface a short message, keep the trace in the server log
            cf.log(f"job {job['id']} failed: {exc!r}")
            with JOBS_LOCK:
                job["status"], job["error"] = "error", str(exc)[:300]


def _prune() -> None:
    with JOBS_LOCK:
        old = sorted(JOBS.values(), key=lambda j: j["created"])[:-MAX_JOBS_KEPT]
        for j in old:
            if j["status"] in ("done", "error"):
                JOBS.pop(j["id"], None)


def validate(body: dict) -> dict:
    topic = " ".join(str(body.get("topic", "")).split())
    if not 3 <= len(topic) <= 160:
        raise ValueError("topic must be 3 to 160 characters")
    url = str(body.get("url", "") or "").strip()
    if url:
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.netloc or len(url) > 300:
            raise ValueError("url must be a full http(s) address")

    def num(key, default, lo, hi):
        try:
            v = int(body.get(key, default))
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number")
        return max(lo, min(hi, v))

    return {"topic": topic, "url": url, "rounds": num("rounds", 2, 1, 3),
            "sample": num("sample", 0, 0, 20), "max_claims": num("max_claims", 8, 0, 12)}


# ------------------------------------------------------------------ http
class Handler(BaseHTTPRequestHandler):
    server_version = "CiteForge/1.0"

    def log_message(self, fmt, *args):  # quieter, no client IPs in logs
        cf.log("http " + fmt % args)

    # -- helpers
    def _headers(self, code: int, ctype: str, length: int, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        if ALLOW_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOW_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, code: int, obj) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(data), {"Cache-Control": "no-store"})
        self.wfile.write(data)

    def _bytes(self, code: int, ctype: str, data: bytes, extra: dict | None = None) -> None:
        self._headers(code, ctype, len(data), extra)
        self.wfile.write(data)

    # -- routes
    def do_OPTIONS(self):
        self._headers(204, "text/plain", 0, {"Access-Control-Allow-Methods": "GET, POST, OPTIONS"})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            llm = cf.LLM()
            return self._json(200, {"ok": True, "mode": "LIVE" if llm.available else "OFFLINE",
                                    "provider": llm.provider if llm.available else None,
                                    "model": (cf.GEMINI_MODEL if llm.provider == "gemini" else cf.MODEL) if llm.available else None,
                                    "reason": llm.reason})
        m = re.match(r"^/api/jobs/([0-9a-f]{16})(?:/(page\.html|site\.zip))?$", path)
        if m:
            return self._job(m.group(1), m.group(2))
        if path.startswith("/api/"):
            return self._json(404, {"error": "not found"})
        return self._static(path)

    def do_POST(self):
        if urlparse(self.path).path != "/api/jobs":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BODY:
                return self._json(413, {"error": "request too large"})
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            params = validate(body)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})
        job_id = secrets.token_hex(8)
        job = {"id": job_id, "status": "queued", "stage": "queued", "message": "Queued", "percent": 0,
               "log": [], "created": time.time()}
        (JOBS_DIR / job_id).mkdir(parents=True, exist_ok=True)
        with JOBS_LOCK:
            JOBS[job_id] = job
        _prune()
        threading.Thread(target=_worker, args=(job, params), daemon=True).start()
        return self._json(202, {"job_id": job_id})

    def _job(self, job_id: str, artifact: str | None):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            snap = _public(job) if job else None
        if not snap:
            return self._json(404, {"error": "unknown job (the server may have restarted)"})
        if artifact is None:
            return self._json(200, snap)
        if snap["status"] != "done":
            return self._json(409, {"error": "job not finished"})
        site = JOBS_DIR / job_id / "site"
        if artifact == "page.html":
            return self._bytes(200, "text/html; charset=utf-8", (site / "index.html").read_bytes(), {
                # the preview is generated content: no scripts, no network, no framing by other sites
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
                "Cache-Control": "no-store"})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(site.iterdir()):
                z.write(f, f"docs/{f.name}")
        return self._bytes(200, "application/zip", buf.getvalue(),
                           {"Content-Disposition": 'attachment; filename="citeforge-site.zip"'})

    def _static(self, path: str):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            return self._json(404, {"error": "not found"})
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._bytes(200, ctype, target.read_bytes(), {"Cache-Control": "no-cache"})


def main() -> None:
    cf.load_env()
    JOBS_DIR.mkdir(exist_ok=True)
    llm = cf.LLM()
    cf.log(f"LLM: {'LIVE via ' + llm.provider if llm.available else 'OFFLINE (' + llm.reason + ')'}")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    cf.log(f"CiteForge running at http://{HOST}:{PORT}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
