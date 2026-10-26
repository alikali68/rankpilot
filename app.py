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
from typing import Any
from core.compare import ComparisonReport, compare_reports
from core.cwv import CWVError, CWVResult, run_cwv

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


def generate_pdf(report: AuditReport, cwv: CWVResult | None = None) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, 750, _pdf_safe(f"RankPilot SEO Audit Report — {report.letter_grade} ({report.total_score}/100)"))
    p.setFont("Helvetica", 10)
    p.drawString(50, 735, _pdf_safe(f"Target: {report.final_url} | Generated: {report.timestamp}"))

    p.line(50, 725, 560, 725)
    y = 700

    if cwv is not None:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Core Web Vitals (Mobile — PageSpeed Insights):")
        y -= 20
        p.setFont("Helvetica", 10)
        for mid in ("lcp", "inp", "cls"):
            m = cwv.metrics[mid]
            verdict_txt = (m.verdict or "not measured").replace("-", " ").upper()
            field_txt = (
                f"real-user p75: {m.field_percentile:.0f}{m.unit} ({m.field_category})"
                if m.field_percentile is not None
                else "real-user: not enough data"
            )
            lab_txt = (
                f"lab: {m.lab_display}" if m.lab_display is not None
                else "lab: not measured"
            )
            p.drawString(60, y, _pdf_safe(f"- {m.label}: {verdict_txt} | {field_txt} | {lab_txt}"))
            y -= 16
        if not cwv.field_available:
            p.drawString(60, y, _pdf_safe("Note: no real-user (CrUX) data for this URL yet — lab values only."))
            y -= 16
        if cwv.opportunities:
            p.drawString(60, y, _pdf_safe("Top opportunities:"))
            y -= 16
            p.setFont("Helvetica", 9)
            for opp in cwv.opportunities:
                if y < 60:
                    p.showPage()
                    y = 750
                save_s = opp["savings_ms"] / 1000.0
                p.drawString(70, y, _pdf_safe(f"- {opp['title']} — saves ~{save_s:.1f}s"))
                y -= 13
            p.setFont("Helvetica", 10)
        y -= 10

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


def generate_comparison_pdf(comp: ComparisonReport) -> bytes:
    """Generates a clean executive PDF (capped at 2 pages) for competitive comparison."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    page_num = 1

    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, 750, _pdf_safe("RankPilot Competitive SEO Comparison"))
    p.setFont("Helvetica", 10)
    p.drawString(
        50,
        734,
        _pdf_safe(f"Your Site: {comp.mine_url} ({comp.mine_pages} pages)  vs.  Competitor: {comp.rival_url} ({comp.rival_pages} pages)"),
    )
    p.line(50, 724, 560, 724)

    y = 700
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Executive Score Summary:")
    y -= 18

    p.setFont("Helvetica", 10)
    sign_avg = "+" if comp.score_delta_avg > 0 else ""
    sign_med = "+" if comp.score_delta_median > 0 else ""
    p.drawString(
        60,
        y,
        _pdf_safe(
            f"Average Score:  You {comp.mine_avg:.1f}/100 (Grade {comp.mine_grade})  |  "
            f"Competitor {comp.rival_avg:.1f}/100 (Grade {comp.rival_grade})  |  "
            f"Delta: {sign_avg}{comp.score_delta_avg:.1f}"
        ),
    )
    y -= 16
    p.drawString(
        60,
        y,
        _pdf_safe(
            f"Median Score:   You {comp.mine_median:.1f}/100  |  "
            f"Competitor {comp.rival_median:.1f}/100  |  "
            f"Delta: {sign_med}{comp.score_delta_median:.1f}"
        ),
    )
    y -= 16
    p.drawString(
        60,
        y,
        _pdf_safe(f"Pages Behind Competitor Average: {comp.pages_behind} of {comp.mine_pages} audited pages"),
    )

    y -= 26
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Category Delta Breakdown (Your % vs. Competitor %):")
    y -= 18

    p.setFont("Helvetica", 10)
    for cat, delta in comp.category_deltas.items():
        d_sign = "+" if delta > 0 else ""
        p.drawString(60, y, _pdf_safe(f"- {cat}: {d_sign}{delta:.1f}%"))
        y -= 15

    y -= 14
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Priority Opportunities (Competitor Passed/Warned, You Failed):")
    y -= 18

    if not comp.opportunities:
        p.setFont("Helvetica", 10)
        p.drawString(60, y, "No critical competitive gaps detected.")
    else:
        p.setFont("Helvetica", 9)
        for idx, opp in enumerate(comp.opportunities, 1):
            if y < 75:
                if page_num >= 2:
                    break
                p.showPage()
                page_num += 1
                y = 750
                p.setFont("Helvetica-Bold", 12)
                p.drawString(50, y, "Priority Opportunities (Continued):")
                y -= 20
                p.setFont("Helvetica", 9)

            p.drawString(
                60,
                y,
                _pdf_safe(
                    f"{idx}. {opp['name']} ({opp['category']}) — "
                    f"You: {opp['mine_score']:.1f}% [{opp['mine_status'].upper()}] vs "
                    f"Rival: {opp['rival_score']:.1f}% [{opp['rival_status'].upper()}] "
                    f"(Delta: {opp['delta']:.1f})"
                ),
            )
            y -= 13
            p.drawString(75, y, _pdf_safe(f"Fix: {opp['recommendation'][:95]}"))
            y -= 16

    p.save()
    buffer.seek(0)
    return buffer.getvalue()


def _run_site_audit_with_progress(
    engine: RankPilotEngine,
    base_url: str,
    max_pages: int,
    stage_prefix: str,
    progress_bar: Any,
    frac_start: float = 0.0,
    frac_end: float = 1.0,
) -> SiteAuditReport:
    """
    Runs a sequential site audit with honest staged progress updates.
    The sitemap is discovered once, inside audit_site(); no fake per-page loop.
    """
    raw_url = base_url.strip()
    if not raw_url:
        raise ValueError("URL cannot be empty.")

    probe_resp, probe_err = engine.fetch(raw_url)
    if probe_err or probe_resp is None:
        raise RuntimeError(probe_err or f"Could not reach {raw_url}.")

    span = frac_end - frac_start
    progress_bar.progress(
        frac_start + 0.05 * span,
        text=f"{stage_prefix} crawling up to {max_pages} pages...",
    )
    site_rep = engine.audit_site(raw_url, max_pages=max_pages)
    valid_pages = [p for p in site_rep.page_reports if p.status_code > 0 and p.checks]
    if not valid_pages:
        raise RuntimeError(
            f"All {site_rep.page_count} discovered page(s) on '{raw_url}' failed validation or blocked the crawler."
        )
    progress_bar.progress(frac_end, text=f"{stage_prefix} done.")
    return site_rep


# Sidebar Navigation
with st.sidebar:
    st.title("⚡ RankPilot Enterprise")
    st.caption("Engine v2.2 • Core Web Vitals (M3)")

    audit_mode = st.radio("Audit Mode", ["Single page", "Full site", "Compare"], horizontal=True)

    if audit_mode == "Compare":
        input_url = st.text_input("Your site", value="https://example.com")
        rival_url = st.text_input("Competitor", value="https://www.iana.org")
    else:
        input_url = st.text_input("Enter Target Domain / URL", value="https://example.com")
        rival_url = ""

    max_pages = 25
    if audit_mode in ("Full site", "Compare"):
        max_pages = st.slider("Max pages (via /sitemap.xml)", min_value=5, max_value=50, value=25, step=5)
    device_profile = st.selectbox("Inspection User-Agent", list(USER_AGENTS.keys()))

    st.markdown("---")
    st.markdown("### ⚡ Core Web Vitals")
    _secret_key = ""
    try:
        _secret_key = st.secrets.get("PAGESPEED_API_KEY", "") or ""
    except Exception:
        _secret_key = ""
    pagespeed_key = st.text_input(
        "PageSpeed API key",
        value=_secret_key,
        type="password",
        help="Free key from Google Cloud (PageSpeed Insights API). "
        "Set it in Streamlit secrets as PAGESPEED_API_KEY, or paste it here "
        "for this session only. It is never saved in the repo.",
    )

    if audit_mode == "Compare":
        btn_label = "🚀 Run Comparison"
    elif audit_mode == "Full site":
        btn_label = "🚀 Run Site Audit"
    else:
        btn_label = "🚀 Run Technical Audit"

    run_btn = st.button(
        btn_label,
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
    if audit_mode == "Compare":
        prog = st.progress(0.0, text="Initializing comparison audit...")
        mine_rep: SiteAuditReport | None = None
        rival_rep: SiteAuditReport | None = None

        try:
            mine_rep = _run_site_audit_with_progress(
                engine, input_url, max_pages, "Auditing your site…", prog, 0.0, 0.45
            )
        except Exception as err:
            prog.empty()
            st.error(
                f"Could not complete the audit for your site ({input_url}): {err} "
                "Please verify the URL and try again."
            )

        if mine_rep is not None:
            try:
                rival_rep = _run_site_audit_with_progress(
                    engine, rival_url, max_pages, "Auditing competitor…", prog, 0.5, 0.95
                )
            except Exception as err:
                prog.empty()
                st.warning(
                    f"We could not crawl the competitor site ({rival_url}). "
                    f"Reason: {err} "
                    "The site may be blocking automated requests, timing out, or missing a reachable landing page. "
                    "Please try a different competitor URL."
                )

        if mine_rep is not None and rival_rep is not None:
            prog.progress(1.0, text="Computing competitive comparison...")
            st.session_state["active_comparison"] = compare_reports(mine_rep, rival_rep)
            st.session_state.pop("active_report", None)
            st.session_state.pop("active_site_report", None)
            st.session_state.pop("active_cwv", None)
            st.session_state.pop("active_cwv_url", None)
            prog.empty()
    else:
        if audit_mode == "Full site":
            label = f"Crawling sitemap and auditing up to {max_pages} pages for {input_url}..."
        else:
            label = f"Crawling and validating technical parameters for {input_url}..."
        with st.spinner(label):
            try:
                if audit_mode == "Full site":
                    st.session_state["active_site_report"] = engine.audit_site(input_url, max_pages=max_pages)
                    st.session_state.pop("active_report", None)
                    st.session_state.pop("active_comparison", None)
                    st.session_state.pop("active_cwv", None)
                    st.session_state.pop("active_cwv_url", None)
                else:
                    st.session_state["active_report"] = engine.inspect_url(input_url)
                    st.session_state.pop("active_site_report", None)
                    st.session_state.pop("active_comparison", None)
                    st.session_state.pop("active_cwv", None)
                    st.session_state.pop("active_cwv_url", None)
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
        _cwv = st.session_state.get("active_cwv")
        if st.session_state.get("active_cwv_url") != rep.final_url:
            _cwv = None
        pdf_bytes = generate_pdf(rep, cwv=_cwv)
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
    tab_overview, tab_matrix, tab_issues, tab_json, tab_cwv = st.tabs([
        "📊 Category Radar & Analytics",
        "📑 Comprehensive Matrix",
        "🚨 Prioritized Action Items",
        "💾 Export Data (JSON)",
        "⚡ Core Web Vitals",
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
            "core_web_vitals": _cwv.to_dict() if _cwv else None,
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

    # Tab 5: Core Web Vitals (mobile-first, PageSpeed Insights)
    with tab_cwv:
        st.markdown("### ⚡ Core Web Vitals — Mobile")
        st.caption(
            "Real-user experience from Google PageSpeed Insights. Each metric "
            "is judged on its own against Google's thresholds — there is no "
            "single combined score. Field data comes from real Chrome users "
            "(CrUX); lab data is the Lighthouse measurement for this run."
        )
        if not pagespeed_key:
            st.info(
                "No API key set — this run will use Google's anonymous quota, "
                "which is much lower. For reliable results, paste your free "
                "PageSpeed Insights API key in the sidebar, or set it in "
                "Streamlit secrets as PAGESPEED_API_KEY."
            )
        if st.button("🚀 Run Core Web Vitals (mobile)", type="primary"):
            with st.spinner("Measuring with PageSpeed Insights (usually 10–30 s)…"):
                try:
                    _result = run_cwv(rep.final_url, api_key=pagespeed_key or None)
                except CWVError as err:
                    st.error(str(err))
                else:
                    st.session_state["active_cwv"] = _result
                    st.session_state["active_cwv_url"] = rep.final_url
                    st.rerun()

        _cwv = st.session_state.get("active_cwv")
        if st.session_state.get("active_cwv_url") != rep.final_url:
            _cwv = None
        if _cwv is not None:
            st.caption(
                f"Strategy: Mobile • Fetched: {_cwv.fetched_at} • "
                f"Lab performance score: "
                f"{_cwv.performance_score * 100:.0f}/100"
                if _cwv.performance_score is not None
                else f"Strategy: Mobile • Fetched: {_cwv.fetched_at}"
            )
            if not _cwv.field_available:
                st.warning(
                    "Not enough real-user (CrUX) data for this URL yet — "
                    "showing lab measurements only. Popular pages accumulate "
                    "field data over time."
                )
            _verdict_color = {
                "good": "#10b981",
                "needs-improvement": "#f59e0b",
                "poor": "#ef4444",
            }
            _cols = st.columns(3)
            for _col, _mid in zip(_cols, ("lcp", "inp", "cls")):
                _m = _cwv.metrics[_mid]
                _color = _verdict_color.get(_m.verdict, "#9ca3af")
                _verdict_txt = (_m.verdict or "not measured").replace("-", " ").title()
                _field_txt = (
                    f"{_m.field_percentile:.0f}{_m.unit} ({_m.field_category})"
                    if _m.field_percentile is not None
                    else "No real-user data"
                )
                _lab_txt = (
                    f"Lab: {_m.lab_display}"
                    if _m.lab_display is not None
                    else "Lab: not measured"
                )
                with _col:
                    st.markdown(
                        f"""
                        <div class="metric-container" style="border-top: 3px solid {_color};">
                            <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase;">{_m.label}</div>
                            <div style="font-size: 1.6rem; font-weight: 800; color: {_color}; margin: 6px 0;">{_verdict_txt}</div>
                            <div style="font-size: 0.95rem;">Real-user p75: <strong>{_field_txt}</strong></div>
                            <div style="font-size: 0.85rem; color: #9ca3af; margin-top: 4px;">{_lab_txt}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            st.markdown("---")
            st.markdown("### 🎯 Top opportunities (by time saved)")
            if not _cwv.opportunities:
                st.success("No significant opportunities found on this run — the page is already lean.")
            else:
                for _opp in _cwv.opportunities:
                    _save = _opp["savings_ms"] / 1000.0
                    _disp = f" — {_opp['display']}" if _opp.get("display") else ""
                    st.markdown(
                        f"- **{_opp['title']}** — saves ~{_save:.1f}s{_disp}"
                    )
            st.caption("The CWV result is included in the PDF and JSON downloads above.")

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

# Compare Mode Dashboard Presentation
if audit_mode == "Compare" and "active_comparison" in st.session_state:
    comp: ComparisonReport = st.session_state["active_comparison"]

    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader(f"Comparison: `{comp.mine_url}` vs `{comp.rival_url}`")
        st.caption(
            f"Your pages audited: {comp.mine_pages} • Competitor pages audited: {comp.rival_pages} • "
            f"Your pages below competitor average: {comp.pages_behind}"
        )
    with col_t2:
        mine_host = urlparse(comp.mine_url).netloc or "yoursite"
        rival_host = urlparse(comp.rival_url).netloc or "competitor"
        st.download_button(
            label="📄 Download comparison PDF",
            data=generate_comparison_pdf(comp),
            file_name=f"RankPilot_compare_{mine_host}_vs_{rival_host}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # 1. Side-by-side Score Cards
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.2])

    with sc1:
        st.markdown(
            f"""
            <div class="metric-container">
                <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase;">Your Site Average</div>
                <div class="score-grade grade-{comp.mine_grade}">{comp.mine_avg:.1f}</div>
                <div style="font-weight: 700; font-size: 1.05rem;">GRADE: {comp.mine_grade} • Median: {comp.mine_median:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with sc2:
        st.markdown(
            f"""
            <div class="metric-container">
                <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase;">Competitor Average</div>
                <div class="score-grade grade-{comp.rival_grade}">{comp.rival_avg:.1f}</div>
                <div style="font-weight: 700; font-size: 1.05rem;">GRADE: {comp.rival_grade} • Median: {comp.rival_median:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with sc3:
        delta_color = "#10b981" if comp.score_delta_avg > 0 else ("#ef4444" if comp.score_delta_avg < 0 else "#9ca3af")
        avg_prefix = "+" if comp.score_delta_avg > 0 else ""
        med_prefix = "+" if comp.score_delta_median > 0 else ""
        st.markdown(
            f"""
            <div class="metric-container">
                <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase;">Score Delta (You vs Rival)</div>
                <div class="score-grade" style="color: {delta_color};">{avg_prefix}{comp.score_delta_avg:.1f}</div>
                <div style="font-weight: 700; font-size: 1.05rem; color: #d1d5db;">
                    Median Delta: {med_prefix}{comp.score_delta_median:.1f} • Pages Behind: {comp.pages_behind}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # 2. Category Delta Bar Chart
    st.markdown("### 📊 Category Performance Deltas (Your % − Competitor %)")
    cat_names = list(comp.category_deltas.keys())
    cat_vals = [comp.category_deltas[c] for c in cat_names]
    bar_colors = ["#10b981" if v >= 0 else "#ef4444" for v in cat_vals]

    fig_delta = go.Figure(
        go.Bar(
            x=cat_names,
            y=cat_vals,
            marker_color=bar_colors,
            text=[f"{'+' if v > 0 else ''}{v:.1f}%" for v in cat_vals],
            textposition="outside",
        )
    )
    fig_delta.update_layout(
        yaxis_title="Score Delta (%)",
        xaxis_title="Category",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f3f4f6"),
        margin=dict(l=30, r=30, t=30, b=30),
        yaxis=dict(zeroline=True, zerolinewidth=1.5, zerolinecolor="#6b7280"),
    )
    st.plotly_chart(fig_delta, use_container_width=True)

    st.markdown("---")

    # 3. Check-by-Check Comparison Table & 4. Opportunities
    tab_opp, tab_checks = st.tabs([
        "🎯 Priority Opportunities (Fix First)",
        "📑 Full Check Comparison Table",
    ])

    with tab_opp:
        st.subheader("Fix These First: Competitor Passed/Warned Where You Failed")
        if not comp.opportunities:
            st.success("You have no checks where you failed while the competitor passed or warned.")
        else:
            for rank, opp in enumerate(comp.opportunities, 1):
                st.markdown(
                    f"""
                    <div style="border-left: 4px solid #ef4444; padding-left: 14px; margin-bottom: 12px; background: #111827; padding-top: 10px; padding-bottom: 10px; border-radius: 0 8px 8px 0;">
                        <span style="font-weight: 800; color: #ef4444;">#{rank} [GAP: -{opp['gap']:.1f} pts]</span>
                        <strong style="font-size: 1.05rem;"> {opp['name']}</strong>
                        <span style="color: #9ca3af; font-size: 0.85rem;"> ({opp['category']})</span>
                        <div style="margin-top: 4px; color: #e5e7eb;">
                            Your Score: <strong>{opp['mine_score']:.1f}%</strong> ({opp['mine_status'].upper()}) &nbsp;|&nbsp;
                            Competitor Score: <strong>{opp['rival_score']:.1f}%</strong> ({opp['rival_status'].upper()}) &nbsp;|&nbsp;
                            Delta: <strong style="color: #ef4444;">{opp['delta']:.1f}</strong>
                        </div>
                        <div style="margin-top: 4px; color: #60a5fa; font-weight: 500;">👉 {opp['recommendation']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with tab_checks:
        sort_col1, sort_col2 = st.columns([2, 2])
        with sort_col1:
            sort_order = st.selectbox(
                "Sort checks by Delta",
                ["Largest Deficit First (Ascending)", "Largest Lead First (Descending)", "Default Check Order"],
            )

        rows_chk = [
            {
                "Check": name,
                "Your Score": m_sc,
                "Competitor Score": r_sc,
                "Delta": d_sc,
                "Status": st_label,
            }
            for (name, m_sc, r_sc, d_sc, st_label) in comp.check_table
        ]
        df_checks = pd.DataFrame(rows_chk)

        if not df_checks.empty:
            if sort_order == "Largest Deficit First (Ascending)":
                df_checks = df_checks.sort_values(by="Delta", ascending=True)
            elif sort_order == "Largest Lead First (Descending)":
                df_checks = df_checks.sort_values(by="Delta", ascending=False)

            def _style_status_row(row: pd.Series) -> list[str]:
                status = row["Status"]
                if status == "win":
                    bg = "background-color: rgba(16, 185, 129, 0.18); color: #10b981;"
                elif status == "lose":
                    bg = "background-color: rgba(239, 68, 68, 0.18); color: #ef4444;"
                else:
                    bg = "background-color: rgba(156, 163, 175, 0.12); color: #d1d5db;"
                return [bg] * len(row)

            styled_df = df_checks.style.apply(_style_status_row, axis=1).format({
                "Your Score": "{:.1f}",
                "Competitor Score": "{:.1f}",
                "Delta": "{:+.1f}",
            })
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
