"""
RankPilot — Commercial Dashboard UI.
Single-entry application runner.
"""

from __future__ import annotations

import io
import json
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from core.engine import RankPilotEngine, USER_AGENTS
from core.models import AuditReport

st.set_page_config(
    page_title="RankPilot — Technical SEO Auditor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-End Styling
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0b0f17;
        color: #f3f4f6;
    }
    .metric-container {
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    }
    .score-grade {
        font-size: 4rem;
        font-weight: 900;
        letter-spacing: -2px;
        line-height: 1;
        margin: 8px 0;
    }
    .grade-A { color: #10b981; }
    .grade-B { color: #3b82f6; }
    .grade-C { color: #f59e0b; }
    .grade-D { color: #f97316; }
    .grade-F { color: #ef4444; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _pdf_safe(text: str) -> str:
    """Strip characters the PDF base fonts cannot render (non-Latin scripts)."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(report: AuditReport) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, 750, _pdf_safe(f"RankPilot SEO Audit Report — {report.letter_grade} ({report.total_score}/100)"))
    p.setFont("Helvetica", 10)
    p.drawString(50, 735, _pdf_safe(f"Target: {report.final_url} | Generated: {report.timestamp}"))

    p.line(50, 725, 560, 725)
    y = 700

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Category Performance Breakdown:")
    y -= 20

    p.setFont("Helvetica", 10)
    for cat, val in report.category_scores.items():
        p.drawString(60, y, _pdf_safe(f"- {cat}: {val['earned']} / {val['max']} pts ({val['pct']}%)"))
        y -= 16

    y -= 10
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Priority Technical Remediation Plan:")
    y -= 20

    fails = [c for c in report.checks if c.status in ("fail", "warn")]
    p.setFont("Helvetica", 9)
    for f in fails[:15]:
        if y < 60:
            p.showPage()
            y = 750
        status_tag = f"[{f.status.upper()}]"
        p.drawString(60, y, _pdf_safe(f"{status_tag} {f.name} ({f.category}): {f.finding}"))
        y -= 12
        p.drawString(75, y, _pdf_safe(f"Action: {f.recommendation}"))
        y -= 16

    p.save()
    buffer.seek(0)
    return buffer.getvalue()


# Sidebar Navigation
with st.sidebar:
    st.title("⚡ RankPilot Enterprise")
    st.caption("Engine v2.0 • Concurrent crawler")

    input_url = st.text_input("Enter Target Domain / URL", value="https://example.com")
    device_profile = st.selectbox("Inspection User-Agent", list(USER_AGENTS.keys()))
    run_btn = st.button("🚀 Run Technical Audit", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### 📋 Audit Weights")
    st.markdown(
        """
        - **Meta & Head**: 20 pts
        - **Headings Structure**: 15 pts
        - **Images & Visual Assets**: 15 pts
        - **Link Health**: 15 pts
        - **Page Performance**: 15 pts
        - **Web Security**: 10 pts
        - **Content Volume**: 10 pts
        """
    )

# Execution Handler
if run_btn:
    engine = RankPilotEngine(user_agent_key=device_profile)
    with st.spinner(f"Crawling and validating technical parameters for {input_url}..."):
        try:
            report = engine.inspect_url(input_url)
            st.session_state["active_report"] = report
        except Exception as err:
            st.error(f"Audit aborted due to critical error: {err}")

# Dashboard Presentation
if "active_report" in st.session_state:
    rep: AuditReport = st.session_state["active_report"]

    # Action Toolbar
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader(f"Results for: `{rep.final_url}`")
        st.caption(f"Status: HTTP {rep.status_code} • Scan Duration: {rep.response_time}s • Timestamp: {rep.timestamp}")
    with col_t2:
        pdf_bytes = generate_pdf(rep)
        st.download_button(
            label="📄 Download PDF Audit",
            data=pdf_bytes,
            file_name=f"RankPilot_{urlparse(rep.final_url).netloc}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # Score Cards
    sc1, sc2, sc3, sc4, sc5 = st.columns([1.5, 1, 1, 1, 1.2])

    with sc1:
        st.markdown(
            f"""
            <div class="metric-container">
                <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase;">Overall Score</div>
                <div class="score-grade grade-{rep.letter_grade}">{rep.total_score:.1f}</div>
                <div style="font-weight: 700; font-size: 1.1rem;">GRADE: {rep.letter_grade}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    passes = sum(1 for c in rep.checks if c.status == "pass")
    warns = sum(1 for c in rep.checks if c.status == "warn")
    fails = sum(1 for c in rep.checks if c.status == "fail")

    with sc2:
        st.metric("Passed Checks", passes, delta=f"{passes}/{len(rep.checks)}")
    with sc3:
        st.metric("Warnings", warns)
    with sc4:
        st.metric("Critical Fails", fails)
    with sc5:
        st.metric("Page Size", f"{rep.metrics['html_kb']} KB")

    st.markdown("---")

    # Tabs
    tab_overview, tab_matrix, tab_issues, tab_json = st.tabs([
        "📊 Category Radar & Analytics",
        "📑 Comprehensive Matrix",
        "🚨 Prioritized Action Items",
        "💾 Export Data (JSON)",
    ])

    # Tab 1: Category Radar
    with tab_overview:
        c1, c2 = st.columns([1.5, 2])
        with c1:
            cats = list(rep.category_scores.keys())
            pcts = [rep.category_scores[c]["pct"] for c in cats]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=pcts,
                theta=cats,
                fill='toself',
                name='Compliance %',
                line_color='#3b82f6'
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=30, r=30, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("### Category Points Distribution")
            df_cats = pd.DataFrame([
                {"Category": k, "Earned": v["earned"], "Max": v["max"], "Score %": f"{v['pct']}%"}
                for k, v in rep.category_scores.items()
            ])
            st.dataframe(df_cats, use_container_width=True, hide_index=True)

    # Tab 2: Matrix
    with tab_matrix:
        filter_status = st.multiselect("Filter by status", ["pass", "warn", "fail"], default=["pass", "warn", "fail"])
        filtered_checks = [c for c in rep.checks if c.status in filter_status]

        for chk in filtered_checks:
            with st.expander(f"[{chk.status.upper()}] {chk.name} — {chk.earned}/{chk.maximum} pts ({chk.category})"):
                st.markdown(f"**Findings:** {chk.finding}")
                st.markdown(f"**Recommended Action:** `{chk.recommendation}`")

    # Tab 3: Action Items
    with tab_issues:
        st.subheader("Action Plan: Ranked by Points Deficit")
        urgent = [c for c in rep.checks if c.status in ("fail", "warn")]
        urgent.sort(key=lambda x: (0 if x.status == "fail" else 1, -(x.maximum - x.earned)))

        if not urgent:
            st.success("No critical issues or warnings detected.")
        else:
            for rank, issue in enumerate(urgent, 1):
                deficit = issue.maximum - issue.earned
                color = "#ef4444" if issue.status == "fail" else "#f59e0b"
                st.markdown(
                    f"""
                    <div style="border-left: 4px solid {color}; padding-left: 14px; margin-bottom: 12px; background: #111827; padding-top: 8px; padding-bottom: 8px; border-radius: 0 8px 8px 0;">
                        <span style="font-weight: 800; color: {color};">#{rank} [{issue.status.upper()}]</span>
                        <strong style="font-size: 1.05rem;">{issue.name}</strong>
                        <span style="color: #9ca3af; font-size: 0.85rem;">(Loss: -{deficit:.1f} pts)</span>
                        <div style="margin-top: 4px; color: #e5e7eb;">{issue.finding}</div>
                        <div style="margin-top: 4px; color: #60a5fa; font-weight: 500;">👉 {issue.recommendation}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Tab 4: JSON Export
    with tab_json:
        export_dict = {
            "target": rep.final_url,
            "score": rep.total_score,
            "grade": rep.letter_grade,
            "categories": rep.category_scores,
            "metrics": rep.metrics,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "earned": c.earned,
                    "max": c.maximum,
                    "status": c.status,
                    "finding": c.finding,
                    "recommendation": c.recommendation,
                }
                for c in rep.checks
            ],
        }
        st.json(export_dict)
        st.download_button(
            "Download Raw JSON",
            data=json.dumps(export_dict, indent=2),
            file_name=f"audit_{urlparse(rep.final_url).netloc}.json",
            mime="application/json",
        )

    st.markdown("---")
    st.markdown(
        "<p style='text-align:center;color:#6b7280;font-size:0.85rem;'>RankPilot — data-driven SEO audits.</p>",
        unsafe_allow_html=True,
    )
