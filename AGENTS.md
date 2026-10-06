# Repository workflow

- Read `CONTRIBUTING.md` before creating branches or pull requests.
- Start new work from `main`. All branches use `<type>/<kebab-case-description>`.
  Do not add tool, agent, or author prefixes.
- PR titles use `<type>(<optional-scope>): <description>`; follow the types and
  examples in `CONTRIBUTING.md`. The `PR naming` status is required before merging.
- After a PR is merged, confirm GitHub removed its remote head branch. Prune
  remote-tracking references. Delete local branches only when their work is
  merged, they have no open PR dependencies, and no worktree has them checked out.
- Preserve uncommitted changes, unmerged commits, and other tasks' worktrees.
