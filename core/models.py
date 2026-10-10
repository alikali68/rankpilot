"""
Data structures for RankPilot engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


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
