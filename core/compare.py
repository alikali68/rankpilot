"""
RankPilot Competitive Comparison Module.
Deterministic side-by-side site audit evaluation.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.engine import RankPilotEngine
from core.models import AuditCheck, SiteAuditReport

TIE_THRESHOLD = 2.0

CATEGORY_ORDER = [
    "Meta & Head",
    "Headings",
    "Images",
    "Links",
    "Performance",
    "Security",
    "Content",
]


@dataclass
class ComparisonReport:
    mine_url: str
    rival_url: str
    mine_avg: float
    rival_avg: float
    mine_median: float
    rival_median: float
    mine_grade: str
    rival_grade: str
    mine_pages: int
    rival_pages: int
    score_delta_avg: float
    score_delta_median: float
    category_deltas: Dict[str, float]
    check_table: List[Tuple[str, float, float, float, str]]
    opportunities: List[Dict[str, Any]] = field(default_factory=list)
    pages_behind: int = 0


def _aggregate_checks(report):
    meta = {}
    order = []
    for page in report.page_reports:
        for chk in page.checks:
            if chk.name not in meta:
                meta[chk.name] = (chk.category, chk.maximum, chk.recommendation)
                order.append(chk.name)
    n_pages = len(report.page_reports)
    aggregated = {}
    for name in order:
        category, max_pts, recommendation = meta[name]
        earned_vals = [
            next((c.earned for c in page.checks if c.name == name), 0.0)
            for page in report.page_reports
        ]
        avg_earned = statistics.mean(earned_vals) if earned_vals else 0.0
        pct_score = round((avg_earned / max_pts) * 100.0, 1) if max_pts > 0 else 100.0
        status = RankPilotEngine._calc_status(avg_earned, max_pts)
        aggregated[name] = {
            "name": name,
            "category": category,
            "earned_avg": round(avg_earned, 2),
            "maximum": max_pts,
            "score": pct_score,
            "status": status,
            "recommendation": recommendation,
            "pages_counted": n_pages,
        }
    return aggregated


def compare_reports(mine, rival):
    score_delta_avg = round(mine.avg_score - rival.avg_score, 1)
    score_delta_median = round(mine.median_score - rival.median_score, 1)
    all_cats = [c for c in CATEGORY_ORDER if c in mine.category_avgs or c in rival.category_avgs]
    for c in list(mine.category_avgs.keys()) + list(rival.category_avgs.keys()):
        if c not in all_cats:
            all_cats.append(c)
    category_deltas = {}
    for cat in all_cats:
        m_val = float(mine.category_avgs.get(cat, 0.0))
        r_val = float(rival.category_avgs.get(cat, 0.0))
        category_deltas[cat] = round(m_val - r_val, 1)
    mine_checks = _aggregate_checks(mine)
    rival_checks = _aggregate_checks(rival)
    check_names = list(mine_checks.keys())
    for name in rival_checks.keys():
        if name not in check_names:
            check_names.append(name)
    check_table = []
    opportunities = []
    for name in check_names:
        m_info = mine_checks.get(name)
        r_info = rival_checks.get(name)
        m_score = m_info["score"] if m_info else 0.0
        r_score = r_info["score"] if r_info else 0.0
        delta = round(m_score - r_score, 1)
        if abs(delta) < TIE_THRESHOLD:
            outcome = "tie"
        elif delta > 0:
            outcome = "win"
        else:
            outcome = "lose"
        check_table.append((name, m_score, r_score, delta, outcome))
        m_status = m_info["status"] if m_info else "fail"
        r_status = r_info["status"] if r_info else "fail"
        if m_status == "fail" and r_status in ("pass", "warn"):
            gap = round(r_score - m_score, 1)
            opportunities.append({
                "name": name,
                "category": (m_info or r_info)["category"],
                "mine_score": m_score,
                "rival_score": r_score,
                "delta": delta,
                "gap": gap,
                "mine_status": m_status,
                "rival_status": r_status,
                "recommendation": (m_info or r_info)["recommendation"],
            })
    opportunities.sort(key=lambda x: (-x["gap"], x["name"]))
    pages_behind = sum(1 for p in mine.page_reports if p.total_score < rival.avg_score)
    return ComparisonReport(
        mine_url=mine.base_url, rival_url=rival.base_url,
        mine_avg=mine.avg_score, rival_avg=rival.avg_score,
        mine_median=mine.median_score, rival_median=rival.median_score,
        mine_grade=mine.grade, rival_grade=rival.grade,
        mine_pages=mine.page_count, rival_pages=rival.page_count,
        score_delta_avg=score_delta_avg, score_delta_median=score_delta_median,
        category_deltas=category_deltas, check_table=check_table,
        opportunities=opportunities, pages_behind=pages_behind,
    )
