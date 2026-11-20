"""R3. Different branches are displayed as distinguishable lanes in the tree."""

from __future__ import annotations

from gittree.gitdata import load_snapshot, open_repository
from gittree.layout import compute_layout


def _rows(repo):
    snap = load_snapshot(open_repository(repo.path))
    return {r.hash: r for r in compute_layout(snap.commits)}


def test_diverging_branches_get_different_lanes_and_colors(forked_repo):
    rows = _rows(forked_repo)
    main_tip = rows[forked_repo.rev("main")]
    feature_tip = rows[forked_repo.rev("feature")]
    assert main_tip.column != feature_tip.column
    assert main_tip.color != feature_tip.color


def test_lane_color_is_stable_along_a_branch(forked_repo):
    rows = _rows(forked_repo)
    e = rows[forked_repo.rev("feature")]
    d = rows[forked_repo.rev("feature~1")]
    assert (e.column, e.color) == (d.column, d.color)


def test_linear_history_uses_single_lane(linear_repo):
    rows = _rows(linear_repo)
    assert {r.column for r in rows.values()} == {0}
    assert len({r.color for r in rows.values()}) == 1


def test_three_branches_three_lanes(make_repo):
    r = make_repo()
    r.commit("base")
    r.branch("b1")
    r.branch("b2")
    r.commit("main work")
    r.checkout("b1")
    r.commit("b1 work")
    r.checkout("b2")
    r.commit("b2 work")
    rows = _rows(r)
    tips = [rows[r.rev(b)] for b in ("main", "b1", "b2")]
    assert len({t.column for t in tips}) == 3
    assert len({t.color for t in tips}) == 3
