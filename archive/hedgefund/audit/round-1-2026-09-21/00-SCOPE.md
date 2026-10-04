> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# 00-SCOPE — external audit, round 1

*This is round 1 of a **separate, externally-numbered** audit track. It does not continue the numbering in
[`AUDIT.md`](../../AUDIT.md), which records five rounds run by the repository's own author. Where this report
refers to those, it calls them "author round 1–5".*

## What was audited

| | |
|---|---|
| Repository | `keyuyuan/hedgefund` (private) |
| Ref | `9a291aa` — "TradeRouter audit (round 5)", `main` HEAD at clone time |
| Audited | 2026-09-21 |
| Deployment status | **Not deployed.** See below. |
| Toolchain | Foundry 1.5.x, solc 0.8.26, `optimizer = true`, `optimizer_runs = 1`, `evm_version = cancun`, `via_ir` off |

### In scope — 12 files, 2,965 lines

```
src/PoolTrader.sol            src/PriceOracle.sol           src/TradingCalendar.sol
src/str/LaunchRouter.sol      src/str/StrategyFactory.sol   src/str/StrategyHook.sol
src/str/StrategyToken.sol     src/str/StrategyTreasury.sol  src/str/StrategyTreasuryBase.sol
src/str/StrategyTreasuryV4.sol src/str/TradeRouter.sol      src/str/TwapRing.sol
```

`script/DeployStrategyLaunchpad.s.sol` is in scope as attack surface (what a typo does permanently), not as
deliverable code. `test/` is in scope as an object of review — whether the suite would catch a regression — rather than as
code to be audited for vulnerabilities in itself. Two findings about the suite are nevertheless graded on the
same severity scale as code defects, and the report says why in each case: a suite whose result depends on
where the repository is checked out, and one that cannot see a core accounting variable being short-changed,
are the mechanism by which an unpatchable contract ships with a defect. They are graded for that consequence,
not as bugs in test code.

### Explicitly NOT covered by this round

- `lib/` — Uniswap v4-core and OpenZeppelin are taken as given. Their *use* is audited; their internals are not.
- `tools/`, `data/`, `docs/band/`, `docs/rule-backtest/` beyond a methodology check of the backtests.
- `emergency/` — read for context, not audited.
- The Robinhood stock token itself and its issuer's powers. `docs/STOCK_TOKEN_ASSESSMENT.md` describes a
  `BeaconProxy` on one beacon whose upgrader is a single code-less address with no timelock. **This audit takes
  that as an unmitigated, external, unbounded risk and does not re-derive it.** Every conclusion here is
  conditional on the stock token continuing to behave as it does today.
- Formal verification, gas optimisation, and the off-chain front end.
- Fork tests were run against live chain state, not a pinned archive block; see the round README.

## Deployment reality — every number read on 2026-09-21

Read over `https://rpc.mainnet.chain.robinhood.com`, chain id **4663**, head block **68,625,197**.

**Nothing in this repository is deployed.** The addresses printed in `docs/DEPLOYMENT.md` come from a local
anvil fork run, and `cast code` returns empty for each:

| what `docs/DEPLOYMENT.md` calls it | address | `cast code` on 2026-09-21 |
|---|---|---|
| factory | `0x1E2e9190Cea3A97b5Aa85d9757117F499D31C47d` | empty |
| calendar | `0x52c9dE743a250a4D8E1194E11e447bb45324436f` | empty |
| oracle | `0x53DaB165b879542E9aDFC41c6474A9d797B9b042` | empty |

So: **zero TVL, zero users, zero launched strategies.** This is a pre-deployment audit, and no finding here
describes money currently at risk.

The intended protocol Safe **does** exist, and **the deployment document's description of it is already out of
date**:

| | `docs/DEPLOYMENT.md:99` (claim about 2026-09-20) | read on chain 2026-09-21 |
|---|---|---|
| address | `0x2910117dd2cB431173Ae9Fb6eAF30726321d1693` | same |
| owners | 3 | **4** — `0x6912…490b`, `0x719A…F13b`, `0xfE23…1BBA`, `0xF9D2…9692` |
| threshold | 2 of 3 | **2 of 4** |
| nonce | 0 | **1** |
| modules | none | none (confirmed) |

`0x719A8920bE95e1dffb73662730B8D3EF2FC3F13b` — the key the deployment document itself flags as heavily used and
also an owner of the market-making Safe — is still an owner. Two of four signatures reach every owner lever in
this protocol.

## Why severity is graded the way it is

Nothing is deployed, so nothing is at risk today. But **once a strategy is launched its three contracts can
never be changed**: no proxy, no owner on the token or the treasury, and the hook's owner reaches two payout
addresses and nothing else. A fix shipped after the first launch does not reach it. Severity is therefore
graded on **the state of a launched strategy**, not on "can this be fixed before mainnet" — the answer to that
is always yes, today, and will never be yes again for a strategy that already exists.

The full rubric is reproduced in [`ISSUES.md`](./ISSUES.md). Two counts are given there: the whole codebase,
and what is new relative to author rounds 1–5.

**This report's severities are not comparable with any other report's**, including `AUDIT.md`'s. The rubric
caps anything requiring manipulation of a long-window TWAP at High, so the report cannot structurally produce
certain gradings.

## Byte budget

`forge build --sizes`, 2026-09-21. The EIP-170 limit is 24,576.

**The number that constrains a fix is not always the contract's own.** `TreasuryDeployer`, `TreasuryV4Deployer`
and `HookDeployer` each embed the *creation code* of the contract they deploy, so a byte added to
`StrategyTreasury` is also a byte added to `TreasuryDeployer`'s runtime. Where the two differ, the deployer is
the binding one.

| contract | runtime | its init code | margin | binding margin for a fix here |
|---|---|---|---|---|
| `StrategyFactory` | 23,631 | 26,937 | 945 | **945** |
| `StrategyTreasury` | 17,204 | 21,581 | 7,372 | **2,158** — via `TreasuryDeployer` (22,418) |
| `StrategyTreasuryV4` | 14,532 | 17,916 | 10,044 | **5,823** — via `TreasuryV4Deployer` (18,753) |
| `StrategyHook` | 13,722 | 15,577 | 10,854 | **8,147** — via `HookDeployer` (16,429) |
| `TradeRouter` | 5,668 | 6,161 | 18,908 | 18,908 |
| `TradingCalendar` | 4,792 | 5,065 | 19,784 | 19,784 |
| `LaunchRouter` | — | — | — | ample |

Each deployer carries exactly one copy of the creation code, not two: 22,418 − 21,581 = 837 bytes of deployer
logic, and the same 837/852-byte gap appears for the other two pairs. `optimizer_runs` is already 1, so there
is nothing further to reclaim by tuning it. Every fix recommendation in `ISSUES.md` states which of these
budgets it spends.

## Result

See [`ISSUES.md`](./ISSUES.md) for the graded findings and [`README.md`](./README.md) for how they were
produced and what this round's method could not reach.
