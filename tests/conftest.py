"""Shared fixtures: build throwaway Git repositories in pytest's tmp_path.

Tests only ever write to repositories they create here; the user's own
repositories are never touched.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


class GitRepo:
    """A small helper that drives real `git` against a temporary repository."""

    def __init__(self, path: Path, env: dict[str, str]) -> None:
        self.path = path
        self._env = env
        self._tick = 0

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            env=self._env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return result.stdout.strip()

    def _dated_env(self) -> dict[str, str]:
        """Strictly increasing timestamps keep commit order deterministic."""
        self._tick += 1
        date = f"{1767225600 + self._tick} +0000"
        return dict(self._env, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)

    def commit(self, message: str) -> str:
        """Create an (empty) commit; return its hash."""
        env = self._dated_env()
        subprocess.run(
            ["git", "commit", "--allow-empty", "-q", "-m", message],
            cwd=self.path,
            env=env,
            capture_output=True,
            check=True,
        )
        return self.head()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def rev(self, name: str) -> str:
        return self.git("rev-parse", name)

    def branch(self, name: str, start: str | None = None) -> None:
        self.git("branch", name, *([start] if start else []))

    def checkout(self, name: str) -> None:
        self.git("checkout", "-q", name)

    def bulk_commits(self, count: int, branch: str = "main") -> None:
        """Quickly create `count` linear commits on `branch` using git fast-import."""
        lines = []
        for i in range(count):
            msg = f"bulk {i}".encode()
            when = 1767225600 + i
            lines.append(f"commit refs/heads/{branch}\n".encode())
            lines.append(f"committer Test User <test@example.com> {when} +0000\n".encode())
            lines.append(f"data {len(msg)}\n".encode() + msg + b"\n")
            if i == 0:
                lines.append(b"deleteall\n")
            lines.append(b"\n")
        subprocess.run(
            ["git", "fast-import", "--quiet"],
            cwd=self.path,
            env=self._env,
            input=b"".join(lines),
            capture_output=True,
            check=True,
        )

    def merge(self, name: str, message: str) -> str:
        env = self._dated_env()
        subprocess.run(
            ["git", "merge", "--no-ff", "-q", "-m", message, name],
            cwd=self.path,
            env=env,
            capture_output=True,
            check=True,
        )
        return self.head()

    def tag(self, name: str, annotated: bool = False) -> None:
        if annotated:
            self.git("tag", "-a", name, "-m", f"tag {name}")
        else:
            self.git("tag", name)

    def delete_branch(self, name: str) -> None:
        self.git("branch", "-D", name)

    def update_ref(self, ref: str, target: str) -> None:
        self.git("update-ref", ref, target)


@pytest.fixture
def git_env(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Isolate git from the user's global/system config for the whole test.

    The variables are also set on the test process so gittree's own read-only
    git calls see the same clean configuration.
    """
    cfg_dir = tmp_path_factory.mktemp("gitconfig")
    global_cfg = cfg_dir / "gitconfig"
    global_cfg.write_text(
        "[user]\n\tname = Test User\n\temail = test@example.com\n"
        "[init]\n\tdefaultBranch = main\n"
        "[commit]\n\tgpgsign = false\n"
        "[tag]\n\tgpgsign = false\n",
        encoding="utf-8",
    )
    values = {
        "GIT_CONFIG_GLOBAL": str(global_cfg),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return dict(os.environ, **values)


@pytest.fixture
def make_repo(tmp_path: Path, git_env: dict[str, str]):
    """Factory: make_repo(name) -> an initialised, empty GitRepo."""

    def _make(name: str = "repo") -> GitRepo:
        path = tmp_path / name
        path.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, env=git_env, check=True)
        return GitRepo(path, git_env)

    return _make


@pytest.fixture
def repo(make_repo) -> GitRepo:
    """An empty repository (no commits yet)."""
    return make_repo()


@pytest.fixture
def linear_repo(make_repo) -> GitRepo:
    """main: A - B - C"""
    r = make_repo()
    r.commit("A")
    r.commit("B")
    r.commit("C")
    return r


@pytest.fixture
def forked_repo(make_repo) -> GitRepo:
    """
    main:    A - B - C
                  \\
    feature:       D - E
    """
    r = make_repo()
    r.commit("A")
    r.commit("B")
    r.branch("feature")
    r.commit("C")
    r.checkout("feature")
    r.commit("D")
    r.commit("E")
    r.checkout("main")
    return r


@pytest.fixture
def merged_repo(forked_repo: GitRepo) -> GitRepo:
    """forked_repo with feature merged into main via a merge commit M."""
    forked_repo.merge("feature", "M: merge feature")
    return forked_repo


def snapshot_tree(root: Path) -> dict[str, tuple[bytes, int]]:
    """Map every file under root (including .git) to (contents, mtime_ns)."""
    state: dict[str, tuple[bytes, int]] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            state[str(p.relative_to(root))] = (p.read_bytes(), p.stat().st_mtime_ns)
    return state
