"""R1. The program can open and read a local Git repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from gittree.cli import main
from gittree.gitdata import NotARepositoryError, load_snapshot, open_repository


def test_opens_repository_root(linear_repo):
    root = open_repository(linear_repo.path)
    assert root.resolve() == linear_repo.path.resolve()


def test_subdirectory_resolves_to_repository_root(linear_repo):
    sub = linear_repo.path / "src" / "deep"
    sub.mkdir(parents=True)
    assert open_repository(sub).resolve() == linear_repo.path.resolve()


def test_non_repository_raises_clean_error(tmp_path: Path, git_env):
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    with pytest.raises(NotARepositoryError):
        open_repository(plain)


def test_missing_path_raises_clean_error(tmp_path: Path, git_env):
    with pytest.raises(NotARepositoryError):
        open_repository(tmp_path / "does_not_exist")


def test_reads_commits_and_refs(linear_repo):
    snap = load_snapshot(open_repository(linear_repo.path))
    assert [c.subject for c in snap.commits] == ["C", "B", "A"]
    assert snap.head == linear_repo.head()
    assert snap.head_ref == "refs/heads/main"
    assert any(r.name == "refs/heads/main" for r in snap.refs)


def test_empty_repository_loads_without_commits(repo):
    snap = load_snapshot(open_repository(repo.path))
    assert snap.commits == ()
    assert snap.head is None


def test_cli_reports_non_repository_without_traceback(tmp_path: Path, git_env, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    code = main([str(plain)])
    err = capsys.readouterr().err
    assert code != 0
    assert "not" in err.lower() and "git repository" in err.lower()
    assert "Traceback" not in err
