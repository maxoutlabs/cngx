"""Auto-detection of the project test command for a zero-arg `cngx verify`.

Every case builds a throwaway project in a temp dir and asserts which command comes back. No
toolchain is ever invoked: `shutil.which` is stubbed so the results do not depend on whether
node, go, cargo or make happen to be installed on the machine running the suite.
"""

import shutil
import sys

import pytest

from cngx.cli.verify_cmd import _autodetect_command


@pytest.fixture
def toolchains(monkeypatch):
    """Control which executables auto-detection believes are installed."""

    available: set[str] = set()

    def fake_which(name, *args, **kwargs):
        return f"/usr/bin/{name}" if name in available else None

    monkeypatch.setattr(shutil, "which", fake_which)
    return available


@pytest.fixture
def no_pytest(monkeypatch):
    """Hide pytest so the fallback branch does not mask the ecosystem under test.

    The suite itself runs under pytest, so without this every temp dir containing a `tests/`
    directory would resolve to the pytest branch.
    """
    import importlib.util

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name, *args, **kwargs):
        return None if name == "pytest" else real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def write(path, name, content=""):
    (path / name).write_text(content, encoding="utf-8")


PACKAGE_WITH_TEST = '{"scripts": {"test": "jest"}}'


class TestNode:
    def test_package_json_with_test_script_uses_npm(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", PACKAGE_WITH_TEST)
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) == ["npm", "test", "--silent"]

    def test_pnpm_lockfile_selects_pnpm(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", PACKAGE_WITH_TEST)
        write(tmp_path, "pnpm-lock.yaml")
        toolchains.update({"npm", "pnpm"})
        assert _autodetect_command(tmp_path) == ["pnpm", "test"]

    def test_yarn_lockfile_selects_yarn(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", PACKAGE_WITH_TEST)
        write(tmp_path, "yarn.lock")
        toolchains.update({"npm", "yarn"})
        assert _autodetect_command(tmp_path) == ["yarn", "test"]

    def test_package_lock_still_uses_npm(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", PACKAGE_WITH_TEST)
        write(tmp_path, "package-lock.json")
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) == ["npm", "test", "--silent"]

    def test_npm_placeholder_script_is_not_detected(self, tmp_path, toolchains, no_pytest):
        # What `npm init -y` writes. It exits 1 by design, so detecting it would block every
        # verify in a repo that never set tests up.
        write(
            tmp_path,
            "package.json",
            '{"scripts": {"test": "echo \\"Error: no test specified\\" && exit 1"}}',
        )
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) is None

    def test_no_test_script_is_not_detected(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", '{"scripts": {"build": "tsc"}}')
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) is None

    def test_empty_test_script_is_not_detected(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", '{"scripts": {"test": "   "}}')
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) is None

    def test_malformed_package_json_is_not_detected(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", "{ this is not json")
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) is None

    def test_package_json_holding_a_list_is_not_detected(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", "[]")
        toolchains.add("npm")
        assert _autodetect_command(tmp_path) is None

    def test_missing_npm_falls_through(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", PACKAGE_WITH_TEST)
        # npm not in `toolchains`
        assert _autodetect_command(tmp_path) is None


class TestGo:
    def test_go_mod_detects_go_test(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "go.mod", "module example.com/demo\n")
        toolchains.add("go")
        assert _autodetect_command(tmp_path) == ["go", "test", "./..."]

    def test_missing_go_toolchain_falls_through(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "go.mod", "module example.com/demo\n")
        assert _autodetect_command(tmp_path) is None


class TestCargo:
    def test_cargo_toml_detects_cargo_test(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\n')
        toolchains.add("cargo")
        assert _autodetect_command(tmp_path) == ["cargo", "test"]

    def test_missing_cargo_toolchain_falls_through(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\n')
        assert _autodetect_command(tmp_path) is None


class TestMake:
    def test_makefile_with_test_target(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "build:\n\techo building\n\ntest:\n\techo testing\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) == ["make", "test"]

    def test_lowercase_makefile_is_honoured(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "makefile", "test:\n\techo testing\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) == ["make", "test"]

    def test_double_colon_target_is_honoured(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "test::\n\techo testing\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) == ["make", "test"]

    def test_target_with_prerequisites_is_honoured(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "test: build lint\n\techo testing\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) == ["make", "test"]

    def test_phony_declaration_alone_is_not_a_target(self, tmp_path, toolchains, no_pytest):
        # `.PHONY: test` names the target without defining it.
        write(tmp_path, "Makefile", ".PHONY: test\n\nbuild:\n\techo building\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) is None

    def test_variable_assignment_is_not_a_target(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "test := pytest -q\n\nbuild:\n\techo building\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) is None

    def test_simply_expanded_assignment_is_not_a_target(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "test ::= pytest -q\n\nbuild:\n\techo building\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) is None

    def test_makefile_without_a_test_target(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "build:\n\techo building\n")
        toolchains.add("make")
        assert _autodetect_command(tmp_path) is None

    def test_missing_make_toolchain_falls_through(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Makefile", "test:\n\techo testing\n")
        assert _autodetect_command(tmp_path) is None


class TestPytest:
    def test_tests_directory_detects_pytest(self, tmp_path, toolchains):
        (tmp_path / "tests").mkdir()
        assert _autodetect_command(tmp_path) == [sys.executable, "-m", "pytest", "-q"]

    def test_test_prefixed_file_detects_pytest(self, tmp_path, toolchains):
        write(tmp_path, "test_thing.py", "def test_ok():\n    assert True\n")
        assert _autodetect_command(tmp_path) == [sys.executable, "-m", "pytest", "-q"]

    def test_test_suffixed_file_detects_pytest(self, tmp_path, toolchains):
        write(tmp_path, "thing_test.py", "def test_ok():\n    assert True\n")
        assert _autodetect_command(tmp_path) == [sys.executable, "-m", "pytest", "-q"]

    def test_python_project_without_tests_is_not_detected(self, tmp_path, toolchains):
        write(tmp_path, "main.py", "print('hi')\n")
        assert _autodetect_command(tmp_path) is None

    def test_pytest_not_installed_falls_through(self, tmp_path, toolchains, no_pytest):
        (tmp_path / "tests").mkdir()
        assert _autodetect_command(tmp_path) is None


class TestPrecedence:
    """First match wins, in the order node, go, cargo, make, pytest."""

    def test_node_beats_go(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "package.json", PACKAGE_WITH_TEST)
        write(tmp_path, "go.mod", "module example.com/demo\n")
        toolchains.update({"npm", "go"})
        assert _autodetect_command(tmp_path) == ["npm", "test", "--silent"]

    def test_go_beats_cargo(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "go.mod", "module example.com/demo\n")
        write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\n')
        toolchains.update({"go", "cargo"})
        assert _autodetect_command(tmp_path) == ["go", "test", "./..."]

    def test_cargo_beats_make(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\n')
        write(tmp_path, "Makefile", "test:\n\techo testing\n")
        toolchains.update({"cargo", "make"})
        assert _autodetect_command(tmp_path) == ["cargo", "test"]

    def test_make_beats_pytest(self, tmp_path, toolchains):
        write(tmp_path, "Makefile", "test:\n\techo testing\n")
        (tmp_path / "tests").mkdir()
        toolchains.add("make")
        assert _autodetect_command(tmp_path) == ["make", "test"]

    def test_an_unusable_earlier_signal_does_not_block_a_later_one(
        self, tmp_path, toolchains, no_pytest
    ):
        # go.mod is present but Go is not installed, so detection continues rather than
        # returning a command that could not run.
        write(tmp_path, "go.mod", "module example.com/demo\n")
        write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\n')
        toolchains.add("cargo")
        assert _autodetect_command(tmp_path) == ["cargo", "test"]


class TestNothingToDetect:
    def test_empty_directory(self, tmp_path, toolchains, no_pytest):
        assert _autodetect_command(tmp_path) is None

    def test_unrelated_files_only(self, tmp_path, toolchains, no_pytest):
        write(tmp_path, "README.md", "# demo\n")
        write(tmp_path, "index.html", "<!DOCTYPE html>\n")
        assert _autodetect_command(tmp_path) is None
