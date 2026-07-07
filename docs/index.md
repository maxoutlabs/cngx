# Cogscope

**Your LLM can still look fine on output-only metrics while the reasoning underneath gets shallower.**

**Cogscope fingerprints how it reasons, compares that to behavior you pinned as normal, and catches silent regression locally — no API keys, no cloud.**

## What it does

1. **Capture** — Intercept LLM traffic through a local proxy (or direct adapter calls).
2. **Fingerprint** — Extract numeric behavioral metrics from each response (depth, verification steps, hedging, and more).
3. **Pin** — Save a baseline fingerprint for a task/model pair.
4. **Diff** — Compare new traffic against that baseline; alert only on corroborated statistical outliers.
5. **Check** — Validate a single prompt against a YAML policy in CI.

Nothing requires a cloud account. Data stays on your machine unless you explicitly run `cogscope submit`.

## Quick start

```bash
pip install cogscope
cogscope quickstart
```

`quickstart` runs in under a minute with **no API keys** and demonstrates catching shallow reasoning that still produces a plausible answer.

![Cogscope quickstart demo](assets/quickstart.svg)

## How it differs from other tooling

| | Output-quality eval tools | Telemetry / observability tools | Cogscope |
|---|---------------------------|----------------------------------|----------|
| **Measures** | Final answers and rubric scores on fixed prompts | Latency, tokens, traces, costs in production | Reasoning-shape metrics on your traffic |
| **Baseline** | Global benchmarks | Fleet aggregates | *Your* pinned fingerprint |
| **Misses** | Shallow reasoning when answers still read well | Drift from behavior you previously accepted | Semantic ground truth about reasoning |

See the [FAQ](faq.md) for skeptical questions answered honestly.

## Documentation map

| Section | What you'll learn |
|---------|-------------------|
| [Installation](getting-started/installation.md) | Install from PyPI or source |
| [Quickstart](getting-started/quickstart.md) | First run with zero configuration |
| [Fingerprinting](concepts/fingerprinting.md) | What metrics mean (and what they don't) |
| [Writing a Policy](concepts/policies.md) | YAML policy schema and severity levels |
| [Drift Detection](concepts/drift.md) | When alerts fire — and when they don't |
| [CLI Reference](cli/reference.md) | Every command with verified examples |
| [Proxy & Privacy](guides/proxy-and-privacy.md) | What leaves your machine (nothing by default) |
| [Public Drift Log](guides/public-drift-log.md) | Community tracker and `cogscope submit` |
| [FAQ](faq.md) | Honest answers to skeptical questions |
| [Roadmap](roadmap.md) | What's in v0.1.0 and what's deferred |

## License

MIT — see [LICENSE](https://github.com/aadi-joshi/cogscope/blob/main/LICENSE) in the repository.
