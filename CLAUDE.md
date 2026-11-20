# CLAUDE.md

## Project

gittree is a CSC299 command-line/TUI project: an interactive, live-updating, read-only Git commit tree
in the terminal. `spec.md` is the source of truth for requirements (R1–R10), approved defaults, and
acceptance criteria. `problem.md` is the original problem statement. Read `spec.md` before making changes.

## Stack

- Python 3.14
- Textual for the TUI
- uv for environment, dependencies, and running
- pytest (with Textual's Pilot for UI tests)

## Commands

- Run: `uv run gittree [PATH]` (PATH defaults to the current directory)
- Test: `uv run pytest`

## Hard rule: read-only (R9)

- The program must never modify the repository it views: no commit, merge, checkout or switch, stage,
  reset, branch or tag create/delete/move, fetch, gc, or any write under `.git` or the working tree.
- All git access goes through the single reader function in `gitdata`. Never call `git` anywhere else.
- That function runs only allowlisted read-only subcommands (`log`, `for-each-ref`, `rev-parse`, `show`,
  `cat-file`, read-only `symbolic-ref`) and always sets `GIT_OPTIONAL_LOCKS=0`.
- Do not use `git status` or other commands that may refresh the index or take locks.
- Tests may write to the temporary fixture repositories they create. Application code never writes.

## Approved defaults (do not change without asking)

- Load at most 1,000 most recent commits across `--all` refs.
- Show local branches, remote-tracking branches, tags, and HEAD (including detached HEAD).
- Separate branch-list panel; Tab switches focus between the graph and the branch list.
- Poll for repository changes every 0.5 seconds.
- Highlight new commits and refs for about 10 seconds.

## Scope for Round 1

Keep it small. Implement only what `spec.md` requires. Do not add GitHub integration, fetching,
staging, committing, merging, checkout, diffs, themes, search, configuration, or other extra features.

## Code conventions

- Keep `layout` and `diff` pure (no I/O) so they can be unit tested without git or a terminal.
- Model repository data as immutable snapshots.
- Write tests alongside each module; map each test to the requirement it verifies (R1–R10).
