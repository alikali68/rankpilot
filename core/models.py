"""
Data structures for RankPilot engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple


@dataclass
class AuditCheck:
    id: str
    name: str
    category: str
    earned: float
    maximum: float
    status: str  # "pass", "warn", "fail"
    finding: str
    recommendation: str
    technical_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    target_url: str
    final_url: str
    status_code: int
    response_time: float
    total_score: float
    letter_grade: str
    category_scores: Dict[str, Dict[str, float]]
    checks: List[AuditCheck]
    metrics: Dict[str, Any]
    timestamp: str


@dataclass
class SiteAuditReport:
    """Aggregated multi-page audit. Built on the existing AuditReport type."""
    base_url: str
    page_reports: List["AuditReport"]
    page_count: int
    avg_score: float
    median_score: float
    category_avgs: Dict[str, float]
    weakest_pages: List[Tuple[str, float]]  # (target_url, total_score), bottom 5
    grade: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "page_count": self.page_count,
            "avg_score": round(self.avg_score, 2),
            "median_score": round(self.median_score, 2),
            "grade": self.grade,
            "category_avgs": {k: round(v, 2) for k, v in self.category_avgs.items()},
            "weakest_pages": [{"url": u, "score": round(s, 2)} for u, s in self.weakest_pages],
            "timestamp": self.timestamp,
            "pages": [
                {
                    "url": p.target_url,
                    "score": round(p.total_score, 2),
                    "grade": p.letter_grade,
                    "status_code": p.status_code,
                }
                for p in self.page_reports
            ],
        }
