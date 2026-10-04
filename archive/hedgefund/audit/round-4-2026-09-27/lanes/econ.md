> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Round 4, lane: mechanism design and manipulation cost of the rebalance engine

Audited: `origin/codex/v2-strategy-engine` @ `5aedceb` (PR #84 tip `9679614` + PR #91), 2026-09-27/28. Baseline:
round 3 (`audit/round-3-2026-09-27/`, rubric reproduced there in `FINDINGS-FULL.md` §1, applied unchanged here).
Read-only: no transaction signed, no RPC called; every number below comes from offline Foundry tests against this
repository's own `V2FactoryFixture` (real PoolManager, real hook, real factory; the stock/USDG venue and feeds are
mocks) or from two pure-Python models that vendor the project's own `lab/trend.py`.

Evidence: [`../poc/econ/run.sh`](../poc/econ/run.sh) (11 tests, **11 passed / 0 failed**, no network),
[`../poc/econ/sandwich_model.py`](../poc/econ/sandwich_model.py), [`../poc/econ/constant_mix.py`](../poc/econ/constant_mix.py).

## What the engine is, in the terms that matter here

`HedgeFunV2EngineTreasury.execute()` (`src/v2/HedgeFunV2EngineTreasury.sol:250-289`) is permissionless and pays
nothing. It books every stock it holds outside `buybackStock` as inventory (`:166-174`, no oracle, no minimum),
values that inventory at the **Chainlink** price `p` from `health()`, asks `V2RebalancePolicy` whether the stock
share `S / (S + U)` is outside `[target - band, target + band]`, and if so trades `min(maxTrade, distance to
target, remaining daily)` through the inherited `PoolTrader._swapBounded` (`src/PoolTrader.sol:122-129`): an
exact-input V3 swap whose price limit is `p x (1 -/+ maxSlippageBps)` and whose realised average must clear
`p x (1 -/+ (maxSlippageBps + poolFeeBps))`. Before that, `health()` (`:104-117`) demands the pool's spot within
`maxDeviationBps` of `p` and within `maxDeviationBps` ticks of the pool's own 600 s mean. One action per `cooldown`;
turnover per UTC day capped at `maxDailyTurnoverUsdg`. A sale's proceeds are USDG inventory. Nothing an action does
touches `buybackStock`.

Three consequences drive every finding:

1. **The pool cannot trigger an action; only Chainlink can.** The deadband is measured at `p`. Pushing the pool can
   only *block* (`health()` shuts past 50 bps) or *worsen the fill*. So the question is never "can an attacker make
   it trade", it is "what does the fill cost when the attacker chooses the moment" -- and anyone may choose it.
2. **The room between the two gates is the sandwich.** Spot may sit anywhere inside `maxDeviationBps` (50) of the
   oracle when the call begins; the fill may run to `maxSlippageBps` (100) past it. That 50 bps of room is what a
   counterparty positioned at the gate's edge collects, less two pool fees.
3. **Graduation hands the engine 100% stock and 0 USDG.** Against any target under 100% its first act is to sell
   the difference, at once, into the listing's V3 pool.

## Findings

| ID | grade | status | one line |
|---|---|---|---|
| X-1 | **Medium** | EXECUTED | The rebalance is a predictable, permissionless, unpaid order; a sandwich inside the gates costs the treasury +50 bps per action and pays the attacker on every 0.05% listing once `maxTrade` exceeds ~10% of the pool's USDG-per-1% depth. Four of twelve live listings are 0.05% pools at the default gates. |
| X-2 | Low | EXECUTED | `maxDailyTurnoverUsdg` is a UTC calendar day: 2x the budget in the ten minutes around 00:00 UTC. |
| X-3 | Info (safe) | EXECUTED | Weekend, holiday and `oraclePaused()` fail closed -- even where kind 0's band path is open. A print inside `maxStockAge` is traded on while the pool sits within 50 bps of it; worst fill vs the stale print 88 bps measured, vs the true price stale-gap + 130 bps. |
| X-4 | Low | EXECUTED | The graduation lot is sold down to target in minutes (3 actions, $5,012 of $10,000, 56 bps) into the pool the raise just bought through: round 3's M-2 in reverse, undisclosed. |
| X-5 | **Medium** | EXECUTED | The only floors are the constructor's: deadband 1 bp, cooldown 1 s, unbounded day, target 1 bp all deploy; the creator-side setter validates nothing and `predict()` quotes what `launch()` refuses. At 1 bp every 0.5% Chainlink print is an action. Round 3's M-4 pattern. |
| X-6 | Low | EXECUTED | `execute()` pays no bounty; `bountyBps` is carried and ignored. The only party paid to call it is the counterparty of its fill. |
| X-7 | **Medium** | EXECUTED | Kind 2 never funds a burn from strategy gains: `buybackStock` is LP-fee only. Model: 0.19% of supply burned on every path against kind 0's 2.20% on +3%/day. Not stated anywhere a buyer would read. |
| X-8 | Info (safe) | EXECUTED | A donation can force an action; it costs the donor ten times the most a sandwich of that action could return. |

Loser in every graded finding: the treasury (token holders through it). Certain gain to an unprivileged caller:
X-1 only, and only on the 0.05% listings. No finding reaches the rubric's High: nothing here takes principal,
needs a Safe misbehaving, or needs a TWAP manipulation.

---

### X-1 · Medium · The sandwich inside the gates

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:250` (`execute`, permissionless, no bounty),
`src/PoolTrader.sol:104-129` (`_health`, `_swapBounded`), `src/HedgeFunTreasury.sol:138-140` (`_swapStock`, not
`virtual`), `docs/ADDRESSES.md:50-63` (fee tiers and gates of the live listings).

**Status** EXECUTED (`test_X1_*`, three tests) and modelled (`sandwich_model.py`).

**Mechanism.** The attacker pushes spot to the edge of the deviation gate (49 bps under the oracle for a treasury
sell), calls `execute()` in the same transaction, and buys back exactly what it sold. `health()` passes: 49 < 50
against the oracle, 49 ticks against a 600 s mean that has not moved. The treasury's exact-input swap then fills
from -49 bps down to the -100 bps limit. On the constant-liquidity V3 step in the PoC, $10,000 of USDG per 1% of
depth, one $2,000 action of the graduation sell-down:

| tier, gates | treasury cost vs oracle, no push | pushed | (slip+fee) floor | attacker P&L |
|---|---|---|---|---|
| 0.30%, 50/100 | 39 bps | **88 bps** | 130 bps | **-$19.86** |
| 0.05%, 50/100 | 14 bps | **63 bps** | 105 bps | **+$4.86** |

The treasury pays the same +49 bps either way. Who collects it is decided by the fee tier: the attacker's push
round-trips two pool fees on ~0.5 x depth of stock, so the capture is `(maxDeviationBps - 2 x poolFeeBps) x
turnover - impact`. On a 0.30% pool that is negative for every depth and every `maxTrade` (the model sweeps $3.3k
to $250k per 1% and $100 to $10,000 per action: no positive cell). On a 0.05% pool it turns positive at
**`maxTrade` = 10.1% of the pool's USDG-per-1% depth, independent of the depth** (breakeven sweep in the model),
and grows with the action: +$0.84 at $500 on $3.3k, +$4.96 at $2,000 on $10k, +$22.30 at $10,000 on $55k. The
per-listing gates of `docs/V2_SANDWICH_FORK.md` (20/50 on a 5 bps pool) shift nothing: 20 > 2 x 5, same breakeven,
smaller absolute (+$1.99 on the $10k/$2,000 cell). The project's fork test in that document lost money for the bot
because it pushed 10 bps against a 20 bps gate on a $5.85 treasury order -- one cell of this grid, and the one the
document itself says not to generalise from.

**Why the gate cannot simply be tightened.** The Chainlink equity feeds print on a 0.5% move, so between prints
the pool legitimately wanders up to ~50 bps from the feed; a 20 bps gate shuts `health()` for most of the session
(the repository's own TR-4 note in `LISTING_CANDIDATES.md:60`). The 50 bps room is structural on this oracle. The
levers are size against depth, and frequency.

**Which gate binds.** Trigger: Chainlink only. Marginal fill: `maxSlippageBps`. Average fill: `maxSlippageBps +
poolFeeBps`. Attacker's room: `maxDeviationBps` (the fill starts wherever spot sits inside it). Profitability:
`maxDeviationBps > 2 x poolFeeBps` -- true on every 0.05% listing at the default gates, false on every 0.30% and
1% listing. Frequency: `cooldown` (creator, floor 1 s), the deadband against the feed's print rate, and
`maxDailyTurnoverUsdg` (creator, no ceiling). Size: `maxTradeUsdg <= sellChunkUsdg` (owner per listing, an
absolute number, 2,000 default, 1,000 on USAR/AMD/INTC) -- the one bound the creator does not set.

**Cost and gain, in bps of treasury value.** Per action the treasury pays up to `maxDeviationBps` extra on the
action's turnover: `50 x (turnover / value)` bps of value, so 50 bps x the band width when an action is one
band-crossing (2.5 bps of value at a 5% band, 0.5 at 1%), and **25 bps of value on graduation day**, when half the
treasury turns over (X-4). Per day, `50 x min(maxDaily, maxTrade x 86400 / cooldown) / value` bps -- with the
repository's test config (100 / 500 per day) on a $10,000 treasury, 2.5 bps/day; with the rehearsal chunk and no
daily cap, bounded only by how often the feed crosses the band (X-5). The attacker keeps that less two fees on
half the depth: $4.86 on the cell above, at most ~$20 per action on a $10k-deep 0.05% pool.

**Live exposure, from `docs/ADDRESSES.md` (2026-09-22) and round 3's depth reads (2026-09-27).** NVDA, SPCX,
GOOGL and GME are listed on 0.05% pools with the default 50/100 gates and the 2,000 chunk. Round 3 measured GME at
+295 bps for $40k (~$13.5k per 1%): a $2,000 action is 15% of that, above breakeven. GOOGL at +36..49 bps for $40k
(~$90k per 1%) is below it at the 2,000 chunk; NVDA is deeper still. **On today's listings the profitable case is
GME and any thin 0.05% listing added later**; every 0.30% listing is safe from the *profitable* sandwich but still
pays the +50 bps to whoever sits at the gate's edge for other reasons.

**Condition list.** (1) a kind-2 launch on a 0.05% listing -- none exists, v2 is undeployed, UNMEASURED; (2)
`maxTradeUsdg >= 10% x` the pool's USDG-per-1% depth at call time -- true for GME at the default chunk (round 3's
read, re-measure); (3) the treasury outside its band with the cooldown expired -- certain for the first minutes
after graduation, and on every band-crossing after that; (4) an attacker willing to hold the push against arbs
for one block -- atomic, no ordering privilege needed on a sequencer chain.

**Fix.**
- 0 bytes, owner: size `sellChunkUsdg` per 0.05% listing at **<= 10% of the measured USDG-per-1% depth**, re-read
  at listing time like round 3's M-2 rule (GME: <= ~$1,300 today). This makes the sandwich a loss everywhere.
- ~150 bytes, engine: bound the fill from the pre-call spot as well as from the oracle -- `limit = min(oracle x
  (1 - slip), spot x (1 - impactCap))` with the same `impactCap` on the average -- so the attacker's room is
  `impactCap`, which can be set under `2 x poolFeeBps`. Needs `HedgeFunTreasury._swapStock` to become `virtual`
  and an override in `HedgeFunV2EngineTreasury` (3,002 bytes free). `HedgeFunTreasury.sol` already differs from
  the live v1 build in this PR (round 3, +55), so the v1 verification argument against touching it is gone.
- Do not rely on a bounty for this (X-6): a bounty makes an honest keeper race the bot, it does not shrink the room.

### X-2 · Low · The turnover cap is a calendar day

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:201-204, 296-299`; `docs/STRATEGY_ENGINE.md:38-40` says so.

**Status** EXECUTED (`test_X2_utcDayBoundaryDoublesTheDailyBudgetInTenMinutes`): five $100 actions at 23:54..23:58
UTC, a sixth refused at 23:59 (`NotDue`), five more from 00:00 -- **$1,000 of a $500/day cap in ten minutes**,
the 60 s cooldown the only thing between them.

**Impact.** Every per-day bound in this report doubles for the 24 h window straddling midnight UTC, including X-1's
and X-5's. The document acknowledges it and defers the decision to "a release". Bounded (2x), documented, no actor
gains beyond X-1's per-action capture -- Low.

**Fix** Either a rolling limiter (a small ring of the last actions' timestamps and sizes, ~300 bytes, fits) or
accept and halve `maxDailyTurnoverUsdg` in the floors. Whichever, decide before a kind-2 launch, as the document
says.

### X-3 · Info (safe) · Closure, pause and the stale print

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:252-255` (`health()` **and** a live `tryPrice()`),
`src/PriceOracle.sol:22-23, 46-54` (`MAX_STOCK_AGE` 48 h, calendar and pause gates), `src/HedgeFunTreasury.sol:90-111`
(kind 0's band path).

**Status** EXECUTED (`test_X3_closureAndPauseFailClosed_staleWithinAgeTrades`).

**What holds.** With a band-enabled request (`bandBpsPerHour = 200`, the ceiling) during a scheduled closure,
`health()` still answers `ok` with the frozen print -- and with the pool pinned 2% away it answers `ok` with a
*pulled* price: that is kind 0's closure path, which `stopLoss` refuses and `takeProfit`/`buyDip` take. The engine
takes none of it: `execute()` reverts `Unhealthy` on the separate `tryPrice()` check, `preview()` says not due.
`oraclePaused()` reverts the same way. **Across a weekend the rebalance cannot execute at any price.** The
"~65 h frozen feed" of the project's notes is therefore a liveness fact for kind 2, not a pricing one.

**What is open, and its bound.** On an open day the feed prints on 0.5% deviation and, if the network is up, the
true price is within 0.5% of the last print by construction. A print 25 h old but inside `maxStockAge` (26 h in
the fixture; 48 h is the constructor ceiling) is traded on when the pool sits within 50 bps of it; with the pool
49 bps under the stale print the measured fill was **88 bps under it**. So the worst fill relative to the true
price is `stale gap + maxDeviationBps + maxSlippageBps + poolFeeBps`: 0.5 + 0.5 + 1.0 + 0.3 = **2.3%** while the
oracle network prints, unbounded by the feed alone if it stops mid-session -- but then the deviation gate is the
guard, and holding the pool within 50 bps of a print the market has left costs the pinner the whole arb flow
against a gain of at most 1.3% of one capped action. Same shape as kind 0, inherited, and the repository's
`CLAUDE.md` already states there is no secondary oracle. Nothing to fix in the engine; the floors in X-5 bound how
often the 2.3% can be paid.

### X-4 · Low · The graduation lot is sold down in minutes

**Location** `src/v2/HedgeFunV2Factory.sol:153-156` (graduation sends stock only), `src/v2/HedgeFunV2EngineTreasury.sol:321-339`.

**Status** EXECUTED (`test_X4_graduationLotIsSoldDownToTargetImmediately`), modelled (`constant_mix.py` table C).

**Mechanism.** The treasury opens at 100% stock. At target 50% / band 5% / `maxTrade` 2,000 / no daily cap, on a
pool as thin as AMD's ($3.3k per 1%): **3 actions, 3 minutes, $5,012 of a $10,000 treasury sold, $4,983 received,
56 bps** -- every fill short at the -1% limit, the pool refilled by arbs between cooldowns. With an hourly keeper
the model needs 5 actions and one day; with the repository's test config (100 / 500 per day) 91 actions and 30
days to reach 54.6%. The cost is bounded per action by the (slip+fee) floor -- at most 1.3% of half the lot, $65
here, $28 measured -- and by depth per fill. What is not bounded by anything in the engine is the *flow*: 25% of
the raise (half of the treasury's half) is sold into the same V3 pool that just absorbed 100% of the raise as
buys, minutes after graduation and typically while arbs are still unwinding that push. This is round 3's M-2 in
reverse, applied to a quarter of the size, and it is disclosed nowhere: `docs/STRATEGY_ENGINE.md` does not say the
engine starts fully invested and liquidates to target at once.

**Fix** 0 bytes: state it, and extend M-2's listing rule to `(1 - target) x treasuryStock x price <= the USDG that
moves the stock's V3 pool by maxDeviationBps`. Or ~100 bytes: let the config carry an opening grace (no sells
until `cooldown x N` after `wire()`), or initialise `target` from the graduation composition and let the creator's
target take over at the first oracle move of more than the band. The floors in X-5 (target >= 20%) cap the worst
case at 80% of the lot.

### X-5 · Medium · The floors admit anything, and they are the creator's

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:119-141` (`_validateEngineConfig`: `deadbandBps == 0`,
`cooldown == 0`, `maxDailyTurnoverUsdg < maxTradeUsdg`, `maxTradeUsdg > p.sellChunkUsdg` are the whole list),
`src/v2/V2TreasuryDeployer.sol:303-319` (`setEngineConfig`: validates the policy key, not one word),
`src/v2/strategy/V2RebalancePolicy.sol:100-105` (accepts `deadbandBps == 0`).

**Status** EXECUTED (`test_X5_*`, `test_X9_*`).

**Mechanism.** A treasury with `targetBps 5000, deadbandBps 1, cooldown 1, maxTradeUsdg 2000, maxDailyTurnoverUsdg
2^256-1` deploys. After the sell-down, one +0.5% Chainlink print sells **$14.24** and the print that reverts it buys
**$12.42** -- 14 bps of a $9,980 treasury each, each paying the full 35-130 bps execution cost, at every print,
forever. The stock move that first crosses the band from target is `band / (target x (1 - target - band))`: at
target 50% that is **0.04% for 1 bp, 0.40% for 10 bps, 4.1% for 100 bps, 22% for 500 bps**. Any band under ~12 bps
acts on every print the feed makes. The worst-day bound is then `130 bps x maxTrade x prints/day` -- for a
volatile name 20-50 prints, so 50-130 x $2,000 x 1.3% = **$1,300-$3,400 a day on a treasury that need not be
larger than $10,000**, and no configured number stops it, because with `cooldown = 1` the day is only bounded by
the feed. A target of 1 bp is "sell 99.99% of the lot at graduation" and also deploys. The setter that binds the
config to the creator's salt checks none of this; `predict()` quotes a `maxTrade` one wei over the chunk that
`launch()` then refuses as an opaque `TreasuryDeployFailed` -- the same shape round 3 flagged for the factory's
own defaults.

**Grade.** Round 3's M-4: floors exist, they are far wider than any sensible value, and the choice is left to the
creator whose incentives are not the holders'. Recurring, bounded per action, unbounded per day by config -- Medium.

**Fix** In `_validateEngineConfig`, five comparisons (~80 bytes of 3,002): the floors in the table below. Mirror
them in `setEngineConfig` so a quote is never given for an unlaunchable config (the deployer has 13,839 bytes).

### X-6 · Low · No bounty

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:321-359` (no transfer to `msg.sender`); `HedgeFunTreasuryBase.sol:369-373,
396-399, 418-422` (kind 0 pays `bountyBps` on every action).

**Status** EXECUTED (`test_X6_executePaysNoBounty`): a stranger's stock, USDG and token balances are unchanged after
a successful `execute()`; `params().bountyBps == 50`.

**Impact.** Liveness rests on a keeper the creator runs at their own expense, and the one party with a reason to
call is the counterparty of the fill (X-1). No loss by itself; it is why X-1's "anyone chooses the moment" has
nobody on the other side of the race. Low.

**Fix** Pay `bountyBps` of the action's turnover in the output asset, sized from the actual fill as kind 0 does
(~120 bytes), or document that kind 2 ships with no keeper economics.

### X-7 · Medium · Strategy gains never reach the burn

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:335-337, 355-357` (proceeds stay inventory), `src/v2/HedgeFunV2Treasury.sol:170-174`
(`creditLiquidityFee`, the only writer of `buybackStock` reachable from kind 2), `docs/STRATEGY_ENGINE.md` (silent).

**Status** EXECUTED (`test_X7_rebalanceGainsNeverReachTheBurn`): sell-down at $100, buys at $80, sells at $100;
USDG reserve $4,988 -> $5,050 and 50.5 stock kept; `buybackStock == 0`, `totalBurned == 0`, `buyback()` reverts
`NotDue`. Modelled (`constant_mix.py`, table B): FUN burned by buy-backs **+0.19% of supply on every path** for
every engine config, the LP fee alone -- against kind 0's +2.20% at +3%/day, +1.27% at +1%/day, +0.49% flat at 4%
vol. In dollars over 90 days at +3%/day: kind 0 burned **$47,390** of stock, kind 2 **$5,419**.

**Impact.** The product's claim to holders is the burn; kind 0 routes the profit share of every take-profit to it.
Kind 2 routes nothing: gains accumulate as USDG in a treasury with no redemption and no claim. That is a coherent
design ("treasury growth") but it is a different product, and nothing a buyer reads says so. The rubric's
disclosure limb -- Medium. Loser: the buyer of a kind-2 token, relative to what the same documents lead them to
expect of a v2 token.

**Fix** Either say it, in `STRATEGY_ENGINE.md` and in the launch page's terms; or add a profit rule to the engine:
a high-water mark on total value at the oracle, and on each sell that lifts the reserve above it, credit a config
share of the excess (in stock, from inventory) to `buybackStock` (~250 bytes). The latter re-couples holders to
the strategy without lots or cost bases.

### X-8 · Info (safe) · Donations as triggers

**Status** EXECUTED (`test_X8_*`). Treasury at rest at target with $9,980; the stock that crosses a 5% band is
**$1,110** (`band x total / (1 - target - band)`); the engine then sells **$555**, of which a sandwich could return
at most 1.3% = **$7.21**. At a 1% band on a $20k treasury: $408 donated for a $204 sale. Irrevocable, an order of
magnitude underwater, and pointless besides: the donor who wanted the timing could have called `execute()` when it
was already due. `docs/STRATEGY_ENGINE.md:42-44` describes the observation correctly.

---

## Checked and found safe (with the line that makes it so)

- **The pool cannot make the treasury act.** `_context` prices inventory at `health()`'s `p`, which on an open day is
  `oracle.tryPrice()` (`PoolTrader.sol:105`); spot enters only as a gate. EXECUTED: a 51 bps push shuts, 49 opens,
  neither changes `preview()`'s action.
- **Rebalance and buy-back cannot double-spend.** `unbookedStock()` floors at 0 and excludes `buybackStock`
  (`HedgeFunTreasuryBase.sol:226-229`); `_executeSell` offers at most `bookedStock` (`:333`); `creditLiquidityFee`
  pulls under the guard (`HedgeFunV2Treasury.sol:170`). EXECUTED in X-7 and in the repository's own
  `test_donationBooksExactlyOnceWithoutTouchingBuybackBucket`.
- **Sell tax is inventory, never burn fuel.** It arrives as a bare balance from the hook's `_pay`
  (`HedgeFunHook.sol:645-656`) and is booked by `_bookInventory`. REASONED from the code; the model books it the
  same way.
- **Execution loss cannot ping-pong the band.** A sell to target loses at most 1.3% of `band x value`, which moves the
  share by under 1.3% of the band. REASONED.
- **A dust fill cannot advance the nonce or the cooldown.** `result.turnover < minLotUsdg` reverts before any state
  is written (`HedgeFunV2EngineTreasury.sol:271`). Read; the repository's accounting tests execute it.
- **M-0 is closed for v2 pools.** `HedgeFunV2Factory.sol:106` freezes `spikeBps = 0` at curve launch, so the
  LP-fee-armed `buyback()` that kind 2 inherits can no longer re-arm a sell spike. Read at this ref.
- **Corporate actions do not unbalance the ledger.** Raw balances never rebase (`uiMultiplier` is a UI view,
  `docs/STOCK_TOKEN_ASSESSMENT.md` row 8, fork-verified there) and the feed already carries the multiplier, so
  `bookedStock` and `stockValueUsdg` stay consistent across a split. REASONED from the project's own assessment;
  not re-verified on chain here.

## The model: kind 2 against kind 0 on the project's own paths

`constant_mix.py` runs `lab/trend.py`'s `run_post_graduation` unchanged for kind 0 (trend_holder: tp 30%/60%, dip
3%, no stop, lot 50%) and the same function with the engine's rule in place of the `Ledger` for kind 2 -- pool, tax,
LP-fee and buy-back flows identical line for line. Base launch as `docs/V2_TREND_SCENARIOS.md`: treasury 200 stock
($20,000 at $100), volume 20% of the raise per day, 90 days, hourly bars, 35 bps per swap, hourly keeper. Engines:
**E-50/5** target 50% band 5%, **E-50/1** band 1%, **E-80/5** target 80% band 5% (all `maxTrade` 2,000, no daily
cap, cooldown 60 s); **E-test** is the repository's test config (100 per action, 500 per day). "Gross" is
everything held plus everything spent on burns, in stock, over everything received -- the contract's own scorecard
omits what buy-backs spent, which is exactly where the two kinds differ, so both are shown.

### Multiple vs hold (scorecard / gross) and what $20,000 became, plus what was burned, 90 days

| path | stock | kind 0 | USD end + burned | E-50/5 | USD end + burned | E-50/1 | USD end + burned | E-80/5 | USD end + burned | E-test | USD end + burned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| +3%/day | 14.30x | 0.51 / 0.54 | $140,662 + $47,390 | 0.44 / 0.47 | $268,593 + $5,419 | 0.42 / 0.45 | $255,392 + $5,419 | 0.74 / 0.76 | $448,520 + $5,419 | 0.70 / 0.72 | $425,642 + $5,419 |
| +1%/day | 2.45x | 0.81 / 0.84 | $60,378 + $18,035 | 0.74 / 0.77 | $77,069 + $1,753 | 0.73 / 0.75 | $75,899 + $1,753 | 0.90 / 0.92 | $93,265 + $1,753 | 0.77 / 0.79 | $80,066 + $1,753 |
| +1%/day, 2% vol | 2.45x | 0.94 / 0.96 | $66,671 + $24,450 | 0.75 / 0.78 | $78,509 + $1,872 | 0.74 / 0.77 | $77,524 + $1,872 | 0.90 / 0.93 | $93,836 + $1,872 | 0.79 / 0.81 | $82,189 + $1,872 |
| flat, 2% vol | 1.00x | 1.00 / 1.03 | $42,555 + $1,153 | 1.02 / 1.05 | $43,402 + $1,153 | 1.02 / 1.04 | $43,343 + $1,153 | 1.01 / 1.03 | $42,803 + $1,153 | 1.02 / 1.05 | $43,463 + $1,153 |
| flat, 4% vol | 1.00x | 1.01 / 1.04 | $39,956 + $5,191 | 1.05 / 1.07 | $44,583 + $1,229 | 1.04 / 1.07 | $44,461 + $1,229 | 1.03 / 1.05 | $43,670 + $1,229 | 1.05 / 1.08 | $44,787 + $1,229 |
| -1%/day, 2% vol | 0.40x | 1.00 / 1.03 | $17,223 + $755 | 1.41 / 1.44 | $24,348 + $755 | 1.43 / 1.46 | $24,641 + $755 | 1.14 / 1.16 | $19,589 + $755 | 1.37 / 1.40 | $23,621 + $755 |
| -1%/day | 0.40x | 1.00 / 1.03 | $17,223 + $713 | 1.38 / 1.40 | $23,698 + $713 | 1.40 / 1.43 | $24,125 + $713 | 1.14 / 1.16 | $19,589 + $713 | 1.33 / 1.36 | $22,915 + $713 |
| -3%/day | 0.06x | 1.00 / 1.03 | $2,744 + $369 | 3.15 / 3.17 | $8,642 + $369 | 3.01 / 3.04 | $8,263 + $369 | 1.60 / 1.62 | $4,383 + $369 | 2.93 / 2.96 | $8,044 + $369 |

### Actions, turnover, execution cost and burns, 90 days

| path | kind | actions | turnover | execution cost | USDG reserve end | buy-back stock spent | FUN burned by buy-backs |
|---|---|---|---|---|---|---|---|
| +3%/day | kind 0 | 755 tp / 0 dip | - | - | $95,725 | 129.6 | +2.20% |
| | E-50/5 | 63 sell / 0 buy | $122,846 | $430 | $122,416 | 10.8 | +0.19% |
| | E-50/1 | 130 sell / 0 buy | $127,386 | $446 | $126,940 | 10.8 | +0.19% |
| | E-80/5 | 35 sell / 0 buy | $69,112 | $242 | $68,870 | 10.8 | +0.19% |
| +1%/day | kind 0 | 190 tp / 0 dip | - | - | $37,600 | 109.5 | +1.27% |
| | E-50/5 | 19 sell / 0 buy | $34,818 | $122 | $34,696 | 10.8 | +0.19% |
| | E-50/1 | 70 sell / 0 buy | $37,750 | $132 | $37,618 | 10.8 | +0.19% |
| | E-80/5 | 8 sell / 0 buy | $15,106 | $53 | $15,053 | 10.8 | +0.19% |
| flat, 4% vol | kind 0 | 25 tp / 21 dip | - | - | $5 | 41.0 | +0.49% |
| | E-50/5 | 13 sell / 0 buy | $23,017 | $81 | $22,936 | 10.8 | +0.19% |
| | E-50/1 | 61 sell / 23 buy | $40,937 | $143 | $22,324 | 10.8 | +0.19% |
| | E-80/5 | 5 sell / 0 buy | $9,219 | $32 | $9,187 | 10.8 | +0.19% |
| -1%/day | kind 0 | 0 tp / 0 dip | - | - | $0 | 10.8 | +0.19% |
| | E-50/5 | 6 sell / 0 buy | $11,109 | $39 | $11,070 | 10.8 | +0.19% |
| | E-50/1 | 14 sell / 0 buy | $11,997 | $42 | $11,955 | 10.8 | +0.19% |
| | E-80/5 | 2 sell / 0 buy | $4,000 | $14 | $3,986 | 10.8 | +0.19% |
| -3%/day | kind 0 | 0 tp / 0 dip | - | - | $0 | 10.8 | +0.19% |
| | E-50/5 | 5 sell / 8 buy | $15,305 | $54 | $4,639 | 10.8 | +0.19% |
| | E-50/1 | 5 sell / 43 buy | $15,737 | $55 | $4,207 | 10.8 | +0.19% |
| | E-80/5 | 2 sell / 6 buy | $6,944 | $24 | $1,042 | 10.8 | +0.19% |

(The full eight-path table, and a check that a keeper calling every cooldown instead of every hour changes no
multiple by more than 0.003, are in the script's output.)

### What the tables say, plainly

- **Does the rebalance kind solve "sells early and never re-enters on a rising stock"? No -- it does not have that
  problem because it has no path at all.** A constant mix holds a fixed fraction; it is never out, so "re-entry"
  is not a thing it does. It sells every rise and buys every fall by construction. On the rising paths it does
  *worse* than kind 0 in stock terms (gross 0.47 vs 0.54 at +3%/day, 0.77 vs 0.84 at +1%/day for E-50/5) because
  it carries 50% USDG the whole way up; it shows more treasury dollars only because it keeps what kind 0 burned
  ($268k against $141k + $47k burned). E-80/5 keeps most of the upside (0.76 / $449k) by giving up most of the
  downside cover (1.16 at -1%/day against E-50/5's 1.40).
- **On a range it earns what a constant mix earns: about sigma^2 / 8.** 90 days of 4% daily vol is 1.05-1.08 gross
  against kind 0's 1.04, from 13-84 actions costing $81-$143 (0.4-0.7% of the initial treasury). At 2% vol the
  band is barely crossed (1.04-1.05, mostly the tax inflow being sold). That is the whole edge, and it is paid for
  in the 35 bps per action that X-1 can turn into 85.
- **On a falling stock it buys all the way down.** 3.17 gross at -3%/day is three times better than holding in
  stock terms and still $8,642 from $20,000 in dollars. Kind 0 sat at 1.00 and $2,744. This is the one path where
  kind 2 is unambiguously the better rule for the treasury, and it is also the path where its holders get the
  same 0.19% burn as under kind 0.
- **The burn is decoupled on every path (X-7).** Every engine, every path: 10.8 stock spent, +0.19% of supply --
  the LP fee. Kind 0 spent 129.6 stock at +3%/day.
- **Most of the turnover is the tax.** At 20% volume the treasury receives ~225 stock of sell tax in 90 days, more
  than its 200-stock lot; the engine's "sells" on the flat and falling paths are mostly that inflow being
  converted to USDG to hold the target. Kind 0 booked it as lots and waited for +30%.
- **The daily cap is a strategy of its own.** E-test (500/day) ends at 0.72 / $426k at +3%/day because it could not
  sell fast enough to get out of the way -- a de facto holder for the first month. Nothing in the config surface
  distinguishes "a rebalancer" from "a holder with a slow leak".

## Recommended floors, and who enforces them today

| parameter | today | enforced by | recommended floor / ceiling | why that number |
|---|---|---|---|---|
| `deadbandBps` | >= 1 | constructor | **>= 100** | the first crossing needs a 4.1% move at target 50%; a single 0.5% print (the feed's own trigger) can never act alone (that needs >= 12) |
| `cooldown` | >= 1 s | constructor | **>= 600 s** (one TWAP window), 3,600 preferred | two actions never share one pinned 600 s mean; bounds a day at 24-144 actions without relying on `maxDaily` |
| `maxDailyTurnoverUsdg` | >= `maxTrade`, no ceiling | constructor | **<= 24 x `maxTradeUsdg`**, and halve it if X-2 stays | worst day 130 bps x 24 x chunk; with the 2,000 chunk, $624/day, $1,248 across midnight |
| `maxTradeUsdg` | <= `sellChunkUsdg` (2,000 / 1,000) | constructor, from the owner's per-listing chunk | **`sellChunkUsdg` <= 10% of the pool's USDG-per-1% depth on 0.05% listings**, re-read at listing | the sandwich breakeven (X-1); GME needs ~1,300 today, NVDA/GOOGL are fine at 2,000 |
| `targetBps` | 1..9999 | constructor | **2,000..9,000** | under 20% the engine is "liquidate the lot at graduation" (X-4); over 90% the band has no room |
| `setEngineConfig` | checks the policy key only | deployer | run the constructor's checks | `predict()` must not quote a config `launch()` refuses (X-5) |

All of these are creator-chosen today except the chunk. Every row is the M-4 pattern: a floor that exists, is wide
enough to be no floor, and is left to the party who does not bear the loss.

## What this lane did not cover

- **A real multi-tick V3 pool.** The venue is one in-range step of constant liquidity computed by Uniswap's own
  `SwapMath`; a concentrated pool with thin ticks near the price makes fills shorter and pushes cheaper than
  modelled. Round 3's fork depth reads (M-2, `poc/fork/Depth.t.sol`) were not re-run; every "USDG per 1%" here is
  a parameter, and the live ones are a day old and moving.
- **Arb behaviour between actions** is modelled as an instant refill to the oracle price and an unmoved 600 s
  mean. A multi-block pin at -49 bps (holding the pool there across several cooldowns) was reasoned, not executed:
  it amortises the push but does not change the sign of the attacker's P&L, which is set by `maxDeviationBps`
  against `2 x poolFeeBps`.
- **Gas and ordering.** Attacker P&L is gross of gas. Robinhood Chain's sequencer gives no public mempool; the
  sandwich here is atomic in one transaction and needs no ordering privilege, which is why it is not discounted.
- **The fork suites, the registry's governance, the options reservation, the hook and vault beyond
  `buybackStock`, and the ABI/front-end surface.** Other lanes.
- **Kind 0's numbers are the project's own** (`run_post_graduation` unchanged); its documented biases
  (bar-close evaluation, `tp2 = 2 x tp1`, one bar per lot exit) apply to the kind 0 column, and the engine model
  shares the ones about bars and volume.
