"""R6. Selecting a branch or commit displays information about it."""

from __future__ import annotations

from gittree.app import GitTreeApp


async def test_commit_details_shown(merged_repo):
    app = GitTreeApp(merged_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        merge = merged_repo.rev("main")
        assert app.selected_commit == merge
        text = app.detail_text
        assert merge in text  # full hash
        assert "Test User" in text and "test@example.com" in text
        assert "M: merge feature" in text
        assert merged_repo.rev("main~1") in text  # parents
        assert merged_repo.rev("feature") in text
        assert "main" in text and "HEAD" in text  # refs pointing at it


async def test_details_follow_cursor(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert linear_repo.rev("main~1") in app.detail_text
        assert "B" in app.detail_text


async def test_branch_details_shown(forked_repo):
    forked_repo.tag("v1")
    app = GitTreeApp(forked_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("tab")
        for _ in range(len(app.branch_list_names())):
            if app.selected_ref == "refs/heads/feature":
                break
            await pilot.press("down")
        await pilot.pause()
        text = app.detail_text
        assert "feature" in text
        assert "local" in text.lower()
        assert forked_repo.rev("feature") in text
        assert "E" in text  # tip commit message


async def test_current_branch_marked_as_head_in_details(forked_repo):
    app = GitTreeApp(forked_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("tab")
        for _ in range(len(app.branch_list_names())):
            if app.selected_ref == "refs/heads/main":
                break
            await pilot.press("down")
        await pilot.pause()
        assert "current head" in app.detail_text.lower()


async def test_tag_details_kind(forked_repo):
    forked_repo.tag("v1", annotated=True)
    app = GitTreeApp(forked_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("tab")
        for _ in range(len(app.branch_list_names())):
            if app.selected_ref == "refs/tags/v1":
                break
            await pilot.press("down")
        await pilot.pause()
        assert "tag" in app.detail_text.lower()
        assert forked_repo.rev("main") in app.detail_text  # annotated tag is peeled to its commit
