"""R10. The program runs on the user's own computer with one command (`uv run gittree [PATH]`)."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from importlib.metadata import entry_points
from pathlib import Path

from gittree.cli import main

PROJECT = Path(__file__).resolve().parent.parent


def test_pyproject_defines_gittree_script():
    data = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["gittree"] == "gittree.cli:main"
    assert data["project"]["requires-python"] == ">=3.14"


def test_entry_point_installed():
    eps = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert eps.get("gittree") == "gittree.cli:main"


def test_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "gittree", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()
    assert "PATH" in result.stdout


def test_main_help_returns_zero(capsys):
    try:
        code = main(["--help"])
    except SystemExit as exc:  # argparse exits on --help
        code = exc.code
    assert code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_main_runs_app_on_repository(linear_repo, monkeypatch):
    launched = {}

    def fake_run(self):
        launched["root"] = self.root

    monkeypatch.setattr("gittree.app.GitTreeApp.run", fake_run)
    assert main([str(linear_repo.path)]) == 0
    assert Path(launched["root"]).resolve() == linear_repo.path.resolve()


def test_main_defaults_to_current_directory(linear_repo, monkeypatch):
    launched = {}

    def fake_run(self):
        launched["root"] = self.root

    monkeypatch.setattr("gittree.app.GitTreeApp.run", fake_run)
    monkeypatch.chdir(linear_repo.path)
    assert main([]) == 0
    assert Path(launched["root"]).resolve() == linear_repo.path.resolve()
