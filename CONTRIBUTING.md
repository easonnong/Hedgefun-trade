# Contributing

Start new work from `main` and open a PR back to `main`. Use a short-lived branch
for each change. For stacked PRs, keep a base branch until its dependent PRs have
been retargeted or merged.

## Branch names

Use `type/kebab-case-description` for all contributors. Do not add tool, agent,
or author prefixes. Descriptions use lowercase letters, numbers, and single
hyphens. Do not use dates or PR numbers as the entire description.

Allowed types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`, `ci`,
`build`, `style`, `revert`.

Examples:

- `feat/treasury-upgrades`
- `fix/stock-buy-fee`
- `docs/testnet-runbook`

GitHub's branch naming ruleset allows new branches only under the listed type
prefixes, with one slash. The required PR check also validates the full lowercase
kebab-case description. All contributors and PRs follow the same convention;
there are no legacy branch-name exemptions.

## PR titles

Use `type(scope): description`. Scope is optional; `!` before the colon marks a
breaking change. Use the same types listed above, and a short lowercase scope
such as `v2`, `v2.1`, `testnet`, or `frontend`. Descriptions may be English or Chinese.

Examples:

- `feat(v2): add delayed treasury upgrades`
- `fix(testnet): correct venue owner checks`
- `docs: 更新测试网部署说明`
- `feat(v2)!: change treasury initialization`

Explain the resulting behavior and relevant validation in the PR description.
The required `PR naming` status checks both the head branch and title on PR
creation, title edits, reopening, and new commits. The workflow reads metadata
only and publishes the status on the PR head commit.

## Merge and cleanup

GitHub automatically deletes remote head branches after merging a PR. The
repository default branch is `main`. Keep branches with unmerged commits or open
PR dependencies; closing a PR without merging does not authorize discarding its
work. Retired work from branch cleanup is preserved under `archive/*` tags. To
resume archived work, create a standard feature branch from the relevant tag.

Refresh local remote references after merging:

```sh
git fetch origin --prune
```

Delete an unused local branch only after its work is merged and it is no longer
checked out in any worktree:

```sh
git branch -d branch-name
```

For squash or rebase merges, confirm the corresponding PR was merged and that
the branch has no newer commits before removing a local branch. Never discard
uncommitted changes or remove another task's active worktree during cleanup.
