"""Pure comparison of two snapshots, used to highlight what is new (R8)."""

from __future__ import annotations

from dataclasses import dataclass

from gittree.gitdata import Snapshot


@dataclass(frozen=True)
class Changes:
    new_commits: frozenset[str] = frozenset()
    changed_refs: frozenset[str] = frozenset()  # refs that are new or now point elsewhere

    @property
    def is_empty(self) -> bool:
        return not self.new_commits and not self.changed_refs


def diff_snapshots(old: Snapshot | None, new: Snapshot) -> Changes:
    """What appeared in `new` that was not in `old`. Nothing is new on first load."""
    if old is None:
        return Changes()
    old_hashes = {c.hash for c in old.commits}
    new_commits = frozenset(c.hash for c in new.commits if c.hash not in old_hashes)
    old_targets = {r.name: r.target for r in old.refs}
    changed_refs = frozenset(r.name for r in new.refs if old_targets.get(r.name) != r.target)
    return Changes(new_commits=new_commits, changed_refs=changed_refs)
