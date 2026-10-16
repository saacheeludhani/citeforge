Integrity Auditor

Overview

The Integrity Auditor is a tool designed to check whether a webpage returns consistent content when accessed using different user-agent identities.

Key Features

- User-Agent Comparison: Checks webpage responses using different user-agent strings, including browser and AI crawler identities.
- HTML Hashing: Generates a hash of the raw HTML response to help identify response differences.
- Text Extraction: Extracts visible text from HTML and compares the resulting hashes.
- JSON-LD Extraction: Detects structured data embedded in the webpage.
- Robots.txt Check: Reads robots.txt rules to check crawler access permissions.
- Sitemap Check: Checks whether a sitemap is available.

How It Works

1. The tool requests a webpage using different user-agent strings.
2. It extracts the HTML content and visible text.
3. It generates hashes to compare the responses.
4. It checks robots.txt and sitemap availability.
5. It reports the results using PASS/FAIL indicators.

Limitations

- JavaScript-rendered content may not be captured.
- Different HTML responses do not necessarily indicate intentional content manipulation.
- User-agent strings can be changed or spoofed.
- Text similarity alone cannot prove that all users see identical content.
- A successful robots.txt or sitemap check does not guarantee that a crawler can access every page.

Purpose

The tool helps identify potential differences in webpage responses and supports preliminary website integrity checks.
