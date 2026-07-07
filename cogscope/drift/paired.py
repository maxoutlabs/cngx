"""Paired significance testing for fixed-benchmark CI regression.

McNemar's test (McNemar, 1947) compares paired binary outcomes (correct vs
incorrect) on the *same* test items under two conditions (baseline model run
vs current model run).

Why here and not on live proxy traffic:
- McNemar requires paired binary labels on identical items across conditions.
- Live open-ended proxy traffic has no ground-truth correctness oracle per call.
- CI regression suites with policy-defined expected answers *do* provide paired
  binary outcomes, which is the setting McNemar is designed for.

Used in recent LLM degradation detection research when benchmark items are fixed
and correctness can be scored; applied only through explicit regression-check paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import stats


@dataclass
class McNemarResult:
    """Result of McNemar's test on paired binary outcomes."""

    statistic: float
    p_value: float
    n_discordant: int
    b_baseline_wrong_current_right: int
    c_baseline_right_current_wrong: int
    degradation_detected: bool
    alpha: float
    summary: str


def mcnemar_test(
    baseline_correct: Sequence[bool],
    current_correct: Sequence[bool],
    alpha: float = 0.05,
    *,
    degradation_direction: str = "current_worse",
) -> McNemarResult:
    """McNemar's test for paired binary correctness vectors.

    Args:
        baseline_correct: Whether baseline run was correct per item.
        current_correct: Whether current run was correct per item (same order).
        alpha: Significance level.
        degradation_direction: ``current_worse`` flags when current fails more
            often on items baseline passed (c > b). Use ``either`` for any change.

    Returns:
        McNemarResult with test statistic and degradation flag.
    """
    if len(baseline_correct) != len(current_correct):
        raise ValueError("baseline_correct and current_correct must have same length")
    if len(baseline_correct) < 2:
        return McNemarResult(
            statistic=0.0,
            p_value=1.0,
            n_discordant=0,
            b_baseline_wrong_current_right=0,
            c_baseline_right_current_wrong=0,
            degradation_detected=False,
            alpha=alpha,
            summary="Insufficient paired items for McNemar test (need >=2).",
        )

    b = 0  # baseline wrong, current right
    c = 0  # baseline right, current wrong
    for bl, cl in zip(baseline_correct, current_correct):
        if not bl and cl:
            b += 1
        elif bl and not cl:
            c += 1

    n_discordant = b + c
    if n_discordant == 0:
        return McNemarResult(
            statistic=0.0,
            p_value=1.0,
            n_discordant=0,
            b_baseline_wrong_current_right=b,
            c_baseline_right_current_wrong=c,
            degradation_detected=False,
            alpha=alpha,
            summary="No discordant pairs; no paired degradation signal.",
        )

    # Exact binomial test on discordant pairs (McNemar)
    if n_discordant < 25:
        p_value = float(stats.binomtest(c, n=n_discordant, p=0.5).pvalue)
        stat = float((abs(c - b) - 1) ** 2 / (b + c)) if (b + c) else 0.0
    else:
        # Chi-square approximation with continuity correction
        stat = float((abs(c - b) - 1) ** 2 / (b + c))
        p_value = float(stats.chi2.sf(stat, df=1))

    if degradation_direction == "current_worse":
        degradation = c > b and p_value < alpha
    else:
        degradation = p_value < alpha

    summary = (
        f"McNemar: discordant b={b}, c={c}, p={p_value:.4f}"
        + (", paired degradation detected." if degradation else ".")
    )

    return McNemarResult(
        statistic=stat,
        p_value=p_value,
        n_discordant=n_discordant,
        b_baseline_wrong_current_right=b,
        c_baseline_right_current_wrong=c,
        degradation_detected=degradation,
        alpha=alpha,
        summary=summary,
    )


def evaluate_item_correctness(
    output: str,
    *,
    expected_substrings: Sequence[str] | None = None,
    forbidden_substrings: Sequence[str] | None = None,
    policy_passed: bool | None = None,
) -> bool:
    """Score one benchmark item as correct/incorrect for McNemar pairing.

    Priority: explicit policy_passed if given, else substring oracle hooks.
    """
    if policy_passed is not None:
        return bool(policy_passed)

    text = output or ""
    if expected_substrings:
        if not all(s in text for s in expected_substrings):
            return False
    if forbidden_substrings:
        if any(s in text for s in forbidden_substrings):
            return False
    return True if (expected_substrings or forbidden_substrings) else False
