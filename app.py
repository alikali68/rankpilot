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
from core.models import AuditReport, SiteAuditReport

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


def generate_site_pdf(site_report: SiteAuditReport) -> bytes:
    """One-page executive summary for a multi-page site audit."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, 750, _pdf_safe(f"RankPilot Site Audit — {site_report.grade} ({site_report.avg_score}/100 avg)"))
    p.setFont("Helvetica", 10)
    p.drawString(50, 735, _pdf_safe(f"Base: {site_report.base_url} | Pages: {site_report.page_count} | Generated: {site_report.timestamp}"))

    p.line(50, 725, 560, 725)
    y = 700

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Category Averages:")
    y -= 20
    p.setFont("Helvetica", 10)
    for cat, pct in site_report.category_avgs.items():
        p.drawString(60, y, _pdf_safe(f"- {cat}: {pct}%"))
        y -= 16

    y -= 10
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Weakest Pages (bottom 5):")
    y -= 20
    p.setFont("Helvetica", 9)
    for url, score in site_report.weakest_pages:
        if y < 60:
            p.showPage()
            y = 750
        p.drawString(60, y, _pdf_safe(f"- {score:.1f}  {url[:90]}"))
        y -= 14

    p.save()
    buffer.seek(0)
    return buffer.getvalue()


# Sidebar Navigation
with st.sidebar:
    st.title("⚡ RankPilot Enterprise")
    st.caption("Engine v2.0 • Concurrent crawler")

    audit_mode = st.radio("Audit Mode", ["Single page", "Full site"], horizontal=True)

    input_url = st.text_input("Enter Target Domain / URL", value="https://example.com")
    max_pages = 25
    if audit_mode == "Full site":
        max_pages = st.slider("Max pages (via /sitemap.xml)", min_value=5, max_value=50, value=25, step=5)
    device_profile = st.selectbox("Inspection User-Agent", list(USER_AGENTS.keys()))
    run_btn = st.button(
        "🚀 Run Site Audit" if audit_mode == "Full site" else "🚀 Run Technical Audit",
        type="primary",
        use_container_width=True,
    )

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
    if audit_mode == "Full site":
        label = f"Crawling sitemap and auditing up to {max_pages} pages for {input_url}..."
    else:
        label = f"Crawling and validating technical parameters for {input_url}..."
    with st.spinner(label):
        try:
            if audit_mode == "Full site":
                st.session_state["active_site_report"] = engine.audit_site(input_url, max_pages=max_pages)
                st.session_state.pop("active_report", None)
            else:
                st.session_state["active_report"] = engine.inspect_url(input_url)
                st.session_state.pop("active_site_report", None)
        except Exception as err:
            st.error(f"Audit aborted due to critical error: {err}")

# Dashboard Presentation
if audit_mode == "Single page" and "active_report" in st.session_state:
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

# Full-Site Dashboard Presentation
if audit_mode == "Full site" and "active_site_report" in st.session_state:
    srep: SiteAuditReport = st.session_state["active_site_report"]

    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader(f"Site results for: `{srep.base_url}`")
        st.caption(f"Pages audited: {srep.page_count} • Timestamp: {srep.timestamp}")
    with col_t2:
        st.download_button(
            label="📄 Download Site PDF",
            data=generate_site_pdf(srep),
            file_name=f"RankPilot_site_{urlparse(srep.base_url).netloc}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    sc1, sc2, sc3, sc4 = st.columns([1.5, 1, 1, 1])
    with sc1:
        st.markdown(
            f"""
            <div class="metric-container">
                <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase;">Average Score</div>
                <div class="score-grade grade-{srep.grade}">{srep.avg_score:.1f}</div>
                <div style="font-weight: 700; font-size: 1.1rem;">GRADE: {srep.grade}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with sc2:
        st.metric("Pages Audited", srep.page_count)
    with sc3:
        st.metric("Median Score", f"{srep.median_score:.1f}")
    with sc4:
        st.metric("Weakest Page", f"{srep.weakest_pages[0][1]:.1f}" if srep.weakest_pages else "—")

    st.markdown("---")

    tab_pages, tab_cats, tab_json = st.tabs([
        "📑 All Pages",
        "📊 Category Averages",
        "💾 Export Data (JSON)",
    ])

    with tab_pages:
        rows = []
        for p in srep.page_reports:
            failed = [c for c in p.checks if c.status == "fail"]
            worst = failed[0].name if failed else "—"
            rows.append({
                "URL": p.target_url,
                "Score": round(p.total_score, 1),
                "Grade": p.letter_grade,
                "HTTP": p.status_code,
                "Worst Failing Check": worst,
            })
        df_pages = pd.DataFrame(rows).sort_values(by="Score", ascending=True)
        st.dataframe(df_pages, use_container_width=True, hide_index=True)

    with tab_cats:
        df_cats = pd.DataFrame([
            {"Category": k, "Average %": v} for k, v in srep.category_avgs.items()
        ])
        st.dataframe(df_cats, use_container_width=True, hide_index=True)
        st.bar_chart(df_cats.set_index("Category"))

    with tab_json:
        st.json(srep.to_dict())
        st.download_button(
            "Download Site JSON",
            data=json.dumps(srep.to_dict(), indent=2),
            file_name=f"site_audit_{urlparse(srep.base_url).netloc}.json",
            mime="application/json",
        )
