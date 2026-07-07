"""One-shot baseline-vs-window drift testing.

Procedure (diff / check population comparisons):
1. Per-metric two-sample Mann-Whitney U test (non-parametric; scipy.stats).
2. Benjamini-Hochberg false discovery rate correction across simultaneous tests
   (Benjamini & Hochberg, 1995).
3. Omnibus decision via Fisher's method combining raw p-values of BH-rejected
   metrics (Fisher, 1925).

This replaces ad hoc z-score cutoffs and hand-rolled "at least two metrics"
rules for batch comparisons. Streaming live traffic uses ADWIN/Page-Hinkley
instead (see streaming.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from cogscope.calibration.profiles import LENGTH_METRICS, QUALITY_METRICS
from cogscope.core.models import BehavioralFingerprint

# Core fingerprint metrics compared in batch mode
BATCH_METRICS: tuple[str, ...] = (
    "depth",
    "total_steps",
    "verification_steps",
    "hedging_ratio",
    "correction_count",
    "branching_factor",
    "uncertainty_markers",
    "tool_call_count",
)


@dataclass
class MetricTestResult:
    """Per-metric Mann-Whitney result."""

    metric: str
    p_value: float
    bh_adjusted_p: float
    bh_rejected: bool
    is_quality: bool
    is_length: bool
    baseline_mean: float
    current_mean: float


@dataclass
class BatchDriftResult:
    """Outcome of BH + Fisher batch drift test."""

    should_alert: bool
    fisher_p_value: float
    fisher_statistic: float
    alpha: float
    metric_results: list[MetricTestResult] = field(default_factory=list)
    rejected_metrics: list[str] = field(default_factory=list)
    summary: str = ""


def _metric_values(fingerprints: list[BehavioralFingerprint], metric: str) -> list[float]:
    return [float(getattr(fp, metric)) for fp in fingerprints]


def benjamini_hochberg(
    p_values: dict[str, float],
    alpha: float = 0.05,
) -> dict[str, tuple[float, bool]]:
    """Benjamini-Hochberg FDR correction.

    Returns mapping metric -> (adjusted_p, rejected_at_alpha).
    """
    if not p_values:
        return {}

    items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted: dict[str, tuple[float, bool]] = {}
    prev_adj = 1.0
    for rank in range(m, 0, -1):
        metric, p = items[rank - 1]
        adj = min(prev_adj, p * m / rank)
        prev_adj = adj
        adjusted[metric] = (adj, adj <= alpha)
    return adjusted


def fisher_combine(p_values: list[float]) -> tuple[float, float]:
    """Fisher's method for combining independent p-values.

    Returns (statistic, combined_p_value).
    """
    if not p_values:
        return 0.0, 1.0
    clipped = [max(min(p, 1.0 - 1e-16), 1e-16) for p in p_values]
    stat, combined_p = stats.combine_pvalues(clipped, method="fisher")
    return float(stat), float(combined_p)


def batch_drift_test(
    baseline_fps: list[BehavioralFingerprint],
    current_fps: list[BehavioralFingerprint],
    alpha: float = 0.05,
    metrics: tuple[str, ...] = BATCH_METRICS,
    require_quality_metric: bool = True,
) -> BatchDriftResult:
    """Run Mann-Whitney + BH + Fisher on two fingerprint populations."""
    if len(baseline_fps) < 3 or len(current_fps) < 3:
        return BatchDriftResult(
            should_alert=False,
            fisher_p_value=1.0,
            fisher_statistic=0.0,
            alpha=alpha,
            summary="Insufficient samples for batch drift test (need >=3 per side).",
        )

    raw_p: dict[str, float] = {}
    means: dict[str, tuple[float, float]] = {}

    for metric in metrics:
        b_vals = _metric_values(baseline_fps, metric)
        c_vals = _metric_values(current_fps, metric)
        b_mean = float(np.mean(b_vals))
        c_mean = float(np.mean(c_vals))
        means[metric] = (b_mean, c_mean)
        try:
            _, p = stats.mannwhitneyu(b_vals, c_vals, alternative="two-sided")
            raw_p[metric] = float(p)
        except Exception:
            raw_p[metric] = 1.0

    bh = benjamini_hochberg(raw_p, alpha=alpha)
    metric_results: list[MetricTestResult] = []
    rejected_raw_ps: list[float] = []
    rejected_names: list[str] = []

    for metric in metrics:
        adj_p, rejected = bh.get(metric, (1.0, False))
        b_mean, c_mean = means[metric]
        metric_results.append(
            MetricTestResult(
                metric=metric,
                p_value=raw_p[metric],
                bh_adjusted_p=adj_p,
                bh_rejected=rejected,
                is_quality=metric in QUALITY_METRICS,
                is_length=metric in LENGTH_METRICS,
                baseline_mean=b_mean,
                current_mean=c_mean,
            )
        )
        if rejected:
            rejected_names.append(metric)
            rejected_raw_ps.append(raw_p[metric])

    fisher_stat, fisher_p = fisher_combine(rejected_raw_ps)

    quality_rejected = [m for m in rejected_names if m in QUALITY_METRICS]
    length_only = rejected_names and all(m in LENGTH_METRICS for m in rejected_names)

    should_alert = (
        len(rejected_names) >= 1
        and fisher_p < alpha
        and not length_only
        and (not require_quality_metric or len(quality_rejected) >= 1)
    )

    if not rejected_names:
        summary = "No metrics rejected after Benjamini-Hochberg correction."
    elif should_alert:
        summary = (
            f"Batch drift: Fisher p={fisher_p:.4f} across "
            f"{len(rejected_names)} BH-rejected metrics."
        )
    else:
        summary = (
            f"BH rejected {len(rejected_names)} metric(s) but omnibus Fisher "
            f"p={fisher_p:.4f} or quality/length guard prevented alert."
        )

    return BatchDriftResult(
        should_alert=should_alert,
        fisher_p_value=fisher_p,
        fisher_statistic=fisher_stat,
        alpha=alpha,
        metric_results=metric_results,
        rejected_metrics=rejected_names,
        summary=summary,
    )


def outliers_from_batch(result: BatchDriftResult) -> list[dict]:
    """Format BH-rejected metrics for TUI / event payloads."""
    outliers: list[dict] = []
    for m in result.metric_results:
        if not m.bh_rejected:
            continue
        direction = "increased" if m.current_mean > m.baseline_mean else "decreased"
        outliers.append(
            {
                "metric": m.metric,
                "p_value": m.p_value,
                "bh_adjusted_p": m.bh_adjusted_p,
                "baseline_mean": m.baseline_mean,
                "current_value": m.current_mean,
                "direction": direction,
                "is_quality": m.is_quality,
                "is_length": m.is_length,
            }
        )
    return outliers
