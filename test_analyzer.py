"""Unit tests for analyzer.py. used a fake client"""

from types import SimpleNamespace

import pytest

from analyzer import MAX_IMAGE_BYTES, AnalyzerError, Screenshot, analyze, build_content, get_client

PNG = Screenshot(b"fake-image", "image/png")


def fake_client(findings):
    """A stand-in for the Anthropic client that returns the given findings."""
    tool_call = SimpleNamespace(type="tool_use", input={"summary": "ok", "findings": findings})
    response = SimpleNamespace(stop_reason="tool_use", content=[tool_call])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


def test_one_screenshot_sends_one_image():
    images = [block for block in build_content(PNG) if block["type"] == "image"]
    assert len(images) == 1


def test_two_screenshots_send_two_images():
    images = [block for block in build_content(PNG, PNG) if block["type"] == "image"]
    assert len(images) == 2


def test_findings_are_sorted_by_severity():
    findings = [{"severity": "Low"}, {"severity": "High"}, {"severity": "Medium"}]
    result = analyze(PNG, client=fake_client(findings))
    assert [f["severity"] for f in result["findings"]] == ["High", "Medium", "Low"]


def test_unsupported_image_type_is_rejected():
    with pytest.raises(AnalyzerError):
        Screenshot(b"x", "image/gif").validate()


def test_large_image_is_rejected():
    with pytest.raises(AnalyzerError):
        Screenshot(b"x" * (MAX_IMAGE_BYTES + 1), "image/png").validate()


def test_missing_api_key_is_reported(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AnalyzerError):
        get_client()
