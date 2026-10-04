> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# 00-SCOPE — external audit, round 3: the v2 pull request

*Round 3 of an audit track numbered separately from [`AUDIT.md`](../../AUDIT.md). "Author round N" always
means one of theirs. See [`../README.md`](../README.md).*

## What was audited

| | |
|---|---|
| Branch | **`codex/v2-main-integration`**, head **`03ad70e`**, 39 commits ahead of `main` (`7c3c137`) |
| | It is the superset — `v2-lowfreq-fork`, `v2-profit-fork` and `v2-opening-tax` are all contained in it |
| Audited | 2026-09-27 |
| `src/` diff | **13 files, +1,513 / −22** |

**Nine contracts that did not exist before (~1,458 lines):** `HedgeFunV2TradeRouter` (282),
`HedgeFunBondingCurve` (218), `HedgeFunV2Treasury` (190), `HedgeFunV2Factory` (175), `V2LiquidityVault` (173),
`V2TreasuryDeployer` (154), `CurveDeployer` (125), `HedgeFunV2NativeRouter` (97),
`HedgeFunV2BuybackTreasury` (44).

**And ~55 lines in four contracts that are already deployed and immutable:** `HedgeFunFactory` (13),
`HedgeFunTreasuryBase` (29), `hooks/HedgeFunHook` (33), `HedgeFunTreasury` (2).

## The deployment reality, and the single most important scoping fact

**V1 is live.** Read on chain 2026-09-27: factory `0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961` has
**`strategyCount() == 9`**, **`publicLaunch() == true`**, and **18 stocks listed** (enumerated from 18
`Listed` events, all still enabled, block 73,816,151 — `docs/ADDRESSES.md` records twelve and is stale).

**Nothing in this PR can reach any of it, and no change in it implies a v1 redeployment.** V2 deploys
alongside v1 as a parallel lineage with its own factory, its own hook, its own deployers. Established three
independent ways and stated here because every severity depends on it:

- **`HedgeFunFactory` compiles byte-identically at `7c3c137` and `03ad70e`** — runtime 18,929, creation
  22,676. All four factory-side edits (the `lpFee` predicate, two new `pure` virtuals, `_terms` going
  `pure → view virtual`, `_openAndSeed`/`unlockCallback` going `virtual`) cost **zero bytes and change no
  behaviour**. The live factory verifies against this PR's source exactly as it verifies against main.
- `HedgeFunHook` grows **18,481 → 19,354 (+873)**, so v2 needs a new hook at a newly mined address, a fresh
  Uniswap routing-allowlist submission, and the live v1 hook cannot serve a v2 pool.
- `HedgeFunTreasury` grows +55, so its CREATE2 address moves; the live treasury `0xc218…4fe0` matches the
  **main** build and not this one.

If a v1 redeployment happened anyway: the nine live strategies **cannot migrate** — bind-once, `AlreadyWired`,
positions unmovable, and no migration primitive anywhere in `src/` — and the 18 listings would have to be
reconstructed from the event log and re-listed one at a time.

## The remediation budget — verified, and not what any contract's own size line says

Three different embedding patterns, each hiding the true cost of a fix behind a different contract. Measured
in clean builds at `03ad70e` and independently reproduced by two later layers.

| a fix here | is really scored against | bytes free |
|---|---|---|
| `HedgeFunV2Factory` | itself | **27** |
| `HedgeFunBondingCurve` **or** `V2LiquidityVault` | **`CurveDeployer`**, which embeds both initcodes (8,944 + 8,233 of its 24,400) | **176** |
| `HedgeFunV2Treasury` | itself — its 26,197 initcode is past EIP-170 and is stored in two chunks | 2,993 |
| `HedgeFunHook` | itself | 5,222 |
| `HedgeFunTreasury` (v1) | **`TreasuryDeployer`** | **1,020** |
| `HedgeFunFactory` (v1) | itself | 5,647 |

**Two of the six are effectively zero while the contract's own size line reads comfortable.** That is a fact
about the deployment, not about any one finding, and it is why it sits here rather than inside one.

## Test state — the first reading is a trap, and it is worth knowing why

`forge test` at `03ad70e` reports failures including
`"stop: refused with something other than NotDue/Unhealthy/Slippage/Cooldown (a panic?)"` and a
`panic: assertion failed (0x01)` in an invariant handler. Both read as rule regressions introduced by this
PR's edits to `HedgeFunTreasuryBase`. **They are not.** Run at `--gas-limit 9999999999` in separate scratch
checkouts of both refs, the stateful-campaign test **passes on `main` and on `03ad70e`**, and the invariant
contract is **47/47 on both**. The default 2^30 cap truncates a long run and surfaces a different assertion
depending on where it cuts.

Clean baseline, gas limit raised: **1,410 passed / 1 failed / 1 skipped**, the one failure being the obsolete
isolation-harness control. `foundry.toml` now sets `bytecode_hash = "none"` (round 2's recommendation landed);
**`gas_limit` still is not set**, which is why the trap is still armed — now on a PR large enough that a
reviewer would plausibly believe the first reading.

## Explicitly NOT covered

- **The v2 deployment configuration.** No v2 `Defaults` exist on chain. Four graded findings live inside
  parameters that have never been set. **This audit certifies no configuration**, and the one finding whose
  mechanism is most striking is conditional on one of them.
- **The deployment runbook**, the launch UI, the ABI/front-end surface, `script/TestRun.s.sol`, and the
  owner's operational procedures. One Info touches the runbook; nothing else does.
- The live-venue fork suites (`RH_FORK=1` + an archive RPC), so the author's "13/13" fork claims are
  UNMEASURED here.
- `lib/`, formal verification, gas optimisation, and the Robinhood stock token itself — whose issuer can
  still upgrade all 194 tokens from one code-less address with no timelock. Every conclusion is conditional
  on today's implementation.

## Result

| | Critical | High | Medium | Low | Info | total |
|---|---|---|---|---|---|---|
| **everything in the PR** | **0** | **0** | **6** | **6** | **23** | **35** |
| only new in `src/v2/` | 0 | 0 | 4 | 4 | 8 | 16 |

See [`ISSUES.md`](./ISSUES.md). How it was produced and what was corrected along the way:
[`README.md`](./README.md). The adversarial pass and the no-source review of this report's own rubric, in
full: [`VERIFICATION.md`](./VERIFICATION.md). The runnable reproductions: [`poc/run.sh`](./poc/run.sh),
32 tests, no network; and [`poc/fork/run-fork.sh`](./poc/fork/run-fork.sh), which re-measures the live
pools behind M-2 and M-3. All 35 findings written out, with the binding rubric, the 75-item safe list and
the rejected list: [`FINDINGS-FULL.md`](./FINDINGS-FULL.md).
