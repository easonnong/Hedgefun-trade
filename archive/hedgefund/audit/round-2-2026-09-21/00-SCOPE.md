> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# 00-SCOPE — external audit, round 2

*Round 2 of an audit track numbered separately from [`AUDIT.md`](../../AUDIT.md). "Author round N" always
means one of theirs. See [`../README.md`](../README.md).*

## Why there is a round 2

[Round 1](../round-1-2026-09-21/00-SCOPE.md) audited `9a291aa`. The client asked a single question about
what came after it: **"he fixed some things — check."**

What came after is not a set of fixes. It is `2b6bfc1`, *"The pre-mainnet release: singleton hook, launch
window, partial-fill sells, token page, V3-only venue — audit rounds 5–7"*, plus `19d3faf` and `0e39f69`.

| | |
|---|---|
| Ref audited | **`0e39f69`** (`origin/main`) |
| Previous ref | `9a291aa` |
| Audited | 2026-09-21 |
| Deployment status | **still nothing deployed** — zero TVL, zero launches |
| Diff over `src/` | 10 files, **+1,102 / −707** |

```
StrategyHook.sol        837 lines changed   rewritten as a SINGLETON serving every strategy
StrategyFactory.sol     336
StrategyTreasuryBase    251
StrategyTreasuryV4.sol  DELETED (−145)      the V4 stock venue is gone; V3 only
StrategyToken.sol       124                 metadata, behind a new TokenDeployer
LaunchRouter 39 · StrategyTreasury 37 · PoolTrader 32 · TradeRouter 6 · TradingCalendar 2
```

Five mechanisms exist that did not exist at `9a291aa`, and **nothing outside the author's own rounds 5–8 had
looked at any of them**: the singleton hook with its shared per-stock `pots[]` RAY index and epoch-on-wipeout;
a buy-side launch window whose creator exemption lives in raw transient storage; `setVoteDelegate`, a new
owner power on a treasury that previously had no owner at all; partial-fill sells, which **deliberately
reverse** an invariant the previous version argued at length was mandatory; and token metadata behind a
`TokenDeployer`.

## On sequence, and what this report does not claim

Their commits are dated **2026-09-21 12:32–12:36 -0400**. Round 1's branch was pushed **02:33 -0700** the
same day, about seven hours earlier. `AUDIT.md:206` still records FA-1 as "fixed" and `docs/SECURITY.md:8`
still reads "No external security review has been done"; round 1's `audit/` directory is not on `main`.

**This report therefore makes no claim about cause.** Every disposition below is judged on the code. Where a
round-1 finding is closed, the change traces to the author's own `R5-*` ledger, and the report says so.

## Scope

In scope: everything in `src/` at `0e39f69`, the test suite as an object of review, and the disposition of
all 59 round-1 findings. Out of scope, unchanged from round 1: `lib/`, formal verification, gas optimisation,
the front end, and the Robinhood stock token itself — whose issuer can still upgrade all 194 tokens from one
code-less address with no timelock, which every conclusion here remains conditional on.

## Sizes — the binding constraint moved

`forge build --sizes`, EIP-170 limit 24,576.

| contract | runtime | margin | round-1 margin |
|---|---|---|---|
| **`TreasuryDeployer`** | 23,609 | **967** ← now the tightest in the system | 2,158 |
| `StrategyFactory` | 18,950 | 5,626 | **945** ← was the tightest |
| `StrategyHook` | 18,362 | 6,214 | 10,854 |
| `StrategyTreasury` | 18,381 | 6,195 | 7,372 |
| `TokenDeployer` | 9,327 | 15,249 | did not exist |
| `LaunchRouter` | 7,525 | 17,051 | 18,581 |

The singleton freed about 4.7 KB in the factory — round 1's headline constraint, that the recommended
factory-side fixes overflowed EIP-170 by 160 bytes, **is gone**. It was replaced: any treasury-side fix is
now scored against `TreasuryDeployer`'s **967 bytes**, because the deployer embeds the treasury's
22,809-byte init code. `StrategyTreasury`'s own 6,195 is not the number.

## Test state — measured, and the conclusion is not the obvious one

`forge test --no-match-path 'test/*Fork*'` on forge 1.8.1, two byte-identical checkouts:

| | path A | path B |
|---|---|---|
| result | 5 failed, 1102 passed | 6 failed, 1079 passed |
| tests that **ran** | 1107 | **1085** |

The sets differ, and a `setUp()` failure silently removes a whole contract's tests from the run — **22 tests
did not execute at path B and the totals moved without comment.**

**None of it is a product defect.** The whole red suite reduces to three things, all verified:

1. **One missing constructor argument in a test helper.** `StrategyToken` gained a fifth argument in this
   release; four of five mining helpers were updated and `test/InteractRuleMev.t.sol:152-153` was not — it
   hashes four arguments and deploys five, so the mining loop is a no-op and the token's side of the stock
   is decided by the metadata CBOR, i.e. by the checkout path. Adding `, address(0)` at `:153` gives
   **byte-identical results at two deliberately different paths: 1126 passed, 3 failed, 1130 ran.**
2. **A gas cap.** `test_holds_statefulCampaigns_…` needs 1,434,977,660 gas; forge 1.8.1's default test limit
   is 2^30 = 1,073,741,824. It **passes** with the limit raised. With (1) and (2): **1128 passed, 1 failed.**
3. **An obsolete harness control.** `test_holds_isolationIsReal_a_…` asserts that a *non-isolated* forge run
   leaks transient storage across top-level calls. Forge 1.8.1 no longer does — measured directly in a
   20-line standalone probe. Its twin `_b`, which asserts the *product* guarantee, passes.

CI pins `FOUNDRY_VERSION: v1.5.0`, so CI is green and none of this is visible to the team.

**Round 1's remediation no longer applies.** `bytecode_hash = "none"` was verified green at two red
checkouts of `9a291aa`; at `0e39f69` it is **not** the fix and applying it alone makes things worse — the
run shrinks from 1130 tests to 1108 and a `setUp()` still dies. It remains worth setting for reproducible
on-chain verification, which is a separate argument.

## Result

| | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|
| **new in round 2** | 0 | 0 | 0 | **4** | **4** |

Plus the disposition of round 1's 59: **6 worse, 28 still open, 3 changed shape, 3 fixed, 2 moot.**

See [`ISSUES.md`](./ISSUES.md). The two supporting reports are [`DISPOSITION.md`](./DISPOSITION.md) and
[`NEW-SURFACE.md`](./NEW-SURFACE.md).
