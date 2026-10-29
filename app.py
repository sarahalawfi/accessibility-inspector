"""Streamlit UI for the AI Accessibility Inspector."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analyzer import SEVERITIES, AnalyzerError, Screenshot, analyze

SEVERITY_ICONS = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}
REPORT_COLUMNS = {
    "severity": "Severity",
    "category": "Category",
    "affected_users": "Affected users",
    "element": "Element",
    "issue": "Issue",
    "user_impact": "User impact",
    "recommendation": "Recommended fix",
}
IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]


def upload_screenshot(column, label: str, help_text: str) -> Screenshot | None:
    with column:
        upload = st.file_uploader(label, type=IMAGE_TYPES, help=help_text)
        if upload is None:
            return None
        st.image(upload, width=260)
        return Screenshot(upload.getvalue(), upload.type)


def render_finding(finding: dict) -> None:
    icon = SEVERITY_ICONS.get(finding["severity"], "⚪")
    with st.expander(f"{icon} {finding['severity']} · {finding['category']} — {finding['element']}"):
        st.markdown(f"**Affected users:** {', '.join(finding.get('affected_users', []))}")
        st.markdown(f"**Issue:** {finding['issue']}")
        st.markdown(f"**User impact:** {finding['user_impact']}")
        st.markdown(f"**Recommended fix:** {finding['recommendation']}")


def render_results(result: dict) -> None:
    findings = result["findings"]
    st.divider()
    st.subheader("Results")

    columns = st.columns(len(SEVERITIES) + 1)
    columns[0].metric("Total findings", len(findings))
    for column, severity in zip(columns[1:], SEVERITIES):
        column.metric(f"{SEVERITY_ICONS[severity]} {severity}", sum(f["severity"] == severity for f in findings))

    st.info(result["summary"])
    if not findings:
        st.success("No visible accessibility issues were found.")
        return

    for finding in findings:
        render_finding(finding)

    report = pd.DataFrame(findings, columns=list(REPORT_COLUMNS)).rename(columns=REPORT_COLUMNS)
    report["Affected users"] = report["Affected users"].apply(lambda groups: ", ".join(groups) if isinstance(groups, list) else "")
    st.download_button(
        "Download CSV report",
        data=report.to_csv(index=False).encode("utf-8-sig"),  # BOM so Excel opens it correctly
        file_name="accessibility_findings.csv",
        mime="text/csv",
    )


def main() -> None:
    st.set_page_config(page_title="AI Accessibility Inspector", page_icon="♿", layout="wide")
    st.title("♿ AI Accessibility Inspector")
   
    left, right = st.columns(2)
    normal = upload_screenshot(left, "Screenshot (required)", "Any Android or iOS screen with default settings.")
    adjusted = upload_screenshot(
        right,
        "Comparison screenshot (optional)",
        "The same screen with a different display setting, such as larger text, dark mode, or grayscale.",
    )

    if st.button("Analyze", type="primary", disabled=normal is None):
        with st.spinner("Analyzing screenshot(s)..."):
            try:
                st.session_state.result = analyze(normal, adjusted)
            except AnalyzerError as e:
                st.session_state.pop("result", None)
                st.error(str(e))

    # Stored in session state so results survive reruns, such as clicking the download button.
    if "result" in st.session_state:
        render_results(st.session_state.result)


main()