# CiteForge — Evidence-Based Generative Engine Optimization

**Making AI Search Visibility Measurable, Verifiable, and Improveable.**

CiteForge is a Generative Engine Optimization (GEO) platform designed to help website owners evaluate how their content performs across AI-powered search and answer systems. It aims to make AI search visibility more measurable through evidence-based evaluation, citation analysis, content integrity checks, and targeted content improvements.

> **Project status:** Under development 🚧  
> CiteForge is a hackathon project. Features and evaluation results should be interpreted according to their current implementation and testing status.

---

## 📌 Project Overview

Traditional Search Engine Optimization (SEO) focuses primarily on improving a website's visibility in search engine results. Generative Engine Optimization (GEO) addresses a related challenge: whether AI-powered systems discover, cite, and accurately represent information from a website when generating answers.

CiteForge aims to help website owners understand this emerging form of visibility by evaluating citation behavior, query coverage, claim accuracy, and website integrity.

Rather than relying solely on rankings or assumptions, the platform is designed to produce measurable observations, identify content weaknesses, and recommend improvements that can be evaluated through subsequent testing.

## 🎯 Problem Statement

As users increasingly rely on AI-powered search and answer systems, website owners face several challenges:

- **Citation invisibility:** Relevant content may not be referenced in AI-generated answers.
- **Information loss:** Important claims may be omitted or inaccurately represented.
- **Inconsistent citations:** Citation results may vary across queries, providers, or repeated evaluations.
- **Limited evaluation tools:** Website owners may lack a unified way to measure AI search visibility and content accuracy.
- **Unclear optimization strategies:** Content improvements may be made without a reliable process for evaluating their impact.
- **Website integrity concerns:** Accessibility, structured data, and crawler-facing responses can affect how content is discovered and interpreted.

CiteForge addresses these challenges through a structured evaluation and improvement workflow.

## 💡 Our Solution

CiteForge proposes an integrated GEO workflow that analyzes website content, evaluates its performance against relevant queries, examines citation and claim accuracy, and identifies opportunities for improvement.

The platform brings together four core activities:

1. **Evaluate** — Measure visibility and representation across supported test queries.
2. **Verify** — Compare answer claims and citations against available source evidence.
3. **Improve** — Generate targeted recommendations for clearer, more accessible content.
4. **Retest** — Compare evaluation results before and after content changes.

The goal is to make GEO optimization more systematic, transparent, and evidence-driven.

## ✨ Key Features

The following features describe CiteForge's intended capabilities. Their implementation status should be documented and updated as development progresses.

### 1. Answer Fidelity Checker

Evaluates whether claims in AI-generated answers accurately reflect the information and evidence available on the source website.

### 2. Citation Stability Analyzer

Compares citation outcomes across repeated evaluations to identify changes in whether and how consistently a source is referenced.

### 3. GEO Benchmarking System

Evaluates content using defined metrics, including citation rate, query coverage, claim accuracy, and citation stability.

### 4. Self-Improving GEO Assistant

Identifies weak or unclear content and proposes targeted improvements. Where supported, subsequent evaluations can help compare results before and after those changes.

### 5. Website Integrity Auditor

Inspects website accessibility, structured data, `robots.txt`, sitemap availability, and responses to configured user-agent strings. These checks help identify potential discoverability and content-delivery issues.

### 6. Evidence-Based Reporting

Consolidates evaluation results into a scorecard that helps users understand observed strengths, weaknesses, and potential next steps.

## 🔄 End-to-End Workflow

CiteForge is designed around the following pipeline:

1. **Topic Input:** The user supplies a topic, target URL, or relevant content.
2. **Query Strategist:** Relevant evaluation queries are prepared.
3. **Page Builder:** Target content is analyzed, or content and supporting page elements are prepared where required.
4. **Citation Arena:** Supported AI search systems are evaluated for relevant answers and source citations.
5. **Performance Scoring:** Results are assessed using defined visibility, accuracy, and consistency metrics.
6. **Editor Agent:** Targeted content improvements are proposed based on the observed weaknesses.
7. **Integrity Audit:** Website accessibility, structured data, and configured crawler responses are checked.
8. **Retesting and Reporting:** Results are summarized and compared to assess observed changes.

*The availability of individual stages depends on the current implementation and the integrations configured for a particular run.*

## 🛠️ Technology Stack

| Component | Technology / Approach |
|---|---|
| Programming language | Python |
| AI integration | Large language model (LLM) API |
| Search integration | Live web search API |
| Information retrieval | BM25 and embeddings |
| Content generation | HTML and CSS |
| Structured data | JSON-LD |
| Version control | Git and GitHub |
| Deployment | Web hosting compatible with the implemented backend and frontend |

The final stack depends on the implementation and integration requirements. Technologies listed here represent the intended approach and should be verified against the actual codebase.

## 🏗️ Project Structure

The following is a conceptual structure for organizing CiteForge as it develops:

```text
CiteForge/
├── README.md
├── .gitignore
├── requirements.txt
├── docs/
│   ├── project-overview.md
│   ├── project-workflow.md
│   ├── technical-architecture.md
│   ├── implementation-status.md
│   ├── testing-plan.md
│   ├── integrity-auditor.md
│   └── research/
│       └── research.md
├── frontend/
├── backend/
├── src/
│   ├── query_strategist/
│   ├── page_builder/
│   ├── citation_arena/
│   ├── performance_scoring/
│   ├── editor_agent/
│   └── integrity_auditor/
└── tests/
```

This structure is illustrative, not a representation of the current repository layout. Update it as the codebase evolves.

## 📊 Evaluation Metrics

CiteForge aims to use clearly defined metrics to evaluate GEO performance.

| Metric | Purpose |
|---|---|
| **Citation Rate** | Measures how often the target website is cited across eligible test queries. |
| **Query Coverage** | Measures the proportion of test queries for which relevant information from the target website is represented. |
| **Claim Accuracy** | Assesses how well evaluated answer claims are supported by available source evidence. |
| **Citation Stability** | Measures the consistency of citation outcomes across repeated evaluations. |
| **Integrity Checks** | Records the results of accessibility, structured-data, sitemap, robots.txt, and configured user-agent checks. |

Each metric requires a documented calculation method, a defined evaluation scope, and a repeatable testing procedure. Results should include relevant test conditions wherever possible.

## 🧪 Testing and Validation

The planned validation process includes:

- Testing individual modules independently.
- Validating URL handling and citation extraction.
- Comparing answer claims against source evidence.
- Repeating evaluations to measure citation variation.
- Testing integrity checks against controlled sample websites.
- Comparing evaluation results before and after content changes.
- Recording errors, limitations, and test conditions to support reproducibility.

Testing should distinguish between successful execution, observed results, and conclusions supported by the available evidence.

## 🚀 Future Scope

Potential extensions include:

- **Competitor citation-gap analysis:** Identify queries where competing sources are cited more frequently.
- **Historical performance dashboards:** Track GEO evaluation results over time.
- **Source freshness monitoring:** Identify potentially outdated or inaccessible content.
- **Explainable recommendations:** Connect each proposed change to an observed issue or evaluation result.
- **Expanded provider support:** Evaluate additional AI search and answer systems.
- **Automated regression testing:** Detect changes in citation behavior after website updates.

These extensions are potential future improvements rather than guaranteed capabilities.

## 👥 Team and Contributions

CiteForge is being developed collaboratively as a hackathon project, with contributions spanning research, documentation, implementation, testing, and presentation.

Contributions should be scoped clearly, tested where applicable, and reviewed before integration into the main branch.

## ⚠️ Limitations and Responsible Interpretation

AI-generated answers and citation behavior can vary depending on the query, provider, model, location, and evaluation time. Results from one provider or test run may not generalize to other systems or conditions.

Additional considerations include:

- Citation rate alone does not establish content quality or factual correctness.
- Claim-accuracy evaluations depend on the quality and completeness of the available evidence.
- Repeated evaluations measure observed variation but do not guarantee future citation behavior.
- User-agent comparisons can identify response differences, but do not independently establish their cause or prove how every crawler is treated.
- A successful integrity check does not guarantee that an AI system will discover or cite a website.
- Content recommendations and generated pages require review before publication.

CiteForge is intended to support evaluation and informed decision-making, not guarantee AI search rankings, citations, or traffic.

## 📄 License

The repository's license has not yet been specified. A license should be selected and added once the team finalizes the terms under which the project may be used, modified, and distributed
