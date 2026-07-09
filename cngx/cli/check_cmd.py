"""cngx check, policy validation for CI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console(stderr=True)
app = typer.Typer(
    help="Check one prompt/response against a behavior policy (message one, no baseline)"
)


def _load_policy(path: Path):
    from cngx.contracts import BehaviorContract

    if path.suffix in (".yaml", ".yml"):
        return BehaviorContract.from_yaml(path)
    return BehaviorContract.from_json(path)


def _load_text_file(path: Path) -> str:
    """Read text from a file path. Use '-' for stdin."""
    if str(path) == "-":
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def _resolve_prompt(
    prompt_arg: Optional[str], prompt_opt: Optional[str]
) -> tuple[Optional[str], Optional[int]]:
    text = prompt_arg or prompt_opt
    if not text or not text.strip():
        console.print("[red]Prompt is required (positional argument or --prompt)[/]")
        return None, 2
    return text, None


def _resolve_response_text(
    response: Optional[str],
    response_file: Optional[Path],
) -> tuple[Optional[str], Optional[int]]:
    if response is not None and response_file is not None:
        console.print("[red]Use only one of --response or --response-file[/]")
        return None, 2
    if response is not None:
        return response, None
    if response_file is not None:
        return _load_text_file(response_file), None
    console.print(
        "[red]Agent output required for offline check: "
        "use --response, --response-file, or pipe to --response-file -[/]"
    )
    return None, 2


def run_policy_check(
    policy: Path,
    prompt: Optional[str] = None,
    prompt_opt: Optional[str] = None,
    response: Optional[str] = None,
    response_file: Optional[Path] = None,
    reasoning_file: Optional[Path] = None,
    model: str = "mock-model",
    adapter: str = "mock",
    task_id: str = "policy_check",
    json_output: bool = False,
) -> int:
    """Route to offline or online policy check based on response inputs."""
    offline = response is not None or response_file is not None
    prompt_text, prompt_err = _resolve_prompt(prompt, prompt_opt)
    if prompt_err is not None:
        return prompt_err

    if offline:
        output_text, output_err = _resolve_response_text(response, response_file)
        if output_err is not None:
            return output_err
        reasoning_content = _load_text_file(reasoning_file) if reasoning_file else None
        offline_model = model if model != "mock-model" else "offline"
        return run_offline_check(
            prompt=prompt_text,
            output=output_text,
            policy=policy,
            model=offline_model,
            task_id=task_id,
            reasoning_content=reasoning_content,
            json_output=json_output,
        )

    return run_check(
        prompt_text,
        policy,
        model,
        adapter,
        task_id,
        json_output,
    )


def run_offline_check(
    prompt: str,
    output: str,
    policy: Path,
    model: str = "offline",
    task_id: str = "policy_check",
    reasoning_content: Optional[str] = None,
    json_output: bool = False,
) -> int:
    """Fingerprint and gate existing agent output. No LLM calls."""
    from cngx.capture.trace_builder import build_trace_from_text
    from cngx.contracts import DeploymentGate
    from cngx.fingerprint.extractor import FingerprintExtractor

    try:
        behavior_policy = _load_policy(policy)
    except Exception as e:
        console.print(f"[red]Could not load policy: {e}[/]")
        return 2

    trace = build_trace_from_text(
        prompt=prompt,
        output=output,
        task_id=task_id,
        model=model,
        reasoning_content=reasoning_content,
    )
    fp = FingerprintExtractor().extract(trace)

    gate = DeploymentGate()
    result = gate.check(fp, behavior_policy, trace)

    if json_output:
        out = result.to_ci_output()
        out["policy"] = out.pop("contract", behavior_policy.name)
        out["mode"] = "offline"
        print(json.dumps(out, indent=2, default=str))
    else:
        console.print(_format_policy_report(result))

    return result.exit_code


def run_check(
    prompt: str,
    policy: Path,
    model: str = "mock-model",
    adapter: str = "mock",
    task_id: str = "policy_check",
    json_output: bool = False,
) -> int:
    """Check prompt against policy. Returns exit code."""
    from cngx.capture.tracer import CngxTracer
    from cngx.contracts import DeploymentGate

    try:
        behavior_policy = _load_policy(policy)
    except Exception as e:
        console.print(f"[red]Could not load policy: {e}[/]")
        return 2

    tracer = CngxTracer(adapter=adapter, model=model)
    try:
        trace = tracer.capture(prompt=prompt, task_id=task_id, save=True)
        fp = tracer.get_fingerprint(trace.id)
    except Exception as e:
        console.print(f"[red]Capture failed: {e}[/]")
        return 2

    if not fp:
        console.print("[red]Fingerprint generation failed[/]")
        return 2

    gate = DeploymentGate()
    result = gate.check(fp, behavior_policy, trace)

    if json_output:
        out = result.to_ci_output()
        out["policy"] = out.pop("contract", behavior_policy.name)
        print(json.dumps(out, indent=2, default=str))
    else:
        console.print(_format_policy_report(result))

    return result.exit_code


def _format_policy_report(result) -> str:
    """User-facing report, always says policy, never gate/contract/compliance."""
    lines = [
        "=" * 60,
        "cngx policy check",
        "=" * 60,
        "",
        f"Policy: {result.contract_name} v{result.contract_version}",
        f"Hash: {result.contract_hash}",
        f"Model: {result.model}",
        f"Trace: {result.trace_id}",
        "",
    ]
    if result.blocked:
        lines.extend(
            [
                "STATUS: BLOCKED",
                "",
                f"Blocking issues: {result.block_count}",
                f"Other failures: {result.fail_count}",
                f"Warnings: {result.warn_count}",
                "",
            ]
        )
        for v in result.violations:
            if v.severity.value == "block":
                lines.append(f"  [BLOCK] {v.message}")
    elif not result.passed:
        lines.extend(
            [
                "STATUS: FAILED",
                "",
                f"Failures: {result.fail_count}",
                f"Warnings: {result.warn_count}",
                "",
            ]
        )
    else:
        lines.extend(["STATUS: PASSED", "", f"Warnings: {result.warn_count}", ""])

    if result.violations and (result.blocked or not result.passed):
        lines.append("Details:")
        for v in result.violations:
            lines.append(f"  [{v.severity.value}] {v.message}")

    lines.extend(["=" * 60, f"EXIT CODE: {result.exit_code}", "=" * 60])
    return "\n".join(lines)


@app.command()
def check(
    prompt: Optional[str] = typer.Argument(
        None,
        help="Prompt or task description (required for online capture)",
    ),
    policy: Path = typer.Option(..., "--policy", "-c", help="Policy YAML file"),
    prompt_opt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Prompt text when not passed as a positional argument",
    ),
    response: Optional[str] = typer.Option(
        None,
        "--response",
        "-r",
        help="Existing agent output to fingerprint and gate (offline, no LLM)",
    ),
    response_file: Optional[Path] = typer.Option(
        None,
        "--response-file",
        "-f",
        help="File with agent output; use - for stdin (offline, no LLM)",
    ),
    reasoning_file: Optional[Path] = typer.Option(
        None,
        "--reasoning-file",
        help="Optional chain-of-thought file for offline check",
    ),
    model: str = typer.Option("mock-model", "--model", "-m"),
    adapter: str = typer.Option("mock", "--adapter", "-a", help="mock, openai, gemini, claude"),
    task_id: str = typer.Option("policy_check", "--task", "-t"),
    json_output: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Check agent output against a behavior policy.

    Online (default): capture a new model response, then gate it.
    Offline: pass --response or --response-file to gate existing output with zero provider calls.

    Exit codes: 0 pass, 1 blocked, 2 failed (soft violations or input errors).
    """
    raise typer.Exit(
        run_policy_check(
            policy=policy,
            prompt=prompt,
            prompt_opt=prompt_opt,
            response=response,
            response_file=response_file,
            reasoning_file=reasoning_file,
            model=model,
            adapter=adapter,
            task_id=task_id,
            json_output=json_output,
        )
    )


if __name__ == "__main__":
    app()
