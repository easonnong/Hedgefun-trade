> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Findings — external audit round 1

Ref `9a291aa`, audited 2026-09-21. Scope, deployment reality and byte budgets: [`00-SCOPE.md`](./00-SCOPE.md).
Method and this round's known weaknesses: [`README.md`](./README.md). The five author rounds, re-verified:
[`PRIOR-ROUNDS.md`](./PRIOR-ROUNDS.md). Runnable reproductions: [`poc/`](./poc/), `./poc/run.sh`.

---

## What this report does and does not license

**It does not clear this protocol for launch, and the counts table is not a decision rule.**

Read these three things before the numbers:

1. **"0 Critical" is mostly a fact about the architecture, not a result.** Critical, under the rubric below,
   requires an unprivileged actor to take or destroy *treasury funds, buyer funds, or the seeded liquidity*.
   This protocol has no treasury withdrawal path for anyone — that is its central design claim and this audit
   confirms it — custodies no buyer funds, and its seed liquidity is provably unremovable. Two of the three
   objects the tier names cannot be extracted from at all, and the third cannot be touched. The tier is close
   to unreachable here **by construction**.
2. **32 of the 41 findings report zero gain to any actor.** The rubric asks what an attacker takes. For most
   of what is wrong with this system nobody takes anything: the loss falls on the treasury, on holders, or on
   the product's own premise. Three of the four Highs had to be graded *against* that framing rather than
   with it. A rubric shaped for a protocol with deposits is the wrong instrument for one with no redemption,
   and the next round should write its own.
3. **The most consequential thing in this report is not a vulnerability.** It is that the project's own
   measurements — the depth table its listing filter and band ceiling rest on, and the backtest of the rule
   it ships by default — do not say what the project's own front page says they say. Neither is a bug. Both
   would change a launch decision.

**What would have made this round say "do not launch"**, stated so the absence of it means something: an
unprivileged path to move value out of a launched treasury or the seeded liquidity; a creator-reachable way
to take a buyer's tokens; or a defect in the immutable per-launch contracts with no configuration that
avoids it. None of those was found. What was found instead is a set of configuration boundaries that permit
inert or predatory strategies, a documentation layer that contradicts the code in three places, and a
measurement basis that is wrong by an order of magnitude — all of which are fixable now and none of which
are fixable after the first launch.

---

## Severity rubric

Reproduced verbatim from the baseline every lane was given. **Severities here are not comparable with any
other report's, including `AUDIT.md`'s.**

Because the code is immutable and unpatchable once launched, severity is graded on the state of a
**launched strategy**, not on "can we fix it before mainnet".

- **Critical** — an unprivileged actor permanently takes or destroys treasury funds, buyer funds, or the
  seeded liquidity, on the normal path, without needing to manipulate a long-window TWAP and without needing
  the protocol Safe to misbehave.
- **High** — the same, but needs favourable market conditions, meaningful capital, or a race; OR it needs
  manipulation of a long-window (≥ 600 s) TWAP (**hard cap: anything that requires moving a long-window TWAP
  is High at most, never Critical**); OR the protocol Safe can do something that `docs/SECURITY.md`
  explicitly promises it cannot.
- **Medium** — bounded or recurring value leak, a grief that degrades the product without taking funds, a
  permanent brick of one non-essential path, or a disclosed risk whose disclosure materially understates it.
- **Low** — small, dust-scale, or needs an implausible precondition, but is real and permanent.
- **Info** — no value impact; clarity, docs, events, getters.

Applied in this order: grade the post-deployment state, not the diff; name the loser explicitly; split
certain gain from option gain; give every finding a condition list with today's status; date every on-chain
number, **including the ones a finding argues against**; label EXECUTED or REASONED; and never treat
"confirmed by N sources" as evidence.

---

## Counts

Graded after an adversarial pass that examined every finding and downgraded two of the four Highs. Nothing
is deployed, so these are all post-launch grades.

| | Critical | High | Medium | Low | Info | total |
|---|---|---|---|---|---|---|
| **whole codebase** | **0** | **2** | **13** | **26** | **18** | **59** |
| new relative to the five author rounds | 0 | 2 | 13 | 21 | 17 | 53 |

Eight sources raised 96 numbered items; 59 survive as findings over roughly 54 distinct mechanisms. The
adversarial pass returned **0 false positives** among the findings, **0 overturned entries** in the
"checked and found safe" section, and **0 overturned rejections** — but it broke one proposed fix, cut the
impact numbers on another, and found that **the full set of factory-side fixes does not fit** (below).

**Read the tiers with these caveats**, which the round's own reviewers raised against it:

- The **Low** tier is doing too much work. It holds the product's central economic facts — that roughly
  4.5% of a seller's tax reaches holders as a burn while 45% locks in a reserve only `buyDip` can spend
  and 50% is extracted, and that a creator has no economic stake in the rule's quality — alongside an
  integer overflow that fires in 2106. Treat the Low tier as unsorted, and read F-37, F-38 and F-34 as if
  they were Mediums for decision purposes.
- **Six of the fifteen High-and-Medium findings are not properties of a launched strategy at all**, which
  is the only thing the rubric claims to grade: two are about the test suite, two about documentation and
  backtest methodology, one is a number in a markdown table, one is a deploy script's logging. They are
  graded here for their consequence — an unpatchable contract shipping with a defect nobody could see —
  not as code defects. A reader counting "fifteen problems that can hurt a launched contract" is out by
  about 40%.

---

## What the adversarial pass changed, including in the lead's own work

Recorded first, because a report that hides its corrections cannot be used as an input to the next round.

**The lead's headline argument for the round's most-cited finding was wrong, and the adversary caught it.**
F-01 as first written said: *you cannot buy more NVDA than the pool holds, the entire NVDA side is worth
~$2.19M, so $54M is unreachable — two balances and one multiplication, no model needed.* That conflates the
**spot value of the stock taken out** with the **USDG paid in**. Walking a pool up you pay rising prices,
so the USDG in exceeds the spot value of the stock out; the adversary's own tick-walk pays **$2,118,250**
against a stock side worth **$2,084,746** — the claimed bound is exceeded by 1.6% by the very quantity it
claims to bound. The correct model-free bound is `1.3 × stock-side value`, and every exact figure falls
inside it. **The conclusion is untouched and the measurement reproduces three independent ways; the
sentence carrying it did not survive and is not published.**

The adversary then found the model-free check the lead should have made, which needs **no RPC call at
all**: `data/listability.json`, committed in this repository at `9a291aa`, carries each pool's TVL, and
**every D30 figure in `AUDIT.md` exceeds the entire pool it describes** — NVDA 8.7×, AAPL 9.9×, SPY 7.4×,
SPCX 5.1×, GOOGL 3.1×, META 2.7×, AMD 1.2×. That is the form this finding should always have taken.

Other changes:

| what changed | why |
|---|---|
| **F-01 High → Medium** | the measurement is right and reproduces, but there is no actor, certain gain is zero, and triage itself called it "not a code path". None of the three High doors opens. It keeps urgency rank 1. |
| **F-02 High → Medium** | its High rested on the rubric's "`docs/SECURITY.md` explicitly promises it cannot" clause — but `docs/SECURITY.md:33` explicitly **grants** `setOverride(day, 2)` by name, with both its gates. One of the two cited in-source contradictions was a **truncated sentence** whose own paragraph scopes it true. And its "re-enables `_book` and `stopLoss`" mechanism is **inert at the shipped configuration**: with `bandBpsPerHour == 0`, `pricedOffPoolOnly()` is already always false, so nothing is re-enabled. The lead's L-7 made the same error. What survives is one genuine, permanent falsehood at `TradingCalendar.sol:14-16` about a permanent owner lever — a Medium, which is where three of the four source lanes had it before triage moved it up. |
| **F-17's primary fix is broken** | adding `q.creator != msg.sender` to `launch` bricks `LaunchRouter` entirely — the very contract whose comment the finding quotes three lines earlier. |
| **F-07's impact numbers cut** | the one-transaction sandwich is refuted by the 18.99% round-trip tax the finding itself measures. The real take is ~$13–16 per event, not the merged figure. |
| **F-04's cause list trimmed** | of its four causes only one is permanent. `setOverride` takes **one day per call**, so an "indefinite" halt needs a transaction per trading day forever; a stuck `oraclePaused()` is a liveness risk of a trusted third party and reverses when lifted. **The load-bearing cause is Chainlink retiring the equity feed**, and the finding now leads with it. |
| **F-04's fix scoped honestly** | denominating the buy-back chunk in stock rescues `buybackStock` only. `bookedStock` and `reserveUsdg` stay frozen, because `takeProfit`, `stopLoss` and `buyDip` all still open with `health()`. One of three buckets, not the headline's "every asset". |

**And the one that constrains everything else: the recommended factory-side fixes do not all fit.**
`StrategyFactory` has **945 bytes** of EIP-170 margin. F-05's bounds block alone measures **275 bytes**, and
the full factory-side set **overflows by 160 bytes**. The F-14 fix returns about **106 bytes** to every
budget by removing the metadata hash, which does not close the gap. Something has to be dropped, and that
choice is the author's, not this report's.

---

## Urgency at first launch

Ranked by **what this costs on the day of the first launch and how fast the window shuts** — not by
severity label. Nothing is deployed, so every row is fixable *today*.

| # | finding | sev | still fixable after the first launch? | why it ranks here |
|---|---|---|---|---|
| **1** | **F-01** the depth table is 8–25× too high | Medium | **No, for that listing** — a treasury's oracle, pool and key are immutable | It is the *input* to rows 2 and 7 and to the listing set itself. Every decision made with it is permanent and it costs nothing to recompute. Fix first, because the other fixes are sized against it |
| **2** | **F-14** the suite's result depends on the checkout path | Medium | Yes — one line in `foundry.toml` | Cheapest fix in the report, verified green at two independently red checkouts, and it gates everything else. It also makes the deployed bytecode reproducible, which a protocol pitched as "verify it yourself" needs on day one, and it **returns ~106 bytes** to every EIP-170 budget |
| **3** | **F-05** `_setDefaults` under-bounds eight fields | Medium | **No** — frozen into the hook and treasury constructors | One `onlyOwner` call away, silent, and F-33 means the operator will not see it in the printed plan. **Measured at 275 bytes**, so it must be sized together with row 6 |
| **4** | **F-04** a dead oracle freezes the treasury forever | **High** | **No** — no owner, no proxy, no escape | Low probability, total and unrecoverable loss. The load-bearing cause is Chainlink retiring the equity feed; the others reverse. The partial fix is small and does not touch the factory |
| **5** | **F-02** `setOverride(day, 2)` contradicts the calendar's own header | Medium | Partly — the calendar is shared and live | Needs a Safe action, so no exposure until one; the fix is two lines and it also resolves F-32's conflicting remedies |
| **6** | **F-06** `maxBuybackImpactBps < 20` bricks the burn | Medium | **No** | A one-character typo in an unprinted field kills the product's only value-return path. Zero net bytes (`== 0` → `< 20`) |
| **7** | **F-03** the band ceiling is 20× too wide | **High** | **No** for launches that opt in | Two gating conditions, **both unmet today**, which is the only reason it is not rank 1. Both are one transaction away, and row 1 makes it worse: the break-even on NVDA falls from ~$181k to **~$7.1k** on the exact walk |
| 8 | **F-09** `book()` unpaid, unbounded in size and time | Medium | **No** | Re-based on row 1, the unsellable-lot threshold on the flagship pool is tens of thousands of dollars, not millions |
| 9 | **F-15** 12 of 24 treasury mutations survive a green suite | Medium | Yes, always | It is why the next finding gets through. Item 1 of its fix list — six `assertGe` → `assertEq` — is a single change |
| 10 | **F-07** the sell spike is absent half of every cycle | Medium | **No** | Small money at the defaults (~$13–16 per event). It ranks here because the honest fix (`buybackCooldown >= 2 × spikeSeconds`) makes the **shipped defaults illegal**, which is a decision someone must take before launch |
| 11 | **F-08** no treasury `_reconcile` | Medium | **No** | Needs an issuer action; permanent and silent when it comes, and untestable today |
| 12 | **F-11**, **F-12** the premise and the backtest | Medium | **Yes** — documentation | No code, no bytes, two sentences and a link. Below the code items only because it is reversible — but see "what this report does and does not license": it is the item most likely to change a launch decision |
| 13 | **F-10**, **F-13**, **F-20** three accounting choices that leak to principal | Medium/Low | **No** | Small per event, permanent, and all three fit `TreasuryDeployer`'s 2,158 B *together* — one pass or not at all |
| 14 | **F-23**, **F-33**, **F-39** deployment-day items | Low | Yes, process and script | Cheap, and the ones that will actually bite on the day |
| 15 | the rest of Low and Info | Low/Info | mostly **no** | Individually small; collectively the argument for one consolidated pre-launch branch rather than a trickle |

### The byte budget cuts across rows 3, 6 and several Infos — and the set does not fit

`StrategyFactory` has **945 bytes**. Measured, not estimated: F-05's bounds block is **275 B**, and the
full factory-side fix set **overflows EIP-170 by 160 bytes**. F-14's fix returns ~106 B, which does not
close the gap. **Something must be dropped, and that is the author's call.** F-06's fix is free (a changed
comparison), F-18's oracle-side half is free (22,365 B spare), and everything treasury-side is scored
against `TreasuryDeployer`'s **2,158 B**, not `StrategyTreasury`'s 7,372.

### The six measurements that gate this report's own conclusions — now taken

The round's internal reviewer flagged that six measurements the report itself calls decisive were missing
from this table, and that three of them gated three of the four original High grades. They were taken. All
dates 2026-09-21; all figures move, so re-read before relying on them.

| # | what was unmeasured | result | what it changed |
|---|---|---|---|
| 1 | **Longest Chainlink weeknight gap** over a real sample | 763 rounds over 68.8 days: **752 weeknight gaps, max 21.04 h, none above 48 h**; 10 weekend gaps, 50.11–78.24 h, all above 48 h | Settled HX-1 down to Low. Confirmed `maxStockAge ≤ 48 h` is correctly placed, with **27 h of margin** on the weeknight side — but only **2.1 h** on the weekend side, and that margin is structural (a weekend is exactly 48.00 h plus however long before Friday's close the last print landed). So the age gate is very nearly **no** second line of defence behind the calendar on a forced-open day, which is the precise version of F-02's condition 2 |
| 2 | **Chainlink `minAnswer` / `maxAnswer`** | `minAnswer = 1`, `maxAnswer ≈ 9.58e52` on both the NVDA and USDG aggregators | The Venus/LUNA failure mode — a real price falling through the floor and the feed returning the clamp — **cannot occur here**. Moves that concern from "missing check" to checked-and-safe, with the caveat that the safety comes from the aggregators' configuration, outside this repo's control |
| 3 | **Gas cost against the bounty** | `gas-price` 49,294,000 wei (0.0493 gwei); a 300k-gas `takeProfit` costs 0.0000148 native tokens | The native token is still unidentified — not in the repo, no feed on this chain — but the quantity is so small that a call would need a **~$340,000** native token to cost $5. F-35 drops to Info |
| 4 | **Does liquidity thin over a weekend?** | Six blocks across one week on NVDA/USDG: **no systematic weekend thinning** — the two highest active-`L` readings of the week are both on the weekend. But `L` swings **2.5× in hours**, and the project's **census block is the single highest reading of the week** (2.971e19 against 1.20–1.37e19 on Wed/Fri/Mon) | Compounds F-01: the depth table is wrong by method **and** sampled at a local maximum ~2.4× the weekday level. Pool NVDA inventory fell **−56% in five days** |
| 5 | **A buy-back's real impact on a genuinely single-sided seeded pool** | Real launch through the real factory: one 500-USDG chunk moves the pool **910 bps of sqrt price (~18% of price) when virgin**, 193 bps after 200 stock of buying, 23 bps after 2,200 | Cuts both ways, and both belong in the report. It **bounds F-07's payoff** — the impact cap binds precisely when impact would be large, so an exiting holder captures ≤ `maxBuybackImpactBps` **by construction**. And it **raises F-06's stakes**: the cap is the binding constraint on every early buy-back, so its floor being wrong is not theoretical |
| 6 | **Arbitrage bleed over a 600-second hold** | `Swap` counts over 10-minute windows on NVDA/USDG: Wed (open) 60 swaps / $15,650; **Sat (shut) 59 / $12,808**; **Sun (shut) 103 / $50,858**; Mon (open) 174 / $41,868 | **The pool does not go quiet when the equity market shuts** — on-chain confirmation that the reference market never closes. Pinning the 600 s mean on a weekend means standing in front of ~59–103 trades and $13k–$51k of flow per window. Against the corrected depth (+1% ≈ $98k) the bleed is the same order as the shove: **expensive but not prohibitive on NVDA**, and on the thin end of the listable set the bleed dominates the fee entirely. **Still open:** decomposing that flow into the part that trades *against* a pin |

---

## The findings

Grades below are **after** the adversarial pass. Where it changed a grade or cut a claim, the finding says
so inline. Its full verdict on every finding, and the third-party review of this report's own rubric and
method, are in [`VERIFICATION.md`](./VERIFICATION.md).


---

### F-01 · Medium · *(downgraded from High by the adversarial pass — no actor, certain gain zero, not a code path. Urgency rank 1 retained.)* The manipulation-cost table that the listing filter, the band ceiling and TR-1's disposition all rest on overstates the cost of moving a listed pool by 8–25×, and on NVDA the figure is arithmetically unreachable

**Lanes and routes** `08-depth-measurement.md` (exact V3 tick-walk, every initialized tick within ±36% of
spot, `liquidityNet` per tick, validated by reconstructing `liquidity()` to 0.003–1.16%, block 68,632,038 /
2026-09-21 07:51:59 UTC). The coordinator reached the same conclusion by a second, model-free route (two
`balanceOf` calls). `04-economic.md`'s E-19 reached the neighbourhood by a third route (constant-active-L,
12.7 h apart) and **explicitly flagged a full tick-walk as the thing that would supersede its absolute
column** — it is superseded; E-19's liquidity-*change* observation is not.

**Location** `AUDIT.md:80-84` (the D30 table), `LISTING_CANDIDATES.md:29-50`,
`src/str/StrategyFactory.sol:265-268` (`setBandCeiling`'s own source comment: *"what a pin costs is that
pool's depth: NVDA takes $54M to walk 30%, AMD $309k"*), `AUDIT.md:290-296` (TR-1's break-even),
`AUDIT.md:429-437` (TR-1 dispositioned "answered by decision — deep pools only").

**Status** EXECUTED. Lane 08's tick-walk; and independently by me, `cast call`, block **68,651,755**,
2026-09-21, pool `0xd4EB21209C4D6093f80B5b84f5C45cc093EA14a3`:

```
token0 = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168  (USDG, 6 dec)
token1 = 0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC  (NVDA, 18 dec)
balanceOf(pool) token0 = 3,895,045.226740 USDG
balanceOf(pool) token1 = 9,789.740373699666 NVDA
tick = 222205  ->  spot ~ 224.0 USDG/NVDA  ->  NVDA side = ~$2,193,000
liquidity() = 1.2033722751e19   (matches lane 08's 1.2034e19 field-for-field)
```

> **Corrected after the adversarial pass — the argument first published here was wrong.** It read: *"you
> cannot buy more NVDA than the pool holds, the entire NVDA side is worth ~$2.19M, so $54M is unreachable —
> no model is needed, two balances and one multiplication."* That conflates the **spot value of the stock
> taken out** with the **USDG paid in**. Walking a pool up you pay rising prices, so the USDG in exceeds the
> spot value of the stock out: the adversary's exact walk pays **$2,118,250** against a stock side worth
> **$2,084,746**, exceeding the claimed "bound" by 1.6%. The valid model-free bound is
> `P(+30%) × inventory` = **1.3 × the stock side**, and every exact figure falls inside it.

To push spot up you buy NVDA out of the pool, and you cannot buy out more than it holds — so the cost is
bounded by `1.3 × the stock side`, which at 9,789.74 NVDA and ~$224.0 is **~$2.85M**. `AUDIT.md`'s **$54M**
is **19×** that valid bound and **24.6×** the inventory itself. It is not a loose estimate of the +30%
cost; it is unreachable. This corroborates lane 08's exact walk of $2.33M and the adversary's independent
walk of $2.12M.

**The check that needs no RPC call at all**, which the adversary found and which this finding should always
have led with: `data/listability.json` is **committed in this repository at `9a291aa`** and carries each
pool's TVL. Every D30 figure in `AUDIT.md` exceeds the **entire pool** it describes, both sides combined —
NVDA **8.7×**, AAPL **9.9×**, SPY **7.4×**, SPCX **5.1×**, GOOGL **3.1×**, META **2.7×**, AMD **1.2×**.

**In fairness to the author**, `AUDIT.md:83-86` states the model, states the assumption and states the
*direction* of the error: *"using the pool's current active-tick liquidity (assumes it extends across the
move; concentrated pools thin out away from price, so real cost is likely lower)."* The finding is
therefore not "the risk model is wrong in the unsafe direction" — it is that the project knew the number
was an overestimate, never bounded how large the overestimate was, and then used it as a hard input to
permanent decisions.

| ticker | `AUDIT.md` / `LISTING_CANDIDATES.md` (+30%) | constant-L today | **exact tick-walk (+30%)** | overstatement |
|---|---|---|---|---|
| NVDA | $54M | $24.6M | **$2.33M** | **23×** |
| AAPL | $5.9M | $3.50M | **$0.235M** | **25×** |
| SPCX | $13M | $10.4M | **$0.76M** | **17×** |
| SPY | $3.2M | $5.22M | **$0.201M** | **16×** |
| GOOGL | $3.9M | $3.81M | **$0.468M** | **8×** |

Why: constant-L demands more of the out-token than the pool physically holds. For NVDA +30% it wants
96,290 NVDA out; the pool holds 10,238 (lane 08's block). The exact walk converges on 98.7% of the stock
side without exceeding it, which is both the correct answer and the sanity check.

**Conditions**
1. The D30 table is the quantitative basis for TR-1's disposition, the `bandCeiling` ceiling and the
   first-wave listing set. — *status: explicit in all three places, cited above.*
2. A listing is permanent for every strategy launched against it (`StrategyTreasuryBase._oracle`,
   `PoolTrader.pool`, `StrategyTreasuryV4.stockKey` all immutable). — *status: confirmed.*
3. The exact figures are themselves a snapshot. — *status: **they must be re-read before anyone relies on
   them.** Active `L` on NVDA fell **−60.6%** in 12.3 h over 2026-09-20 → 21 with TVL essentially
   unchanged (lane 08; E-19 measured −59.5% over 12.7 h independently). A depth number without a read date
   is not a number.*
4. Arbitrage bleed over a 600 s hold. — ***UNMEASURED**, and it must stay so. Lane 08's round-trip column
   is the fee floor (`f/(1−f) × (leg1+leg2)`), not the cost of holding against arb flow, which was not
   sampled.*

**Mechanism** Not a code path. The project's own risk model is wrong by one to one and a half orders of
magnitude in the unsafe direction, and three permanent, unpatchable decisions are made with it.

**Impact** Loser: the **treasury** of every strategy launched against a pool certified by this filter, and
through it every holder. No attacker; the severity comes entirely from what rests on the number.
Certain gain: 0. Option gain: 0. Three concrete consequences:

1. `setBandCeiling`'s ceiling of 200 bps/h is justified in its own source comment by "NVDA takes $54M to
   walk 30%". The flagship listing's figure is 23× too high. See F-03.
2. TR-1 was dispositioned "answered by decision — deep pools only". The deep pools are not deep in the
   sense that decision assumed. TR-1's break-even, `treasury size traded > ~6.7 × pool fee × D30`, falls
   on NVDA from **~$181k to ~$7.8k**. That moves TR-1 from "only a large treasury is worth pinning" to
   "almost any treasury is". See F-03.
3. `LISTING_CANDIDATES.md`'s own ~$500k cutoff would **exclude AAPL** at the exact figure ($235k) while
   the constant-L figure ($5.9M) puts it comfortably inside. The first wave is mis-selected on the current
   number.

One thing the correction does **not** do: at ±0.5% and ±1% constant-L is **not a bound in either
direction** (0.53× to 1.35×), because none of these pools stays inside one tick range even for a 0.5%
move. So the small-move arithmetic elsewhere in this report (the sandwich table, F-34) is *not* off by
23×; only the +30% column is. Nothing in the repo's depth reasoning is conservative at the sizes the
deviation gate actually operates at, in either direction.

**Fix** Recompute the table with an exact tick-walk before the first `list()`; list on the **minimum**
across a full week including both weekend days, not on a snapshot; make `tools/listability.py` a hard
gate re-run immediately before each `list()` transaction (`LISTING_CANDIDATES.md:49` already asks for
this and the measured half-life justifies making it mandatory); publish a treasury-size cap per listing,
since TR-1's break-even is a function of treasury size against D30 and only one of those is under
anyone's control. No contract change, no byte cost.

**PoC** Not applicable — reproduce with `cast call <pool> "token1()(address)"` then
`cast call <token1> "balanceOf(address)(uint256)" <pool>` and compare to the table.

**Grading note, stated once.** A reader who insists severity must track an attacker's gain will read this
as Medium ("a disclosed risk whose disclosure materially understates it" — by 23×). I grade it High
because the rubric grades the launched state and this number is the sole quantitative basis for three
decisions that are permanent the moment the first strategy launches. The urgency ranking (§4) puts it
first either way.

---

### F-02 · Medium · *(downgraded from High by the adversarial pass — `docs/SECURITY.md:33` explicitly grants `setOverride(day, 2)` by name, one cited contradiction was a truncated sentence, and the `_book`/`stopLoss` mechanism is inert at the shipped `bandBpsPerHour == 0`.)* `setOverride(day, 2)` lets the Safe change the price the rule trades at, which `docs/SECURITY.md`'s "It cannot" column and the calendar's own file header both say it cannot

**Lanes and routes — four, independently.** `01-clean.md` C-01 reached it from the source comment with no
document access at all (EXECUTED). `03-checklist.md` CL-12 reached it from a pausability inventory
(EXECUTED). `02-historical.md` HX-2 reached it from the frozen-feed exploit class. The lead's L-7 reached
it from the `isScheduledClosure` predicate. That the context-free lane and the full-context lane both
landed on it tells you how reachable it is: it is one `onlyOwner` call with no timelock.

**Location** `src/TradingCalendar.sol:15-16` (the file header's claim), `:29` (`setOverride`),
`:130-135` (`dateClosed` honours mode 2), `:137-142` (the second, contradictory claim: *"The owner can
stop the rule trading, and cannot change what price it trades at"*), `:157-160` (`isScheduledClosure`),
`:163` (`isClosed`); `src/PriceOracle.sol:51` (the only calendar gate any trading path applies), `:42`
(`maxStockAge <= 48 hours`); `src/str/StrategyTreasury.sol:129-131`;
`src/str/StrategyTreasuryBase.sol:251`, `:290` (`pricedOffPoolOnly` guards `_book` and `stopLoss`);
`docs/SECURITY.md:31` ("It cannot … **change the price the rule trades at**, or open the closed-market
path") against `docs/SECURITY.md:32` ("It can … force a day **open** (`setOverride(day, 2)`)"), and the
section heading `docs/SECURITY.md:169` ("**The calendar owner can halt and only halt**").

**Status** EXECUTED — by two lanes independently, and the repo's own suite asserts it: the prior-rounds
lane ran `test_audit_calendarOwnerCanHaltOrReopenEveryLaunchedStrategy`, whose part (b)
(`test/AuditFactory.t.sol:209-217`) ends `assertTrue(ok, "the launched treasury trades on a Saturday at
Friday's close")`. C-01's own run, Saturday 2026-09-19 12:00 UTC:

```
isClosed            true  -> false     after setOverride(day, 2)
isScheduledClosure  true  -> false
isClosedByRule      true  -> true      (unchanged)
```

I re-read the source and both contradictory comments are present verbatim at the lines cited.

**Conditions**
1. The calendar owner calls `setOverride(d, 2)` for a genuine closure. — *status: reachable, `onlyOwner`,
   no timelock, no expiry, no bound on how many days, and only the owner can clear one. The Safe is
   **2-of-4** (chain read 2026-09-21), not the 2-of-3 `docs/DEPLOYMENT.md:99` claims.*
2. The stock feed's last round is inside `maxStockAge` (<= 48 h, `PriceOracle.sol:42`). — *status: holds
   for most of a weekend. Measured feed ages at block 68,632,038, 2026-09-21: NVDA 6.58 h, AAPL/GOOGL/SPY
   7.86 h, SPCX 3.87 h. A Friday-close print is inside 48 h until roughly Sunday afternoon.*
3. `oraclePaused()` false. — *status: **false on all 11 measured stock tokens**, 2026-09-21 (lane 08).*
4. The pool's spot (and on V3 its 600 s mean) within `maxDeviationBps` of the frozen feed. — *status:
   cheaper than any lane assumed. Two of five measured pools already sit past **half** the default
   `maxDeviationBps` of 50 bps against their own oracle — GOOGL **+0.330%**, SPY **+0.229%** (lane 08,
   2026-09-21) — and the fee floor for a ±1% shove-and-unwind is **$69–$717** at the exact depths. The
   cost of **holding** that for 600 s against arbitrage is **UNMEASURED**.*

**Mechanism** `TradingCalendar.sol:15-16` states *"an override can only ever stop trading, never widen
what trades: see `isScheduledClosure`"*. That is true of `isScheduledClosure` and false of `isClosed`,
which routes through `dateClosed` and returns `false` for mode 2. `PriceOracle.tryPrice` — the single gate
in front of every trading path — asks `isClosed`. So `setOverride(saturday, 2)` flips `tryPrice` from
"refuse" to "serve Friday's frozen close". Simultaneously `isScheduledClosure` goes false, so
`StrategyTreasury._feed()` refuses, `pricedOffPoolOnly()` returns false, and the two calls the band
machinery exists to keep off a pool-only price — `_book` (`:251`) and `stopLoss` (`:290`) — are
re-enabled during a closure. Without the override nothing trades at all, so the override strictly **adds**
tradeable states.

**Impact** Loser: the **treasury**, and through it every holder. The owner receives nothing, so
**certain gain to any actor: 0**. **Option gain:** bounded per fill by `maxSlippageBps` (<= 300 bps,
shipped 100) off the frozen print, times the lots the override makes reachable, and the frozen print's own
error over a weekend's news is the unbounded term — the repo measures the overnight tail at 589 bps on
CRCL (`StrategyTreasury.sol:52-53`). The realistic damage is a lot sold or bought in a thin weekend book
rather than a Monday one.

**Why High, against three lanes' Medium.** C-01 graded Medium and named the exact test that would flip it:
*"If `SECURITY.md` repeats the line at `TradingCalendar.sol:15-16`, this is High by the rubric as
written."* It does — `docs/SECURITY.md:31` and the heading at `:169`. HX-2 graded Medium "only because
line 33 of the same table discloses the mechanism" and explicitly flagged it for re-grading. CL-12 graded
Info by scoping itself to the comment and deferring the behaviour to FA-1. The rubric's third High clause
is mechanical — *the protocol Safe can do something `docs/SECURITY.md` explicitly promises it cannot* —
and its trigger is met. That an adjacent row discloses the mechanism is a mitigating fact that belongs in
the writeup, not in the grade; a promise contradicted one row later is still a promise made.

**Fix** Pick one and make code and docs agree.
(a) Drop mode 2: `function dateClosed(uint256 day) public view returns (bool) { return override_[day] == 1
|| dateClosedByRule(day); }` plus `require(mode <= 1, "mode")` in `setOverride`. Two lines in
`TradingCalendar`, **19,784 B of margin, no factory bytes**. This is what `docs/SECURITY.md:31` and `:169`
already claim, and it removes a permanent owner lever.
(b) Keep mode 2 and give `PriceOracle.tryPrice` a much tighter age bound on a forced-open day, so a
force-open cannot resurrect a print from the previous session. One immutable and one comparison in
`PriceOracle` (22,365 B spare).
Either way delete or scope the clause at `TradingCalendar.sol:15-16`, fix `docs/SECURITY.md:31` and the
`:169` heading, and note that `setOverride` has no bound on the number of days and no expiry.

**PoC** (C-01's, passing)
```solidity
function test_overrideMode2_opensAClosedWeekend() public {
    uint256 ts = 1789819200;                       // Sat 2026-09-19 12:00 UTC
    assertTrue(c.isClosed(ts));
    assertTrue(c.isScheduledClosure(ts));
    c.setOverride(c.tradingDate(ts), 2);
    assertFalse(c.isClosed(ts));                   // PriceOracle.tryPrice now serves
    assertFalse(c.isScheduledClosure(ts));         // and the band path is simultaneously off
    assertTrue(c.isClosedByRule(ts));
}
```

---

### F-03 · High (rubric cap: needs a >= 600 s TWAP hold) · `MAX_BAND_BPS_PER_HOUR = 200` is 20× the value at which the repo's own measurement says the band stops buying anything, and the ceiling was sized against a depth number 23× too high

**Lanes and routes** `04-economic.md` E-6 (EXECUTED, read straight out of the committed
`docs/band/crcl-usdg-14d.csv`); `08-depth-measurement.md` and my own chain read supply the cost side;
`06-prior-rounds.md` §2.4 establishes that the two gates are owner-settable and future-launches-only.
This is the finding F-01 re-grades.

**Location** `src/str/StrategyTreasuryBase.sol:102` (`MAX_BAND_BPS_PER_HOUR = 200`);
`src/str/StrategyFactory.sol:269-272` (`setBandCeiling`, `if (bps > 200) revert`) and its justifying
comment at `:265-268`; `src/str/StrategyTreasury.sol:46` (`MAX_BAND_BPS = 3000`), `:106-112`;
`src/str/StrategyFactory.sol:364` (the launch check, forcing 0 on V4).

**Status** EXECUTED for the uptime/reach table (committed CSV) and for the depth figures (tick-walk plus
my own `balanceOf` read). REASONED for the composition of the two.

**Conditions**
1. The owner raises `bandCeiling[stock]` above zero for some stock. — *status: **zero for every stock
   today**, default mapping, and `docs/SECURITY.md:192-195` says it stays zero until the Safe raises it.
   This is the gate that makes the finding inert right now.*
2. A creator then picks a band at or near the ceiling. — *status: **UNMEASURED**, but the incentive points
   that way: a higher band means the rule trades more, which markets better, and the creator bears none of
   the downside (F-37).*
3. A scheduled closure, and the attacker holds the V3 pool's 600 s mean off the frozen feed. — *status:
   the hold cost is **UNMEASURED**; the fee floor is now measured and is small (lane 08: NVDA ±3%
   round trip $1,574; AMD $200).*
4. CRCL's 14 days are representative of other pools. — *status: **UNMEASURED**. One pool, 14 days.*

**Mechanism / measurement** From `docs/band/crcl-usdg-14d.csv`:

| `bandBpsPerHour` | uptime, all hours | honest pull p99 | adversarial pull p99 | adv ÷ honest | worst fill vs feed p99 |
|---|---|---|---|---|---|
| 0 | 60.7% | 0 | 0 | — | — |
| **10** | **96.3%** | 272.7 bps | 742.2 bps | 2.7× | 842.2 bps |
| 25 | 96.3% | 272.7 | 1,855.4 | 6.8× | 1,955.4 |
| 50 / 100 | 96.3% | 272.7 | 2,950 (cap) | 10.8× | 3,050 |
| **200 (enforced ceiling)** | **96.3%** | 272.7 | 2,950 | **10.8×** | **3,050** |

Uptime is **identical** from 10 to 200. Adversarial reach grows 4× over the same span. `README.md:290`
already states the first half ("anything above 10 bought nothing more and only widened what a pinned pool
could reach") and the enforced ceiling is nonetheless 200.

**What F-01 adds, and why it moves the grade.** The ceiling's own source comment
(`StrategyFactory.sol:265-268`) justifies 200 with "NVDA takes $54M to walk 30%, AMD $309k". NVDA's exact
figure is $2.33M. TR-1's break-even — `treasury size traded > ~6.7 × pool fee × D30` — falls on NVDA from
**~$181k to ~$7,800**. The premise of the whole "deep pools only" disposition was that a pin is only worth
mounting against a large treasury. On the exact depths it is worth mounting against almost any treasury.

**Impact** Loser: the **treasury**, and through it every holder, on any lot the pin reaches. **Certain
gain to the pinner**: `AUDIT.md`'s own TR-1 measurement of +3,311 USDG on an AMD-sized pool for ~$218k
round-tripped — and that measurement was taken against the overstated depth, so it is a floor.
**Option gain: 0** — the pinner banks the spread on the fill. Per event: one pinned take-profit at band 10
costs the treasury 842 bps of fill-vs-feed against a 10% `tp1` gain — a single event wipes out most of a
full cycle; at the enforced ceiling it is 3,050 bps, which is three cycles.

**Why High.** Capped at High by the rubric's TWAP clause regardless. It clears the bar for High on
"needs favourable market conditions" (a closure) plus the two gating owner/creator actions, and the value
at risk per event is a multiple of the cycle it is supposed to earn. Both gating conditions are **not met
today**, which is why it is not the top of the urgency table — but both are one transaction away and
permanent for every launch after them.

**Fix** `MAX_BAND_BPS_PER_HOUR = 10` in `StrategyTreasuryBase` (a changed literal, **no byte cost**, and
it lands inside `TreasuryDeployer`'s 2,158 B either way) and `if (bps > 10) revert BadRequest();` in
`setBandCeiling` (a changed literal, **no net factory bytes**). If 10 is felt to be over-fitted to one
pool over 14 days, then set the ceiling from the same `tools/band_backtest.py` run `docs/SECURITY.md:196`
already requires per listing, and make the constant the largest band for which uptime is still rising on
that pool. Leaving it at 200 means the ceiling encodes no measurement at all. Separately: correct the
comment at `StrategyFactory.sol:265-268`, which is now the most load-bearing wrong number in `src/`.

**PoC** Not applicable — the finding is that a committed measurement and a committed constant disagree,
and that the constant's stated justification is off by 23×.

---

### F-04 · High · A treasury whose oracle stops permanently loses every asset it holds, forever, five days later

**Lanes and routes** `04-economic.md` E-1, **single source**. It ranks here on the strength of its call
path, which I enumerated myself against `9a291aa` rather than taking on trust.

**Location** `src/str/StrategyTreasuryBase.sol:97` (`MAX_SIZING_AGE = 5 days`), `:212` (`_notePrice`),
`:249` (`_book`), `:261-262` (`takeProfit`), `:291` (`stopLoss`), `:309` (`buyDip`), `:364-369`
(`buyback`'s fallback); `src/PriceOracle.sol:50-58`; `src/str/StrategyTreasury.sol:118-120`.

**Status** REASONED. I read every branch; no lane ran it.

**Conditions**
1. `PriceOracle.tryPrice()` returns false permanently. Four independent causes, none under the protocol's
   control: (a) the stock token's `oraclePaused()` stuck true — the issuer holds `BEACON_UPGRADER_ROLE` on
   one address with no timelock; (b) Chainlink retires the equity feed, so `updatedAt` ages past
   `maxStockAge` for good; (c) the stock is delisted or merged away; (d) the calendar owner sets
   `setOverride(day, 1)` indefinitely and then calls `renounceOwnership` (compare F-19, F-32). — *status:
   **UNMEASURED**. Chainlink retires feeds routinely; no base rate attempted. `oraclePaused()` is false on
   all 11 stock tokens today (lane 08, 2026-09-21).*
2. More than `MAX_SIZING_AGE = 5 days` since the last successful **rule action** — not since the last
   oracle print. — *status: automatic once (1) holds.*
3. The treasury holds anything. — *status: true for any strategy that has ever been swept.*

**Mechanism** Every value-moving entry point requires `health()`: `_book` (`:249`), `takeProfit` (`:261`),
`stopLoss` (`:291`), `buyDip` (`:309`). `buyback` is the sole exception and only for sizing: `:364-369`
tries the oracle, falls back to `lastGoodPrice`, and reverts `Unhealthy` once that is over five days old.
`lastGoodPrice` is written **only** by `_notePrice`, which is called only from the four gated functions —
so the cache ages from the last rule action, not from the last oracle print. There is no owner, no rescue,
no proxy, no timelocked escape, and no other token outflow: the only ones are the four bounty transfers,
the two swap settlements and `poolManager.take` back **into** the treasury.

The protocol has already reasoned correctly about this exact shape one contract over.
`StrategyHook._reconcile` (`:343-351`) exists precisely so an issuer burn cannot silently strand the
ledger. The treasury has no equivalent for the oracle dying, and the two failures have the same permanence.

**Impact** Loser: the **treasury**, i.e. every token holder (the entire forward burn stream) and every
creator who funded a seed through `LaunchRouter` (explicitly one-way). **Certain gain to any attacker: 0.
Option gain: 0.** Nobody profits. Magnitude: **100% of `bookedStock + buybackStock + reserveUsdg`,
permanently.**

**Why High, on a rubric written around an attacker.** The High tier reads "the same, but needs favourable
market conditions…", where "the same" is *permanently takes **or destroys** treasury funds*. Destruction
is the operative verb and it does not require the actor to profit. The stock issuer holds a unilateral,
permanent switch (`oraclePaused()`); they are a privileged third party but they are **not** the protocol
Safe, which is the only actor the rubric excludes. The Medium tier tops out at "a permanent brick of **one
non-essential** path"; this is a permanent brick of every path plus a total freeze of every asset.
`docs/SECURITY.md:52-68` discusses the issuer's pause, deny-list and `adminBurn` and states a paused token
"recovers fully when lifted" — it never states what a permanently-false `oraclePaused()` or a retired feed
does, which is total, unrecoverable loss.

**Fix** Cheap, and it does **not** touch `StrategyFactory`. `buyback` uses the stock oracle for exactly
two things: converting `buybackChunkUsdg` into a stock amount (`:370`) and the dust floor (`:380`).
Denominate the chunk in **stock** — `buybackChunkStock`, with a floor of
`min(buybackStock, buybackChunkStock / N)` — and `buyback` needs no stock oracle at all; its execution
price is already bounded by the token pool's own 600 s mean, which has nothing to do with Chainlink. The
burn path then survives any oracle failure, which is the path that matters most to holders. Cost: a struct
field swap plus two changed expressions in `StrategyTreasuryBase`, against **`TreasuryDeployer`'s 2,158 B**
and `TreasuryV4Deployer`'s 5,823 B — comfortable, but it must be sized against the deployer, not the
treasury. A second, larger fix (an escape hatch letting anyone sell the lots at the stock pool's own TWAP
after N days of oracle silence) is a design change, not a parameter, and is a pre-launch decision.

**PoC** (E-1's sketch, not run)
```solidity
function test_deadOracleFreezesTheTreasuryForever() public {
    _launchAndFund();
    vm.mockCall(address(stock), abi.encodeWithSignature("oraclePaused()"), abi.encode(true));
    vm.warp(block.timestamp + 6 days);
    vm.expectRevert(); treasury.takeProfit(0);
    vm.expectRevert(); treasury.buyDip();
    vm.expectRevert(); treasury.stopLoss(0);
    assertFalse(treasury.book());
    vm.expectRevert(StrategyTreasuryBase.Unhealthy.selector); treasury.buyback();
    vm.warp(block.timestamp + 3650 days);
    vm.expectRevert(StrategyTreasuryBase.Unhealthy.selector); treasury.buyback();
    assertGt(stock.balanceOf(address(treasury)) + usdg.balanceOf(address(treasury)), 0);
}
```

---

### F-05 · Medium · `_setDefaults` bounds eleven things and leaves eight unbounded; three of them are launchable honeypots or permanent bricks, frozen into every strategy launched afterwards

**Lanes and routes — five.** `01-clean.md` C-02 (`spikeSeconds`, EXECUTED) and C-03 (`protocolBps`,
EXECUTED end to end against a real `PoolManager`); `03-checklist.md` CL-1 (the full nine-value table,
EXECUTED); `00-lead-notes.md` L-1 as narrowed after its own retraction (EXECUTED, three fields);
`04-economic.md` E-5's `minTaxBps` half. Five routes into one validation block.

**Location** `src/str/StrategyFactory.sol:252-263` (`_setDefaults`, the whole block — I re-read it and the
checks are exactly `supply != 0`, `minTaxBps <= maxTaxBps`, `protocolBps + maxCreatorBps <= 1e4`,
`maxTaxBps <= 1500`, `spikeBps <= 9000`, `sweepTipBps <= 100`, `bountyBps <= 200`,
`0 < maxSlippageBps <= 300`, `0 < maxDeviationBps < maxSlippageBps`, `0 < maxBuybackImpactBps <= 1000`,
`minLotUsdg != 0`, `buybackChunkUsdg != 0`, `lpFee == 0`, `tickSpacing >= 1`);
reachable via `:251` and the constructor `:247`. Consequences at `src/str/StrategyHook.sol:126`
(the hook's own check, which also omits `spikeSeconds`), `:161-167` (`sellRateBps`), `:282-284`
(`toTreasury = rest - cut - mine`); `src/str/StrategyTreasuryBase.sol:250`, `:313`, `:322`, `:359`,
`:380`, `:456`.

**Status** EXECUTED (three lanes ran `setDefaults` with every value below and got no revert; C-03 ran a
full launch/buy/sell/sweep cycle).

**Conditions**
1. The factory owner sets one of these values, maliciously or by a units mistake. — *status: one
   `onlyOwner` call. The deploy script's own defaults are sane, but every one is `vm.envOr`-overridable
   and **11 of the 19 are never printed back** by the script (F-33) — including every value in this
   finding.*
2. A strategy launches while that default is live. — *status: `publicLaunch` ships false, but the owner
   may launch regardless (`:359`).*
3. Nobody notices before the launch. — *status: **partly closed, and this is what keeps it at Medium.**
   The creator mines the hook salt against `_hookArgs`, which embeds the defaults — see the retraction in
   §5.11 and the "safe" entry in §6. Committing is not reading, but it is a commitment. A token **buyer**
   commits to nothing and has no restatement guard at all; every value is a public getter on an immutable
   hook, so it is a disclosure question rather than a technical one.*

**Mechanism** The eight unbounded or zero-accepting fields, and what each does permanently:

| field | only check | consequence, frozen at launch |
|---|---|---|
| **`spikeSeconds`** (uint32) | **none, anywhere** — not in `_setDefaults`, not in `StrategyHook`'s constructor | `sellRateBps()` decays `spikeBps` linearly over this many seconds. At `spikeBps = 9000`, `spikeSeconds = type(uint32).max`: measured **9000 bps at launch, 8933 one year later, 8273 eleven years later**. A ~90% sell tax for 136 years. `docs/SECURITY.md:235` says the spike lasts "120 s, **and not a second longer**" — a statement about one default, not about the contract |
| **`buybackCooldown`** (uint32) | **none** | `buyback()` reverts `Cooldown` until `lastBuybackAt + cooldown`. At uint32 max, the only mechanism that returns value to holders fires once per 136 years |
| **`protocolBps`** | only the sum with `maxCreatorBps` (`> 1e4`, a strict `>`) | `protocolBps = 10000` with `maxCreatorBps = 0` passes here **and** the hook's identical check. `toTreasury = rest - cut - mine == 0`: the treasury of every strategy launched afterwards receives **exactly zero** of the sell tax, forever, while `README.md` promises "the remainder to the treasury". C-03 measured the mirror case at the other end — `protocolBps 1000 / creatorBps 9000` sent 13.068972202064220905 stock to the creator, 1.452108022451580100 to the protocol and **1 wei** to the treasury |
| `minLotUsdg` | `!= 0` | upper-unbounded. `_book` returns false, `buyDip`/`buyback` revert `NotDue`. USDG is 6 decimals; a 1e12 units error makes the rule inert forever while the treasury keeps collecting tax it can never book |
| `sweepTipBps` | `> 100` | `0` accepted. Nothing in `src/` calls `hook.sweep()` (grepped, zero callers); the tip is the **only** economic reason anyone moves the ERC-6909 claims out of the hook. At 0 the treasury's funding depends on altruism |
| `bountyBps` | `> 200` | `0` accepted. `book`/`takeProfit`/`stopLoss`/`buyDip`/`buyback` all become permissionless **and unpaid** |
| `minTaxBps` | `minTaxBps <= maxTaxBps` | `0` accepted. With `lpFee == 0` a round trip through the launch pool then costs **nothing**, and the protocol, creator and treasury receive nothing from flat-rate trading at all (E-5) |
| `tickSpacing` / `supply` | `>= 1` / `!= 0` | `tickSpacing` upper-unbounded to 32,767, fixing seed granularity forever; `supply = 1` accepted |

**Impact** Loser: the **token buyer**, in every row — they buy into a pool whose sell tax, treasury
funding and buy-back cadence were fixed by a third party before they arrived, with no exit other than
paying the tax. For `buybackCooldown`, `minLotUsdg`, `sweepTipBps` and `bountyBps` the loser is the
**treasury and every holder**.
**Certain gain to an attacker-owner: 0 for `spikeSeconds` alone** — a 90% sell tax is *split*, so a
malicious owner setting only that would be paying the creator and the treasury most of it. The dangerous
value is `protocolBps`, where the certain gain is **100% of the stock-side tax** that the docs promise
goes to the treasury, banked per sale. In composition with `maxCreatorBps` at the ceiling the creator
banks `creatorBps/1e4 × (1 − sweepTipBps/1e4)` of every sell-tax dollar for the life of the token — 90%
of the stock-side take in C-03's run. **Option gain: 0** — these are standing diversions, not price bets.

**Why Medium and not High.** It needs the Safe to misbehave, it reaches future launches only, every value
is a public getter, and the mined salt means the creator commits to the exact set. It is Medium under "a
disclosed risk whose disclosure materially understates it": `_setDefaults`'s own comment claims
*"Everything a launch hands to a constructor is checked HERE as well"*, and `StrategyHook.sol:43-46`
frames the spike as a short anti-dump measure timed in seconds. Both understate what the block accepts.

**This is not `AUDIT.md` FA-4.** FA-4 was about values that make the next launch **revert loudly**
(`sweepTipBps = 101`, `spikeBps > 9000`, `minLotUsdg = 0`, bad `tickSpacing`) and those four checks are
now present at `:257-261`. What survives is the complement: the values that let a launch **succeed** and
then behave wrongly forever. A loud revert is recoverable; this is not.

**Fix** Add to `_setDefaults`:
```solidity
if (d.spikeSeconds > 1 days || d.buybackCooldown > 7 days) revert BadRequest();
if (d.sweepTipBps == 0 || d.bountyBps == 0 || d.minTaxBps < 100) revert BadRequest();
if (d.protocolBps > 5000) revert BadRequest();
if (d.minLotUsdg > 1e12 || d.buybackChunkUsdg > 1e15 || d.tickSpacing > 200) revert BadRequest();
```
and mirror `spikeSeconds` in `StrategyHook`'s constructor at `:126` so the invariant survives a future
factory (free: `HookDeployer` has 8,147 B).
**Byte budget: this touches `StrategyFactory`'s 945 B, and the lanes disagree on the cost** — C-02
estimates ~40–70 B for a subset, CL-1 estimates ~250–400 B for the full block. Nobody measured it. That
disagreement decides whether F-06's and I-7's factory-side fixes also fit, so **the whole factory-side fix
set must be written and sized in one build before anything is committed** (§5.12). If it does not fit, the
cheapest subset by impact is `protocolBps`, `spikeSeconds`, `maxBuybackImpactBps` (F-06).

**PoC** (CL-1's, passing)
```solidity
function test_setDefaults_acceptsEveryKillSwitch() public {
    StrategyFactory.Defaults memory d = _d();
    d.spikeSeconds = uint32(3650 days); d.buybackCooldown = type(uint32).max;
    d.minLotUsdg = 1e30; d.sweepTipBps = 0; d.bountyBps = 0;
    d.maxBuybackImpactBps = 1; d.protocolBps = 10000; d.maxCreatorBps = 0;
    d.tickSpacing = 32767; d.supply = 1;
    vm.prank(owner); f.setDefaults(d);              // no revert
    assertEq(f.getDefaults().spikeSeconds, uint32(3650 days));
}
```

---

### F-06 · Medium · `maxBuybackImpactBps` below ~20 is accepted by all three validators and permanently bricks `buyback()` — the product's only value-return path

**Lanes and routes — three.** `01-clean.md` C-04 (EXECUTED: the acceptance, and the arithmetic against a
line-for-line replica of `_buybackLimitSqrtP`); `02-historical.md` HX-3; `03-checklist.md` CL-2. CL-2
alone got the floor right.

**Location** `src/str/StrategyTreasuryBase.sol:456` (`uint256 half = uint256(params.maxBuybackImpactBps) / 2`),
`:457`, `:466-467`, `:487-489` (`_clampToSpot`), `:380` (`buyback` turns a zero fill into `NotDue`);
accepted at `src/str/StrategyFactory.sol:259`, `src/str/StrategyTreasury.sol:37`,
`src/str/StrategyTreasuryV4.sol:68` — all three test `== 0 || > 1000`, **none requires `>= 2`**.

**Status** EXECUTED for the acceptance and the arithmetic; REASONED for the end-to-end brick.

**Conditions**
1. `maxBuybackImpactBps` is set to 1, 2 or 3. — *status: the deploy script's default is 300; nothing
   deployed. Any value below ~20 has the effect.*
2. A launch happens under it. — *status: ordinary.*
3. No path exists to change it afterwards. — *status: **confirmed** — `params` is written once in the
   constructor and the treasury has no owner.*

**Mechanism** `half = 1 / 2 = 0` in integer arithmetic, so `fromSpot == sqrtP` exactly and `fromMean` is
unadjusted. Whichever branch is taken, `_clampToSpot` returns `sqrtP - 1` or `sqrtP + 1` — a limit one wei
past spot, which fills nothing. `spent` is 0 or dust, and `:380` reverts `NotDue`. Every buy-back,
forever. `buybackStock` accrues dead and `totalBurned` stays at zero, so the product's one link between
treasury and token (`StrategyToken.sol:7-8`: "a shrinking supply is the only link between the two") never
fires. **CL-2's correction, which the other two lanes missed: the effective floor is ~20, not 2.** At
`maxBuybackImpactBps = 2` or `3`, `half = 1` — one basis point of *sqrt*, i.e. ~2 bps of price, inside one
tick at most spacings. The `== 0` check reads as if it establishes a floor; it establishes nothing.

**Impact** Loser: **every holder** of a strategy launched under that default, permanently. **Certain gain
0, option gain 0** — a self-inflicted brick, not a theft. Silent: the function reverts `NotDue`, which
reads like "no profit yet".

**Why Medium, against three lanes' Low.** The rubric's Medium clause is "a permanent brick of **one
non-essential** path". `buyback()` is the essential path — it is the only mechanism by which a holder ever
receives anything. Low is reserved for "dust-scale, or needs an implausible precondition"; a one-character
typo in a nineteen-field struct that the deploy script never prints back (F-33) is not implausible, and
the consequence is total for that strategy.

**Fix** `if (d.maxBuybackImpactBps < 20 || d.maxBuybackImpactBps > 1000) revert BadRequest();` at
`StrategyFactory.sol:259`, and the same in both treasury constructors. In the factory this **replaces** an
existing `== 0` comparison with a `< 20` comparison: **no net bytecode growth**, so the 945 B margin is
untouched. Better still, and it does not touch the factory at all: compute the limit as
`mulDiv(sqrtP, 2e4 ± maxBuybackImpactBps, 2e4)` at `:457`/`:467` so odd values cannot truncate to zero —
a few bytes against `TreasuryDeployer`'s 2,158 B.

**PoC** (C-04's arithmetic leg is passing; the end-to-end is HX-3's sketch)
```solidity
function test_impactCapOfOneBricksTheBuybackForever() public {
    StrategyTreasuryBase.Params memory p = _params(0);
    p.maxBuybackImpactBps = 1;                                  // accepted by every constructor
    treasury = _deploy(p); _wireAndEarnProfit();
    skip(7 days);                                               // drift cannot help: it multiplies half == 0
    vm.prank(bot); vm.expectRevert(StrategyTreasuryBase.NotDue.selector); treasury.buyback();
    assertEq(treasury.totalBurned(), 0, "nothing can ever be burned");
}
```

---

### F-07 · Medium · The sell spike is provably absent for exactly half of every cycle, by construction, and a seller chooses which half

**Lanes and routes** `00-lead-notes.md` L-12 (EXECUTED, minimal CREATE2-mined harness) and L-14
(EXECUTED, shove cost against a real V4 `PoolManager` at the repo's own defaults); `04-economic.md` E-4
reached the same window from the incentive side. Two routes, one of them measured twice.

**Location** `src/str/StrategyHook.sol:145-149` (`noteEvent`, the `2 * spikeSeconds` guard — I re-read it:
`if (block.timestamp < lastEventAt + 2 * spikeSeconds) return;`), `:161-167` (`sellRateBps`, which returns
`taxBps` once `dt >= spikeSeconds`); `src/str/StrategyTreasuryBase.sol:357-391` (`buyback`, permissionless,
pays `bountyBps` of the burn, calls `noteEvent()` last).

**Status** EXECUTED.

**Conditions**
1. `buyback()` is permissionless and the caller picks the moment. — *status: confirmed, `:357`.*
2. `buybackStock != 0` and the cooldown has elapsed. — *status: if `buybackStock == 0` no spike can arm at
   all and the seller is already safe, so the two branches cover every case.*
3. `noteEvent` refuses to re-arm inside `2 * spikeSeconds`. — *status: confirmed, and the guard was added
   for a good and independent reason, stated at `:140-144`: without it, a permissionless `buyback` with a
   cooldown shorter than the spike could pin a 90% sell tax on every holder forever.*

**Mechanism** Arm at T. With the repo's defaults (`spikeSeconds = 120`, `spikeBps = 9000`,
`taxBps = 1000`):

| window | `sellRateBps()` | a buy-back landing here is |
|---|---|---|
| T .. T+120 | 9000 decaying to 1000 | protected by the spike already running |
| **T+120 .. T+240** | **1000, flat** | **not protected at all** — `noteEvent` refuses to re-arm |
| T+240 | re-arms to 9000 | protected |

Measured: at T+60 the rate is 4500 and `lastEventAt` is unchanged; at T+120 and T+239 it is **1000** and
`lastEventAt` is still T; at T+240 it re-arms to 9000. The unprotected share is
`spikeSeconds / (2 × spikeSeconds)` = **50%**, independent of every parameter — confirmed at
`spikeSeconds` of 60, 600 and 86,400 — and the buy-back cooldown does not change it, only how many
buy-backs land in each half. **The two documented requirements are in direct conflict and the code
resolves it silently in favour of the second.**

Two uses follow. A seller who wants a clean exit calls `buyback()` themselves at T, waits `spikeSeconds`,
and sells at the flat rate — and is paid `bountyBps` of the burn for doing it. And inside
[T+120, T+240) the buy-back sandwich collapses into one transaction: buy, call `buyback()` (which does
*not* arm a spike), sell, paying only the flat tax on both legs with no price risk between them.

**What is actually protecting the buy-back** (L-14, EXECUTED, real V4 `PoolManager`, repo defaults): a
shove and its immediate unwind through a launch pool costs **18.99%** of notional at the flat rate
(matching `1 − 0.9 × 0.9`) and **90.99%** with the spike live. Against at most `maxBuybackImpactBps`
(factory ceiling 1000 bps, default 300) of payoff. So a round-trip shove does not pay at any impact cap
the factory permits, by roughly a factor of two even at the loosest. **The tax is the defence; the spike
and the anchor are not carrying the weight the documents attribute to them** (see also §6 on L-9).

**The case that arithmetic does not cover, and it is the finding.** An existing holder who was going to
sell anyway pays the sell leg regardless of when. Their *marginal* cost of timing that sale into a
buy-back is **zero**; the marginal gain is the buy-back's own price impact. They choose the moment
themselves — there is no race to win.

**Impact** Loser: the **treasury**, and through it every holder, as fewer tokens burned per chunk; and
every uninformed seller, relatively. **Certain gain** to the informed seller: up to `maxBuybackImpactBps`
of one `buybackChunkUsdg`, once per `buybackCooldown`, for as long as `buybackStock` lasts — at the
factory defaults (`300` bps, `500e6`) that is **<= 15 USDG per buy-back**, scaling linearly in both at the
permitted maximum. Plus, on the exit side, the difference between paying `taxBps` and paying up to
`spikeBps`: on a $10,000 exit at `taxBps = 1000`, $1,000 rather than up to $9,000. **Option gain: 0.**

**Why Medium.** Small absolute numbers at the defaults, so not High. Medium under the disclosure clause:
`README.md:45`, `docs/SECURITY.md:219-220` and the hook's own header (`StrategyHook.sol:43,46` — "It
exists so that a buy-back cannot simply be dumped into", "whoever snipes the opening block cannot simply
dump it") all present the spike as a defence, and half the time at the seller's election it is not one.

**UNMEASURED** Whether the buy-back's impact on a genuinely single-sided *seeded* pool is larger than on
the two-sided pool L-14's harness used. It probably is, which makes the payoff bigger, not smaller. That
measurement needs a real seeded launch pool and is the first thing the next round should run.

**Fix** None preserves both properties cleanly — this is the price of a guard that closes a worse hole.
Three candidates, none touching the factory: re-arm on every buy-back but cap the *rate* rather than the
frequency; make the re-arm bound `spikeSeconds` rather than `2 × spikeSeconds` and accept a permanently
armed but always-decaying spike; or require `buybackCooldown >= 2 * spikeSeconds` at construction so
consecutive buy-backs cannot land in the unprotected half. The third is one comparison in the treasury
constructors (**`TreasuryDeployer`'s 2,158 B**) and changes no live behaviour — but note it makes the
shipped defaults (cooldown 60, `spikeSeconds` 120) illegal, which is itself the finding. **The honest
minimum is to stop describing the spike as an anti-dump mechanism** and describe it as a 120-second
friction on sellers who do not watch the chain.

---

### F-08 · Medium · The treasury has no `_reconcile`; an issuer `adminBurn` permanently blocks all further booking and permanently overstates the published scorecard

**Lanes** `04-economic.md` E-10, **single source**. Verified by me against `9a291aa`.

**Location** `src/str/StrategyTreasuryBase.sol:195-197` (`unbookedStock`, which floors at 0), `:120`
(`bookedStock`), `:205-210` (`stockEquivalentHeld`, which reads the **ledger**, not the balance);
contrast `src/str/StrategyHook.sol:343-351` (`_reconcile`, which exists for exactly this event).

**Status** REASONED. I read `unbookedStock` — `return b > held ? b - held : 0;` — and confirmed
`stockEquivalentHeld` returns `bookedStock + buybackStock + _ruleStockFor(reserveUsdg(), p)`.

**Conditions**
1. The stock issuer calls `adminBurn(treasury, X)`. — *status: the power exists and
   `docs/SECURITY.md:56-58` says it "ignores both the pause and the deny-list… nothing here can detect
   one". Probability **UNMEASURED**.*
2. `X` exceeds the treasury's unbooked balance. — *status: automatic for any meaningful burn.*

**Mechanism** After the burn, `balanceOf(treasury) < bookedStock + buybackStock`, so `unbookedStock()`
returns 0 — **no further sell tax can ever be booked** until the balance has climbed back past the
phantom. Every unit of tax arriving meanwhile silently backfills a hole nobody is told about, with no
event. `stockEquivalentHeld()` keeps reporting the pre-burn `bookedStock`, so the scorecard the README
tells buyers to read overstates the treasury by exactly the burned amount, forever.

The hook's own docstring at `:265-269` spells out why this shape is unacceptable there — "the loss lands
on the recipients whose money it was, not on the treasury, which would otherwise be starved until new tax
had refilled their debt". The identical failure exists in the treasury and is not defended.

**Impact** Loser: the **treasury** and every holder; separately, anyone reading the scorecard.
**Certain gain 0, option gain 0** — the issuer is not an attacker here. Magnitude: the burn, plus all
subsequent tax up to the burn, plus a permanently wrong public metric. Test-suite note: the mock token
models no `adminBurn` at all, so nothing in 620 tests reaches this state (F-15, lane 05 §7).

**Fix** The mirror of the hook's `_reconcile`, in `_book`: if
`_stock.balanceOf(address(this)) < bookedStock + buybackStock`, write both down pro rata and emit.
Roughly ten lines in `StrategyTreasuryBase`; **budget is `TreasuryDeployer`'s 2,158 B**, which it fits.
It also fixes `stockEquivalentHeld`, which is the number a buyer is told to judge the product by.

**PoC** — E-10's, not run. `_launchAndBook`, `vm.prank(issuer) stock.adminBurn(treasury, X)`, send new
tax, then `assertEq(treasury.unbookedStock(), 0)`, `assertFalse(treasury.book())`,
`assertEq(treasury.bookedStock(), bookedBefore)`, `assertGt(held, stock.balanceOf(treasury))`.

---

### F-09 · Medium · `book()` is unpaid, unbounded in time and unbounded in size: it fixes every lot's permanent cost basis, and a single oversized lot is permanently unsellable

Two mechanisms with one root — the only function in the rule nobody is paid to get right.

**Lanes and routes** `06-prior-rounds.md` §3.3 (the **cost-basis** half, EXECUTED PoC) and
`04-economic.md` E-3 (the **size** half, code path REASONED, depth table COMPUTED). Neither lane saw the
other's half. E-3's depth table is built on `AUDIT.md`'s D30, which F-01 supersedes — **the correction
makes E-3 worse by 8–25×, not better**, and that re-grade is mine.

**Location** `src/str/StrategyTreasuryBase.sol:244-258` (`book`/`_book` — no bounty transfer anywhere in
it), `:246-247` (`uint256 un = unbookedStock()` — the whole balance becomes **one** `Lot`), `:263` (the
only automatic trigger, inside `takeProfit`), `:266-272` (a lot sells whole, or exactly in half when
`tp2 != 0` — there is no third granularity), `:294` (`stopLoss` against `L.cost`), `:234` and
`src/str/StrategyTreasury.sol:136-138` (`requireFull = !buy`), `src/PoolTrader.sol:138`
(`if (requireFull && spent != amountIn) revert PartialFill`); the bounties it lacks are at `:281`,
`:302`, `:323`, `:385`.

**Status** EXECUTED for the cost-basis half; REASONED + COMPUTED for the size half.

**Conditions**
1. `book()` pays no bounty while every other rule function does. — *status: **confirmed**, I re-read
   `_book` and there is no transfer.*
2. `takeProfit` cannot substitute, because `_book()` at `:263` runs before `lots[id]` and the `NotDue`
   revert at `:267`/`:270` undoes it. — *status: confirmed.*
3. Tax stock sits unbooked. — *status: the normal, default state.*
4. For the loss half, `stopBps != 0`. — *status: **off by default**, creator's choice, and the repo's own
   backtest argues against it (a stop lowers the full-run multiple from 0.55 to 0.39). **UNMEASURED**
   what creators will pick — `0` in the deploy script's `_req` shape, `2000` in the repo's own harness.*
5. A lot exists whose principal exceeds the pool's depth inside `maxSlippageBps`. — *status: the
   threshold is below, and it is 8–25× lower than E-3 stated.*

**Mechanism (a) — the caller picks the permanent number.** Nobody is paid to book promptly, so the tax
accrues until someone volunteers, and whoever calls chooses which healthy Chainlink print becomes the
lot's permanent cost — anywhere in the range the feed visits in between. No manipulation is required; the
price is honest. The only *automatic* booking is `_book()` inside `takeProfit`, which by construction runs
at a price that just cleared a take-profit trigger — a local high. So the default behaviour of an
unattended strategy is to cost new lots at highs. A high basis is what arms `stopLoss`, and the caller who
books high and then stops it is paid `bountyBps` of the **whole** proceeds (F-13). EXECUTED: the same 100
stock, the same treasury on the audited Chainlink-only path, booked an hour apart on honest feeds,
produces `cost = 100e18` or `cost = 130e18`.

**Mechanism (b) — one lot, and `requireFull`.** `_book` books the entire unbooked balance as a single
`Lot`. `takeProfit` then sells `principal = q·cost/p` in one swap with `requireFull = true`; if the whole
principal cannot fill inside `oracle·(1 − maxSlippageBps)`, the call reverts and **there is no way to sell
a smaller slice**. Largest sellable principal, **re-based on F-01's exact walk** (2026-09-21) rather than
on `AUDIT.md`'s D30:

| pool | `AUDIT.md` D30 | **exact D30** | E-3's stated largest sellable lot | **corrected** |
|---|---|---|---|---|
| NVDA 0.05% | $54.0M | **$2.33M** | ~$1.0–1.9M | **~$43–83k** |
| AAPL 0.05% | $5.9M | **$0.235M** | ~$105–210k | **~$4.2–8.4k** |
| GOOGL 0.05% | $3.9M | **$0.468M** | ~$69–139k | **~$8.3–16.7k** |

*(scaled by the same D30 ratio E-3 used; the ±1% scaling is itself only good to 0.53–1.35× per lane 08, so
treat these as an order of magnitude, not a threshold. **UNMEASURED**: the exact D(0.5%)/D(1%) walk.)*

**Impact** Loser: the **treasury**, and through it every holder. Two distinct costs.
*Certain, no attacker*: a treasury on a mid-cap pool whose tax accumulates unbooked for a few months
produces one lot it can never sell — on the corrected depths that threshold is tens of thousands of
dollars on the **flagship** listing, not one to two million. Plus the cost-basis half, which is a
permanent number chosen by whoever showed up.
*Cheap grief, with leverage*: donating stock to the treasury is a plain `transfer` and is permissionless.
An attacker who sees `unbookedStock()` just under the threshold donates the marginal difference and calls
`book()`; they freeze the whole pile. **Certain gain to the attacker: negative** (they burn their own
stock). **Option gain: 0.** Leverage = existing unbooked ÷ marginal donation, unbounded in principle. It
is spite with leverage, which is why this is Medium and not High.

**Relationship to `AUDIT.md` TR-2.** TR-2 ("a pinned price becomes a permanent cost basis", Low) was
framed around the word *pinned* and round 3 fixed exactly that (`:253`, `if (pricedOffPoolOnly()) return
false`). Neither half above needs a pin, a band, a closure or any manipulation. The generalisation — *any
permissionless writer of a permanent number picks it* — was never stated.

**Fix** Three, none in `StrategyFactory`, all against **`TreasuryDeployer`'s 2,158 B**:
(a) cap what `_book` takes at once —
`uint256 un = Math.min(unbookedStock(), _ruleStockFor(maxLotUsdg, p));` — so the tax becomes several lots;
(b) pay `book()` a bounty out of the booked stock, like every other function;
(c) cost a lot at the price at which the tax *arrived* rather than at which someone noticed — the hook
knows that moment. Optionally let `takeProfit` sell a caller-specified fraction with a floor at
`minLotUsdg`, which also rescues lots already booked oversized. All are pre-launch decisions: none reaches
a launched treasury.

**PoC** (E-3's size half, not run)
```solidity
function test_oversizedLotIsPermanentlyUnsellable() public {
    _launch();                                            // AMD-calibrated V3 pool
    vm.prank(attacker); stock.transfer(address(treasury), 500_000e18);
    assertTrue(treasury.book());                          // ONE lot, principal >> D(1%)
    _movePriceTo(cost * 115 / 100);                       // well past tp1
    vm.expectRevert();  treasury.takeProfit(0);           // PartialFill
    assertEq(treasury.lotCount(), 1);                     // and there is no smaller-slice path
}
```

---

### F-10 · Medium · `lastSalePrice` is one global scalar shared by every lot, so USDG raised by selling one lot is redeployed at a rung set by a different lot's sale

**Lanes** `04-economic.md` E-7, **single source**. Verified by me: it is one `uint256` at `:122`.

**Location** `src/str/StrategyTreasuryBase.sol:122` (one slot for the whole treasury), `:283`
(`takeProfit` overwrites it), `:303` (`stopLoss`), `:325` (`buyDip`), `:311` (the only reader).

**Status** REASONED, with arithmetic.

**Conditions**
1. More than one lot exists. — *status: automatic — each `book()` and each `buyDip` pushes one.*
2. Lots sell at different prices. — *status: automatic in any trending market.*
3. `dipBps` is smaller than the gap between the two sales. — *status: `dipBps >= 2·(maxSlippageBps +
   poolFeeBps)` = 260 bps at the 0.30% tier, so any move larger than the dip qualifies.*

**Mechanism** `buyDip` re-enters at `p <= lastSalePrice · (1 − dipBps)`. The USDG raised by selling lot A
at 110 is re-deployed at a rung set by lot B's sale at 150:

| A sold at | B sold at | `dipBps` | reserve A redeployed at | vs A's own sale |
|---|---|---|---|---|
| 110 | 130 | 10% | 117.0 | **+6.4%** |
| 110 | 150 | 10% | 135.0 | **+22.7%** |
| 110 | 200 | 10% | 180.0 | **+63.6%** |

**Impact** Loser: the **treasury**, mechanically, on every cycle in a rising market. This is not market
risk — it is a bookkeeping choice. **Certain gain to any attacker: 0. Option gain: 0.** Magnitude: the gap
between the highest recent sale and the sale that raised the reserve, times the reserve. In a market where
lots sell at a ladder of rising prices, every rung of reserve is deployed at the top of the ladder minus
`dipBps`. The docstring at `:54` describes the rule per lot ("then, for each lot on its own"), and
`buyDip` is the one part that is not.

**Fix** Store the sale price **on the reserve**: a small FIFO of `(usdgAmount, salePrice)` entries, and
have `buyDip` spend only entries whose own sale price is at least `dipBps` above `p`. If that is too much
storage, the cheap version is `lastSalePrice = min(lastSalePrice, p)` on `takeProfit` when a reserve
balance already exists, so a later higher sale cannot raise the rung for money raised earlier. Budget:
**`TreasuryDeployer`'s 2,158 B**; the cheap version is a few bytes, the FIFO is not and should be sized
before it is written.

---

### F-11 · Medium · The front page's single performance figure is a hand-built favourable unit test, while the repo's own multi-year replay of the shipped rule returns 0.37–0.60 on the three stocks queued to launch first — and the front page neither says so nor links it

**Lanes and routes** `04-economic.md` E-2 (EXECUTED, every number recomputed from the committed CSVs);
`00-lead-notes.md` L-18 (a narrowing challenge to E-2's wording). I verified both readings myself.

**Location** `README.md:306-317` ("Reading the scorecard"); `docs/rule-backtest/README.md:10-13, 33-45`;
`docs/rule-backtest/all-stocks.csv`, `deep-pools.csv`; the scorecard itself at
`src/str/StrategyTreasuryBase.sol:136-146, 205-210`.

**Status** EXECUTED. I read `README.md:306-317` and `docs/rule-backtest/README.md:33-45` directly, and ran
`grep -n "rule-backtest" README.md` → **no match**.

**Conditions**
1. The backtest's forward column is the real price history. — *status: yes; `--reverse` is the synthetic
   control (see F-12).*
2. The three first-wave tickers are NVDA, AAPL, GOOGL. — *status: stated, `AUDIT.md:459-467` and
   `LISTING_CANDIDATES.md:29-40`. Note F-01: AAPL would fall outside the project's own cutoff on the
   exact depth figures.*
3. A buyer reads the front page. — *status: it is the repository's front page and the launch narrative.*

**Mechanism / measurement** What `README.md` actually says: *"The premise is **beat holding the
stock**"*; the formula `(stockEquivalentHeld() + totalStockSpentOnBuybacks) / totalStockReceived`; *"**1.0
means the rule did nothing a sleepwalker would not have done**"*; and exactly one number — *"Measured on a
sell-high-rebuy-lower round trip in the unit suite: **1.0278**"*.

What `docs/rule-backtest/README.md` says about the **same shipped default rule**: forwards, 2015–26 as one
run, **0.37 / 0.54 / 0.60** for NVDA / AAPL / GOOGL, worst-year 0.57 / 0.78 / 0.73 — and in its own words,
*"the shipped 5% rule is the worst row on every ticker in every up year"*.

E-2's wider recomputation, which stands: over the 25 `listable` rows of `all-stocks.csv`, median `d55_up`
**0.8872**, only **3 of 25** above 1.0; across all 252 rows of `deep-pools.csv`, **0/252** clear 1.0 on
every forward-time statistic. The only column that clears 1.0 is the reversed path, which is a
deterministic negation of the same single sample (F-12).

**Where the lead is right, and I adopt it.** E-2's headline says the front page "still advertises the
opposite". That overstates. `docs/rule-backtest/README.md` is candid to the point of arguing against its
own product: it discloses that every ticker in the sample rose, replays each path backwards to control for
it, ranks rules by their worst window rather than their best, and calls the optimiser's own answer
("barely trade") what it is. Nothing is concealed. **The finding is about *where* the two numbers sit, not
about concealment** — and the concrete, checkable fact is that `README.md` contains no link or mention of
the backtest at all; the only pointer is one row of a table in `docs/README.md:45`.

Also worth recording, because it inverts a natural prior: E-2 tested whether the security filter and the
economic filter point in opposite directions and found **they do not** — corr(log10 D30, `d55_up`) =
**+0.487** over the 25 listable rows. Deeper pools score better. But corr(log10 D30, `d55_burn`) =
**−0.612**: the deep pools give away less because the rule *does* less, and they burn less for the same
reason.

**Impact** Loser: the **token buyer** who reads the front page and not the subdirectory. No attacker;
**certain gain 0, option gain 0**. Medium under the disclosure clause: the front page defines 1.0 as the
neutral point, gives one number above it from a unit test, and the product's whole framing rests on it.

In fairness, the backtest README's own defence at `:22-24` is correct and E-2 verified it: `d55_burn` on
the 25 listable rows has median 0.306, and NVDA/AAPL/GOOGL 0.364/0.293/0.266 — a third of the tax does
reach holders as burns even where the multiple is 0.79. **But that is a different claim from the one the
front page makes**, and the two sit in the same repository contradicting each other.

**Fix** Documentation, no byte cost. Either restate the premise as "convert sell tax into burns" and drop
"beat holding the stock" and the 1.0-is-neutral framing; or put the `all-stocks.csv` per-ticker forward
multiple on the launch page next to each strategy, which is what `README.md:288-291` already says a buyer
should judge a launch by for the band. Two sentences and a link is the minimum.

**PoC** Not applicable — a measurement, reproduced from committed data.

---

### F-12 · Medium · The backtest has no out-of-sample split, its "backwards" control is a deterministic negation of the single sample, its ranking metric silently drops the worst column, and the `health()` gate is not modelled at all

**Lanes** `04-economic.md` E-18, **single source**, EXECUTED — recomputed from the committed CSVs and the
committed generator.

**Location** `docs/rule-backtest/README.md`, `tools/rule_backtest.py`, `docs/rule-backtest/*.csv`.

**Status** EXECUTED.

**Conditions** 1. Anyone uses the backtest to choose parameters or to believe the premise. — *status: it
is the stated basis for the rule defaults and for F-11's framing.*

**Mechanism** The five classic errors, each with its status:

- **Single directional window — present, and disclosed.** All 11 of `eleven-stocks.csv` rose; 163 of 192
  in `all-stocks.csv` rose. **The mitigation is weaker than the document treats it as**: `--reverse`
  (`tools/rule_backtest.py:87`) sets `r'_i = −r_{n−i}`, so the backwards path is perfectly
  anti-correlated with the only sample, not a second one — confirmed in the data (`ann_vol_up ==
  ann_vol_dn` on every row, `path_x_dn == 1/path_x_up`). It also **negates skew**: equity returns are
  negatively skewed, the reversed series positively, and a sell-into-strength / buy-the-dip rule is
  structurally flattered by positive skew. That is the source of the headline at `:14`. It also reverses
  prices while keeping the original timestamps, so the daily-booking boundary lands on the wrong bars.
- **Survivorship — present structurally, undisclosed.** The universe is the tokens Robinhood Chain lists
  **today** (`tools/_registry.py:10-15`). Names delisted or bankrupt 2023–2026 cannot appear. Losers were
  *not* filtered on performance (29 of 192 have `px < 1`), and two names are dropped by hand.
- **In-sample selection — present, and the ranking metric hides the worst column.**
  `score = min(min, h_fwd, h_rev)` exactly (0 mismatches in 252 rows) and **silently excludes `d_all`**,
  the 2015–26 single run, which is the worst number for every rule. For the shipped rule `d_all = 0.3733`
  against `score = 0.5712`. The longest, most realistic window is dropped from the ranking.
- **Wrong frequency / unreachable prices — the largest unmodelled gap.** The backtest evaluates at the
  close and fires on **100% of bars**. The `health()` gate is not modelled at all. The repo itself
  quantifies the error: `docs/band/crcl-usdg-14d.csv` at `bandBpsPerHour = 0` — the only band a
  first-wave launch can have — gives `open_all_pct = 60.7`, and GME's 0.5% gate is open **42%** of the
  cash session. **Real availability 42–90% against a modelled 100%**, and the gate shuts precisely when
  the pool has run away from the feed, i.e. during the moves that generate the triggers.
- **Costs — charged, but at a tenth of the real bound.** One lumped `--cost-bps`, default 35; the deep
  pools were run at **10 bps per swap** while the same document states the real per-swap floor is
  `maxSlippage + pool fee` = 105 bps. `minLotUsdg` is not modelled, so the backtest executes dips the
  contract would refuse. Quantified: 10 → 105 bps moves NVDA's multiple by ≈ **0.010**. **None of this
  changes a sign**, and E-18 says so plainly — the 0.37/0.54/0.60 result is a trend effect, not a cost
  effect.

Two structural problems beyond the five. **The tax is not modelled**: the generator books a constant
`inflow / p` at the first bar of each calendar day — a deterministic $100/day DCA — where real funding is
`taxBps` on sell volume, which is heavily autocorrelated and **positively correlated with drawdowns**. No
sensitivity test on inflow exists in any CSV. And **one load-bearing claim does not reconcile**:
`docs/rule-backtest/README.md:37-40` reports "share of tax that became buy-backs" as 36/37/42% for the
shipped rule rising to 91/73/75% at tp 60/120 — the entire argument at `:42-45` for widening the
take-profit — while the only burn statistic in `deep-pools.csv` moves **the opposite way**: 0.0907
(shipped) → 0.0508 (30/60) → **0.0000** (60/120). They are different statistics, but the README's figures
appear in **no committed file**, so a reader cannot check the claim the recommendation rests on.

**Provenance.** `tools/rule_backtest.py`'s output schema matches **none** of the three CSVs' headers;
`all-stocks.csv` and `deep-pools.csv` come from scripts not in the repo, and no price history is committed
(`docs/OPERATIONS.md:188` says so deliberately). **Nothing can be re-run end to end.**

**Impact** Loser: anyone relying on the backtest to choose parameters or believe the premise. **Certain
gain 0, option gain 0.** Medium under the disclosure clause. Note the methodology errors **do not rescue
F-11**: every one of them flatters the rule, and the rule still loses.

**Fix** (a) Split 2015–2020 / 2021–2026 and report out-of-sample; (b) include `d_all` in `score` or say
why not; (c) replay with the `health()` availability the repo has already measured; (d) commit the two
missing generators and the burn-share figures, or delete the table at `:37-40`. No byte cost.

---

### F-13 · Medium · The `stopLoss` and `buyDip` bounties are paid on principal while `takeProfit`'s is paid on profit, so a caller is paid ~10× more for realising a loss than a gain, out of the treasury's principal

**Lanes** `04-economic.md` E-8, **single source**; the same asymmetry is noted in passing by
`02-historical.md` HX-4 and `01-clean.md` C-09 without being graded. Verified by me — I read all three
bounty expressions.

**Location** `src/str/StrategyTreasuryBase.sol:281` (`bounty = profit * bountyBps / 1e4`), `:302`
(`bounty = got * bountyBps / 1e4` — the **whole proceeds**), `:323`
(`bounty = spent * bountyBps / 1e4` — the **whole spend**), `:101` (`MAX_BOUNTY_BPS = 200`).

**Status** COMPUTED.

**Conditions**
1. `stopBps != 0`. — *status: **off by default**; a creator must opt in, and the repo's own backtest says
   they should not (a stop lowers the full-run multiple from 0.55 to 0.39).*
2. A stop fires. — *status: automatic once configured and the price falls.*
3. `buyDip`'s principal base applies regardless of `stopBps`. — *status: `buyDip` is the normal path.*

**Mechanism / measurement** Per unit of lot value, at `bountyBps = 50`:

| call | base | tip | ratio to `takeProfit` at `tp1 = 10%` |
|---|---|---|---|
| `takeProfit`, tp1 = 2.6% (the constructor floor) | profit | 1.27 bps | 0.28× |
| `takeProfit`, tp1 = 10% | profit | 4.55 bps | 1.0× |
| **`stopLoss`, stop = 5%** | **whole proceeds** | **47.50 bps** | **10.4×** |
| `stopLoss`, stop = 20% | whole proceeds | 40.00 bps | 8.8× |

At `MAX_BOUNTY_BPS = 200` the stop tip is **190 bps of the lot's whole value**, paid out of USDG
principal. `buyDip` has the same principal base, so a stop→dip→stop→dip cycle in a falling market pays
2 × `bountyBps` of the reserve per cycle (2% at the ceiling) on top of 2 × (`maxSlippageBps` + pool fee)
= 2.6% of execution cost, and **burns nothing** — `stopLoss` sends everything to the reserve, with no
`buybackStock` write. Compounding with F-09: the caller who books a lot at a high and then stops it out is
paid on the whole proceeds of a lot they made stoppable.

**Impact** Loser: the **treasury's principal**. **Certain gain** to a caller running both sides: 2% of the
reserve per full cycle at the ceiling, 0.5% at the shipped value — on a $100k reserve at the shipped
`bountyBps = 50`, $1,000/cycle in tips plus $2,600 in execution, against zero burns. **Option gain: 0.**

The comment at `:299-301` justifies the stop bounty ("the only loss-limiting function in the rule was also
the only one nobody was paid to call") and that reasoning is right. What is not right is the **base**:
`MAX_BOUNTY_BPS = 200` is sensible for a tip on **profit** and roughly 10× too high for a tip on
**principal**.

**Fix** Give the principal-based tips their own, much lower ceiling —
`MAX_PRINCIPAL_BOUNTY_BPS = 20` applied at `:302` and `:323`, leaving `MAX_BOUNTY_BPS = 200` for the
profit-based tips at `:281` and `:385`. One constant and two multiplications in `StrategyTreasuryBase`;
**budget `TreasuryDeployer`'s 2,158 B**, a comfortable fit. (Paying the stop out of "shortfall avoided" is
the conceptually right answer and is hard to define; do not attempt it in immutable code.)

**PoC** Not applicable — the two bases are at `:281` and `:302`; the table is arithmetic.

---

### F-14 · Medium · The test suite's pass/fail set is a function of the checkout's absolute path. Four checkouts produced four different results on three different tests

**This is the item three lanes each saw one shard of.** Stating the actual finding.

**Lanes and routes — four, and they disagreed only because each ran in its own directory.**
`00-lead-notes.md` L-16 (EXECUTED, two byte-identical checkouts, `test_router_tokenIsCurrency0_V3venue`
PASS in one and `revert("no nonce")` in the other, three runs each with identical gas — and the lead
diagnosed the root cause correctly). `06-prior-rounds.md` §3.7 (EXECUTED, its own scratch tree, a
**different** test red: `test_seedRangeIsSingleSided_tokenIsCurrency0`, `revert("no ordering")`).
`05-tests.md` §1a (EXECUTED, the same test as the lead, and it independently *proved* the metadata
mechanism by copying the tree with `lib` symlinked and diffing `MockToken`'s creation code: identical but
for the trailing CBOR bytes, and green in that tree). And **me**, in a fifth directory, with a fourth
result on a **third** test.

**Location** `foundry.toml` (no `bytecode_hash` key, so solc's default `ipfs` applies);
`src/str/StrategyFactory.sol:310-313` (`predictToken` hashes `type(StrategyToken).creationCode`);
`test/AuditRouterRound4.t.sol:83-90` (`_qOrdered`, brute-forces nonces 0..199, `revert("no nonce")`);
`test/InteractFactory.t.sol:855-862` (`_reqWithOrdering`, brute-forces 200 symbols,
`revert("no ordering")`); `test/LaunchRouter.t.sol:56-67`
(`test_theFirstBuyPaysExactlyWhatAStrangersBuyPays`).

**Status** EXECUTED — by three lanes and by me. My run, 2026-09-21, forge 1.8.1, scratch copy at
`…/scratchpad/triage-scratch` (`src`, `test`, `script`, `data`, `foundry.toml` copied, `lib` symlinked):

```
forge test --no-match-path 'test/*Fork*'
  -> 619 passed, 1 FAILED, 1 skipped
[FAIL: the router's buy is priced differently from anyone else's:
       149989578354309148954288246 != 149989578354309148954288251]
  test_theFirstBuyPaysExactlyWhatAStrangersBuyPays()   test/LaunchRouter.t.sol:56
```

Then, changing nothing but adding `bytecode_hash = "none"` and `cbor_metadata = false` to
`[profile.default]`:

```
forge test --no-match-path 'test/*Fork*'
  -> 620 passed, 0 failed, 1 skipped
```

**The fix is confirmed, by me, in the directory that was red.**

**Conditions**
1. `foundry.toml` sets no `bytecode_hash`. — *status: confirmed; I read the file.*
2. solc's default `ipfs` metadata hash is a function of the source file **paths**. — *status: confirmed by
   the tests lane's byte diff and by my result flipping on that one setting.*
3. Any test whose outcome depends on a CREATE2 address. — *status: at least three, in three files.*

**Mechanism** `predictToken` hashes `type(StrategyToken).creationCode`, whose trailing CBOR metadata
carries a hash of the source paths. So every CREATE2 address the tests predict moves with the checkout
directory. Two of the three affected tests then brute-force a search over that address space and revert
with a string when they miss.

**What the lanes did not have, and it widens the class.** My failure is **not** a brute-force search.
`test_theFirstBuyPaysExactlyWhatAStrangersBuyPays` launches "FAIR" and "FAIR2" and asserts their buy
outputs are **exactly equal** — and the two tokens' addresses are effectively random draws that determine
`tokenIs0` and therefore the seed's tick rounding. It is off by **5 wei**. So the class is not "the two
brute-force search helpers"; it is "every test whose outcome depends on a predicted CREATE2 address",
which includes exact-equality assertions nobody flagged. The lead's fix suggestion (raise the search
bounds, assert rather than `revert`) is right and insufficient on its own; `bytecode_hash = "none"` is the
one that closes the class.

**Impact** Loser: the **team**, and through them every future holder, because this is the CI that gates
contracts that can never be patched. **Certain gain 0, option gain 0.** Three reasons it matters more than
a flaky test:
1. `CLAUDE.md` in the sibling repository records that assuming one token ordering "has been shipped
   twice". The both-orderings tests are the coverage for that class and are exactly the ones that resolve
   by address lottery. A draw that *found* a different subset would silently reduce coverage instead of
   failing loudly.
2. CI is green at CI's path, so this is invisible to the team and lands on whoever clones the repo
   somewhere else. A contributor's first experience is a red suite they did not break, which trains people
   to ignore it. (CI also pins `FOUNDRY_VERSION: v1.5.0` and reports `StrategyFactory` at 23,329 B against
   this machine's 23,631 — the toolchains genuinely differ, which compounds it.)
3. The same missing setting makes the **deployed bytecode unreproducible**: anyone verifying the contracts
   from a fresh clone at their own path gets a trailing-bytes mismatch. For a protocol whose pitch is
   "immutable, verify it yourself", that is worth fixing on its own.

**Fix** One line, no contract change, no bytes anywhere: add `bytecode_hash = "none"` and
`cbor_metadata = false` to `[profile.default]` in `foundry.toml`. **Verified green by me.** Independently,
the two search loops should assert they found something rather than reverting with a string, raise their
bounds, and derive the ordering deterministically (mine the stock mock's address, as `_mineToken` already
does) rather than searching the token's; and `test_theFirstBuyPaysExactlyWhatAStrangersBuyPays` should
pin both orderings explicitly rather than hoping two draws agree to the wei.

---

### F-15 · Medium · Treasury arithmetic is not covered: 12 of 24 one-line mutations survive a green 620-test run

**Lanes** `05-tests.md` §2.0, **single source**, EXECUTED (mutation harness in its own scratch tree; the
repo was never modified).

**Location** the assertions, not the source. Principally `test/InteractRuleMev.t.sol:259` and `:1007`,
`test/InteractVenueParity.t.sol:401-402`, `test/AuditTreasury.t.sol:444`,
`test/AuditLedgerRound4.t.sol:287`, `test/AuditOwnerRound4.t.sol:569`,
`test/StrategyTreasuryV4Unit.t.sol:188`, `test/Emergency.t.sol:209,218`.

**Status** EXECUTED.

**Conditions** 1. Anyone treats a green run as evidence about the treasury. — *status: BASELINE does, and
CI does.*

**Mechanism** The suite's *shape* is unusually good — a real v4-core `PoolManager` everywhere, both
currency orderings as separate suites, a differential V3-vs-V4 harness with a one-wei negative control, an
adversarial front-run suite that nails `_shrink` exactly. The *assertions* are the weak point: 236 are
directional (`assertGt(x, 0)` / `assertGe` / `assertApproxEq`) where the exact integer is derivable from
constants the test already holds.

The contrast is the evidence. Short-changing the treasury's cut by **one wei** in the hook
(`StrategyHook.sol:284`) turns **66 tests red**, with exact derived expectations. Short-changing
`buybackStock` by **one wei** on every `takeProfit` (`StrategyTreasuryBase.sol:282`) leaves **all 620
green**, because the only conservation check the treasury suite has is
`assertGe(balance, booked + buyback)` — an inequality in the one direction the bug moves.

**The 12 survivors** — green with the bug in place: `buybackStock += profit - bounty - 1`; the
`takeProfit` caller bounty **doubled**; `totalStockSpentOnBuybacks += 0`; `totalBurned += burned / 2`;
`q = (L.qty + 1) / 2`; the buy-back drift clamp 9000 → 9500; the `MAX_SIZING_AGE` boundary off by one
second; the **token-side sweep tip doubled**; the oracle's `answer <= 0` guard **deleted**; the oracle
staleness boundary off by one second; `maxStockAge <= 48 hours` → `96 hours`; and the `TwapRing`
negative-mean rounding correction **deleted**. Also `if (oldest.ts > target)` loosened to `> target + 1`,
and `setOverride`'s `mode <= 2` loosened to `mode <= 3`.

The pattern is stark: **the hook's ledger and the two bounties someone thought to compute exactly are
protected; everything expressed as `assertGt(x, 0)` is not.** Same quantity, same contract: three of four
bounties asserted exactly and killed their mutants, the fourth left directional and its mutant silently
doubles the payment.

**Impact** Loser: the **team**, and every future holder, because this is the gate in front of unpatchable
code. **Certain gain 0, option gain 0.** Medium: a green run is evidence about the hook and the router and
**no evidence at all** about treasury arithmetic, the oracle's round-sanity guards, or the TWAP ring, and
nothing in the green tick says which half you are looking at.

**Fix**, in the order the lane gives, which I endorse:
1. Turn the six Group-A `assertGe` conservation checks into `assertEq` with a harness-tracked donation
   total. One change; kills two survivors and closes the exact bug class
   `StrategyTreasuryBase.sol:42-48` was written to prevent.
2. Assert the `takeProfit` bounty exactly (`StrategyTreasuryV4Unit.t.sol:188` and three fork siblings).
3. Drive `PriceOracle._read`'s other three clauses and its `catch` arms — the mock already has `setAt`;
   nothing calls it with 0, a negative answer or a future timestamp.
4. Add a `TwapRing` wrap test (>1024 observations) and a negative-mean rounding test; both mutants
   survived, and the wrap is the scenario the library exists for.
5. Make `invariant_callSummary` actually report (`afterInvariant` + `emit log_named_uint`) and **assert**
   the counters — `takeovers` reads **0** today, so the three `acceptCreator` branches the handler is
   written to validate are never reached and the suite is green anyway.
6. Raise `InteractRuleMevInvariantTest` from `runs = 12`, and add an invariant that catches a permanently
   reverting entry point — the `try/catch` + `fail-on-revert = false` combination currently forgives one
   (`reverts: 0` is guaranteed by construction and means nothing).
7. Replace the 29 bare `vm.expectRevert()` with selectors, starting with the nine whose own comment names
   the error. Seven declared errors have **zero** selector assertions
   (`PoolTrader.Slippage`, `PoolTrader.ShortObservationRing`, `StrategyTreasuryV4.Slippage`,
   `StrategyHook.HookNotImplemented`, `WrongPool`, `NotSeeder`, `PriceOracle.Unhealthy`); four of the
   seven have no test that reaches the path at all.
8. Give the calendar mocks a forced-OPEN mode so `StrategyTreasury.sol:129-130` can be driven with
   override mode 2 on a real weekend — **which is F-02's path, and it is currently untestable by
   construction.**

---

## The Low tier

Each is real and permanent. They are written more briefly than the tiers above; every one carries its
lanes, its status, its conditions, its loser, its gain split and its fix budget.

### F-16 · Low · `_shrink`'s swap-and-pop makes a caller-supplied lot index unstable: `takeProfit(id)` can execute on a lot the caller never chose, and an out-of-range `id` panics rather than reverting by name

**Lanes — four, and two of them reached opposite-sounding verdicts that are both correct.**
`01-clean.md` C-09 (REASONED), `03-checklist.md` CL-5 (REASONED, from the events angle),
`00-lead-notes.md` L-2 (**EXECUTED**, two reproductions against a real V4 `PoolManager`),
`02-historical.md` item 28 (which concluded "this is the flagged area, and it is safe").

**The resolution, precisely.** The historical lane is right that **nothing can be stolen and no undue lot
can be sold**: the eligibility test reads `lots[id]` *after* every mutation in the call — `_book()` first
(`:263`, which only pushes), then `Lot storage L = lots[id]` (`:264`), then the threshold at `:267`/`:270`,
and `stopLoss` the same at `:293-294`. A shifted index either reverts or sells a lot that genuinely
qualifies. The lead is right that **a caller's transaction can act on a lot they never chose**, at a
different cost basis, with the bounty paid on that lot's profit — and that an index that has gone out of
range fails as **panic 0x32**, not as a named error. Both statements are true of the same code; they are
answers to different questions ("can value be taken?" — no; "is `id` a stable identifier?" — no).

**Location** `src/str/StrategyTreasuryBase.sol:347-351` (`_shrink`: `lots[id] = lots[lots.length - 1];
lots.pop();`), called from `takeProfit` `:273` and `stopLoss` `:296`; consumers `:260`, `:288`, the
`lots(uint256)` auto-getter, `lotCount()` `:193`; `LotBooked` at `:161`.

**Status** EXECUTED (L-2, `test/ZZLeadLots.t.sol`, green 2026-09-21):
`test_lead_aClosedLotTurnsSomeoneElsesIndexIntoAnOutOfBoundsPanic` — three lots, another caller closes lot
0 in two `takeProfit` calls, a pending `takeProfit(2)` reverts **panic 0x32**.
`test_lead_anIndexCanSilentlyBecomeADifferentLot` — lot 0 at cost 100e18, lot 1 at cost 90e18; after lot 0
closes, `lots(0)` is asserted to be the **90-cost** lot, and a pending `takeProfit(0)` then succeeds on it
and is paid a bounty.

**Conditions** 1. Two rule calls land in the same block or back-to-back. — *status: bounties make racing
the expected behaviour, not an edge case, and F-13 makes the racing incentive strongest exactly where the
index churn is.* 2. The lot popped into slot `id` is itself due. — *status: required, and it bounds the
impact.*

**Impact** Loser: **the caller** (gas on a revert, and a bounty expected on a different lot) and the
**integrator** (an indexer keying lots by the `id` in `LotBooked` shows the wrong cost basis from that
block on, with no event to correct it; the only correct approach is to poll `lots(i)` for all
`i < lotCount()` after every `ProfitTaken`/`Stopped`). **No treasury loss. Certain gain 0, option gain 0.**

**Fix** Take `(qty, cost)` as additional arguments and require them to match, or key lots by a monotonic
id in a mapping instead of an array; at minimum `emit LotMoved(from, to)` inside the `if` at `:349` and a
length check with a named error. Budget: **`TreasuryDeployer`'s 2,158 B** — one event is ~60 B, the
argument check is small, the mapping rewrite is not and must be sized before it is written.

### F-17 · Low · Launch squatting: `_salt` does not bind `msg.sender`, so one launch fee permanently burns a pending `(symbol, creator, nonce)` — and the copier chooses the rule and the tax of the token bearing the victim's name

**Lanes** `01-clean.md` C-05, `02-historical.md` HX-5. **Not new** — acknowledged in-code at
`LaunchRouter.sol:60-63` and as R4-2. What **is** new is the second half of the sentence.

**Location** `src/str/StrategyFactory.sol:308` (`_salt = keccak256(abi.encode(q.symbol, q.creator,
q.nonce))` — no `msg.sender`), `:363` (`q.creator` validated only as non-zero), `:392`
(`new StrategyToken{salt: _salt(q)}` — CREATE2 to an occupied address reverts), `:394`;
`src/str/LaunchRouter.sol:64` (`if (q.creator != msg.sender) revert NotYourLaunch()`, which closes the
router path only).

**Status** REASONED (both lanes).

**Conditions** 1. `publicLaunch == true`. — *status: **false on a fresh factory** (`:206`), and the deploy
script leaves it off deliberately.* 2. The victim's request is visible. — *status: it must be — a front
end calls `predict` and mines ~16k hashes before submitting, and the request is then in the mempool.*
3. The attacker pays one launch fee. — *status: 25 USDG at the script's default; `FeeCurrency.None` is a
legal setting.*

**Mechanism** The attacker copies `(symbol, creator, nonce)`, mines their own hook salt for whatever
`stock`, `taxBps <= maxTaxBps`, `creatorBps <= maxCreatorBps` and rule they like — **none of those is in
`_salt`** — and lands first. The victim's `launch` then reverts for that nonce, permanently. Recovery is
`nonce + 1` **plus a full re-mine**, because `_hookArgs` includes the token address, which includes the
nonce.

**Impact** Loser: the **creator** (re-mining and a squatted symbol) and the **protocol** (a junk strategy
in `strategies[]` that nobody can remove). **Certain gain to the attacker: 0** — `creatorBps` pays the
*victim's* address, and the repo's own `test_R4_2_aCopyThroughTheFactoryBuysTheCopierNothing` asserts the
copier holds zero tokens. **Option gain: brand capture** — buyers who bookmarked the announced address buy
the attacker's rule and pay the attacker's tax. The in-code comment ("that only costs the copier a launch
fee for a strategy that pays the victim") does not say the copier also chooses the rule and the tax.

**Fix** `if (q.creator != msg.sender && msg.sender != owner()) revert BadRequest();` in `launch` — one
comparison, ~30 B against the factory's **945 B**, and it makes `LaunchRouter`'s guard redundant rather
than load-bearing. It removes the "launch on behalf of a creator" feature; if that feature is wanted, bind
`msg.sender` into `_salt` instead and make `predict` take the launcher (a front-end change, a few more
bytes). What the regression test is missing is the assertion that **the victim's own subsequent launch
reverts** — HX-5 supplies it.

### F-18 · Low · `PriceOracle` caps `maxStockAge` at 48 h and leaves `maxUsdgAge` unbounded, and the USDG leg — the denominator of every price — was measured 16.26 hours old

**Lanes — four.** `01-clean.md` C-14, `03-checklist.md` CL-11, `00-lead-notes.md` L-4,
`08-depth-measurement.md` (the measured age).

**Location** `src/PriceOracle.sol:42` — I read it: `require(maxStockAge_ != 0 && maxStockAge_ <= 48 hours
&& maxUsdgAge_ != 0, "age");` — used at `:54` (`tryPrice`) and `:68` (`lastPriceAt`, which deliberately
drops the calendar and stock-age gates and keeps **only** the USDG age check).
`src/str/StrategyFactory.sol:280`/`:298`: `list`/`listV4` check only `IOracleStock(oracle).stock() ==
stock` — not the ages, not the calendar, not that it is even a `PriceOracle`.

**Status** REASONED for the asymmetry; **EXECUTED** for the age — lane 08, block 68,632,038, 2026-09-21:
**USDG feed 16.26 h old**, against stock feeds at 3.87–7.86 h.

**Conditions** 1. An oracle is deployed with a large `maxUsdgAge`. — *status: raised materially by the
fact that **the deploy script does not deploy oracles at all** (an explicit manual step), so every
`PriceOracle` on this chain will be hand-constructed, one per stock, with no script and no guard.*
2. The USDG feed goes stale and drifts. — *status: the 16.26 h gap is **measured and is the normal state**;
the drift of a dollar stablecoin over that window is **UNMEASURED** and is presumably small.*

**Mechanism** `tryPrice` computes `p = s · _num / (u · _den)`. The stock leg is age-gated to 48 h with the
reason in the source ("72h would serve Friday's close at Sunday's open"). The USDG leg gets the same
`_read` with an operator-chosen ceiling and no cap. A seconds-vs-hours typo produces an oracle that
accepts a USDG price from any point in the past, permanently, in a contract with no setter — and `:68`'s
comment ("the dollar leg never gets to be stale") is exactly what the band path leans on.

**Impact** Loser: the **treasury**, trading against a stale denominator. **Certain gain to an attacker: 0**
directly; it needs the feed to be both stale *and* drifted, and the result is bounded by
`maxDeviationBps` against the pool. **Option gain 0.** Low, and permanent per oracle.

**Fix** `require(maxUsdgAge_ != 0 && maxUsdgAge_ <= 24 hours, "age")` in the constructor — ~20 B against
`PriceOracle`'s 22,365 B. And in `StrategyFactory.list`, compare `PriceOracle(oracle).calendar()` against
a factory immutable: ~40 B plus one immutable slot against the **945 B** margin — this is the one fix I
would measure before promising. It also belongs in the runbook: `docs/DEPLOYMENT.md` should state both
ages for every oracle the operator hand-deploys.

### F-19 · Low · `renounceOwnership()` is one call and permanently kills `setProtocol` / `proposeCreator` / `acceptCreator` on *every* hook ever launched

**Lanes** `01-clean.md` C-10; `AUDIT.md` FA-10 records the factory half. **Not new.**

**Location** `src/str/StrategyFactory.sol:119` (`is Ownable2Step`); `src/TradingCalendar.sol:22` (same);
`src/str/StrategyHook.sol:395` (`owner()` reads `IOwned(seeder).owner()` **live**), `:397-441`,
`:299-302`; `lib/openzeppelin-contracts/contracts/access/Ownable.sol:76-78` — `renounceOwnership` is
public, one step, and `Ownable2Step` does **not** override it.

**Status** REASONED. **Conditions** 1. The owner calls it. — *status: a plausible "decentralise the
launchpad" action, and nothing in the code warns against it.* 2. A `protocol` or `creator` address later
becomes unpayable. — *status: the hook's own comments treat this as live, which is why `claim(to)` exists.*

**Impact** Loser: the **protocol** (its own accrued cut, stuck) and any **creator who needs the role
reassigned** (accruing forever). **Certain gain 0, option gain 0.** Two compounding notes: with
`publicLaunch == false` a renounced factory can never launch again (FA-10); and a renounced **calendar**
means `setOverride` is dead — which kills F-02's lever and also the only patch mechanism for a calendar
bug (F-32). Those two remedies are in direct conflict.

**Fix** Override `renounceOwnership()` to revert in `StrategyFactory` and in `TradingCalendar`. Three
lines, ~20 B against **945 B**; free in the calendar (19,784 B).

### F-20 · Low · The dip lot's cost basis excludes the bounty the treasury just paid, so "a lot is never sold below its own cost" is false by up to `bountyBps` of principal on every dip lot

**Lanes** `02-historical.md` HX-4, **single source**. Verified by me at `:315-327`.

**Location** `src/str/StrategyTreasuryBase.sol:315` (`_swapStock(true, spend - spend*bountyBps/1e4, p)`),
`:323` (`bounty = spent * params.bountyBps / 1e4`), `:324`
(`lots.push(Lot(got, Math.mulDiv(spent, _SCALE, got), false))`), `:327` (the transfer). The claim it
breaks: `:55`. Related: `:73`'s comment describing every bounty as paid "out of what the call produced" —
true of `takeProfit`, false of `buyDip` and `stopLoss` (F-13).

**Status** REASONED. **Conditions** 1. `bountyBps != 0` — *status: shipped 50.* 2. A `buyDip` fires —
*status: the normal path.* 3. Frozen at birth — *status: yes, `Params` is constructor-only.*

**Mechanism** The treasury's total USDG outflow for `got` stock is `spent + bounty`; the lot is booked at
`spent / got`. Every later decision about that lot — `takeProfit`'s threshold, `stopLoss`'s threshold, and
`principal = mulDiv(q, cost, p)` — uses the understated basis, so `profit` is overstated by the bounty's
share, `buybackStock` is credited stock the treasury did not earn, and the **second** bounty is computed
on that overstated profit.

**Impact** Loser: the **treasury**, recurring, on every dip/take-profit cycle. **Certain leak**:
`bountyBps` of each dip's principal, mis-booked as profit — 0.1% of the reserve per dip rung at the
shipped 50 bps on a 20%-of-reserve lot. **Option leak**: the constructor's economic floor
(`tp1Bps >= 2·(maxSlippageBps + poolFeeBps)`) does not include `bountyBps`, so `bountyBps = 200` with
`maxSlippageBps = 1` and a 1 bp pool gives `tp1 >= 4` bps against 200 bps of round-trip bounty — a
configuration that realises a loss on every "profitable" lot. **UNMEASURED** whether anyone would set it.
No attacker gain beyond the intended keeper payment: the bug is the accounting, not the payment.

**Fix** Hoist `bounty` above the push and book at `Math.mulDiv(spent + bounty, _SCALE, got)`. Two lines;
**`TreasuryDeployer`'s 2,158 B**, trivially. Separately include `bountyBps` in the `tp1Bps`/`dipBps`
floors in both treasury constructors, and correct the `Params` comment at `:73`.

### F-21 · Low · Unchecked `uint160` downcasts in `_buybackLimitSqrtP` / `_clampToSpot` turn "fills nothing" into a hard revert once the token pool climbs into the top ~1,000 ticks

**Lanes** `01-clean.md` C-07, **single source**, EXECUTED.

**Location** `src/str/StrategyTreasuryBase.sol:457` (`fromSpot`, computed in `uint256`), `:466-467`
(`fromMean`), `:474` (`return uint160(fromSpot)`), `:487-489` (`_clampToSpot` returns `uint160(lim)`).

**Status** EXECUTED — at tick 886,500: `sqrtP` 1.4061e48, `lim` 1.4764e48 (**> uint160 max** 1.46150e48),
clamped to 1.4916e46, which is **below** `sqrtP`. A limit below spot on a `!zeroForOne` swap makes
`v4-core`'s `Pool.swap` revert `PriceLimitAlreadyExceeded`, so `buyback()` **reverts** instead of
returning `NotDue`, and every subsequent call reverts identically.

**Conditions** 1. `sqrtPriceX96 > type(uint160).max × 1e4 / (1e4 + half)` — for
`maxBuybackImpactBps = 1000` that is tick ≈ **886,297**, 975 ticks below `MAX_TICK`. — *status: requires
essentially the entire seeded supply to have been bought; implausible, but reachable in principle because
`_seedRange` runs the range to `maxUsableTick`.* 2. `stockIsCurrency0InTokenPool == false`. — *status:
50/50 on address ordering.*

**Impact** Loser: **holders** of a token that has appreciated by ~e^88 from its opening price — which is
to say essentially nobody. **Certain gain 0, option gain 0.** Reported because the contract is unpatchable
and because the same unchecked-cast shape appears three times in one function.

**Fix** Clamp before the cast inside `_clampToSpot`: `uint256 cap = uint256(TickMath.MAX_SQRT_PRICE) - 1;
if (lim > cap) lim = cap;` and the symmetric `MIN_SQRT_PRICE + 1` floor. ~40 B against
**`TreasuryDeployer`'s 2,158 B**.

### F-22 · Low · `TwapRing.write` uses checked `uint32` subtraction, so the 2106 wraparound reverts `afterSwap` and permanently bricks every strategy pool

**Lanes** `01-clean.md` C-08, **single source**. Verified by me: `int56(uint56(nowTs - last.ts))` at
`:52` is a checked `uint32` subtraction, and `meanTick` has the guard (`:66-67`) that `write` lacks.

**Location** `src/str/TwapRing.sol:45`, `:52`, `:64`, `:66-67`; the only caller,
`src/str/StrategyHook.sol:182-185`, inside `afterSwap`.

**Status** REASONED. **Conditions** 1. `block.timestamp >= 2^32` (2106-02-07). — *status: certain, 80
years out.* 2. The pool still has in-range liquidity then. — *status: implausible but not impossible.*

**Impact** Loser: **every holder**, in 2106. At the wrap, `nowTs` is small and `last.ts` near `2^32`, so
the subtraction underflows and reverts. That revert propagates out of `afterSwap` and out of
`PoolManager.swap`, so **every swap in the pool fails forever** — the pool is bricked, not merely
un-priced, and the seeded liquidity is equally unreachable because nothing can remove it. **Certain gain
0, option gain 0.** Low by horizon; noted because the rubric grades the launched, unpatchable state and
because the fix is one branch `meanTick` already has.

**Fix** In `write`, mirror `meanTick`'s guard: `if (nowTs < last.ts) { r.obs[r.index].tick = tick;
return; }` — or make the subtraction `unchecked` and accept V3's own wraparound semantics. Zero to 15
bytes in a library; it lands in `StrategyHook` → **`HookDeployer`'s 8,147 B**.

### F-23 · Low · `BoundDeployer.bind()` is permissionless, so a stranger can grief every deployment attempt indefinitely

**Lanes — three.** `01-clean.md` C-06, `03-checklist.md` CL-10 (**EXECUTED**), `00-lead-notes.md` L-6.
**Not new** — `AUDIT.md` FA-7 lists "a loud bind race". What the lanes add is the **repeatability**, which
FA-7 does not discuss.

**Location** `src/str/StrategyFactory.sol:53-56` (`bind()`, no access control — I read it),
`:238`, `:244-246` (the factory binds all three from its own constructor);
`script/DeployStrategyLaunchpad.s.sol:196-202` (four separate `new`s inside one `broadcast`, which
`forge script` submits as four transactions).

**Status** EXECUTED (CL-10, passing: `td.bind()` from `0xBAD`, then `new StrategyFactory(...)` reverts
`AlreadyBound`).

**Conditions** 1. The deployers land in transactions earlier than the factory. — *status: the natural
`forge script` shape does exactly this, confirmed at `:196-202`.* 2. Mempool visibility on chain 4663. —
***UNMEASURED**; the chain makes a block every 0.1 s, so the window is short but non-zero.*

**Impact** Loser: the **team**, for the gas of three redeploys per attempt, repeatable. **No user funds,
ever. Certain gain 0, option gain 0.** The in-code comment anticipates the revert and correctly calls it
"loud"; the liveness half is not discussed anywhere.

**Fix** Deploy the three deployers and the factory from a single helper contract's constructor, so no
block boundary exists between them — or give `bind()` a deployer-set expected factory. Neither touches the
factory's 945 B. At minimum the runbook must say so.

### F-24 · Low · `TradeRouter.buy` refunds an unabsorbed V4 hop in the **stock**, to a caller who paid in USDG, and `minTokensOut` does not cover it

**Lanes** `01-clean.md` C-11; `06-prior-rounds.md` Part 4 reaches the same asymmetry while grading round 5
and calls it "deliberate and undocumented". **Not new** in substance.

**Location** `src/str/TradeRouter.sol:67-76` (`buy` passes `refundTo = msg.sender`), `:147-148`
(`if (owedIn < amountIn) IERC20(tokenIn).safeTransfer(refundTo, amountIn - owedIn)` — I read it), `:74`
(`minTokensOut` checked against `tokensOut` only); contrast `:116-117`, where the V3 hop is deliberately
all-or-nothing (`if (spent != amountIn) revert PartialFill(spent)`, the T5-1 fix).

**Status** REASONED. **Conditions** 1. The V4 hop fills short. — *status: the pool opens single-sided with
the whole supply in one range, so a short fill needs the range exhausted; implausible early, reachable
late.* 2. The caller does not want stock. — *status: definitional for a USDG-in router.*

**Impact** Loser: **the caller**, left holding an unwanted asset to sell at their own slippage.
**Certain gain to anyone 0, option gain 0.** The contract is now inconsistent between its two hops. On
`sell` the same design has a sharper edge that round 5 acknowledged: `stockGot` is produced by the V4 hop
and must then be absorbed whole by the chosen V3 tier, so a thin tier makes `sell` unusable rather than
lossy.

**Fix** Mirror the V3 hop — `if (owedIn != amountIn) revert PartialFill(owedIn);` — or route the residue
back through the V3 pool into USDG. `TradeRouter` is unregistered periphery with 18,908 B spare: the
cheapest fix in the system, deploy another. **But the old one stays live forever and cannot be paused**,
and users with standing allowances keep it reachable.

### F-25 · Low · `buyback()`'s five-day sizing fallback can carry a price the *pool* set, not one Chainlink signed

**Lanes** `01-clean.md` C-12, **single source**.

**Location** `src/str/StrategyTreasuryBase.sol:364-370` (`p = lastGoodPrice` when `tryPrice` fails,
`MAX_SIZING_AGE = 5 days` at `:97`), `:212` (`_notePrice`), `:275`, `:297`, `:314` (`_notePrice(p)` called
with whatever `health()` served); `src/str/StrategyTreasury.sol:112` (the band branch returns a **pulled**
price), `:90`.

**Status** REASONED. **Conditions** 1. `bandBpsPerHour != 0`. — *status: **zero for every stock today**;
requires a `setBandCeiling` (see F-03).* 2. A scheduled closure during which someone holds the V3 pool's
600 s mean off the frozen feed. — *status: this is the disclosed TR-1 precondition; it needs a 600 s hold,
so it is **High-capped** by the rubric even where it bites.* 3. `takeProfit` or `buyDip` is called during
that window. — *status: **neither checks `pricedOffPoolOnly()`** — only `_book` (`:251`) and `stopLoss`
(`:290`) do — and both are permissionless and bounty-paying.*

**Mechanism** `_notePrice(p)` is called unconditionally by `takeProfit` and `buyDip`, and `p` on the band
branch is `feed ± (dev − agree)` — up to `MAX_BAND_BPS = 3000` bps from the feed. `lastGoodPrice` then
carries that pool-set number for up to five days, sizing `buyback`'s chunk. `_book`'s comment at
`:252-253` is explicit that a lot's cost must never come from a pool-only price; `lastGoodPrice` is
subject to the same argument and is not protected.

**Impact** Loser: **holders**, via a mis-sized burn — up to ~43% too large or ~30% too small. Execution
price is still bounded by the hook's 600 s mean, so this is a **sizing** error, not a price error.
**Certain gain 0, option gain 0.**

**Fix** `if (!pricedOffPoolOnly()) _notePrice(p);` in `takeProfit` and `buyDip`, so `lastGoodPrice` only
ever holds a Chainlink-signed number. Two calls, ~30 B against **`TreasuryDeployer`'s 2,158 B**.

### F-26 · Low · A fast honest rally clamps the buy-back's mean branch to spot and reverts `NotDue`, with no widening term — and `docs/SECURITY.md`'s "one cap-sized step per cooldown" is true only of the other branch

**Lanes** `02-historical.md` HX-6, **single source**. Verified against `:464-471` and `:476`.

**Location** `src/str/StrategyTreasuryBase.sol:464-471` (the mean branch), `:475-479` (the anchor branch,
where `drift` grows one impact cap per elapsed cooldown), `:487-489`, `:380`, `:93`
(`BUYBACK_TWAP_WINDOW = 600`).

**Status** REASONED. **Conditions** 1. The ring can serve the window, so the mean branch is taken. —
*status: true from ~600 s after the pool's first liquidity-bearing swap and **permanently thereafter**,
because the ring cannot be starved — see §6.* 2. Spot has moved more than roughly `maxBuybackImpactBps`
away from the 600 s mean in the direction making the token dearer. — *status: routine for a just-launched
single-sided token; at the shipped 300 a 3% move inside ten minutes suffices.* 3. `buybackStock > 0`. —
***UNMEASURED**; needs at least one `takeProfit`.*

**Impact** Loser: **token holders** (the burn is delayed) and the **bounty caller** (never paid). No
principal is lost — `buybackStock` is not consumed by a failed call and the cooldown is not spent. Self-
healing after ~600 s. **Certain gain to a griefer: 0**, and they pay the buy tax, which is burned;
**option gain**: they hold a token position bought at the top of their own push.

**Fix** Either give the mean branch the widening term the anchor branch has — replace `half` at `:467`
with `half * (1 + (block.timestamp - lastBuybackAt) / cd)`, capped — three lines against
**`TreasuryDeployer`'s 2,158 B**; or accept it and **say so**, because `docs/SECURITY.md` currently claims
"Genuine appreciation still gets bought, one cap-sized step per cooldown", which is true of the anchor
branch and false of the branch that is always taken (§6, L-9).

### F-27 · Low · The V4 `health()` reads spot alone, with no second witness, so an atomic push both opens and closes the gate

**Lanes** `01-clean.md` C-13. **Not new** — disclosed in `StrategyTreasuryV4`'s own header at `:32-40`.

**Location** `src/PoolTrader.sol:113-126` (V3: spot **and** the 600 s mean, either failing returns false);
`src/str/StrategyTreasuryV4.sol:87-93` (V4: spot only); `src/str/StrategyTreasuryBase.sol:249`, `:261`,
`:291`, `:309`.

**Status** REASONED. **Conditions** 1. Capital to move the stock/USDG pool's spot past `maxDeviationBps`
(< `maxSlippageBps` <= 300) for one block. — *status: at the exact depths (F-01) a ±1% shove-and-unwind
costs **$69–$717** in fees and parks $10k–$719k; the cost of **holding** it is **UNMEASURED**.*
2. Sustained griefing needs the push held across blocks against arbitrage. — *status: the arb is what makes
this a grief rather than a lock.*

**Impact** Loser: **holders**, in deferred rule execution. `health()` is fail-closed by design, so pushing
spot outside the band is a denial tool, not an extraction tool: it blocks `book`, `takeProfit`, `stopLoss`
and `buyDip`. **Certain gain 0**; **option gain** bounded by `maxSlippageBps` on the *opening* direction
only. The V4 header's claim that "the worst a manipulated gate buys an attacker is forcing one fill to the
edge of that band" is correct for opening the gate and **does not mention the closing direction, which is
the cheaper of the two** — a push *away* from the oracle needs no counterparty willing to take the other
side. Two of five measured pools already sit at 0.229%–0.330% against a 50 bps gate (lane 08, 2026-09-21),
so the starting distance is smaller than assumed.

**Fix** None that is clean without a second oracle; the honest fix is to say so. The V3 path is the better
one and `v4ListingEnabled` defaults to false (`StrategyFactory.sol:212`), which is the right default.

### F-28 · Low · `LaunchRouter` funds the fee from its own read of `getDefaults()`; a fee lowered or switched off in between strands the difference in an ownerless contract

**Lanes** `03-checklist.md` CL-14, **single source**.

**Location** `src/str/LaunchRouter.sol:65` (`factory.getDefaults()`), `:89-95` (`_fundFee`), against
`src/str/StrategyFactory.sol:362` and `:378-389`.

**Status** REASONED. **Conditions** 1. The owner lowers `launchFeeAmount`, or sets
`launchFeeCurrency = None`, ordered before a pending router launch in the same block. — *status:
possible; frequency **UNMEASURED**.* 2. `q.maxFee` still passes `:365`. — *status: automatic — a lower fee
always passes a `maxFee` restatement.*

**Impact** Loser: the **launcher**, of at most one launch fee (25 USDG at the script's default).
**Certain gain to the *next* launcher through the router**: the stranded amount, which part-pays their
fee. **Option gain 0.** Dust-scale, permanent (the router has no owner, no rescue and no sweep), and
reachable only by an unlucky ordering. The `FeeCurrency.None` variant is worse in kind: `_fundFee` still
pulls while `_chargeLaunchFee` charges nothing, so the whole fee strands.
`docs/SECURITY.md:256` states "the fee approval to the factory is exact and consumed" — true when the
defaults do not move mid-flight, which is the case this misses. Note the **converse is safe**: the router
and the factory read `defaults` in the same transaction and `launch` is `nonReentrant`, so they cannot
disagree about anything that changes a CREATE2 address (§6).

**Fix** After `factory.launch` returns, refund `feeToken.balanceOf(address(this))` to `msg.sender` and
zero the allowance. `LaunchRouter` has 18,581 B and is redeployable periphery: a non-issue.

### F-29 · Low · `Swept` reports the amounts **credited**, not the amounts **paid**, and the sweeper's tip appears in no event at all

**Lanes** `03-checklist.md` CL-4, **single source**.

**Location** `src/str/StrategyHook.sol:294` (`emit Swept(0, toTreasury, cut, mine)`) preceded by
`:288-292`; `:254` (`emit Swept(t - tip, 0, 0, 0)`); the event at `:107`; `_pay` at `:354-369`.

**Status** REASONED. **Conditions** 1. One of the three recipients cannot receive the stock. — *status:
the issuer holds a deny-list checked on `to`; whether it is ever used against these addresses is
**UNMEASURED**.* 2. Someone indexes `Swept`. — *status: the product has a front end; behaviour
**UNMEASURED**.*

**Mechanism** `distributeStock` credits all three ledgers, then calls `_pay` three times. `_pay` **never
reverts** — a failed transfer restores the debt and returns 0 — but the event reports `toTreasury`, `cut`
and `mine` unconditionally. A sweep in which the creator's transfer failed emits a non-zero
`stockToCreator` while zero stock reached the creator; when they later `claim(to)`, a `Claimed` fires for
the same money. Two further gaps: the tip is computed and paid but is **in neither event**, so the one
number explaining why a stranger called `sweep` is invisible on chain; and a single `sweep` emits **two**
`Swept` events, each with zeros in the other leg's fields.

**Impact** Loser: the **integrator**, and through them anyone reading the front end. No funds move wrongly
— the ledger is correct and `owed(who)` is queryable. **Certain gain 0, option gain 0.** Permanent.

**Fix** `_pay` already returns the paid amount; build the event from the three return values plus the tip.
Free against **`HookDeployer`'s 8,147 B**. If the signature must stay, emit `SweptTip(caller, amount)` and
document that `Swept` reports credits.

### F-30 · Low · `StrategyTreasuryV4` exposes no getter for its `PriceOracle`

**Lanes** `03-checklist.md` CL-9, **single source**.

**Location** `src/str/StrategyTreasuryBase.sol:105-107` (`_stock`, `_usdg`, `_oracle` are `internal
immutable`); `src/str/StrategyTreasuryV4.sol:41` (does not inherit `PoolTrader`); contrast
`src/PoolTrader.sol:36-39`, where `usdg`, `stock`, `pool` and `oracle` are all `public immutable` — which
is why the V3 treasury is fine and only the V4 one is affected.

**Status** REASONED, with the storage layout EXECUTED (a public-member sweep lists
`StrategyTreasuryV4`'s public members as `stockKey`, `stockIsCurrency0`, `stockPoolFeeBps` plus the
base's; `_oracle` is absent).

**Conditions** 1. A stock is listed on V4. — *status: `v4ListingEnabled` ships **false**, so this affects
nothing today; but `docs/` motivates V4 with SPY and COIN, so it is expected to be used.* 2. An integrator
wants to verify which oracle prices a strategy. — *status: `docs/SECURITY.md:34` calls the oracle choice
"pure trust", which makes it exactly the thing a buyer should be able to verify independently.*

**Impact** Loser: the **integrator**, and the **buyer** who cannot verify the price source on chain. It is
recoverable only from `factory.listings(stock).oracle` at the launch block (an archive read; the current
value may have been re-listed) or from constructor calldata. **Certain gain 0, option gain 0.** Permanent
for every V4 strategy. The base's reasoning for `internal` (`:35-40`: a name collision with `PoolTrader`'s
`oracle`) is correct for the V3 contract and does not apply to the V4 one.

**Fix** `function oracle() external view returns (PriceOracle) { return _oracle; }` in
`StrategyTreasuryV4` — ~50 B against **`TreasuryV4Deployer`'s 5,823 B**. Better, put `oracleAddress()` in
the base so both venues answer the same question: ~50 B against **`TreasuryDeployer`'s 2,158 B**.

### F-31 · Low · The stock issuer's pause is the only halt that shuts a holder's exit, and `docs/SECURITY.md:60` calls the recovery "full" without saying what is blocked meanwhile

**Lanes** `03-checklist.md` CL-3, **single source**.

**Location** `src/str/StrategyHook.sol:169-205` (the swap path is untouched by any pause — `afterSwap`
never reads the calendar or the oracle, and `sellRateBps` is pure time arithmetic); the dependency is the
pool's `take` of the **stock** to the seller; `src/str/TradeRouter.sol:80-90` (the partial mitigation);
`docs/SECURITY.md:60-61`.

**Status** REASONED. **Conditions** 1. The issuer pauses the token. — *status: they hold both the pause
and a deny-list; frequency **UNMEASURED**.* 2. A holder wants out. — *status: n/a, nothing launched.*

**Impact** Loser: the **token holder**, for the duration of a pause. The strategy token's only market is
`<token>/<stock>`; a sale ends with the PoolManager transferring the **stock** to the seller, and a paused
stock reverts it. There is no redemption, no second pool and no floor. **Certain gain 0, option gain 0.**
The mitigation is real and worth stating: `TradeRouter.sell` takes the stock to **itself** and hands the
seller USDG, so a **deny-listed** individual can still exit through the router. A **pause** blocks the
router's leg too and there is no way round it.

**Fix** No code change is possible. One sentence in `docs/SECURITY.md`: while the stock is paused a
strategy token has no exit, direct or routed, because its only quote currency is the stock.

### F-32 · Low · A bug in `TradingCalendar` is unfixable for every launched strategy, and the two proposed remedies for the calendar's owner power are in direct conflict

**Lanes** `03-checklist.md` CL-6, **single source**; it composes with F-02 and F-19.

**Location** `src/PriceOracle.sol:31` (`ITradingCalendar public immutable calendar`), `:43`, `:51`;
`src/str/StrategyTreasuryBase.sol:107` (`PriceOracle internal immutable _oracle`);
`src/str/StrategyFactory.sol:326-327` (the oracle is baked into the treasury's constructor args).

**Status** REASONED. **Conditions** 1. A bug is found in the calendar's date arithmetic after a launch. —
*status: `AUDIT.md` reports all 20 NYSE closures for 2026-27 matching day by day over 733 days with DST
flips exact, so the probability is low — but the rules are computed forward forever and **UNMEASURED past
2027**.* 2. Nothing in calendar → oracle → treasury can be re-pointed. — *status: **confirmed**, all three
links immutable.*

**Impact** Loser: every **treasury** on that calendar and through them every **token holder**, by the rule
mis-firing or refusing on the wrong days. No direct theft; **certain gain 0, option gain 0.** The calendar
is the **only** contract whose state a launched strategy reads *live* — every other dependency is frozen
at birth — and it is also un-replaceable for a launched strategy. Widest blast radius, narrowest
remediation path.

**The conflict, which is the part worth acting on.** `setOverride` day-by-day is the only patch mechanism
for a calendar bug. `AUDIT.md` FA-1's suggested remedy is to **renounce calendar ownership**, which also
removes F-02's lever. Those two mitigations cannot both be taken, and the trade-off should be decided
explicitly before the first launch rather than discovered afterwards. **My recommendation:** take F-02's
fix (a) instead — make `setOverride` halt-only — which removes the dangerous half of the power while
keeping the patch mechanism, and makes renouncing unnecessary.

### F-33 · Low · The deploy script never prints 11 of the 19 defaults it sets — including every silent kill switch in F-05 — and its one multi-value line is mislabelled

**Lanes** `03-checklist.md` CL-8, **single source**. This is the operational half of F-05 and they should
be fixed together.

**Location** `script/DeployStrategyLaunchpad.s.sol:217-223`, against the `Defaults` struct at
`src/str/StrategyFactory.sol:171-191`.

**Status** REASONED (a direct reading of the `console2.log` calls against the struct).

**Mechanism** The "--- read back ---" block prints `supply`, `lpFee`, `minTaxBps`, `maxTaxBps`,
`protocolBps`, `maxCreatorBps`, `launchFeeCurrency`, `launchFeeAmount`, `publicLaunch`. It does **not**
print `tickSpacing`, `spikeBps`, `spikeSeconds`, `sweepTipBps`, `bountyBps`, `maxSlippageBps`,
`maxDeviationBps`, `maxBuybackImpactBps`, `buybackCooldown`, `minLotUsdg` or `buybackChunkUsdg` — eleven
of nineteen, and **every single silent kill switch in F-05 is in that unprinted list**. The script's
header says "read the printed plan, then sign it yourself"; the printed plan omits exactly the values
whose mistakes do not announce themselves. Separately, line 218 is labelled
`"supply / lpFee / tickSpacing:"` and passes **two** values — `tickSpacing` is printed nowhere in the
script, so an operator reading the output believes they have verified it.

**Impact** Loser: the **team**, and through a bad default every future **token buyer**. No funds directly.
**Certain gain 0, option gain 0.**

**Fix** Print all nineteen and fix the label. Script only; no byte budget.

### F-34 · Low · `maxSlippageBps = 100` is the right number for the first-wave pools and the wrong one for thin ones, and the break-evens move with a depth figure that halves overnight

**Lanes** `04-economic.md`'s manipulation-cost section; re-based by me on `08-depth-measurement.md`.

**Location** `src/str/StrategyTreasuryBase.sol:102` (`MAX_SLIPPAGE_BPS = 300`);
`src/str/StrategyFactory.sol:258`; the recheck at `src/PoolTrader.sol:139-140` and
`src/str/StrategyTreasuryV4.sol:109`.

**Status** COMPUTED. **Conditions** 1. A treasury trade larger than the break-even below. — *status:
**UNMEASURED** per listing.* 2. The depth figures hold. — *status: they do not hold for long — NVDA's
active `L` fell **−60.6%** in 12.3 h, 2026-09-20 → 21, with TVL essentially unchanged.*

**Mechanism** Max extraction per treasury trade is `(maxSlippageBps + poolFeeBps) × size`, re-checked
against the realised average. The attacker's cost to displace the pool that far and unwind is the pool fee
twice over the displaced notional. On E's constant-L figures the break-even treasury trade was $192k on
NVDA and **$2,965 on INTC**; a treasury doing $7k `takeProfit`s on AMD is profitably sandwiched. **The
F-01 correction does *not* divide these by 23**: at ±0.5% and ±1% constant-L is not a bound in either
direction (0.53×–1.35×), so the small-move column is approximately right and is simply uncertain in both
directions. What it *is* is unstable: every break-even is linear in depth, and depth moved −60.6% on the
flagship pool in half a day.

**Impact** Loser: the **treasury**, on any trade above the break-even for its pool. **Certain gain** to
the sandwicher: up to `(maxSlippageBps + poolFeeBps)` of the treasury's trade, minus their round trip.
**Option gain 0.** Unlike TR-1 this applies on **ordinary open trading days**, not only during a closure —
a second, independent reason to list only deep pools, and a reason to keep `maxSlippageBps` at 100 rather
than at the permitted 300, which divides every break-even by three.

**Fix** Keep `maxSlippageBps` at 100; publish a per-listing maximum treasury size (F-36 gives the other
reason to want one); and measure D(0.5%)/D(1%) by exact tick-walk per listing rather than by constant-L.
No code change.

### F-35 · Low · `minLotUsdg = 5` may be far below the lot size at which a `takeProfit` tip covers its own gas — conditional on a price the repository never states

**Lanes** `04-economic.md` E-13, **single source**, and the lane is explicit that the conclusion depends
on an unknown.

**Location** `src/str/StrategyTreasuryBase.sol:78`, `:250`, `:313`, `:380`;
`script/DeployStrategyLaunchpad.s.sol:172` (`MIN_LOT_USDG = 5e6`).

**Status** COMPUTED. Gas price **0.049538 gwei**, read 2026-09-21 at block 68,636,383; a ~450k-gas
`takeProfit` costs 2.23e-5 of the native token.

**Conditions** 1. The native token's price. — ***UNMEASURED, and the repo never states what the native
token is.*** At ~$4,000 the lot needed to cover gas is $196–704 depending on `tp1`; at ~$1 it is $0.03–0.18
and the finding collapses to nothing.

**Impact** If the native token is expensive there is a band from $5 up to $196–704 in which a lot is
bookable but not worth anyone's gas to sell, and it accumulates. Loser: the **treasury**. **Certain gain
0, option gain 0.** Independently, the backtest lane reaches the same place from the other side: at
`--inflow 100` and `tp1 = 5%` a take-profit tip is **$0.0125** across 1,478–1,650 assumed keeper calls per
ticker.

**Fix** State the native token and its price assumption in `docs/OPERATIONS.md`, and set `minLotUsdg` per
listing so `bountyBps · tp1/(1+tp1) · minLotUsdg` exceeds a call's gas by a stated multiple. Operational;
`minLotUsdg` is a `Default`, so no code change.

### F-36 · Low · A treasury large relative to its stock pool can neither deploy its reserve nor sell its lots — and the threshold is 8–25× lower than the lane computed

**Lanes** `04-economic.md` E-12; re-based by me on `08-depth-measurement.md`. The mirror of F-09's size
half on the buy side.

**Location** `src/str/StrategyTreasuryBase.sol:312` (`spend = reserveUsdg() * lotBps / 1e4`), `:322` (a
short fill under `minLotUsdg` reverts), `:325` (`lastSalePrice = p` after **any** dip, so the next rung
needs a further `dipBps`), plus F-09's `requireFull` on the sell side.

**Status** COMPUTED. **Conditions** 1. Treasury size relative to pool depth. — ***UNMEASURED** per
listing, and the depth numbers move −60.6% in half a day.*

**Impact** Loser: the **treasury**, as opportunity cost. A dip absorbs at most the depth between spot and
`oracle · (1 + maxSlippageBps)`, and then `lastSalePrice` ratchets to `p`, so the reserve cannot be topped
into the same rung. On E's figures a $1M reserve on an AMD-sized pool needs ~90 successive `dipBps` rungs
to deploy — the stock falling to essentially nothing. On the corrected depths the same problem starts on
**NVDA**. **No attacker. Certain gain 0, option gain 0.**

**Fix** Scale `minLotUsdg` / `buybackChunkUsdg` / `lotBps` per listing rather than globally — they are
`Defaults`, so this is operational discipline, not code — and publish the maximum treasury size each
listed pool can serve in `LISTING_CANDIDATES.md` alongside the exact depth.

### F-37 · Low · `creatorBps` is a rebate on the creator's own selling, the burn is a rebate on their own buying, and the creator has no economic stake in the rule's quality

**Lanes** `04-economic.md` E-14, **single source**.

**Location** `src/str/StrategyHook.sol:274-295` (the creator is paid `creatorBps` of every stock-side
take, **including their own**), `:248-255` (the buy-side tax is burned pro rata to every holder, including
the creator); `src/str/StrategyFactory.sol:129` ("receives `creatorBps` of the stock-denominated tax,
**forever**"); `src/str/LaunchRouter.sol:57-86`.

**Status** COMPUTED. **Conditions** 1. The creator takes a meaningful share of supply through
`LaunchRouter`. — *status: permitted, and `docs/SECURITY.md:214-218` and R4-1 both say so, framing it as
curve pricing rather than as a fee rebate.*

**Impact** Loser: the **public seller**, relatively. **Certain gain to the creator**: at
`creatorBps = 3000`, their effective sell tax is **0.70 × `taxBps`** while everyone else's is `taxBps` —
on a $1M creator exit at `taxBps = 1000`, $29,850 back out of $100,000 paid, on top of 30% of everyone
else's. A creator holding 45% of supply faces an effective **buy** tax of 0.55 × `taxBps`. **Option gain
0.** Separately and more importantly: the creator's revenue is `creatorBps` of sell volume and is
**entirely independent of `tp1`, `tp2`, `dipBps`, `stopBps`, `lotBps` and `bandBpsPerHour`**. There is no
stake, no vesting and no clawback; the only alignment is reputation. That is worth stating plainly next to
`docs/SECURITY.md`'s "Creators — untrusted", and it is the reason F-03's condition 2 should be assumed
against the protocol.

**Fix** Disclosure. The front end should show the creator's effective round-trip tax next to the published
one, and `LaunchedWithCapital(…, tokensBought, …)` next to the token — which `docs/SECURITY.md:236-238`
already says a front end **must** do.

### F-38 · Low · About 4.5% of a seller's tax reaches holders as a burn on the first pass; 45% is locked in a reserve only `buyDip` can spend and 50% is extracted

**Lanes** `04-economic.md` E-16, **single source**.

**Location** `src/str/StrategyHook.sol:274-295` (the split); `src/str/StrategyTreasuryBase.sol:277-284`
(only the *profit* becomes `buybackStock`; the principal becomes USDG), `:385-389`.

**Status** COMPUTED. Per 1.0 of stock-denominated sell tax, at the shipped split with `creatorBps` at its
`maxCreatorBps = 3000` ceiling: sweep tip 0.50%, protocol 19.90%, creator 29.85%, treasury 49.75% — of
which **burned for holders on the first `takeProfit` (`tp1 = 10%`): 4.48%**, caller bounties 0.05%, and
**locked as USDG reserve: 45.23%**. At the constructor's `tp1` floor of 2.6% the burn share falls to
**1.25%**; at `tp1 = 30%` it rises to 11.37%.

**Impact** Loser: the **token buyer**, whose only return is the burn. Nobody is cheated — every number is
in the contract — but no document states the composition, and `README.md:42-44` describes the split as
"`protocolBps` to the protocol, `creatorBps` to the creator, and the remainder to the treasury" without
saying how much of "the remainder" ever comes back out. A buyer reading that would reasonably expect the
treasury's 50–80% to work for them; on the first pass, 4.5–7.2% does. The reserve is not lost — each later
cycle converts another `tp1/(1+tp1)` — but only `buyDip` can spend it, which needs a prior sale and a
subsequent `dipBps` fall (F-10, F-36), and in a monotone uptrend it is never spent at all.
**Certain gain 0, option gain 0.**

**Fix** Publish the table. It costs nothing and it is the single most informative fact about the token.

### F-39 · Low · FA-4's mirror and TR-3's floor shipped in the same commit and contradict each other: raising `maxSlippageBps` bricks pending launches with the exact opaque error FA-4 existed to remove

**Lanes** `06-prior-rounds.md` §3.1, **single source**, EXECUTED.

**Location** `src/str/StrategyFactory.sol:252-262` (`_setDefaults`) against `src/str/StrategyTreasury.sol:41`
and `src/str/StrategyTreasuryV4.sol:78`. Both landed in `4deb193`.

**Status** EXECUTED — `test_probe_raisingMaxSlippageBricksAPendingLaunchWithAnOpaqueReason` launches the
shipped request successfully, then `setDefaults` with `maxSlippageBps = 300`, then
`vm.expectRevert(bytes("treasury deploy"))` on the identical request and salt. Passes.

**Mechanism** FA-4's fix is described as "`setDefaults` mirrors every constructor bound. Because a
constructor's revert reason does not survive CREATE2." TR-3's fix, in the same commit, added a constructor
bound that **depends on a creator input**: `tp1Bps, dipBps >= 2·(maxSlippageBps + poolFeeBps)`.
`maxSlippageBps` is a *default*, `tp1Bps` is in the `Request`, `poolFeeBps` comes from the listed pool —
so `_setDefaults` cannot mirror it and does not, and `launch()` does not pre-check it either. Raising
`maxSlippageBps` from 100 to 300 (both inside every bound `_setDefaults` checks) moves the floor from 260
to 660 bps and makes every pending launch with `tp1Bps < 660` die as
`require(a != address(0), "treasury deploy")`.

**Impact** Loser: the **creator** — a 16k-hash mined salt and an unnamed failure, then a nineteen-field
diff to find out why. No funds. **Certain gain 0, option gain 0.**

**Fix** Move the floor check into `launch()` with a named error (~40 B against **945 B**), or state in
`docs/SECURITY.md` that the mirror covers default-only bounds. And **re-read FA-4's claim**, which became
false the day its sibling shipped.

### F-40 · Low · `_noteTokenSpot` lacks the liquidity guard `afterSwap` has; three unrelated accidents defend it and none is stated as an invariant

**Lanes** `06-prior-rounds.md` §3.2 and `02-historical.md`'s "also checked" section, which reached the
same place and the same conclusion independently.

**Location** `src/str/StrategyHook.sol:182-185` (HK-4's fix — the ring refuses a tick with no liquidity
behind it) against `src/str/StrategyTreasuryBase.sol:339-344` (`_noteTokenSpot` reads `getSlot0` with
**no** `getLiquidity(poolId) != 0` test, and the anchor is a one-way ratchet toward "token cheaper").

**Status** REASONED (both lanes).

**Mechanism** A single observation at the empty-side extreme would pin `buybackAnchorSqrtP` at MIN/MAX
sqrt price for the life of the strategy, and the anchor branch of `_buybackLimitSqrtP` would then clamp
every future buy-back to `sqrtP ± 1` — `buyback()` reverting `NotDue` forever on that branch.

**It is not reachable today, and every reason is accidental.** (1) R4-3's guard at `:339`
(`observationCount() == 0 → return`) covers the launch instant, which is HK-4's own reproduction window,
and it was added for an unrelated reason. (2) After the first in-range swap, returning to the empty side
requires selling back **more tokens than the pool ever issued** — impossible, because `StrategyToken` has
no mint, the hook's token-side take is burned, and the treasury burns what it buys back, so circulating
supply is monotonically non-increasing. (3) The anchor branch is itself near-dead once the ring can serve
600 s (§6).

**Impact** No exposure today. **Certain gain 0, option gain 0.** Recorded because three separate accidents
defend it, none is stated as an invariant, and the line `docs/SECURITY.md` offers — "It also refuses to
record a tick with no liquidity behind it" — is **true of the ring and false of the anchor**. Any future
change that mints a strategy token, adds a second liquidity path, or seeds the anchor at `wire()` re-opens
it into a permanent brick of `buyback()`.

**Fix** One line at `:340`: `if (poolManager.getLiquidity(poolKey.toId()) == 0) return;` — a few bytes
against **`TreasuryDeployer`'s 2,158 B**. Defence in depth, and it makes an invariant explicit.

### F-41 · Low · `AUDIT.md`'s status header records FA-1 / TR-6 as "fixed". It is not fixed; it was decided and documented, and the decision left both halves of the power live

**Lanes** `06-prior-rounds.md` §2.2, **single source**, EXECUTED.

**Location** `AUDIT.md:39` (blocker 5 listed among items "fixed on `fix/audit-pre-launch-2`") against
`AUDIT.md:435` (blocker 5's own row, which offers three options, the third being "accept it and correct
the README"). What shipped is the third option plus a narrowing.

**Status** EXECUTED — the prior-rounds lane ran
`test_audit_calendarOwnerCanHaltOrReopenEveryLaunchedStrategy` at `9a291aa` and it passes, asserting
exactly the behaviour FA-1 described.

**Impact** Loser: **the next reader of the ledger**, and through them the go/no-go decision. No funds.
**Certain gain 0, option gain 0.** One word in a status header, and the ledger is wrong forever: the halt
works seven days in seven (round 3 made the brake *stronger*, which was the right trade) and the
force-open path is live (F-02). The narrow claim that *does* survive is accurate and worth keeping: an
override cannot open the **pool-only closed-market path**, because `StrategyTreasury.sol:129-131` asks
`isScheduledClosure`.

**Fix** Change the disposition to "accepted by decision, disclosed" and say which half of the original
claim survives. **Process:** grade the disposition, not the finding.

---

## The Info tier

No value impact. Each is recorded so the next round does not re-derive it.

| ID | claim | lanes | status | note |
|---|---|---|---|---|
| **I-1** | `donate()` is open: `BEFORE_DONATE`/`AFTER_DONATE` are absent from `0x2844`, so the PoolManager never calls the hook's reverting stubs. Anyone may `poolManager.donate()` into a launch pool; it credits the only in-range position — the seed, which nobody can ever collect. | L-11, HX-7, prior §3.4(a) | EXECUTED (bit decode) | Permanently stranded, not stolen; it benefits nobody and costs only the donor. **FA-5's fix pinned the *parameter* (`lpFee == 0`) and left the *mechanism* open.** The hook's two reverting donate callbacks read as a control and are not one — say so in a comment, or set the bits so the revert is real. |
| **I-2** | `launchFeeCurrency` is the one launch input in no constructor's arguments and not restated by `maxFee`. `docs/SECURITY.md` says the pair "exist so that the owner cannot restate the fee … underneath a pending launch", which is stronger than the code. | prior §2.3, historical, checklist §6 | REASONED | Every flip was worked: `Usdg→Stock` and `Stock→Usdg` are loud or cost the *owner*; `*→Native` is a loud revert; only `None→Usdg/Stock` bites, up to `maxFee`, and only with a standing approval. **One sentence in `docs/SECURITY.md`.** The class FA-2 named was enumerated one member short. |
| **I-3** | `StrategyFactory.sol:404` downcasts the opening sqrt price to `uint160` with no MIN/MAX_SQRT_PRICE bound, so an extreme `openPriceE18` wraps to a small in-range value and the pool opens at a price nobody asked for. | HX-8 | REASONED | Owner-set per listing and restated by the creator, so a configuration footgun, not an attack. `require(sq <= TickMath.MAX_SQRT_PRICE)` is the cheap version; a few bytes against **945 B**. |
| **I-4** | `wire()` does not reject `key.hooks == address(0)`. `hook != address(0)` is the "already wired" sentinel, so a zero-hook key leaves the treasury permanently unwired: `buyback` reverts `NotDue` forever, `_noteTokenSpot` returns early, and `wire` stays callable. | HX-9, checklist §6 | REASONED | **Not reachable through `StrategyFactory`**, whose only call passes the real hook. A silent brick behind one unverified field; one `if` fixes it. |
| **I-5** | `PriceOracle._read` has no `minAnswer`/`maxAnswer` clamp check (the Venus/BNB, Impermax class): during a crash past the aggregator's floor, `latestRoundData` keeps returning the floor with a fresh `updatedAt` and `answer <= 0` does not catch it. | HX-11 | REASONED | Mitigated by the deviation gate — a clamped feed the pool disagrees with fails closed — but **the mitigation is incidental**: it is the pool agreeing, not the clamp being detected. Robinhood-Chain equity feeds' `minAnswer`/`maxAnswer` are **UNMEASURED** and worth reading before launch. |
| **I-6** | `list()` does not mirror `PoolTrader`'s `observationCardinality >= 660` check, so a thin listing looks fine, `predict()` works, and the first launch dies as `require(a != address(0), "treasury deploy")`. | CL-15 | REASONED | Lane 08 measured all 11 candidate pools 2026-09-21: NVDA 6000, SPCX 3100, **META 1400/next 1801**, AMD 1400/1400, the rest 1801 — **all pass today**. The fix (`slot0` staticcall plus a compare) is ~120–180 B and **competes with F-05's for the 945 B**; F-05's is the better value. |
| **I-7** | `Launched` records none of the mutable terms the strategy was born with — every economic term came from `defaults`, which is mutable. | CL-13 | REASONED | Recoverable by replaying `DefaultsSet` and interleaving by block, or by an archive read of the deployed immutables. Re-emitting `DefaultsSet` from inside `launch` is the cheap form (~40 B against **945 B**). |
| **I-8** | `_setDefaults`'s stated invariant is false for the creator-supplied half of the rule: `tp1Bps`, `tp2Bps`, `dipBps`, `stopBps`, `lotBps` reach the treasury constructor unchecked and fail as the same opaque `"treasury deploy"`. | C-15 | REASONED | Same root as F-39. A front end reading `predict()` can pre-check, so Info. |
| **I-9** | V4 settlement assumes a stock with no transfer fee and no rebase: a fee makes `paid < delta` and the unlock reverts `CurrencyNotSettled`, bricking `buyback()`, both `TradeRouter` legs and `LaunchRouter`'s first buy **simultaneously**; a rebase desyncs `bookedStock`/`buybackStock` and `unbookedStock()` silently floors to 0. | C-16 | REASONED | Not a bug in this code; a **hard requirement on the listed asset**, worth stating because none of the three contracts can be redeployed for an existing strategy — and the repo itself notes the stock is a beacon proxy one address can upgrade with no timelock, so "today's token has no transfer fee" is not a durable property. |
| **I-10** | `StrategyFactory.sol:426` is the one raw `IERC20.transfer` in the codebase; everything else uses `SafeERC20`. | C-17 | REASONED | **Safe as written** — the token is `StrategyToken`, an OZ ERC20 that reverts rather than returning false. Noted only because it is the single deviation from the file's own convention, inside the unlock callback where a silent false would surface as `CurrencyNotSettled` rather than a clear error. |
| **I-11** | `_SCALE` is 0 when `usdgDec > 18 + stockDec`, which makes `_ruleStockFor` divide by zero; and `listV4` does not check the stock/USDG pool's fee, so above ~970,000 the `keep` subtraction underflows and every `_swapStock` reverts. | C-18 | REASONED | Absurd decimals; the value is immutable with no guard. On the fee: `Hooks.isValidHookAddress` means a **hookless** pool cannot carry a dynamic fee, so `listV4`'s `hooks == 0` requirement does rule out the honeypot case. Owner-listed either way. |
| **I-12** | `buybackCooldown` is inert: the binding rate limit is `BUYBACK_TWAP_WINDOW` (600 s), ten times longer, because the impact cap is **cumulative against the mean**. | E-11 | COMPUTED | No value impact, but `buybackCooldown` is one of nineteen `Defaults` a reader would expect to control buy-back throughput and it does not. It also means the 240 s spike guard and the 60 s cooldown were sized against each other on a premise that does not hold (see I-14). Say so in `docs/ARCHITECTURE.md` and set the parameter to 600 so it states the real behaviour. |
| **I-13** | The fee model needs **$1.26M–$12.6M/yr** of aggregate sell volume to clear a $25k/yr cost, and buying pays the protocol nothing. | E-17 | COMPUTED | Protocol revenue is 19.9 bps of **sell** volume at `taxBps = 1000`, 2.0 bps at 100. The 25 USDG launch fee needs 1,000 launches to cover $25k. In an up-market there are few sells, so protocol, creator **and** treasury starve together — and per F-11 an up-market is also where the rule performs worst. Neither regime deadlocks; both starve the burn. Recorded so the counts are honest. |
| **I-14** | The spike-pinning grief is ~2 orders of magnitude weaker than `docs/SECURITY.md:209-212` discloses ("time-averaged sell tax 27.8% against 10% flat"). **A re-grade DOWN.** | E-15 | COMPUTED | The `2 × spikeSeconds` guard caps the armed fraction at exactly 1/2, so the *ceiling* is `spikeBps/4 + taxBps/2` = 27.5% — which matches, and is independent of `spikeSeconds`, a nice result. But holding it there needs one buy-back per 240 s = 131,400/yr, each spending a chunk of **realised profit**: that is **$65.7M/yr** at the shipped chunk. At $100k/yr of realised profit the time-averaged rate is **10.03%**. I-12 halves the ceiling again. Reported because a document that overstates one risk by 100× spends the credibility it needs for F-01 and F-04. |
| **I-15** | Dead but publicly callable and untested: `TradingCalendar.nextOpen` (`:172`) and `nextClose` (`:180`) have **no consumer anywhere in the repository, not even a test**, yet are `public view` and in the deployed runtime. `PoolTrader._swapForExit` (`:143`) is `internal` and called by nothing in `src/`. | L-13, tests §5 | EXECUTED (grep) | `TradingCalendar` has 19,784 B so this is not a budget question; it is that a front end reading `nextOpen` is reading code no test has ever executed. Hand-checked and both look correct, including that `nextOpen` always advances at least one day. `_swapForExit` costs no bytes (unreferenced internals are not emitted) but the contract-level comment documents a path that exists in no contract deployed from this repo. |
| **I-16** | **Correction to CL-7's mechanism.** `TreasuryDeployer`'s runtime does **not** contain `StrategyTreasury`'s creation code twice; solc emits **one** copy. | L-15, verified by me | **EXECUTED** | 22,418 − 21,581 = **837 bytes** of deployer logic; two copies would be ~43 KB and could not deploy at all. The same 837/852-byte gap appears for the other two pairs. **CL-7's conclusion survives and its proposed fix does not:** dropping `predict` saves ~837 B, not "roughly half the deployer". |
| **I-17** | Fork-test hygiene: **not one** of the 18 fork entries is pinned to a block, and `FirstBatchFork` is **permanently dead** on the configured endpoint (`historical state … is not available` — `publicnode` is not an archive node). | tests §1c, §3 | EXECUTED | It is the **only** test in the repo that reads and ages a real V3 observation ring, i.e. the only place `PoolTrader._meanTick`'s negative-rounding correction fires against reality. Also: the documented fork command `--match-path 'test/*Fork*'` **misses** `DeployGuardsForkTest`; and `TradeRouterFork.t.sol:93` asserts a live-pool value inside a hand-tuned 78–87% window that a depth change moves out either side — which, given −60.6% in 12.3 h, it will. **A red fork job currently carries no information.** |
| **I-18** | `via_ir` is **OFF** and the sibling repo's IR hazards therefore do not apply today — but the obvious next lever for the factory's 945 bytes is `via_ir = true`, and the suite is pervasively `skip()`/`vm.warp()`-dependent. | tests §4, verified by me | EXECUTED | I re-read `foundry.toml`: no `via_ir` key, default false. **Before enabling it, re-run and diff the spike-decay boundaries and the 14-day takeover clock; do not assume.** `skip()` is `vm.warp(block.timestamp + x)` and reads `block.timestamp` itself, so it is the first thing that would misbehave. |

---


---

## Checked and found safe

This section is a deliverable of equal standing to the findings: it records what was examined and found
sound, with the line that makes it sound, so the next round starts here rather than re-deriving it. The
adversarial pass was asked to attack these exonerations as well as the findings and **overturned none of
them**, recording two precision defects instead (see `VERIFICATION.md`). It remains the section with the
fewest independent eyes on it, and a wrongly-cleared attack surface costs more than a wrongly-reported
finding.


Merged and deduplicated across all eight lanes. **This section is a deliverable of equal standing** — it
is what stops the next round re-deriving the same ground. Each item names the line that makes it safe.
Items marked **EXECUTED** were demonstrated against a real `lib/v4-core` `PoolManager` on 2026-09-21.

## The seeded liquidity

- **The seed cannot be withdrawn, and the proof is the library, not the repo's test.**
  `PoolManager.modifyLiquidity` keys the position with `owner: msg.sender`
  (`lib/v4-core/src/PoolManager.sol:161`) into `Position.calculatePositionKey(owner, tickLower, tickUpper,
  salt)` (`lib/v4-core/src/libraries/Position.sol:48-60`) — the **direct caller**, not the unlocker, not
  a recipient argument. `grep -rn "modifyLiquidity" src/` returns **exactly one hit**,
  `StrategyFactory.sol:423`, with a **positive** `liquidityDelta`, inside `unlockCallback` gated on
  `msg.sender == address(poolManager) || !_seeding` (`:418`), with `_seeding` set only around one `unlock`
  in `_openAndSeed` (`:408-410`), and `launch` is `nonReentrant`. There is no second path and no owner
  path. Reached independently by the lead (L-10, at the library), the clean lane, the historical lane and
  the prior-rounds lane (§3.4a).
- **No attacker code executes inside the seeding window.** The hook is freshly CREATE2'd from the
  factory's own initcode, the token is a plain OZ ERC20, and the seed is single-sided so the issuer's
  stock is never touched. The repo's `test_fork_liquidityIsUnremovable_byAnyone` is a spot check (one
  `Rugger` with the exact ticks plus four guessed selectors) — **the `_seeding` latch is the real proof
  and the test does not exercise it.**
- **No third party can add liquidity.** `StrategyHook.beforeAddLiquidity` → `_onlySeed` →
  `if (sender != seeder) revert NotSeeder()` (`:459-468`), `seeder` immutable (`:87`). **EXECUTED** — a
  stranger's `modifyLiquidity` reverts. This is what closes HK-1's whole class (range order, full-range,
  JIT in front of `buyback()`), not just its reproduction. The absence of the two REMOVE_LIQUIDITY flags
  from `0x2844` is therefore consistent, not a hole.
- **`lpFee` is forced to 0** (`StrategyFactory.sol:261`), so **nothing accrues** to the uncollectable
  position. Correct for its own reason (FA-5).
- **The seed really is single-sided** and the factory keeps nothing: `_seedRange` puts `lo = floorT + sp`
  above spot for `tokenIs0` and `hi = floorT` at-or-below otherwise (`:433-438`), and the
  `supply - supply/1e12` slack is burned at `:411-412`. **EXECUTED** — in-range liquidity 0 immediately
  after launch; factory token balance 0; a 1e27 supply seeded with 1e15 wei of slack burned back as dust.
  The liquidity formulae match `getAmount0Delta`/`getAmount1Delta` and round **down**, so the manager's
  round-up is always covered.

## Pool identity, hook identity, deployment

- **A pending launch's pool key cannot be initialised before the hook has code.** `Hooks.callHook`
  requires a matching selector in the return data (`lib/v4-core/src/libraries/Hooks.sol:151-155`) and a
  codeless address returns nothing. **EXECUTED.** Closes FA-3 for any symbol, not just the PoC's.
- **Exactly one pool per hook.** `_onlySeed` compares `key.toId()` against the immutable `poolId`
  (`StrategyHook.sol:466`, fixed at `:134`), so the same hook on a different fee or tick spacing reverts
  `WrongPool`. **EXECUTED.** This is also the second half of the Cork closure: a stranger's pool carrying
  this hook cannot reach any of its accounting.
- **Hook permission bits match the callbacks implemented.** `:129` —
  `if (uint160(address(this)) & 0x3FFF != 0x2844) revert BadConfig();` — and `0x2844` decodes against
  `Hooks.sol:29-47` as exactly `BEFORE_INITIALIZE | BEFORE_ADD_LIQUIDITY | AFTER_SWAP |
  AFTER_SWAP_RETURNS_DELTA`. **EXECUTED** (bit decode). The only gap is donate, which is I-1: a control
  that does not exist rather than a control that is wrong.
- **The deployers cannot be used by anyone but the bound factory** (`_onlyFactory` at `:67`, `:81`,
  `:93`), and **a duplicate deployer address is caught**: the second `bind()` sees `factory != 0` and
  reverts `AlreadyBound`.
- **The mined hook salt is a complete restatement guard over all nineteen `Defaults` fields** — stronger
  than the explicit `maxFee`/`expectedOpenPriceE18` pair, which covers the two fields that reach no
  constructor. EXECUTED by the lead, verified independently by me (§5.11). **Load-bearing, accidental,
  and named nowhere. It should be written down before someone refactors it away.**
- **A mid-launch `setDefaults` cannot produce a mismatched deployment.** `_treasuryArgs`/`_hookArgs`
  re-read `defaults` from storage while `_openAndSeed` uses the memory copy, so any change moves the hook
  address or the pool id and the launch reverts rather than landing inconsistent; `nonReentrant` (`:358`)
  blocks the re-entry itself, including through the native-fee `protocol.call{value:}` at `:382`.
- **`_hookArgs`'s two-encodings-are-one claim is correct.** `Currency` is a user-defined value type over
  `address`, `Rates` is six static integers, every other argument is elementary — no dynamic member, no
  offset table, so the concatenation is byte-identical to the eleven-argument encoding. Same reasoning
  verified for `_treasuryArgs`, where `PoolKey` and `Params` are both all-static.
- **`LaunchRouter` derives the PoolKey from `factory.getDefaults()` — the exact shape of T5-2 — and is
  safe, by atomicity**: `:65` reads and `:67` calls in the same transaction, `setDefaults` is `onlyOwner`,
  `launch` is `nonReentrant`. **Safe for a different reason than the fix round 5 applied to
  `TradeRouter`, and nothing records that.**
- **`listV4` refuses a hooked pool** (`:295`) **and an uninitialised one** (`:296-297`), and a hookless
  pool cannot carry a dynamic fee (`Hooks.isValidHookAddress`, `lib/v4-core/src/libraries/Hooks.sol:124-127`),
  so the fee-flip honeypot is closed.

## Callback authentication

- **No `unlockCallback` in this repo can be invoked by a third party.** `PoolManager.unlock` calls back
  only its own `msg.sender`, and each implementation additionally checks it: `StrategyFactory.sol:418`
  (plus `!_seeding`), `StrategyHook.sol:217`, `LaunchRouter.sol:99`, `TradeRouter.sol:134`,
  `StrategyTreasury.sol:143` (plus `_swapKind == 2`), `StrategyTreasuryV4.sol:123-126` (plus an explicit
  revert on any kind but 1 or 2). `_swapKind` is non-zero only between
  `StrategyTreasuryBase.sol:372` and `:374`. The repo's own `CallbackForger`
  (`test/AuditRouterRound4.t.sol:48-57`) is the regression test.
- **Neither V3 callback can be driven by a fake pool.** `PoolTrader.uniswapV3SwapCallback` requires
  `msg.sender == address(pool) && _swapping` (`PoolTrader.sol:160`); `TradeRouter`'s requires
  `msg.sender == _v3Pool`, non-zero only between `:107` and `:110`, **and** the pool is proven canonical
  first: `factory.v3Factory().getPool(usdg, stock, IV3SwapPool(pool).fee()) != pool` reverts (`:100-102`)
  — which whatever `fee()` a poser answers can only hold for a canonical pool.
  `test_holds_strangerWithControlMidSwap_latchOpen_cannotMoveAnyonesApproval` drives a stock token with a
  `_update` callback through every door and asserts the selector each answers with. Three lanes called
  this the best-built test in the repo.
- **`StrategyFactory.unlockCallback` cannot be entered outside seeding** (`!_seeding` reverts, `:418`).
- **No `delegatecall` and no `tx.origin` anywhere in `src/`** (grep, EXECUTED), and `PoolManager` carries
  `noDelegateCall`.
- **No assembly in any V4 callback path** — every decode is `abi.decode`. The only assembly in scope is
  the three `create2` blocks, each followed by a zero-address check.
- **`hookData` is ignored entirely** by `afterSwap` (the last parameter is unnamed), and both of the
  protocol's own swaps pass `""`.
- **`sync` is always called after the swap and immediately before the transfer**, in all four settlement
  sites, each with exactly one sync/settle pair — so no stale `CurrencyReserves` can be settled against.

## The tax and the hook's ledger

- **The hook's delta convention matches `v4-core` exactly.** `unspecifiedIsCurrency1 = params.zeroForOne
  == (params.amountSpecified < 0)` (`:193`) is the same predicate `Hooks.afterSwap` uses to place the
  returned delta (`Hooks.sol:307-309`), and the `mint`-then-return-delta pair nets the hook's currency
  delta to exactly zero. **EXECUTED** — a 1,000-stock buy produced `hookClaim * 1e4 == (got + hookClaim) *
  300` to within 1e-6.
- **Exact-output is refused** (`:191`), closing the currency inversion and the `1/(1+r)` vs `1−r` gap —
  which at the 90% spike is 0.526 against 0.100, a 5.3× cheaper exit for exactly the trade the spike
  exists to deter. **EXECUTED.** And it is refused *after* the ring write and *after* the treasury
  exemption, so the treasury's own exact-input swaps are unaffected and the ring has no holes an attacker
  chose.
- **The treasury's tax exemption cannot be borrowed.** `sender == treasury` (`:187`) where `sender` is
  `PoolManager`'s `msg.sender`; the treasury calls `swap` only from `_swapTokenPool`, whose parameters are
  entirely internal. Neither router is exempt.
- **`tax` can never exceed the output and cannot wrap.** `rate <= MAX_SPIKE_BPS = 9000` (enforced at
  `:126`) against a divisor of `1e4`, and `moved` derives from an `int128` pool delta, so
  `int128(int256(tax))` at `:204` is safe.
- **Rounding is always against the hook and toward the pool** (`tax = moved * rate / 1e4`, early return on
  `tax == 0`), so the Bunni class — rounding compounded across many small swaps — leaks nothing to the
  caller. The write-down in `_reconcile` rounds each role down and leaves the dust in the balance, where
  `:277` picks it up as ordinary revenue next sweep.
- **The OZ v4-core Critical (sync → mint-on-behalf → settle → take) does not apply.** The hook never calls
  `sync`/`settle`, and its only 6909 operations are on its **own** balance: mint to itself (`:202`), burn
  its own (`:243`), `take` exactly what it burned (`:244`).
- **`bal >= totalOwed` is an invariant**, and the ledger is kept by **role**, not by address.
  `_reconcile` (`:343-351`) restores it by writing down pro rata; `_pay` (`:354-369`) moves the ledger
  **before** the transfer and restores it on failure (the L4-1 fix, holding for all three roles
  independently); `distributeStock` computes new revenue as `bal - totalOwed`, never the raw balance.
  `_reconcile` cannot divide by zero (`bal >= totalOwed` returns early, so `totalOwed > bal >= 0` implies
  `totalOwed > 0`), and `totalOwed -= amount` is preceded by `amount = p + c + t` drawn from the same
  three variables.
- **Every state-mutating payout entry point is behind the `_distributing` latch** — `sweep` (`:212`),
  `distributeStock` (`:275`), `claim` (`:319`), `claimFor` (`:327`), `setProtocol` (`:401`),
  `proposeCreator` (`:409`), `acceptCreator` (`:434`) — the O4-1 fix, applied uniformly — and `payStock`
  additionally requires the latch to be **set** (`:449`), so the escape hatch cannot be called from
  outside a payout. `distributeToken` is deliberately outside it and touches only the token leg, whose
  token is a plain OZ ERC20 with no callback.
- **The token and stock legs cannot strand each other**: four independent `try`s in `unlockCallback`
  (`:223-226`).
- **The sweep split is arithmetically correct and the tip is taken off the top** (`tip` first, then `rest`
  is split), so it does not distort the three proportions. **EXECUTED** — 14.557 stock of claims became
  25 bps tip, then 1000 bps protocol / 500 bps creator / remainder treasury, to the wei; the token leg
  burned the claim minus 25 bps; `poolManager.balanceOf(hook, stockId) == 0` afterwards. `MAX_TIP_BPS =
  100` is enforced and the tip is paid only out of **new** revenue, so a second sweep in the same block
  pays nothing.
- **The creator takeover cannot be run on no notice.** `TAKEOVER_DELAY` 14 d, `ACCEPT_WINDOW` 14 d,
  `VETO_QUIET` 180 d, `pendingBy != msg.sender` forces a successor owner to restart (`:437`), and the
  creator can prove life with nothing pending (`:426`). All four match `docs/SECURITY.md:36` exactly.
  `acceptCreator` is **the only timing option in the codebase with both bounds** — every other function
  with a lower bound has no upper one.
- **`owner()` reverting does not brick the hook**: `afterSwap`, `sweep`, `claim`, `claimFor` and
  `vetoCreator` all still work (`AuditOwnerRound4.t.sol:256`).
- **"Vamping" is impossible**: every rate is immutable from the hook's constructor and the hook has no
  owner of its own; the only two things the factory owner can move are the two payout addresses.

## The observation ring

- **It cannot be starved at the window actually used, and this is the property the whole buy-back bound
  rests on.** `SLOTS = 1024` (`TwapRing.sol:26`) against `BUYBACK_TWAP_WINDOW = 600`
  (`StrategyTreasuryBase.sol:93`), with at most one write per second (`:51`), so a full ring always spans
  at least 1,023 s. **EXECUTED** (the lead's L-9 and the clean lane, independently): 3,000 one-per-second
  writes leave `meanTick(600)` **ok = true** with the mean exactly 0 for a symmetric flip;
  `meanTick(1023)` serves and `meanTick(1024)` does not; a pool with one observation an hour old serves
  `meanTick(600)` and returns that tick. **Therefore `meanTick` never returns to `false` after its first
  `true`.** The comments in both files (`TwapRing.sol:60-61`, `StrategyTreasuryBase.sol:434-437`, and
  `PoolTrader.twapPrice`'s at `:79-82`) describe eviction as a live risk; **at these constants it cannot
  happen, so the comments are wrong, not the code.** Two consequences, and the second is the real one:
  the `buybackAnchorSqrtP` drift mechanism is reachable only in the first 600 s of a pool's life (and
  needs a `takeProfit` inside that window too), so it is **effectively dead code** — which is fortunate,
  because its ratchet can otherwise lock out a token that appreciates more than `1/(1 − drift_cap)`; and
  `docs/SECURITY.md`'s "one cap-sized step per cooldown" describes only that dead branch (F-26).
- **Sample times are chosen by whoever trades, not by a sampler** (written from `afterSwap` on every
  swap), which is what the `poke()` failure mode in `TwapRing.sol:5-14` replaces.
- **The last write of a second wins** (`:51`, the HK-2 fix — V3's own rule), so a shove and its unwind
  inside one second leave **nothing** behind; held across one second boundary it carries exactly 1/600 of
  the window. **EXECUTED**, both, exactly.
- **A tick with no liquidity behind it is not recorded** (`StrategyHook.sol:182`), so a free walk to
  MIN/MAX through the empty side of the single-sided range writes nothing and pays nothing. **EXECUTED**
  in both orderings. (True of the ring; **not** of `_noteTokenSpot` — F-40.)
- **Negative means floor rather than truncate toward zero** (`TwapRing.sol:84`, and the same correction in
  `PoolTrader._meanTick` at `:93-97`), matching Uniswap's `OracleLibrary`. **EXECUTED** — a −599/600
  cumulative gives −1, not 0.
- **`int56 cum` cannot overflow**: `|tick| <= 887272` against int56's ~3.6e16 ceiling is ~1,287 years, and
  0.8 would revert rather than wrap.
- **`TwapRing` fails closed on a window it cannot serve** — five separate `return (false, 0)` paths — and
  **both consumers treat false as "no opinion" and refuse rather than substituting spot**
  (`StrategyTreasuryBase.sol:465`, `StrategyTreasury.sol:102`).
- **Manipulating the mean can only make the buy-back bound tighter, never looser**: `bound` is
  `max(fromMean, fromSpot)` for `zeroForOne` and `min(...)` otherwise (`:468-469`), and `_clampToSpot`
  turns an over-tight bound into a zero fill rather than a revert, which `buyback` converts to `NotDue`
  **without consuming the cooldown or firing the spike** (`:380`, `:384`, `:390`).
- **The buy-back anchor only ratchets toward cheaper** (`_noteTokenSpot`'s `better` test, `:341-344`) and
  `_swapTokenPool` re-notes **after** the swap, so a shoved fill cannot teach the anchor its own price.
- **The V3 `PoolTrader` refuses at construction a pool whose ring cannot serve the window**
  (`PoolTrader.sol:61-62`, `cardinality >= 660`), so the deviation gate can never silently degrade to
  spot-only. Measured 2026-09-21: all 11 candidate pools pass.

## The rule's accounting

- **`bookedStock == Σ lots[i].qty`** holds and is asserted exactly by the suite.
- **`takeProfit` conserves**: `bookedStock` falls by `q`, the balance falls by `principal + bounty`, and
  `buybackStock` rises by `q − principal − bounty`. Net zero against `unbookedStock()`. Walked
  independently by two lanes.
- **No undue lot can ever be sold**, and here is the line: the eligibility test reads `lots[id]` *after*
  every mutation in the call — `_book()` first (`:263`, push-only), then `Lot storage L = lots[id]`
  (`:264`), then `:267`/`:270`; `stopLoss` the same at `:293-294`. A shifted index either reverts or
  sells a lot that genuinely qualifies. (The *identity* of the lot is F-16.) The half-tranche path writes
  `L.half = true` **before** `_shrink`, and `_shrink` cannot pop in that branch since `q = L.qty / 2 !=
  L.qty` for any `qty > 0`.
- **No zero-quantity lot can exist**: `_book` refuses below `minLotUsdg` (`:250`) and `buyDip` refuses
  below it too (`:322`). **The one-wei-lot concern is therefore unreachable** — EXECUTED negative result,
  §7.
- **`buyDip` sizes everything off what actually filled, not what was asked** (`:315-323`) and refuses a
  dust fill, so a shover cannot be paid on an ask the swap could not fill and cannot burn the dip rung for
  a purchase that did not happen. Its tip is **independent of the price it fires at** (on `spent`), so the
  caller has no reason to time it badly.
- **`_swapStock` requires a full fill on every sale** (`StrategyTreasury.sol:137` pins `requireFull =
  !buy`; `StrategyTreasuryV4.sol:107` re-checks), which is what keeps `_shrink`'s already-written
  `bookedStock` reduction honest — and a dip buy may fill short, which is the invariant
  `StrategyTreasuryBase.sol:42-48` states.
- **`buyDip` cannot divide by zero** on `mulDiv(spent, _SCALE, got)`: the slippage check inside
  `_swapStock` reverts before `got` can be 0 with `spent > 0`, and `spent == 0` trips `NotDue` first.
- **`buyback` cannot spend more than the realised profit** (`amountIn = min(buybackStock, …)`), and
  **the impact cap is cumulative against the 600 s mean, not per chunk** — EXECUTED by driving the exact
  integer path: chunk 2 receives `limit/spot = 1.00000000`, `_clampToSpot` returns `sqrtP − 1`, the swap
  fills nothing, `:380` turns it into `NotDue`. **A 600 s hold cannot be harvested over ten 60 s
  cooldowns.** This is a genuinely good design and it was not stated anywhere.
- **`lots` is never iterated on chain** — every access is O(1) by index — so donating `minLotUsdg`
  repeatedly to spam lots buys an attacker nothing but their own gas. The only loops in scope are
  `TwapRing._atOrBefore`'s 10-iteration binary search and the calendar's two 14-bounded loops.
- **Every rule entry point is `nonReentrant`** (`:244`, `:260`, `:288`, `:308`, `:357`) **and every one
  pays its bounty last**, after all state is written (`:285`, `:305`, `:327`, `:386`). `launch` is
  `nonReentrant` too. The comment at `:239-243` records the exact bug this was added for (a bounty
  recipient re-entering `book` and having the profit booked twice, 111.26 against a balance of 105.63).
- **The action cannot be split to farm more bounty**: `buyDip` is one lot per `dipBps` rung because `:325`
  moves `lastSalePrice`; `buyback` is one chunk per cooldown; `takeProfit` is at most two tranches per lot.
- **`_swapKind` correctly disambiguates the two unlock consumers on V4** and pins V3 to the buy-back only.
- **With `bandBpsPerHour = 0` — the shipped state for every stock — no amount of pool manipulation can
  create or suppress a trigger.** `StrategyTreasury.sol:96-97` returns `(ok0, p0, false)` straight from
  `_health`, whose `p` is **Chainlink's** (`PoolTrader.sol:115`). **The pool is only ever a veto, never
  the price.** This is the single most important safety property in the rule and it holds byte for byte;
  it is also why the profit-based bounties need no manipulation bound.
- **No treasury outflow exists other than the four bounties and swap settlement.** `grep` over both
  treasuries and `PoolTrader` for `safeTransfer|transfer(|take(` returns exactly `:285`, `:305`, `:327`,
  `:386` (bounties), `:422` and `StrategyTreasuryV4.sol:140` (settle), `PoolTrader.sol:161-162` (the V3
  callback), and two `take`s back **into** the treasury. Holders have no claim on the treasury — and
  neither does anyone else, which is F-04's problem, not a flaw in this claim.
- **The scorecard's construction is honest and does not flatter.** `stockEquivalentHeld` marks the USDG
  reserve at the *current* price, so a treasury that sold into a rally shows the loss rather than hiding
  it, and the ratio correctly floors at `tp1/(1+tp1)` in an unbounded rally. Leaving the division off
  chain is the right call for a token with no redemption. The problem is the front page's *interpretation*
  of the number (F-11), not the number.

## The oracle and the calendar

- **`tryPrice` fails closed on all four legs** — calendar, `oraclePaused()`, both round sanity checks,
  both ages — and **every `try` has a `catch` that returns `(false, 0)`** (`PriceOracle.sol:50-58`).
  `_read` rejects a non-positive answer, a zero `updatedAt`, a future `updatedAt` and an over-age round.
- **`maxStockAge <= 48 hours` is enforced at construction with the reason in the source** (`:42`: "72h
  would serve Friday's close at Sunday's open"). Measured 2026-09-21: the weekend gap is **52.08 h**, so
  across a weekend the age cap and the calendar are **redundant** — a good property nobody had stated.
- **`lastPriceAt` keeps the USDG freshness gate while dropping the stock age gate, and still rejects a
  zero, negative or future round** (`:67-75`), and it is used **solely** by the band path, which is off by
  default.
- **No path prices anything off spot alone.** V3 requires spot **and** the 600 s mean to agree with
  Chainlink; V4 has no history to require but **every V4 execution limit is derived from the oracle**
  (`StrategyTreasuryV4.sol:103`), re-checked against the realised average at `:109`. So a pushed V4 spot
  can only open or close the gate; it cannot set the fill price.
- **The 40%-gap-open case holds**, and it is the case the design is proudest of: `_health` requires spot
  within 50 bps of Chainlink **and** within 50 bps of the pool's own 600 s mean, so a 40% gap fails both
  until pool and feed have agreed for ten minutes. No lot is realised at a stale price and no dip is
  bought at a phantom one. The rule waits, which is right.
- **The holiday rules are correct.** **EXECUTED** — New Year (2026 and 2027), MLK, Presidents, Good
  Friday, Memorial, Juneteenth, the Saturday-July-4 → Friday observation, Labor, Thanksgiving, Christmas;
  a Saturday Jan 1 does **not** close the preceding Friday (`:117-118`), matching NYSE practice; weekend
  Christmas/Juneteenth/Independence move to the adjacent weekday. The Easter computus cannot underflow
  (`32 + 2e + 2i − h − k >= 0`, `n >= 107`) and Good Friday is always in the `(m == 3 || m == 4)` window.
  `_sessionStart`'s two-pass DST derivation is correct and both loops are bounded at 14.
- **Round 3's `isScheduledClosure` regression is closed in both directions.** `:157-160` requires
  `override_[day] == 0 && dateClosedByRule(day)`, so `setOverride(day, 1)` halts on a weekend **and**
  `setOverride(day, 2)` cannot open the band path on a live day. EXECUTED. (What it *does* open is F-02.)
- **`bandCeiling` defaults to 0 and is enforced in four independent places**:
  `StrategyFactory.sol:214`, `:270`, `:364` (forcing 0 on V4), `StrategyTreasury.sol:35` and
  `StrategyTreasuryV4.sol:66`. **A treasury launched today can never trade a closure**, because its band
  is immutable at 0 — confirmed by two lanes. The residual is process, not code (F-03).
- **A halt does not trap value.** Holders have no redemption at all, so a halted treasury holds funds that
  were never claimable. Specifically checked and clean: a calendar halt does not touch the
  `<token>/<stock>` V4 pool (`afterSwap` never reads the calendar or the oracle; `sellRateBps` is pure
  time arithmetic), does not touch `TradeRouter`, and does not trap the hook's ledger (`claim(to)` pays to
  any address and needs no oracle, calendar or pool). The instinct is the opposite and the instinct is
  wrong.

## Tokens, routers, and the rest

- **Fee-on-transfer / burn-on-transfer / rebasing (the Balancer STA class) cannot be exploited here**: no
  path in scope derives an amount from a `balanceOf` **difference** across a transfer. The three balance
  reads are all "what is here now, split it", and a stock that under-delivered would cause the ledger to
  write down pro rata, which is the designed response. (The *requirement* on the asset is I-9.)
- **Donation / first-depositor inflation does not apply**: there are no shares, no redemption, no NAV and
  **no ratio anywhere for a donation to inflate**. A donation of stock to the treasury is booked as a lot
  at the oracle price; to the hook it is split or burned. The donor loses and nobody's accounting moves in
  their favour.
- **Circulating strategy-token supply is monotonically non-increasing** — no mint after construction, the
  token-side tax burned, buy-backs burned. **This is the unstated invariant that makes the pool's empty
  side unreachable after the first buy** (F-40) and it is asserted nowhere.
- **The launch-snipe mitigation checks out**: the sell spike's clock starts at **deployment**, so the
  first `spikeSeconds` of a launch carry up to a 90% sell tax and the opening-block sniper cannot dump.
  (What it does *not* do is F-07.)
- **Neither router can spend a third party's allowance**: `TradeRouter.buy` pulls `usdg` from
  `msg.sender` (`:71`), `sell` pulls the token from `msg.sender` (`:84`), `LaunchRouter` pulls the fee,
  the buy and the seed all from `msg.sender`. No path reads any other address's allowance —
  `docs/SECURITY.md:256`'s claim verified. **A standing allowance to a buggy router is spendable only by
  the approver**, which is what makes "deploy another router" a real remedy.
- **`TradeRouter` reads the pool key the strategy was born with, not today's defaults** (`_key(treasury)`
  → `IKeyed(treasury).poolKey()`, the key the factory wired once). The T5-2 regression cannot recur.
- **Both routers hold nothing between calls**: every amount moved is a computed delta, never a balance
  read, and both refund the exact residue. `LaunchRouter._fundFee` approves the factory for exactly the
  fee and the factory pulls exactly that, leaving no dangling allowance (the F-28 ordering case aside).
- **A stray `msg.value` on a non-native launch is refused rather than kept** (`:379`, `:386`).
- **`StrategyToken` has no owner, no mint, no pause, and a burn restricted to the caller's own balance.**
- **Nothing in `src/` is upgradeable.** EXECUTED grep for
  `delegatecall|selfdestruct|upgradeTo|initializer|Initializable|Proxy|_authorizeUpgrade` over `src/`:
  **zero matches**, across all twelve files.
- **The deploy script's Safe guard asks the question it means to**: `_requireSafe` rejects zero, the
  broadcaster, a code-less address, an **EIP-7702 delegation designator** (the 23-byte `0xef0100` check —
  the lesson from this chain), and a Safe with `threshold < 2`. Its own comment is honest that any
  contract can fake the two staticcalls.
- **No low-integer private keys anywhere in `test/`** — no `vm.addr`, no `vm.sign`, no `makeAddrAndKey`,
  no ECDSA, and nothing in `src/` verifies a signature, so the EIP-7702 delegation hazard that bites in
  fork mode does not exist here. **The repo is ahead on this**, and the guard is tested with `vm.etch`
  plus a fork test against the real delegated anvil-1 address.
- **`Params` and `Listing` auto-getters return every field**, including the nested `PoolKey v4Key` with
  all five components — EXECUTED against the generated ABI. A V4 listing is fully readable on chain.
  (A candidate finding that died on inspection.)
- **No `test_BUG_*` function remains** (EXECUTED grep: two comments, zero definitions), and **fork tests
  skip rather than vacuously pass**, with CI running them in a separate job. FA-11 is genuinely closed.
- **The `_shrink` swap-and-pop is genuinely well tested** — `InteractRuleMev.t.sol:271-292` builds three
  lots, has an attacker pop one, and asserts **by exact cost** that the last lot slid into slot 0 and that
  the victim's pending `takeProfit(0)` half-sold a lot she never chose; `:296-308` asserts the OOB variant
  as `stdError.indexOOBError`; `:313-333` sweeps every index × every whole price 96–118. The tests lane
  called it the best work in the suite.
- **Partial-fill coverage is strong**: V3 sell-must-fill, V3 dip-may-short, V4 both, cross-venue selector
  parity, the router's V3 hop, buy-back short fill, and the hook taxing only what moved — all present and
  selector-checked.
- **Depth and rule performance are positively correlated among the listable set** (corr(log10 D30,
  `d55_up`) = **+0.487**), so "deep pools only" does **not** trade safety against returns. The economic
  lane expected the opposite and recorded that it was wrong.

---


---

## Findings rejected, and why

Claims raised by a lane that did not survive. Recorded because a suspicion that was chased and disproved
tells the next round the ground is covered. The adversarial pass reviewed these too and overturned none,
noting one inconsistency (see `VERIFICATION.md`).


A lane claim I could not stand up is as useful to record as one I could. Nothing below reaches the
finding list.

### Rejected outright

**R-1 · L-3 (lead) and HX-10 (historical): `takeProfit` on a one-wei lot.** L-3 claimed `q = L.qty / 2`
gives `q == 0` for a one-wei lot, marking it half-taken while selling nothing and reverting inside the
venue swap; HX-10 reported the same as Info.
**Rejected — the lead retracted it himself with an EXECUTED negative result, and the reasoning is
correct.** `_book` refuses anything whose `_ruleValue` is below `minLotUsdg` (`:250`), and at the
harness's numbers the smallest bookable lot is **exactly 5e16 wei** (5e16 − 1 refused, 5e16 books). A lot
shrinks by `qty / 2` once and then fully, so `qty` can never reach 1 and the `q == 0` branch is
**unreachable**. `buyDip` refuses a dust fill too. HX-10 reports an unreachable path. Recorded here so
the next round does not re-derive it; the positive statement is in §6.

**R-2 · L-1 (lead), strong form: "the owner can substitute defaults underneath a pending launch."**
**Rejected, and falsified twice** — by the lead before triage (EXECUTED) and by me independently
(§5.11). Any change to any `Defaults` field changes the hook's init-code hash, the mined salt misses
`0x2844`, `StrategyHook`'s constructor reverts `BadConfig` and the launch reverts. **It does not execute
on new terms.** What survives is the much narrower F-05.

**R-3 · CL-7's mechanism: "`TreasuryDeployer` embeds `StrategyTreasury`'s creation code twice over."**
**Rejected, EXECUTED** — 22,418 − 21,581 = 837 bytes of deployer logic; two copies would be ~43 KB and
could not deploy. **Its conclusion survives** (2,158 B is the binding budget) and is used throughout; its
**proposed fix does not** — dropping `predict` saves ~837 bytes, not half the deployer. Recorded as I-16.

**R-4 · HX-1's trading-loss framing: "the treasury is the counterparty at a price the attacker chooses,
on an ordinary weeknight."** **Rejected as a value finding** — see §5.1. The premise (a 16 h-old print is
served as tradeable) is correct and measured. The conclusion is not supported: the feed publishes on a
0.5% deviation overnight, so a quiet feed bounds the error at roughly 1%; **and the repository discloses
the 10–18 h weeknight gap in the calendar's own file header** (`TradingCalendar.sol:18-20`) as the reason
the calendar exists. No lane measured the cost of holding a pool on a stale print for 600 s on a
weeknight against the deviation gate. It survives as a docstring correction (I-5, §5.1).

**R-5 · E-19's absolute D30 column.** **Superseded** by lane 08's exact tick-walk, by the coordinator's
two-`balanceOf` check and by my own reproduction — and by E-19's own stated falsification condition. Its
liquidity-*change* observation stands and is load-bearing (F-01 condition 3).

**R-6 · E-2's "the front page still advertises the opposite."** **Rejected as worded**, adopted as
narrowed. See §5.2. The substance becomes F-11 at Medium; the High grade and the concealment framing are
not supported.

**R-7 · C-01's, HX-2's and CL-12's Medium/Info grades for the calendar override.** **Rejected in favour
of High**, on C-01's own stated test. See §5.6.

**R-8 · C-04's and HX-3's Low grade and their `< 2` floor for `maxBuybackImpactBps`.** **Rejected** in
favour of Medium and CL-2's `< 20`. See §5.7.

**R-9 · The idea that the F-01 depth correction rescales every depth-derived number by 8–25×.**
**Rejected before anyone made it.** Only the +30% column is wrong by that factor; at ±0.5% and ±1%
constant-L errs 0.53×–1.35× and is not a bound in either direction. See §5.10 and F-34.

### Could not stand up — recorded as unproven rather than rejected

**U-1 · C-02's claim that `supply < 1e12` breaks the seed.** The clean lane's table asserts that at
`supply < 1e12` the `supply − supply/1e12` slack at `:421` is 0 and "the seed's round-up can exceed the
factory's balance, reverting every launch". **No lane ran it**, and the lane's own EXECUTED test only
demonstrates that `setDefaults` **accepts** `supply = 1`. The arithmetic is plausible — the manager rounds
what it is owed up and the slack is the only cushion — but a revert at launch is loud and recoverable,
which is a different severity from the silent items in F-05. **UNMEASURED; worth one test.**

**U-2 · E-5's magnitude: "0.09% of whatever the treasury spends" per buy-back sandwich.** The lane itself
names this as the finding most likely to be wrong in magnitude: its model is constant-product while the
real seed is a finite V3 range, and the figure is small enough that model error could flip its sign. Lane
08's finding that constant-L is not a bound in either direction at small moves makes that concern
concrete. **The magnitude is not stood up. The parameter relationship is** — the economically safe cap is
≈ 2.05 × `taxBps` against a factory ceiling of 1000, and `minTaxBps` has **no lower bound at all**, so
`taxBps = 0` is launchable and makes the launch-pool round trip free. That half is folded into F-05.

**U-3 · The historical lane's whole-codebase count (2 Medium / 5 Low / 5 Info).** Not a claim I can
reject, and not one I can use: it is that lane's coverage of its own exploit list, which the lane says
explicitly. Same for every other lane's count. The union is §2.

**U-4 · CL-1's "certain gain … 18% of gross sale proceeds to the protocol address."** Arithmetically
fine, but it is the same fact as F-05's `protocolBps` row combined with a decade-long `spikeSeconds` —
not an additional finding. **Folded, not rejected.**

**U-5 · Whether a weeknight Chainlink gap has ever exceeded 48 h.** The lead's sample is 30 rounds over
7 days and the longest weeknight gap in it is 16.32 h. **UNMEASURED, and it is the one thing that would
reopen R-4.** Worth the next round's time.

**U-6 · Whether weekend liquidity thinning is systematic.** Two snapshots 12.3–12.7 h apart show NVDA
−60.6%/−59.5% and AAPL −47.9%/−42.7% across a weekend closure — the exact window in which the band path
would run if a ceiling were ever raised. **One weekend is not a pattern. UNMEASURED, and per the economic
lane it is the single most valuable thing to measure before signing any `setBandCeiling`.**

**U-7 · The buy-back's impact on a genuinely single-sided seeded pool.** L-14's harness is two-sided.
The lead expects the real figure to be larger, which makes F-07's payoff bigger rather than smaller.
**UNMEASURED; needs a real seeded launch pool, and it is the first measurement the next round should run.**

**U-8 · The arbitrage bleed over a 600 s hold, on any pool.** Lane 08's round-trip column is the fee
floor, not the cost of holding against arb flow, which was not sampled. **UNMEASURED, and it must stay
labelled so in anything derived from lane 08** — it is the difference between "theoretically reachable"
and "economically reachable" for F-02, F-03, F-25 and F-27.

**U-9 · The chain's native token and its price.** Not established by any lane, and F-35 collapses to
nothing if it is cheap. **UNMEASURED.**

**U-10 · Robinhood-Chain equity feeds' `minAnswer` / `maxAnswer`.** **UNMEASURED** (I-5). Worth reading
before launch, because the mitigation for a clamped feed is incidental rather than designed.

---
