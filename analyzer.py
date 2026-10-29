"""Claude Vision integration for screenshot-based accessibility reviews."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 4096
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Claude API per-image limit
SUPPORTED_TYPES = ("image/png", "image/jpeg", "image/webp")

SEVERITIES = ("High", "Medium", "Low")
USER_GROUPS = ("Low vision", "Color blindness", "Motor disabilities")
CATEGORIES = (
    "Text readability",
    "Color contrast",
    "Touch target size",
    "Spacing",
    "Visual clarity",
    "Layout with accessibility settings",
)

SYSTEM_PROMPT = """You are an experienced mobile accessibility reviewer supporting QA engineers.
Review mobile app screenshots for barriers that affect users with low vision, color blindness, and motor
disabilities.

Focus only on what is visible: text readability, color contrast, touch target size, spacing between
interactive elements, and visual clarity.

When a second screenshot of the same screen is provided, it was taken with one or more accessibility settings
enabled, such as larger text, bold text, display zoom, dark mode, increased contrast, or grayscale. Identify
which setting changed by comparing the two, mention it in the summary, and look for problems that appear only
with it: overlapping, clipped, or hidden content with larger text or zoom; elements that lose contrast or
disappear in dark mode or increased contrast; and information shown only by color in grayscale.

Rules:
- Report only issues you can see, and name the affected element clearly (label, position, role).
- Findings are preliminary visual estimates. Do not claim WCAG compliance or non-compliance, and do not
  assess screen-reader behavior, focus order, or anything not visible in a screenshot.
- Describe contrast and size as estimates ("appears low", "appears small"), not exact values.
- Recommendations must be practical and specific enough for a developer to act on.
- If the screen looks good, return few or no findings rather than inventing issues.
- Always respond by calling the report_findings tool."""

# Returning results through a tool call gives JSON that matches this schema.
REPORT_TOOL = {
    "name": "report_findings",
    "description": "Return the accessibility review of the screenshot(s).",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Two or three sentences on the screen's overall accessibility.",
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": list(SEVERITIES)},
                        "category": {"type": "string", "enum": list(CATEGORIES)},
                        "affected_users": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(USER_GROUPS)},
                            "description": "The user groups this issue affects most.",
                        },
                        "element": {"type": "string", "description": "Affected element and its location."},
                        "issue": {"type": "string"},
                        "user_impact": {"type": "string"},
                        "recommendation": {"type": "string"},
                    },
                    "required": [
                        "severity", "category", "affected_users", "element", "issue", "user_impact", "recommendation"
                    ],
                },
            },
        },
        "required": ["summary", "findings"],
    },
}


class AnalyzerError(Exception):
    """User-facing error for configuration, input, or API failures."""


@dataclass
class Screenshot:
    data: bytes
    media_type: str

    def validate(self) -> None:
        if self.media_type not in SUPPORTED_TYPES:
            raise AnalyzerError("Unsupported image type. Use PNG, JPG, or WEBP.")
        if len(self.data) > MAX_IMAGE_BYTES:
            raise AnalyzerError("Each screenshot must be 5 MB or smaller.")

    def to_content_block(self) -> dict:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": self.media_type,
                "data": base64.standard_b64encode(self.data).decode(),
            },
        }


def get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnalyzerError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
    return anthropic.Anthropic(api_key=api_key)


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def build_content(normal: Screenshot, adjusted: Screenshot | None = None) -> list[dict]:
    content = [text_block("Screenshot 1: default display settings."), normal.to_content_block()]
    if adjusted is None:
        return content + [text_block("Review this screenshot.")]

    return content + [
        text_block("Screenshot 2: the same screen with accessibility settings enabled."),
        adjusted.to_content_block(),
        text_block(
            "Review both screenshots. Report problems that appear only in screenshot 2 "
            "under the 'Layout with accessibility settings' category."
        ),
    ]


def analyze(
    normal: Screenshot,
    adjusted: Screenshot | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Return {"summary": str, "findings": [...]} with findings sorted by severity."""
    for screenshot in (normal, adjusted):
        if screenshot is not None:
            screenshot.validate()

    client = client or get_client()
    try:
        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", DEFAULT_MODEL),
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[REPORT_TOOL],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": build_content(normal, adjusted)}],
        )
    except anthropic.AuthenticationError as e:
        raise AnalyzerError("Invalid API key. Check ANTHROPIC_API_KEY in your .env file.") from e
    except anthropic.RateLimitError as e:
        raise AnalyzerError("Rate limit reached. Wait a moment and try again.") from e
    except anthropic.APIConnectionError as e:
        raise AnalyzerError("Could not reach the Claude API. Check your internet connection.") from e
    except anthropic.APIStatusError as e:
        raise AnalyzerError(f"Claude API error ({e.status_code}): {e.message}") from e

    return parse_response(response)


def parse_response(response) -> dict:
    # A truncated response would contain incomplete tool input.
    if response.stop_reason == "max_tokens":
        raise AnalyzerError("The analysis was cut off. Try again with a single screenshot.")

    for block in response.content:
        if block.type == "tool_use":
            findings = sorted(block.input.get("findings", []), key=severity_rank)
            return {"summary": block.input.get("summary", ""), "findings": findings}

    raise AnalyzerError("Claude did not return a structured result. Try again.")


def severity_rank(finding: dict) -> int:
    severity = finding.get("severity")
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)