"""R2. The program displays the repository's commits as a visual tree in the terminal."""

from __future__ import annotations

from gittree.app import GitTreeApp
from gittree.gitdata import MAX_COMMITS, load_snapshot, open_repository
from gittree.layout import NODE_GLYPHS, compute_layout


def test_max_commits_default_is_1000():
    assert MAX_COMMITS == 1000


def test_linear_history_one_row_per_commit_in_topological_order(linear_repo):
    snap = load_snapshot(open_repository(linear_repo.path))
    rows = compute_layout(snap.commits)
    assert [r.hash for r in rows] == [c.hash for c in snap.commits]
    assert len(rows) == 3
    for row in rows:
        assert row.column == 0
        assert row.text[row.column * 2] in NODE_GLYPHS


def test_children_appear_before_parents(merged_repo):
    snap = load_snapshot(open_repository(merged_repo.path))
    position = {c.hash: i for i, c in enumerate(snap.commits)}
    for c in snap.commits:
        for p in c.parents:
            if p in position:
                assert position[c.hash] < position[p]


def test_commit_cap_is_enforced(make_repo):
    r = make_repo()
    r.bulk_commits(MAX_COMMITS + 5)
    snap = load_snapshot(open_repository(r.path))
    assert len(snap.commits) == MAX_COMMITS
    # Most recent commits are the ones kept.
    assert snap.commits[0].subject == f"bulk {MAX_COMMITS + 4}"


async def test_app_shows_one_graph_row_per_commit(linear_repo):
    app = GitTreeApp(linear_repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.graph_table.row_count == 3
        rendered = app.row_plain_text(linear_repo.head())
        assert "C" in rendered
        assert linear_repo.head()[:7] in rendered


async def test_app_handles_empty_repository(repo):
    app = GitTreeApp(repo.path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.graph_table.row_count == 0
        assert "no commits" in app.detail_text.lower()
