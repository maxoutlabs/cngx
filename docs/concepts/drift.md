# Drift Detection

Drift detection answers: **"Is this response unusually different from behavior I've already pinned as normal?"**

It does **not** answer: "Is this model worse than last month industry-wide?" or "Is GPT better than Claude?"

Cogscope uses **different statistical methods for different situations**. They are not blended into one mechanism.

## Pin a baseline first

```bash
cogscope watch          # capture traffic via proxy
cogscope pin --label my-baseline
```

A baseline stores a reference fingerprint for a task/model pair in `.cogscope/cogscope.db`.

## Compare live traffic

```bash
cogscope diff --baseline my-baseline
```

Or watch the live TUI during `cogscope watch`, drift scores appear when a baseline is pinned.

## Live proxy path (streaming, no ground truth)

**Algorithms:** [ADWIN](https://doi.org/10.1137/1.9781611972771.63) and Page-Hinkley (Page, 1954) via the [frouros](https://github.com/IFCA/frouros) library (BSD-3-Clause).

- One streaming detector per **(model, pinned baseline, metric)** for core fingerprint metrics (depth, verification steps, hedging ratio, corrections, branching factor, etc.).
- Each new proxied call updates its metric streams in **background analysis**, the streamed response is not blocked.
- A per-metric drift flag comes from the formal streaming test, not an arbitrary z-score cutoff.
- **User-facing alerts** still require corroboration: at least two metric streams must flag drift, including at least one *quality* metric. Length-only shifts never alert alone.

Implementation: `cogscope/drift/streaming.py`, wired from `cogscope/proxy/analysis.py`.

## One-shot diff / check path (batch comparison)

**Procedure** (`cogscope/drift/batch.py`):

1. Per-metric **Mann-Whitney U** test (non-parametric two-sample comparison).
2. **Benjamini-Hochberg** false discovery rate correction across simultaneous tests (Benjamini & Hochberg, 1995).
3. **Fisher's method** combining p-values of BH-rejected metrics into one omnibus statistic (Fisher, 1925).

This replaces the previous hand-rolled "at least two raw p-values" rule with a named, FDR-controlled procedure.

Used by `cogscope diff`, `cogscope drift detect`, and population comparisons in `DriftDetector`.

## CI regression path (paired benchmarks with oracle)

**Algorithm:** **McNemar's test** (McNemar, 1947) on paired binary correct/incorrect outcomes.

- Applies when the **same fixed benchmark items** are run against a baseline and a current model, and a correctness oracle exists (policy YAML, expected substrings, etc.).
- **Not** used on live open traffic, McNemar requires paired binary labels on identical items, which streaming proxy traffic without ground truth does not provide.

```bash
cogscope regression --suite benchmarks.yaml --policy policy.yaml \
  --baseline-outcomes baseline_correct.json
```

Implementation: `cogscope/drift/paired.py`.

## Optional semantic drift signal

Heuristic regex metrics cannot detect all semantic shifts. For users who want a local, zero-API signal:

```bash
pip install cogscope[semantic]
cogscope watch --semantic
```

- Embeds response text with **sentence-transformers** `all-MiniLM-L6-v2` (~80MB, CPU, downloaded once).
- Compares baseline vs current embedding distributions via **Jensen-Shannon divergence** on a reduced projection.
- **Strictly opt-in**, default `pip install cogscope` and `quickstart` are unchanged.

Implementation: `cogscope/drift/semantic.py`.

## When alerts fire (summary)

| Scenario | Method | Alerts? |
|----------|--------|---------|
| Shorter answer, quality metrics stable | Streaming ADWIN/Page-Hinkley | No |
| Verification + depth drop together vs baseline | Streaming corroboration | Yes |
| Population window shift (diff) | Mann-Whitney + BH + Fisher | Yes if omnibus significant |
| Fixed benchmark regression | McNemar paired test | Yes if paired degradation |
| Single metric wiggles | Any path | No (by design) |

## Drift score

The `drift_score` (0 to 1) from `DiffEngine` is a weighted summary of metric deltas, useful for ranking, not as a standalone alarm. Formal tests gate alerts.

## Reports

```bash
cogscope report              # terminal summary, last 24 hours
cogscope report -o report.html   # HTML export
```

## Public tracker

Opt-in anonymous submissions feed the [Public Drift Log](../guides/public-drift-log.md). Your local prompts never leave your machine unless you run `cogscope submit` and confirm.

## Related

- [Fingerprinting](fingerprinting.md)
- [FAQ](../faq.md), gaming and pseudo-science objections
