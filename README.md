# CiteForge — Evidence-Based Generative Engine Optimization

Making AI Search Visibility Measurable, Verifiable, and Improveable.

## 📌 Project Overview

CiteForge is an evidence-based Generative Engine Optimization (GEO) platform designed to help website owners understand how their content performs across AI-powered search and answer systems.

Unlike traditional SEO, which primarily focuses on search engine rankings, GEO focuses on whether AI systems discover, reference, and accurately represent information from a website.

CiteForge aims to evaluate content visibility, citation consistency, claim accuracy, and content integrity, then recommend evidence-based improvements.

Project Status: Under Development 🚧

## 🎯 Problem Statement

As users increasingly rely on AI-powered search systems for answers, website owners face new challenges:

- Their content may not be cited in AI-generated answers.
- Important claims may be omitted or inaccurately represented.
- Citations may vary across queries or repeated evaluations.
- Website content may need improvement to make its information easier for AI systems to discover and interpret.
- Website owners lack a unified way to evaluate AI search visibility and content integrity.

## 💡 Our Solution

CiteForge proposes an integrated GEO evaluation workflow that analyzes website content, tests its visibility across supported AI search systems, evaluates citation and claim accuracy, and identifies areas for improvement.

The platform is designed to provide measurable evaluation results and actionable recommendations instead of relying on assumptions about AI search visibility.

## ✨ Key Features

### 1. Answer Fidelity Checker

Evaluates whether information in AI-generated answers accurately reflects the claims and evidence available on the source website.

### 2. Citation Stability Analyzer

Tracks citation results across repeated evaluations to identify changes in whether and how often a source is referenced.

### 3. GEO Benchmarking System

Measures content performance using evaluation metrics such as citation rate, query coverage, claim accuracy, and citation stability.

### 4. Self-Improving GEO Assistant

Recommends targeted content improvements based on evaluation results and supports retesting to compare performance before and after changes.

### 5. Integrity Auditor

Checks website accessibility, compares responses returned for configured user-agent strings, inspects structured data, and examines robots.txt and sitemap availability.

### 6. Evidence-Based Reporting

Brings evaluation results together into a scorecard so users can identify content strengths, weaknesses, and potential next steps.

Note: These describe the planned capabilities. Individual features will be marked complete only after implementation and testing.

## 🔄 End-to-End Workflow

1. Topic Input: The user provides a topic, website, or target content.
2. Query Strategist: Relevant queries are prepared for evaluation.
3. Page Builder: Website content and relevant structured data are prepared or analyzed.
4. Citation Arena: Supported AI search systems are tested for relevant answers and citations.
5. Performance Scoring: Citation rate, query coverage, claim accuracy, and stability are evaluated.
6. Editor Agent: The system proposes improvements for weak or unclear content.
7. Integrity Audit: Website accessibility, structured data, and configured bot responses are checked.
8. Retesting & Reporting: Results are compared and summarized in an evidence-based report.

## 🛠️ Proposed Technology Stack

Component| Technology / Approach
Programming Language| Python
AI Integration| LLM API
Search Integration| Live web search API
Information Retrieval| BM25 and embeddings
Content Generation| HTML and CSS
Structured Data| JSON-LD
Version Control| Git and GitHub
Deployment| GitHub Pages or Netlify for a compatible frontend

The final technology choices will depend on the team's implementation and integration requirements.

## 🏗️ Proposed Project Structure

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

This is the proposed structure. Directories should be updated as the team finalizes and implements the modules.

## 📊 Evaluation Metrics

- Citation Rate: How often the evaluated website is cited across eligible test queries.
- Query Coverage: The proportion of test queries for which relevant website information is represented.
- Claim Accuracy: The degree to which evaluated answer claims are supported by available evidence.
- Citation Stability: How consistently citation results appear across repeated tests.
- Integrity Checks: Results of website accessibility, structured-data, and configured bot-response checks.

Each metric will require a defined calculation method and a documented test procedure.

## 🧪 Testing and Validation

The planned validation process includes:

- Testing each module independently.
- Checking citation extraction and URL handling.
- Comparing answer claims against source evidence.
- Repeating queries to measure citation variation.
- Testing website integrity checks on controlled sample pages.
- Comparing evaluation results before and after content changes.

## 🚀 Future Scope

- Competitor citation-gap analysis.
- Source freshness and accessibility monitoring.
- Historical GEO performance dashboards.
- Explainable content-improvement recommendations.
- Expanded support for AI search providers.
- Automated regression testing for content changes.

## 👥 Team and Contributions

CiteForge is being developed collaboratively as a hackathon project. Team members contribute to research, documentation, implementation, testing, and presentation.

Contributions should be made through clearly scoped changes and reviewed before integration into the main branch.

## ⚠️ Limitations

AI search results may vary depending on the query, provider, location, model, and time of evaluation. User-agent comparisons alone cannot prove that a website treats every crawler differently or establish the cause of a response difference.

CiteForge's results should therefore be interpreted as measured observations under documented testing conditions, not as guarantees of AI search ranking or citation outcomes.

## 📄 License

A project license will be specified once the team finalizes the repository's licensing terms.
