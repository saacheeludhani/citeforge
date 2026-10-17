#!/usr/bin/env python3
"""Tiny fake of Gemini's generateContent REST endpoint, for testing CiteForge without a key or network.

    python tests/fake_gemini.py            # listens on 127.0.0.1:8765
    CITEFORGE_GEMINI_BASE=http://127.0.0.1:8765 GEMINI_API_KEY=test python server.py
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("FAKE_PORT", "8765"))
CALLS = []

FACTS = [
    "Lithium iron phosphate batteries typically tolerate more charge cycles than other lithium chemistries.",
    "Most home battery warranties state a minimum retained capacity after a set number of years.",
    "Home batteries last exactly 40 years regardless of use.",                       # -> contradicted
    "Cold temperatures can reduce usable battery capacity.",
    "Battery calendar life depends on age even with light use.",
    "Warranty throughput limits are expressed in megawatt hours.",                   # -> insufficient
    "Depth of discharge affects how many cycles a battery delivers.",
    "Installers usually recommend keeping batteries between 15 and 30 degrees Celsius.",
]


def grounded(*domains):
    return {"groundingChunks": [{"web": {"uri": f"https://vertexaisearch.cloud.google.com/grounding-api-redirect/{i}",
                                         "title": d}} for i, d in enumerate(domains)]}


def reply(prompt: str):
    if "Generate 200 diverse questions" in prompt or "diverse questions" in prompt:
        qs = [{"query": f"home battery question {i}", "intent": "practical"} for i in range(30)]
        return json.dumps(qs), None
    if "Write a factual, well-sourced web page" in prompt:
        page = {"title": "Home battery lifespan: what the evidence says",
                "summary": "A home battery typically lasts 10 to 15 years, depending on chemistry, charge cycles, "
                           "depth of discharge and temperature. Warranties from manufacturers usually state both a "
                           "time limit and a retained-capacity threshold, so compare both before buying a system.",
                "key_facts": FACTS,
                "sections": [{"heading": "How long does a home battery last?", "body": "Lifespan depends on chemistry, cycling and conditions."},
                             {"heading": "What does a warranty cover?", "body": "Warranties cover time, throughput and retained capacity."}],
                "faqs": [{"q": "Does cold weather hurt a battery?", "a": "Cold can reduce usable capacity temporarily."},
                         {"q": "What is cycle life?", "a": "Cycle life is the number of full charge and discharge cycles."}],
                "sources": [{"title": "Example source", "url": "https://example.org/batteries"}]}
        return json.dumps(page), grounded("example.org", "energy.gov")
    if "evidence-review assistant" in prompt:
        claim = prompt.split("CLAIM:")[1].split("Rules:")[0].strip()
        if "exactly 40 years" in claim:
            v = "contradicted"
        elif "megawatt" in claim:
            v = "insufficient_evidence"
        else:
            v = "supported"
        data = {"claim": claim, "verification_status": v, "explanation": f"Retrieved sources {v.replace('_', ' ')} this claim.",
                "evidence": [{"source_title": "Energy.gov battery guide", "source_url": "https://energy.gov/guide",
                              "relevant_finding": "Relevant finding."},
                             {"source_title": "Made-up site", "source_url": "https://totally-invented.example/x",
                              "relevant_finding": "Should be dropped: not in grounded sources."}],
                "limitations": "Fake test data."}
        return json.dumps(data), grounded("energy.gov", "example.org")
    if "You are an editor improving a web page" in prompt:
        m = re.search(r"CURRENT PAGE JSON:\n(.*?)\n\nUNANSWERED", prompt, re.S)
        try:
            page = json.loads(m.group(1))
        except Exception:                      # prompt text was truncated mid-JSON; rebuild a valid page
            page = {"title": "Home battery lifespan", "summary": "Edited summary.", "key_facts": FACTS, "sections": [], "faqs": [], "sources": []}
        page["key_facts"] = [k for k in page["key_facts"] if "exactly 40 years" not in k] + \
            ["Round-trip efficiency of home batteries is commonly between 85 and 95 percent."]
        page["faqs"] = page.get("faqs", []) + [{"q": "How efficient is a home battery?", "a": "Round-trip efficiency is commonly 85 to 95 percent."}]
        page.pop("claims", None); page.pop("url", None); page.pop("updated", None); page.pop("topic", None)
        return json.dumps(page), grounded("energy.gov")
    # citation-test style question: pretend the user's host gets cited for even-numbered questions
    cited = prompt.lower().startswith("what is")      # deterministic: only definition questions cite the user's host
    return "A short answer.", grounded("energy.gov", *(["user.github.io"] if cited else []))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["contents"][0]["parts"][0]["text"]
        CALLS.append(prompt[:60])
        if "x-goog-api-key" not in {k.lower() for k in self.headers.keys()}:
            self.send_response(401); self.end_headers(); return
        text, gm = reply(prompt)
        cand = {"content": {"parts": [{"text": text}]}}
        if gm and body.get("tools"):
            cand["groundingMetadata"] = gm
        out = json.dumps({"candidates": [cand]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
