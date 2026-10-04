> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Round 4, lane "delta": what changed since round 3, and the round-3 ledger

*External audit round 4 of the Hedgefun launchpad. Audited tip `5aedceb` = `origin/codex/v2-strategy-engine`:
PR #84 (`origin/codex/v2-main-integration`, tip `9679614`) merged with PR #91. Round 3 audited `03ad70e`; its
findings, rubric and PoCs are on `origin/audit/round-3-v2-review` under `audit/round-3-2026-09-27/`. Grades use
round 3's rubric unchanged (section 1 of its `FINDINGS-FULL.md`). Dates: read 2026-09-27/28. No transaction was
signed or broadcast; one read-only `eth_call` was made (noted where used). Everything else is offline Foundry.*

## 0 · The delta, in five commits

```
03ad70e (round 3)
  └─ d5218ee  fix: harden PR84 strategy launch and fork gates          src: HedgeFunTreasuryBase (+5 −1 code), kind-1 relabel
       ├─ 0d9fca8  fix(v2): isolate LP fee legs, buybacks at flat sell tax  src: V2LiquidityVault, HedgeFunV2Factory, CurveDeployer, hook comment
       │    └─ 9679614  docs(v2): align evidence and launch checks      docs only
       └─ 7252ab2  feat: add bounded V2 strategy engine                 (engine lane, not this one)
            └─ 7027539  fix: harden strategy execution and audit gates src: HedgeFunV2EngineTreasury (one check), tools
                 └─ 5aedceb  merge of 9679614 into 7027539              abi/ regenerated; no src conflicts
```

**The merge commit changed nothing of its own.** `git diff 7027539 5aedceb -- src` is hunk-for-hunk identical to
`git diff d5218ee 9679614 -- src`, and `git diff 9679614 5aedceb -- src` to `git diff d5218ee 7027539 -- src`
(diff-of-diffs, both directions, EXECUTED). The only files the merge touched beyond the union are `abi/*.json` and
`abi/SURFACE.md`, and regenerating them at `5aedceb` reproduces them byte-for-byte except the provenance line
(section 3, D-5).

### Source lines changed in this lane's scope (everything but the engine)

| file | what | lines |
|---|---|---|
| `src/v2/V2LiquidityVault.sol` | `pendingStockFee` + `try this.creditPendingStock()` self-call; the burn no longer waits on the stock leg | `:34`, `:105-108`, `:115-127` |
| `src/v2/HedgeFunV2Factory.sol` | `rates.spikeBps = 0` frozen at launch for every V2 pool | `:104-106` |
| `src/v2/CurveDeployer.sol` | `predictVault` deleted | (−3) |
| `src/HedgeFunTreasuryBase.sol` | `buyback()` calls `_notePrice(p)` when the oracle is live; the `lastGoodPrice` comment rewritten | `:141-145`, `:459-464` |
| `src/hooks/HedgeFunHook.sol` | one NatSpec line on `registerGraduated` | `:197` |
| `src/v2/HedgeFunV2BuybackTreasury.sol` | "DRAFT" → "Opt-in: production must register its exact code chunks"; spike sentence removed | `:6`, `:11-12` |
| `src/v2/HedgeFunV2EngineTreasury.sol` | dust-fill check `turnover < minLotUsdg → NotDue` (was `== 0 → BadIntent`) | `:265-272` |

### Sizes at `5aedceb` (`forge build --sizes`, 2026-09-28) against round 3's remediation-budget table

| a fix here | is scored against | bytes free at `03ad70e` | **at `5aedceb`** | note |
|---|---|---:|---:|---|
| `HedgeFunV2Factory` | itself | 27 | **25** | `rates.spikeBps = 0` cost 2 |
| `HedgeFunBondingCurve` **or** `V2LiquidityVault` | `CurveDeployer` | 176 | **12** | the M-1 fix: vault initcode 8,233 → 8,448, minus `predictVault` |
| `HedgeFunV2Treasury` | itself (initcode chunked, 26,216) | 2,993 | 2,974 | the base's `_notePrice` line |
| `HedgeFunV2EngineTreasury` | itself (initcode chunked, 27,866) | — | 3,002 | new (engine lane) |
| `HedgeFunV2BuybackTreasury` | itself (own chunked initcode) | 9,736 | 9,717 | |
| `V2TreasuryDeployer` | itself, **initcode** 38,024 / 49,152 | 17,224 | 11,128 | runtime 10,737 |
| `HedgeFunHook` | itself | 5,222 | 5,222 | unchanged |
| `HedgeFunTreasury` (V1) | `TreasuryDeployer` | 1,020 | **1,001** | the base's `_notePrice` line, +19 |
| `HedgeFunFactory` (V1) | itself | 5,647 | 5,647 | byte-identical to `main` (section 4) |

Round 3's two effectively-zero budgets are now **25 and 12 bytes**. Nothing below proposes a byte on either.

## 1 · The round-3 ledger at `5aedceb`

Status vocabulary: **FIXED** (the mechanism is gone), **PARTIALLY FIXED** (one limb, or process/disclosure only),
**NOT ADDRESSED**, **ACCEPTED-BY-DESIGN** (the delta chose not to, for a reason round 3 itself gave). Evidence is
`file:line` at the tip, and where a round-3 PoC exists, what it does now. Round 3's 32 offline PoCs were re-run
against the tip (section 2): **verbatim they no longer compile** (`AuditLane13V2b.t.sol` calls the deleted
`predictVault`); with that one file patched to compute the CREATE2 address locally, **27 pass and 5 fail, and all
five failures are the fixes landing.**

### Mediums

| ID | round-3 grade | status at `5aedceb` | evidence |
|---|---|---|---|
| **M-0** LP fee re-arms the 90% sell spike | Medium | **FIXED for V2**, by the first of round 3's two zero-byte fixes made structural: `HedgeFunV2Factory._openAndSeed` freezes `rates.spikeBps = 0` (`:104-106`) for every V2 pool, whatever the Defaults say; the rehearsal Defaults also zero it (`script/RehearseV2Launchpad.s.sol:154-155`). EXECUTED: round 3's four arming PoCs (`test_T3_oneWeiPotArmsTheNinetyPercentSpike`, `test_T3_oneWeiSpikeIsReArmableEvery240s`, `test_T3_e1EndToEndByAnUnprivilegedCaller`, `test_ADV_h1DoesNotNeedLastEventAtZero`) now fail on `1000 != 9000`. **What remains**: the fuel line (`test_T3_smallestRealFeeThatFundsThePot` still passes at the tip: a sub-lot LP fee still funds a pot), the zero-burn one-wei buy-back, its `noteEvent()` and its cooldown consumption — the second fix (gate `noteEvent` on `burned != 0`) was not taken, so the base is unchanged and a factory that registers a graduated pool with `spikeBps != 0` re-opens M-0 in full. See D-2. | `src/v2/HedgeFunV2Factory.sol:104-106`; `poc/delta/AuditDelta4Spike.t.sol` |
| **M-1** `collectFees` couples the stock leg to the token burn | Medium | **FIXED**, in the shape round 3's adversarial pass proposed: `pendingStockFee` (private) + a `try this.creditPendingStock()` self-call, `predictVault` deleted to pay for it. Cost measured: `CurveDeployer` 176 → **12** bytes (the adversarial pass predicted +15). EXECUTED: `test_L13_blockedStockLegAlsoStrandsTheTokenBurn` now fails with "next call did not revert as expected" — the burn goes through. The two triggers round 3 said no fix can reach still stand, by design: `test_L13_blockedVaultAlsoStopsTheTokenBurn` passes (a blocklisted vault reverts inside V4's `take`, before any delivery leg), and the docs now say so (`docs/V2_BONDING_CURVE.md:157-161`, `docs/V2_DUAL_ENGINE_REVIEW.md:27`). Regression hunt in section 3: none found; one observability Info (D-1). | `src/v2/V2LiquidityVault.sol:105-127`; `poc/delta/AuditDelta4Vault.t.sol` |
| **M-2** a full raise is a one-directional buy through the stock's only V3 pool | Medium | **PARTIALLY FIXED (process, 0 bytes)**. The listing rule round 3 asked for now exists as runbook step 3 of `docs/V2_DEPLOYMENT_REHEARSAL.md:38`: compute `Rg` in raw units, fork-simulate sourcing it through the intended V3 route as a single buyer, check the post-swap spot against the oracle and V3 TWAP at the tightest live V1 deviation gate for that stock, replay each affected V1 treasury's `health()`, record block/decimals/deviation/buffer, keep the listing disabled until it passes, monitor depth while public launches are open. No code enforces it and the doc says so ("cannot guarantee a check immediately before a permissionless launch"). The chain measurement was **not re-run** in this lane (no RPC): the ten-of-eighteen count is UNMEASURED at the tip. | `docs/V2_DEPLOYMENT_REHEARSAL.md:38-39` |
| **M-3** buyer funds stranded on a curve that cannot graduate | Medium | **PARTIALLY FIXED**. The structural instance (INTC) is covered by the same runbook rule, with the correct caveat that "direct-stock buys remain possible, so V3 inventory alone does not prove a curve can never graduate". The other limb — a graduation that fails should leave a retryable, observable state — is **NOT ADDRESSED**: `graduate(uint256)` is still dead code (L-1; `test_L13_graduateFallbackIsUnreachable` passes), a reverting graduation still rolls `Ready` back inside the final buy, and the factory has 25 bytes. | `src/v2/HedgeFunV2Factory.sol:129-142` |
| **M-4** parameter floors wider than the project's own conclusion | Medium | **PARTIALLY FIXED (disclosure only)**. `MIN_LP_BPS = 1000` (`src/v2/V2TreasuryDeployer.sol:107`) and `MAX_SALE_BPS = 9000` (`src/v2/HedgeFunV2Factory.sol:24`) are unchanged. The rehearsal now states that "the code's permissive 90% sale / 10% LP bounds are validity bounds, not recommended settings; the experiment's 70% / 60% is a hypothesis", requires `saleBps` and `lpBps` to be written explicitly into the Safe proposal with full-raise size, V4 opening depth and early-buyer exit scenarios, and forbids relying on an unset deployer default. Bound-versus-policy again resolves as policy, now labelled. | `docs/V2_DEPLOYMENT_REHEARSAL.md:39` |
| **M-5** the documents' numbers do not reproduce | Medium | **FIXED for the table, re-staled by the merge for the counts.** The mature-TWAP table in `docs/V2_ADVERSARIAL_REVIEW.md:59-65` was re-measured and now reproduces at the tip to the shown precision: `testMatureTwapBoundaryToken0/1` print 785.7778 / 351.0870 / 1.7643 / 92.1512 (EXECUTED, 2026-09-28), and the doc names the tests, the date and the fact that the old table was `01e515a`'s. The GO verdict is re-scoped as historical (I-15). But the same document's "1,422 passed / 0 failed / 52 skipped" and `README.md:169`'s "1,420 passed" were written before the merge; the tip measures **1,474 / 0 / 52** (D-5). The fork block `70,717,634` and the "6.450877 GME" figure round 3 could find in no test are still cited (`:87`, `:89`). | `docs/V2_ADVERSARIAL_REVIEW.md`; `$tmp/m5-mature-twap.txt` |
| **M-6** documents disagree on who sets the LP split | Medium | **FIXED**. `docs/V2_DUAL_ENGINE_REVIEW.md:11-12` now reads `floor(reserve * lpBps / 10000)`, "the factory owner sets `lpBps` per stock for future launches (10%–100%, default 50%); each launch freezes it into its treasury" — which is what the code does. | `docs/V2_DUAL_ENGINE_REVIEW.md:11-12` |

### Lows

| ID | round-3 grade | status | evidence |
|---|---|---|---|
| **L-1** the permissionless `graduate(id)` fallback can never fire | Low | **NOT ADDRESSED**. `graduate(uint256)` and its "Permissionless fallback" comment are still at `src/v2/HedgeFunV2Factory.sol:136-137`; `docs/REFERENCE.md` repeats the comment. PoC `test_L13_graduateFallbackIsUnreachable` passes at the tip. Deleting it is still the one fix that would *add* margin to a 25-byte contract. | |
| **L-2** the scorecard numerator moves on a bare `transfer` | Low | **NOT ADDRESSED**. `docs/SECURITY.md` has zero changed lines since `03ad70e`; no V1 test with `unbookedStock() > 0` was added by any of the four commits; PoC `test_aStockDonationNowInflatesTheScorecardWithoutBeingBooked` passes. Re-cost note: `TreasuryDeployer` is now 1,001. | `git diff --stat 03ad70e 5aedceb -- docs/SECURITY.md` (empty) |
| **L-3** `maxBuybackImpactBps` never checked against round-trip friction | Low | **NOT ADDRESSED, and the candidate configuration sits on the wrong side of it.** `V2TreasuryDeployer._validate` (`:360-366`) still checks only the stop against friction. The rehearsal's Defaults are `minTaxBps = 100`, `maxBuybackImpactBps = 300`, `lpFee = 3000` (`script/RehearseV2Launchpad.s.sol:148-162`); round 3's threshold at tax 100 and lpFee 3000 is 257.7 bps, so 300 is inside the profitable window it measured (+0.02 USDG per cycle at those numbers — real, tiny, and the reason it was Low). The zero-byte fix it proposed, `minTaxBps ≥ 122` in the V2 Defaults, was not taken. | |
| **L-4** an unpaid, undeadlined `book()` sets the cost basis of the whole treasury share | Low | **NOT ADDRESSED**. `HedgeFunV2Treasury.book()` (`:48`) is still unpaid with no deadline; the factory's `try … book() … catch {}` at `:155` is unchanged. | |
| **L-5** vault addresses are predictable before graduation; anything sent there is destroyed | Low | **NOT ADDRESSED in substance; the on-chain helper was deleted.** `CurveDeployer.predictVault` is gone (0d9fca8), but the address is still a public CREATE2 function of public inputs — the repository's own `test_predonatedVaultTokensNeverIncreaseLpBudgetOrCollectedFees` now computes it locally (`test/V2DualEngine.t.sol:57-60`), and the patched round-3 PoC `test_L13_vaultDonationsArePermanentlyLocked` passes unchanged. No document says the vault has no recovery path (`docs/V2_BONDING_CURVE.md:226` says donations "remain isolated"). Round 3's fix was docs, not deletion; the deletion buys 51 bytes and removes the one `@notice` slot that could have carried the warning. | |
| **L-6** the last tenth of every curve is negative-EV at purchase | Low | **NOT ADDRESSED (design)**, disclosure improved: the rehearsal now demands early-buyer exit scenarios at the chosen `saleBps`/`lpBps` before a listing. | `docs/V2_DEPLOYMENT_REHEARSAL.md:39` |

### Infos

| ID | status | evidence |
|---|---|---|
| **I-1** `registerGraduatedWithVault` validates nothing about the vault | NOT ADDRESSED. `src/hooks/HedgeFunHook.sol:204-210` unchanged; PoC `test_theHookAcceptsAnyContractAsTheVault` passes. | |
| **I-2** a graduated pool opens with the spike off, unexplained | PARTIALLY. `pools[id].lastEventAt = 0` at `:209` is still uncommented, but it no longer matters: the rate itself is 0, with a two-line reason in the factory, and the three documents now say so (`V2_BONDING_CURVE.md:189-191`, `V2_LP_DEPTH_EXPERIMENT.md:46-52` "historical, now-disabled", `V2_MARKET_SCENARIOS.md`). | |
| **I-3** the vault-less `registerGraduated` is unreachable and would burn a registration slot | NOT ADDRESSED. Still at `:196-201`; only its comment changed. | |
| **I-4** F-40's precondition met, three records not updated | NOT ADDRESSED. `docs/SECURITY.md` unchanged; base comments at `src/HedgeFunTreasuryBase.sol:429-433` and `:537-541` still say the anchor is not seeded at `wire()`; `HedgeFunV2Treasury.wire()` (`:185-191`) still seeds it. Round 3 ranked this first for remediation; it is the one zero-byte item nobody touched. | |
| **I-5** the anchor override's justification names a condition that cannot occur | NOT ADDRESSED. `src/v2/HedgeFunV2Treasury.sol:182-184` still says "exhaust the hook's observation ring"; `docs/REFERENCE.md` repeats it. | |
| **I-6** `predict()` is no longer total | NOT ADDRESSED. No document says `predict` may revert `Unseedable` (grep: only the error tables). | |
| **I-7** `nonReentrant` on the wrappers, `_canAddLot` base default `true` | NOT ADDRESSED. No comment added to the base. | |
| **I-8** kind 1's `book()` never reaches `_book()`; the scorecard divides by zero | **NOT ADDRESSED, and its "no impact" condition is gone.** Round 3 graded it Info because "kind 1 is marked DRAFT and registered by nobody". d5218ee relabels it "Opt-in: production must register its exact code chunks" (`src/v2/HedgeFunV2BuybackTreasury.sol:6`), the rehearsal registers it (`script/RehearseV2Launchpad.s.sol:105-108`), the CI fork job requires `test_fork_kindOneRegistersLaunchesGraduatesAndBuysBackOnLiveVenue` to have run, and the runbook wires keepers for it (`V2_DEPLOYMENT_REHEARSAL.md:41`). `book()` (`:30-37`) still never writes `totalStockReceived`. EXECUTED at the tip (`AuditDelta4Kind1`: numerator 1.015e20, denominator 0, for life). **Re-graded to Low as D-4.** | `poc/delta/AuditDelta4Kind1.t.sol` |
| **I-9** the creator picks the treasury bytecode and the factory emits nothing naming it | NOT ADDRESSED / ACCEPTED. `V2TreasuryDeployer` already emitted `StrategyKindSet` at `03ad70e` (grep); the factory still emits nothing; the runbook now says "wire keepers by strategy kind". | |
| **I-10** `lpFee` left the base with no ceiling of its own | ACCEPTED-BY-DESIGN. `HedgeFunFactory` unchanged and byte-identical to `main` at the tip (section 4); PoC `test_v1FactoryStillRefusesEveryNonZeroLpFee` passes. | |
| **I-11** `_minLpFee() = 1` makes the fee-only vault economically null | NOT ADDRESSED in code (`:54` still `1`); the rehearsal ships `lpFee = 3000`, and M-0's inlet is now severed by the rate rather than the fee — one of the two defensible positions round 3 named. | |
| **I-12** the opening burn is not a fee and not ordering protection | NOT ADDRESSED (design). `V2_MARKET_SCENARIOS.md` still shows the second-1 and second-2 sandwiches; only its spike sentences changed. | |
| **I-13** the doc contradicts itself on the factory's margin | **FIXED**. "143 bytes" is gone; `docs/V2_BONDING_CURVE.md:112` says 25 and the table says 25. | |
| **I-14** `seed`'s `onlyFactory` covered by no test | **NOT ADDRESSED — re-EXECUTED.** With `src/v2/V2LiquidityVault.sol:71` deleted, the full suite at the tip is still **1,474 passed / 0 failed / 52 skipped** (2026-09-28). No test calls `seed()` from a non-factory address; `test/V2LiquidityVault.t.sol` constructs the vault with the test contract as factory. Round 3 withdrew the causal story about a `CurveDeployer` split; with 12 bytes left there, that split is now the only way to add anything to the curve or the vault, which puts the story back. | `$tmp/mutation-i14.txt` |
| **I-15** the adversarial review's GO is scoped to a ref two contracts predate | **FIXED**. `docs/V2_ADVERSARIAL_REVIEW.md:3-10`: "Original scope … `885123e`", "Historical result: GO … at `885123e` only. The current PR #84 adds the fee vault, strategy kinds and other contracts absent at that ref; this verdict does not approve its deployment." | |
| **I-16** the review's reproduction evidence does not reproduce | PARTIALLY. Counts restated (and stale again after the merge, D-5); `:87` still cites block 70,717,634 against the test's pin of 70,786,980; `:89` still quotes 6.450877074340927318 GME, in no test. | |
| **I-17** "fee claims" tested by total, never per role | NOT ADDRESSED. No per-role assertion added (`test/V2AdversarialAccounting.t.sol` has no `protocolBps`/`creatorBps` assertion). | |
| **I-18** `snipeSeconds` has no upper bound | ACCEPTED-BY-DESIGN (`HedgeFunFactory` byte identity). | |
| **I-19** "roughly 100 stock" overstates the pool's depth | NOT ADDRESSED. `docs/V2_BONDING_CURVE.md:80`. | |
| **I-20** unannotated `assembly` in `CurveDeployer.deploy` | NOT ADDRESSED. `:110` bare, `:119` `("memory-safe")`; `via_ir` still off. | |
| **I-21** `bind()` permissionless on four deployers | ACCEPTED-BY-DESIGN. Unchanged; the rehearsal deploys and binds in one run. | |
| **I-22** protocol revenue ≈ $361 per lifecycle | n/a. The spiked-case revenue line (990/1,485) is now moot. | |
| **I-23** the size table omits the embedding deployers | **NOT ADDRESSED and REGRESSED** by the merge: `docs/V2_BONDING_CURVE.md:265-274` still lacks `TreasuryDeployer` and `HedgeFunV2BuybackTreasury`, and its `V2TreasuryDeployer` row now reads 4,773 / 31,947 against a build of **10,737 / 38,024**; `HedgeFunV2EngineTreasury` is absent. See D-5. | |

**Tally.** Mediums: 3 FIXED (M-1, M-6, M-5's table), 1 FIXED-for-V2-with-residue (M-0), 3 PARTIALLY (M-2, M-3, M-4).
Lows: 0 of 6 addressed (L-5 lost its helper, not its mechanism). Infos: 2 FIXED (I-13, I-15), 2
PARTIALLY (I-2, I-16), 1 worsened (I-8 → D-4), 1 regressed (I-23 → D-5), the rest unchanged.

## 2 · Re-running round 3's PoCs at `5aedceb`

`audit/round-3-2026-09-27/poc/run.sh` staged verbatim: **compile failure** —
`Error (9582): Member "predictVault" not found … in contract CurveDeployer` (`AuditLane13V2b.t.sol:92,189`).
With that one file patched to compute the CREATE2 address locally (the same four lines the author added to
`test/V2DualEngine.t.sol`), 6 suites, 32 tests: **27 passed, 5 failed.**

| test | at `03ad70e` | at `5aedceb` | meaning |
|---|---|---|---|
| `test_T3_oneWeiPotArmsTheNinetyPercentSpike` | pass (bug shown) | FAIL `1000 != 9000` | M-0 fixed |
| `test_T3_oneWeiSpikeIsReArmableEvery240s` | pass | FAIL `1000 != 9000` | M-0 fixed |
| `test_T3_e1EndToEndByAnUnprivilegedCaller` | pass | FAIL `1000 != 9000` | M-0 fixed |
| `test_ADV_h1DoesNotNeedLastEventAtZero` | pass | FAIL `1000 != 9000` | M-0 fixed |
| `test_L13_blockedStockLegAlsoStrandsTheTokenBurn` | pass | FAIL "did not revert" | M-1 fixed |
| `test_L13_blockedVaultAlsoStopsTheTokenBurn` | pass | pass | the unfixable trigger, as round 3 said |
| `test_T3_smallestRealFeeThatFundsThePot`, `test_T3_smallestBuyThatRefillsThePot` | pass | pass | the fuel line still exists (D-2) |
| `test_ADV_spikeBpsZeroKillsH1` | pass | pass | now the shipped state |
| `test_L13_graduateFallbackIsUnreachable` | pass | pass | L-1 unchanged |
| `test_L13_vaultDonationsArePermanentlyLocked` (patched) | pass | pass | L-5 unchanged |
| `test_aStockDonationNowInflatesTheScorecardWithoutBeingBooked`, `test_scorecardIsNowTheWholeStockBalance` | pass | pass | L-2 unchanged |
| `test_theHookAcceptsAnyContractAsTheVault` | pass | pass | I-1 unchanged |
| the other 15 (curve invariant fuzz, vault principal, graduation split, delegatecall isolation, last seller, V1 `lpFee`, snipe window, registration uniqueness, opening burn, pool depth, crossing buyer) | pass | pass | round 3's safe list holds where it was executed |

Output: `poc-r3-verbatim.txt`, `poc-r3-patched.txt` in this lane's scratch (summarised above; not committed).

## 3 · New findings

Graded on round 3's rubric. None reaches Medium. Everything marked EXECUTED runs from
[`../poc/delta/run.sh`](../poc/delta/run.sh): 4 suites, 13 tests, no network.

### D-1 · Info · A parked stock fee is unobservable on chain, and the event that used to mean "fees earned" now means "fees delivered"

**Location** `src/v2/V2LiquidityVault.sol:34` (`pendingStockFee` is `private`), `:108` (`stockFee = delivered`),
`:111` (`emit FeesCollected(stockFee, tokenBurned)`), `abi/V2LiquidityVault.json` (no getter).
**Status** EXECUTED (`AuditDelta4Vault.test_parkedAmountIsOnlyObservableAsARawBalance`, `…EventStreamAddsUp`).
**Mechanism** While the issuer refuses delivery, `collectFees()` returns and emits `stockFee = 0` although stock
was taken from V4; when the refusal lifts, one call reports the whole backlog. The stream still *sums* correctly
(EXECUTED: four collections, Σ`stockToTreasury` == the treasury's budget delta), so an indexer that sums is not
misled; one that attributes per period is, and one that alerts on "no stock fee" sees nothing unusual in a zero.
The only on-chain view of the parked amount is `stock.balanceOf(vault)`, which also counts donations (L-5) and
cannot be split. **Loser** an operator who needs to know a treasury is not being paid; no value moves.
**Conditions** the issuer refuses the treasury (or a fee-on-transfer surcharge trips `InexactTransfer`, also
EXECUTED) — same status as M-1's condition 2. **Fix** 0 bytes: a runbook alert on `FeesCollected(0, >0)` and a
documented balance-based monitor. A getter is ~40 bytes on `CurveDeployer`'s 12 and does not fit.

### D-2 · Info · The arming buy-back is untouched; only the rate it arms is zero, and only on this factory

**Location** `src/HedgeFunTreasuryBase.sol:479` (dust floor `min(amountIn, …)`), `:489` (`noteEvent()`),
`src/hooks/HedgeFunHook.sol:288-292`, against the fix at `src/v2/HedgeFunV2Factory.sol:106`.
**Status** EXECUTED (`AuditDelta4Spike.test_oneWeiBuybackArmsNothing_butStillConsumesTheCooldown`).
**Mechanism** One wei of LP fee still lets anyone call `buyback()`: `spent = 1, burned = 0`, `noteEvent()` still
writes `lastEventAt`, and `lastBuybackAt` is set, so a real pot arriving next must wait one `buybackCooldown`
(60 s in the rehearsal and fixture Defaults). Round 3's second fix — refuse to `noteEvent` when `burned == 0` — was not
taken, so the base still treats a zero-burn buy-back as an event. **Loser** none today: a 60-second delay per wei
is not a tax. **Why recorded** the fix lives in one factory's frozen rate. The hook still honours any nonzero
`spikeBps` (`_sellRate`), the base still fires, and V1's `TreasuryDeployer` has 1,001 bytes for the base-side
gate. A third factory (or a V2 factory whose `_openAndSeed` is overridden again) registering a graduated pool with
`spikeBps != 0` has M-0 back in full. **Fix** either accept and write it into `docs/SECURITY.md` as the invariant
it now is ("graduated V2 pools carry `spikeBps = 0`; a nonzero rate on a pool whose `buybackStock` is fed by anything
but realised profit re-opens round 3's M-0"), or spend ~15 bytes of `TreasuryDeployer`'s 1,001 on
`if (burned != 0) IHedgeFunHook(hook).noteEvent();` — which forfeits nothing, since `HedgeFunTreasury` already
differs from `main`.

### D-3 · Info · `buyback()` is now a writer of the sizing cache gated by `tryPrice()` alone; every earlier writer went through `health()`

**Location** `src/HedgeFunTreasuryBase.sol:458-464` against `:291-305`, `:327-350`, `:379-387`, `:405-410`
(the four rule writers, all behind `health()`); the sole reader at `:465-466`.
**Status** EXECUTED (`AuditDelta4Buyback`, three tests).
**Mechanism** `lastGoodPrice` was "the last price the rule itself traded at" (the deleted comment); it is now also
the feed price at the last successful buy-back. The new writer checks feed age, calendar and `oraclePaused` but
not the pool-versus-feed deviation gate: with the mocked stock venue shoved 20% off the oracle, `health()` is
shut and `buyback()` still notes the feed's price (EXECUTED). **What holds** the write happens only on a
*successful* buy-back (a `Cooldown` revert writes nothing; any later revert unwinds it); a closed-market
buy-back sized off the cache cannot refresh it; the five-day window cannot be extended from inside a closure
(EXECUTED: 27 h into a stale feed the cache stays put, and at 5 d + 1 s it reverts `Unhealthy`); and the value is
always a signed Chainlink print at most `maxStockAge` old when written. **Reader set** one: the buy-back's own
sizing fallback (`git grep lastGoodPrice -- src`), whose execution price is bounded by the token pool's TWAP/anchor,
not by this number. **Loser** none. **Why recorded** it is the one delta line that changes V1 semantics for any
future V1 deployment (`HedgeFunTreasury` 18,344 → 18,363; `TreasuryDeployer` margin 1,020 → 1,001), and the
deviation-gate asymmetry is the kind of thing a later reader of `lastGoodPrice` would assume away. **Fix** none
needed; one sentence at `:141-145` saying the buy-back's note is feed-gated, not pool-gated. 0 bytes.

### D-4 · Low · Kind 1 is now an opt-in production strategy whose published score is undefined for life (round 3's I-8, condition gone)

**Location** `src/v2/HedgeFunV2BuybackTreasury.sol:30-37` against `src/HedgeFunTreasuryBase.sol:152,300`
(`totalStockReceived`, written only by `_book`); the formula at `README.md:385` and `docs/REFERENCE.md:1063`.
**Status** EXECUTED (`AuditDelta4Kind1.test_kindOneScorecardDividesByZeroForLife`): after graduation, one
buy-back and one later booking, numerator 1.015e20 stock-wei, denominator 0.
**Conditions** 1. kind 1 registered — **now a documented production option** (relabelled in source, registered by
the rehearsal script, required by the CI fork gate, wired in the runbook's keeper step). 2. A front end computes
the score as `README.md` says — true (four documents name it). **Impact** the product's headline number is a
division by zero for every kind-1 strategy: a front end shows Infinity, NaN, or nothing. **Loser** a reader of the
token page; **certain gain** none; **option gain** a creator who prefers an unscorable strategy to a scored one.
Graded Low by analogy with round 3's L-2 (a scorecard that reads wrong, no value moved); strictly the rubric's Info
limb. **Fix** `totalStockReceived += pending;` in `book()` — ~20 bytes against kind 1's **own** 9,717 (it is its
own chunked initcode; 0 on the factory, 0 on `CurveDeployer`); or state in `README.md` and `LAUNCH_KIT.md` that
the score is undefined for kind 1 and give the front end the substitute (`totalStockSpentOnBuybacks + buybackStock`
against the graduation share, which `GraduationCapitalSplit.treasuryStock` emits).

### D-5 · Info · Three generated documents were regenerated on the pre-merge tree and not after it

**Location** `docs/V2_BONDING_CURVE.md:265-274`, `docs/V2_ADVERSARIAL_REVIEW.md:99`, `README.md:169`,
`abi/SURFACE.md:3`, `docs/REFERENCE.md:7`.
**Status** EXECUTED (build sizes, full suite, ABI regeneration, all 2026-09-28).
**Mechanism** the same class as round 3's M-5, I-13 and I-23 — a number regenerated at one ref and shipped at
another: (a) the size table's `V2TreasuryDeployer` row says 4,773 / 31,947; the tip builds **10,737 / 38,024**,
and `HedgeFunV2EngineTreasury` (21,574 / 27,866) is absent, as are the `TreasuryDeployer` and kind-1 rows I-23 asked
for; (b) "1,422 passed / 0 failed / 52 explicitly skipped" and README's "1,420 passed" against a measured
**1,474 / 0 / 52** at the tip (at default gas and with the cap lifted; round 3's test-state trap did not fire here);
(c) `abi/SURFACE.md` and `docs/REFERENCE.md` both say "generated at `7027539`", a tree that has no
`creditPendingStock`, while their content is the merged tree's — regenerating the ABI at `5aedceb` differs in the
provenance line only. CI's `tools/check_docs.py` compares `REFERENCE.md`'s content and evidently not its commit
line (it passes at the tip). **Loser** the next auditor. **Fix** regenerate at the merge commit; have
`check_docs.py` also require the provenance hash to be an ancestor-or-equal of `HEAD` whose tree matches. 0 bytes.

### D-6 · Info · `"editor": null` in a metadata plan now means "revoke", and the one committed plan carries it

**Location** `tools/metadata_batch.py:218-226` (d5218ee), `deploy/metadata-crclgrid-2026-09-22.json:20`,
`docs/OPERATIONS.md:249`.
**Status** REASONED; one read-only `eth_call` (2026-09-28): `editor()` on `0xF5501c0D…F332` returns `address(0)`.
**Mechanism** before, a falsy `editor` was skipped; now an explicit `null` emits `setEditor(address(0))` unless the
chain already reads zero. The only committed plan says `"editor": null` with the intent line "while it is, only the
Safe can rewrite this entry" — consistent with revoke — and the token's editor is zero, so re-running the tool on it
today is a no-op ("editor already 0x0…; no setEditor"). Tests were added (`lab/test_metadata_batch.py`).
`OPERATIONS.md` documents appointing an editor, not that `null` revokes. **Loser** none today; a future plan
copied from this one with an editor since appointed would revoke it, in a batch the operator reads before signing.
**Fix** one sentence in `OPERATIONS.md`. 0 bytes.

## 4 · The V1 question

**No deployed V1 contract can change**; the question is what a V1 re-deployment from this tree would get, and
whether the V1 test surface regressed. Measured by building `origin/main` (`5c28050`) in a scratch worktree with
the same `lib/` and `foundry.toml` (the tip adds one RPC alias, nothing else) and comparing `deployedBytecode`:

| contract | `main` | `5aedceb` | |
|---|---:|---:|---|
| `HedgeFunFactory` | 18,929 | 18,929 | **byte-identical** (round 3's finding re-verified at the tip) |
| `HedgeFunToken`, `HedgeFunTradeRouter`, `HedgeFunLaunchRouter`, `PriceOracle`, `TradingCalendar`, `TokenDeployer` | | | **byte-identical** |
| `HedgeFunHook` | 18,481 | 19,354 | differs, as at `03ad70e`; the delta changed one comment |
| `HedgeFunTreasury` | 18,289 | 18,363 | differs; `03ad70e` was 18,344, **+19 in the delta** (the `_notePrice` line) |
| `TreasuryDeployer` | | | differs (embeds the treasury); margin 1,001 |

The one behavioural change that reaches V1 semantics is D-3, and it is benign. The V1 test surface: the full
offline suite is **1,474 / 0 / 52** at default gas and with `--gas-limit 9999999999`; round 3's "first reading is
a trap" did not fire at this tip, although `foundry.toml` still sets no `gas_limit`. The hook's registration paths
and the base's rule paths are untouched by the delta except the buy-back line; round 3's V1-delta PoCs (8/8) pass.

## 5 · Checked and found safe (the delta)

Each with the line that makes it safe. EXECUTED where a test in `poc/delta/` or a round-3 PoC proves it.

**The vault fix (M-1's replacement code)**
1. **The parked fee cannot be lost.** It is the vault's own stock balance; `pendingStockFee` resets only in the
   success branch of the `try` (`:108`); `creditPendingStock` transfers exactly `pendingStockFee` and checks both
   balances moved by exactly that (`:125-126`). EXECUTED: delivered once, vault left at 0.
2. **It cannot be double-counted.** `pendingStockFee += newStockFee` before the try; on failure the sum persists
   and the next success delivers it once; the treasury's `buybackStock` grows by exactly the delivered amount;
   an empty retry credits 0. EXECUTED, including the event sum.
3. **The self-call guard holds.** `msg.sender == address(this)` — outsider, treasury, pool manager and factory all
   revert `Busy` while a fee is parked. EXECUTED. No other internal path calls it.
4. **Gas starvation cannot force a park.** Scanned 40,000–600,000 gas at 1,000 steps under snapshots: success is
   monotone (largest failure 227,000, smallest success 228,000), and no budget yields `(0, >0)`. By the 63/64 rule a
   partial outcome needs the inner leg to cost more than 63× the tail after the `try`; here ~1e5 against ~2e4.
   EXECUTED.
5. **The catch cannot block the burn**, which is outside the `try` (`:109`) and burns the vault's own balance,
   verified by `_take` (`:174`). EXECUTED (four burns while blocked).
6. **Reentrancy** `collectFees` during `creditLiquidityFee` → `_mode == 2` → `Busy` → caught → parked, state
   consistent; the treasury's `creditLiquidityFee` is itself `nonReentrant` (`HedgeFunV2Treasury.sol:170`).
   REASONED.
7. **The treasury can always be credited**: `setLiquidityVault` runs in `_seedGraduation` before registration
   (`CurveDeployer.sol:93`), once, from the factory.
8. **A blocklisted vault and a global pause still revert both legs** inside V4's `take`, exactly as round 3 said no
   fix could avoid. EXECUTED.
9. **`predictVault` has no remaining reference** in `src`, `script`, `tools`, `docs`, `abi`, `lab` (grep: 0);
   `REFERENCE.md` and `SURFACE.md` were regenerated without it.

**The spike fix (M-0's replacement)**
10. `HedgeFunHook._sellRate` returns `taxBps` whenever `spikeBps * (secs − dt) / secs ≤ taxBps`, so 0 is flat at
    every `dt`; `spikeSeconds` (still 120) only bounds how often `noteEvent` may *write*. `rates(id)`,
    `graduationConfig(id)` and the live `sellRateBps` agree on 0. EXECUTED.
11. Nothing else reads `spikeBps`: `V2TreasuryDeployer._validate` checks the stop only; `_setDefaults` bounds it;
    `_rates` (V1) still passes `d.spikeBps` untouched, so V1 launches are unaffected (grep).
12. `registerGraduatedWithVault` still refuses a snipe window and stores `r.spikeBps` as given (`:206-210`).

**The buy-back cache**
13. Written only on success; never inside a closure; never past five days; sole reader is the sizing fallback.
    EXECUTED (D-3).

**The engine hardening line (7027539) as it touches this lane**
14. `turnover < minLotUsdg → NotDue` still refuses a zero fill because `minLotUsdg == 0` is rejected by
    `HedgeFunFactory._setDefaults` (`:199`) and the treasury constructor (`HedgeFunTreasury.sol:38`); the error
    changed from `BadIntent` to `NotDue`, which is the right class for a venue condition. The engine itself is the
    engine lane's.

**The merge**
15. Source is exactly the union of both sides (diff-of-diffs identical in both directions); tests, docs, script and
    lab likewise; ABI regenerated from the merged tree (D-5 is about the label, not the content).

**"Harden PR84 strategy launch and fork gates" (d5218ee) — what was hardened, and whether it holds**
16. **CI fork job**: retries only when the log matches `HTTP error 429|rate limit exceeded|retry_after_ms`, at most
    8×65 s, fails immediately on any other failure, fails on `[SKIP`, greps the four required tests and the two
    `LP bps` lines after a passing run, and adds a second 70/30 job with the same gates. Holds as written. What it
    rests on and this lane could not measure: that `blockmachine` serves state at block 70,786,980 when
    `RH_ARCHIVE_RPC_URL` is absent (forked PRs). `timeout-minutes` 20 → 45.
17. **Rehearsal script**: refuses `ScriptBroadcast`/`ScriptResume` contexts and any chain but 31337 (`:41-43`);
    rehearses kind-1 registration with `vm.prank(owner)` — a simulation, not a signing path; reads back the
    registered chunks against `type(HedgeFunV2BuybackTreasury).creationCode` (`:118-123`).
18. **`lab/fork_runner.py`**: the source-mutating "variant" runner is gone; the LP split goes through the production
    `setLpBps` path (`test/V2LiveVenueFork.t.sol:135-142`, asserted frozen at launch `:158-160`); the subprocess is
    list-form (no shell), the RPC alias is allow-listed to `blockmachine`, `lp_bps` is an `int` in 1000–10000,
    `timeout` 15–600, compiler output goes to a temp dir. `lab/server.py` re-validates.
19. **`test/V2LiveVenueFork.t.sol`** kind-1 lifecycle test lowers `minLotUsdg` to 0.25 USDG **for that fork only**
    and says why (`:116-122`); the rehearsal Defaults keep 5 USDG.
20. **`tools/metadata_batch.py`**: D-6; tested; no-op on the committed plan today.

**Round 3's safe list, where the delta touched its proof**
21. Curve invariant fuzz, vault principal by any route, graduation split, delegatecall isolation, last seller
    redeemable, opening burn rate, pool depth against the raise, crossing buyer: the round-3 PoCs pass unchanged
    (section 2). The vault's "fee-only" property: `unlockCallback` is unchanged (`:129-160`); the new code runs
    after the unlock returns and can only move stock the unlock already took.

## 6 · Not covered by this lane

- **`7252ab2` — the strategy engine** (`HedgeFunV2EngineTreasury`, `V2RebalancePolicy`, `IStrategyPolicy`, the
  +272 lines in `V2TreasuryDeployer`, `V2StrategyEngineInvariant.t.sol`). The engine lane's. Noted only that the
  deployer's initcode grew to 38,024 / 49,152 and that its `_validate` and `lpBps` paths are unchanged.
- **Chain state.** M-2/M-3's depth figures were not re-measured (no RPC); the fork suites were not run; whether
  `blockmachine` is an archive node is UNMEASURED. One read-only `eth_call` was made for D-6.
- **The rehearsal script's own run**, the lab UI beyond the diffs, the front end, `docs/STRATEGY_ENGINE.md`.
- **Round 3's fork PoCs** (`poc/fork/`).
- **A context-free read of the delta.** Every line cited above was read; no claim is made about lines not cited.

## 7 · Reproducing

```
git worktree add ../audit4-delta origin/codex/v2-strategy-engine     # 5aedceb
# round 3's PoCs (one file needs the four-line predictVault patch described in section 2)
git show origin/audit/round-3-v2-review:audit/round-3-2026-09-27/poc/run.sh
# this lane's PoCs: 4 suites, 13 tests, no network
./audit/round-4-2026-09-27/poc/delta/run.sh
# M-5's table
forge test --mt testMatureTwapBoundaryToken -vv
# the full suite, both ways
forge test && forge test --gas-limit 9999999999
# sizes
forge build --sizes
# I-14's mutation: delete src/v2/V2LiquidityVault.sol:71, forge test, git checkout -- src/v2/V2LiquidityVault.sol
```
