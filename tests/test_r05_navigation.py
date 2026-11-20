"""R5. The user can navigate through and select branches and commits using the keyboard."""

from __future__ import annotations

from gittree.app import GitTreeApp


async def test_arrow_and_vim_keys_move_commit_cursor(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.selected_commit == linear_repo.rev("main")
        await pilot.press("down")
        assert app.selected_commit == linear_repo.rev("main~1")
        await pilot.press("j")
        assert app.selected_commit == linear_repo.rev("main~2")
        await pilot.press("k")
        assert app.selected_commit == linear_repo.rev("main~1")
        await pilot.press("up")
        assert app.selected_commit == linear_repo.rev("main")


async def test_cursor_stops_at_bounds(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("up", "up")
        assert app.selected_commit == linear_repo.rev("main")
        await pilot.press("down", "down", "down", "down", "down")
        assert app.selected_commit == linear_repo.rev("main~2")


async def test_home_end_jump(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("end")
        assert app.selected_commit == linear_repo.rev("main~2")
        await pilot.press("home")
        assert app.selected_commit == linear_repo.rev("main")


async def test_tab_switches_between_graph_and_branch_list(forked_repo):
    app = GitTreeApp(forked_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.focused is app.graph_table
        await pilot.press("tab")
        assert app.focused is app.branch_table
        await pilot.press("tab")
        assert app.focused is app.graph_table


async def test_branch_list_lists_all_ref_kinds(forked_repo):
    forked_repo.tag("v1")
    forked_repo.update_ref("refs/remotes/origin/main", forked_repo.rev("main~1"))
    app = GitTreeApp(forked_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        names = app.branch_list_names()
        assert "refs/heads/main" in names
        assert "refs/heads/feature" in names
        assert "refs/remotes/origin/main" in names
        assert "refs/tags/v1" in names


async def test_selecting_branch_moves_graph_cursor_to_tip(forked_repo):
    app = GitTreeApp(forked_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("tab")
        # Move through the branch list until "feature" is selected.
        for _ in range(len(app.branch_list_names())):
            if app.selected_ref == "refs/heads/feature":
                break
            await pilot.press("down")
        assert app.selected_ref == "refs/heads/feature"
        await pilot.pause()
        assert app.graph_cursor_commit == forked_repo.rev("feature")


async def test_q_quits(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code in (0, None)
    assert not app.is_running
