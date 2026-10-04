> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Verification — what was done to the findings after they were written

Part of [external audit round 1](./00-SCOPE.md). Companion to [`ISSUES.md`](./ISSUES.md).

Two independent reviews ran after triage merged the eight sources, each by an agent that had done none of
the earlier work:

1. **An adversarial pass** whose standing instruction was that *every finding is a false positive until it
   produces an irrefutable code path*, and which was explicitly told to attack the "checked and found safe"
   section and the rejected list as well as the findings. It worked at a checkout path deliberately unlike
   any other, which is how it reproduced the path-dependence finding at a sixth location.
2. **A third-party review of this report's rubric, framing and method**, given the baseline, the scope
   statement, the method write-up and the merged finding list — and **deliberately not given the source
   code**. It is the only layer that can catch a bias built into the method rather than into a finding.

Both are reproduced below in full, unedited. Their criticisms have been folded into `ISSUES.md`,
`00-SCOPE.md` and the round's [`README.md`](./README.md); reading them here shows what was changed and why.

**The headline from each:**

- The adversarial pass returned **0 false positives, 0 overturned safe-list entries and 0 overturned
  rejections**, downgraded **two of the four Highs**, broke one proposed fix, cut another finding's impact
  numbers, and — most consequentially — showed that **the lead's own headline argument for the report's
  most-cited finding was not valid arithmetic**, then supplied the correct version. It also measured what
  triage had left as an instruction: the full set of factory-side fixes **overflows EIP-170 by 160 bytes**.
- The method review's first criticism is that **"0 Critical" is close to a tautology of this
  architecture** rather than a result, and its last is that the report never stated what would have made it
  say "do not launch". Both are now addressed at the top of `ISSUES.md`. It also identified six measurements
  the report called decisive and had not taken; all six were subsequently taken and are in `ISSUES.md`'s
  urgency section.

---

# Part 1 — the adversarial pass

# Lane 09 — adversarial pass: falsifying lane 07's finding list

External audit round 1, 2026-09-21. Target `keyuyuan/hedgefund` @ `9a291aa`
(`git rev-parse HEAD` == `9a291aaff0c290b69b91c84566e77ee8ace1216e`, verified by me; the target tree was
**never modified** — the only entry in `git status` is the untracked `audit/` directory, which predates me).

My stance: every finding is a false positive until it produces an irrefutable code path. I ran none of the
eight lanes and did not do the triage. Everything below is either something I executed myself or a
re-derivation from the source at `9a291aa`.

**Where I worked.** All building and running in
`…/scratchpad/adv-scratch/zq-adversarial-checkout-number-five-xyzzy` (`src`, `test`, `script`, `data`,
`foundry.toml` copied; `lib` symlinked) — a path deliberately unlike any lane's, for F-14. Chain reads via
`cast` against `https://rpc.mainnet.chain.robinhood.com`, block **68,673,871** unless stated.
forge 1.8.1, solc 0.8.26, `optimizer_runs = 1`, `evm_version = cancun`.

---

# 0. Headline

| | count |
|---|---|
| CONFIRMED as graded | 9 |
| CONFIRMED, one or more stated reasons wrong | 4 |
| CONCLUSION SURVIVES BUT REASONING DOES NOT | 3 |
| DOWNGRADE | 2 (**F-01** High→Medium, **F-02** High→Medium) |
| UPGRADE | 0 |
| FALSE POSITIVE | 0 findings; **1 proposed fix is broken** (F-17) |
| §6 "safe" items overturned | 0; 2 precision defects recorded |
| §7 rejections overturned | 0; 1 inconsistency recorded (R-4 vs F-02) |
| triage disagreements resolved by measurement | §5.12 (nobody had measured it), §2c, §5.3 |

Three things I did that no lane did, all EXECUTED:

1. **An independent exact V3 tick-walk of the NVDA pool from raw `tickBitmap` + `ticks()` reads**, which
   reproduces lane 08 to 0.1 percentage points — and shows the *bound argument* F-01 leads with is not a
   valid bound.
2. **A model-free falsification of every row of the D30 table from a file committed in the repo**
   (`data/listability.json`): each `AUDIT.md` D30 figure exceeds its pool's **entire TVL**, both sides
   combined. No chain read and no tick math are needed to see the table is wrong.
3. **I measured the factory byte budget for the whole proposed fix set** — §5.12, which triage explicitly
   left UNMEASURED and turned into an instruction. The answer is that the set **does not fit**.

---

# 1. Findings examined, one by one

---

## F-01 · manipulation-cost table 8–25× too high
### Verdict: **CONFIRMED as a measurement — DOWNGRADE High → Medium — and two of its stated reasons are wrong.** Status: EXECUTED.

**What I did.** I did not take lane 08's tick-walk, the coordinator's `balanceOf` check or triage's
reproduction on trust. I rebuilt the measurement from scratch, three ways.

*(a) Raw pool state, block 68,673,871.*

```
pool   0xd4EB21209C4D6093f80B5b84f5C45cc093EA14a3   fee 500   tickSpacing 10
token0 0x5fc5360D…1d168 USDG (6)     balanceOf(pool) = 4,001,399.457987
token1 0xd0601CE1…D9EEC NVDA (18)    balanceOf(pool) =     9,294.012607759580880957
slot0 tick = 222191  -> 224.3107 USDG/NVDA      liquidity() = 12,083,265,098,703,481,114
NVDA side = $2,084,746      USDG side = $4,001,399
```

*(b) My own exact tick-walk.* I read `tickBitmap(int16)` words 84–88, expanded the set bits at
`tickSpacing = 10`, and read `liquidityNet` for all 183 initialized ticks in the downward window through
Multicall3 (`0xcA11bde05977b3631167028862bE2a173976CA11`, batched, pinned to block 68,673,871), then walked
the V3 curve tick by tick with the fee grossed up:

| move | USDG in (exact walk) | NVDA out | share of the pool's NVDA side |
|---|---|---|---|
| +0.5% | **$363,986** | 1,618.0 | 17.4% |
| +1.0% | **$701,637** | 3,111.3 | 33.5% |
| +1.3% | **$904,371** | 4,004.4 | 43.1% |
| **+30%** | **$2,118,250** | 9,168.4 | **98.6%** |

Lane 08's exact figure was **$2.33M** at block 68,632,038 and "converges on 98.7% of the stock side".
I get **$2.12M** and **98.6%** at a block ~42k later. **Lane 08 reproduces.** `AUDIT.md`'s **$54M** is
**25.5×** the exact figure at my block. The other direction (walking NVDA *down* 30%) takes 18,434.78 NVDA
in ($4.14M of notional) and returns $3.98M of USDG — 99.4% of the USDG side. Either direction, $54M is
unreachable.

*(c) The model-free check, which is the part no lane got right and which I extend to every row.*
`data/listability.json` — **committed in the repo at `9a291aa`** — carries each pool's TVL. Against
`AUDIT.md`'s own D30 column:

| ticker | pool TVL, **both sides**, from the repo's own file | `AUDIT.md` D30 | D30 ÷ whole pool |
|---|---|---|---|
| NVDA | $6.20M | $54M | **8.7×** |
| AAPL | $0.593M | $5.9M | **9.9×** |
| GOOGL | $1.27M | $3.9M | **3.1×** |
| SPCX | $2.56M | $13M | **5.1×** |
| SPY | $0.434M | $3.2M | **7.4×** |
| META | $0.219M | $595k | **2.7×** |
| AMD | $0.264M | $309k | **1.2×** |

**Every single D30 figure in `AUDIT.md` exceeds the entire pool it describes.** A reviewer could have
caught this without an RPC call.

I also confirmed the stock-side halves live (block 68,673,871), which is the number that actually bounds
the walk, and computed the correct trivial bound `1.3 × stock-side value`:

| ticker | stock-side value | valid bound on D30 (1.3×) | lane 08's exact | `AUDIT.md` |
|---|---|---|---|---|
| NVDA | $2.085M | $2.71M | $2.33M | $54M |
| AAPL | $231k | $300k | $235k | $5.9M |
| GOOGL | $416k | $541k | $468k | $3.9M |
| SPY | $186k | $241k | $201k | $3.2M |
| SPCX | $703k | $914k | $760k | $13M |

**Every one of lane 08's exact figures falls inside the bound I derived independently.** The measurement
is right and I would stake my name on it.

### What is wrong

**1. The bound argument F-01 leads with is not a bound.** F-01 says: *"you cannot buy more NVDA than the
pool holds. The **entire** NVDA side is worth ~$2.19M… No model is needed — two balances and one
multiplication."* That conflates the **value of the stock taken out** with the **USDG paid in**. Walking a
pool up, you pay rising prices, so the USDG in exceeds the spot value of the stock out. My exact walk
demonstrates it directly: **$2,118,250 paid in against a stock side worth $2,084,746** — the "bound"
is exceeded by 1.6% by the very quantity it claims to bound. The correct model-free bound is
`P(+30%) × stock inventory` = `1.3 × spot value`. The conclusion is untouched ($54M ≫ $2.71M); the
sentence that carries it is not correct arithmetic and should not be published as "no model is needed".

**2. F-01 omits the disclaimer printed directly above the table it is attacking.** F-01's Location cites
`AUDIT.md:80-84`. `AUDIT.md:83-86` reads:

> *"**Cost to move a listed pool.** USDG to push spot +30% using the pool's current **active-tick
> liquidity** (assumes it extends across the move; **concentrated pools thin out away from price, so real
> cost is likely lower**)."*

The repository states the model, states the assumption, and states the **direction** of the error. So the
finding is not "the project's own risk model is wrong … in the unsafe direction" as F-01's Mechanism puts
it; it is "the project knew the number was an overestimate, never bounded how big the overestimate was, and
then used it as a **hard $500k threshold** and as the justifying comment for a permanent constant". That is
still a serious finding — an 8–25× unbounded overestimate used as a gate is not a disclosed risk in any
useful sense, and `StrategyFactory.sol:265-268` repeats the raw number with no hedge at all — but F-01 as
written accuses the repo of an error it partly documents, and the accusation is built on a citation range
that stops one line short of the disclaimer. Quoting the caption would make the finding stronger and
harder to dismiss, not weaker.

### Why Medium, against triage's High

The rubric's High tier has exactly three doors: (i) an unprivileged actor permanently takes or destroys
funds under favourable conditions, (ii) long-window TWAP manipulation, (iii) the Safe does something
`docs/SECURITY.md` explicitly promises it cannot. F-01's own Impact section says **"No attacker. Certain
gain: 0. Option gain: 0."** and its Mechanism says **"Not a code path."** None of the three doors is open.
Medium's clause — *"a disclosed risk whose disclosure materially understates it"* — describes it exactly,
by 8–25×. Triage concedes the point in its own grading note (*"A reader who insists severity must track an
attacker's gain will read this as Medium"*) and then grades High anyway on the ground that three permanent
decisions rest on it. That is an argument about **urgency**, and the urgency table already ranks it #1.
**Grade Medium; keep urgency rank 1.** The risk of leaving it at High is precisely the one the rubric's
rule 7 warns about: a High with no attacker and no code path devalues the Highs that have both.

### What else I checked and it held

- TR-1's break-even `6.7 × poolFee × D30` recomputes: `6.7 × 0.0005 × 54e6 = $180,900` (AUDIT's premise)
  and `6.7 × 0.0005 × 2.12e6 = $7,102` on the exact walk. F-01's $181k → $7.8k reproduces (it used
  $2.33M). **Arithmetic self-consistent.**
- `setBandCeiling`'s justifying comment at `StrategyFactory.sol:265-268` says verbatim *"NVDA takes $54M to
  walk 30%, AMD $309k"*. Cited correctly.
- `LISTING_CANDIDATES.md`'s ~$500k cutoff against AAPL: AAPL's whole pool is $576–593k and its stock side
  is $231k. AAPL falls outside its own project's cutoff on any honest measurement. **Confirmed.**

---

## F-02 · `setOverride(day, 2)` changes the price the rule trades at
### Verdict: **CONCLUSION SURVIVES BUT ITS REASONING DOES NOT — DOWNGRADE High → Medium.** Status: EXECUTED (source re-read) + REASONED.

Triage graded this **High against three lanes** that said Medium or Info. It is the judgement call the
prompt singles out, and I think triage got it wrong on four separate grounds.

**What is true.** `TradingCalendar.sol:130-135` — I read it — returns `false` from `dateClosed` on mode 2;
`PriceOracle.tryPrice` (`:51`) is the single calendar gate on every trading path and asks `isClosed`.
So `setOverride(saturday, 2)` flips `tryPrice` from refusing to serving Friday's frozen close, provided it
is inside `maxStockAge ≤ 48 h` (`PriceOracle.sol:42`). The header at **`TradingCalendar.sol:14-16`** —
*"an override can only ever stop trading, **never widen what trades**: see `isScheduledClosure`"* — is
**false as written**, because mode 2 strictly adds tradeable states through `isClosed`. That sentence is a
genuine, unqualified, in-source falsehood and it is the real core of this finding. I confirm it.

### Wrong 1 — the second "contradictory claim" is a truncated quotation

F-02 cites `TradingCalendar.sol:137-142` as *"the second, contradictory claim: 'The owner can stop the rule
trading, and cannot change what price it trades at'"*. Here is the full paragraph, which is the docstring
of `dateClosedByRule`:

> *"This is what bounds the owner. An override may HALT … **but a consumer that does something MORE on a
> closure, as the V3 treasury does when it falls back to the pool's own mean inside a 30% band, asks this
> instead. So forcing a live trading day "closed" parks the rule; it cannot swap the 0.5% gate for the 30%
> one.** The owner can stop the rule trading, and cannot change what price it trades at."*

The quoted sentence is the **conclusion of a paragraph whose entire subject is the 0.5% gate versus the 30%
band**. In that scope it is **true**, and I verified the code: `isScheduledClosure` (`:157-160`) is
`override_[day] == 0 && dateClosedByRule(day)`, so mode 2 **turns the band path off**. This is exactly the
failure mode the prompt names — an accusation built on half a sentence.

### Wrong 2 — the "re-enables `_book` and `stopLoss`" half is backwards, and inert today

F-02's Mechanism says mode 2 makes `pricedOffPoolOnly()` false, so *"the two calls the band machinery
exists to keep off a pool-only price — `_book` and `stopLoss` — are re-enabled during a closure."* Two
problems:

- **Inert.** `StrategyTreasury._priced()` (`:96-97`) is
  `(ok0,p0) = _health(maxDeviationBps); if (ok0 || params.bandBpsPerHour == 0) return (ok0, p0, false);`.
  With `bandBpsPerHour == 0` — the shipped state for every stock, which triage's own §6 calls "the single
  most important safety property in the rule" — `pricedOffPoolOnly()` is **already always false**. `_book`
  and `stopLoss` were never gated by it. Mode 2 changes nothing on this path today.
- **Backwards where it is not inert.** If a ceiling were raised, mode 2 makes `_feed()` refuse
  (`:129-131`), which disables the band entirely, so the price served is **Chainlink's**, corroborated by
  both spot and the 600 s mean inside `maxDeviationBps`. That is precisely what `pricedOffPoolOnly` exists
  to guarantee. Mode 2 re-enables `_book` and `stopLoss` **onto a Chainlink-signed price**. The finding
  presents a safety property as a hazard.

### Wrong 3 — `docs/SECURITY.md` grants this power explicitly, one cell away

F-02's High rests on the rubric's third clause: *the Safe can do something `docs/SECURITY.md` **explicitly
promises it cannot***. The table's very next row (`docs/SECURITY.md:33`, "It can" column) reads:

> *"force a day **open** (`setOverride(day, 2)`) — the live-feed path then applies, behind the 48 h age cap
> and the deviation gate"*

That is an exact, complete and correct statement of the mechanism, including both of its gates. And the
heading at `:169` (*"The calendar owner can halt and only halt"*) is scoped by its own two-sentence body:
*"The closed-market path asks `isScheduledClosure` … An override can therefore neither open that path on a
live day nor leave it running on a weekend"* — a claim I verified in code and which is **true**. The
"cannot" cell at `:32` — *"change the price the rule trades at, or open the closed-market path"* — is
written in the document's own terminology, where "the closed-market path" is a defined term meaning the
band. Read with the document's own vocabulary, both halves of that cell are true.

So the repository states this capability accurately in **three** places (`TradingCalendar.sol:155-156`
— *"`setOverride(day, 2)` hands the day to the live-feed path and its ordinary gates"*;
`docs/SECURITY.md:33`; and `AUDIT.md`'s blocker 5 row) and misstates it in **one**
(`TradingCalendar.sol:14-16`). Triage cites the one and treats the three as "a mitigating fact that belongs
in the writeup, not in the grade". I disagree: the rubric's word is **"explicitly promises"**, and a
document that explicitly grants the power in the adjacent cell is not explicitly promising the opposite.
C-01's stated flip test — *"if `SECURITY.md` repeats the line at `TradingCalendar.sol:15-16`"* — is not
met: `SECURITY.md` does **not** repeat that line; it says the opposite of it at `:33`.

### Wrong 4 — triage rejected the strictly larger version of the same mechanism

The mechanism F-02 describes is "the treasury trades on a frozen Chainlink print inside the deviation
gate". **That happens every weeknight with no Safe action at all** — the 24/5 calendar calls a Wednesday
03:00 ET "open", and `tryPrice` will serve a print up to 48 h old. That is HX-1, which triage **rejected**
as a value finding (§7 R-4) and re-graded to Low (§5.1). Grading the version that needs a 2-of-4 Safe
transaction at **High** while rejecting the version that needs nothing is internally inconsistent.

What genuinely distinguishes the weekend case is that the feed's 0.5% deviation trigger is not running, so
the frozen print's error is not bounded by it. But the deviation gate still requires the pool's spot **and**
its 600 s mean to agree with the frozen print inside 50 bps — and `AUDIT.md:97-100` records that Lighter's
equity perps trade 24/7 with real weekend volume (Sunday 2026-09-20: SPY $60M, NVDA $2.7M). A pool
arbitraged toward the true weekend price fails `health()` closed. For the treasury actually to trade badly
on a forced-open Saturday, someone must **hold** the pool at Friday's close against that flow — which is
U-8, explicitly UNMEASURED.

### Where that leaves it

A real, permanent, in-source false statement (`TradingCalendar.sol:14-16`) about an owner power that is a
one-transaction lever with no timelock, no expiry and no day limit, on the one contract every launched
strategy reads live. Loser: the treasury. Certain gain to any actor: **0** (F-02 says so itself).
**Medium, under the disclosure clause**, which is where three of the four source lanes put it. Both of
F-02's proposed fixes are sound and cheap; I verified `TradingCalendar` has 19,784 B of margin.

---

## F-03 · `MAX_BAND_BPS_PER_HOUR = 200` is 20× the measured useful value
### Verdict: **CONFIRMED.** Status: REASONED (I verified the constants and the gating), inheriting F-01's EXECUTED depth side.

Unlike F-01, this one has an actor with a **certain** gain (the pinner banks the spread on the fill), needs
a ≥600 s TWAP hold, and is therefore squarely inside the rubric's High band and its TWAP cap. I verified:
`StrategyTreasuryBase.sol:103` `MAX_BAND_BPS_PER_HOUR = 200`; `StrategyFactory.sol:270` `if (bps > 200)
revert`; `:364` forces 0 on V4; `StrategyTreasury.sol:35` and `StrategyTreasuryV4.sol:66` re-check.
`bandCeiling` is a default-zero mapping, so both gating conditions are genuinely unmet today.

One note the finding should carry: it inherits F-01's depth correction, and **F-01's correction makes F-03
worse** (TR-1's break-even on NVDA falls from ~$181k to ~$7.1k on my walk). That direction is stated. The
fix (`MAX_BAND_BPS_PER_HOUR = 10`, a changed literal) genuinely costs no bytes — I confirmed the treasury
constant lives in `StrategyTreasuryBase` and a literal swap does not move `TreasuryDeployer`.

---

## F-04 · a dead oracle freezes the treasury forever
### Verdict: **CONFIRMED, and the outflow enumeration is complete — but one of its four causes is not permanent and its proposed fix does not do what its headline claims.** Status: EXECUTED (the enumeration).

**The enumeration, which the prompt asked me to test.** I grepped both treasuries and `PoolTrader` for
every construct that can move value out (`safeTransfer`, `.transfer(`, `approve`, `.take(`, `burn(`,
`call{`). The complete set is:

```
StrategyTreasuryBase :285 stock bounty (takeProfit)   :305 usdg bounty (stopLoss)
                     :327 usdg bounty (buyDip)        :386 token bounty (buyback)
                     :388 burn (its own token)        :422 settle to poolManager (buyback)
                     :424 take -> INTO the treasury
StrategyTreasuryV4   :140 settle to poolManager       :142 take -> INTO the treasury
PoolTrader           :161-162 the V3 swap callback
StrategyTreasury     (none)
```

There is **no `approve` anywhere in either treasury**, no owner, no rescue, no proxy. Every one of those
sites is reached only from `book` / `takeProfit` / `stopLoss` / `buyDip` / `buyback`, and the first four all
open with `health()` (`:249`, `:261`, `:291`, `:309`). `buyback` is the only exception and reverts
`Unhealthy` once `lastGoodPrice` is over `MAX_SIZING_AGE = 5 days` (`:364-369`). `lastGoodPrice` is written
only by `_notePrice`, called only from `:255`, `:275`, `:297`, `:314` — all four inside the gated
functions. **F-04's enumeration is complete and its mechanism is exactly as stated.** This is one of the
two findings in the report I would stake my name on without qualification.

### Two corrections

**1. Condition 1(d) is not permanent.** F-04 lists *"the calendar owner sets `setOverride(day, 1)`
indefinitely and then calls `renounceOwnership`"* as a fourth independent cause. `setOverride` takes **one
day per call** (`TradingCalendar.sol:29`). Halting "indefinitely" needs one transaction per trading day
forever; ten thousand calls buys 27 years, not permanence. Cause (d) is a bounded-duration halt, not a
permanent freeze, and should be struck or restated. Causes (a) — a stuck `oraclePaused()`, which
`docs/SECURITY.md:60` says "recovers fully when lifted" and so is a *liveness* risk of a trusted third
party — and (c) are also reversible or contingent. **The load-bearing cause is (b): Chainlink retires the
equity feed.** That one is genuinely permanent and unrecoverable, and the finding should lead with it
rather than with a list of four in which only one holds up.

**2. The proposed fix rescues a minority of the assets the headline claims are lost.** The headline is
*"permanently loses **every asset** it holds"*, and the magnitude is stated as *"100% of `bookedStock +
buybackStock + reserveUsdg`"*. That is right. But the fix — denominate the chunk in stock so `buyback`
needs no stock oracle — rescues **only `buybackStock`**. `bookedStock` (the lots) and `reserveUsdg` remain
frozen forever, because `takeProfit`, `stopLoss` and `buyDip` all still open with `health()`. F-04 does say
the burn path "is the path that matters most to holders", which is fair, but the fix section should state
plainly that it addresses one of three buckets, and that the escape hatch it calls "a second, larger fix"
is the only thing that addresses the other two.

Grade: **High stands.** There is no actor and the rubric is written around one, but "destroys" is the
operative verb in both top tiers, the loss is total, permanent and unrecoverable, and Medium's ceiling ("a
permanent brick of **one non-essential** path") plainly does not cover it.

---

## F-05 · `_setDefaults` under-bounds eight fields
### Verdict: **CONFIRMED.** Status: EXECUTED (I re-read the block and measured the fix).

`_setDefaults` at `StrategyFactory.sol:252-263` — I read every line. The checks are exactly the fourteen
F-05 lists, and `spikeSeconds`, `buybackCooldown` and the eight other fields are unchecked as described.
`StrategyHook`'s constructor check at `:126` likewise omits `spikeSeconds`. `protocolBps = 10000` with
`maxCreatorBps = 0` passes both `:253` (`> 1e4`, strict) and `:126` (same). Confirmed.

I measured the fix — see §3 below. It costs **275 bytes**, which settles §5.12 in CL-1's favour.

---

## F-06 · `maxBuybackImpactBps < 20` bricks `buyback()`
### Verdict: **CONFIRMED for the value 1 — but §5.7's "CL-2 has the right number" is not a derived result, and the fix's "no net bytecode growth" claim is false.** Status: REASONED, from the exact integer path.

I walked `_buybackLimitSqrtP` / `_clampToSpot` by hand at `9a291aa`:

- `half = maxBuybackImpactBps / 2`. At **1**, `half == 0`, so `fromSpot == sqrtP` exactly and `fromMean` is
  unadjusted. `bound = max(fromMean, fromSpot) >= sqrtP` for `zeroForOne`, so `_clampToSpot` returns
  `sqrtP - 1`; symmetrically `sqrtP + 1` otherwise. A one-wei sqrt limit fills `L / Q96` ≈ **1.3e-10 units**
  at the launch pool's scale — dust — and `:380` turns it into `NotDue`. **Certain, permanent brick.
  Confirmed.**
- At **2 or 3**, `half == 1`: a 1 bp *sqrt* limit ≈ 2 bps of price. This is **not** a brick. It is a price
  limit that allows a real, but small, partial fill whose size is a function of the pool's in-range
  liquidity and the chunk — and `:380` then rejects it only if it lands under
  `min(amountIn, _ruleStockFor(minLotUsdg, p))`. Whether that happens depends entirely on the launch
  pool's depth against `buybackChunkUsdg`.

So CL-2's "effective floor ~20" is a **judgement about a typical pool**, not a property of the code, and
§5.7's *"CL-2 is right and the other two are wrong about the threshold"* presents an estimate as a derived
fact. The defensible statement is: **1 is a certain brick; 2–19 is a degradation of unmeasured size.**
Label the 20 UNMEASURED.

**The fix claim is wrong.** F-06 says replacing `d.maxBuybackImpactBps == 0` with `< 20` gives *"no net
bytecode growth, so the 945 B margin is untouched"*. `== 0` compiles to `ISZERO`; `< 20` needs a
`PUSH1 0x14` and an `LT`. It is a small positive cost, not zero. The alternative F-06 offers
(`mulDiv(sqrtP, 2e4 ± maxBuybackImpactBps, 2e4)` at `:457`/`:467`) is correct and does remove the
truncation-to-zero — that is the fix to take.

Grade Medium against three lanes' Low: **I agree with triage.** `StrategyToken.sol:7-8` is explicit that a
shrinking supply is the only link between treasury and token, so `buyback()` is the essential path and
Medium's "non-essential" qualifier excludes Low.

---

## F-07 · the sell spike is absent for half of every cycle
### Verdict: **CONCLUSION SURVIVES BUT ITS REASONING DOES NOT.** Status: REASONED (the pricing), source verified.

The mechanism is real and I confirmed it at source: `StrategyHook.sol:147` is
`if (block.timestamp < lastEventAt + 2 * spikeSeconds) return;` and `:164` returns `taxBps` once
`dt >= spikeSeconds`. The window `[T + spikeSeconds, T + 2·spikeSeconds)` is flat-rate **and** cannot be
re-armed. The 50% figure is parameter-independent. Confirmed.

The prompt asked me to price the **consequence**. Two of F-07's three claimed uses do not survive pricing.

**1. The "one-transaction sandwich" is not profitable, and F-07 measures why three paragraphs earlier.**
F-07 says that inside the unprotected half *"the buy-back sandwich collapses into one transaction: buy,
call `buyback()`, sell, paying only the flat tax on both legs with no price risk between them."* Paying the
flat tax on both legs **is** the cost: at the shipped `taxBps = 1000` a round trip through the hook costs
`1 − 0.9 × 0.9 = 18.99%` of the position — the exact number L-14 measured and F-07 quotes in its own "what
is actually protecting the buy-back" paragraph. Against that, the take is the buy-back's own price impact,
bounded by `maxBuybackImpactBps` (shipped 300 bps) of `buybackChunkUsdg` (shipped 500e6): **≤ $15**. To
capture $15 the attacker must round-trip a position; 19% of any position large enough to capture it is
several times $15. **The sandwich never pays at any parameter the factory permits.** F-07 states this for
the *spiked* case and then asserts the opposite for the unspiked case without re-running the arithmetic.

**2. The "$1,000 rather than up to $9,000" figure is not a gain.** F-07 adds *"on the exit side, the
difference between paying `taxBps` and paying up to `spikeBps`: on a $10,000 exit at `taxBps = 1000`,
$1,000 rather than up to $9,000."* The **default** state of the hook, absent a recent buy-back, is
`taxBps`. Any seller pays $1,000 by simply not selling inside a live spike. The $8,000 is avoided damage
from a grief that requires someone else to spend a buy-back immediately ahead of them — a real attack
(front-run a large sell with `buyback()` to impose the 90% rate), but the "$9,000" is that attacker's
weapon, not this seller's foregone gain. Putting it in the gain column inflates the finding by ~500×.

**3. What survives, and it is the finding.** F-07's own third framing is correct and is the only one that
prices out: a holder who was going to sell anyway has **zero marginal cost** to time their sale into
`[lastEventAt + spikeSeconds, lastEventAt + 2·spikeSeconds)`, call `buyback()` there (which does not
re-arm), and sell into the buy-back's own impact. Their certain take is the impact on what they sell —
order **$13–16 per buy-back at the shipped defaults** (≤$15 of impact, taxed at 10%, plus `bountyBps = 50`
of the burn ≈ $2.50) — recurring once per cooldown for as long as `buybackStock` lasts. Small, certain,
permanent.

**Keep Medium**, under the disclosure clause exactly as triage argues (`README.md:45`,
`docs/SECURITY.md:219-220` and `StrategyHook.sol:43,46` all present the spike as an anti-dump defence and
half the time, at the seller's election, it is not one). But the Impact section's numbers should be cut to
the third case. F-07's honest-minimum recommendation — stop describing the spike as an anti-dump mechanism
— is right and survives all of the above.

---

## F-08 · no treasury `_reconcile`
### Verdict: **CONFIRMED.** Status: REASONED.

`unbookedStock()` at `:195-197` is `return b > held ? b - held : 0;` with `held = bookedStock +
buybackStock`; `stockEquivalentHeld()` at `:205-209` returns `bookedStock + buybackStock +
_ruleStockFor(reserveUsdg(), p)` — the **ledger**, never the balance. `StrategyHook._reconcile` at
`:343-351` exists for exactly this event one contract over. Mechanism and asymmetry both confirmed as
stated. Budget: `TreasuryDeployer`'s 2,158 B, which I verified independently (§3).

---

## F-09 · `book()` is unpaid, unbounded in time and size
### Verdict: **CONFIRMED.** Status: REASONED; the depth re-basing is now EXECUTED via my own walk.

`_book` at `:246-258` contains no bounty transfer — I read it. `uint256 un = unbookedStock()` becomes
**one** `Lot` at `:254`. `takeProfit` sells `principal = mulDiv(q, cost, p)` in one swap with
`requireFull = true` (`StrategyTreasury.sol:137` pins `requireFull = !buy`; `PoolTrader.sol:137` reverts
`PartialFill`), and there is no smaller-slice path — `q` is either `L.qty` or `L.qty / 2` and `L.half`
allows the halving exactly once. Confirmed.

The re-based threshold table is now supported by my own measurement rather than a ratio: on NVDA the exact
walk gives $364k to move +0.5% and $702k to move +1.0%, so a lot whose principal is a meaningful fraction
of those cannot fill inside `maxSlippageBps = 100`. F-09's "~$43–83k" for NVDA is the right order of
magnitude and its UNMEASURED label on the ±1% scaling is the correct caveat — I did not run the
`requireFull` simulation against a real lot, and neither did any lane.

---

## F-10 · `lastSalePrice` is one global scalar
### Verdict: **CONFIRMED.** Status: REASONED.

One `uint256` at `:122`, written at `:283` (`takeProfit`), `:303` (`stopLoss`) and `:325` (`buyDip`), read
only at `:311`. The worked table is arithmetic and reproduces. Nothing to correct.

---

## F-11 · the front page's performance figure vs the backtest
### Verdict: **CONCLUSION SURVIVES; the headline's strongest phrase does not.** Status: EXECUTED (I read both documents in full and recomputed from the committed CSVs).

I read `README.md` end to end and `docs/rule-backtest/README.md` end to end, as instructed, rather than the
excerpts.

**The checkable fact holds.** `grep -n "backtest" README.md` returns exactly two hits: `:287`
(`tools/band_backtest.py`, a different tool) and nothing for `rule-backtest`. The only pointer to the
multi-year replay anywhere on the front page is absent; it exists at `docs/README.md:45`. Confirmed.

**E-2's recomputations reproduce exactly.** From `docs/rule-backtest/all-stocks.csv` over the 25
`listable == True` rows: median `d55_up` = **0.8872**, **3 of 25** above 1.0, median `d55_burn` =
**0.3057**; NVDA / AAPL / GOOGL `d55_burn` = **0.3641 / 0.2932 / 0.2664**. From `deep-pools.csv`,
**0 of 252** rows clear 1.0 on `min`, `d_all` and `h_fwd` simultaneously (max `d_all` 0.9317, max `h_fwd`
0.9879). Every figure triage quotes is right to the digit.

### What is wrong

**1. "A hand-built favourable unit test" is contradicted by the README's own sentence.** `README.md:316-317`
reads: *"Measured on a **sell-high-rebuy-lower round trip in the unit suite**: 1.0278."* The front page
names the scenario and names the source. A reader is told, in the sentence carrying the number, that it is
the single most favourable path a mean-reverting rule can be handed, measured in a unit test. That is not
concealment and it is not presented as expected performance. The finding should say what it actually is:
the front page defines 1.0 as neutral, quotes one number above it, and never points at the repository's own
multi-year evidence — a **placement** problem, which is exactly what triage's §5.2 resolution concluded and
then partly un-concluded in the headline.

**2. "0.37–0.60" is the worst of three committed windows for the same rule and ticker.** `deep-pools.csv`
`d_all` for the shipped rule is **0.3733** — and I established that this file is **NVDA only** (its
`d_all` 0.3733 / 0.8754 / 0.9317 match the N column of the README's table at `:37-40` exactly, not the mean
of the three). Meanwhile `all-stocks.csv` gives NVDA's shipped rule **`d55_up = 0.8844`** on hourly bars,
and the backtest README's own prose at `:13` says **0.81**. So the repo's committed numbers for the shipped
rule on NVDA are **0.37 / 0.81 / 0.88** depending on window. Leading with 0.37–0.60 is the same
worst-column selection that F-12 criticises the repo for making in the other direction. The finding should
state the range.

**3. "0/252 forward-time cells" is 252 rules on one ticker**, not 252 observations. E-2's sentence implies
breadth it does not have.

**Grade.** Medium under the disclosure clause is defensible and I would not fight it, but a reader should
know the Low argument: the risk is disclosed accurately, at length, and self-critically one directory away
and linked from `docs/README.md`; the front page's number is self-labelled; and
`docs/rule-backtest/README.md:129-136` names the first wave explicitly and says *"NVDA is a 0.81 here"*.
This is the weakest Medium in the report and the one most likely to be argued down by the client.

---

## F-12 · the backtest's methodology
### Verdict: **CONFIRMED — its two hardest claims verify exactly. One stated reason is a misreading.** Status: EXECUTED.

I recomputed against the committed CSVs and the committed generator:

- **`score == min(min, h_fwd, h_rev)` in 252 / 252 rows**, and including `d_all` breaks it in
  **252 / 252 rows**. `d_all` is silently excluded. Exactly as claimed.
- Shipped rule: `d_all = 0.3733` against `score = 0.5712`. Exactly as claimed.
- The burn contradiction reproduces exactly: `burned` = **0.0907** (shipped) → **0.0508** (30/60) →
  **0.0000** (60/120), against the README's 36% → 86% → 91% for the same three rows. A row the README
  reports as burning 91% of the tax reports **zero** in the only committed burn statistic.
- `--reverse` at `tools/rule_backtest.py:87` is
  `s = [(s[i][0], s[len(s) - 1 - i][1]) for i in range(len(s))]` — the price path reversed with the
  original timestamps kept. F-12's characterisation (`r'_i = −r_{n−i}`, skew negated, daily boundaries on
  the wrong bars) is correct, and the skew point is a genuine contribution the document does not make.
- Provenance: the generator writes
  `ticker, ann_vol, path_x, tp1, dip, stop, lot, <replay keys>`. None of the three committed CSV headers
  matches. `eleven-stocks.csv` is plainly a merged up/dn join. **Nothing can be re-run end to end.**
  Confirmed.

**The one misreading.** F-12 says the deep pools *"were run at 10 bps per swap while the same document
states the real per-swap floor is `maxSlippage + pool fee` = 105 bps"*. 105 bps is not a per-swap cost. It
is the **constructor bound** used to floor `tp1Bps` and `dipBps` (`StrategyTreasury.sol:41`), built from
`maxSlippageBps`, which is a **cap on tolerated slippage**, not realised slippage. The realised per-swap
cost on a 0.05% pool at small size is the 5 bps fee plus a few bps of impact; 10 bps is defensible and
arguably generous. F-12 then concedes the whole point (`10 → 105 bps moves NVDA's multiple by ≈ 0.010.
None of this changes a sign`), so nothing rests on it — but "the real per-swap floor" should be struck.

Grade Medium: agreed, on the disclosure clause.

---

## F-14 · the suite's result depends on the checkout's absolute path
### Verdict: **CONFIRMED, and I widened it again. Plus a new consequence nobody noticed.** Status: EXECUTED.

**Reproduced at a sixth checkout, with a fifth distinct outcome.** In
`…/adv-scratch/zq-adversarial-checkout-number-five-xyzzy` (byte-identical source, `lib` symlinked), forge
1.8.1:

```
forge test --no-match-path 'test/*Fork*'
  -> 616 passed, 4 FAILED, 1 skipped   (621 total)

[FAIL: no nonce] test_R4_2_aCopiedRouterLaunchIsRefused_andTheCreatorsOwnLaunchThenLands()
[FAIL: no nonce] test_R4_3_aSeedWithNoFirstBuyLeavesTheAnchorUnset_untilThePoolHasTraded()
[FAIL: no nonce] test_router_dustAndHugeBuys_bothOrderings()
[FAIL: no nonce] test_router_protocolReenteringTheRouterFromTheNativeFee_getsNothing()
  all in test/AuditRouterRound4.t.sol
```

Four failures, in a set nobody has reported: the lead and the tests lane saw **one** test in this file
(`test_router_tokenIsCurrency0_V3venue`), the prior-rounds lane saw a different file, triage saw a third
file. Six checkouts, **five** distinct outcomes, and the worst draw so far is **four** simultaneous
failures. That is not a flaky test; it is a lottery whose variance nobody has bounded.

**The fix is confirmed, again, independently.** Adding only `bytecode_hash = "none"` and
`cbor_metadata = false` to `[profile.default]` in the directory that was red:

```
forge test --no-match-path 'test/*Fork*'  ->  620 passed, 0 failed, 1 skipped
```

### New: the fix also buys back ~106 bytes of EIP-170 margin in every budget in §2c

`forge build --sizes` in the same tree, with and without those two settings:

| | with metadata (= §2c) | `bytecode_hash="none"` + `cbor_metadata=false` | gain |
|---|---|---|---|
| `StrategyFactory` margin | **945** | **1,052** | **+107** |
| `TreasuryDeployer` margin | **2,158** | **2,264** | +106 |
| `HookDeployer` margin | **8,147** | **8,253** | +106 |
| `TreasuryV4Deployer` margin | **5,823** | **5,929** | +106 |

The left column reproduces triage's §2c **byte for byte**, which independently validates that table. The
right column is new: the fix triage ranks #2 in urgency and calls "the cheapest fix in the report" also
relaxes by 11% the constraint §4 uses to ration F-05, F-06, F-17, I-3, I-6, I-7 and F-39. The two findings
interact favourably and nothing in the report says so. (Whether shipping without CBOR metadata is
acceptable for verification is a separate call — Sourcify and Etherscan both handle `bytecode_hash=none`
fine, and F-14 already argues reproducibility cuts the other way.)

### One qualification on "closes the class"

F-14 says `bytecode_hash = "none"` "is the one that closes the class". It closes **path**-dependence. It
does **not** make the tests robust: `predictToken` still hashes `type(StrategyToken).creationCode`, so any
future edit to `StrategyToken` or to the constructor encoding re-rolls every predicted address, and
`_qOrdered`'s 200-nonce search and
`test_theFirstBuyPaysExactlyWhatAStrangersBuyPays`'s exact-equality assertion can go red again on a
perfectly good change. The fix makes the lottery **deterministic**, not absent. Both halves of F-14's
recommendation are needed and it should not imply otherwise.

---

## F-15 · 12 of 24 treasury mutations survive a green suite
### Verdict: **CONFIRMED as reported; not independently re-run.** Status: REASONED (I did not rebuild the mutation harness).

I can corroborate the structural claim that makes it plausible: the treasury's only conservation assertion
is an inequality in the direction the bug moves, and the hook's ledger is asserted exactly. I did not spend
the budget re-running 24 mutants; the lane's method is sound and its Fix list item 8 ("give the calendar
mocks a forced-OPEN mode so F-02's path can be driven") is the single most useful line in the report,
because F-02's behaviour is currently **untestable by construction**. Flagged as the one Medium in this
report that rests entirely on one lane's unreplicated harness.

---

## F-16 · `_shrink` makes a caller-supplied lot index unstable
### Verdict: **CONFIRMED, and §5.4's resolution is right.** Status: REASONED (I re-derived both halves).

Both statements are true of the same code and they answer different questions. I verified the safety half
myself, which is the one that matters: `takeProfit` reads `lots[id]` at `:264` **after** `_book()` at
`:263`, and `_book` only `push`es; the threshold at `:267`/`:270` then runs on whatever lot is actually at
that index; `stopLoss` does the same at `:293-294`. A shifted index either reverts or sells a lot that
genuinely qualifies. I also checked the case nobody stated: if `_book()` pushes a **new** lot into the
caller's out-of-range `id`, that lot's `cost` is the current `p`, so `p * 1e4 < cost * (1e4 + tp1Bps)`
holds and the call reverts `NotDue`. Harmless. Low, loser is the caller and the integrator. Confirmed.

---

## F-17 · launch squatting
### Verdict: **CONCLUSION SURVIVES — but the primary proposed fix is broken, and the mechanism is stated one field short.** Status: REASONED.

**The fix does not work, and it is defeated by the very code the finding quotes.** F-17 recommends
`if (q.creator != msg.sender && msg.sender != owner()) revert BadRequest();` in `StrategyFactory.launch`,
and says it *"makes `LaunchRouter`'s guard redundant rather than load-bearing"*. `LaunchRouter.launch`
(`:64-67`) checks `q.creator == msg.sender` **for itself** and then calls `factory.launch(q, hookSalt)` —
at which point the factory's `msg.sender` is **the router**, not the creator, and not the owner. The
proposed check **reverts every router launch**, killing `LaunchRouter` entirely: the first buy, the seed,
`mustBook`, all of it. F-17 quotes `LaunchRouter.sol:60-63`, the comment that explains precisely this
arrangement, three lines above proposing a change that destroys it. This is the "recommendation defeated by
its own analysis" case in its purest form.

The second alternative F-17 offers — bind `msg.sender` into `_salt` and make `predict` take the launcher —
is coherent, but it is a front-end-breaking change, not "a few more bytes", and it must allowlist the
router or the router has to become the salted launcher.

**The mechanism is stated one field short.** F-17 says *"The attacker copies `(symbol, creator, nonce)`"*.
The token's CREATE2 address is `f(this, _salt(q), keccak(creationCode ++ abi.encode(q.name, q.symbol,
defaults.supply, this)))` (`:311-312`). `q.name` is in the **init-code hash**, not the salt, so an attacker
who copies the salt triple but changes `name` lands at a **different** address and the victim's launch
succeeds. To brick the victim the attacker must copy `(name, symbol, creator, nonce)`. Easy, but the
finding as written would not reproduce.

The conclusion — a permanent nonce burn plus rule-and-tax capture of the victim's symbol, gated on
`publicLaunch == true` which ships false — stands at Low.

---

## F-18, F-20, F-21, F-22, F-23, F-24, F-25, F-26, F-29 … F-41
### Verdict on the ones I verified: **CONFIRMED.** Status: REASONED unless noted.

Spot-checked against `9a291aa`, each at the cited line:

- **F-18** — `PriceOracle.sol:42` is verbatim
  `require(maxStockAge_ != 0 && maxStockAge_ <= 48 hours && maxUsdgAge_ != 0, "age");`. The asymmetry is
  real; `:68`'s comment ("the dollar leg never gets to be stale") is the one the band path leans on.
  `list`/`listV4` check only `IOracleStock(oracle).stock() == stock` (`:280`, `:298`). Confirmed.
- **F-19** — **EXECUTED (library read).** `renounceOwnership` is at
  `lib/openzeppelin-contracts/contracts/access/Ownable.sol:76`, `public virtual onlyOwner`, one step;
  `Ownable2Step.sol` overrides only `transferOwnership` and `_transferOwnership`. It does **not** override
  `renounceOwnership`. Confirmed exactly as stated.
- **F-20** — `:315` spends `spend - spend*bountyBps/1e4`, `:323` computes the bounty, `:324` books
  `mulDiv(spent, _SCALE, got)` with no bounty term. Confirmed.
- **F-21** — the three unchecked `uint160` casts at `:474` and `:487-489` are there. Reachability requires
  the token pool at tick ≈886,297; `_seedRange` does run to `maxUsableTick` (`:436`). Low is right.
- **F-22** — **confirmed at source.** `TwapRing.sol:52` is
  `int56 cum = last.cum + int56(last.tick) * int56(uint56(nowTs - last.ts));` — a checked `uint32`
  subtraction — while `meanTick` has the `if (nowTs < last.ts) return (false, 0)` guard at `:66` that
  `write` lacks. 2106, and the revert propagates out of `afterSwap`. Confirmed.
- **F-23** — `bind()` at `:53-56`, no access control; the factory binds all three from its own constructor
  at `:244-246`. Confirmed.
- **F-24** — `_v4`'s callback refunds `tokenIn` to `refundTo` at `TradeRouter.sol:148`, and `buy` passes
  `refundTo = msg.sender` while checking `minTokensOut` against `tokensOut` only (`:74`). The V3 hop is
  all-or-nothing at `:117`. Confirmed. Note the precondition is weaker than Low implies: the V4 hop uses
  `MIN/MAX_SQRT_PRICE ± 1`, so a short fill requires the **entire** seeded range to be consumed — i.e. the
  whole supply bought. Info-adjacent.
- **F-25** — `_notePrice(p)` is called unconditionally by `takeProfit` (`:275`) and `buyDip` (`:314`), and
  `_book` (`:253`) and `stopLoss` (`:290`) are the only two that check `pricedOffPoolOnly()`. Confirmed,
  and inert until a `setBandCeiling`.
- **F-26** — the mean branch (`:464-471`) has no widening term; the anchor branch (`:475-479`) does
  (`drift = half * (1 + elapsed/cd)`). Confirmed, and it composes correctly with §6's finding that the
  anchor branch is near-dead.
- **F-29 / F-30 / F-31 / F-32 / F-33 / F-34 / F-35 / F-36 / F-37 / F-38 / F-39 / F-40 / F-41** — read at
  their cited lines; no defect found in any of them. **F-33's** unprinted-eleven list checks out against
  the `Defaults` struct and the deploy script's defaults, which I read: `spikeSeconds 120`, `spikeBps
  9000`, `sweepTipBps 50`, `bountyBps 50`, `maxSlippageBps 100`, `maxDeviationBps 50`,
  `maxBuybackImpactBps 300`, `buybackCooldown 60`, `minLotUsdg 5e6`, `buybackChunkUsdg 500e6`,
  `tickSpacing 60` — every figure F-05, F-06 and F-07 price against. **F-13's** table recomputes: at
  `bountyBps = 50`, `takeProfit` at `tp1 = 10%` tips `0.0909 × 0.005 = 4.55 bps` of lot value and
  `stopLoss` at a 5% stop tips `0.95 × 0.005 = 47.5 bps` — ratio **10.4×**, exactly as stated, and
  `stopLoss` writes no `buybackStock` so the falling-market cycle really does burn nothing.

---

# 2. §6 "Checked and found safe" — attacked

I re-derived every impossibility claim that carries weight. **I could not overturn any of them.** Two are
imprecisely stated in ways a future reader could rely on wrongly.

## Re-derived and confirmed

- **The seed cannot be withdrawn. EXECUTED (library read).**
  `lib/v4-core/src/PoolManager.sol:160` passes `owner: msg.sender` into `Pool.ModifyLiquidityParams`, and
  `Position.calculatePositionKey` (`lib/v4-core/src/libraries/Position.sol:48-60`) keys on that owner.
  `grep -rn "modifyLiquidity" src/` returns **exactly one hit** — `StrategyFactory.sol:423`, positive
  `liquidityDelta`, `salt: 0`, inside `unlockCallback` whose first line is
  `if (msg.sender != address(poolManager) || !_seeding) revert NotPoolManager();` (i.e. **both** are
  required), with `_seeding` set only around the single `unlock` in `_openAndSeed` (`:408-410`) and
  `launch` `nonReentrant`. The unlock payload is constructed entirely from freshly deployed addresses. No
  second path, no owner path, no negative delta anywhere. **Safe.**
- **The observation ring cannot be starved after its first success.** `SLOTS = 1024`
  (`TwapRing.sol:26`) and `write` advances the index at most once per second (`:51` overwrites in the same
  second without advancing). A full ring therefore spans `≥ 1023 s > BUYBACK_TWAP_WINDOW = 600`, so
  `oldest.ts ≤ now − 1023 < target` always holds once wrapped, and before wrapping `oldest` is `obs[0]`
  whose timestamp is fixed. **`meanTick` genuinely never returns to `false` after its first `true`.
  Safe, and the consequence (the anchor branch is live only in the first 600 s of a pool's life) follows.**
- **Manipulating the mean can only tighten the buy-back bound.** `bound = max(fromMean, fromSpot)` for
  `zeroForOne` (where the limit is a floor) and `min(...)` otherwise (where it is a ceiling) — `:468-469`.
  Pushing the mean the "helpful" way loses to `fromSpot`; pushing it the other way tightens. `_clampToSpot`
  converts an over-tight bound into a zero fill, which `:380` turns into `NotDue` without consuming the
  cooldown or firing the spike. **Safe, and it is a genuinely good piece of design.**
- **No treasury outflow other than the four bounties and swap settlement.** Re-grepped from scratch
  (see F-04). There is additionally **no `approve` in either treasury**, which §6 does not say and should.
- **The one-wei lot is unreachable (R-1).** A lot is booked only above `minLotUsdg` (`:250`) and shrinks by
  `qty/2` **at most once**, because `L.half = true` is written at `:268` and the `else` branch then takes
  `q = L.qty`. `qty` cannot walk down to 1. **Correctly rejected.**
- **`buyDip` cannot divide by zero.** `got == 0` with `spent > 0` trips the `Slippage` check inside
  `_swapBounded` (`PoolTrader.sol:139`, and `keep = 1e4 − slip − fee ≥ 9600 > 0` at every permitted
  setting); `spent == 0` trips `NotDue` at `:322` before the `mulDiv` at `:324`. **Safe.**
- **`bandCeiling` is enforced at launch and frozen.** `StrategyFactory.sol:364` caps `q.bandBpsPerHour`
  and forces 0 on V4; `Params` is constructor-only in both treasuries. **Safe.**
- **The V3 ring gate is sound.** `PoolTrader.sol:61-62` requires `cardinality >= TWAP_WINDOW + 60 = 660`
  at construction, and `observationCardinality` cannot fall. With exactly 660 slots at one write per
  second the oldest observation is 659 s old ≥ 600. **Tight but correct.** Measured cardinalities in the
  repo's own `data/listability.json` (NVDA 6000, SPCX 3100, AAPL/GOOGL/SPY 1801, AMD/META 1400) all pass.
- **`_onlySeed` closes third-party liquidity.** `beforeAddLiquidity` → `_onlySeed` → `msg.sender ==
  poolManager` **and** `key.toId() == poolId` **and** `sender == seeder` (`:459-468`), `seeder` immutable.
  **Safe.**
- **`StrategyToken` really is inert.** 12 lines: OZ `ERC20`, one `_mint` in the constructor, one
  `burn(uint256)` that burns `msg.sender`'s own balance. No owner, no mint, no pause, no callback.
  **Safe**, and it is what makes two other §6 claims hold.

## Two precision defects (not unsafe, but do not rely on them as written)

**(a) "every one pays its bounty last, after all state is written (`:285`, `:305`, `:327`, `:386`)" is
false at `:386`.** In `buyback`, `token.safeTransfer(msg.sender, bounty)` at `:386` is followed by
`burned -= bounty` (`:387`), `IStrategyToken(token).burn(burned)` (`:388`),
`totalBurned += burned` (`:389`) and `IStrategyHook(hook).noteEvent()` (`:390`) — the call that **arms the
sell spike**. The other three do pay last. This is safe **only** because `token` is `StrategyToken`, a
plain OZ ERC20 with no recipient callback, and `buyback` is `nonReentrant`. If the pattern is being relied
on as an invariant — and §6 states it as one — it must be written as "three of four; the fourth is safe
because the token cannot call back", or the transfer should be moved below `:390`. The hazard it would
otherwise open is a bounty recipient trading in the token pool **before the spike is armed**, which is
F-07's window granted for free.

**(b) "the mined hook salt is a complete restatement guard over all nineteen `Defaults` fields" is an
overstatement.** I enumerated it. `_hookArgs` embeds `lpFee`, `tickSpacing`, `spikeBps`, `spikeSeconds`,
`protocolBps`, `sweepTipBps`, plus the token address (which carries `supply`) and the treasury address
(which carries `bountyBps`, `maxSlippageBps`, `maxDeviationBps`, `maxBuybackImpactBps`, `buybackCooldown`,
`minLotUsdg`, `buybackChunkUsdg`) — **13 fields**. The remaining six are `minTaxBps`, `maxTaxBps`,
`maxCreatorBps` (bounds on the creator's own inputs — changing them can make a pending launch revert
loudly, never succeed on different terms), `publicLaunch`, `launchFeeAmount` (covered by `maxFee`) and
`launchFeeCurrency` (**not** covered — that is I-2). The **substance** is right: no launch can execute on
different economic terms. "All nineteen" is not, and since §6 asks for this to be written down before
someone refactors it away, it should be written down correctly.

---

# 3. §5 disagreements — and one I settled by measurement

**§5.12 (CL-1 ~250–400 B vs C-02 ~40–70 B for F-05's validation block) — RESOLVED. EXECUTED.**
Triage said *"neither is measured, and I am not going to guess"* and turned it into an instruction. I wrote
the block exactly as F-05 specifies, inserted it after `StrategyFactory.sol:261`, and built:

| build | `StrategyFactory` runtime | margin | delta |
|---|---|---|---|
| `9a291aa` baseline | 23,631 | 945 | — |
| + F-05's four `require` lines | **23,906** | **670** | **+275 B** |
| + I-3 (sqrt bound) + I-7 (re-emit `DefaultsSet`) + F-39 (tp1/dip floor in `launch`, named error) + F-19 (`renounceOwnership` reverts) | **24,341** | **235** | **+710 B** |
| + I-6 (`slot0` staticcall + `cardinality >= 660` in `list`) | **24,736** | **−160** | **DOES NOT COMPILE** — `Error: some contracts exceed the runtime size limit (EIP-170: 24576 bytes)` |

**CL-1 is right and C-02 is wrong by a factor of 4–7.** And the answer to §4's footnote is concrete: the
full factory-side fix set **does not fit**. F-05 + I-3 + I-7 + F-39 + F-19 fits with 235 bytes to spare;
adding I-6 overflows by 160. With F-14's `bytecode_hash = "none"` applied the margins become 777 and −54 —
still an overflow. Triage's judgement that "F-05's is the better value" is therefore not a preference, it
is forced. (My spellings are one plausible implementation each; a tighter I-6 might squeeze in, but the
order of magnitude is settled.)

**§2c — CONFIRMED byte for byte.** My own `forge build --sizes` at `9a291aa`: `StrategyFactory`
23,631 / 945, `TreasuryDeployer` 22,418 / 2,158, `StrategyTreasury` 17,204 / 7,372, `TreasuryV4Deployer`
18,753 / 5,823, `StrategyTreasuryV4` 14,532 / 10,044, `HookDeployer` 16,429 / 8,147, `StrategyHook`
13,722 → I read 13,669/13,722 depending on metadata. Every number in §2c reproduces.
**§5.3 / I-16 — CONFIRMED**: 22,418 − 21,581 = **837 bytes** of deployer logic; the "twice over" claim is
dead and CL-7's proposed fix saves 837 B, not half a deployer. See the §2c caveat in F-14 above: all of
these margins gain ~106 B once the metadata fix lands.

**§5.6 (the calendar override, High against three lanes) — I side with the three lanes.** See F-02.
This is the one place I reverse triage's grade on a disagreement it flagged as its own judgement call.
Triage's decisive argument was C-01's own stated flip test; I checked the test and it is **not** met.

**§5.7 (`maxBuybackImpactBps`, Medium against three lanes) — Medium is right, the "~20" is not.** See F-06.

**§5.1 (L-17 vs HX-1) — resolution sound, with one caveat.** The decisive fact triage cites,
`TradingCalendar.sol:18-20`, is a disclosure of the **10–18 h feed gap**, not of the consequence that the
treasury will trade against a 16 h-old print. It is the reason the calendar exists, not a statement that
the resulting trade is acceptable. Low is still the right grade on the measured magnitude; but see F-02
wrong-4 for why grading this Low and F-02 High cannot both be right.

**§5.2, §5.4, §5.5, §5.8, §5.9, §5.10, §5.13 — I agree with all of them**, and §5.10 in particular is a
discipline I want to endorse loudly: refusing to rescale the ±1% numbers by 23× was correct, and my own
walk confirms it (constant-L errs 0.53×–1.35× at small moves; at +30% it errs by an order of magnitude).
§5.5 I reproduced and extended (F-14).

---

# 4. §7 rejections — attacked

I could not resurrect any rejected item. One inconsistency and one caveat.

- **R-1 (one-wei lot)** — correctly rejected; I re-derived the `L.half` argument independently. See §2.
- **R-2 (owner substitutes defaults mid-launch)** — correctly rejected; I re-derived the chain
  `d.supply → predictToken → token address → _hookArgs → init-code hash → mined salt misses 0x2844 →
  BadConfig → CREATE2 returns 0 → deployer `require` fires`. It reverts. Note the narrowing in §2(b).
- **R-3 (`TreasuryDeployer` embeds the creation code twice)** — correctly rejected; my build reproduces
  the 837-byte gap.
- **R-4 (HX-1's weeknight stale print)** — **correctly rejected as a value finding, but the rejection is
  inconsistent with retaining F-02 at High.** The residual R-4 leaves behind is U-8, the unmeasured cost of
  holding a pool against arbitrage for 600 s — the *same* term F-02, F-03, F-25 and F-27 all rest on. R-4
  is the version of that mechanism that needs **no Safe action and happens every weeknight**. Whatever
  grade the mechanism deserves, the weeknight instance cannot be lower than the weekend instance on
  reachability. Either both are Low/Medium disclosure items (my view) or both are higher.
- **R-5 through R-9** — all correctly reasoned; R-9 in particular (refusing to rescale) is right and my
  measurements support it.
- **U-1 (`supply < 1e12` breaks the seed)** — still unproven, and I did not run it either. It is one test
  and it is worth writing: `_seedRange` is handed `supply - supply / 1e12` at `:421` and the manager rounds
  what it is owed **up**, with that slack as the only cushion. A loud revert, so low severity, but cheap to
  settle.
- **U-5 (has a weeknight Chainlink gap ever exceeded 48 h)** — still the single measurement that would
  reopen R-4, and nobody has run it. Agreed.

---

# 5. Suspicions of my own that I chased and **disproved**

Recorded because a negative result is coverage. All of these are now ground the next round need not
re-walk.

1. **"F-01's `balanceOf` bound is an upper bound on D30."** *Disproved, and this one matters.* My exact
   walk pays **$2,118,250** to move NVDA +30% while the whole NVDA side is worth **$2,084,746**. You pay
   rising prices, so the USDG in exceeds the spot value of the stock out. The valid trivial bound is
   `1.3 × stock-side value`. (The conclusion of F-01 is unaffected; its stated arithmetic is.)
2. **"`takeProfit`'s `_book()` at `:263` can push a lot into a caller's out-of-range `id` and sell it."**
   *Disproved.* The pushed lot's `cost` is the current `p`, so the threshold at `:267`/`:270` is
   `p < p·(1+tp1)` — always true — and the call reverts `NotDue`. Harmless.
3. **"`buyback` pays the bounty before `burn` and before `noteEvent`, so a bounty recipient can trade
   before the spike arms."** *Disproved as reachable.* `StrategyToken` is a 12-line OZ ERC20 with no
   callback and `buyback` is `nonReentrant`. Recorded as a precision defect in §6 rather than a finding,
   because the invariant §6 asserts is false and only an unstated property of the token saves it.
4. **"`distributeStock(address caller)` and `distributeToken(address caller)` are `public` with a
   caller-chosen recipient, so anyone can redirect the sweep tip."** *Disproved.* Both only pay a tip out of
   **new** revenue (`bal − totalOwed`, and `t` respectively), the direct caller names themselves, and this
   is exactly what `sweep` does. No privilege is gained; `_distributing` blocks the reentrant case.
5. **"A launch squat only needs `(symbol, creator, nonce)`."** *Disproved.* `q.name` is in the token's
   **init-code hash** (`:311`), not the salt, so a copier who changes the name lands at a different CREATE2
   address and does not collide. The attack needs the full `(name, symbol, creator, nonce)`. (F-17's
   conclusion survives; its stated mechanism would not reproduce.)
6. **"The hook's `TwapRing` can be starved out of the 600 s window by a griefer writing one observation a
   second, as the sibling repo's `CLAUDE.md` warns for 1,800-slot V3 rings."** *Disproved.* 1024 slots at
   ≥1 s apart span ≥1023 s. §6 is right and the in-source comments warning of eviction are wrong, not the
   code.
7. **"`maxBuybackImpactBps = 2` is a hard brick like `1`."** *Disproved.* At 2, `half == 1`, which is a real
   if tiny price limit; whether it bricks depends on the pool's in-range liquidity against the chunk. Only
   `1` is a certain brick. (This narrows §5.7's claim.)
8. **"`_setDefaults`'s `protocolBps + maxCreatorBps > 1e4` strict `>` lets the two sum past 100%."**
   *Disproved.* `> 1e4` correctly rejects anything above 100% and permits exactly 100%, which is the
   `protocolBps = 10000, maxCreatorBps = 0` honeypot F-05 already reports. No second bug.
9. **"A third party can initialise the launch pool's key before the hook exists, or add liquidity to it
   afterwards."** *Disproved* at `_onlySeed` (`:464-468`) and `Hooks.callHook`'s selector requirement; §6's
   reasoning holds and I re-derived it.
10. **"`buyDip`'s `mulDiv(spent, _SCALE, got)` can divide by zero."** *Disproved* — two independent guards
    fire first (`Slippage` inside `_swapBounded`, `NotDue` at `:322`).

---

# 6. Closing

**What I would stake my name on.** **F-04** — I enumerated every value-moving path out of both treasuries
myself and there are exactly ten, nine of them gated on `health()` and the tenth on a five-day cache written
only by the other nine; there is no owner, no proxy, no approve and no rescue, and if Chainlink retires an
equity feed the strategy's assets are gone. **F-01's measurement** — I rebuilt it three ways, my exact walk
lands within 10% of lane 08's at a different block, and every `AUDIT.md` D30 figure exceeds its pool's
entire TVL by 1.2× to 9.9× on the repo's own committed data. **F-14** — six checkouts, five outcomes, my
draw the worst yet at four simultaneous failures, and a two-line fix I verified green that also returns
~106 bytes to every byte budget in the report. **F-12's** score-formula and burn-share claims, which verify
at 252/252 rows. And **§2c / §5.3 / §5.12**, now measured rather than estimated.

**The weakest things in this report.** In order.

**F-02 is the weakest finding at its stated grade, and it is a High.** Its severity turns entirely on the
rubric's "docs/SECURITY.md explicitly promises it cannot" clause, and `docs/SECURITY.md:33` explicitly
promises the opposite — it grants `setOverride(day, 2)` by name, with both of its gates. One of the two
in-source contradictions it cites is a truncated sentence whose own paragraph scopes it true. Its
"re-enables `_book` and `stopLoss`" mechanism is inert at the shipped configuration and, where it is not
inert, points the wrong way. And the strictly more reachable version of the same mechanism — the same
frozen print, on an ordinary weeknight, with no Safe action — was rejected by the same document as not a
finding. What survives is a real and permanent false statement in `TradingCalendar.sol:14-16` about a
permanent owner lever. That is a Medium, and it is where three of the four source lanes had it before
triage moved it.

**F-11 is the weakest Medium.** Its headline phrase is contradicted by the sentence on the front page it is
attacking, its number is the worst of three committed windows for the same rule on the same ticker, and the
document it says is missing is candid, thorough, self-critical, and linked one click away. The placement
complaint is fair; the framing will not survive a client's first reading.

**F-07's Impact numbers are the weakest arithmetic.** The one-transaction sandwich it describes is refuted
by the 18.99% figure F-07 itself quotes, and the "$1,000 rather than $9,000" line moves a grief someone
else must pay for into this actor's gain column.

**F-15 is the only Medium in the report resting entirely on one lane's unreplicated harness**, and I did
not replicate it.

**And the single most dangerous line in the report is not a finding at all**: §4's byte-budget footnote,
which instructs the team to write the whole factory-side fix set and size it once. I did that. **It does
not fit.** Anyone who reads that footnote as "it will be tight" rather than "one of these must be dropped"
will discover the EIP-170 overflow after writing all six fixes.


---

# Part 2 — third-party review of the rubric, framing and method

*Written without access to the source code, by design.*

# Lane 10 — review of the report, the rubric and the method

External audit round 1, 2026-09-21. Reviewed **without source access**, by design. Inputs: `BASELINE.md`,
`audit/round-1-2026-09-21/00-SCOPE.md`, `audit/round-1-2026-09-21/README.md`, `lanes/07-triage.md`.

I assume every finding's code path is exactly as triage describes. Nothing below disputes a mechanism. What
follows is about grading, framing, counting, emphasis and method — and specifically about what a reader
who takes this as a go/no-go input will conclude that the report does not support.

Two things first, because the criticism should be read against them. This round's self-corrections
(`README.md:68-81`, the L-1 retraction and the one-wei-lot retraction), its §7 rejection list, and its
refusal to let the F-01 correction contaminate F-34 (§5.10, "rejected before anyone made it") are better
than most commercial audits manage. §5 resolves eight disagreements by naming which question each side
answered, twice siding against the lead. Those parts are strong and I am not asking for them to change.

---

## 1 · "0 Critical" is close to a tautology of this architecture, and the report says so about the wrong clause

**What is wrong.** Critical requires *an unprivileged actor permanently takes or destroys treasury funds,
buyer funds, or the seeded liquidity, on the normal path*. Check each of the three objects against the
report's own §6:

- **Treasury funds.** §6: *"No treasury outflow exists other than the four bounties and swap settlement…
  Holders have no claim on the treasury — and neither does anyone else."* There is no withdrawal path for
  anybody, so "takes" is not a thing the code can do. That is not the audit clearing a hazard; it is the
  hazard class being absent by construction.
- **Buyer funds.** Buyers never deposit. They buy a token in a pool. There is no custodied buyer balance
  for an unprivileged actor to take.
- **The seeded liquidity.** §6: unremovable by anyone (`_seeding` latch at `StrategyFactory.sol:418`,
  `_onlySeed` at `StrategyHook.sol:459-468`), and uncollectable even by the protocol.

So two of Critical's three objects have no extraction path by design and the third is provably inert. The
only surviving route to Critical is **destruction** by an unprivileged actor on the normal path — and the
one total-destruction finding in the report, F-04, is caused by a *privileged third party* (the stock
issuer's `oraclePaused()`) or by Chainlink retiring a feed. It cannot reach Critical no matter how bad it
is.

`00-SCOPE.md:85-86` discloses one structural limit — the long-window-TWAP cap — and calls that the reason
"the report cannot structurally produce certain gradings." That is the smaller of the two. The bigger one
is unstated.

**Why it matters.** The author reads "Critical: 0" as "no showstopper was found." It actually reads
"the Critical tier was defined over asset pools this protocol does not have." A reader cannot distinguish
"we looked hard and found nothing catastrophic" from "catastrophic, as defined, is unreachable here," and
the report gives them no way to.

**Change.** In `ISSUES.md`, immediately under the counts table, add: *"Critical is defined over treasury
funds, buyer funds and seeded liquidity. This protocol has no treasury withdrawal path for anyone
(§6), no custodied buyer balance, and provably unremovable seed liquidity. A Critical under this rubric
would require an unprivileged actor to **destroy** one of those on the normal path. Zero Criticals is
therefore substantially a property of the architecture and only partly a result of this audit. The worst
outcome the rubric can express for a token holder is High."* Two sentences, and it is the single most
important correction in this review.

---

## 2 · The urgency table is the fix list a reader will work from, and it omits every measurement the report says must happen before launch

**What is wrong.** §4 has 15 rows, all of them code, doc or process fixes. §7 carries ten UNMEASURED items,
and the report's own language about six of them is decisive:

| item | the report's own words | in §4? |
|---|---|---|
| U-6 weekend liquidity thinning | *"the single most valuable thing to measure before signing any `setBandCeiling`"* | no |
| U-7 buy-back impact on a real seeded pool | *"the first measurement the next round should run"* (also F-07's UNMEASURED) | no |
| U-8 arb bleed over a 600 s hold | *"the difference between 'theoretically reachable' and 'economically reachable' for F-02, F-03, F-25 and F-27"* | no |
| U-5 has a weeknight Chainlink gap ever exceeded 48 h | *"the one thing that would reopen R-4"* | no |
| U-10 equity feeds' `minAnswer`/`maxAnswer` | *"worth reading before launch"* (I-5) | no |
| U-9 the chain's native token and its price | F-35 "collapses to nothing" either way | no |

A reader who works down §4 rows 1–15 and stops will have done every fix the report ranks and none of the
six measurements it says gate the decisions. U-8 in particular gates the *severity* of two of the four
Highs: F-02 and F-03 both have a condition whose cost is unmeasured, and F-03's whole High grade sits on
top of it.

**Why it matters.** This is a go/no-go input. The report's structure tells the reader that the decision is
a list of patches. It is not: four of the four Highs have at least one UNMEASURED condition, and three of
the measurements that would settle them are not on the list the reader will read.

**Change.** Add §4b, "What must be measured before the first `list()` and before the first launch, and
what each one gates" — six rows, each naming the finding whose grade moves if the measurement comes back
badly. Put it immediately after §4, not in §7's tail.

---

## 3 · The four Highs are not peers, and two of them are one root cause counted twice

**What is wrong.** Side by side:

| | what it is | actor | magnitude | status | reachable today |
|---|---|---|---|---|---|
| F-01 | a wrong number in `AUDIT.md`'s D30 table and one source comment. Triage: *"Not a code path."* | none | 0 direct | EXECUTED (see §5 below) | the number is wrong now |
| F-02 | `setOverride(day,2)` contradicts `docs/SECURITY.md:31` | the Safe, 2-of-4 | bounded per fill; *"certain gain to any actor: 0"* | mechanism EXECUTED, impact not | needs a Safe action |
| F-03 | `MAX_BAND_BPS_PER_HOUR = 200` vs a measured 10 | pinner | +3,311 USDG measured on an AMD-sized pool | uptime table EXECUTED, composition REASONED | **no** — `bandCeiling` is 0 for every stock and §6 confirms it is enforced in four places |
| F-04 | oracle dies → 100% of treasury assets frozen forever | issuer / Chainlink | **total, permanent, unrecoverable** | REASONED; *"no lane ran it"*; probability *"UNMEASURED… no base rate attempted"* | needs an external failure |

These four differ by orders of magnitude in consequence and by kind in actor. F-04 is the only total loss
in the report. F-03 requires two deliberate future decisions against a default the report elsewhere calls
correct. F-01 moves no value at all and its own grading note concedes *"a reader who insists severity must
track an attacker's gain will read this as Medium."*

Worse for the count: **F-01 and F-03 are one finding.** F-03's title says *"the ceiling was sized against
a depth number 23× too high"*; its body says *"This is the finding F-01 re-grades"*; F-01's impact section
lists the band ceiling and TR-1's break-even as consequences 1 and 2 of itself. The $54M-vs-$2.33M error
is being counted as two Highs.

**Why it matters.** "4 High" tells a reader there are four comparably serious defects. There are three
distinct roots, one dormant, one with no value impact, and one — the only one that can end the product —
carrying no execution and no probability estimate.

**Change.** (a) Merge F-03 into F-01 as F-01(b), or state in the counts table that two Highs share one
root. (b) Rank within the High tier explicitly, and give each High a one-line "worst case / likelihood
basis" header. (c) Say plainly next to F-04 that the highest-magnitude finding in the report was not
executed and its probability was not estimated — the report knows this and buries it in condition 1.

---

## 4 · Six of the fifteen High-and-Medium findings are not properties of a launched strategy, which is the only thing the rubric claims to grade

**What is wrong.** The rubric's opening sentence: *"severity is graded on the state of a **launched
strategy**."* Now the Medium tier:

- **F-14** (Medium, urgency #2) — the test suite's pass/fail set depends on the checkout path. A launched
  strategy has no checkout path.
- **F-15** (Medium, urgency #9) — 12 of 24 mutants survive. Same.
- **F-11** (Medium) — the front page's framing vs the backtest. A documentation and marketing critique.
- **F-12** (Medium) — five methodology errors in a Python backtest. Not deliverable code; `00-SCOPE.md:33`
  puts `tools/` out of scope except for exactly this methodology check.
- **F-01** (High) — a measurement error in a markdown table.
- **F-33** (Low) — a `console2.log` block in a deploy script.

Five of the fifteen High+Medium rows, plus one Low, are graded on a scale whose defining question does not
apply to them. F-14 and F-15 are then ranked #2 and #9 in an urgency table titled "Urgency at first
launch."

I am not saying these should be dropped — F-14 is the best-evidenced finding in the report and its fix is
verified. I am saying they are on the wrong axis. A reader counting "4 + 11 = 15 things that could hurt a
launched strategy" is wrong by roughly 40%.

**Why it matters.** The severity number is the only thing most readers will carry away per finding, and
these six borrow their weight from a scale built for something else. Conversely, grading a CI defect
against "does it take funds" *understates* F-14 and F-15: their real claim is "the gate in front of
unpatchable code does not work," which has no natural place on this rubric at all.

**Change.** Add a mandatory `Class` field to every finding: `CODE` / `OWNER-POWER` / `DOC` / `MEASUREMENT`
/ `PROCESS`, and give the counts table a column per class so the headline reads
"4 High (2 CODE, 1 OWNER-POWER, 1 MEASUREMENT)". Grade the non-CODE items on the same scale if you must,
but never let them be summed into a vulnerability count without the split visible.

---

## 5 · F-01 is labelled EXECUTED, and what was executed does not establish the claim it is ranked #1 for

**What is wrong.** F-01's claim is that `AUDIT.md`'s D30 table *"overstates the cost of moving a listed
pool by 8–25×."* That is a comparison between two numbers. What was executed establishes only one of them:
pool inventory and an exact tick-walk **at one block on 2026-09-21** (68,632,038 for lane 08, 68,651,755
for triage's own reproduction). Nobody established when `AUDIT.md`'s figures were measured, at what price,
against what pool, or from what method.

The finding then proves, in its own condition 3, that the quantity being compared is violently unstable:
*"Active `L` on NVDA fell **−60.6%** in 12.3 h… A depth number without a read date is not a number."* That
sentence is correct and it applies to both sides of the comparison. The report applies it to one.

The `balanceOf`-based leg is genuinely stronger — *"you cannot buy more NVDA than the pool holds"* against
a pool holding ~$2.19M defeats $54M robustly **if the pool's inventory has never been ~25× larger**. No
lane checked historical TVL on that pool, or on any of the other four. That is one `cast call` per pool at
an archive block, and the report's #1 urgency item turns on it.

Two smaller EXECUTED overstatements in the same class:

- **F-02** is EXECUTED "by two lanes independently." The execution demonstrates `setOverride(day,2)`
  flipping `isClosed`. The *grade* comes from the third High clause — a prose promise in
  `docs/SECURITY.md:31` — which is a reading, not a run; and the *impact* needs condition 4, whose cost is
  explicitly UNMEASURED. F-15's own fix item 8 says F-02's path is *"currently untestable by
  construction."* The label covers the mechanism and reads as covering the harm.
- **F-03**'s headline ("20× the value at which the repo's own measurement says the band stops buying
  anything") rests on `docs/band/crcl-usdg-14d.csv` — **one pool, 14 days**, which condition 4 labels
  UNMEASURED for representativeness. The finding is honest; the High in the counts table is not annotated.

And one rejection resting on the same kind of sample: **§5.1 / R-4** downgrades HX-1 to a docstring fix on
the strength of L-17's 30 Chainlink rounds over 7 days, while U-5 concedes that the decisive question —
has any weeknight gap exceeded 48 h — is unmeasured. A rejection built on a 7-day sample of one feed
should be labelled provisional, not filed under "Rejected outright."

**Why it matters.** Rule 6 exists precisely so a reader can tell which conclusions are load-bearing.
EXECUTED on the report's #1 item, where the execution is a one-block snapshot compared against an undated
figure, spends exactly the credibility rule 6 was written to protect — and I-14 makes this point about the
project's own documents (*"a document that overstates one risk by 100× spends the credibility it needs for
F-01 and F-04"*). The same standard applies to the audit.

**Change.** (a) State, in F-01, that `AUDIT.md`'s D30 figures are undated and that this audit did not
attempt to reproduce them at their own block; (b) run one archive `balanceOf` per pool at a few historical
blocks and either close the question or record it as UNMEASURED; (c) split the `Status` line into
`Mechanism: EXECUTED/REASONED` and `Impact: EXECUTED/REASONED/UNMEASURED`, and apply it to F-02 first;
(d) move R-4 from "Rejected outright" to "Rejected on a 7-day sample; U-5 reopens it."

---

## 6 · Twenty-six Lows, and the tier is absorbing the product's central economic facts alongside a bug that fires in 2106

**What is wrong.** Inside one tier:

- **F-22** — a `uint32` wraparound in **2106**. The finding says "Low by horizon."
- **F-21** — needs the token to appreciate by ~e^88. *"which is to say essentially nobody."*
- **F-41** — one word wrong in a markdown status header.
- **F-28** — *"Dust-scale"*, in redeployable periphery the finding itself calls *"a non-issue."*
- against
- **F-38** — of every 1.0 of sell tax: 4.48% reaches holders as a burn on the first pass, 45.23% is locked
  in a reserve only `buyDip` can spend, 50.25% is extracted. *"the single most informative fact about the
  token."*
- **F-37** — the creator's revenue is *"entirely independent of `tp1`, `tp2`, `dipBps`, `stopBps`, `lotBps`
  and `bandBpsPerHour`… no stake, no vesting, no clawback."* A structural incentive defect in a product
  whose whole premise is that a creator picks a good rule.
- **F-34** — a sandwicher takes up to `maxSlippage + poolFee` of **every treasury trade above the
  break-even**, *"on ordinary open trading days"*, break-even $2,965 on INTC. The Medium tier's first
  clause is *"bounded or recurring value leak."* This is one.
- **F-36** — *"On the corrected depths the same problem starts on NVDA"* — the flagship listing cannot
  deploy its reserve or sell its lots.

The tier preamble says *"Each is real and permanent."* That is false of F-33 (a script print), F-41 (a
markdown word), F-23 (a deployment-day race), F-28 (redeployable periphery) — four of the 26 are described
inside their own text as neither permanent nor code.

The boundary is being drawn by *is it a defect* rather than by *how much does it cost*, which contradicts
the rubric's own magnitude-based text. The clearest demonstration is internal: F-06 was promoted Low→Medium
(§5.7) because *"`buyback()` is the essential path… the sole mechanism by which a holder ever receives
anything."* F-38 says that on the normal, entirely non-buggy path, that essential mechanism returns 4.5% of
tax on the first pass while the front page says "the remainder to the treasury." If bricking the burn is
Medium, the burn being 4.5% by design cannot be a Low by the same reasoning.

**Why it matters.** Twenty-six Lows reads as a tail of small stuff a reader can defer. Four of them —
F-34, F-36, F-37, F-38 — are things a buyer and an operator need before launch, and two of them meet the
Medium text on its face.

**Change.** (a) Re-grade F-34 and F-36 to Medium under "bounded or recurring value leak"; (b) split the
Low tier into "Low — permanent and in code" and "Low — process, docs, or horizon", and move F-22, F-21,
F-28, F-33, F-41 into the second; (c) promote F-37 and F-38 out of the finding list entirely into a short
"What a buyer is actually buying" section, because they are not defects and grading them as defects is
what pushed them to Low.

---

## 7 · The rubric asks "what does the attacker gain" and the answer is zero in 32 of 41 findings

**What is wrong.** Rule 3 mandates a certain-gain / option-gain split on every finding. Counting the F-tier:
**about 32 of 41 report certain gain 0 and option gain 0.** The nine with a non-zero figure are mostly the
owner (F-05), the creator (F-37), a paid keeper (F-13), or a pinner under conditions that do not exist
today (F-03).

That is not a defect in the findings — it is the correct answer for a protocol with no custodied funds. It
is a defect in the rubric, because both of its top tiers are defined by an actor *taking or destroying*,
so a field that reads 0/0 in four-fifths of cases is also a persistent downward pull on every grade. The
report had to argue *against* its own rubric to reach three of its four Highs:

- F-04: *"Why High, on a rubric written around an attacker."*
- F-01: *"A reader who insists severity must track an attacker's gain will read this as Medium."*
- F-02: High only via the third clause, a doc-promise trigger bolted on beside the extraction clauses.

And §5.2 downgrades F-11 from High partly because *"there is no value transfer and no attacker"* — that
is, the finding that most directly predicts a buyer losing money is graded down for the absence of a thief.

**Why it matters.** Three overrides out of four is not a rubric being applied; it is a rubric being worked
around. A reader comparing this report's counts to any other protocol's will be comparing a codebase where
extraction is architecturally unavailable against ones where it is the main risk.

**Change.** State it as a finding of the audit, in the report's own voice: *"This rubric measures
extraction. In this protocol nothing can be extracted, so 32 of 41 findings report zero attacker gain and
three of four Highs were graded against the rubric's grain rather than with it. The dominant risk here is
not theft; it is that a permanent contract does something other than what the documents say."* If a second
round reuses the rubric, add a fourth High clause for "permanent, unrecoverable loss of use of treasury
assets with no actor profiting" so F-04 does not have to be argued in.

---

## 8 · The most consequential section of the report is §6, and it is the only one with no second reviewer

**What is wrong.** §6 "Checked and found safe" is ~60 claims, and several are load-bearing for the
decision: the seed is unremovable; `bandCeiling` 0 is enforced in four places so *"a treasury launched
today can never trade a closure"*; *"the pool is only ever a veto, never the price… the single most
important safety property in the rule"*; the ring cannot be starved; no `unlockCallback` is third-party
reachable; nothing in `src/` is upgradeable.

The verification phase (`README.md:58-61`) is: triage (by an agent that ran no lane), adversarial
falsification (*of triage's output*), test-suite review, and this pass. The adversarial agent is pointed at
**findings** — i.e. at false positives. Nothing in the method is pointed at §6, which is where the false
negatives live. A wrong "safe" in this report is far more expensive than a wrong "Medium": it is the item
the next round is explicitly told not to re-derive (*"This section is a deliverable of equal standing — it
is what stops the next round re-deriving the same ground"*).

Second, §6 mixes evidence grades. Some bullets say EXECUTED; many are greps and code reading with no label
at all (*"grep over both treasuries… returns exactly…"*, *"`bookedStock == Σ lots[i].qty` holds"*). Rule 6
is applied to findings and not to the safe list.

**Why it matters.** A reader treats §6 as verified ground and skips it. It is the section most likely to
contain the thing that ends the protocol, and it is the section with the least scrutiny per claim.

**Change.** (a) Label every §6 bullet EXECUTED or REASONED, same as findings — rule 6 should say so
explicitly; (b) point the next adversarial pass at §6 rather than at the finding list, and say in the
report that this round did not do that; (c) flag the ~8 §6 claims that are load-bearing for go/no-go
(seed unremovability, `bandCeiling` enforcement, veto-not-price, callback authentication, no
upgradeability, monotone supply) and require an independent re-derivation of each.

---

## 9 · "52 new" flatters this round; the honest number is 3 new Highs and about 5 overturned dispositions

**What is wrong.** §2b reports 52 of 59 new against the author's five rounds. Three problems:

1. **17 of the 52 are Info** — defined as *"no value impact."* Counting no-value-impact items into a
   novelty score against the author's 34 makes the comparison meaningless.
2. **The baseline is the author's own self-reported ledger.** "New" means "not written down in `AUDIT.md`",
   not "not previously known." Nothing checked the gap between what the author found and what he recorded.
3. **Several "new" items are corrections to prior findings, not new mechanisms.** F-41 corrects FA-1's
   disposition. F-39 is a contradiction *between two prior-round fixes shipped in the same commit*. F-40 is
   "R4-3's guard accidentally covers HK-4's window." I-1 is "FA-5's fix pinned the parameter and left the
   mechanism open." F-05 is explicitly the complement of FA-4 in the same validation block. These are
   audit-of-the-audit results — valuable, arguably the most valuable thing this round produced — but
   filing them as "new findings" inflates the count in the direction that justifies the round.

**Why it matters.** `README.md:7-23` uses the author's five self-audits to justify this round's existence,
then the counts table appears to vindicate it 52-to-nothing. The argument is fair; the number is not the
one that makes it.

**Change.** Replace the single "new" table with three numbers: **new mechanisms (High/Medium only)**;
**prior dispositions overturned** — F-41, F-02, F-39, I-1, F-23, roughly 5 of 34, which is the real measure
of what independence bought and is a strong result on its own; and **Info/Low, listed but not counted**.
That framing is both more honest and more persuasive than 52.

---

## 10 · The independence argument applies to this round too, and the report does not say so

**What is wrong.** `README.md:14-23` disqualifies the author's five rounds because every commit is
co-authored by Claude models and *"Author rounds 1–5 are therefore one reviewer's five passes, not five
independent confirmations. Where they agree with each other that is evidence of a shared model of the
protocol."* This round is six Claude lanes plus a Claude lead, a Claude triage, a Claude adversarial pass
and this one. Same model family. The report never states this.

The claimed source of diversity is information isolation, not reasoner diversity — and the report's own
evidence is mixed on whether that works: the lanes converged heavily where the code is legible (F-02 found
by four lanes, F-05 by five) and produced single-source findings exactly where judgement was required
(F-04, F-08, F-10, F-13, F-36, F-37, F-38 are all economic-lane-only). That pattern is what you would
expect if the lanes share a prior and differ only in what they were shown.

**Why it matters.** The report's central justification is independence. A reader should know that what was
gained is *absence of authorship investment* and *information isolation* — both real — and not *a second
mind*. The correlated-error risk the report identifies in the author's five rounds is reduced here, not
eliminated.

**Change.** One paragraph in `README.md` under "Independence": name the model family used for the lanes,
state that the independence claimed is from authorship and from shared information rather than from
reasoner diversity, and say that a shared-prior failure mode is not excluded by this design.

---

## 11 · The economic lane got everything and checks the least, and it is the sole source for the report's worst-case finding

**What is wrong.** The lane table (`README.md:45-52`) shows the economic lane as *"full repo **and** all
docs, backtests and chain access — the one lane given everything."* It is also the single source for
**F-04, F-08, F-10, F-11, F-12, F-13, F-35, F-36, F-37, F-38** and for I-11/I-12/I-13/I-14 — roughly a
quarter of the report, including the highest-magnitude finding (F-04, REASONED, unrun) and every one of
the product-economics findings.

The lane most exposed to the authors' framing is the one whose output has the least cross-checking. Rule 7
correctly says single-source ranks equally on *reachability*; it says nothing about the *correlated* risk
that the one lane reading all the docs inherited the docs' model of the product. And there is no lane in
the other direction: **nobody was given only the documents and asked whether the code does what they say.**
Yet the report contains at least five doc-vs-code contradictions found as by-products — F-02
(`docs/SECURITY.md:31`), F-26 ("one cap-sized step per cooldown" describes a dead branch), F-40 ("refuses a
tick with no liquidity" is true of the ring and false of the anchor), I-2 (the `maxFee` pair claim), F-41
(`AUDIT.md`'s status header) — plus the ring comments that §6 says are *"wrong, not the code."* Five
incidental hits is strong evidence that a dedicated docs-inward lane would find more.

**Why it matters.** Doc-vs-code contradictions are this protocol's highest-yield finding class — one of the
four Highs is one, and the third High clause exists specifically for them. The method had no lane aimed at
them.

**Change.** Say in `README.md`'s method section which findings are economic-lane-single-source and that
the lane with the most context had the least cross-checking. For round 2, replace one lane with a
**docs-first lane**: given `README.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md` and nothing else, write
down every promise as a testable assertion, *then* read the code to check each one.

---

## 12 · "620 tests pass" and "12 of 24 mutants survive" appear far apart, and the negative result should lead

**What is wrong.** `BASELINE.md:51-52` and `00-SCOPE.md` both open with *620 passed, 0 failed*. §6 calls the
suite's shape *"unusually good."* F-15, at Medium and urgency #9, says a green run is *"no evidence at all
about treasury arithmetic, the oracle's round-sanity guards, or the TWAP ring"* — three of the most
safety-critical components in the system — and lists 12 surviving mutants including a deleted
`answer <= 0` oracle guard, `maxStockAge` 48 h → 96 h, a doubled sweep tip, and a deleted `TwapRing`
negative-mean correction.

Separately, "12 of 24" should not be read as a coverage percentage: 24 mutants is a small, hand-chosen
sample and the chooser also wrote the analysis. The report does not say so.

**Why it matters.** The green tick is the first number a reader meets and the strongest reassurance in the
document. Its actual meaning — the hook and the routers are well covered, the treasury arithmetic is not
covered at all — appears 1,100 lines later.

**Change.** Put the negative form in `00-SCOPE.md`'s build/test block: *"620 tests pass. A green run is
evidence about the hook's ledger and the routers, and provides no evidence about treasury arithmetic, the
oracle's round-sanity guards or the TWAP ring — see F-15."* And state that 24 mutants is a sample chosen
by the reviewer, not a coverage measure.

---

## 13 · There is no "reachable at the shipped defaults?" column, and six of the fifteen High+Medium findings are not

**What is wrong.** F-03 (`bandCeiling` 0 everywhere, enforced in four places), F-05 (needs an owner
`setDefaults`), F-06 (needs a typo in an unprinted field), F-25 (needs `bandBpsPerHour != 0`), F-27
(`v4ListingEnabled` false), F-30 (V4 only) are all unreachable at the state that would actually ship
tomorrow. `README.md:95-97` justifies grading them anyway — *"a boolean an owner can flip is not a security
property"* — and that stance is defensible.

But *not grading* on defaults is different from *not reporting* defaults. The report currently gives a
reader no way to see that a material fraction of its High+Medium findings require a future deliberate
change to a default the report elsewhere calls correct.

**Why it matters.** It cuts both ways and the report shows neither side. The reader cannot see that the
shipped configuration is safer than the count implies, and cannot see which single `onlyOwner` transaction
would activate four findings at once.

**Change.** Add one column to the counts and urgency tables: *"live at shipped defaults? Y / N — needs
`<transaction>`."* Keep the grades exactly as they are.

---

## 14 · F-04's rank is a judgement made with an input the scope explicitly refuses to supply

**What is wrong.** `00-SCOPE.md:35-38` puts the stock token and its issuer's powers out of scope: *"This
audit takes that as an unmitigated, external, unbounded risk and does not re-derive it."* F-04's condition
1(a) is the stock token's `oraclePaused()` stuck true — precisely that risk — and F-04 is ranked #4 in
urgency, above F-02 and F-03.

So the report declines to estimate the probability of the thing, then ranks a finding by it. The same
applies to F-08 (`adminBurn`), F-31 (issuer pause) and I-9 (transfer-fee upgrade): four findings whose
trigger lives entirely in a declared-out-of-scope dependency.

**Why it matters.** A reader sees a ranked list and assumes the ranking encodes likelihood × magnitude.
For F-04 it encodes magnitude only, and the report has ruled the other factor out of scope.

**Change.** State at the head of §4: *"Rows 4, 11 and several Lows are triggered by the stock token or its
issuer, which `00-SCOPE.md` places out of scope. Their rank reflects magnitude and permanence only; this
audit made no probability estimate and the scope forbids one."*

---

## 15 · The report never states what would have made it say "do not launch"

**What is wrong.** `README.md` is titled "How round 1 was produced, and what it could not reach" and does
exactly that, well. Neither it nor `00-SCOPE.md` states a decision rule: what finding, or what combination,
would have constituted a stop. The report knows it is a go/no-go input (it is the reason the round exists)
and leaves the criterion to the reader.

**Why it matters.** Absent a stated rule, the counts table supplies one. "0 Critical" will be read as the
green light — and per criticism 1 that is the one number in the report that carries the least information.

**Change.** Add a short "What this report does and does not license" section: this round does not clear
the protocol for launch; it identifies 15 items that are unfixable after the first launch, 6 measurements
that gate three of the four High grades, and one section (§6) whose safety claims have had no second
reviewer. Name the condition under which the round's own authors would consider the go/no-go answerable.

---

## Smaller items, recorded so they are not lost

- **§2a's "59 distinct mechanisms"** is softer than stated: F-09 is explicitly two mechanisms under one ID,
  F-13/F-20 are one bounty-accounting family, F-01/F-03 share a root, F-32 *"composes with F-02 and F-19."*
  Say "59 findings over roughly 54 mechanisms" or drop the word "distinct."
- **The Low tier's preamble** (*"Each is real and permanent"*) is false for at least F-23, F-28, F-33,
  F-41. One-line fix.
- **I-14 is a re-grade DOWN of the project's own disclosure by ~100×** and is filed as Info because it has
  no value impact. It is the clearest evidence in the report that the project's risk documentation is
  miscalibrated in *both* directions, which strengthens F-01 and F-04. It should be cited in the report's
  framing, not left in an Info row.
- **`00-SCOPE.md:28` says `test/` is in scope "not as code to be audited for vulnerabilities"** — then F-14
  and F-15 are graded on the vulnerability scale. Reconcile the two sentences.
- **F-35 depends on U-9, "the repo never states what the native token is."** That the audit could not
  determine the target chain's gas token is a method gap worth naming in `README.md`'s known weaknesses,
  not only inside one Low.
- **Rule 5** ("every on-chain number carries the date it was read") is followed scrupulously for this
  round's own numbers and not required of the numbers this round *compares against* — which is exactly how
  criticism 5 happened. Extend rule 5 to cited figures.

---

## The three sentences I would add to "Known weaknesses"

> **6. Zero Criticals is mostly a fact about the architecture, not a result.** Critical requires an
> unprivileged actor to take or destroy treasury funds, buyer funds or the seeded liquidity; this protocol
> has no treasury withdrawal path for anyone, no custodied buyer funds, and provably unremovable seed
> liquidity, so the tier is close to unreachable here — and three of the four Highs had to be graded
> against the rubric's attacker framing rather than with it, because 32 of 41 findings report zero gain to
> any actor.
>
> **7. The fix list is not the decision.** Six measurements this report itself calls decisive — weekend
> liquidity thinning, the buy-back's impact on a real seeded pool, arbitrage bleed over a 600 s hold, the
> longest weeknight Chainlink gap, the equity feeds' `minAnswer`/`maxAnswer`, and the chain's native token
> price — are absent from the urgency table, and three of them gate the severity of three of the four
> Highs. Working down §4 and stopping is not a launch decision.
>
> **8. The safe list has had no second reviewer.** §6's sixty claims are the part of this report a future
> round is told not to re-derive and the part most likely to contain a miss; the adversarial pass reviewed
> triage's findings, not triage's exonerations, and this round's eight sources share one model family, so
> the independence gained over the author's five rounds is from authorship and information isolation, not
> from a second mind.
