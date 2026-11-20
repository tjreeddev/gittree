"""Command-line entry point: `uv run gittree [PATH]` (R1, R10)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from gittree.gitdata import GitError, NotARepositoryError, open_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gittree",
        description="Read-only, live-updating, interactive Git commit tree for the terminal.",
    )
    parser.add_argument(
        "path",
        metavar="PATH",
        nargs="?",
        default=".",
        help="repository (or any folder inside one) to view; defaults to the current directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = open_repository(args.path)
    except NotARepositoryError:
        print(f"gittree: error: {args.path} is not inside a Git repository", file=sys.stderr)
        return 2
    except GitError as exc:
        print(f"gittree: error: {exc}", file=sys.stderr)
        return 2

    from gittree.app import GitTreeApp  # imported late so --help and errors stay fast

    GitTreeApp(root).run()
    return 0
