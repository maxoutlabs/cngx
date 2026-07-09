"""End-to-end offline agent gate (no API keys, no network)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cngx.cli.main import app

runner = CliRunner()

ROOT = Path(__file__).resolve().parents[2]
STRICT_POLICY = ROOT / "examples/contracts/coding_agent_verification.yaml"
VERIFIED = ROOT / "tests/fixtures/agent_outputs/verified_fix.txt"
UNVERIFIED = ROOT / "tests/fixtures/agent_outputs/unverified_patch.txt"


@pytest.fixture
def project_dir(tmp_path):
    """Initialized cngx project in a temp directory."""
    prev = os.getcwd()
    os.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    yield tmp_path
    os.chdir(prev)


class TestOfflineAgentGate:
    def test_fixtures_exist(self):
        assert STRICT_POLICY.is_file()
        assert VERIFIED.is_file()
        assert UNVERIFIED.is_file()

    def test_unverified_output_blocked(self, project_dir):
        del project_dir  # init only; policies and fixtures are repo-relative
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(STRICT_POLICY),
                "-p",
                "Fix the pagination bug and run tests before merge",
                "--output-file",
                str(UNVERIFIED),
            ],
        )
        assert result.exit_code == 1
        assert "BLOCKED" in result.stdout or "BLOCKED" in result.stderr

    def test_verified_output_passes(self, project_dir):
        del project_dir
        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(STRICT_POLICY),
                "-p",
                "Fix the pagination bug and run tests before merge",
                "--output-file",
                str(VERIFIED),
            ],
        )
        assert result.exit_code == 0
        assert "PASSED" in result.stdout or "PASSED" in result.stderr

    def test_offline_gate_does_not_use_adapter(self, project_dir, monkeypatch):
        del project_dir

        def fail_capture(*_args, **_kwargs):
            raise AssertionError("CngxTracer.capture should not run in offline mode")

        monkeypatch.setattr("cngx.capture.tracer.CngxTracer.capture", fail_capture)

        result = runner.invoke(
            app,
            [
                "check",
                "-c",
                str(STRICT_POLICY),
                "-p",
                "Fix bug",
                "--output-file",
                str(UNVERIFIED),
            ],
        )
        assert result.exit_code == 1
