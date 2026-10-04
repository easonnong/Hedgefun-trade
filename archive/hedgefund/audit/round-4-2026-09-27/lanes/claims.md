> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Claims lane — external audit round 4: the bounded strategy engine

**Audited tip** `codex/v2-strategy-engine` @ `5aedceb` (= PR #84 `codex/v2-main-integration` @ `9679614` + PR #91
"bounded strategy engine"). Audited 2026-09-27/28. Round 3's claims lane checked the ten `docs/V2_*.md`; this
lane checks the documents and PR bodies that the delta added or touched: `docs/STRATEGY_ENGINE.md`, PR #91's
description, PR #84's description and its last three commit messages (`d5218ee`, `0d9fca8`, `9679614`), the
delta's edits to `docs/V2_BONDING_CURVE.md` and `docs/V2_DUAL_ENGINE_REVIEW.md` (and the numbers the same
commits put in `DEVELOPMENT.md`, `V2_PROFIT_FORK.md`, `V2_ADVERSARIAL_REVIEW.md`), `abi/SURFACE.md`,
`docs/REFERENCE.md` and the engine's own NatSpec.

**Method.** Every claim is one sentence with its source. A guard or limit is checked by *mutation*: delete or
invert it, run the suite, record whether anything noticed, restore. A number is re-measured on a clean build of
the ref it is quoted for. Everything else is checked by reading, and says so. The 41 mutations, the two full-suite
control runs and every diff are in [`../poc/claims/mutations.md`](../poc/claims/mutations.md) (the diffs also ship as
files under [`../poc/claims/diffs/`](../poc/claims/diffs/) for `git apply`); the 13 tests that
would have turned the green mutations red are in [`../poc/claims/AuditClaims4.t.sol`](../poc/claims/AuditClaims4.t.sol)
and run with `../poc/claims/run.sh` (no network; all 13 pass on the unmutated tip).

**Verdicts.** SUPPORTED — a test fails when the property is broken, or the code plainly enforces it (marked
"(code)" when no test pins it). NARROWER — true, but for less than the sentence says. UNSUPPORTED — the code does
it, and no test would notice if it stopped. CONTRADICTED — the code or the measurement says something else.
UNMEASURED — needs a fork RPC this lane did not use.

## Counts

| | SUPPORTED | NARROWER | UNSUPPORTED | CONTRADICTED | UNMEASURED | total |
|---|---|---|---|---|---|---|
| claims | **46** | **10** | **10** | **5** | 2 | **73** |
| mutations that left the suite green / red | | | **22 green** | | | 41 (+2 controls) |

The two headline numbers of PR #91 — 104 suites / 1,474 passed / 0 failed / 52 skipped, and the engine at
21,574 / 27,866 bytes — reproduce exactly, as do the lab count, the link count, the regenerated reference and the
regenerated ABI. **PR #84's description does not reproduce at its own tip on either of its two numbers** (C-6), and
the delta left `V2_BONDING_CURVE.md`'s size table one contract stale and two contracts short (C-7).

The pattern in the engine is the same one round 3 found in the vault: the documented security model is fully
implemented and about half of it is pinned by no test. Of the twelve execution-time checks `STRATEGY_ENGINE.md`
¶2 lists, **five can be deleted with every test green** (nonce, execution-time codehash, gas bound, capability,
direction) and a sixth (oracle and venue health) with the invariant suite green too. The three new owner-only registry
entry points and `deploy()`'s factory-only guard are likewise unpinned. None of this is exploitable today — every
guard is present — and all of it is one refactor away from silently not being.

---

## The claims

Mutation names (`E01` …) refer to `mutations.md`; PoC names (`C1` …) to `AuditClaims4.t.sol`. Line numbers are
at `5aedceb`. `E` = `src/v2/HedgeFunV2EngineTreasury.sol`, `D` = `src/v2/V2TreasuryDeployer.sol`,
`V` = `src/v2/V2LiquidityVault.sol`.

### `docs/STRATEGY_ENGINE.md`

| # | claim (source line) | verdict | evidence |
|---|---|---|---|
| K-1 | A registered policy can return only one fixed-width intent: hold, buy stock, or sell stock, plus a next-state word (¶1) | SUPPORTED | `E05` RED (exact 160-byte return; `test_hugePolicyReturndata…`); a `BuybackBurn` intent reverts `BadIntent` at `E:318` |
| K-2 | It cannot choose a pool, route, recipient, approval, callback, calldata or asset (¶1) | SUPPORTED (code) | `StrategyIntent` carries none of these (`IStrategyPolicy.sol:51-57`); execution is the inherited `_swapStock` on the bound V3 pool (`HedgeFunTreasury.sol:138`) |
| K-3 | On every execution the engine checks the domain-separated launch config hash (¶2) | SUPPORTED | `E02` RED — `test_wrongCommitmentAndExcessiveAmountBothFailClosedAtTheCore` |
| K-4 | … and the current strategy nonce (¶2) | **UNSUPPORTED** | `E01` GREEN (subset and full suite). `WrongNonceStrategyPolicy` exists in the mocks and is exercised only by the fixture test, never against the engine. PoC `C1` → C-1 |
| K-5 | … the registered policy runtime code hash (¶2) | NARROWER | Pinned at configuration time (`D09` RED — `test_policyCodeReplacementFailsBeforePredictionOrLaunch`) but not at execution time: `E03` GREEN deletes `E:394`. PoC `C2` → C-1. Note: on a Cancun chain (`evm_version = cancun`) the runtime code of a deployed contract cannot change after its creation transaction (EIP-6780), so the execution-time re-check guards a path that is not reachable there |
| K-6 | … call gas (¶2) | **UNSUPPORTED** | `E04` GREEN replaces `staticcall(gasLimit, …)` with `staticcall(gas(), …)`; `GasBombStrategyPolicy` is never launched into an engine. PoC `C3` → C-1 |
| K-7 | … and exact 160-byte return size (¶2) | SUPPORTED | `E05` RED |
| K-8 | … live oracle and venue health (¶2) | **UNSUPPORTED** | `E06` GREEN (drop `if (!ok) revert Unhealthy()` at `E:253`) and `E07` GREEN (drop `if (!live) revert Unhealthy()` at `E:255`), **including the invariant suite** whose handler shoves the venue, pauses the oracle and makes the feed stale. The venue-deviation case is partly masked by the swap's own 1% slippage bound; a 0.6% deviation (past the 50 bps gate, inside the bound) executes under the mutation. PoC `C13` → C-2. The `live` limb is only reachable with `bandBpsPerHour > 0` during a scheduled closure; no PoC written |
| K-9 | … policy capability (¶2) | **UNSUPPORTED** | `E08` GREEN deletes both capability tests at `E:328,348`; no test launches a SELL-only policy that proposes a BUY. PoC `C4` → C-1 |
| K-10 | … cooldown (¶2) | SUPPORTED | `E09` RED — `test_cooldownAndDailyCapUseCumulativeActualTurnover` |
| K-11 | … target/deadband direction (¶2) | **UNSUPPORTED** | `E10` GREEN deletes `stockValueUsdg <= upperValue` / `>= lowerValue`; a sell proposed inside the deadband (53% against a 50±5% band) executes. PoC `C5` → C-1 |
| K-12 | … per-call notional (¶2) | SUPPORTED | `E11` RED (2 tests) |
| K-13 | … and daily turnover (¶2) | SUPPORTED | `E12` RED |
| K-14 | … actual swap input/output, including the minimum executable lot, before committing inventory, turnover, state or nonce; a price-limit dust fill reverts atomically and cannot renew the cooldown (¶2) | SUPPORTED | `E13` RED (4 tests, including the invariant replay), `E23` RED (`testFuzz_shortSellFillUsesOnlyActualInput`) |
| K-15 | The config is appended to initcode, so changing it changes the CREATE2 treasury address and therefore the factory terms (¶3) | SUPPORTED | `test_registryAndCreate2BindTheExactCorePolicyAndConfig`, `test_engineSelectionRestatesQuote…`; `D:331-356` appends the 192-byte `abi.encode(config)` |
| K-16 | Engine kinds and policy registrations are append-only (¶3) | SUPPORTED (code) | No update or delete path exists; `_kinds.push` only (`D:187,204`); a policy key is the hash of its whole manifest. The duplicate-key guard itself is unpinned (`D10` GREEN) → C-10 |
| K-17 | Disabling a policy prevents new predictions/launches but cannot rewrite an already deployed treasury (¶3) | NARROWER | `test_policyDisableBlocksFutureLaunches…` covers a *new configuration* after the disable and the treasury's immutables. For a salt configured *before* the disable, both checks that block its launch (`D:347` and `E:133`) can be deleted together with the suite green (`E24` GREEN). PoC `C7` → C-5 |
| K-18 | The treasury stores its policy identity and limits as immutables (¶3) | NARROWER | Identity fields are `immutable` (`E:34-39`); the limits live in `_engineConfig`, a private storage struct written once in the constructor with no setter (`E:33,96`) → C-11 |
| K-19 | The factory's `V2TreasuryDeployer` reference is immutable (¶4) | SUPPORTED (code) | `HedgeFunFactory.sol:122` `immutable treasuryDeployer`; `BoundDeployer.bind()` is once-only |
| K-20 | A pre-registry PR84 factory cannot acquire these engine APIs later through `registerKind` (¶4) | SUPPORTED | `registerKind` stores schema 0 (`D:187`); `setEngineConfig` refuses schema-0 kinds (`D:308`) and `setStrategyKind` refuses engine kinds (`D11` RED); the PR84 deployer bytecode has no engine entry point at all |
| K-21 | Runtime codehash binding detects code replacement but cannot prove an implementation does not read mutable storage or delegate through a proxy (Policy admission) | SUPPORTED | `test_fixture_codehashDoesNotCommitMutableStorageSemantics`, `test_fixture_proxyCodehashDoesNotCommitImplementation`; detection: `D09` RED |
| K-22 | `maxDailyTurnoverUsdg` is a UTC-aligned epoch limit (`block.timestamp / 1 days`), not a rolling window | SUPPORTED | `E:296`; `test_cooldownAndDailyCap…` warps to the next UTC day and asserts the reset |
| K-23 | The cooldown remains active across the epoch boundary | SUPPORTED (code) | `E:295` is independent of `E:296`; no repository test pins it (the handler's `advanceEpoch` always warps past the cooldown). PoC `C8` pins it |
| K-24 | Stock or USDG sent directly is an irrevocable donation, becomes part of the next observation, and remains subject to the same limits | NARROWER | Irrevocable: no withdraw path in the ABI. Booking is tested through an explicit `book()` (`test_donationBooksExactlyOnce…`); `execute()`'s own `_bookInventory()` at `E:251` can be deleted with the suite green (`E20` GREEN), so "part of the *next* observation" is not pinned → C-10 |
| K-25 | The spot engine rejects all option capability bits; registering an options policy against it must fail before a treasury can launch (Options extension) | SUPPORTED | `E15` RED (3 boundary tests), `D08` RED (2) |
| K-26 | A release policy must be stateless and non-proxy; governance must reject mutable and proxy policies (Policy admission) | SUPPORTED as stated | The document says the code cannot enforce this, and it cannot (K-21). `V2RebalancePolicy` declares no storage |
| K-27 | The policy is called with `STATICCALL` (engine NatSpec `E:19`; PR #91) | SUPPORTED | `E19` RED — `test_staticcallTrapsPolicyStateWrites` |
| K-28 | The engine rejects a malformed config at construction: deadband ≥ target, target + deadband ≥ 10000, cooldown 0, maxTrade 0 or > `sellChunkUsdg`, maxDaily < maxTrade (`E:137-139`; REFERENCE `BadEngineConfig`) | **UNSUPPORTED** | Only the reserved-bits limb is pinned (`E16` RED); all six bounds delete together with the suite green (`E17` GREEN). PoC `C12` → C-4 |

### PR #91 description

| # | claim | verdict | evidence |
|---|---|---|---|
| K-29 | Policies are advisory `STATICCALL`s with pinned runtime codehash, gas, and exact returndata bounds | NARROWER | STATICCALL and returndata pinned (K-27, K-7); codehash pinned at configuration only (K-5); gas not pinned (K-6) |
| K-30 | The engine independently checks config/nonce commitments, oracle and venue health, direction, cooldown, per-call size, UTC epoch turnover, and actual fills | NARROWER | Config hash, cooldown, per-call, epoch and fills pinned; nonce, health and direction not (K-4, K-8, K-11) |
| K-31 | Actual turnover below `minLotUsdg` reverts atomically, so a price-limit dust fill cannot advance nonce/policy state or renew cooldown | SUPPORTED | = K-14 |
| K-32 | Dedicated stateful invariants cover donations, 499/500 bps fills, partial fills, 59/60/61-second cooldown edges, UTC rollover, stale-feed recovery, oracle pause, venue deviation, bucket solvency, failure atomicity, and an independent ghost turnover ledger | NARROWER | The handler performs every listed action (`V2StrategyEngineInvariant.t.sol:57-103`). The four invariants assert consistency — nonce = successes, buckets ≤ balance, turnover ≤ cap, digest unchanged on failure — and nothing about the *gates*: `E06`/`E07` pass the invariant suite. "Oracle pause / venue deviation / stale feed" are covered as things the engine survives, not as things that stop it → C-12 |
| K-33 | Foundry 1.5.0 / solc 0.8.26: 104 suites, 1,474 passed, 0 failed, 52 RPC-gated fork tests skipped | SUPPORTED | Reproduced exactly (`forge test --summary`, 2026-09-27). All 52 skip reasons name `RH_FORK` |
| K-34 | Python lab: 30 passed | SUPPORTED | `python3 -m pytest lab -q`: 30 passed |
| K-35 | Strategy invariant suite: 4 invariants × 256 runs × 500 calls, plus directed boundary coverage; 0 handler reverts | SUPPORTED | `forge config`: `invariant.runs = 256`, `depth = 500` (defaults; `foundry.toml` sets neither); four `invariant_*` functions, each `fail-on-revert = true`; suite green |
| K-36 | Generated docs: 369 links checked and `docs/REFERENCE.md` matches source | SUPPORTED | `tools/check_docs.py --links`: 369 relative links in 51 files; `gen_reference.py --stdout` at `5aedceb` is identical to the committed file except the commit line |
| K-37 | Generated ABI export reproduced byte-for-byte | SUPPORTED | `tools/export_abi.py` at `5aedceb`: all 17 JSON files byte-identical; `SURFACE.md` identical except its commit line, which records `7027539` (see K-65) |
| K-38 | Engine runtime/initcode: 21,574 / 27,866 bytes (3,002 / 21,286-byte margins) | SUPPORTED | `forge build --sizes` at `5aedceb`: 21,574 / 27,866 / 3,002 / 21,286 |
| K-39 | Options, buyback and unknown capabilities are rejected by this spot engine | SUPPORTED | = K-25; `E15` RED includes the buyback and the `1 << 68` cases |
| K-40 | Preserves legacy kind 0 / kind 1 behaviour | SUPPORTED (weak) | `V2StrategyKindsTest` (6) and `V2BuybackKindTest` pass; the delta's only kind-0 change is the appended `Action` values; `D11` RED keeps the legacy setter off engine kinds |
| K-41 | The factory's treasury deployer is immutable and binds once; the pre-registry PR #84 bytecode cannot be upgraded in place | SUPPORTED | = K-19, K-20 |
| K-42 | Engine, policy and deployer ABI surfaces exported and included in the generated reference | SUPPORTED | `abi/SURFACE.md` §HedgeFunV2EngineTreasury / V2RebalancePolicy / V2TreasuryDeployer; `docs/REFERENCE.md` sections present |
| K-43 | Foundry 1.5.0 / solc 0.8.26 | SUPPORTED | `forge 1.5.0-stable`; `solc_version = "0.8.26"` |

### PR #84 description and its last three commits

| # | claim | verdict | evidence |
|---|---|---|---|
| K-44 | `forge test`: 1,399 passed, 0 failed, 51 intentionally skipped | **CONTRADICTED** | Clean build of `9679614` (the PR's own head): **98 suites, 1,422 passed, 0 failed, 52 skipped** (1,474 tests). The body predates its last three commits and was not updated → C-6 |
| K-45 | V2 Factory runtime is 24,433 bytes, 143 bytes below the EIP-170 limit | **CONTRADICTED** | `forge build --sizes` at `9679614` and at `5aedceb`: **24,551 bytes, 25 free**. The documents the same PR ships say 25 (K-51); round 3 I-13 had already flagged 143 vs 27 → C-6 |
| K-46 | The real stock reserve funds LP and the strategy treasury in a 50/50 split | NARROWER (stale) | `lpBps` per stock, 10–100%, default 50% (`D:106-107`); round 3 M-6; `V2_BONDING_CURVE.md` and `V2_DUAL_ENGINE_REVIEW.md` now say so, the PR body does not → C-11 |
| K-47 | Pinned Robinhood fork: 13/13 low-frequency replays passed | UNMEASURED | 13 test functions exist in `test/V2LowFrequencyFork.t.sol`; all skip without `RH_FORK=1` and an archive RPC |
| K-48 | The final strategy path is a single atomic `execute()`: due stop-loss lots first, no dip buy while any due lot remains (including partial fills), price rechecked before a possible buy | SUPPORTED (code) | `HedgeFunV2Treasury.sol:84-124`, unchanged by this delta; round 3 scope |
| K-49 | `0d9fca8` "isolate LP fee legs" | SUPPORTED | `V01` RED (`test_stockCreditFailureParksFeeButStillBurnsTokenFee`), `V02` RED (caught by `testFuzz_threeActorSequencesConserveBeforeAndAfterGraduation` in `V2AdversarialTrading`), `V03` RED |
| K-50 | `0d9fca8` "keep buybacks at flat sell tax" | SUPPORTED | `F01` RED — six tests across `V2Factory`, `V2DualEngine`, `V2BuybackKind` and the market scenarios |
| — | `d5218ee` "harden PR84 strategy launch and fork gates", `9679614` "align evidence and launch checks with fee fixes" | not checkable | No property stated. The evidence they "align" is checked as K-44/K-45/K-63/K-64 |

### `docs/V2_BONDING_CURVE.md` (lines the delta touched)

| # | claim | verdict | evidence |
|---|---|---|---|
| K-51 | The factory sits 25 bytes under EIP-170; the CurveDeployer has 12 | SUPPORTED | 24,551 / 25 and 24,564 / 12 at `5aedceb` |
| K-52 | The size table (eight V2 contracts, runtime and initcode) | **CONTRADICTED** (one row), incomplete | `V2TreasuryDeployer` is listed at 4,773 / 31,947; at the tip it is **10,737 / 38,024** (the registry added 5,964 runtime bytes in PR #91 and the table was not regenerated). `HedgeFunV2EngineTreasury` (21,574 / 27,866) and `V2RebalancePolicy` (1,799 / 1,827) are absent. The other seven rows reproduce, the curve's initcode (8,944) re-measured with `forge inspect` since `--sizes` omits it → C-7 |
| K-53 | Graduated V2 pools freeze `spikeBps = 0`, so buyback notifications cannot turn trading volume into a repeated sell spike | SUPPORTED | `F01` RED; `V2BuybackKind.t.sol:70` asserts `sellRateBps` stays at the flat rate after a buyback |
| K-54 | If the issuer or treasury rejects stock delivery after V4 collection, the vault keeps that fee and retries it on the next `collectFees()`; the token burn still completes | SUPPORTED | `V01` RED; `V02` RED (the "and clears it once delivered" half, caught by an adversarial fuzz, not by the vault's own unit tests — PoC `C11` pins it directly) |
| K-55 | A stock transfer refused inside V4's `take` still reverts that collection transaction | SUPPORTED (code) | `V:169-175` has no `try`; a refusal inside `unlock` propagates. No test |
| K-56 | Kind 1 is opt-in and production registration requires a separate Safe transaction; this release registers only kind 0 | SUPPORTED | Constructor pushes kind 0 only (`D:129-133`); `test_shippedTreasuryIsKindZeroAndNeedsNoCall` |
| K-57 | A buyback call still reverts `NotDue` if the impact-bounded fill is below `minLotUsdg` | SUPPORTED (code) | `HedgeFunTreasuryBase.sol:479`; round 3 M-0 measured the carve-out on that line |
| K-58 | The fixed-block live-venue test covers kind-1 registration, selection, graduation and buyback against the real USDG/GME contracts | UNMEASURED | `test_fork_kindOneRegistersLaunchesGraduatesAndBuysBackOnLiveVenue` exists (`V2LiveVenueFork.t.sol:399`); skipped here |

### `docs/V2_DUAL_ENGINE_REVIEW.md` and the other documents the same commits touched

| # | claim | verdict | evidence |
|---|---|---|---|
| K-59 | `floor(reserve · lpBps / 10000)` is the V4 stock budget; the owner sets `lpBps` per stock, 10–100%, default 50%, frozen per treasury | SUPPORTED | `D:106-123`; `V2LpShareTest` (2) |
| K-60 | Graduated V2 rates freeze `spikeBps = 0`; V1's existing hook behaviour is unchanged | SUPPORTED | The freeze is in `HedgeFunV2Factory.sol:106`; the hook diff in these commits is one comment line |
| K-61 | The kind-1 fork case uses a 0.25 USDG test minimum lot | SUPPORTED | `V2LiveVenueFork.t.sol:121` `minLotUsdg = 250_000` |
| K-62 | (`V2_ADVERSARIAL_REVIEW.md`) the live-venue fork suite has 4 cases | SUPPORTED | 4 test functions |
| K-63 | (`V2_PROFIT_FORK.md`) 1,422 passed / 0 failed / 52 skipped in the offline profile | SUPPORTED | Reproduced at `9679614` |
| K-64 | (`DEVELOPMENT.md`) `forge test`: 1,420 passed, 0 failed, 51 skipped (1,471 tests, 98 suites) | **CONTRADICTED** | 1,422 / 0 / 52 / 1,474 / 98 at `9679614`; 1,474 / 0 / 52 / 1,526 / 104 at `5aedceb`. Three different counts for one tip inside one PR (K-44, K-63, K-64) → C-6 |

### `abi/SURFACE.md`, `docs/REFERENCE.md`, NatSpec

| # | claim | verdict | evidence |
|---|---|---|---|
| K-65 | "Generated by `tools/export_abi.py` at commit `7027539`" / "Generated from commit `7027539…`" | NARROWER | The audited tip is the merge `5aedceb`; regenerating there reproduces every table and file, only the commit line differs → C-11 |
| K-66 | SURFACE lists `buyDip()`, `stopLoss(uint256)`, `takeProfit(uint256)` under `read` for the engine | NARROWER | They are `pure` and always revert `UseExecute` (REFERENCE says so); a front end reading SURFACE alone would offer them as reads → C-11 |
| K-67 | REFERENCE: `HedgeFunV2Treasury.Action` is `0`..`4` with `RebalanceBuy`, `RebalanceSell` appended | SUPPORTED | `HedgeFunV2Treasury.sol:29` |
| K-68 | REFERENCE: `execute()` — anyone, `nonReentrant` | SUPPORTED | `E:250` |
| K-69 | REFERENCE: `registerPolicy`, `registerEngineKind`, `disablePolicy` revert `NotOwner` for a non-owner; `deploy` reverts `NotFactory` for a non-factory | **UNSUPPORTED** | `D01`, `D02`, `D03`, `D05` GREEN (D01 also under the full suite). Only the legacy `registerKind` is pinned (`D04` RED). PoCs `C9`, `C10` → C-3 |
| K-70 | REFERENCE: `creditLiquidityFee` reverts `NotFactory` if `msg.sender != liquidityVault` | **UNSUPPORTED** | `T01` GREEN; the only test pranks *as* the vault → C-9 |
| K-71 | Mock NatSpec: "A spot engine must reject this raw action word before attempting an enum ABI decode"; engine range check `uint8(intent.action) <= BuybackBurn` (`E:376`) | **CONTRADICTED** | `abi.decode` at `E:407` validates the enum first and reverts with *empty* data; `_basicIntentValid` never sees the word. `E18` GREEN deletes the check with no observable change. PoC `C6` → C-8 |
| K-72 | `deploy()` re-verifies the deployed engine's version, policy id and config hash (`D:380-388`) | UNSUPPORTED (defensive) | `D06` GREEN; the constructor already fails the launch for every case the introspection would catch → C-10 |
| K-73 | `registerPolicy` enforces `maxGas ≤ 500,000`, `maxReturnBytes == 160`, non-zero manifest hashes and non-zero policy metadata (`D:219-237`) | UNSUPPORTED (defensive) | `D07`, `D12` GREEN; the engine constructor re-checks gas and return size (`E:134-135`) → C-10 |

---

## The numbers, re-measured

| quoted | where | measured | at |
|---|---|---|---|
| 104 suites, 1,474 passed, 0 failed, 52 skipped | PR #91 | **104 / 1,474 / 0 / 52** | `5aedceb` |
| 30 lab tests | PR #91 | **30 passed** | `5aedceb` |
| 369 links | PR #91 | **369** in 51 files | `5aedceb` |
| engine 21,574 / 27,866, margins 3,002 / 21,286 | PR #91, REFERENCE | **21,574 / 27,866 / 3,002 / 21,286** | `5aedceb` |
| 1,399 passed, 51 skipped | PR #84 body | **1,422 / 52** (98 suites, 1,474 tests) | `9679614` |
| 1,420 passed, 51 skipped, 1,471 tests, 98 suites | `DEVELOPMENT.md` | **1,422 / 52 / 1,474 / 98** | `9679614` |
| 1,422 passed, 52 skipped | `V2_PROFIT_FORK.md` | **1,422 / 52** | `9679614` |
| factory 24,433, 143 free | PR #84 body | **24,551, 25 free** | `9679614` and `5aedceb` |
| factory 25 free, CurveDeployer 12 | `V2_BONDING_CURVE.md` | **25 / 12** | `5aedceb` |
| V2TreasuryDeployer 4,773 / 31,947 | `V2_BONDING_CURVE.md` | 4,773 / 31,947 at `9679614`; **10,737 / 38,024** at `5aedceb` | both |
| HedgeFunBondingCurve 6,971 / 8,944 | `V2_BONDING_CURVE.md` | **6,971 / 8,944** (`forge inspect`) | `5aedceb` |
| CurveDeployer 24,564 / 24,614 · V2Factory 24,551 / 28,692 · V2Treasury 21,602 / 26,216 · Vault 7,327 / 8,448 · TradeRouter 11,150 / 11,677 · NativeRouter 5,749 / 6,147 | `V2_BONDING_CURVE.md` | all reproduce | `5aedceb` |
| 13 low-frequency fork tests; 4 live-venue | `V2_ADVERSARIAL_REVIEW.md`, PR #84 | 13 and 4 functions exist; **not run** | — |

---

## Findings

Graded on round 3's rubric (post-deployment state of an immutable contract; Info = no value impact). Every
finding below is a coverage or documentation hole: **no guard is missing, and nothing here is exploitable at the
tip.** They are graded on what a silent regression would cost, because two of the three contracts involved have
margins that make a later fix expensive (`HedgeFunV2Factory` 25 bytes) or a redeploy (any treasury).

### C-1 · Low · Five of the engine's twelve documented execution-time checks are pinned by no test

**Status** EXECUTED (`E01`, `E03`, `E04`, `E08`, `E10` GREEN; `E01` GREEN under the full 104-suite run).
**Location** `E:375` (nonce), `E:394` (codehash at execution), `E:400` (gas), `E:328,348` (capability),
`E:328,348` (direction).

`STRATEGY_ENGINE.md` ¶2 and PR #91 list twelve things the engine "independently checks" on every execution. Six
are pinned (config hash, return size, cooldown, per-call size, daily turnover, actual fill — the last three by
several tests each), the health gate is C-2, and five are not: an engine that forwarded all its gas to the policy, accepted a stale nonce, skipped the runtime
codehash, ignored the registered capability, or sold inside its own deadband would pass every test in the tree.
The mocks for four of the five already exist in `test/mocks/StrategyPolicyMocks.sol` (`WrongNonceStrategyPolicy`,
`GasBombStrategyPolicy`) or are three lines (`SellOnlyPolicyThatBuys`, `AlwaysSellPolicy`); the adversarial-mocks
test file's own header says engine tests "should reuse these policies", and for these two they do not.

**Loser if it regressed** the treasury's holders, through a policy that trades when it should not (direction,
capability) or a keeper whose `execute()` costs a block of gas (gas). **Fix** add `C1`–`C5` from
`AuditClaims4.t.sol` to `test/V2StrategyEngine.t.sol`; ~90 lines, 0 bytes.

### C-2 · Low · The oracle/venue health gate of `execute()` is untested, and the invariant suite cannot see it

**Status** EXECUTED (`E06`, `E07` GREEN, both including `V2StrategyEngineInvariantTest`). **Location** `E:252-255`.

The `health()` gate is the line that stops the engine trading a price the V3 venue disagrees with. Deleting it
passes the unit tests and the 256×500 invariant campaign, whose handler shoves the venue ±50% and pauses the oracle
— because the invariants assert that state stays consistent, not that the gate closed. The swap's own
`maxSlippageBps` bound masks the large deviations; a deviation between the 50 bps gate and the 100 bps slippage
bound executes (`C13`). The `tryPrice()` limb (`E07`) is reachable only with `bandBpsPerHour > 0` during a
scheduled closure, which no engine fixture sets up; this lane did not write that PoC.

**Fix** `C13` for the deviation gate (0 bytes); a closed-market fixture with a band for the `live` limb; and one
invariant that asserts `failedExecutions` grew whenever the handler's last action left `health()` false. Also
narrow the PR #91 sentence (K-32) to what the invariants assert.

### C-3 · Low · The three new owner-only registry entry points and `deploy()`'s factory-only guard are unpinned

**Status** EXECUTED (`D01`, `D02`, `D03`, `D05` GREEN; `D01` GREEN under the full suite; `D04` RED as control).
**Location** `D:218` (`registerPolicy`), `D:197` (`registerEngineKind`), `D:281` (`disablePolicy`), `D:369` (`deploy`).

`registerPolicy` is the "policy admission" gate `STRATEGY_ENGINE.md` describes: the one place governance rejects a
mutable or proxy policy before a creator can launch under it. Its `_onlyOwner()` can be deleted with every test
green, as can the engine-kind registration and the disable. The legacy `registerKind` is covered by
`test_onlyFactoryOwnerRegistersAKindAndKindsAreWriteOnce`, which was evidently not extended when the three new
entry points were added beside it. `deploy()` without `_onlyFactory()` would let anyone create treasuries through
the deployer and emit `TreasuryCodeBound` for them; no existing treasury is affected, but the event stream a front
end indexes would be.

**Loser if it regressed** buyers who read "registered" as "reviewed": an open registry admits the
`MutableDecisionStrategyPolicy` / `MutableStrategyPolicyProxy` that the fixture tests prove the codehash cannot
catch. The engine's caps bound what such a policy can do; they do not bound who chose it. **Fix** `C9`, `C10`;
~25 lines, 0 bytes.

### C-4 · Low · The engine's configuration bounds are enforced and untested, except the reserved bits

**Status** EXECUTED (`E17` GREEN; `E16` RED). **Location** `E:137-139`.

Six bounds — `deadband < target`, `target + deadband < 10000`, `cooldown ≠ 0`, `maxTrade ≠ 0`,
`maxTrade ≤ sellChunkUsdg`, `maxDaily ≥ maxTrade` — delete together with the suite green; only `packed >> 64 == 0`
is pinned. A treasury launched with `deadband == target` never buys (lower band is 0) and one with
`target + deadband ≥ 10000` never sells: a dead engine whose capital sits where graduation left it, immutable.
`V2RebalancePolicy._validate` re-checks a subset, but a policy is advisory and a different policy need not.
The fixture's `sellChunkUsdg = uint128.max` also means the `maxTrade ≤ sellChunkUsdg` limb has never been binding
in any test. **Fix** `C12` (six launches, each expecting `TreasuryDeployFailed`); 0 bytes.

### C-5 · Info · "Disabling a policy prevents new predictions/launches" is pinned only for new configurations

**Status** EXECUTED (`E24` GREEN). **Location** `D:347`, `E:133`.

A creator who configured a salt before the owner disabled its policy can still be blocked from predicting and
launching — by two checks, one in `_code` and one in the engine constructor — and both delete together with the
suite green. The existing test disables and then tries to *configure* a new salt. Graded Info: the disable is an
owner action about future launches, and a treasury that got through would still be bounded. **Fix** `C7`.

### C-6 · Info · PR #84's description quotes two numbers that do not reproduce at its own tip, and its documents disagree with each other

**Status** EXECUTED (clean build of `9679614`). **Location** PR #84 body; `docs/DEVELOPMENT.md:98`.

The body says 1,399 passed / 51 skipped and a factory at 24,433 bytes with 143 free. At `9679614` the suite is
1,422 / 52 and the factory 24,551 / 25. Inside the same PR, `DEVELOPMENT.md` says 1,420 / 51 (1,471 tests),
`V2_PROFIT_FORK.md` says 1,422 / 52 (correct), and `V2_BONDING_CURVE.md` says 25 free (correct). The body was
written before the last three commits and not refreshed; the 143 figure is the one round 3 I-13 already
flagged as stale. Round 3 M-5's finding — "the quantitative evidence does not reproduce at the audited ref" —
therefore recurs one round later on the PR that fixed it. **Fix** regenerate the counts from the tip in the body
and in `DEVELOPMENT.md`, or drop them from the body and point at the document that is generated.

### C-7 · Info · `V2_BONDING_CURVE.md`'s size table is one contract stale and two contracts short after PR #91

**Status** EXECUTED. **Location** `docs/V2_BONDING_CURVE.md:265-273`.

`V2TreasuryDeployer` grew from 4,773 / 31,947 to 10,737 / 38,024 when the registry landed, and the engine and
policy contracts are not in the table at all. The same commit regenerated `REFERENCE.md` (which is right). The
table is hand-maintained where the reference is generated; the PR #91 body quotes the right engine numbers but
does not touch the table. **Fix** regenerate the table from `forge build --sizes` (plus the `forge inspect` line
for the curve, which `--sizes` omits) or delete it in favour of the reference's size column.

### C-8 · Info · The engine's action-range check is dead code, and the mock that documents it is wrong

**Status** EXECUTED (`E18` GREEN; PoC `C6`). **Location** `E:376`, `test/mocks/StrategyPolicyMocks.sol:160`.

`abi.decode(result, (StrategyIntent))` at `E:407` validates the enum before `_basicIntentValid` runs, so a policy
returning action word 64 reverts with **empty revert data** — not `BadIntent`, not `NotDue`, not a `Panic`. The
mock's NatSpec ("a spot engine must reject this raw action word before attempting an enum ABI decode") describes a
check the engine does not perform, and the range test at `E:376` can be deleted with no observable change. No value
impact: the call reverts either way and nothing is committed. What is lost is a named error: a keeper sees a bare
revert it cannot distinguish from out-of-gas. **Fix** either decode the raw word and check it before the enum cast
(then `C6` expects `BadIntent`) or delete the dead comparison and fix the mock's comment.

### C-9 · Info · `creditLiquidityFee`'s vault-only check is untested

**Status** EXECUTED (`T01` GREEN). **Location** `src/v2/HedgeFunV2Treasury.sol:171`.

The only test pranks *as* the vault. If the check were lost, a stranger could push their own stock into
`buybackStock` — a donation into the buyback bucket, which is not a loss. **Fix** one negative test.

### C-10 · Info · Defensive checks with no observable behaviour and no test

**Status** EXECUTED (`E14`, `E20`, `E22`, `D06`, `D07`, `D10`, `D12` GREEN).

Listed so the next round need not re-run them: the post-fill daily check (`E:272`, unreachable because `offered`
is already capped); the pre-swap minimum-lot check (`E:334,354`, the post-fill check at `E:271` catches the same
case); `deploy()`'s introspection (`D:384-387`, the constructor fails first); `registerPolicy`'s gas/return/hash
bounds (`D:219-223`, re-checked by the engine constructor); the duplicate-key guard (`D:253`, the key is the hash of
the manifest); the zero-metadata guard (`D:237`). And `execute()`'s own `_bookInventory()` (`E:251`), whose deletion
means a donation is booked by the *next* explicit `book()` rather than being part of *this* observation — a
narrower reading of `STRATEGY_ENGINE.md`'s "becomes part of the next strategy observation" (K-24).

### C-11 · Info · Documentation that is narrower than the code

- `STRATEGY_ENGINE.md` ¶3: limits are stored "as immutables"; they are a storage struct written once (K-18).
- `abi/SURFACE.md`: three always-reverting `pure` functions listed as `read` on the engine (K-66).
- `SURFACE.md` and `REFERENCE.md` record `7027539`; the tip is the merge `5aedceb` (contents identical) (K-65).
- PR #84 body: "50/50 split" (K-46), already superseded in the documents by round 3 M-6.

### C-12 · Info · The invariant-coverage sentence in PR #91 is narrower than stated

See K-32 and C-2. The handler performs every action the sentence lists; the invariants assert consistency, not
gating. The sentence should say "survives", not "covers", for stale-feed recovery, oracle pause and venue
deviation — or gain the invariant C-2 asks for.

---

## Checked and found safe, by mutation

For the next round's safe list, with the mutation that proves each (all RED, i.e. a test caught the break):
config-hash binding (`E02`); exact 160-byte return (`E05`); cooldown (`E09`); per-call cap (`E11`); epoch cap
(`E12`); actual-fill minimum lot, atomic (`E13`, four tests including the invariant replay); options / buyback /
unknown capability rejection in the constructor (`E15`) and at configuration (`D08`); reserved config bits (`E16`);
STATICCALL (`E19`); preview's minimum-lot honesty (`E21`); inventory debited by the actual fill (`E23`); legacy
`registerKind` owner-only (`D04`); configuration-time codehash (`D09`); legacy setter refused on engine kinds
(`D11`); parked stock fee retry (`V01`); parked fee cleared on delivery (`V02`, caught by an adversarial fuzz in
`V2AdversarialTrading`, not by the vault's unit tests); `creditPendingStock` self-call only (`V03`);
`spikeBps = 0` on graduation (`F01`, six tests).

Round 3's I-14 (`V2LiquidityVault.seed`'s `onlyFactory` deletable with the suite green) was not re-run; nothing in
the delta adds a test for it, so it should be assumed to stand.

## What this lane did not do

- **No fork RPC.** K-47 and K-58 (the 13 low-frequency replays and the four live-venue cases, including the kind-1
  lifecycle at 5000 and 7000 LP bps) are UNMEASURED. The functions exist and skip cleanly; whether they pass at the
  pinned block `70,786,980` is the author's claim only.
- **The `live`-oracle limb of C-2** has no PoC: it needs a `SwitchableCalendar` oracle and a `bandBpsPerHour > 0`
  request, which no engine fixture provides.
- **Economics, mechanism and the round-3 findings' status** are other lanes' work. This lane did not re-derive
  M-0..M-6 or check which of them the delta closes, beyond noting that `F01` (spike freeze) and `V01` (fee-leg
  retry) are the code changes M-0 and M-1 asked for and that both are now pinned by tests.
- **Only `src/v2` was mutated.** The hook, `HedgeFunTreasuryBase` and the V1 contracts were read where a claim
  pointed at them (K-57, K-60) and not mutated; they are deployed and outside the delta.
- **The subset.** Mutations ran against `test/V2*` (28 suites, 184 tests) rather than the full suite, for speed.
  The soundness argument and two full-suite controls are in `mutations.md`; a reader who distrusts the argument can
  replay any diff with plain `forge test` in about 35 seconds on a warm cache.

## How to replay

```
git checkout 5aedceb
git checkout audit/round-4-lane-claims -- audit/round-4-2026-09-27
./audit/round-4-2026-09-27/poc/claims/run.sh                  # 13 passing on the clean tip
git apply audit/round-4-2026-09-27/poc/claims/diffs/E01-nonce.diff
forge test --match-path 'test/V2*'                           # green: the guard is unpinned
./audit/round-4-2026-09-27/poc/claims/run.sh                  # C1 fails: the guard is now pinned
git checkout -- src
```
