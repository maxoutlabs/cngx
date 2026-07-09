"""CLI tests for cngx check offline mode."""

from pathlib import Path

from typer.testing import CliRunner

from cngx.cli.main import app
from cngx.system_demo.scenarios import CodingAgentFixScenario

runner = CliRunner()

SHALLOW_OUTPUT = (
    "Patch: use items[(page - 1) * size : page * size] for 1-based pages. " "Ready to merge."
)


def _write_policy(tmp_path: Path) -> Path:
    contract = CodingAgentFixScenario.get_scenario().contract
    policy = tmp_path / "coding_agent.yaml"
    policy.write_text(contract.to_yaml(), encoding="utf-8")
    return policy


class TestCheckOfflineCli:
    def test_response_flag_blocks_shallow_patch(self, tmp_path):
        policy = _write_policy(tmp_path)
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(policy),
                "-p",
                "Fix pagination bug",
                "-r",
                SHALLOW_OUTPUT,
            ],
        )
        assert result.exit_code == 1
        assert "BLOCKED" in result.stdout or "BLOCKED" in result.stderr

    def test_response_file_blocks_shallow_patch(self, tmp_path):
        policy = _write_policy(tmp_path)
        output_file = tmp_path / "agent.txt"
        output_file.write_text(SHALLOW_OUTPUT, encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(policy),
                "-p",
                "Fix pagination bug",
                "-f",
                str(output_file),
            ],
        )
        assert result.exit_code == 1

    def test_stdin_response_file_blocks(self, tmp_path):
        policy = _write_policy(tmp_path)
        result = runner.invoke(
            app,
            ["check", "-c", str(policy), "-p", "Fix bug", "-f", "-"],
            input=SHALLOW_OUTPUT,
        )
        assert result.exit_code == 1

    def test_online_mode_still_works(self, tmp_path):
        policy = tmp_path / "basic.yaml"
        policy.write_text(
            (
                Path(__file__).resolve().parents[2] / "examples/contracts/basic_reasoning.yaml"
            ).read_text(),
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(policy),
                "Step 1: think. Step 2: answer 4. Verified.",
                "--adapter",
                "mock",
            ],
        )
        assert result.exit_code in (0, 2)

    def test_missing_prompt_errors(self, tmp_path):
        policy = _write_policy(tmp_path)
        result = runner.invoke(
            app,
            ["check", "-c", str(policy), "-r", SHALLOW_OUTPUT],
        )
        assert result.exit_code == 2

    def test_both_response_flags_errors(self, tmp_path):
        policy = _write_policy(tmp_path)
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(policy),
                "-p",
                "Fix",
                "-r",
                "out",
                "-f",
                "also",
            ],
        )
        assert result.exit_code == 2

    def test_json_offline_includes_mode(self, tmp_path):
        policy = _write_policy(tmp_path)
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(policy),
                "-p",
                "Fix",
                "-r",
                SHALLOW_OUTPUT,
                "--json",
            ],
        )
        assert result.exit_code == 1
        import json

        data = json.loads(result.stdout)
        assert data["mode"] == "offline"
