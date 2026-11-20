"""R8. New commits or branches are visually highlighted when they appear."""

from __future__ import annotations

import asyncio
import time

from gittree.app import HIGHLIGHT_SECONDS, HIGHLIGHT_STYLE, GitTreeApp
from gittree.diff import diff_snapshots
from gittree.gitdata import load_snapshot, open_repository


def _snap(repo):
    return load_snapshot(open_repository(repo.path))


def test_highlight_duration_default():
    assert HIGHLIGHT_SECONDS == 10.0


def test_no_changes_on_first_load(linear_repo):
    changes = diff_snapshots(None, _snap(linear_repo))
    assert changes.is_empty


def test_unchanged_repo_has_no_changes(linear_repo):
    assert diff_snapshots(_snap(linear_repo), _snap(linear_repo)).is_empty


def test_new_commit_detected(linear_repo):
    before = _snap(linear_repo)
    new = linear_repo.commit("D")
    changes = diff_snapshots(before, _snap(linear_repo))
    assert changes.new_commits == frozenset({new})
    assert "refs/heads/main" in changes.changed_refs  # main moved


def test_new_branch_detected(linear_repo):
    before = _snap(linear_repo)
    linear_repo.branch("topic", "main~1")
    changes = diff_snapshots(before, _snap(linear_repo))
    assert changes.new_commits == frozenset()
    assert changes.changed_refs == frozenset({"refs/heads/topic"})


def test_new_tag_detected(linear_repo):
    before = _snap(linear_repo)
    linear_repo.tag("v1")
    assert diff_snapshots(before, _snap(linear_repo)).changed_refs == frozenset({"refs/tags/v1"})


def test_deleted_branch_is_not_highlighted(linear_repo):
    linear_repo.branch("topic")
    before = _snap(linear_repo)
    linear_repo.delete_branch("topic")
    assert diff_snapshots(before, _snap(linear_repo)).is_empty


async def _wait_for(pilot, condition, timeout=10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        await pilot.pause(0.05)
    return condition()


async def test_nothing_highlighted_at_startup(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        for c in app.snapshot.commits:
            assert not app.is_highlighted(c.hash)


async def test_new_commit_row_highlighted_then_expires(linear_repo):
    app = GitTreeApp(linear_repo.path, poll_interval=0.1, highlight_seconds=1.0)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        old = linear_repo.head()
        new = await asyncio.to_thread(linear_repo.commit, "D")
        assert await _wait_for(pilot, lambda: app.snapshot.commit(new) is not None)
        await pilot.pause()
        assert app.is_highlighted(new)
        assert not app.is_highlighted(old)
        assert app.is_ref_highlighted("refs/heads/main")
        assert app.hash_cell(new).style == HIGHLIGHT_STYLE
        assert app.hash_cell(old).style != HIGHLIGHT_STYLE
        # Highlight fades after the configured duration.
        assert await _wait_for(pilot, lambda: not app.is_highlighted(new), timeout=5.0)
        assert app.hash_cell(new).style != HIGHLIGHT_STYLE


async def test_new_branch_highlighted(linear_repo):
    app = GitTreeApp(linear_repo.path, poll_interval=0.1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await asyncio.to_thread(linear_repo.branch, "topic", "main~1")
        assert await _wait_for(pilot, lambda: "refs/heads/topic" in app.branch_list_names())
        assert app.is_ref_highlighted("refs/heads/topic")
        assert not app.is_ref_highlighted("refs/heads/main")
