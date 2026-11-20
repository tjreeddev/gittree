# gittree

An interactive, live-updating Git commit tree for the terminal. GitTree is strictly **read-only**: it never modifies your repository.

```
◆─╮    ddf6d4f  HEAD → main  tag: v1  Merge fix
│ ●    ad2b76d  fix  F
● │    c120105  G
◆─┼─╮  e1d42e8  Merge feat
│ │ ●  b17bcce  feat  E
● │ │  589dbd5  C
●─╯─╯  daa394f  B
```

## What it does

- Draws the repository's commits as a colored graph. Each line of history has its own lane, and forks and merges are drawn as connectors.
- Shows local branches, remote-tracking branches, tags and HEAD, both as labels on the graph and in a separate branch list.
- Shows details for the selected commit (hash, author, date, parents, refs, message) or branch (kind, tip, whether it is the current HEAD).
- Checks the repository every 0.5 seconds while running. When you commit, branch, merge, check out or tag in another terminal, the view updates by itself.
- Highlights new commits and new or moved refs for about 10 seconds.
- Loads the 1,000 most recent commits.
- Read-only: only allowlisted read-only git commands are run, always with `GIT_OPTIONAL_LOCKS=0`.

## Setup

Requires [uv](https://docs.astral.sh/uv/), git, and Python 3.14 (uv can install Python for you).

```
git clone <this repo>
cd gittree
uv sync
```

## Run

```
uv run gittree [PATH]
```

`PATH` is the repository (or any folder inside it) to view. It defaults to the current directory. To view another repository from this project folder:

```
uv run gittree C:\path\to\other\repo
```

## Controls

| Key | Action |
|---|---|
| `↑` / `↓` or `k` / `j` | Move up / down |
| `PgUp` / `PgDn` | Move one page |
| `Home` / `End` | First / last row |
| `Tab` | Switch between the commit graph and the branch list |
| `Enter` (branch list) | Select the branch and jump to its tip |
| `q` | Quit |

Moving the cursor in the branch list also moves the graph cursor to that branch's tip commit.

## Test

```
uv run pytest
```

The tests create temporary Git repositories and never touch your own repositories.
