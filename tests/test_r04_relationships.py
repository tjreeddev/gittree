"""R4. The tree shows relationships between commits, including branches splitting and merging."""

from __future__ import annotations

from gittree.gitdata import load_snapshot, open_repository
from gittree.layout import compute_layout


def _load(repo):
    snap = load_snapshot(open_repository(repo.path))
    return snap, {r.hash: r for r in compute_layout(snap.commits)}


def test_parent_lists_are_correct(merged_repo):
    snap, _ = _load(merged_repo)
    merge = snap.commit(merged_repo.rev("main"))
    assert merge.parents == (merged_repo.rev("main~1"), merged_repo.rev("feature"))
    assert snap.commit(merged_repo.rev("feature~1")).parents == (merged_repo.rev("feature~2"),)


def test_fork_point_has_two_children_converging(forked_repo):
    """B is the parent of both C (main) and D (feature): two lanes meet at B."""
    _, rows = _load(forked_repo)
    fork = rows[forked_repo.rev("main~1")]  # B
    incoming = {fork.column, *fork.joins}
    assert len(incoming) == 2
    # The joined lane comes from the feature branch's lane.
    feature_lane = rows[forked_repo.rev("feature~1")].column  # D
    assert feature_lane in incoming


def test_merge_commit_has_two_parent_edges(merged_repo):
    _, rows = _load(merged_repo)
    merge = rows[merged_repo.rev("main")]
    assert len(merge.parent_columns) == 2
    assert merge.parent_columns[0] == merge.column  # first parent continues straight down
    assert merge.parent_columns[1] != merge.column  # second parent in another lane
    # The second parent (feature tip) is drawn in that lane.
    assert rows[merged_repo.rev("feature")].column == merge.parent_columns[1]


def test_root_commit_has_no_parent_edges(linear_repo):
    _, rows = _load(linear_repo)
    root = rows[linear_repo.rev("main~2")]
    assert root.parent_columns == ()


def test_rendered_graph_shows_merge_and_fork_connectors(merged_repo):
    _, rows = _load(merged_repo)
    merge = rows[merged_repo.rev("main")]
    fork = rows[merged_repo.rev("main~2")]  # B
    assert "╮" in merge.text or "┤" in merge.text  # line leaving node towards second parent
    assert "╯" in fork.text or "┤" in fork.text  # lane joining back into fork point
