"""
Core Web Vitals via the Google PageSpeed Insights API (Module M3).

One URL, one strategy (mobile-first), three metrics: LCP, INP, CLS.
Each metric is judged separately against Google's thresholds — there is
no single combined CWV score. Field data (Chrome UX Report, real users)
is the source of truth for pass/fail; lab data (Lighthouse) is diagnostic.

The API key is never stored here. The caller passes it in (Streamlit
secrets or a session-only sidebar field). Calls without a key are allowed
by Google at a lower quota and are surfaced as such, never silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

PSI_ENDPOINT = (
    "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
)

# Google's CWV thresholds: (good_max, needs_improvement_max).
# LCP/INP in milliseconds, CLS unitless.
THRESHOLDS = {
    "lcp": (2500.0, 4000.0),
    "inp": (200.0, 500.0),
    "cls": (0.1, 0.25),
}

LAB_AUDIT_IDS = {
    "lcp": "largest-contentful-paint",
    "inp": "interaction-to-next-paint",
    "cls": "cumulative-layout-shift",
}

FIELD_METRIC_IDS = {
    "lcp": "LARGEST_CONTENTFUL_PAINT_MS",
    "inp": "INTERACTION_TO_NEXT_PAINT",
    "cls": "CUMULATIVE_LAYOUT_SHIFT_SCORE",
}

LABELS = {
    "lcp": "Largest Contentful Paint",
    "inp": "Interaction to Next Paint",
    "cls": "Cumulative Layout Shift",
}

UNITS = {"lcp": "ms", "inp": "ms", "cls": ""}

# CrUX category -> verdict.
FIELD_CATEGORY_VERDICT = {
    "FAST": "good",
    "AVERAGE": "needs-improvement",
    "SLOW": "poor",
}


class CWVError(Exception):
    """A user-facing Core Web Vitals failure (never a raw traceback)."""


def verdict_for_value(metric: str, value: Optional[float]) -> Optional[str]:
    """Pass/fail for one metric value. None when there is no value."""
    if value is None:
        return None
    good_max, ni_max = THRESHOLDS[metric]
    if value <= good_max:
        return "good"
    if value <= ni_max:
        return "needs-improvement"
    return "poor"


@dataclass
class CWVMetric:
    id: str  # "lcp" | "inp" | "cls"
    label: str
    unit: str
    field_percentile: Optional[float] = None
    field_category: Optional[str] = None
    lab_value: Optional[float] = None
    lab_display: Optional[str] = None
    lab_score: Optional[float] = None
    verdict: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "field_percentile": self.field_percentile,
            "field_category": self.field_category,
            "lab_value": self.lab_value,
            "lab_display": self.lab_display,
            "verdict": self.verdict,
        }


@dataclass
class CWVResult:
    url: str
    strategy: str
    fetched_at: str
    field_available: bool
    field_overall_category: Optional[str] = None
    performance_score: Optional[float] = None
    metrics: Dict[str, CWVMetric] = field(default_factory=dict)
    opportunities: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "strategy": self.strategy,
            "fetched_at": self.fetched_at,
            "field_available": self.field_available,
            "field_overall_category": self.field_overall_category,
            "performance_score": self.performance_score,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "opportunities": self.opportunities,
        }


def fetch_cwv(
    url: str,
    api_key: Optional[str] = None,
    strategy: str = "mobile",
    timeout: int = 90,
) -> Dict[str, Any]:
    """Call runPagespeed for one URL. Returns the raw JSON payload.

    Raises CWVError with a plain-language message on any failure.
    """
    params: Dict[str, str] = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
    }
    if api_key:
        params["key"] = api_key
    try:
        resp = requests.get(PSI_ENDPOINT, params=params, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise CWVError(
            "PageSpeed Insights took too long to answer (over "
            f"{timeout}s). The target may be slow or unreachable from "
            "Google's servers — try again."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise CWVError(f"Could not reach PageSpeed Insights: {exc}") from exc

    if resp.status_code == 200:
        return resp.json()
    detail = ""
    try:
        detail = str((resp.json().get("error") or {}).get("message", ""))
    except Exception:
        detail = ""
    if resp.status_code == 400:
        if "API key" in detail:
            raise CWVError(
                "PageSpeed Insights rejected the API key (the key is not "
                "valid). Check the key in the sidebar or Streamlit secrets."
            )
        raise CWVError(
            "PageSpeed Insights rejected the request (HTTP 400). The URL "
            "may be malformed or unreachable — check it and try again."
        )
    if resp.status_code == 403:
        raise CWVError(
            "PageSpeed Insights refused the API key (HTTP 403). Check that "
            "the key is valid and that the PageSpeed Insights API is "
            "enabled for its Google Cloud project."
        )
    if resp.status_code == 429:
        raise CWVError(
            "PageSpeed Insights rate limit reached (HTTP 429). Wait a few "
            "minutes, or add an API key — keyless calls have a much lower quota."
        )
    raise CWVError(
        f"PageSpeed Insights returned HTTP {resp.status_code}. "
        "Try again in a few minutes."
    )


def parse_cwv(payload: Dict[str, Any], url: str, strategy: str) -> CWVResult:
    """Turn a raw runPagespeed payload into a CWVResult. Never invents numbers.

    Field (CrUX) data is used when present; a missing field metric stays
    None and is reported as 'not enough real-user data'. A lab metric that
    Lighthouse did not measure (INP is commonly absent) stays None.
    """
    loading = payload.get("loadingExperience") or {}
    field_metrics = loading.get("metrics") or {}
    lighthouse = payload.get("lighthouseResult") or {}
    audits = lighthouse.get("audits") or {}
    categories = lighthouse.get("categories") or {}

    result = CWVResult(
        url=url,
        strategy=strategy,
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        field_available=bool(field_metrics),
        field_overall_category=loading.get("overall_category"),
        performance_score=(categories.get("performance") or {}).get("score"),
    )

    for metric_id in ("lcp", "inp", "cls"):
        field_entry = field_metrics.get(FIELD_METRIC_IDS[metric_id]) or {}
        lab_audit = audits.get(LAB_AUDIT_IDS[metric_id]) or {}
        lab_value = lab_audit.get("numericValue")
        if lab_value is not None:
            lab_value = float(lab_value)

        field_percentile = field_entry.get("percentile")
        if field_percentile is not None:
            field_percentile = float(field_percentile)
        field_category = field_entry.get("category")

        # Field verdict wins when real-user data exists; otherwise lab value.
        verdict = None
        if field_category in FIELD_CATEGORY_VERDICT:
            verdict = FIELD_CATEGORY_VERDICT[field_category]
        else:
            verdict = verdict_for_value(metric_id, lab_value)

        result.metrics[metric_id] = CWVMetric(
            id=metric_id,
            label=LABELS[metric_id],
            unit=UNITS[metric_id],
            field_percentile=field_percentile,
            field_category=field_category,
            lab_value=lab_value,
            lab_display=lab_audit.get("displayValue"),
            lab_score=lab_audit.get("score"),
            verdict=verdict,
        )

    opportunities: List[Dict[str, Any]] = []
    for audit_id, audit in audits.items():
        if not isinstance(audit, dict):
            continue
        details = audit.get("details") or {}
        if details.get("type") != "opportunity":
            continue
        savings = details.get("overallSavingsMs")
        if savings is None or float(savings) <= 0:
            continue
        opportunities.append(
            {
                "id": audit_id,
                "title": audit.get("title") or audit_id,
                "display": audit.get("displayValue"),
                "savings_ms": float(savings),
            }
        )
    opportunities.sort(key=lambda o: o["savings_ms"], reverse=True)
    result.opportunities = opportunities[:3]
    return result


def run_cwv(
    url: str,
    api_key: Optional[str] = None,
    strategy: str = "mobile",
    timeout: int = 90,
) -> CWVResult:
    """Fetch and parse in one call (the entry point the UI uses)."""
    return parse_cwv(fetch_cwv(url, api_key, strategy, timeout), url, strategy)
