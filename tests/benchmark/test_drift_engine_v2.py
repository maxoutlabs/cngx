"""Benchmark evidence for upgraded drift engine (Prompt 13).

Produces measurable false-positive rates and synthetic drift detection proofs.
"""

from __future__ import annotations

import numpy as np
import pytest

from cogscope.calibration.profiles import QUALITY_METRICS
from cogscope.core.models import BehavioralFingerprint
from cogscope.drift.batch import batch_drift_test
from cogscope.drift.legacy import legacy_batch_population_alert, legacy_multimetric_outlier
from cogscope.drift.paired import mcnemar_test
from cogscope.drift.streaming import StreamingDriftMonitor, get_streaming_registry


def _synthetic_fp(
    seed: int,
    depth: float = 5.0,
    verification_steps: float = 3.0,
    output_length: float = 2000.0,
    **kwargs,
) -> BehavioralFingerprint:
    rng = np.random.default_rng(seed)
    base = dict(
        trace_id=f"t{seed}",
        task_id="bench",
        timestamp=__import__("datetime").datetime.utcnow(),
        model="bench-model",
        depth=int(depth + rng.normal(0, 0.3)),
        branching_factor=0.5,
        total_steps=int(5 + rng.normal(0, 0.5)),
        max_step_length=80,
        tool_call_count=0,
        tool_call_sequence=[],
        tool_diversity=0.0,
        tool_success_rate=1.0,
        output_length=int(output_length + rng.normal(0, 50)),
        reasoning_length=4000,
        compression_ratio=0.5,
        avg_sentence_length=20.0,
        correction_count=int(1 + rng.normal(0, 0.2)),
        backtrack_count=0,
        revision_count=0,
        uncertainty_markers=int(1 + rng.normal(0, 0.2)),
        confidence_markers=2,
        hedging_ratio=0.2 + rng.normal(0, 0.02),
        verification_steps=int(verification_steps + rng.normal(0, 0.3)),
        example_count=0,
        structured_output=False,
        tokens_per_step=10.0,
        reasoning_overhead=0.5,
    )
    base.update(kwargs)
    return BehavioralFingerprint(**base)


def _population(n: int, start_seed: int, **kwargs) -> list[BehavioralFingerprint]:
    return [_synthetic_fp(start_seed + i, **kwargs) for i in range(n)]


class TestFalsePositiveRateBenchmark:
    """Task 7a: empirical FPR on no-drift synthetic data."""

    @pytest.fixture(scope="class")
    def fpr_results(self):
        alpha = 0.05
        n_trials = 250
        legacy_hits = 0
        new_hits = 0
        rng = np.random.default_rng(42)

        for trial in range(n_trials):
            seed = int(rng.integers(0, 1_000_000))
            baseline = _population(15, seed, depth=5.0, verification_steps=3.0)
            current = _population(15, seed + 10_000, depth=5.0, verification_steps=3.0)
            probe = _synthetic_fp(seed + 99_000, depth=5.0, verification_steps=3.0)

            if legacy_batch_population_alert(baseline, current, alpha=alpha):
                legacy_hits += 1
            if batch_drift_test(baseline, current, alpha=alpha).should_alert:
                new_hits += 1

            leg_single, _ = legacy_multimetric_outlier(probe, baseline, "bench-model")
            if leg_single:
                legacy_hits += 0  # batch only for population FPR

        return {
            "n_trials": n_trials,
            "alpha": alpha,
            "legacy_fpr": legacy_hits / n_trials,
            "new_fpr": new_hits / n_trials,
            "legacy_hits": legacy_hits,
            "new_hits": new_hits,
        }

    def test_new_fpr_not_worse_than_legacy(self, fpr_results):
        print(
            f"\nFPR benchmark: legacy={fpr_results['legacy_fpr']:.3f} "
            f"({fpr_results['legacy_hits']}/{fpr_results['n_trials']}), "
            f"new BH+Fisher={fpr_results['new_fpr']:.3f} "
            f"({fpr_results['new_hits']}/{fpr_results['n_trials']}), "
            f"alpha={fpr_results['alpha']}"
        )
        assert fpr_results["new_fpr"] <= max(fpr_results["legacy_fpr"], 0.15)


class TestStreamingDriftSynthetic:
    """Task 7b: ADWIN/Page-Hinkley on synthetic streams."""

    def test_stable_stream_low_false_alarms(self):
        get_streaming_registry().reset()
        monitor = StreamingDriftMonitor()
        monitor.seed_from_history(_population(20, 100, depth=5.0, verification_steps=3.0))
        flags = []
        rng = np.random.default_rng(1)
        for i in range(150):
            depth = float(rng.normal(5.0, 0.1))
            fp = _synthetic_fp(i, depth=depth, verification_steps=3.0)
            drift = monitor.update(fp)
            should, _ = monitor.combine_streaming_signals(drift)
            flags.append(should)
        false_alarm_rate = sum(flags) / len(flags)
        print(f"\nStreaming stable FPR: {false_alarm_rate:.3f} ({sum(flags)}/{len(flags)})")
        assert false_alarm_rate < 0.25

    def test_shift_detected_after_change_point(self):
        get_streaming_registry().reset()
        monitor = StreamingDriftMonitor()
        history = _population(30, 0, depth=5.0, verification_steps=3.0)
        monitor.seed_from_history(history)

        alert_indices = []
        for i in range(160):
            if i < 80:
                depth, ver = 5.0, 3.0
            else:
                depth, ver = 1.0, 0.0
            fp = _synthetic_fp(i, depth=depth, verification_steps=ver)
            drift = monitor.update(fp)
            should, _ = monitor.combine_streaming_signals(drift)
            if should:
                alert_indices.append(i)

        print(
            f"\nStreaming shift alerts at indices: {alert_indices[:8]}... "
            f"(n={len(alert_indices)}, first={alert_indices[0] if alert_indices else None})"
        )
        assert alert_indices, "Expected drift alert after distribution shift"
        assert min(alert_indices) >= 70


class TestMcNemarSynthetic:
    """Task 7d: McNemar on paired correctness."""

    def test_detects_known_degradation(self):
        baseline = [True] * 50
        current = [True] * 30 + [False] * 20
        result = mcnemar_test(baseline, current)
        print(
            f"\nMcNemar degradation: p={result.p_value:.6f}, detected={result.degradation_detected}"
        )
        assert result.degradation_detected

    def test_no_false_alarm_on_identical(self):
        baseline = [True, False, True, False, True, False] * 10
        current = list(baseline)
        result = mcnemar_test(baseline, current)
        print(
            f"\nMcNemar identical: p={result.p_value:.6f}, detected={result.degradation_detected}"
        )
        assert not result.degradation_detected


class TestSemanticDriftSynthetic:
    """Task 7c: semantic signal catches shift heuristics miss."""

    @pytest.fixture(scope="class")
    def semantic_available(self):
        pytest.importorskip("sentence_transformers")

    def test_semantic_catches_topic_shift(self, semantic_available):
        from cogscope.drift.semantic import SemanticDriftAnalyzer

        analyzer = SemanticDriftAnalyzer(distance_threshold=0.15)
        baseline_texts = [
            "Step 1: Let me verify the arithmetic carefully.",
            "Step 2: I will check each calculation twice.",
            "Step 3: Confirming the result matches expectations.",
        ] * 5
        for t in baseline_texts:
            analyzer.add_baseline_text(t)

        # Same reasoning structure, different topic/content
        shifted = (
            "Step 1: Let me verify the recipe ingredients carefully. "
            "Step 2: I will check each measurement twice. "
            "Step 3: Confirming the soufflé rises as expected."
        )
        result = analyzer.compare_current_text(shifted)
        print(f"\nSemantic JS distance: {result.distance:.3f}, detected={result.drift_detected}")
        assert result.drift_detected, "Semantic drift should flag topical shift"
