"""Read-only access to a Git repository.

This module is the ONLY place in gittree that runs git (R9). Every call goes
through `run_git`, which:

* only allows a fixed set of read-only subcommands,
* rejects the writing forms of `symbolic-ref`,
* always sets GIT_OPTIONAL_LOCKS=0 so git never takes optional locks or
  refreshes the index.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MAX_COMMITS = 1000

ALLOWED_SUBCOMMANDS = frozenset({"log", "for-each-ref", "rev-parse", "show", "cat-file", "symbolic-ref"})

# Config overrides that keep git's output predictable regardless of user config.
# `-c` only affects this single invocation and never writes any config file.
_SAFE_CONFIG = (
    "-c", "color.ui=false",
    "-c", "log.showSignature=false",
    "-c", "i18n.logOutputEncoding=UTF-8",
    "-c", "core.fsmonitor=false",
)

_FIELD = "\x1f"  # unit separator between fields of one commit
_RECORD = "\x00"  # NUL between commits (git log -z)


class GitError(Exception):
    """A git command failed or git is unavailable."""


class NotARepositoryError(GitError):
    """The given path is not inside a Git working tree."""


class ReadOnlyViolation(GitError):
    """Something tried to run a git command that could modify the repository."""


def _check_read_only(subcommand: str, args: tuple[str, ...]) -> None:
    if subcommand not in ALLOWED_SUBCOMMANDS:
        raise ReadOnlyViolation(f"git {subcommand} is not allowed: gittree is read-only")
    if subcommand == "symbolic-ref":
        # Read form only: `git symbolic-ref [-q] [--short] <name>`.
        if any(a in ("-d", "--delete", "-m") for a in args):
            raise ReadOnlyViolation("git symbolic-ref may only be used to read refs")
        positional = [a for a in args if not a.startswith("-")]
        if len(positional) != 1:
            raise ReadOnlyViolation("git symbolic-ref may only be used to read refs")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.pop("GIT_INDEX_FILE", None)
    return env


def run_git(root: str | os.PathLike[str], subcommand: str, *args: str, check: bool = True) -> str:
    """Run one read-only git command in `root` and return stdout.

    With check=False a failing command returns "" instead of raising.
    """
    _check_read_only(subcommand, args)
    cmd = ["git", "-C", str(root), *_SAFE_CONFIG, subcommand, *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_env(),
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found on PATH") from exc
    if result.returncode != 0:
        if check:
            raise GitError(f"git {subcommand} failed: {result.stderr.strip()}")
        return ""
    return result.stdout


# --------------------------------------------------------------------------- data model


@dataclass(frozen=True)
class Commit:
    hash: str
    parents: tuple[str, ...]
    author_name: str
    author_email: str
    author_date: str
    subject: str
    message: str

    @property
    def short_hash(self) -> str:
        return self.hash[:7]


@dataclass(frozen=True)
class Ref:
    name: str  # full name, e.g. refs/heads/main
    short_name: str  # e.g. main, origin/main, v1.0
    kind: str  # "local" | "remote" | "tag"
    target: str  # commit hash (annotated tags are peeled)


@dataclass(frozen=True)
class Snapshot:
    root: Path
    commits: tuple[Commit, ...]
    refs: tuple[Ref, ...]
    head: str | None  # commit HEAD points at, None for an unborn branch
    head_ref: str | None  # e.g. refs/heads/main, None when detached
    _by_hash: dict[str, Commit] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        self._by_hash.update({c.hash: c for c in self.commits})

    @property
    def detached(self) -> bool:
        return self.head is not None and self.head_ref is None

    def commit(self, hash_: str) -> Commit | None:
        return self._by_hash.get(hash_)

    def ref(self, name: str) -> Ref | None:
        return next((r for r in self.refs if r.name == name), None)

    def refs_at(self, hash_: str) -> list[Ref]:
        return [r for r in self.refs if r.target == hash_]


# --------------------------------------------------------------------------- loading


def open_repository(path: str | os.PathLike[str]) -> Path:
    """Return the root of the working tree containing `path`."""
    p = Path(path)
    if not p.is_dir():
        raise NotARepositoryError(f"{p} is not a directory")
    try:
        top = run_git(p, "rev-parse", "--show-toplevel").strip()
    except GitError as exc:
        if "not found on PATH" in str(exc):
            raise
        raise NotARepositoryError(f"{p} is not inside a Git repository") from exc
    if not top:
        raise NotARepositoryError(f"{p} is not inside a Git repository")
    return Path(top)


_REF_KINDS = (("refs/heads/", "local"), ("refs/remotes/", "remote"), ("refs/tags/", "tag"))


def load_refs(root: Path) -> tuple[Ref, ...]:
    out = run_git(
        root,
        "for-each-ref",
        "--format=%(refname)%00%(objectname)%00%(*objectname)",
        "refs/heads",
        "refs/remotes",
        "refs/tags",
    )
    refs = []
    for line in out.splitlines():
        if not line:
            continue
        name, obj, peeled = (line.split("\x00") + ["", "", ""])[:3]
        for prefix, kind in _REF_KINDS:
            if name.startswith(prefix):
                short = name[len(prefix):]
                break
        else:
            continue
        if kind == "remote" and short.endswith("/HEAD"):
            continue  # origin/HEAD is just an alias for the default remote branch
        refs.append(Ref(name=name, short_name=short, kind=kind, target=peeled or obj))
    return tuple(refs)


def load_head(root: Path) -> tuple[str | None, str | None]:
    head = run_git(root, "rev-parse", "--verify", "-q", "HEAD", check=False).strip() or None
    head_ref = run_git(root, "symbolic-ref", "-q", "HEAD", check=False).strip() or None
    if head is None:
        head_ref = None  # unborn branch: nothing to point at yet
    return head, head_ref


def load_commits(root: Path, refs: tuple[Ref, ...], head: str | None, max_commits: int) -> tuple[Commit, ...]:
    if not refs and head is None:
        return ()
    revs = ["--branches", "--remotes", "--tags"]
    if head is not None:
        revs.append("HEAD")
    fmt = _FIELD.join(["%H", "%P", "%an", "%ae", "%aI", "%B"])
    out = run_git(
        root,
        "log",
        "-z",
        "--topo-order",
        "--no-color",
        f"--max-count={max_commits}",
        f"--format={fmt}",
        *revs,
        "--",
    )
    commits = []
    for record in out.split(_RECORD):
        if not record.strip():
            continue
        parts = record.lstrip("\n").split(_FIELD)
        if len(parts) < 6:
            continue
        h, parents, an, ae, ad, body = parts[0], parts[1], parts[2], parts[3], parts[4], _FIELD.join(parts[5:])
        message = body.strip("\n")
        subject = message.splitlines()[0] if message else ""
        commits.append(
            Commit(
                hash=h,
                parents=tuple(parents.split()),
                author_name=an,
                author_email=ae,
                author_date=ad,
                subject=subject,
                message=message,
            )
        )
    return tuple(commits)


def load_snapshot(root: str | os.PathLike[str], max_commits: int = MAX_COMMITS) -> Snapshot:
    root = Path(root)
    refs = load_refs(root)
    head, head_ref = load_head(root)
    commits = load_commits(root, refs, head, max_commits)
    return Snapshot(root=root, commits=commits, refs=refs, head=head, head_ref=head_ref)


def fingerprint(root: Path) -> str:
    """A cheap string that changes whenever HEAD or any shown ref changes."""
    refs = run_git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/remotes", "refs/tags", check=False)
    head, head_ref = load_head(root)
    return f"{head}|{head_ref}\n{refs}"
