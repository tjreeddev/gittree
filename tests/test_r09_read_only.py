"""R9. The program is read-only and never modifies the repository."""

from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path

import pytest

import gittree
from gittree import gitdata
from gittree.app import GitTreeApp
from gittree.gitdata import ALLOWED_SUBCOMMANDS, ReadOnlyViolation, load_snapshot, open_repository, run_git
from gittree.watch import RepoWatcher

from conftest import snapshot_tree


def test_allowlist_contains_only_read_commands():
    assert ALLOWED_SUBCOMMANDS == frozenset(
        {"log", "for-each-ref", "rev-parse", "show", "cat-file", "symbolic-ref"}
    )


@pytest.mark.parametrize(
    "args",
    [
        ("commit", "-m", "x"),
        ("checkout", "main"),
        ("switch", "main"),
        ("merge", "feature"),
        ("add", "."),
        ("branch", "-D", "feature"),
        ("tag", "v9"),
        ("reset", "--hard"),
        ("update-ref", "refs/heads/x", "HEAD"),
        ("fetch",),
        ("gc",),
        ("status",),
        ("symbolic-ref", "HEAD", "refs/heads/feature"),
        ("symbolic-ref", "-d", "HEAD"),
        ("symbolic-ref", "--delete", "HEAD"),
    ],
)
def test_reader_rejects_writing_commands(forked_repo, args):
    before = snapshot_tree(forked_repo.path)
    with pytest.raises(ReadOnlyViolation):
        run_git(forked_repo.path, *args)
    assert snapshot_tree(forked_repo.path) == before


def test_every_git_call_disables_optional_locks(forked_repo, monkeypatch):
    seen: list[tuple[list[str], dict[str, str]]] = []
    real_run = subprocess.run

    def spy(cmd, *a, **kw):
        seen.append((list(cmd), dict(kw.get("env") or {})))
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(gitdata.subprocess, "run", spy)
    root = open_repository(forked_repo.path)
    load_snapshot(root)
    RepoWatcher(root).has_changed()
    assert seen, "expected git to be invoked"
    for cmd, env in seen:
        assert env.get("GIT_OPTIONAL_LOCKS") == "0", cmd


def test_only_gitdata_spawns_processes():
    """All subprocess use is confined to the read-only reader module."""
    pkg = Path(gittree.__file__).parent
    offenders = []
    for py in pkg.glob("*.py"):
        if py.name == "gitdata.py":
            continue
        if re.search(r"\bsubprocess\b|\bos\.system\b|\bPopen\b", py.read_text(encoding="utf-8")):
            offenders.append(py.name)
    assert offenders == []


async def test_full_session_leaves_repository_byte_identical(merged_repo):
    merged_repo.tag("v1", annotated=True)
    merged_repo.update_ref("refs/remotes/origin/main", merged_repo.rev("main~1"))
    (merged_repo.path / "work.txt").write_text("uncommitted\n", encoding="utf-8")
    before = snapshot_tree(merged_repo.path)

    app = GitTreeApp(merged_repo.path, poll_interval=0.1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("down", "down", "j", "k", "end", "home", "pagedown", "pageup")
        await pilot.press("tab", "down", "down", "enter", "up", "tab")
        await asyncio.sleep(1.0)  # several poll cycles
        await pilot.press("q")

    assert snapshot_tree(merged_repo.path) == before
