> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# External audit track

> **Names, 2026-09-21.** These reports were written against `src/str/Strategy*.sol`. The tree has since become
> `src/` + `src/hooks/` + `src/interfaces/` + `src/libraries/` and the contracts `HedgeFun*` (`StrategyHook` ->
> `HedgeFunHook`, `LaunchRouter` -> `HedgeFunLaunchRouter`, and so on); selectors, events and errors did not change.
> The reports are left as written.

An audit track **separate from [`AUDIT.md`](../AUDIT.md)**, with its own numbering.

`AUDIT.md` records five rounds run by this repository's own author, working with Claude subagents. Every
commit in the repository is authored by that one person; `docs/SECURITY.md` states in its own words that
"No external security review has been done." Those rounds are thorough and this track does not replace them —
but five passes by one reviewer sharing one model of the protocol are not five independent confirmations, so
they are re-verified here rather than assumed.

To avoid the confusion of two things both called "round 3", this track numbers from 1 and always says
"author round N" when it means one of theirs.

## Rounds

| round | date | ref audited | deployment status | scope | result |
|---|---|---|---|---|---|
| [1](./round-1-2026-09-21/) | 2026-09-21 | `9a291aa` | **not deployed** | all 12 contracts in `src/` (2,965 lines), the test suite, and the five author rounds | **0 Critical, 2 High, 13 Medium, 26 Low, 18 Info** — [`ISSUES.md`](./round-1-2026-09-21/ISSUES.md) |
| [2](./round-2-2026-09-21/) | 2026-09-21 | `0e39f69` | **not deployed** | the `2b6bfc1` release — singleton hook, launch window, partial-fill sells, token page, V3-only venue — and the disposition of all 59 round-1 findings | **0 Critical, 0 High, 0 Medium, 4 Low, 4 Info** new; of round 1: 6 worse, 3 fixed — [`ISSUES.md`](./round-2-2026-09-21/ISSUES.md) |
| [3](./round-3-2026-09-27/) | 2026-09-27 | `03ad70e` (PR branch `codex/v2-main-integration`) vs `main` `7c3c137` | **v1 live, 9 strategies / 18 listings; v2 not deployed** | the nine new v2 contracts (~1,458 lines) — bonding curve, liquidity vault, factory, treasury, routers, deployers — plus ~55 changed lines in four already-deployed contracts, and the ten `docs/V2_*` documents | **0 Critical, 0 High, 6 Medium, 6 Low, 23 Info** — [`ISSUES.md`](./round-3-2026-09-27/ISSUES.md) |
| [4](./round-4-2026-09-27/) | 2026-09-27/28 | `5aedceb` (`codex/v2-strategy-engine` = PR #84 tip `9679614` + PR #91) | **v1 live, 9 strategies / 18 listings (round 3's read); v2 not deployed — no V2 `Defaults`, engine kind or policy on chain** | the bounded strategy engine (PR #91, ~870 lines — engine treasury, policy interface, rebalance policy, the deployer's policy registry), PR #84's ~40 changed source lines since round 3, and every round-3 finding re-graded at the tip | **0 Critical, 0 High, 3 Medium, 9 Low, 14 Info**; of round 3's: 3 Mediums fixed, 1 fixed for v2 with residue, 3 partially; 0 of 6 Lows addressed — [`ISSUES.md`](./round-4-2026-09-27/ISSUES.md) |

## How to read a round

Each round directory is self-contained and dated, and its first file is always `00-SCOPE.md`:

| file | what it answers |
|---|---|
| `00-SCOPE.md` | exactly which ref, what was deployed on the day, which chain readings and when, what is **not** covered |
| `ISSUES.md` | the graded findings, and the consolidated "checked and found safe" |
| `FINDINGS-FULL.md` | round 3 only: every finding written out, the binding rubric, the full safe list and the rejected list — triage's merged document, whose grades the later layers then moved |
| `README.md` | how the round was produced, and this round's own known weaknesses |
| `PRIOR-ROUNDS.md` | the five author rounds: every finding, its stated disposition, and whether that disposition holds at the audited ref |
| `VERIFICATION.md` | the adversarial pass over the findings, and a third-party review of this report's rubric and method written without the source. **Round 4 had neither**: its `VERIFICATION.md` is the reproduction guide and a record of what triage re-ran |
| `DISPOSITION.md` | round 2 only: every previous finding re-checked against the current code |
| `NEW-SURFACE.md` | round 2 only: the code that did not exist when the previous round ran |
| `lanes/` | round 4 only: the four lane reports in full, which are the evidence under every merged finding |
| `poc/` | runnable reproductions, with `run.sh`. Round 3 adds `poc/fork/`: chain-state **measurement probes** whose emitted tables are the evidence, asserting only on what is deterministic. Round 4 has one runner per lane, the claims lane's mutation diffs to `git apply` (`poc/claims/diffs/`), and two offline Python models (`poc/econ/`) |
| `pr-body.txt` | rounds 3 and 4: the pull request's description, as text to paste |

## Two rules that apply to every round here

**Severities are not comparable across reports, including with `AUDIT.md`.** Each round reproduces the rubric
it used. This track's rubric caps anything requiring manipulation of a long-window TWAP at High, and grades on
the state of a **launched** strategy rather than on whether a fix is still possible — so it cannot
structurally produce certain gradings, and a "Medium" here is not a "Medium" there.

**Every on-chain number carries the date it was read — including the ones a finding argues against.** Depth, liquidity, feed ages, Safe membership and
balances all move. Where a finding's severity turns on such a number, the number is dated in place and the
finding says so. Re-read before relying on any of them: active liquidity on the NVDA/USDG pool moved 60% in
twelve hours during this round.

That second half was learned the hard way in round 1: a finding compared a freshly measured pool depth against
a figure in the project's documentation whose own read date and method had not been checked. The finding
survived — the documented figure was wrong on the day it was written, verified against an archive node at the
project's own census block — but the comparison was not established until that check was done. A number you
are refuting needs a date as much as a number you are asserting.

## A third rule, learned in round 2

**A remediation is only verified against the ref it was verified on.** Round 1 measured a one-line fix for
its test-suite finding and confirmed it green at two checkouts of `9a291aa`. At `0e39f69` that fix is wrong
— the release introduced a second, different root cause on top of the first, and applying round 1's
remedy alone makes the suite *worse*. Re-test a carried-forward recommendation before repeating it.

## A fourth rule, learned in round 3

**A round's own baseline is on-chain data and decays like any other.** Round 3 opened by handing four lanes a
size table carried forward from round 2 without re-measuring: one contract's runtime size was 119 bytes stale
and another was missing entirely, so remediation budgets were being costed against the wrong numbers until a
lane caught it mid-round. The report criticises the project's documents for exactly this (M-5). Re-measure the
baseline against the ref being audited, not against the last report.

**And grade the fix path, not only the finding.** Round 3's Medium M-1 recommends a change to a contract whose
untested `onlyFactory` guard is filed as Info; the fix is what makes the Info matter. A reader triaging this
report by severity alone would take the Medium and skip the Info that the Medium walks into.

## A fifth rule, learned in round 4


**A test is a pin only if it fails when the guard is gone. Apply the mutation and run the test before calling it
one.** Round 4's claims lane shipped thirteen tests "that would have turned the green mutations red", and the
report told the fix branch to copy five of them. One pinned nothing: its policy proposed a buy too small to
execute, so with the nonce check deleted the engine still refused it — with the same error the test expected. It
passed with the guard and without it. Triage found it by applying the one-line mutation and running the test.

**And check what a bound multiplies.** The same round priced a worst day as `130 bps × maxTrade × prints/day` —
$1,300–$3,400 on a $10,000 treasury. The engine only trades back toward its target, so a price print forces a
trade the size of the move, not the size of the cap. The day was ≈ 0.08% of value, two orders smaller, and the
lane's own measured trade sizes said so.
