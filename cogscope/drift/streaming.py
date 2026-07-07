"""Streaming concept-drift detection for live proxy traffic.

Uses frouros (BSD-3-Clause) ADWIN per metric stream on non-negative behavioral
values. Page-Hinkley (Page, 1954) is implemented in-house in
``page_hinkley_two_sided`` because frouros PageHinkley targets 0-1 error-rate
streams and did not reliably flag integer metric shifts in our evaluation.

Each metric stream is independent; user-facing alerts require corroboration
across multiple metrics (see combine_streaming_signals). Gradual drift is
detected as ADWIN/Page-Hinkley state accumulates across proxied calls.
Immediate snapshot comparison on a single call uses the batch path in
``assess_against_pinned_baseline`` (see batch.py).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from frouros.detectors.concept_drift.streaming import ADWIN, ADWINConfig

from cogscope.calibration.profiles import LENGTH_METRICS, QUALITY_METRICS
from cogscope.core.models import BehavioralFingerprint

STREAMING_METRICS: tuple[str, ...] = (
    "depth",
    "total_steps",
    "verification_steps",
    "hedging_ratio",
    "correction_count",
    "branching_factor",
    "uncertainty_markers",
)


class PageHinkleyTwoSided:
    """Classic Page (1954) two-sided CUSUM for mean shifts up or down."""

    def __init__(self, delta: float = 0.005, lambda_: float = 8.0) -> None:
        self.delta = delta
        self.lambda_ = lambda_
        self.n = 0
        self.mean = 0.0
        self.ph_up_sum = 0.0
        self.ph_up_min = 0.0
        self.ph_down_sum = 0.0
        self.ph_down_max = 0.0

    def update(self, x: float) -> bool:
        self.n += 1
        self.mean += (x - self.mean) / self.n
        self.ph_up_sum += x - self.mean - self.delta
        self.ph_up_min = min(self.ph_up_min, self.ph_up_sum)
        up = (self.ph_up_sum - self.ph_up_min) > self.lambda_
        self.ph_down_sum += self.mean - x - self.delta
        self.ph_down_max = max(self.ph_down_max, self.ph_down_sum)
        down = (self.ph_down_sum - self.ph_down_max) > self.lambda_
        return up or down


@dataclass
class StreamingMetricState:
    """ADWIN + in-house Page-Hinkley for one metric stream."""

    adwin: ADWIN = field(
        default_factory=lambda: ADWIN(config=ADWINConfig(min_num_instances=8, delta=0.002))
    )
    page_hinkley: PageHinkleyTwoSided = field(default_factory=PageHinkleyTwoSided)
    last_drift: bool = False
    updates: int = 0

    def seed(self, values: list[float]) -> None:
        for v in values:
            self._update_internal(float(v), track_drift=False)

    def update(self, value: float) -> bool:
        return self._update_internal(float(value), track_drift=True)

    def _update_internal(self, value: float, track_drift: bool) -> bool:
        self.adwin.update(value=value)
        ph_drift = self.page_hinkley.update(value)
        self.updates += 1
        drift = bool(self.adwin.drift or ph_drift)
        if track_drift:
            self.last_drift = drift
        return drift if track_drift else False


@dataclass
class StreamingKey:
    model: str
    baseline_name: str

    def as_tuple(self) -> tuple[str, str]:
        return (self.model, self.baseline_name)


class StreamingDriftMonitor:
    """One monitor per (model, pinned baseline) with per-metric detectors."""

    def __init__(
        self,
        min_drift_metrics: int = 2,
        require_quality_metric: bool = True,
    ):
        self.min_drift_metrics = min_drift_metrics
        self.require_quality_metric = require_quality_metric
        self._metrics: dict[str, StreamingMetricState] = {
            m: StreamingMetricState() for m in STREAMING_METRICS
        }
        self._seeded = False

    def seed_from_history(self, fingerprints: list[BehavioralFingerprint]) -> None:
        """Initialize streams from baseline-era fingerprints."""
        for metric in STREAMING_METRICS:
            values = [float(getattr(fp, metric)) for fp in fingerprints]
            if values:
                self._metrics[metric].seed(values)
        self._seeded = True

    def update(self, fingerprint: BehavioralFingerprint) -> dict[str, bool]:
        """Update all metric streams; return per-metric drift flags this step."""
        flags: dict[str, bool] = {}
        for metric in STREAMING_METRICS:
            value = float(getattr(fingerprint, metric))
            flags[metric] = self._metrics[metric].update(value)
        return flags

    def combine_streaming_signals(
        self,
        drift_flags: dict[str, bool],
    ) -> tuple[bool, list[dict]]:
        """Corroboration: >=2 metrics with ADWIN/PH drift, >=1 quality, not length-only."""
        drifted = [
            m for m in STREAMING_METRICS if drift_flags.get(m) or self._metrics[m].last_drift
        ]
        if len(drifted) < self.min_drift_metrics:
            return False, []

        quality_drifted = [m for m in drifted if m in QUALITY_METRICS]
        length_only = all(m in LENGTH_METRICS for m in drifted)

        should_alert = not length_only and (
            not self.require_quality_metric or len(quality_drifted) >= 1
        )

        details = [
            {
                "metric": m,
                "streaming_drift": True,
                "is_quality": m in QUALITY_METRICS,
                "is_length": m in LENGTH_METRICS,
                "direction": "shift detected",
            }
            for m in drifted
        ]
        return should_alert, details


class StreamingDriftRegistry:
    """Process-wide registry of streaming monitors keyed by model + baseline."""

    def __init__(self) -> None:
        self._monitors: dict[tuple[str, str], StreamingDriftMonitor] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        model: str,
        baseline_name: str,
    ) -> StreamingDriftMonitor:
        key = (model, baseline_name)
        with self._lock:
            if key not in self._monitors:
                self._monitors[key] = StreamingDriftMonitor()
            return self._monitors[key]

    def reset(self, model: Optional[str] = None, baseline_name: Optional[str] = None) -> None:
        with self._lock:
            if model is None and baseline_name is None:
                self._monitors.clear()
                return
            keys = [
                k
                for k in self._monitors
                if (model is None or k[0] == model)
                and (baseline_name is None or k[1] == baseline_name)
            ]
            for k in keys:
                del self._monitors[k]


_registry: Optional[StreamingDriftRegistry] = None


def get_streaming_registry() -> StreamingDriftRegistry:
    global _registry
    if _registry is None:
        _registry = StreamingDriftRegistry()
    return _registry
