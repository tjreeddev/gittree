"""Pure graph layout: turn commits (topologically ordered) into drawable rows.

Git does not record which branch a commit belongs to, so lanes are computed:
each line of history occupies a column ("lane") that carries the hash it is
waiting for. A commit is placed in the lane expecting it; its first parent
inherits that lane (and its color), extra parents (merges) get other lanes,
and extra lanes that were waiting for the same commit (forks) end here.

Each commit is drawn on one line. Every lane is 2 characters wide: a glyph
and a gap that may hold a horizontal connector.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from gittree.gitdata import Commit

NODE = "●"
MERGE_NODE = "◆"
NODE_GLYPHS = frozenset({NODE, MERGE_NODE})


@dataclass(frozen=True)
class Cell:
    char: str
    color: int | None  # lane color index; None for blank


@dataclass(frozen=True)
class GraphRow:
    hash: str
    column: int  # lane the commit's node is drawn in
    color: int  # color index of that lane
    joins: tuple[int, ...]  # other lanes that end in this commit (fork point: >1 child)
    parent_columns: tuple[int, ...]  # lane each parent continues in, in parent order
    lanes_before: tuple[str | None, ...]
    lanes_after: tuple[str | None, ...]
    cells: tuple[Cell, ...]

    @property
    def text(self) -> str:
        return "".join(c.char for c in self.cells)


def _free_slot(lanes: list[str | None], avoid: frozenset[int] = frozenset()) -> int:
    for i, h in enumerate(lanes):
        if h is None and i not in avoid:
            return i
    lanes.append(None)
    return len(lanes) - 1


def compute_layout(commits: Sequence[Commit]) -> list[GraphRow]:
    lanes: list[str | None] = []
    colors: list[int] = []
    next_color = 0
    rows: list[GraphRow] = []

    def ensure(idx: int) -> None:
        while len(colors) <= idx:
            colors.append(-1)

    for commit in commits:
        before = tuple(lanes)
        expecting = [i for i, h in enumerate(lanes) if h == commit.hash]
        if expecting:
            column = expecting[0]
            joins = tuple(expecting[1:])
        else:
            column = _free_slot(lanes)
            ensure(column)
            colors[column] = next_color
            next_color += 1
            joins = ()
            before = tuple(lanes)  # include the (empty) slot we just made

        color = colors[column]
        for j in joins:
            lanes[j] = None

        parent_columns: list[int] = []
        new_lanes: set[int] = set()
        if commit.parents:
            lanes[column] = commit.parents[0]
            parent_columns.append(column)
            for parent in commit.parents[1:]:
                existing = next((i for i, h in enumerate(lanes) if h == parent and i != column), None)
                if existing is not None:
                    parent_columns.append(existing)
                    continue
                slot = _free_slot(lanes, avoid=frozenset({column, *joins}))
                ensure(slot)
                lanes[slot] = parent
                colors[slot] = next_color
                next_color += 1
                parent_columns.append(slot)
                new_lanes.add(slot)
        else:
            lanes[column] = None

        while lanes and lanes[-1] is None:
            lanes.pop()
        after = tuple(lanes)

        cells = _draw(
            column=column,
            color=color,
            is_merge=len(commit.parents) > 1,
            before=before,
            joins=joins,
            parent_columns=tuple(parent_columns),
            new_lanes=new_lanes,
            colors=colors,
        )
        rows.append(
            GraphRow(
                hash=commit.hash,
                column=column,
                color=color,
                joins=joins,
                parent_columns=tuple(parent_columns),
                lanes_before=before,
                lanes_after=after,
                cells=cells,
            )
        )
    return rows


def _draw(
    *,
    column: int,
    color: int,
    is_merge: bool,
    before: tuple[str | None, ...],
    joins: tuple[int, ...],
    parent_columns: tuple[int, ...],
    new_lanes: set[int],
    colors: list[int],
) -> tuple[Cell, ...]:
    extra_parents = set(parent_columns[1:])
    connected = set(joins) | extra_parents
    width = max([len(before), column + 1, *(c + 1 for c in connected)])
    lo = min([column, *connected])
    hi = max([column, *connected])

    cells: list[Cell] = []
    for col in range(width):
        passing = col < len(before) and before[col] is not None
        lane_color = colors[col] if col < len(colors) and colors[col] >= 0 else color
        if col == column:
            glyph = Cell(MERGE_NODE if is_merge else NODE, color)
        elif col in joins:
            glyph = Cell("╯" if col > column else "╰", lane_color)
        elif col in new_lanes:
            glyph = Cell("╮" if col > column else "╭", lane_color)
        elif col in extra_parents:  # merge into a lane that already exists
            glyph = Cell("┤" if col > column else "├", lane_color)
        elif passing and lo < col < hi:
            glyph = Cell("┼", lane_color)
        elif passing:
            glyph = Cell("│", lane_color)
        elif lo < col < hi:
            glyph = Cell("─", color)
        else:
            glyph = Cell(" ", None)
        cells.append(glyph)

        # Gap between this lane and the next.
        if col < width - 1:
            if lo <= col < hi:
                right = col + 1
                gap_color = colors[right] if right in connected and right < len(colors) else color
                if col < column:
                    gap_color = colors[col] if col in connected and col < len(colors) else color
                cells.append(Cell("─", gap_color))
            else:
                cells.append(Cell(" ", None))
    return tuple(cells)
