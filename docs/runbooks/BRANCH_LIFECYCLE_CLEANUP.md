# Branch Lifecycle Cleanup

Use short-lived branches for the normal implementation loop:

1. Create a task branch from fresh `origin/main`.
2. Implement the slice.
3. Commit, push, wait for GitHub Actions.
4. Merge the PR.
5. Delete the local branch and stale worktree metadata.

## Guarded Local Cleanup

Always start with a dry run:

```powershell
py -3 scripts\cleanup_merged_branches.py --repo drsapaev/final --prune-worktrees
```

If local `main` is behind `origin/main`, fast-forward it explicitly:

```powershell
py -3 scripts\cleanup_merged_branches.py --repo drsapaev/final --prune-worktrees --sync-local-base
```

If the output only lists branches that should be removed, rerun with explicit
deletion:

```powershell
py -3 scripts\cleanup_merged_branches.py --repo drsapaev/final --prune-worktrees --delete
```

The script uses `origin/main` by default, not the local `main`, because local
`main` can be stale or checked out in another worktree. It also checks GitHub PR
state so squash-merged or rebase-merged branches can still be recognized as
complete.

The local base freshness check is intentionally separate from branch deletion:
`--sync-local-base` only fast-forwards local `main` when it has no local-only
commits and its worktree is clean. If local `main` has ahead commits or dirty
files, the script reports the problem and refuses to guess.

## Safety Rules

- Active worktree branches are never deleted.
- Local `main` freshness is checked against `origin/main` every run.
- Protected names such as `main`, `master`, `develop`, `staging`, and
  `production` are never deleted.
- Branches with no merged evidence are reported as kept.
- Graph-merged branches are removed with `git branch -d`.
- GitHub-confirmed merged branches use `git branch -D`, because squash/rebase
  merges may not be visible in the local commit graph.
