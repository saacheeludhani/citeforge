#!/usr/bin/env python3
"""
CiteForge - GEO experimentation pipeline (PS-04: Get Cited)

Pipeline:  Topic -> Query Strategist -> Page Builder -> Citation Arena
           -> Performance Scoring -> Editor Agent -> Integrity Audit -> Publish

Two modes
  * OFFLINE (if no API key): no network, no API key needed.
    Generates 200+ queries from templates, builds a scaffold page from a facts
    file, scores passage coverage with BM25 + TF-IDF, audits integrity,
    and writes the site. Good for testing the pipeline.
  * LIVE (GEMINI_API_KEY / ANTHROPIC_API_KEY set): uses Gemini (or Claude) with web search
    for query generation, grounded page writing, real citation testing,
    claim-accuracy judging and automated editing.

Only the Python standard library is required (Gemini mode needs no pip installs).

Usage
  python citeforge.py --topic "Your assigned topic" --url https://user.github.io/repo/
  python citeforge.py --topic "..." --facts facts.json --rounds 2
  python citeforge.py --audit-url https://user.github.io/repo/     # cloaking check on live page
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

MODEL = os.environ.get("CITEFORGE_MODEL", "claude-sonnet-5-5")          # only used with sk-ant- keys
GEMINI_MODEL = os.environ.get("CITEFORGE_GEMINI_MODEL", "gemini-3.5-flash")
# Keys are read from the environment / .env (GEMINI_API_KEY, GOOGLE_API_KEY or ANTHROPIC_API_KEY). Never hard-code them.
API_KEY = ""   # leave empty: set GEMINI_API_KEY in .env or your environment
OUT_DIR = Path(os.environ.get("CITEFORGE_OUT", "docs"))   # 'docs' works with GitHub Pages
STOP = set("a an and are as at be by for from has have how in is it its of on or that the "
           "this to was what when where which who why will with does do can i you your".split())


# --------------------------------------------------------------------------- utils
def log(msg: str) -> None:
    print(f"[citeforge] {msg}", flush=True)


def load_env(path: str = ".env") -> None:
    """Minimal .env loader (stdlib only). Real environment variables take priority."""
    here = Path(globals().get("__file__", ".")).resolve().parent   # __file__ is undefined in notebook cells
    for candidate in (Path(path), here / path):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def extract_json(text: str):
    """Pull the first JSON object/array out of an LLM reply. Returns None on failure."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = text.find(open_c), text.rfind(close_c)
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                continue
    return None


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "page"


# --------------------------------------------------------------------------- LLM layer
class LLM:
    """LLM wrapper. Gemini REST API (default for AQ./AIza keys) or Anthropic (sk-ant- keys).
    Stdlib only - no pip installs needed for Gemini. `available` is False when no key."""

    def __init__(self) -> None:
        self.key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                    or os.environ.get("ANTHROPIC_API_KEY") or API_KEY or "").strip()
        self.provider = "anthropic" if self.key.startswith("sk-ant-") else "gemini"
        self.client = None
        self.reason = ""
        if not self.key:
            self.reason = "no API key set"
        elif self.provider == "anthropic":
            try:
                import anthropic  # type: ignore
                self.client = anthropic.Anthropic(api_key=self.key)
            except Exception as exc:
                self.reason = f"anthropic SDK unavailable ({exc})"
                self.key = ""

    @property
    def available(self) -> bool:
        return bool(self.key)

    # ---- Gemini over plain HTTPS
    def _gemini(self, prompt: str, system: str, web: bool, max_tokens: int) -> tuple[str, list[dict]]:
        import time
        base = os.environ.get("CITEFORGE_GEMINI_BASE", "https://generativelanguage.googleapis.com").rstrip("/")
        url = f"{base}/v1beta/models/{GEMINI_MODEL}:generateContent"
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max(max_tokens, 1024), "temperature": 0.4}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if web:
            body["tools"] = [{"google_search": {}}]
        data = json.dumps(body).encode("utf-8")
        last_err = "unknown error"
        for attempt in range(5):
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "Content-Type": "application/json", "x-goog-api-key": self.key})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    resp = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                last_err = f"HTTP {exc.code}: {detail}"
                if exc.code in (429, 500, 503) and attempt < 4:
                    # free-tier quota (429) needs a longer pause than a transient 503
                    time.sleep((8 if exc.code == 429 else 2) * (attempt + 1))
                    continue
                raise RuntimeError(last_err)
            except Exception as exc:
                last_err = str(exc)
                if attempt < 4:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(last_err)
        else:
            raise RuntimeError(last_err)
        return parse_gemini_response(resp)

    def complete(self, prompt: str, system: str = "", web: bool = False,
                 max_tokens: int = 4000) -> tuple[str, list[dict]]:
        """Returns (text, sources) where sources = [{'url':..., 'title':...}]."""
        if not self.available:
            raise RuntimeError("LLM not available: " + self.reason)
        if self.provider == "gemini":
            return self._gemini(prompt, system, web, max_tokens)
        kwargs = dict(model=MODEL, max_tokens=max_tokens,
                      messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system
        if web:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}]
        resp = self.client.messages.create(**kwargs)
        text_parts: list[str] = []
        sources: list[dict] = []
        for block in resp.content:
            b = block.model_dump() if hasattr(block, "model_dump") else dict(block)
            btype = b.get("type")
            if btype == "text":
                text_parts.append(b.get("text", ""))
                for c in b.get("citations") or []:
                    if c.get("url"):
                        sources.append({"url": c["url"], "title": c.get("title", "")})
            elif btype == "web_search_tool_result":
                content = b.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("url"):
                            sources.append({"url": item["url"], "title": item.get("title", "")})
        return "".join(text_parts), dedupe_sources(sources)


def dedupe_sources(sources: list[dict]) -> list[dict]:
    seen, uniq = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            uniq.append(s)
    return uniq


def parse_gemini_response(resp: dict) -> tuple[str, list[dict]]:
    """Extract text + grounding sources from a Gemini generateContent response."""
    cands = resp.get("candidates") or []
    if not cands:
        block = (resp.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
        raise RuntimeError(f"Gemini returned no answer ({block})")
    cand = cands[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    sources = []
    for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks") or []:
        web = ch.get("web") or {}
        if web.get("uri"):
            # Gemini returns redirect URIs; 'title' is normally the real site domain.
            sources.append({"url": web["uri"], "title": web.get("title", "")})
    return text, dedupe_sources(sources)


# --------------------------------------------------------------------------- data model
@dataclass
class FAQ:
    q: str
    a: str


@dataclass
class Page:
    topic: str
    title: str
    summary: str                               # direct answer, 40-60 words
    key_facts: list[str] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)   # {heading, body}
    faqs: list[FAQ] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)    # {title, url}
    claims: list[dict] = field(default_factory=list)     # verified key facts, see verify_claim()
    url: str = ""
    updated: str = field(default_factory=lambda: date.today().isoformat())

    def passages(self) -> list[str]:
        """Passage-level units that an AI engine would extract."""
        out = [self.summary] + self.key_facts
        out += [f"{s['heading']}. {s['body']}" for s in self.sections]
        out += [f"{f.q} {f.a}" for f in self.faqs]
        return [p for p in out if p.strip()]

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["faqs"] = [f.__dict__ for f in self.faqs]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Page":
        d = dict(d)
        d["faqs"] = [FAQ(**f) for f in d.get("faqs", [])]
        return Page(**d)


# --------------------------------------------------------------------------- 2. Query strategist
INTENTS = {
    "definition": ["what is {t}", "define {t}", "{t} explained simply", "meaning of {t}",
                   "what does {t} mean", "{t} in simple words"],
    "how":        ["how does {t} work", "how to get started with {t}", "how is {t} used",
                   "how do I learn {t}", "steps to understand {t}", "how to implement {t}"],
    "why":        ["why is {t} important", "why does {t} matter", "why use {t}",
                   "why do people care about {t}", "reasons to learn {t}"],
    "compare":    ["{t} vs alternatives", "difference between {t} and similar approaches",
                   "is {t} better than traditional methods", "{t} pros and cons",
                   "alternatives to {t}"],
    "history":    ["history of {t}", "who invented {t}", "when did {t} start",
                   "origin of {t}", "timeline of {t}"],
    "evidence":   ["is {t} proven", "research on {t}", "statistics about {t}",
                   "does {t} really work", "evidence for {t}", "studies on {t}"],
    "practical":  ["examples of {t}", "best practices for {t}", "common mistakes with {t}",
                   "tools for {t}", "{t} checklist", "{t} for beginners",
                   "{t} for businesses", "{t} for students", "{t} cost", "{t} limitations"],
    "future":     ["future of {t}", "{t} trends", "{t} challenges", "is {t} worth it",
                   "{t} risks", "{t} ethics"],
}
MODIFIERS = ["in 2026", "explained", "guide", "overview", "for beginners", "key facts",
             "examples", "step by step", "quick answer", "FAQ"]


def offline_queries(topic: str, n: int = 220) -> list[dict]:
    out, seen = [], set()
    for intent, templates in INTENTS.items():
        for tpl in templates:
            q = tpl.format(t=topic)
            if q not in seen:
                seen.add(q)
                out.append({"query": q, "intent": intent})
    for intent, templates in INTENTS.items():
        for tpl in templates:
            for m in MODIFIERS:
                q = f"{tpl.format(t=topic)} {m}"
                if q not in seen:
                    seen.add(q)
                    out.append({"query": q, "intent": intent})
                if len(out) >= n:
                    return out
    return out


def generate_queries(llm: LLM, topic: str, n: int = 200) -> list[dict]:
    queries = offline_queries(topic, n)
    if llm.available:
        try:
            prompt = (f"Topic: {topic}\nGenerate {n} diverse questions real users might ask an AI "
                      "assistant about this topic. Cover intents: definition, how, why, compare, "
                      "history, evidence, practical, future. Include short and long, casual and "
                      "expert phrasing. Reply ONLY with a JSON array of objects "
                      '{"query": str, "intent": str}.')
            text, _ = llm.complete(prompt, max_tokens=8000)
            data = extract_json(text)
            if isinstance(data, list):
                have = {q["query"].lower() for q in queries}
                for item in data:
                    if isinstance(item, dict) and item.get("query") and item["query"].lower() not in have:
                        queries.append({"query": str(item["query"]), "intent": str(item.get("intent", "other"))})
                        have.add(item["query"].lower())
        except Exception as exc:
            log(f"LLM query generation failed, using templates only: {exc}")
    return queries


# --------------------------------------------------------------------------- 3. Page builder
def build_page_live(llm: LLM, topic: str, queries: list[dict]) -> Page:
    sample = "\n".join(q["query"] for q in queries[:40])
    prompt = f"""Write a factual, well-sourced web page about: {topic}

Use web search to ground every factual claim. Do NOT invent statistics, dates, quotes or sources.
If you are unsure of a fact, leave it out.

GEO rules: open with a 40-60 word direct answer; name entities explicitly (no vague pronouns);
every section heading is a question or clear noun phrase; each paragraph stands alone as an
extractable passage; FAQ answers are 1-3 sentences. Same content is for humans and AI; no tricks.

Questions the page should be able to answer (sample):
{sample}

Reply ONLY with JSON:
{{"title": str, "summary": str, "key_facts": [str, ...8],
  "sections": [{{"heading": str, "body": str}}, ...6-8],
  "faqs": [{{"q": str, "a": str}}, ...12-20],
  "sources": [{{"title": str, "url": str}}, ...]}}"""
    text, found = llm.complete(prompt, web=True, max_tokens=8000)
    data = extract_json(text)
    if not isinstance(data, dict) or "summary" not in data:
        raise ValueError("LLM did not return valid page JSON")
    srcs = data.get("sources") or []
    known = {s.get("url") for s in srcs if isinstance(s, dict)}
    for s in found:  # add real URLs the search tool actually returned
        if "vertexaisearch.cloud.google.com" in s["url"]:
            continue  # Gemini redirect links; keep only the model's own cited sources
        if s["url"] not in known:
            srcs.append({"title": s.get("title") or s["url"], "url": s["url"]})
    return Page(topic=topic, title=data.get("title", topic), summary=data["summary"],
                key_facts=list(data.get("key_facts", [])), sections=list(data.get("sections", [])),
                faqs=[FAQ(f["q"], f["a"]) for f in data.get("faqs", []) if "q" in f and "a" in f],
                sources=[s for s in srcs if isinstance(s, dict) and s.get("url")])


def build_page_offline(topic: str, facts_path: str | None) -> Page:
    """Scaffold from a facts.json you write. Without facts, makes a clearly-marked skeleton."""
    if facts_path:
        data = json.loads(Path(facts_path).read_text(encoding="utf-8"))
        return Page(topic=topic, title=data.get("title", topic), summary=data["summary"],
                    key_facts=data.get("key_facts", []), sections=data.get("sections", []),
                    faqs=[FAQ(f["q"], f["a"]) for f in data.get("faqs", [])],
                    sources=data.get("sources", []))
    log("No --facts file and no API key: building a SKELETON page. Fill in real content before publishing!")
    return Page(
        topic=topic, title=f"{topic}: Complete Guide",
        summary=(f"{topic} is the subject of this guide. [REPLACE with a 40-60 word, fact-checked "
                 f"direct answer that names the key entities involved in {topic}.]"),
        key_facts=[f"[REPLACE: verified fact {i} about {topic}]" for i in range(1, 6)],
        sections=[{"heading": f"What is {topic}?", "body": f"[REPLACE: define {topic} in 2-3 sentences.]"},
                  {"heading": f"How does {topic} work?", "body": "[REPLACE: explain mechanism.]"},
                  {"heading": f"Why does {topic} matter?", "body": "[REPLACE: explain importance.]"}],
        faqs=[FAQ(f"What is {topic}?", "[REPLACE]"), FAQ(f"How does {topic} work?", "[REPLACE]")],
        sources=[])


# --------------------------------------------------------------------------- HTML rendering
CSS = """
:root{--fg:#1a1a1a;--bg:#fff;--muted:#555;--accent:#9b2c1f}
@media (prefers-color-scheme:dark){:root{--fg:#eee;--bg:#161616;--muted:#aaa;--accent:#ff8a78}}
body{font:18px/1.6 system-ui,sans-serif;color:var(--fg);background:var(--bg);max-width:50rem;margin:0 auto;padding:1rem}
h1,h2{line-height:1.25}h2{margin-top:2rem;color:var(--accent)}
.summary{font-size:1.15em;border-left:4px solid var(--accent);padding-left:1rem}
.meta{color:var(--muted);font-size:.9rem}a{color:var(--accent)}
"""


VERDICT_LABEL = {"supported": "supported by retrieved sources",
                 "contradicted": "contradicted by retrieved sources",
                 "insufficient_evidence": "evidence insufficient or mixed",
                 "unverified": "not yet checked"}


def render_fact(text: str, claim: dict | None) -> str:
    e = html.escape
    if not claim:
        return f"<li>{e(text)}</li>"
    v = claim.get("verdict", "unverified")
    links = []
    for ev in claim.get("evidence", [])[:3]:
        label = e(ev.get("source_title") or "source")
        links.append(f'<a href="{e(ev["source_url"])}" rel="noopener">{label}</a>' if ev.get("source_url") else label)
    src = (" Sources: " + "; ".join(links) + ".") if links else ""
    return f'<li>{e(text)} <span class="meta">[Check: {e(VERDICT_LABEL.get(v, v))}.{src}]</span></li>'


def render_html(p: Page) -> str:
    e = html.escape
    faq_ld = [{"@type": "Question", "name": f.q,
               "acceptedAnswer": {"@type": "Answer", "text": f.a}} for f in p.faqs]
    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": p.title,
         "description": p.summary, "dateModified": p.updated, "datePublished": p.updated,
         "about": p.topic, "mainEntityOfPage": p.url or None,
         "citation": [s["url"] for s in p.sources if s.get("url")]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq_ld},
    ]
    ld_json = json.dumps(ld, ensure_ascii=False, indent=2).replace("</", "<\\/")
    canon = f'<link rel="canonical" href="{e(p.url)}">' if p.url else ""
    parts = [
        "<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{e(p.title)}</title>", f'<meta name="description" content="{e(p.summary[:300])}">',
        canon, f"<style>{CSS}</style>",
        f'<script type="application/ld+json">{ld_json}</script></head><body><main>',
        f"<h1>{e(p.title)}</h1>",
        f'<p class="meta">Last updated {e(p.updated)}</p>',
        f'<p class="summary"><strong>Short answer:</strong> {e(p.summary)}</p>',
    ]
    if p.key_facts:
        by_text = {c["claim"]: c for c in p.claims}
        parts.append("<h2>Key facts</h2><ul>" + "".join(render_fact(k, by_text.get(k)) for k in p.key_facts) + "</ul>")
        if p.claims:
            parts.append('<p class="meta">Key facts marked with a check were reviewed against live web search results by an '
                         'automated reviewer. This is a preliminary check, not a guarantee: read the linked sources.</p>')
    for s in p.sections:
        parts.append(f"<section><h2>{e(s['heading'])}</h2><p>{e(s['body'])}</p></section>")
    if p.faqs:
        parts.append("<h2>Frequently asked questions</h2>")
        for f in p.faqs:
            parts.append(f"<section><h3>{e(f.q)}</h3><p>{e(f.a)}</p></section>")
    if p.sources:
        parts.append("<h2>Sources</h2><ol>" + "".join(
            f'<li><a href="{e(s["url"])}" rel="noopener">{e(s.get("title") or s["url"])}</a></li>'
            for s in p.sources) + "</ol>")
    parts.append("</main></body></html>")
    return "\n".join(x for x in parts if x)


# --------------------------------------------------------------------------- 4/5. Scoring (BM25 + TF-IDF)
class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = [tokenize(d) for d in docs]
        self.k1, self.b = k1, b
        self.avg = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query: str, i: int) -> float:
        d = self.docs[i]
        if not d or not self.avg:
            return 0.0
        tf = Counter(d)
        s = 0.0
        for t in tokenize(query):
            if t in tf:
                f = tf[t]
                s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
        return s

    def best(self, query: str) -> tuple[float, int]:
        if not self.docs:
            return 0.0, -1
        scores = [self.score(query, i) for i in range(len(self.docs))]
        i = max(range(len(scores)), key=scores.__getitem__)
        return scores[i], i


def cosine_tfidf(a: str, b: str) -> float:
    ta, tb = Counter(tokenize(a)), Counter(tokenize(b))
    dot = sum(ta[t] * tb[t] for t in ta if t in tb)
    na = math.sqrt(sum(v * v for v in ta.values()))
    nb = math.sqrt(sum(v * v for v in tb.values()))
    return dot / (na * nb) if na and nb else 0.0


def coverage_analysis(page: Page, queries: list[dict], min_cos: float = 0.18) -> dict:
    """Which queries have a passage that plausibly answers them? Returns gaps."""
    passages = page.passages()
    bm = BM25(passages)
    covered, gaps = 0, []
    for q in queries:
        _, idx = bm.best(q["query"])
        sim = cosine_tfidf(q["query"], passages[idx]) if idx >= 0 else 0.0
        if sim >= min_cos:
            covered += 1
        else:
            gaps.append({**q, "best_similarity": round(sim, 3)})
    n = max(len(queries), 1)
    return {"coverage": round(covered / n, 3), "covered": covered, "total": len(queries), "gaps": gaps}


# --------------------------------------------------------------------------- 4. Citation arena (live)
def host_of(u: str) -> str:
    return (urlparse(u).netloc or "").lower().removeprefix("www.")


def citation_test(llm: LLM, page: Page, queries: list[dict], sample: int = 25) -> dict:
    """Ask a live-web AI each query; record whether our URL is among the cited sources."""
    if not llm.available:
        return {"mode": "skipped", "reason": llm.reason, "citation_rate": None, "results": []}
    if not page.url:
        return {"mode": "skipped", "reason": "pass --url (your published page) to test citations",
                "citation_rate": None, "results": []}
    my_host, my_path = host_of(page.url), urlparse(page.url).path.rstrip("/")
    step = max(len(queries) // sample, 1)
    chosen = queries[::step][:sample]
    results, hits = [], 0
    for q in chosen:
        try:
            ans, srcs = llm.complete(q["query"], web=True, max_tokens=1200)
        except Exception as exc:
            results.append({"query": q["query"], "error": str(exc)})
            continue
        def is_mine(s: dict) -> bool:
            if host_of(s["url"]) == my_host:
                return urlparse(s["url"]).path.rstrip("/").startswith(my_path)
            return host_of("//" + s.get("title", "").strip()) == my_host  # Gemini: title = domain
        cited = any(is_mine(s) for s in srcs)
        hits += cited
        results.append({"query": q["query"], "cited": cited,
                        "position": next((i + 1 for i, s in enumerate(srcs) if is_mine(s)), None),
                        "answer_excerpt": ans[:300]})
    tested = [r for r in results if "error" not in r]
    return {"mode": "live", "tested": len(tested), "hits": hits,
            "citation_rate": round(hits / len(tested), 3) if tested else None, "results": results}


def claim_accuracy(llm: LLM, page: Page) -> dict:
    """LLM-as-judge: are the page's claims supported by its own listed sources? (live only)"""
    if not llm.available:
        return {"mode": "skipped", "score": None}
    try:
        prompt = ("Fact-check this page using web search. List claims that are wrong, unsupported or "
                  "exaggerated. Reply ONLY JSON {\"accuracy\": 0-1, \"problems\": [{\"claim\": str, \"issue\": str}]}.\n\n"
                  + "\n".join(page.passages())[:12000])
        text, _ = llm.complete(prompt, web=True, max_tokens=2000)
        data = extract_json(text)
        if isinstance(data, dict):
            return {"mode": "live", "score": data.get("accuracy"), "problems": data.get("problems", [])}
    except Exception as exc:
        return {"mode": "error", "score": None, "error": str(exc)}
    return {"mode": "error", "score": None}


# --------------------------------------------------------------------------- 6. Editor agent
def edit_page(llm: LLM, page: Page, gaps: list[dict], problems: list[dict]) -> Page:
    """Fill gaps with grounded FAQ answers and fix flagged claims. Live mode only."""
    if not llm.available:
        return page
    if not gaps and not problems:
        return page
    gap_qs = [g["query"] for g in gaps[:15]]
    prompt = ("You are an editor improving a web page for accuracy and AI-extractability. "
              "Use web search to ground facts. Never invent facts or sources. Keep tone neutral.\n"
              f"CURRENT PAGE JSON:\n{json.dumps(page.to_dict(), ensure_ascii=False)[:14000]}\n\n"
              f"UNANSWERED QUESTIONS (add concise FAQ answers for the best 8-10 distinct ones):\n{gap_qs}\n\n"
              f"CLAIMS TO FIX OR REMOVE:\n{json.dumps(problems)[:3000]}\n\n"
              "Return the FULL improved page as JSON with the same keys (title, summary, key_facts, "
              "sections, faqs, sources).")
    try:
        text, found = llm.complete(prompt, web=True, max_tokens=8000)
        data = extract_json(text)
        if not isinstance(data, dict) or "summary" not in data:
            return page
        new = Page(topic=page.topic, title=data.get("title", page.title), summary=data["summary"],
                   key_facts=list(data.get("key_facts", page.key_facts)),
                   sections=list(data.get("sections", page.sections)),
                   faqs=[FAQ(f["q"], f["a"]) for f in data.get("faqs", []) if "q" in f and "a" in f] or page.faqs,
                   sources=[s for s in data.get("sources", page.sources) if isinstance(s, dict) and s.get("url")],
                   claims=page.claims, url=page.url)
        return new
    except Exception as exc:
        log(f"Editor failed, keeping previous version: {exc}")
        return page


# --------------------------------------------------------------------------- 7. Integrity audit
class _Visible(HTMLParser):
    """Collects visible text and flags hidden-content tricks."""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.issues: list[str] = []
        self._skip = 0
        self.jsonld: list[str] = []
        self._in_ld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = (a.get("style") or "").replace(" ", "").lower()
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld, self._buf = True, []
        elif tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            if tag == "noscript":
                self.issues.append("<noscript> content (can differ from what humans see)")
        if "hidden" in a:
            self.issues.append(f"<{tag}> has the hidden attribute")
        if a.get("aria-hidden") == "true" and tag not in ("svg", "span", "i"):
            self.issues.append(f"<{tag}> is aria-hidden")
        for bad in ("display:none", "visibility:hidden", "font-size:0", "opacity:0",
                    "text-indent:-", "left:-9999", "color:#fff", "color:white"):
            if bad in style:
                self.issues.append(f"<{tag}> inline style '{bad}'")

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.jsonld.append("".join(self._buf))
        elif tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)
        elif not self._skip and data.strip():
            self.text.append(data.strip())


def integrity_audit(html_text: str, page: Page) -> dict:
    v = _Visible()
    v.feed(html_text)
    visible = re.sub(r"\s+", " ", " ".join(v.text))
    issues = list(v.issues)
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", html_text, re.S | re.I):
        css = m.group(1).replace(" ", "").lower()
        for bad in ("display:none", "visibility:hidden", "font-size:0"):
            if bad in css:
                issues.append(f"stylesheet contains '{bad}'")
    # JSON-LD must parse and match visible text
    ld_faq_count = 0
    for raw in v.jsonld:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(f"invalid JSON-LD: {exc}")
            continue
        for node in data if isinstance(data, list) else [data]:
            if node.get("@type") == "FAQPage":
                for q in node.get("mainEntity", []):
                    ld_faq_count += 1
                    name = q.get("name", "")
                    ans = q.get("acceptedAnswer", {}).get("text", "")
                    if name not in visible or ans not in visible:
                        issues.append(f"JSON-LD FAQ not visible on page: '{name[:60]}'")
            if node.get("@type") == "Article" and node.get("description") and node["description"] not in visible:
                issues.append("JSON-LD description differs from visible summary")
    if ld_faq_count != len(page.faqs):
        issues.append("JSON-LD FAQ count differs from visible FAQ count")
    placeholders = len(re.findall(r"\[REPLACE", visible))
    if placeholders:
        issues.append(f"{placeholders} unfilled [REPLACE] placeholders (do NOT publish yet)")
    if not page.sources:
        issues.append("no sources listed (hurts credibility and accuracy checks)")
    return {"passed": not issues, "issues": issues, "visible_words": len(visible.split())}


def cloaking_check(url: str) -> dict:
    """Fetch the live URL as a browser and as several AI crawlers; hashes must match."""
    agents = {"browser": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36",
              "GPTBot": "Mozilla/5.0 (compatible; GPTBot/1.1; +https://openai.com/gptbot)",
              "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
              "PerplexityBot": "Mozilla/5.0 (compatible; PerplexityBot/1.0)",
              "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    hashes, errors = {}, {}
    for name, ua in agents.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=20) as r:
                hashes[name] = hashlib.sha256(r.read()).hexdigest()[:16]
        except Exception as exc:
            errors[name] = str(exc)
    return {"identical": len(set(hashes.values())) == 1 and not errors and bool(hashes),
            "hashes": hashes, "errors": errors}


# --------------------------------------------------------------------------- 7. Publish
def publish(page: Page, out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_html(page), encoding="utf-8")
    base = page.url.rstrip("/") if page.url else ""
    (out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n" + (f"Sitemap: {base}/sitemap.xml\n" if base else ""), encoding="utf-8")
    if base:
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{html.escape(base)}/</loc><lastmod>{page.updated}</lastmod></url></urlset>\n", encoding="utf-8")
    llms = [f"# {page.title}", "", f"> {page.summary}", "", "## Key facts"] + [f"- {k}" for k in page.key_facts]
    (out / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return sorted(str(p) for p in out.iterdir())


# --------------------------------------------------------------------------- 5. Claim verification (from the LLM notebook)
VERDICTS = {"supported", "contradicted", "insufficient_evidence"}


def is_redirect(u: str) -> bool:
    return "vertexaisearch.cloud.google.com" in u or "grounding-api-redirect" in u


def source_host(s: dict) -> str:
    """Real host of a search source. Gemini grounding returns redirect URLs whose *title* is the domain."""
    if is_redirect(s.get("url", "")):
        return (s.get("title") or "").strip().lower().removeprefix("www.")
    return host_of(s.get("url", ""))


def verify_claim(llm: LLM, claim: str) -> dict:
    """Research one claim with live web search and rate the retrieved evidence.

    Same contract as the notebook's research_and_verify(): verdict is one of
    supported / contradicted / insufficient_evidence, and only sources that the
    search tool actually returned may be linked (model-invented URLs are dropped).
    """
    prompt = f"""You are CiteForge's evidence-review assistant.

Use Google Search to find credible evidence relevant to the claim.

CLAIM:
{claim}

Rules:
- Prefer primary sources, official organizations, peer-reviewed research, and authoritative institutions.
- Do not invent sources, quotations, statistics, or URLs.
- A source being relevant does not automatically mean it supports the claim.
- If the evidence is mixed, incomplete, or indirect, use "insufficient_evidence".
- Use "supported" only when the retrieved evidence supports the main claim.
- Use "contradicted" only when reliable retrieved evidence conflicts with the main claim.
- You are evaluating the retrieved evidence, not proving universal truth.

Return ONLY valid JSON with these keys:
{{"claim": "the original claim",
  "verification_status": "supported, contradicted, or insufficient_evidence",
  "explanation": "brief explanation of what the evidence says",
  "evidence": [{{"source_title": "source title", "source_url": "source URL", "relevant_finding": "brief summary"}}],
  "limitations": "what remains uncertain"}}"""
    out = {"claim": claim, "verdict": "insufficient_evidence", "explanation": "", "evidence": [],
           "sources": [], "limitations": "", "error": False}
    try:
        text, found = llm.complete(prompt, web=True, max_tokens=3000)
        data = extract_json(text)
        if not isinstance(data, dict):
            raise ValueError("reviewer did not return JSON")
    except Exception as exc:
        out.update(explanation="The research or parsing step failed.", limitations=str(exc)[:300], error=True)
        return out
    verdict = data.get("verification_status")
    out["verdict"] = verdict if verdict in VERDICTS else "insufficient_evidence"
    out["explanation"] = str(data.get("explanation") or "")[:800]
    out["limitations"] = str(data.get("limitations") or "")[:500]
    grounded_hosts = {source_host(x) for x in found if source_host(x)}
    out["sources"] = [{"title": x.get("title", ""), "url": x["url"]} for x in found][:8]
    for ev in data.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        u = str(ev.get("source_url") or "")
        keep = u.startswith(("http://", "https://")) and not is_redirect(u) and host_of(u) in grounded_hosts
        out["evidence"].append({"source_title": str(ev.get("source_title") or host_of(u) or "source")[:160],
                                "source_url": u if keep else "",
                                "relevant_finding": str(ev.get("relevant_finding") or "")[:400]})
    return out


def verify_claims(llm: LLM, facts: list[str], known: dict[str, dict] | None = None,
                  progress=None, pause: float = 1.0) -> list[dict]:
    """Verify each fact once; facts already in `known` (same text) keep their earlier verdict."""
    import time
    known = known or {}
    results = []
    todo = [f for f in facts if f not in known]
    done = 0
    for f in facts:
        if f in known:
            results.append(known[f])
            continue
        if progress:
            progress("verify", f"Checking claim {done + 1} of {len(todo)}", None)
        results.append(verify_claim(llm, f))
        done += 1
        if done < len(todo):
            time.sleep(pause)
    return results


def tally(claims: list[dict]) -> dict:
    t = {"supported": 0, "contradicted": 0, "insufficient_evidence": 0}
    for c in claims:
        t[c.get("verdict", "insufficient_evidence")] = t.get(c.get("verdict", "insufficient_evidence"), 0) + 1
    t["total"] = len(claims)
    return t


# --------------------------------------------------------------------------- orchestration
def _noop(stage: str, msg: str, pct) -> None:
    return None


def pipeline(topic: str, *, url: str = "", facts_path: str | None = None, rounds: int = 2,
             num_queries: int = 200, sample: int = 0, max_claims: int = 8, out: str | Path | None = None,
             progress=_noop, llm: LLM | None = None, check_live: bool = False) -> dict:
    """Topic -> queries -> page -> claim checks -> coverage/edit loop -> audit -> (citation test) -> publish.

    `progress(stage, message, percent_or_None)` is called as work advances.
    Returns a JSON-serialisable result dict (what the web UI renders).
    """
    llm = llm or LLM()
    live = llm.available
    mode = "LIVE" if live else "OFFLINE"
    log(f"Mode: {mode}" + ("" if live else f" ({llm.reason})"))
    notes: list[str] = []
    if not live:
        notes.append(f"Offline mode: {llm.reason}. The page is a placeholder skeleton, not publishable.")

    progress("queries", "Generating test questions", 5)
    queries = generate_queries(llm, topic, num_queries)
    intents = sorted({q["intent"] for q in queries})
    log(f"Query strategist: {len(queries)} queries across {len(intents)} intents")

    progress("page", "Researching and writing the page", 15)
    if live:
        try:
            page = build_page_live(llm, topic, queries)
        except Exception as exc:
            log(f"Live build failed ({exc}); falling back to offline scaffold")
            notes.append(f"Live page build failed ({str(exc)[:160]}); a placeholder skeleton was used instead.")
            page = build_page_offline(topic, facts_path)
            live = False
    else:
        page = build_page_offline(topic, facts_path)
    page.url = url or ""

    def check(facts: list[str], known: dict | None = None) -> list[dict]:
        return verify_claims(llm, facts[:max_claims], known, progress) if (live and max_claims > 0) else []

    progress("verify", "Checking key facts against live search", 35)
    page.claims = check(page.key_facts)

    history = []
    cov = coverage_analysis(page, queries)
    for rnd in range(1, rounds + 1):
        cov = coverage_analysis(page, queries)
        history.append({"round": rnd, "coverage": cov["coverage"], "gaps": len(cov["gaps"]),
                        "supported": tally(page.claims)["supported"], "claims": len(page.claims)})
        log(f"Round {rnd}/{rounds}: coverage={cov['coverage']} gaps={len(cov['gaps'])}")
        if rnd < rounds and live:
            progress("edit", f"Editor agent, round {rnd}", 55 + int(25 * rnd / max(rounds, 1)))
            problems = [{"claim": c["claim"], "issue": c["explanation"]}
                        for c in page.claims if c["verdict"] == "contradicted"]
            if cov["gaps"] or problems:
                known = {c["claim"]: c for c in page.claims}
                page = edit_page(llm, page, cov["gaps"], problems)
                page.claims = check(page.key_facts, known)   # only changed/new facts cost an API call
        elif rnd < rounds:
            notes.append("The editor needs LIVE mode, so no improvement rounds were run.")
            break

    # A published page should never carry a fact its own check contradicted.
    removed = [c for c in page.claims if c["verdict"] == "contradicted"]
    if removed:
        drop = {c["claim"] for c in removed}
        page.key_facts = [k for k in page.key_facts if k not in drop]
        page.claims = [c for c in page.claims if c["claim"] not in drop]
        cov = coverage_analysis(page, queries)
        history.append({"round": "final", "coverage": cov["coverage"], "gaps": len(cov["gaps"]),
                        "supported": tally(page.claims)["supported"], "claims": len(page.claims)})
        notes.append(f"{len(removed)} key fact(s) contradicted by retrieved sources were removed from the page.")

    progress("audit", "Running the integrity audit", 88)
    audit = integrity_audit(render_html(page), page)
    log("Audit PASSED" if audit["passed"] else "Audit issues: " + "; ".join(audit["issues"]))

    citation = {"mode": "skipped", "reason": "no published URL given", "citation_rate": None, "results": []}
    if url and sample > 0 and live:
        progress("arena", "Testing citations on live search", 92)
        citation = citation_test(llm, page, queries, sample)
    elif url and not live:
        citation["reason"] = llm.reason

    files: list[str] = []
    if out:
        progress("publish", "Writing site files", 97)
        files = [Path(f).name for f in publish(page, Path(out))]
        if url and check_live:
            audit["cloaking"] = cloaking_check(url)

    t = tally(page.claims)
    result = {
        "topic": topic, "mode": mode, "notes": notes, "url": page.url, "model": GEMINI_MODEL if llm.provider == "gemini" else MODEL,
        "page": page.to_dict(),
        "claims": page.claims,
        "metrics": {
            "queries": len(queries), "intents": len(intents),
            "coverage": cov["coverage"], "covered": cov["covered"], "gaps": len(cov["gaps"]),
            "claims_total": t["total"], "supported": t["supported"],
            "insufficient": t["insufficient_evidence"], "removed": len(removed),
            "citation_rate": citation.get("citation_rate"), "citations_tested": citation.get("tested", 0),
            "citation_hits": citation.get("hits", 0),
        },
        "history": history, "audit": audit, "citation": citation,
        "gap_sample": cov["gaps"][:15], "files": files,
    }
    progress("done", "Done", 100)
    return result


# --------------------------------------------------------------------------- CLI
def run(args: argparse.Namespace) -> int:
    load_env()
    res = pipeline(args.topic, url=args.url, facts_path=args.facts, rounds=args.rounds,
                   num_queries=args.num_queries, sample=args.sample, max_claims=args.max_claims,
                   out=args.out, check_live=args.check_live,
                   progress=lambda st, msg, pct: log(f"[{st}] {msg}"))
    Path("citeforge_report.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out).parent.joinpath("citeforge_state.json").write_text(
        json.dumps(res["page"], ensure_ascii=False, indent=2), encoding="utf-8")
    log("Report: citeforge_report.json  |  site: ./" + str(args.out))
    for n in res["notes"]:
        log("NOTE: " + n)
    return 0 if res["audit"]["passed"] or res["mode"] == "OFFLINE" else 2


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description="CiteForge GEO pipeline")
    ap.add_argument("--topic", help="assigned topic")
    ap.add_argument("--url", default="", help="public URL where the page will be hosted")
    ap.add_argument("--facts", help="facts.json (offline mode content)")
    ap.add_argument("--out", default=str(OUT_DIR), help="output folder (default: docs)")
    ap.add_argument("--rounds", type=int, default=2, help="measure/improve rounds")
    ap.add_argument("--num-queries", type=int, default=200)
    ap.add_argument("--sample", type=int, default=0, help="queries sent to live AI for the citation test (needs --url)")
    ap.add_argument("--max-claims", type=int, default=8, help="key facts to verify with live search")
    ap.add_argument("--check-live", action="store_true", help="after publishing, run cloaking check on --url")
    ap.add_argument("--audit-url", help="only run the cloaking check against this live URL")
    args, _unknown = ap.parse_known_args()      # tolerate Jupyter/Colab's extra '-f kernel.json'
    if args.audit_url:
        print(json.dumps(cloaking_check(args.audit_url), indent=2))
        return 0
    if not args.topic:
        ap.error("--topic is required")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
