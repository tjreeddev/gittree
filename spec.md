# gittree — Specification (Round 1)

## 1. Problem

Git commands can show branches, commits, merges, and history, but only as text output. gittree is an
interactive terminal (TUI) program that shows a local Git repository as a visual commit tree. It
updates live while the user runs Git commands in another terminal. The user can select branches and
commits to inspect them. The program is strictly read-only.

## 2. Approved decisions and defaults

| Topic | Decision |
|---|---|
| Language / runtime | Python 3.14 |
| TUI framework | Textual |
| Project tooling | uv |
| Launch command | `uv run gittree [PATH]` — `PATH` defaults to the current directory |
| Commits loaded | All refs (`--all`), capped at the **1,000 most recent** commits |
| Refs shown | Local branches, remote-tracking branches, tags, and HEAD (including detached HEAD) |
| Branch selection | Separate **branch-list panel**; Tab switches focus between graph and branch list |
| Change detection | Polling every **0.5 seconds** |
| New-item highlight | New commits and refs highlighted for **approximately 10 seconds**, then return to normal style |
| Git access | Completely read-only; every git call runs with `GIT_OPTIONAL_LOCKS=0` and goes through a subcommand allowlist |

## 3. Requirements and acceptance criteria

### R1. Open and read a local Git repository
- `uv run gittree` opens the repository containing the current directory; `uv run gittree PATH` opens the repository at or containing `PATH`.
- A path inside a repository (a subdirectory) resolves to the repository root.
- A path that is not in a Git repository causes a clear error message and a non-zero exit, with no traceback.
- A repository with no commits opens and shows an empty-state message instead of crashing.

### R2. Display commits as a visual tree
- Each loaded commit appears as one row in the graph, in topological order (children above parents).
- Each row shows a node glyph in its lane, the short hash, a one-line message summary, and any ref labels.
- At most 1,000 commits are loaded.

### R3. Branches as distinguishable lanes
- Git does not record which branch a commit "belongs to". Lanes are computed by a layout algorithm: each line of history gets a column (lane), and each lane gets a color.
- Diverging lines of history are drawn in different lanes with different colors.
- Lane colors stay stable for a given lane across redraws where possible.

### R4. Show relationships: splits and merges
- A commit with several children shows edges fanning out to each child's lane (a fork).
- A commit with two or more parents (a merge) shows edges from each parent's lane joining into it.
- Edges connect each commit to all of its parents within the loaded range.

### R5. Keyboard navigation and selection
- The graph panel has a cursor: Up/Down (and `j`/`k`) move one row; PageUp/PageDown move one page; Home/End jump to the first and last rows.
- The cursor cannot move past the first or last row.
- Tab switches focus between the graph panel and the branch-list panel.
- The branch-list panel lists local branches, remote-tracking branches, and tags, with the current HEAD marked, and supports the same up/down navigation.
- Selecting a branch in the branch list moves the graph cursor to that branch's tip commit.
- `q` quits.

### R6. Show information about the selection
- When a commit is selected, the detail panel shows: full hash, author name and email, author date, full commit message, parent hashes, and every branch, tag, or HEAD that points at it.
- When a branch is selected, the detail panel shows: branch name, kind (local / remote-tracking / tag), whether it is the current HEAD, and the tip commit's hash and message.

### R7. Automatic refresh
- While running, gittree polls the repository every 0.5 seconds for changes to HEAD and refs.
- When a change is detected (new commit, branch created, deleted, or moved, checkout, merge, rebase, tag added or removed), the snapshot is reloaded and the display redrawn without restarting.
- After refresh, the selected commit or branch stays selected if it still exists; otherwise the selection moves to a nearby valid row.
- Polling does not write to the repository (see R9).

### R8. Highlight new commits and branches
- On each refresh, the new snapshot is compared with the previous one to find commits that were not present before, and refs that are new or point at a different commit.
- These commits and ref labels are drawn with a distinct highlight style for approximately 10 seconds, then return to normal style.
- Nothing is highlighted on the first load.

### R9. Read-only
- gittree never commits, merges, switches branches, stages files, creates, deletes, or moves refs, fetches, or otherwise modifies the repository or its working tree.
- All Git access goes through one function that:
  - runs only allowlisted read-only subcommands (`log`, `for-each-ref`, `rev-parse`, `show`, `cat-file`, `symbolic-ref` in read form);
  - always sets `GIT_OPTIONAL_LOCKS=0` so that Git does not write `index.lock` or refresh the index;
  - rejects any other subcommand with an error.
- Commands that may write (for example `status`, `fetch`, `gc`) are not used.

### R10. Runs with one command
- After cloning the project, `uv run gittree [PATH]` starts the program on the user's computer. No other setup step is needed beyond having uv and git installed.
- `uv run gittree --help` prints usage and exits with status 0.

## 4. Architecture outline

| Module | Responsibility |
|---|---|
| `gitdata` | The only place that runs git. Read-only allowlist, `GIT_OPTIONAL_LOCKS=0`. Builds an immutable `Snapshot` (commits, refs, HEAD). |
| `layout` | Pure function: `Snapshot` → graph rows (lanes, edges, colors). No I/O. |
| `diff` | Pure function: (old `Snapshot`, new `Snapshot`) → new commit hashes and new or moved refs. |
| `watch` | Polls a cheap fingerprint of HEAD and refs every 0.5 s and triggers a reload on change. |
| `app` | Textual app: graph panel, branch-list panel, detail panel, footer with key help. |

## 5. Testing expectations

Tests use pytest and build temporary repositories with real `git` commands in fixtures.

| Req | Tests verify |
|---|---|
| R1 | Valid repo loads; subdirectory resolves to root; non-repo gives a clean error; empty repo works |
| R2 | A linear history of N commits gives N rows in topological order; the 1,000-commit cap is enforced |
| R3 | Two diverging branches get different lanes and colors |
| R4 | A fork gives one parent with two outgoing edges; a merge gives two incoming edges; parent lists are correct |
| R5 | Textual Pilot key presses move the cursor, stop at the bounds, Tab switches panels, selecting a branch jumps to its tip |
| R6 | The detail panel contains the expected hash, author, message, and ref names for a selected commit and branch |
| R7 | A commit, branch creation, or branch deletion made during the test is reflected within a timeout |
| R8 | The diff finds new commits and new or moved refs, and finds nothing on an unchanged repo; new rows get the highlight style, which expires |
| R9 | All files under `.git` are byte-for-byte identical (contents and mtimes) before and after a full session; the reader rejects non-allowlisted subcommands; every call sets `GIT_OPTIONAL_LOCKS=0` |
| R10 | `uv run gittree --help` exits 0; the `gittree` entry point is defined |

## 6. Out of scope for Round 1

GitHub or any remote integration, fetching, staging, committing, merging, checkout, branch management,
diffs or file contents, themes or configuration, search or filtering, mouse-specific features.
