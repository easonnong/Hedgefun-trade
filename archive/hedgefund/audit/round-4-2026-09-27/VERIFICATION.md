> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Verification — how to re-run everything in round 4, and what triage re-ran

Part of [external audit round 4](./00-SCOPE.md). Companion to [`ISSUES.md`](./ISSUES.md).

**This is not what round 3's `VERIFICATION.md` was.** Round 3's held an adversarial pass and a review of the
report's method written without the source. Round 4 had neither ([`README.md`](./README.md) says so and why it
matters). This file is the reproduction guide: every runnable piece of evidence, what it is expected to show, the
full-suite and size numbers the lanes reported, and exactly what triage re-ran on 2026-09-28 and what it did not.

## Setup

The audit branch is the audited tip plus `audit/` and nothing else (`git diff --stat 5aedceb audit/round-4-2026-09-27
-- . ':(exclude)audit'` is empty), so it is itself a valid checkout of the code under audit.

```
git fetch origin
git worktree add ../audit4 origin/audit/round-4-2026-09-27        # = 5aedceb + audit/
cd ../audit4
git submodule update --init --recursive                           # lib/: forge-std, openzeppelin-contracts, v4-core
forge --version                                                   # 1.5.0-stable; solc 0.8.26 from foundry.toml
```

No network, RPC or environment variable is needed after `lib/` is populated. Every runner stages its files into
`test/`, runs only them, and removes them on exit (a `trap`), so `git status` is clean afterwards. In a worktree
whose `lib/` was copied rather than checked out as submodules, `forge` prints "Missing dependencies found.
Installing now..." and a failed `git clone`; the failure is harmless and the run continues.

## The four runners

| runner | tests | expected | triage, 2026-09-28 (UTC) |
|---|---|---|---|
| `./audit/round-4-2026-09-27/poc/engine/run.sh` | 21 in 6 suites | 21 pass | **PASS 21 / 0**, 04:47 |
| `./audit/round-4-2026-09-27/poc/delta/run.sh` | 13 in 4 suites | 13 pass | **PASS 13 / 0**, 04:47 |
| `./audit/round-4-2026-09-27/poc/claims/run.sh` | 13 in 1 suite | 13 pass | **PASS 13 / 0**, 04:47 |
| `./audit/round-4-2026-09-27/poc/econ/run.sh` | 11 in 1 suite | 11 pass | **PASS 11 / 0**, 04:48 |

**58 of 58**, run one at a time from the audit branch, `git status` clean after each. Every test *passing* is the
expected result: a finding's PoC asserts the defect's behaviour, a safe item's PoC asserts the guard, and a
claims-lane PoC asserts the property whose guard the suite leaves unpinned. Run each with `-vvv` appended to see
the logged figures.

### Engine lane — `poc/engine/`

| test | ID | shows |
|---|---|---|
| `test_E1_maxTradeBelowMinLotLaunchesAndIsPermanentlyInert` | L4-1 | `maxTradeUsdg < minLotUsdg` launches; `execute()` is `NotDue` in every state |
| `test_E2_oneBpDeadbandTradesOnEveryPrintAndBleedsValue` | M4-2 | a 1 bp band trades on 40 of 40 prints; 20,000.000000 → 19,999.492120 USDG, fee only |
| `test_E3_executePaysNoBounty` | L4-4 | the caller's balances are unchanged after a successful `execute()` |
| `test_E4_twoDailyCapsOneSecondApartAcrossMidnightUtc` | L4-2 | the full cap clears at 23:59:58, is refused at 23:59:59, clears again at 00:00:00 |
| `test_E6_setEngineConfigAcceptsWhatTheConstructorRefuses` | M4-2 | an all-zero config and a chunk-plus-one `maxTrade` are accepted and quoted, then `launch` reverts `TreasuryDeployFailed` |
| `test_E8_launchedSaltRecordIsStillWritableButInert` | I4-3 | after launch the deployer's record for the salt is rewritten; the treasury is not |
| `test_E5_outOfRangeActionWordIsRefusedByAnEmptyDecodeRevertNotByTheEngine` | I4-1 | action word 64 reverts with empty data; nothing committed |
| `test_E7_mutableStoragePolicyChangesBehaviourUnderThePinnedCodehash`, `test_E7_proxyPolicyRegistersLaunchesAndIsRepointed` | I4-2 | same address and codehash, different behaviour; the engine's caps still hold |
| `test_safe_malformed159ByteReturnFailsClosed`, `test_safe_gasBombIsBoundedByTheManifestGasAndFailsClosed`, `test_safe_dirtyNonceWordIsRefusedByDecode`, `test_safe_buybackBurnIntentFromASpotPolicyIsBadIntent`, `test_safe_sellOnlyPolicyCannotBuy` | safe list | the policy boundary fails closed five ways |
| `test_safe_reentryFromInsideTheSwapIsRefused`, `test_safe_sellCannotReachTheBuybackBucket`, `test_safe_strangerCannotTouchTheCreatorsSalt` | safe list | re-entry 0 of 3; the buy-back bucket untouched; a stranger's config cannot reach the creator's salt |
| `test_safe_sellThenBuy_*` (four suites: stock or USDG as token0, 18 or 6 stock decimals) | safe list | each ordering and decimal moves exactly the pool's amounts, allowances zero afterwards |

### Delta lane — `poc/delta/`

| test | ID | shows |
|---|---|---|
| `AuditDelta4Vault` — `test_parkedFeeIsDeliveredExactlyOnce_andTheEventStreamAddsUp`, `test_feeOnTransferStockParksTooAndRecovers`, `test_gasStarvationCannotParkTheFee`, `test_onlyTheVaultItselfCanRetry`, `test_blocklistedVaultStillRevertsBothLegs` | M-1 ledger, safe list | round 3's M-1 fix: a refused fee parks and is delivered once; the event stream sums; no gas budget forces a park; only the vault retries; a blocklisted vault still fails both legs, by design |
| `AuditDelta4Vault` — `test_parkedAmountIsOnlyObservableAsARawBalance` | I4-6 | while parked, `FeesCollected` reports 0 and no getter shows the amount |
| `AuditDelta4Spike` — `test_v2PoolsFreezeSpikeZeroWhateverTheDefaultsSay` | M-0 ledger | the factory freezes `spikeBps = 0` whatever the Defaults say |
| `AuditDelta4Spike` — `test_oneWeiBuybackArmsNothing_butStillConsumesTheCooldown`, `test_hookStillHonoursANonZeroSpikeRate_soTheFixLivesInTheFactoryAlone` | I4-7 | a 1-wei buy-back burns 0 and still consumes the cooldown; the hook still honours a nonzero rate |
| `AuditDelta4Buyback` — three tests | I4-8 | `buyback()` writes `lastGoodPrice` with `health()` shut, only on success, never from inside a closure |
| `AuditDelta4Kind1` — `test_kindOneScorecardDividesByZeroForLife` | L4-5 | kind 1's score: numerator 1.015e20 stock-wei, denominator 0 |

### Claims lane — `poc/claims/`

Each test pins one property the repository's suite leaves unpinned. On the clean tip every one passes; the column
"turns red under" is what makes it a pin, and triage checked it (below).

| test | ID | pins | turns red under | triage replay |
|---|---|---|---|---|
| `test_C1_nonceMismatchFailsClosedAtTheCore` | L4-6 | the nonce check | `E01` (claimed) | **does not** — see the corrected pin below |
| `test_C2_policyCodeReplacementAfterLaunchFailsClosed` | L4-6 | execution-time codehash | `E03` | red ✓ |
| `test_C3_gasBombIsBoundedByTheRegisteredGas` | L4-6 | the gas bound | `E04` | red ✓ |
| `test_C4_sellOnlyPolicyCannotBuy` | L4-6 | capability at execution | `E08` | red ✓ |
| `test_C5_sellInsideTheDeadbandIsRefused` | L4-6 | direction gates | `E10` | red ✓ |
| `test_C6_outOfRangeActionWordRevertsEmptyBeforeTheRangeCheck` | I4-1 | characterises the empty revert; `E18` deletes dead code, so nothing can turn red | — | green, as expected |
| `test_C7_disabledPolicyCannotLaunchAnAlreadyConfiguredSalt` | I4-11 | the disable, for a salt configured before it | `E24` | red ✓ |
| `test_C8_cooldownSurvivesTheEpochBoundary` | safe list (claims K-23) | cooldown across 00:00 UTC | no mutation shipped | not replayed |
| `test_C9_registryWritesAreOwnerOnly` | L4-8 | `registerPolicy`, `registerEngineKind`, `disablePolicy` owner-only | `D01`, `D02`, `D03` | red ✓ (all three) |
| `test_C10_deployIsFactoryOnly` | L4-8 | `deploy()` factory-only | `D05` | red ✓ |
| `test_C11_secondStockFeeCollectionDeliversAgain` | safe list | a delivered fee is cleared | `V02` | red ✓ |
| `test_C12_engineConfigBoundsAreEnforcedAtConstruction` | L4-9 | the six constructor bounds | `E17` | red ✓ |
| `test_C13_unhealthyVenueBlocksExecution` | L4-7 | the deviation limb of the health gate | `E06` | red ✓ |

The oracle-live limb of the health gate (`E07`) has no PoC in any lane; `E07` stays green against everything
shipped.

### Economics lane — `poc/econ/`

| test | ID | shows (logged figures, triage re-run) |
|---|---|---|
| `test_X1_sandwichOn30bpsPool_treasuryPays50bpsMore_attackerLoses` | M4-1 | $2,000 on $10k per 1%: treasury 39 → 88 bps, attacker −19.864478 USDG |
| `test_X1_sandwichOn5bpsPool_attackerProfits` | M4-1 | same cell at 0.05%: treasury 14 → 63 bps, attacker **+4.862294** USDG |
| `test_X1_deviationGateBindsAt50bps` | M4-1, safe list | a 51 bps push shuts `health()`, 49 opens it, neither changes the decision |
| `test_X2_utcDayBoundaryDoublesTheDailyBudgetInTenMinutes` | L4-2 | 1,000 USDG of a 500/day cap in the ten minutes around 00:00 UTC |
| `test_X3_closureAndPauseFailClosed_staleWithinAgeTrades` | safe list | closure and `oraclePaused()` refuse; a stale print inside `maxStockAge` fills 88 bps under it |
| `test_X4_graduationLotIsSoldDownToTargetImmediately` | L4-3 | 3 actions, 3 minutes, 5,011.99 sold for 4,983.44, 56 bps, share 50.02% |
| `test_X5_floorsAdmitOnePipBandOneSecondCooldownUnboundedDay_everyPrintIsAnAction` | M4-2 | on 9,980.51 USDG: +0.5% print sells 14.24, −0.5% buys 12.42 — 14 bps of value each (the input to M4-2's corrected figure) |
| `test_X6_executePaysNoBounty` | L4-4 | the caller's stock, USDG and token balances unchanged; `bountyBps == 50` unused |
| `test_X7_rebalanceGainsNeverReachTheBurn` | M4-3 | reserve 4,988.49 → 5,049.58 after 80 → 100; `buybackStock == 0`, `totalBurned == 0` |
| `test_X8_donationTriggersASellButCostsTheDonorTheDonation` | safe list | 1,109.95 donated for a 554.91 sale of which at most 7.21 is capturable |
| `test_X9_deployerAcceptsAnyWordsTheConstructorDoesNotRefuse` | M4-2 (X-5's setter limb) | `setEngineConfig` accepts words the constructor refuses |

## The two Python models

Standard library only, plus `lab/trend.py`, `lab/model.py` and `tools/rule_backtest.py` vendored unmodified from
`research/v2-trend-scenarios` @ `f1af82e` under `poc/econ/vendor/`. No network, no arguments.

```
cd audit/round-4-2026-09-27/poc/econ
PYTHONDONTWRITEBYTECODE=1 python3 sandwich_model.py     # < 1 s, 185 lines
PYTHONDONTWRITEBYTECODE=1 python3 constant_mix.py       # < 1 s, 82 lines
```

`PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` out of the vendored directory.

| model | expected | triage, 2026-09-28 |
|---|---|---|
| `sandwich_model.py` | the sandwich grid for 0.30% and 0.05% pools at gates 50/100 and 20/50, both sides; the no-push case; deadband → trigger move; donation cost; the configured per-day bound | **exit 0.** Reproduces +$0.84 ($500 on $3.3k), +$4.96 ($2,000 on $10k), +$22.30 ($10,000 on $55k) at 0.05%, and no profitable cell at 0.30%. **Does not print the "10.1% of depth" breakeven** the lane and M4-1 quote; the grid brackets it between 5% and 15% of depth at every depth. The last table's configured per-day bound ($2,246,400/day at cooldown 1 s) is a ceiling on configuration, not reachable: the turnover a day of prints forces is set by the price, see M4-2 |
| `constant_mix.py` | tables A–D: kind 2 against kind 0 on eight 90-day paths; the graduation sell-down; hourly against per-cooldown keeper | **exit 0.** Reproduces +2.20% against +0.19% of supply burned at +3%/day, $47,390 against $5,419, table C (E-50/5 sells $10,000 of $20,000 on day 1), and table D's keeper check (no multiple moves by more than 0.003) |

The Foundry X-1 cell (+$4.86) and the model's cell (+$4.96) differ by $0.10 on the same inputs: one is Uniswap's
`SwapMath` on a mocked step, the other a closed-form constant-`L` step.

## Replaying a mutation

The claims lane's 41 mutations ship as diffs under `poc/claims/diffs/` and are written out with their results in
[`poc/claims/mutations.md`](./poc/claims/mutations.md): **22 green** (no test noticed) and **19 red**. To replay one:

```
git apply audit/round-4-2026-09-27/poc/claims/diffs/E01-nonce.diff
forge test --offline --match-path 'test/V2*'                  # expected green: 28 suites, 184 passed, 17 skipped
./audit/round-4-2026-09-27/poc/claims/run.sh                  # the PoC that pins it should now fail
git checkout -- src                                           # always restore
```

The V2 subset is the lane's choice for speed; its soundness argument and two full-suite controls (`E01`, `D01`:
1,474 passed with the guard deleted) are in `mutations.md`.

**Triage's replay, 2026-09-28.** Fifteen mutations — the thirteen green ones that a claims PoC or the lane's
text addresses, plus `E07` and `V02` — each applied alone to a clean `src/`, the claims runner run, `src/`
restored:

| mutation | claims runner | | mutation | claims runner |
|---|---|---|---|---|
| `E01-nonce` | **all 13 pass — C1 does not catch it** | | `E18-action-range` | all pass (dead code; expected) |
| `E03-codehash-exec` | C2 fails ✓ | | `E24-enabled-both` | C7 fails ✓ |
| `E04-gas` | C3 fails ✓ | | `D01-registerPolicy-owner` | C9 fails ✓ |
| `E06-health` | C13 fails ✓ | | `D02-registerEngineKind-owner` | C9 fails ✓ |
| `E07-live` | all pass (no PoC exists; expected) | | `D03-disablePolicy-owner` | C9 fails ✓ |
| `E08-capability` | C4 fails ✓ | | `D05-deploy-onlyFactory` | C10 fails ✓ |
| `E10-direction` | C5 fails ✓ | | `V02-no-clear` | C11 fails ✓ |
| `E17-config-bounds` | C12 fails ✓ | | | |

`E01` was also run against the V2 subset: 184 passed, 0 failed, 17 skipped — green, as the lane reported.

### A nonce pin that works

C1's policy proposes a buy of `amountIn = 1`; with the nonce check deleted, the engine refuses that on the
minimum-lot floor with the same `NotDue`, so C1 cannot tell the two apart. The pin has to propose an action the
engine would otherwise **execute**. Triage staged this beside `AuditClaims4.t.sol` (it inherits its helpers), ran
it, and removed it; it passes at `5aedceb` and fails under `E01` with "next call did not revert as expected":

```solidity
/// Proposes an executable 50 USDG buy, but echoes nonce + 1.
contract WrongNonceExecutableBuyPolicy is StrategyPolicyMockBase {
    function decide(StrategyContext calldata context, EngineConfig calldata, bytes32)
        external pure override returns (StrategyIntent memory intent)
    {
        intent = _intent(context, StrategyAction.BuyStock, 50e6);
        unchecked { intent.nonce = context.nonce + 1; }
    }
}

contract TriageNoncePinTest is AuditClaims4Test {
    function test_T_nonceMismatchOnAnExecutableBuyIsRefused() public {
        HedgeFunV2EngineTreasury t = _launchPolicy(address(new WrongNonceExecutableBuyPolicy()), 100_000, "nonce2");
        _setShare(t, 2500);                          // under the 45% lower band: a buy is due
        uint256 usdgBefore = t.reserveUsdg();
        uint256 bookedBefore = t.bookedStock();
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();
        assertEq(t.strategyNonce(), 0);
        assertEq(t.reserveUsdg(), usdgBefore);
        assertEq(t.bookedStock(), bookedBefore);
    }
}
```

It is not shipped as a fourth runner: it is evidence about the claims lane's PoC, and the lane's file is left as
shipped. The fix branch should carry its own copy.

## The full suite

```
forge test --offline --summary                 # default gas cap
forge test --offline --gas-limit 9999999999    # the cap lifted, as round 3 advised
```

| who | when | gas | suites | passed | failed | skipped |
|---|---|---|---:|---:|---:|---:|
| claims lane | 2026-09-27 | default | 104 | 1,474 | 0 | 52 |
| delta lane | 2026-09-28 | default and lifted | 104 | 1,474 | 0 | 52 |
| engine lane | 2026-09-27/28 | lifted | 104 | 1,474 | 0 | 52 |
| **triage** | **2026-09-28 04:49 UTC** | default, `--offline` | **104** | **1,474** | **0** | **52** |

The 52 skips are the `RH_FORK=1` fork suites. Round 3's gas-cap trap did not fire at this ref; `foundry.toml` still
sets no `gas_limit`. Triage did not re-run the lifted-cap variant.

## Sizes

```
forge build --sizes --offline
```

Triage re-measured on 2026-09-28 and every figure in `00-SCOPE.md`'s remediation-budget table reproduces:
`HedgeFunV2Factory` 24,551 (25 free), `CurveDeployer` 24,564 (12), `HedgeFunV2Treasury` 21,602 / 26,216 (2,974),
`HedgeFunV2EngineTreasury` 21,574 / 27,866 (3,002 runtime, 21,286 initcode), `V2RebalancePolicy` 1,799 (22,777),
`V2TreasuryDeployer` 10,737 / 38,024 (13,839 runtime, 11,128 initcode), `HedgeFunV2BuybackTreasury` 14,859 (9,717),
`HedgeFunHook` 19,354 (5,222), `HedgeFunTreasury` 18,363, `TreasuryDeployer` 23,575 (1,001), `HedgeFunFactory`
18,929 (5,647).

## Round 3's PoCs at the tip

From the delta lane; **not re-run by triage.** Round 3's `poc/run.sh`, staged verbatim at `5aedceb`, fails to
compile because `AuditLane13V2b.t.sol:92,189` calls the deleted `CurveDeployer.predictVault`. With that file
patched to compute the vault's CREATE2 address locally — the same four lines the author added at
`test/V2DualEngine.t.sol:57-60` — 32 tests run: 27 pass and 5 fail, and all five failures are round 3's M-0 and M-1
fixes landing. The table is in `ISSUES.md`.

```
git show origin/audit/round-3-v2-review:audit/round-3-2026-09-27/poc/run.sh
```

## What triage did not re-run

The lanes' results stand for these, unverified by a second hand: the 26 mutations not listed above (18 red, whose
catching tests are the repository's own, and eight green ones that no PoC addresses — `E14`, `E20`, `E22`, `D06`,
`D07`, `D10` and `D12`, I4-13's shadowed checks, and `T01`, I4-12's); round 3's PoCs at the
tip; the lifted-cap full suite; the ABI and reference regeneration (claims K-36, K-37; delta D-5); the M-5
mature-TWAP table; `python3 -m pytest lab -q`; and the clean build of `9679614` behind I4-9's PR #84 numbers.
