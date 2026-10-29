# AI Accessibility Inspector

## Overview

An AI-powered tool that uses the Claude API to analyze mobile application screenshots and identify potential accessibility issues.

It provides a quick accessibility review with clear findings and recommendations to improve application usability. Findings are based on screenshots only and should be verified manually.

## Features

- Analyze application screenshots for potential accessibility issues.
- Compare screenshots with different accessibility settings.
- Display findings with severity, affected users, user impact, and recommended fixes.
- Export results as a CSV report.

## Project Value

Supports QA teams in identifying accessibility issues early, reducing manual review effort, and improving application usability for people with disabilities.

## Future Enhancement

Integrate with Appium to automate screen inspection and analyze UI elements and accessibility properties for more comprehensive testing.

## Getting Started

**Requirements:** Python 3.9+ .

```bash
git clone <repo-url>
cd accessibility-inspector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your API key to `.env`:

```
ANTHROPIC_API_KEY=your-api-key-here
```

Run the application:

```bash
streamlit run app.py
```
