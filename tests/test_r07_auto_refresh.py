"""R7. The program automatically refreshes when the Git repository changes while it is running."""

from __future__ import annotations

import asyncio
import time

from gittree.app import GitTreeApp
from gittree.watch import POLL_INTERVAL, RepoWatcher

TIMEOUT = 10.0


async def _wait_for(pilot, condition) -> bool:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if condition():
            return True
        await pilot.pause(0.05)
    return condition()


def test_poll_interval_default():
    assert POLL_INTERVAL == 0.5


def test_watcher_detects_new_commit(linear_repo):
    w = RepoWatcher(linear_repo.path)
    assert w.has_changed() is False  # first call establishes the baseline
    assert w.has_changed() is False
    linear_repo.commit("D")
    assert w.has_changed() is True
    assert w.has_changed() is False


def test_watcher_detects_branch_create_delete_and_checkout(linear_repo):
    w = RepoWatcher(linear_repo.path)
    w.has_changed()
    linear_repo.branch("topic")
    assert w.has_changed() is True
    linear_repo.checkout("topic")
    assert w.has_changed() is True
    linear_repo.checkout("main")
    w.has_changed()
    linear_repo.delete_branch("topic")
    assert w.has_changed() is True


async def test_app_shows_new_commit_without_restart(linear_repo):
    app = GitTreeApp(linear_repo.path, poll_interval=0.1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        new = await asyncio.to_thread(linear_repo.commit, "D")
        assert await _wait_for(pilot, lambda: app.snapshot.commit(new) is not None)
        assert app.graph_table.row_count == 4


async def test_app_reflects_branch_creation_and_deletion(linear_repo):
    app = GitTreeApp(linear_repo.path, poll_interval=0.1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await asyncio.to_thread(linear_repo.branch, "topic", "main~1")
        assert await _wait_for(pilot, lambda: "refs/heads/topic" in app.branch_list_names())
        await asyncio.to_thread(linear_repo.delete_branch, "topic")
        assert await _wait_for(pilot, lambda: "refs/heads/topic" not in app.branch_list_names())


async def test_selection_preserved_across_refresh(linear_repo):
    app = GitTreeApp(linear_repo.path, poll_interval=0.1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("down")
        selected = app.selected_commit
        new = await asyncio.to_thread(linear_repo.commit, "D")
        assert await _wait_for(pilot, lambda: app.snapshot.commit(new) is not None)
        await pilot.pause()
        assert app.selected_commit == selected
