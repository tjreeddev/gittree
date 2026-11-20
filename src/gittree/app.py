"""The Textual TUI: commit graph, branch list, detail panel (R2–R8)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Static

from gittree.diff import diff_snapshots
from gittree.gitdata import MAX_COMMITS, GitError, Ref, Snapshot, load_snapshot
from gittree.layout import GraphRow, compute_layout
from gittree.watch import POLL_INTERVAL, RepoWatcher

HIGHLIGHT_SECONDS = 10.0
HIGHLIGHT_STYLE = "bold black on #f9e64f"
HASH_STYLE = "#e5c07b"
LANE_PALETTE = (
    "#61afef",  # blue
    "#e06c75",  # red
    "#98c379",  # green
    "#c678dd",  # purple
    "#56b6c2",  # cyan
    "#d19a66",  # orange
    "#f472b6",  # pink
    "#a3e635",  # lime
)
REF_STYLES = {
    "head": "bold #1e1e1e on #56b6c2",
    "local": "bold #98c379",
    "remote": "bold #e06c75",
    "tag": "bold #e5c07b",
}
KIND_LABELS = {"local": "local branch", "remote": "remote-tracking branch", "tag": "tag"}
DETACHED_KEY = "HEAD"


class NavTable(DataTable):
    """A row-cursor DataTable with vim-style j/k in addition to the arrow keys."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("home", "first_row", "First", show=False),
        Binding("end", "last_row", "Last", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=False, **kwargs)

    def action_first_row(self) -> None:
        if self.row_count:
            self.move_cursor(row=0)

    def action_last_row(self) -> None:
        if self.row_count:
            self.move_cursor(row=self.row_count - 1)


class GitTreeApp(App):
    TITLE = "gittree"
    CSS = """
    Screen { layout: horizontal; }
    #graph { width: 2fr; height: 1fr; border: round #4b5263; }
    #graph:focus { border: round #61afef; }
    #side { width: 1fr; height: 1fr; }
    #branches { height: 45%; border: round #4b5263; }
    #branches:focus { border: round #61afef; }
    #detail { height: 1fr; border: round #4b5263; padding: 0 1; overflow-y: auto; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_panel", "Switch panel", priority=True),
        Binding("shift+tab", "toggle_panel", "Switch panel", show=False, priority=True),
    ]

    def __init__(
        self,
        root: str | Path,
        *,
        poll_interval: float = POLL_INTERVAL,
        highlight_seconds: float = HIGHLIGHT_SECONDS,
        max_commits: int = MAX_COMMITS,
    ) -> None:
        super().__init__()
        self.root = Path(root)
        self.poll_interval = poll_interval
        self.highlight_seconds = highlight_seconds
        self.max_commits = max_commits
        self.watcher = RepoWatcher(self.root)
        self.snapshot: Snapshot | None = None
        self.rows: list[GraphRow] = []
        self.detail_text = ""
        self._hl_commits: dict[str, float] = {}
        self._hl_refs: dict[str, float] = {}
        self._polling = False

    # ------------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        yield Header()
        self.graph_table = NavTable(id="graph")
        self.graph_table.border_title = "Commits"
        self.branch_table = NavTable(id="branches")
        self.branch_table.border_title = "Branches & tags"
        self.detail = Static(id="detail")
        self.detail.border_title = "Details"
        yield self.graph_table
        with Vertical(id="side"):
            yield self.branch_table
            yield self.detail
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = str(self.root)
        self.graph_table.add_column("Graph", key="graph")
        self.graph_table.add_column("Hash", key="hash")
        self.graph_table.add_column("Message", key="message")
        self.branch_table.add_column("Ref", key="ref")
        self.watcher.has_changed()  # baseline before the first load, so no change is missed
        self._apply_snapshot(load_snapshot(self.root, self.max_commits))
        self.graph_table.focus()
        self._show_commit(self.selected_commit)
        self.set_interval(self.poll_interval, self._poll)

    # ------------------------------------------------------------------ public helpers (also used by tests)

    @property
    def selected_commit(self) -> str | None:
        return self._cursor_key(self.graph_table)

    @property
    def graph_cursor_commit(self) -> str | None:
        return self._cursor_key(self.graph_table)

    @property
    def selected_ref(self) -> str | None:
        return self._cursor_key(self.branch_table)

    def branch_list_names(self) -> list[str]:
        return [str(row.key.value) for row in self.branch_table.ordered_rows]

    # Highlight state is cleared only by _expire_highlights, which also re-renders,
    # so these always agree with what is drawn on screen.
    def is_highlighted(self, hash_: str) -> bool:
        return hash_ in self._hl_commits

    def is_ref_highlighted(self, name: str) -> bool:
        return name in self._hl_refs

    def hash_cell(self, hash_: str) -> Text:
        return self.graph_table.get_cell(hash_, "hash")

    def row_plain_text(self, hash_: str) -> str:
        return " ".join(
            cell.plain if isinstance(cell, Text) else str(cell) for cell in self.graph_table.get_row(hash_)
        )

    # ------------------------------------------------------------------ refresh (R7, R8)

    async def _poll(self) -> None:
        if self._polling:
            return
        self._polling = True
        try:
            changed = await asyncio.to_thread(self.watcher.has_changed)
            if not changed or not self._is_live():
                return
            snapshot = await asyncio.to_thread(load_snapshot, self.root, self.max_commits)
            if self._is_live():  # the app may have quit while git was running
                self._apply_snapshot(snapshot)
        except GitError:
            pass  # e.g. a ref mid-update in the other terminal; the next poll retries
        finally:
            self._polling = False

    def _apply_snapshot(self, snapshot: Snapshot) -> None:
        changes = diff_snapshots(self.snapshot, snapshot)
        if not changes.is_empty:
            until = time.monotonic() + self.highlight_seconds
            for h in changes.new_commits:
                self._hl_commits[h] = until
            for name in changes.changed_refs:
                self._hl_refs[name] = until
            self.set_timer(self.highlight_seconds, self._expire_highlights)
        self.snapshot = snapshot
        self.rows = compute_layout(snapshot.commits)
        self._render_tables()
        if self._branch_focused():
            self._show_ref(self.selected_ref)
        else:
            self._show_commit(self.selected_commit)

    def _is_live(self) -> bool:
        """True while the app is running and its screens still exist."""
        try:
            return self.is_running and bool(self.screen_stack)
        except Exception:  # screen stack already torn down during shutdown
            return False

    def _branch_focused(self) -> bool:
        """Whether the branch list has focus; False once the app is shutting down.

        Reading `self.focused` with no screens on the stack raises ScreenStackError,
        which can happen when a queued table event is delivered during shutdown.
        """
        return self._is_live() and self.focused is self.branch_table

    def _expire_highlights(self) -> None:
        if not self._is_live():
            return
        now = time.monotonic() + 0.05  # small tolerance for timer jitter
        self._hl_commits = {h: t for h, t in self._hl_commits.items() if t > now}
        self._hl_refs = {n: t for n, t in self._hl_refs.items() if t > now}
        self._render_tables()
        if self._branch_focused():
            self._show_ref(self.selected_ref)
        else:
            self._show_commit(self.selected_commit)

    # ------------------------------------------------------------------ rendering

    def _render_tables(self) -> None:
        assert self.snapshot is not None
        prev_commit, prev_commit_row = self.selected_commit, self.graph_table.cursor_row
        prev_ref, prev_ref_row = self.selected_ref, self.branch_table.cursor_row

        self.graph_table.clear()
        for row in self.rows:
            commit = self.snapshot.commit(row.hash)
            assert commit is not None
            new = self.is_highlighted(row.hash)
            hash_text = Text(commit.short_hash, style=HIGHLIGHT_STYLE if new else HASH_STYLE)
            message = Text()
            if new:
                message.append(" NEW ", style=HIGHLIGHT_STYLE)
                message.append(" ")
            message.append_text(self._ref_labels(row.hash))
            message.append(commit.subject)
            self.graph_table.add_row(self._graph_text(row), hash_text, message, key=row.hash)

        self.branch_table.clear()
        for key, label in self._branch_entries():
            self.branch_table.add_row(label, key=key)

        self._restore_cursor(self.graph_table, prev_commit, prev_commit_row)
        self._restore_cursor(self.branch_table, prev_ref, prev_ref_row)

    def _graph_text(self, row: GraphRow) -> Text:
        text = Text()
        for cell in row.cells:
            style = LANE_PALETTE[cell.color % len(LANE_PALETTE)] if cell.color is not None else ""
            if cell.char in ("●", "◆"):
                style += " bold"
                if row.hash == self.snapshot.head:
                    text.append("◉", style=style)
                    continue
            text.append(cell.char, style=style)
        return text

    def _ref_labels(self, hash_: str) -> Text:
        snap = self.snapshot
        text = Text()
        labels: list[tuple[str, str, str]] = []  # (label, style, ref name for highlight)
        refs = snap.refs_at(hash_)
        if snap.head == hash_ and snap.detached:
            labels.append(("HEAD", REF_STYLES["head"], DETACHED_KEY))
        for ref in refs:
            if ref.name == snap.head_ref:
                labels.insert(0, (f"HEAD → {ref.short_name}", REF_STYLES["head"], ref.name))
            elif ref.kind == "tag":
                labels.append((f"tag: {ref.short_name}", REF_STYLES["tag"], ref.name))
            else:
                labels.append((ref.short_name, REF_STYLES[ref.kind], ref.name))
        for label, style, name in labels:
            text.append(f" {label} ", style=HIGHLIGHT_STYLE if self.is_ref_highlighted(name) else style)
            text.append(" ")
        return text

    def _branch_entries(self) -> list[tuple[str, Text]]:
        snap = self.snapshot
        entries: list[tuple[str, Text]] = []
        if snap.detached:
            entries.append((DETACHED_KEY, Text("* HEAD (detached)", style=REF_STYLES["head"])))
        for ref in snap.refs:
            marker = "* " if ref.name == snap.head_ref else "  "
            prefix = {"local": "", "remote": "", "tag": "tag: "}[ref.kind]
            style = HIGHLIGHT_STYLE if self.is_ref_highlighted(ref.name) else REF_STYLES[ref.kind]
            entries.append((ref.name, Text(f"{marker}{prefix}{ref.short_name}", style=style)))
        return entries

    @staticmethod
    def _cursor_key(table: DataTable) -> str | None:
        if table.row_count == 0:
            return None
        try:
            return str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        except Exception:
            return None

    @staticmethod
    def _restore_cursor(table: DataTable, key: str | None, old_row: int) -> None:
        if table.row_count == 0:
            return
        if key is not None:
            try:
                table.move_cursor(row=table.get_row_index(key), animate=False)
                return
            except Exception:
                pass
        table.move_cursor(row=min(max(old_row, 0), table.row_count - 1), animate=False)

    # ------------------------------------------------------------------ details (R6)

    def _set_detail(self, text: Text) -> None:
        self.detail_text = text.plain
        self.detail.update(text)

    def _show_commit(self, hash_: str | None) -> None:
        snap = self.snapshot
        if snap is None or not snap.commits:
            self._set_detail(Text("No commits yet in this repository.", style="italic"))
            return
        commit = snap.commit(hash_) if hash_ else None
        if commit is None:
            return
        t = Text()
        t.append("Commit   ", style="bold")
        t.append(commit.hash + "\n", style=HASH_STYLE)
        t.append("Author   ", style="bold")
        t.append(f"{commit.author_name} <{commit.author_email}>\n")
        t.append("Date     ", style="bold")
        t.append(commit.author_date + "\n")
        t.append("Parents  ", style="bold")
        if commit.parents:
            t.append(("\n" + " " * 9).join(commit.parents) + "\n", style=HASH_STYLE)
        else:
            t.append("(none - root commit)\n", style="dim")
        labels = self._ref_labels(commit.hash)
        if labels.plain.strip():
            t.append("Refs     ", style="bold")
            t.append_text(labels)
            t.append("\n")
        if self.is_highlighted(commit.hash):
            t.append("New since last refresh\n", style=HIGHLIGHT_STYLE)
        t.append("\n")
        t.append(commit.message or "(no message)")
        self._set_detail(t)

    def _show_ref(self, name: str | None) -> None:
        snap = self.snapshot
        if snap is None or name is None:
            return
        if name == DETACHED_KEY:
            title, kind, full, target, is_head = "HEAD", "detached HEAD", "HEAD", snap.head, True
        else:
            ref: Ref | None = snap.ref(name)
            if ref is None:
                return
            title, kind, full, target = ref.short_name, KIND_LABELS[ref.kind], ref.name, ref.target
            is_head = ref.name == snap.head_ref
        t = Text()
        t.append(title, style="bold")
        if is_head:
            t.append("  (current HEAD)", style=REF_STYLES["head"])
        t.append("\n")
        t.append("Kind     ", style="bold")
        t.append(kind + "\n")
        t.append("Ref      ", style="bold")
        t.append(full + "\n")
        if self.is_ref_highlighted(name):
            t.append("New or moved since last refresh\n", style=HIGHLIGHT_STYLE)
        t.append("Tip      ", style="bold")
        t.append(f"{target}\n", style=HASH_STYLE)
        commit = snap.commit(target) if target else None
        if commit is not None:
            t.append(f"\n{commit.subject}\n")
            t.append(f"{commit.author_name} · {commit.author_date}\n", style="dim")
        else:
            t.append(f"\nTip commit is outside the loaded history ({self.max_commits} most recent commits).\n", style="dim")
        self._set_detail(t)

    def _jump_to_ref_tip(self, name: str | None) -> None:
        snap = self.snapshot
        if snap is None or name is None:
            return
        target = snap.head if name == DETACHED_KEY else (snap.ref(name).target if snap.ref(name) else None)
        if target and snap.commit(target) is not None:
            self.graph_table.move_cursor(row=self.graph_table.get_row_index(target), animate=False)

    # ------------------------------------------------------------------ events (R5)

    def action_toggle_panel(self) -> None:
        if self._branch_focused():
            self.graph_table.focus()
            self._show_commit(self.selected_commit)
        else:
            self.branch_table.focus()
            self._show_ref(self.selected_ref)
            self._jump_to_ref_tip(self.selected_ref)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._is_live():
            return  # event queued before shutdown; nothing left to update
        if event.data_table is self.graph_table:
            if not self._branch_focused():
                self._show_commit(self.selected_commit)
        elif event.data_table is self.branch_table and self._branch_focused():
            self._show_ref(self.selected_ref)
            self._jump_to_ref_tip(self.selected_ref)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self._is_live():
            return
        if event.data_table is self.branch_table:
            self._show_ref(self.selected_ref)
            self._jump_to_ref_tip(self.selected_ref)
