> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Round 4, engine lane — `HedgeFunV2EngineTreasury`, `V2RebalancePolicy`, `IStrategyPolicy`, the deployer registry

*One lane of external audit round 4. Audited tip `origin/codex/v2-strategy-engine` @ **`5aedceb`** (= PR #84's
`9679614` + PR #91 "bounded strategy engine"). Graded on round 3's rubric, reproduced in
`audit/round-3-2026-09-27/FINDINGS-FULL.md` §1. Written 2026-09-27/28. PoCs: [`../poc/engine/`](../poc/engine/).*

## Result

| | Critical | High | Medium | Low | Info | total |
|---|---|---|---|---|---|---|
| **engine surface** | **0** | **0** | **0** | **2** | **9** | **11** |

No path was found by which a policy, a creator, a keeper, the factory owner or any caller moves stock or USDG
anywhere but the listed V3 pool's swap callback and the inherited buy-back's `poolManager.settle()`. The two Lows
are both **missing constructor checks** that V1 makes in the equivalent place; both cost **zero runtime bytes**
(the check lives in initcode, which the deployer chunks). Everything else is documentation, configuration, test
coverage or diagnosability.

| ID | grade | status | one line |
|---|---|---|---|
| E-1 | **Low** | EXECUTED | `maxTradeUsdg < minLotUsdg` is accepted; the launched treasury can never execute anything, ever |
| E-2 | **Low** | EXECUTED | `deadbandBps` has no floor against `maxSlippageBps + poolFeeBps`; a 1 bp band trades on every print and bleeds |
| E-3 | Info | EXECUTED | `execute()` pays no bounty: the only paid caller is a sandwicher, and nobody is paid to keep the strategy alive |
| E-4 | Info | EXECUTED | daily cap is a UTC calendar epoch (2× `maxDaily` two seconds apart); `maxDaily` has no owner ceiling (documented) |
| E-5 | Info | EXECUTED | out-of-range action word is refused by `abi.decode` with an **empty** revert; the engine's own range check is dead |
| E-6 | Info | EXECUTED | `setEngineConfig` validates none of the three words; `predict` succeeds, `launch` fails opaque `TreasuryDeployFailed`; the `sellChunkUsdg` bound has no test |
| E-7 | Info | EXECUTED | mutable-storage and proxy policies pass `registerPolicy`, `setEngineConfig` and the constructor, then change behaviour under the pinned codehash (documented); EIP-7702 accounts too (REASONED) |
| E-8 | Info | EXECUTED | a launched salt's deployer record (`engineConfigOf`, `strategyKindOf`) stays writable; the treasury is unaffected, indexers are not |
| E-9 | Info | EXECUTED | remediation budget after this branch: engine **3,002**, `HedgeFunV2Factory` **25**, `CurveDeployer` **12** (the last two moved on `v2-main-integration`, not here) |
| E-10 | Info | REASONED | an engine launch must still pass V1's `tp1/tp2/dip/stop/lot` validation for parameters the engine never reads; `Request` has no engine field |
| E-11 | Info | REASONED | `policyGasLimit` is immutable; a future gas repricing that pushes `decide()` over it kills `execute()` for good (buy-back survives) |

**PoCs: 21 tests, 6 suites, all passing, no network** —
`./audit/round-4-2026-09-27/poc/engine/run.sh` (stages `AuditEngine*.sol` into `test/`, runs with `--offline`,
removes them). The repository's own suite at `5aedceb` with `--gas-limit 9999999999`: **1,474 passed, 0 failed,
52 skipped** (the `RH_FORK=1` suites).

---

## What I read, and how

**Every line of** `src/v2/HedgeFunV2EngineTreasury.sol` (409), `src/v2/strategy/IStrategyPolicy.sol` (81),
`src/v2/strategy/V2RebalancePolicy.sol` (107), `src/v2/V2TreasuryDeployer.sol` (402, the whole file, not just the
diff), and the 4-line `HedgeFunV2Treasury.sol` diff (the `Action` enum append).

**Every line of what they inherit and call**, because the engine's custody boundary is mostly not in the engine:
`HedgeFunV2Treasury.sol`, `HedgeFunTreasury.sol`, `HedgeFunTreasuryBase.sol`, `PoolTrader.sol`,
`PriceOracle.sol`, `HedgeFunDeployers.sol`, `HedgeFunV2Factory.sol`, `HedgeFunFactory.sol`,
`HedgeFunV2BuybackTreasury.sol`, `libraries/HedgeFunMath.sol`. Traced (not read in full): the hook's calls into a
treasury (`HedgeFunHook.sol` — it makes none, it only transfers stock), `CurveDeployer.executeGraduation` (wire
order), `V2LiquidityVault.collectFees` → `creditLiquidityFee`.

**Tests read in full:** `V2StrategyEngine.t.sol`, `V2StrategyEngineAccounting.t.sol`,
`StrategyPolicyAdversarialMocks.t.sol`, `V2StrategyOptionsBoundary.t.sol`, `mocks/StrategyPolicyMocks.sol`,
`utils/V2FactoryFixture.sol`, `mocks/Mocks.sol`; the invariant suite's handler and invariants; the policy suite's
test names and its rejection test. `docs/STRATEGY_ENGINE.md` for intent only; `docs/REFERENCE.md` (generated)
grepped for claims about bounties, keepers and the turnover window.

**Method.** Read first, hypothesise second. Every finding graded EXECUTED has a Foundry test under
`poc/engine/` that inherits the repository's own `V2FactoryFixture` (real `PoolManager`, mined hook, real V2
factory and deployers) and replaces only the stock/USDG V3 venue with the flat-price `MockPool` from
`test/mocks/Mocks.sol` — chosen over the engine suite's `EngineVenue` because it supports **both token orderings and
any decimals**, which the engine suite never exercises. Sizes measured in clean builds of both `5aedceb` and
`origin/codex/v2-main-integration` (`9679614`). The byte cost of the two proposed fixes was measured by applying
them, building, and reverting.

---

## Findings

### E-1 · Low · `maxTradeUsdg` below `minLotUsdg` launches and is permanently inert

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:119-141` (`_validateEngineConfig`; the size limbs at `:139`),
`:334` and `:354` (the `minLotUsdg` dust floors), `:271`. Contrast `src/HedgeFunFactory.sol:199,277`
(`sellChunkUsdg < minLotUsdg` refused twice, with the comment "a chunk under a lot: thousands of calls").

**Status** EXECUTED — `poc/engine/AuditEngineConfig.t.sol::test_E1_*`. **Code defect** (missing validation).

**Mechanism.** The constructor checks fifteen properties of the config (`:130-140`) and not that one action can
ever clear the core's own floor. Every executable path requires `≥ minLotUsdg` of notional (`:334`, `:354`, and
again on the actual fill at `:271`), and every path's notional is `≤ min(maxTrade, remainingDaily) ≤ maxTradeUsdg`
(`:332-333`, `:352-353`). With `maxTradeUsdg < minLotUsdg` the two bounds cannot both hold, so `execute()` ends in
`NotDue` in every state: over-weight, under-weight, after a doubling, a halving, a week, a fresh epoch. `preview()`
reports "not due", which is also what it reports on a healthy treasury that happens to be in band, so nothing
distinguishes a dead strategy from a resting one.

The repository's own `test_previewDoesNotClaimDustBelowTheCoreMinimumIsExecutable` launches exactly this
configuration (`_launch(105, 1e6, 5e6)` against `minLotUsdg = 5e6`) and asserts the not-due — it documents the
symptom as intended preview behaviour without noticing the launch should not have been possible.

**Impact.** Loser: buyers of that strategy token, who paid the curve for a strategy that will never act; the
treasury's share of the raise sits as idle stock forever. Nothing is taken and nothing is destroyed — the stock is
still there, and the inherited `buyback()` still spends LP fees. Gain to anyone: none.

**Conditions.** A creator sets `words[1]` below the listing's `minLotUsdg` — a decimals slip (`100` for `100e6`) is
enough. The config is three raw `bytes32` words set in a separate call from the launch (`setEngineConfig`), with no
front end yet. Status: UNMEASURED (no v2 deployment, no v2 `Defaults`).

**Why Low and not Medium.** The rubric's Medium limb "permanent brick of one non-essential path" is close; here the
bricked path is the essential one, but only for one launch, only by that launch's own creator, and the frozen
config is readable on chain before anyone buys. A reader who weights "buyers paid for a strategy that cannot fire"
over "the creator chose it" will call it Medium.

**Fix** One comparison in `_validateEngineConfig`: `|| maxTradeUsdg < p.minLotUsdg`. **Measured: 0 runtime bytes**
(runtime stays 21,574; initcode 27,866 → 27,913, chunked by the deployer, 21,239 under the 49,152 initcode limit).
Mirror it in `setEngineConfig` as well (see E-6).

### E-2 · Low · No floor on `deadbandBps` against the execution friction the engine itself allows

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:137-138` (`deadbandBps == 0 || deadbandBps >= targetBps` is all
there is). Contrast `src/HedgeFunTreasury.sol:39-42`: "the rule must clear its own execution cost, twice over" —
`tp1Bps < 2·(maxSlippageBps + poolFeeBps)` and `dipBps < 2·(…)` are both refused.

**Status** EXECUTED — `poc/engine/AuditEngineConfig.t.sol::test_E2_*`. **Code defect** (missing floor) in a
creator-chosen parameter.

**Mechanism.** The engine sells when the stock weight exceeds `target + deadband` and buys below `target − deadband`
(`:327-331`, `:347-351`), at a price the venue may set anywhere inside `maxSlippageBps` of the oracle
(`PoolTrader.sol:125-128`) plus the pool fee. With a 50/50 target a relative price move `r` moves the weight by
about `r/4`, so a band of `δ` is crossed by a move of `4δ`; a 1 bp band is crossed by every 0.5% Chainlink print,
and each crossing is a trade that pays up to `maxSlippageBps + poolFeeBps` (130 bp on the fixture's 0.30% tier
with the default 100 bp slippage) to capture 0.5%. The next print in the other direction reverses it at the same
cost. The rule can never clear its own friction, which is the property V1's constructor refuses to launch without.

**Measured** on the flat mock (fee only, no slippage, no sandwich): 20 round trips of ±0.5% prints → **40 trades**
on a 1 bp band, value at the same price **20,000.000000 → 19,999.492120 USDG**; the 5% band beside it traded
**zero** times and lost nothing. On a real pool each leg can additionally cost up to `maxSlippageBps` to whoever
sandwiches the call — and E-3 says that is the only person paid to make it.

**Impact.** Loser: the treasury (so the token's narrative and scorecard). Certain gain to a sandwicher: up to
`maxSlippageBps` of each trade; the pool's LPs take the fee. Bounded per trade by `maxTradeUsdg` and per day by
`maxDailyTurnoverUsdg`, but the latter has no ceiling (E-4). Worst case with a 1 bp band, ~50 prints/day and a
sandwich on every one: ≈ 0.08% of treasury value per day. With the fee alone: ≈ 0.02%.

**Conditions.** A creator chooses a band below `maxSlippageBps + poolFeeBps` (the fixture uses 500 bp; the field
is raw bps in a packed word). No attacker can shrink it after launch, and donations cannot amplify it (a donation
that crosses the band costs its donor more than the sandwich returns). UNMEASURED on chain.

**Why Low.** A recurring leak is the Medium limb, but it exists only for a launch whose creator set the band inside
friction, it is small per event, and it is visible in the frozen config. Flagged for the same reason as E-1.

**Fix** `|| deadbandBps < p.maxSlippageBps + poolFeeBps` in `_validateEngineConfig` (`poolFeeBps` is already an
immutable of `PoolTrader`). A round trip then captures at least `4δ ≥ 4·friction` at 50/50 against `2·friction`
paid; for skewed targets the crossing move is larger still. **Measured together with E-1: 0 runtime bytes.**

### E-3 · Info · Nobody is paid to call `execute()`

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:250-289` — no transfer to `msg.sender` anywhere; `Params.bountyBps`
(`HedgeFunTreasuryBase.sol:65`) is carried, validated (`V2TreasuryDeployer.sol:364`, `HedgeFunV2Treasury.sol:38`)
and never read by the engine.

**Status** EXECUTED — `test_E3_executePaysNoBounty`. **Design decision**, not a defect; recorded because V1's own
comment at `HedgeFunTreasuryBase.sol:394-395` ("without a bounty the only loss-limiting function in the rule would
be the only one nobody is paid to call") states the risk this design accepts.

**Consequence.** Rebalances happen when a searcher finds the sandwich worth the gas, or not at all. That is the same
per-trade exposure as V1 (bounded by `maxSlippageBps`), with two differences: an honest keeper has no reason to
race the searcher, and a treasury whose rebalance is never profitable to sandwich may simply never rebalance. The
first rebalance after every graduation is a deterministic sale of `(1 − target)` of the treasury's stock share
(the treasury graduates with zero USDG), in `maxTradeUsdg` chunks per cooldown — a predictable, MEV-visible
sequence. No loss beyond the inherited slippage bound; no gain to anyone but the sandwicher.

### E-4 · Info · The daily cap is a UTC calendar epoch, and has no ceiling

**Location** `:296-299` (`uint64(block.timestamp / 1 days)`), `:139` (`maxDailyTurnoverUsdg < maxTradeUsdg` is the
only bound on `words[2]`). `docs/STRATEGY_ENGINE.md:38-40` states the epoch semantics and calls the choice an open
release decision.

**Status** EXECUTED — `test_E4_*`: with cooldown 1 s, the full cap clears at 23:59:58 UTC, is refused at 23:59:59
(`NotDue`, same epoch), and clears again at 00:00:00 — **2× `maxDaily` two seconds apart**. `maxDaily =
type(uint256).max` is accepted at construction. **Documentation/configuration**, consistent with the code.

**Why Info.** The "daily" bound is a creator's own choice with no owner ceiling; the only owner-set bound on the
engine's turnover is `maxTradeUsdg ≤ sellChunkUsdg` per call (`:139`). But the engine's turnover is *structurally*
bounded regardless: it only ever trades toward the target, so total turnover is bounded by how far price and
donations move the weight, not by the cap. The cap is a belt over that brace. The 2× at midnight is the documented
open item.

### E-5 · Info · The out-of-range action word is refused by the decoder, not the engine; the engine's check is dead

**Location** `:404-407` (`abi.decode(result, (StrategyIntent))`), `:374-377` (`uint8(intent.action) <=
uint8(StrategyAction.BuybackBurn)`), `:404` (`size > policyReturnLimit`, redundant with `size != 160` because the
limit is pinned to 160 at `:135`). `test/mocks/StrategyPolicyMocks.sol:160`: "A spot engine must reject this raw
action word before attempting an enum ABI decode."

**Status** EXECUTED — `poc/engine/AuditEnginePolicy.t.sol::test_E5_*`: a policy with spot capabilities returning
action word `64` makes `execute()` revert **with empty revert data** (Solidity's decoder validation, not
`Panic(0x21)`, not `BadPolicyReturn`), nonce, cooldown, epoch, state and balances unchanged. **Cosmetic code
issue** — fails closed; the mock's comment describes a check that was not implemented, and the check at `:376` can
never be false.

Two related diagnosability notes, same status: `preview()` reverts (`PolicyFailure`) rather than answering
`(false, Hold, 0)` when the policy reverts or runs out of gas (measured in `test_safe_gasBomb*`); and the policy is
called (`:258`, up to 500k gas) *before* the cooldown check (`:262`, `:295`), so a keeper who calls during a
cooldown pays the policy's gas to be told `NotDue` (from `V2RebalancePolicy`, which holds during cooldown) or
`Cooldown` (from a policy that ignores it).

### E-6 · Info · `setEngineConfig` validates no word; the failure surfaces as an opaque `TreasuryDeployFailed`

**Location** `src/v2/V2TreasuryDeployer.sol:303-319` (policy and schema are checked, `config.words` are not),
`:394-397` (`predict` builds the same initcode without running the constructor), `:368-376`. Contrast
`src/HedgeFunFactory.sol:193-196`: "A constructor's revert reason does not survive CREATE2, so a default the
treasury refuses bricks every launch as an opaque `TreasuryDeployFailed` until someone works out which of two dozen
numbers it was" — V1 mirrors every constructor check for that reason.

**Status** EXECUTED — `test_E6_*`: `target = deadband = cooldown = maxTrade = maxDaily = 0` is accepted by
`setEngineConfig`, `predict` returns an address and terms, `launch` reverts `TreasuryDeployFailed`; likewise
`maxTradeUsdg = uint128.max + 1` against the fixture's `sellChunkUsdg`. **UX/code**; nothing is lost (the launch fee
transfer is inside the reverted transaction).

**Coverage note.** No test in the tree exercises the `maxTradeUsdg > p.sellChunkUsdg` limb (`:139`): every fixture
sets `sellChunkUsdg = type(uint128).max`. The PoC above is the first to hit it. The limb works.

**Fix** Re-run `_validateEngineConfig`'s word checks in `setEngineConfig` (the deployer has 13,839 bytes; the
engine's `Params` are not available there, so `minLotUsdg`/`sellChunkUsdg` limbs need the factory's defaults or a
`view` on the engine chunk — the schema/range limbs are free).

### E-7 · Info · Codehash pinning does not pin semantics: mutable-storage, proxy and EIP-7702 policies all pass

**Location** `V2TreasuryDeployer.sol:211-278` (`registerPolicy`: `code.length != 0`, `policyMetadata()` answers,
`codehash` recorded), `:310`, `:348`, `HedgeFunV2EngineTreasury.sol:134`, `:394`. `docs/STRATEGY_ENGINE.md:29-32`
says exactly this ("cannot prove that an implementation does not read mutable storage or delegate through a
proxy … governance review must still reject mutable and proxy policies").

**Status** EXECUTED — `test_E7_*`: (a) a policy with a public `setAction` sells one bounded chunk, is switched to
`Hold` by an arbitrary caller (the policy has no owner), and the treasury's strategy is off; switched back, it is
on, still capped. Same address, same codehash. (b) `MutableStrategyPolicyProxy` passes `registerPolicy` (its
fallback delegates `policyMetadata()`), `setEngineConfig` and the constructor, launches, and is re-pointed
afterwards. **Documented limitation**, correctly described; the point of executing it is to record the blast
radius: a switched policy can **only** choose *when* to act among the moments the engine already permits (direction
gates `:328`/`:348`, size caps, dust floors, cooldown, epoch). It cannot pick a route, recipient, pool or amount
beyond the cap, and it cannot make the engine trade against the deadband. Worst case is a strategy that stops.

**EIP-7702 (REASONED, `evm_version = cancun` in `foundry.toml` so not executable here).** A delegated EOA has 23
bytes of code, so it passes `code.length != 0`; its `EXTCODEHASH` is the hash of the delegation designator, which is
stable while the *delegate* is a proxy. `CLAUDE.md` records that low-key EOAs on this chain already carry 7702 code
from sweeper bots. The governance rule in the doc should say "no EOA, no proxy, no mutable storage" explicitly.

### E-8 · Info · A launched salt's deployer record stays writable

**Location** `V2TreasuryDeployer.sol:295-300`, `:303-319` — neither setter checks whether the salt has launched.

**Status** EXECUTED — `test_E8_*`: after launch, `setEngineConfig` on the same `(symbol, nonce)` rewrites
`engineConfigOf(salt)` and emits `EngineConfigSet` again; `setStrategyKind` rewrites `strategyKindOf(salt)` to 0.
The treasury's `engineConfig()` and immutables are unchanged and a relaunch on the salt cannot happen (the token's
CREATE2 address is occupied; note the collision consumes the whole gas limit, which is V1 behaviour). **Code
hygiene**: an indexer that reads the deployer's record or its events instead of `treasury.engineConfig()` can be
made to disagree with the chain by the creator. Read the treasury.

### E-9 · Info · Remediation budget after this branch

Measured 2026-09-27, `forge build --sizes`, clean builds, `via_ir` off (this repository), `optimizer_runs = 1`.

| contract | `9679614` (main-integration) | `5aedceb` (this) | free | note |
|---|---:|---:|---:|---|
| `HedgeFunV2EngineTreasury` | — | **21,574** | **3,002** | initcode 27,866, chunked; 21,286 under the 49,152 initcode limit |
| `V2RebalancePolicy` | — | 1,799 | 22,777 | |
| `V2TreasuryDeployer` | 4,773 / init 31,947 | **10,737** / init 38,024 | 13,839 / 11,128 | the only pre-existing contract this PR grows |
| `HedgeFunV2Treasury` | 21,602 | 21,602 | 2,974 | the enum append costs nothing |
| `HedgeFunV2BuybackTreasury` | — | 14,859 | 9,717 | unchanged |
| `HedgeFunV2Factory` | **24,551** | 24,551 | **25** | round 3 measured 27 at `03ad70e`; the 2 bytes went on `v2-main-integration` |
| `CurveDeployer` | **24,564** | 24,564 | **12** | round 3 measured **176**; the 164 bytes went on `v2-main-integration` (`0d9fca8`, the LP-fee-leg fix) |
| `TreasuryDeployer` (v1) | 23,575 | 23,575 | 1,001 | round 3: 1,020 |
| `HedgeFunHook` | 19,354 | 19,354 | 5,222 | |
| `HedgeFunFactory` (v1) | 18,929 | 18,929 | 5,647 | byte-identical to `main`, as in round 3 |

**This PR changes no deployed-contract size except the deployer's.** But the two contracts round 3 named as the
binding budgets are now at 12 and 25 bytes: **nothing can be added to `CurveDeployer` or `HedgeFunV2Factory`
without first removing something.** That is the other lane's delta to attribute; it is recorded here because "the
engine has 3,002 bytes free" is true and would mislead a reader into thinking the release has room.

Both engine fixes proposed above (E-1, E-2) were applied together and measured at **0 runtime bytes, +47 initcode**.

### E-10 · Info · Unused V1 rule parameters still gate an engine launch

`Request` (`HedgeFunFactory.sol:52-78`) carries `tp1Bps/tp2Bps/dipBps/stopBps/lotBps/bandBpsPerHour`; the engine
reads none of them (`_canAddLot` is `false`, `execute()` is fully overridden), yet `HedgeFunTreasury.sol:35-42`,
`HedgeFunV2Treasury.sol:38` and `V2TreasuryDeployer.sol:360-366` still refuse a launch whose *ignored* rule does not
clear friction, and the engine config travels in a separate `setEngineConfig` call keyed by the creator's own
`msg.sender` — a launcher contract that launches "on behalf of" a creator (`launchers[]`) cannot set it for them.
REASONED; UX/documentation. `HedgeFunV2BuybackTreasury` has the same shape and says so in its header; the engine's
header does not.

### E-11 · Info · `policyGasLimit` is frozen

`HedgeFunV2EngineTreasury.sol:37`, `:398-400`. The manifest's `maxGas` becomes an immutable and is the exact gas
handed to every `decide()`. A hard fork that reprices the opcodes `decide()` uses past that number turns every
`execute()` into `PolicyFailure` for good; `buyback()` survives. The fixtures register 150,000 for a policy that
needs a small fraction of it; the ceiling is 500,000. REASONED; the same class as every other frozen constant in
this protocol, listed so the registration guidance can say "register with headroom".

---

## Checked and found safe

Each with the line that makes it safe, and the PoC where one exists. Proved at `5aedceb`.

**Custody and authority**

1. **The only outward stock/USDG movement is the V3 swap callback paying the listed pool.** `PoolTrader.sol:141-145`:
   `msg.sender == pool && _swapping`, `pool` immutable from the owner's listing; pays exactly the pool's positive
   deltas. The engine adds no transfer, no `approve`, no new callback. PoC: allowances to the venue, the policy and
   the caller are all zero after a sell and a buy (`AuditEngineCustody.t.sol`, four suites).
2. **The buy-back's stock leaves only through `poolManager.settle()`** inside `unlockCallback`, gated by `msg.sender
   == poolManager && _swapKind == 2` (`HedgeFunTreasury.sol:144-148`, `HedgeFunTreasuryBase.sol:521-523`) —
   inherited, unchanged.
3. **The policy has no custody.** It is `STATICCALL`ed (`:400`), so it cannot write state, cannot call a
   non-view function, and holds no allowance. Repo test: SSTORE trapped. PoCs: 159-byte return → `BadPolicyReturn`;
   gas bomb → `PolicyFailure` costing about the manifest's gas, not the block; dirty `uint64` nonce word → decoder
   revert; action word 64 → decoder revert; each with nonce, cooldown, epoch, state and balances unchanged.
4. **Re-entry from inside the swap is refused.** `execute`, `book`, `buyback`, `creditLiquidityFee` share one
   `ReentrancyGuard`. PoC: a venue that calls all three from inside `swap()` before paying — 0 of 3 succeed, the
   outer `execute()` completes (`test_safe_reentryFromInsideTheSwapIsRefused`).
5. **The hook never calls into a treasury** — it only `safeTransfer`s stock (`HedgeFunHook.sol:681`; no `.book(`
   and no `IHedgeFunTreasury(` call in the file), so the engine's `nonReentrant` `book()` cannot deadlock the
   buy-back's `afterSwap`.
6. **Sells cannot reach the buy-back bucket.** Offered `≤ bookedStock` (`:333`); `creditLiquidityFee` credits
   `buybackStock` only (`HedgeFunV2Treasury.sol:170-174`); `buyback()` spends `≤ buybackStock` (`:469`). PoC: credit
   7 stock of LP fees, sell to target in five calls, bucket untouched, balance covers both buckets.
7. **Donations.** `_bookInventory` sweeps `unbookedStock()` into `bookedStock` with no oracle and no lot
   (`:166-174`); `unbookedStock()` floors at 0 (`HedgeFunTreasuryBase.sol:226-229`) so an issuer burn or a
   fee-on-transfer cannot underflow it (it inflates `bookedStock`, and a later sell of more than the balance reverts
   in the callback — documented as an asset-admission rule, `STRATEGY_ENGINE.md:34-36`). The invariant
   `bookedStock + buybackStock == balance` holds in the repo's invariant suite and in every PoC.
8. **`buyback()` interaction.** The engine never funds `buybackStock` from strategy proceeds (a sell produces USDG),
   so the token's buy-back is funded by LP fees alone — stated in the engine's header (`:160-161`). `execute()`
   calls `_notePrice(p)` (`:263`) so the buy-back's five-day sizing fallback keeps a fresh reference.

**Commitment integrity**

9. **Config → initcode → CREATE2 → terms.** `_code` appends `abi.encode(config)` (`:339-356`; 192 bytes, a static
   6-word struct, exactly the 9-argument constructor's ABI after the factory's 672-byte 8-argument encoding); the
   address is in `_terms` (`HedgeFunFactory.sol:301`); a config change after `predict` reverts `Restated` (repo
   test). A stranger's `setEngineConfig` lives under a salt containing *their* `msg.sender` (`:314`) and cannot
   touch the creator's prediction (PoC `test_safe_strangerCannotTouchTheCreatorsSalt`).
10. **Post-launch immutability.** `policyImplementation`, `policyRuntimeCodeHash`, `policyCapabilities`,
    `policyGasLimit`, `policyReturnLimit`, `configHash` are immutables (`:34-39`); `_engineConfig` has no setter;
    `disablePolicy` flips one bool for *future* launches (`:284`; repo test); `configHash` binds chain id, the
    treasury's own address, factory, stock, USDG, the config and the manifest (`:102-116`).
11. **Registry append-only.** `_kinds` is only ever pushed (`:187`, `:204`); a policy key is set once (`:253`) and
    is the hash of every manifest field (`:240-252`), so "the same code with a different `maxGas`" is a different
    policy; disabling is one-way. The owner *can* re-register disabled code under a new audit hash — by design.
12. **Codehash pinned four times**: constructor (`:134`), `setEngineConfig` (`:310`), `_code` at predict/deploy
    (`:348`), and every `_policyIntent` (`:394`). Post-Cancun there is no `SELFDESTRUCT` that outlives its
    transaction, so the runtime check is defensive; if it ever fires the treasury's strategy is dead and its
    buy-back is not.
13. **`deploy()`'s post-check** (`:380-388`): `engineVersion`, `strategyId` and a non-zero `configHash` read back
    from the new contract, so registering a non-engine kind as an engine fails closed (opaque, see E-6). Kind 0
    and kind 1 take the unchanged 672-byte path (`configLen = 0`, `:331`).
14. **`makeChunks` is open and inert** (`:137-141`): only the owner registers (`:183`, `:197`), and registration
    records `keccak(a.code ++ b.code)` (`:202`). A split that happened to start chunk B with `0xEF` would fail at
    `makeChunks` (EIP-3541), i.e. at deployment time, loudly; it does not today.

**Limits and state**

15. **Return bound.** `returndatasize()` is read before anything is copied (`:400-404`); the 64 KiB return is
    refused without a copy (repo test), 159 bytes is refused (PoC).
16. **Gas bound.** `staticcall(gasLimit, …)` with `gasLimit ≤ 500,000` enforced at registration (`:220`) and
    construction (`:135`). PoC: the gas bomb costs ≈ the manifest, `execute()` and `preview()` both fail closed.
17. **Capabilities enforced at execution**, not just at registration: `SPOT_SELL`/`SPOT_BUY` (`:328`, `:348`) →
    `BadIntent`; `BuybackBurn` → `BadIntent` (`:318`); options bits refused in the constructor (`:136`; repo tests
    including an over-broad kind). PoCs: sell-only policy proposing a buy; spot policy proposing `BuybackBurn`.
18. **Direction gates.** A sell needs `stockValue > totalValue·(target+deadband)/BPS`, a buy `< ·(target−deadband)`
    (`:327-331`, `:347-351`): no policy can sell an under-weight book or buy an over-weight one, whatever it asks.
19. **Sizing.** Sell `≤ min(maxTrade, remainingDaily, excess)` in USDG at the oracle, converted with a floor
    (`:331-333`); buy `≤ min(requested, maxTrade, remainingDaily, deficit, usdgInventory)` (`:351-353`). Post-swap
    `turnover ≤ remainingDaily` (`:272`) cannot fail for a V3 exact-input (spent ≤ offered) and is a re-check.
    Repo test: a `uint256.max` request is capped to `maxTrade`; rounding never sells through the target.
20. **Dust floors, before and after the swap.** `< minLotUsdg → NotDue` before (`:334`, `:354`) and on the actual
    fill after (`:271`) — the second revert unwinds the swap, its transfers, `_notePrice` and `_noteTokenSpot`
    atomically (repo tests at fill 499/500 bp; the invariant handler drives fills of 1/499/500/501 bp).
21. **Partial fills** debit `actualInput` and credit `actualOutput` (`:336`, `:356`; repo fuzz, both directions).
22. **Cooldown** `block.timestamp < lastStrategyAt + cooldown` (`:295`; `uint32` cooldown, no overflow); first
    action free; boundary inclusive (invariant handler warps 59/60/61). `V2RebalancePolicy` applies the same test
    and also guards `block.timestamp < lastActionAt` (`:47`).
23. **Nonce/state advance only after everything** (`:273-277`): there is no `try/catch` anywhere in `execute()`,
    so every failure is a revert; repo invariant `strategyNonce == successfulExecutions`. `policyState` is one
    word the policy sets on success and nothing reads but the policy.
24. **Oracle and venue health.** `health()` (`HedgeFunV2Treasury.sol:177-180` → `HedgeFunTreasury.sol:82` →
    `PoolTrader.sol:104-117`): live feed, spot within `maxDeviationBps` of the feed, spot within `maxDeviationBps`
    of the 600 s mean. **And** `tryPrice()` live (`:254-255`), which is false on any calendar closure and on
    `oraclePaused()` (`PriceOracle.sol:47-48`) — so the band/pool-only branch of `_priced()` is unreachable in the
    engine and `_poolOnlyPace` is not needed. The invariant handler pauses the oracle, stales the feeds and shoves
    the venue; the PoCs move feed and venue together.
25. **The context is priced by the oracle, not the venue.** `stockValueUsdg = _ruleValue(bookedStock, p)` with
    `p` from `health()` (`:366`); the venue only gates (24) and fills, and the fill is bounded by `oracle ±
    maxSlippageBps` with the realised average re-checked (`PoolTrader.sol:125-128`). A venue shoved past the
    gate gives `Unhealthy`; inside it, at most `maxSlippageBps` — the same bound as V1 and round 3's safe list.
26. **Arithmetic.** All products are 512-bit `mulDiv`; `stockValue + usdg` overflow is guarded (`:300`, policy
    `:60`); `totalValue == 0 → NotDue` (`:302`); `targetBps ∈ [deadband+1, BPS−deadband−1]` (`:137-138`) so
    `target − deadband ≥ 1` and `target + deadband ≤ BPS−1` — no underflow at `:347`, no overshoot past BPS. The
    policy divides by `stockValueUsdg` only on the sell branch, where it is `> upperValue ≥ 0` (`:77-79`), and
    holds on `price == 0` (`:60`). `_ruleStockFor` and `_ruleValue` floor in the treasury's favour.
27. **The policy's looser validator is harmless.** `V2RebalancePolicy._validate` (`:86-106`) accepts `deadband ==
    0`, `deadband == target`, `target + deadband == BPS` and `cooldown == 0`; the engine's constructor refuses all
    four, so for any launched config the policy's `BadConfig` is unreachable. Fine, but two validators for one
    struct will drift; the engine's is the binding one.
28. **Token ordering and decimals.** PoCs: stock-as-token0 and USDG-as-token0, at 18 and 6 stock decimals — a sell
    then a buy, each moving exactly the pool's reported amounts of the right asset in the right direction, with
    value conservation within fee+slippage. (The engine suite covers stock-as-token0 at 18 decimals only.)
29. **Graduation → wire → book order.** `executeGraduation` wires the treasury (`CurveDeployer.sol:88`) before
    `_graduate` sends the treasury's share and try/catches `book()` (`HedgeFunV2Factory.sol:154-155`); the engine's
    `book()` needs `hook != 0` (`:167`), which holds by then; anything left unbooked is swept by the next `execute()`
    (`:251`). `execute()` before graduation is `Unhealthy` (`health()` false while `hook == 0`).
30. **`preview()` and `execute()` agree**: `bookedStock + unbookedStock()` in the view (`:181`) equals the post-book
    `bookedStock` in the action (`:251`, `:257`); the same limits and dust floors (`:191-247`); repo test that
    preview includes the daily gate.
31. **The `Action` enum append** (`HedgeFunV2Treasury.sol:29`) leaves values 0–2 and both kind-0 and kind-1 runtime
    bytes unchanged (21,602 and 14,859 on both branches).
32. **Nothing here touches V1.** `HedgeFunFactory` and `HedgeFunTreasury` are byte-identical across the two branches
    (E-9 table); the nine live strategies are unreachable from any of this.

---

## Not covered

- **The live-venue fork suites** (`RH_FORK=1`, 52 skipped): the engine against a real V3 pool with real depth is
  UNMEASURED here. The PoC venue is flat-priced; every slippage statement above is the bound, not a measurement.
- **The v2 deployment configuration** — no v2 `Defaults`, no listing gates, no registered policy or engine kind
  exist on chain. E-1, E-2 and E-4 live inside parameters nobody has set. This lane certifies no configuration.
- **`docs/REFERENCE.md`** (378 regenerated lines) beyond a grep for claims about bounties, keepers and the
  turnover window (it makes none that contradict the code); the claims lane owns it.
- **Economic tuning** of `target/deadband/cooldown/maxTrade` against measured pool depth, and whether a
  constant-mix rebalancer is a good strategy at all — the economics lane.
- **EIP-7702** behaviour is REASONED (tests run at Cancun).
- **`HedgeFunHook.sol` and `V2LiquidityVault.sol`** were traced only for their calls into a treasury, not re-read.
- **Mutation testing** of the engine suite (round 3's method for coverage holes) was not run; the one hole found
  (the `sellChunkUsdg` limb, E-6) was found by reading.
