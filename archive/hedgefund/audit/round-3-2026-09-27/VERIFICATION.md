> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Verification — what was done to the findings after they were written

Part of [external audit round 3](./00-SCOPE.md). Companion to [`ISSUES.md`](./ISSUES.md).

Two independent reviews ran after triage merged the five sources, each by an agent that had done none of the
earlier work. Both are reproduced below in full and unedited, because what a review changed is only legible
next to what it said.

1. **An adversarial pass** whose standing instruction was that *every finding is a false positive until it
   produces an irrefutable code path*, told to attack the "checked and found safe" section and the rejected
   list as well as the findings. It re-measured every header number before trusting anything, rebuilt three
   candidate fixes byte by byte, and re-read all 18 pools at a fresher block. **It killed two conclusions,
   one of which the lead had promoted to the client as the round's most actionable result.**

2. **A review of this report's own rubric, framing and method**, given the baseline, the merged finding list
   and the lead's notes — and **deliberately not given the source code**. It is the only layer that can catch
   a bias built into the method rather than into a finding. Its first criticism is that the rubric measures
   whether anyone took money in a round where the new code is the first in this protocol to custody anyone else's
   assets; that criticism is now at the top of `ISSUES.md`.

Where the two disagreed, the lead settled it and said so — once in favour of the adversarial pass (I-11 was
a false positive, so the method review's criticism 4 is withdrawn) and once in favour of the method review
(M-0 does not belong at the head of the report).

**Names used inside the two reviews.** They are reproduced exactly as written, so they still refer to this
round's working papers by their internal names. `17-triage3.md` is the merged findings document, shipped here
as [`FINDINGS-FULL.md`](./FINDINGS-FULL.md). `BASELINE3.md` is the pinned baseline the four lanes worked
from; its scope, size table and rubric are in [`00-SCOPE.md`](./00-SCOPE.md) and `FINDINGS-FULL.md` section 1.
`00-lead-notes3.md` and `15-v2-economics.md` are the lead's notes and the economics lane's report, which are
not shipped — anything either of them is cited for is restated where it is used.

---

# Part 1 — the adversarial pass

# Adversarial pass — external audit round 3, target `17-triage3.md`, ref `03ad70e`, 2026-09-27

I ran none of the lanes and did not do the triage. My job was to falsify, one finding at a time. Every
finding was treated as a false positive until it produced a call path I could open and, where possible,
a number I could reproduce.

**Where I worked.** `…/scratchpad/adv3-scratch/{w1,w2,w3,fork}`. `w1` is a byte-verified copy of the PR's
`src/` at `03ad70e` (I hashed every file under `src/` against `git show 03ad70e:<path>` — no differences).
`w2` and `w3` are pristine copies used for mutation runs. `fork` is a standalone Foundry project for the
Robinhood-Chain V3 depth work. Everything was run with `--gas-limit 9999999999`. The read-only repository
at `/Users/daneil/Documents/app/side_project/hedgefund` was never modified and its branch never switched.

**Header numbers I re-measured before trusting anything else** (`forge build --sizes`, clean builds of both
refs, EXECUTED):

| | `7c3c137` (main) | `03ad70e` |
|---|---:|---:|
| `HedgeFunV2Factory` | — | 24,549 (**margin 27**) |
| `CurveDeployer` | — | 24,400 (**margin 176**) |
| `V2LiquidityVault` | — | 7,112 runtime / **8,233 initcode** |
| `HedgeFunV2Treasury` | — | 21,583 / 26,197 |
| `HedgeFunHook` | **18,481** | 19,354 (**+873**) |
| `HedgeFunFactory` | 18,929 / 22,676 | 18,929 / 22,676 (**byte-identical**) |
| `HedgeFunTreasury` | 18,289 | 18,344 (**+55**) |
| `TreasuryDeployer` | 23,501 (margin 1,075) | 23,556 (**margin 1,020**) |

All four of `BASELINE3.md`'s CORRECTIONS reproduce exactly. The hook is 18,481 not 18,362; the treasury
deployer's margin is 1,020 not 2,158; `HedgeFunFactory` is byte-identical at both refs; 18 stocks are
listed (I re-enumerated the `Listed` events myself, all 18 still `enabled`, block 73,816,151).

Full non-fork suite at `03ad70e` in a pristine copy: **1,410 passed / 1 failed / 1 skipped**, the one
failure being the obsolete isolation-harness control the baseline names. (Triage reported "51 skipped";
that is an artefact of a different path filter, not a discrepancy that matters.)

---

## 1 · Verdict per finding

### H-1 · High · the LP fee makes the 90% sell spike volume-gated and re-armable
**Verdict: CONCLUSION SURVIVES BUT SOME OF ITS REASONING DOES NOT. Mechanism CONFIRMED (EXECUTED).
Grade defensible at High only under an actor framing the report does not make; as written, its own
certain/option split argues Medium.**

**What I did.** EXECUTED. I re-derived the chain from the source first, then re-ran triage's five tests in
my own copy, then wrote four of my own (`w1/test/AuditAdv3.t.sol`, 4 passed).

*Re-derived by reading, independently of triage's wording:*
- `V2LiquidityVault.collectFees()` (`:91`) has no access control — first line is `if (!seeded)`.
- `:101-110` delivers the stock leg via `creditLiquidityFee`; `HedgeFunV2Treasury.creditLiquidityFee`
  (`:168-172`) is `msg.sender == liquidityVault`, pulls with `safeTransferFrom`, and does
  `buybackStock += amount`.
- `HedgeFunTreasuryBase.buyback()` (`:451`) is `external`, **not** `virtual`, and permissionless.
- `:464` `amountIn = Math.min(buybackStock, _ruleStockFor(chunkUsdg, p))`; `:474` the dust floor is
  `spent < Math.min(amountIn, _ruleStockFor(minLotUsdg, p))`. With a 1-wei pot both `min`s collapse to 1.
- `:484` `noteEvent()`. Hook `:289-293`: no-op inside `2·spikeSeconds`, else `lastEventAt = now`.
  `_sellRate` `:320-327`: `secs == 0 || last == 0 → tax`, else decaying `spikeBps`.
- V4 exact-input of 1 wei at `lpFee = 3000`: `amountRemainingLessFee = 1·997000/1e6 = 0`, so the pool takes
  0 in, returns 0 out, and `feeAmount = 1`. Hence `spent = 1, burned = 0` **by construction**, not by luck.

*Re-ran triage's tests (my copy, my build):* `spent: 1`, `burned: 0`, `sellRateBps after: 9000`;
end-to-end by an unprivileged caller with a 1-stock buy giving a `2999999999999999` wei stock fee (0.30%
exactly); victim out **0.100690033534210535** spiked vs **0.906210301807894814** flat, ratio **8.999**;
smallest buy producing a collectable fee **334 wei**, fee **1 wei**. Every figure in triage's H-1 reproduces.

*My own probes, which is where the reasoning breaks:*
1. **`spikeBps = 0` kills it entirely — EXECUTED** (`test_ADV_spikeBpsZeroKillsH1`). With the owner's
   Defaults at `spikeBps = 0`, the whole chain still runs (`spent = 1`) and `sellRateBps` stays **1000**.
   Triage says this; I confirm it is exactly true and costs zero bytes.
2. **`lastEventAt = 0` is NOT load-bearing — EXECUTED** (`test_ADV_h1DoesNotNeedLastEventAtZero`). After the
   first arming, `lastEventAt` is a real timestamp — precisely the counterfactual state that *not* zeroing it
   at `registerGraduatedWithVault:209` would produce — and the spike re-arms from it for one wei at +241 s.
   So E-11's merged "re-arming half" buys the attacker **the first 240 seconds after graduation and nothing
   else**. The merge is therefore *not* double-counting (good), but H-1's Mechanism paragraph and §5.2's
   sentence "`lastEventAt = 0` makes `noteEvent()`'s guard pass trivially, so **the first** `buyback()` after
   graduation arms the spike" materially overstate that line's significance.
3. The `Math.min` carve-out at `:474` is **pre-existing v1 code** — `git diff 7c3c137 03ad70e --
   src/HedgeFunTreasuryBase.sol` does not touch it. Triage never claims otherwise, but the report reads as
   though `:474` is part of what this PR did. What this PR added is the *inlet*, nothing else.
4. The one-wei fill's `bounty = bps(0, 50) = 0` and `burn(0)` both succeed — so the actor's **certain gain
   is zero**, which is triage's own text.

**What is wrong, specifically.**
- **The High does not map onto a rubric limb as written.** All three High limbs require either an actor who
  "takes or destroys" (limb 1, softened by conditions), a ≥600 s TWAP manipulation (limb 2), or the Safe
  breaking a documented promise (limb 3). Triage explicitly denies limb 1 ("Not Critical: the taker is not
  the caller") and then grants High on prose — "recurring, unprivileged, permanent transfer that needs only
  timing" — which is not one of the three limbs and is close to the Medium text ("a grief that degrades the
  product"). By triage's own certain/option split the *actor* holds only an option gain; the certain gains
  accrue to two passive recipients.
- **The framing that does reach High is never stated.** A **creator** running the bot on their own pool is
  an unprivileged actor with a *certain* gain (`creatorBps` of every sell inside the window), recurring,
  permanent, needing only timing. That is limb 1 with favourable conditions. The report names the creator
  only as a beneficiary. If the report wants High, it must name the operator.
- **"27.8% time-average" is an unexecuted behavioural model**, carried from v1's `AUDIT.md:461`, and it is
  what turns the creator's gain from "if someone sells into the window" into "certain". Triage labels it
  carried-forward, but then leans on it for the word *certain*.
- **The decisive condition is an owner dial that does not exist yet and costs nothing to set safely.**
  Every other graded finding in the report is anchored to something immutable at deployment (M-3's
  constants, M-2's curve arithmetic, M-1's coupling). H-1 alone evaporates on a `setDefaults` call. That is
  worth stating next to the grade, not only in the conditions list.

**What I could not falsify.** The mechanism, the 334-wei fuel threshold, the 9.0× seller loss, the 240 s
cadence, the one-wei degeneracy at `:474`, and the fact that `buyback()` is not `virtual` so v2 cannot
override it. All of that is solid and I would stake my name on it.

### M-1 · Medium · `collectFees()` couples its two legs; "the correct fix is 36 bytes over EIP-170"
**Verdict: coupling CONFIRMED (Medium stands). The headline structural conclusion — "therefore split
`CurveDeployer` in two" — is a FALSE POSITIVE. EXECUTED.**

**The coupling itself.** Read at the line and confirmed: `creditLiquidityFee` at `:106` runs before the
unconditional `HedgeFunToken(token).burn(tokenBurned)` at `:111`, one function, no `try`, and there is no
`collectTokenFeesOnly()`. The contrast with `HedgeFunHook.sol:460-469` and its comment is real. The vault
has no function that can move a pre-existing balance, so catch-and-abandon does convert a freeze into a
loss. All true.

**The byte arithmetic reproduces to the byte.** I rebuilt all three variants myself in `w1`:

| variant | vault runtime | vault initcode | `CurveDeployer` | margin |
|---|---:|---:|---:|---:|
| as shipped | 7,112 | 8,233 | 24,400 | **176** |
| inline `try … catch { stockFee = 0; }` | 7,118 | 8,239 | 24,406 | 170 |
| `try this.deliverStockFee(…)`, no retry | 7,274 | 8,395 | 24,562 | 14 |
| self-call + `uint256 public pendingStockFee` retry | 7,324 | 8,445 | 24,612 | **−36** |

Lane 13's table is exact. I could not shake a single byte of it.

**And then the conclusion falls over, twice.**

1. **The `−36` is an artefact of one keyword.** Making the retry accumulator `private` instead of `public`
   — i.e. dropping a getter nothing needs — gives `V2LiquidityVault` 7,290 / 8,411 and `CurveDeployer`
   **24,578: two bytes over**, not thirty-six. EXECUTED.
2. **`CurveDeployer.predictVault` is dead code on chain and pays for the whole fix.**
   `git grep predictVault 03ad70e` returns the definition (`src/v2/CurveDeployer.sol:122`), **one** caller —
   `test/V2DualEngine.t.sol:46`, a test — and two rows in `docs/REFERENCE.md`. Nothing in `src/`, `script/`
   or `deploy/` calls it; `executeGraduation` uses `deployVault`, never the prediction. Deleting it frees
   **51 bytes** (`CurveDeployer` 24,400 → **24,349**, margin 176 → **227**) because
   `type(V2LiquidityVault).creationCode` is still required by `deployVault` and is emitted once.
   With `predictVault` deleted and the *public*-getter retry variant in place: `CurveDeployer` **24,561,
   margin +15. It fits.** EXECUTED.

So the report's self-described "single most actionable structural result" — that M-1's only correct fix
requires splitting the graduation path into two modules, with the second module's address read from the
first because the factory has 27 bytes — **does not survive**. The fix fits after deleting a view function
that no non-test caller uses. This also dissolves the M-1 → I-14 link ("the most likely future change to
this system is the one that makes this untested control load-bearing"): the most likely future change no
longer requires separating deployment from seeding.

**A second defect in M-1's own analysis.** Condition 2 names three triggers — "the stock's registry
blocklists **the vault** or the treasury, or the stock/registry is **paused**". The proposed correct fix
addresses only the middle one. `unlockCallback` mode 2 calls `_take(key.currency0, fee0)` and
`_take(key.currency1, fee1)` at `:142-143`, and V4's `PoolManager.take` is
`_accountDelta(...); currency.transfer(to, amount)` — a plain ERC-20 `transfer` into the vault (verified in
`lib/v4-core/src/PoolManager.sol` and `src/types/Currency.sol`). A blocklisted **vault**, or a global
pause, reverts there, inside the `unlock`, **before any delivery leg exists to wrap in a `try`**. No
vault-side fix of any size helps those two cases; the token-side burn is stranded regardless. M-1's fix
table should say so.

**Grade.** Medium survives on the "permanent brick of one non-essential path" limb and on the repository's
own threat model. I would not raise it and I would not lower it. But the Fix section and the exposure
table's row 4 ("**NO** — 36 bytes over EIP-170 on `CurveDeployer`. Requires splitting it in two") must be
rewritten.

### M-2 · Medium · the raise is a ~$40k one-directional buy through the stock's only V3 pool
**Verdict: CONFIRMED, and independently re-measured at a fresher block. One headline number is stale and
one listing has moved to the gate's edge. EXECUTED.**

**What I did.** I re-enumerated the 18 `Listed` events from chain myself (block 73,816,151), read
`getDefaults()` on the live factory (`supply = 1e27`, `spikeBps = 9000`, `spikeSeconds = 120`,
`minTaxBps = 100`, `maxBuybackImpactBps = 300`, `bountyBps = 50`, `minLotUsdg = 5e6`,
`buybackChunkUsdg = 500e6`, `launchFeeAmount = 5e6` — every live figure triage quotes checks out), computed
`Rg = 4·openPriceE18·supply/1e18` per listing, and re-ran the exact-output swap and the 50-bps binary search
against **live pool state at block 73,817,759 / 73,818,xxx**, ~32,000 blocks after lane 15's 73,785,844.

| stock | lane 15 (73,785,844) | **mine (fresh)** | 50-bps budget, mine |
|---|---:|---:|---:|
| NVDA | +4 | **+1** | $459,039 |
| SPCX | +7 | +7 | $167,590 |
| GLD | +14 | +14 | $135,134 |
| USO | +19 | +19 | $105,792 |
| QQQ | +21 | **+22** | $88,900 |
| AMZN | +32 | **+33** | $54,206 |
| CRCL | +38 | +38 | $51,185 |
| **GOOGL** | +36 | **+49** | $38,688 |
| AAPL | +72 | **+75** | $28,431 |
| TSLA | +97 | **+98** | $21,565 |
| MSFT | +105 | **+114** | $20,969 |
| MU | +142 | +142 | $18,410 |
| META | +151 | **+162** | $15,251 |
| MSTR (gate 125) | +162 | **+164** | $12,322 |
| GME | +295 | **+279** | $13,100 |
| USAR | +1,060 | +1,060 | $1,107 |
| AMD | +1,200 | **+1,222** | **$2,984** (was $3,350) |
| **INTC** | cannot fill | **cannot fill — the swap reverts** | $3,529 |

**The structural claim is confirmed and got worse.** INTC's pool holds **285.48 INTC** against
`Rg = 330.80` — **115.9%**, not the 104% triage prints. The exact-output swap for `Rg` **reverts** on a
fresh fork; my run of lane 15's own `All18` test aborts at INTC with a custom error, and its `Rest7`
companion catches it and prints `REVERT — pool cannot supply Rg`. So: **the 317.71 figure in M-2's headline
is a stale level** (inventory fell 10.2% in 32,000 blocks), and the conclusion it supports is stronger than
stated.

**What is durable and what is a level, restated.** The ordering held across 32,000 blocks and the ten/eight
split held — but **GOOGL moved from +36 to +49 bps, one basis point under the gate**, so "ten of eighteen"
is really "ten, with an eleventh at 49/50". AMD's 50-bps budget fell another **10.9%** inside my own session
(the same instability lane 15 flagged at −36.7%/30 min). Only INTC's claim is level-independent, and only
because it exceeds 100% of inventory.

**One thing M-2 does not say that it should.** The `+1,222 bps` figure is a *single-transaction* fill of the
whole raise. The durable and much more plausible statement is the 50-bps budget column: **any single buy
over $2,984 on AMD, or $1,107 on USAR, breaks the gate** — no full raise required. M-2 leads with the
worse-sounding number and buries the more reachable one.

**Mechanism re-read.** `HedgeFunTreasury._priced()` runs `_health(maxDeviationBps)` first, which is spot
against **Chainlink** as well as spot against the 600 s mean. So a sustained pool deviation keeps the gate
shut until arbitrage closes it; the mean catching up does not re-open it. That makes the coupling limb
slightly stronger than M-2 argues, not weaker.

### M-3 · Medium · the enforced parameter floors are 6× and 11× wider than the author's own conclusion
**Verdict: CONFIRMED on the code limb; REASONED and single-sourced on the price limb. Grade stands.**

REASONED plus targeted reading. I verified every code fact: `MIN_SALE_BPS = 1000` / `MAX_SALE_BPS = 9000`
(`HedgeFunV2Factory.sol:22-24`); `DEFAULT_LP_BPS = 5000` / `MIN_LP_BPS = 1000` and `setLpBps` accepting
`1000..10000` with **no timelock** (`V2TreasuryDeployer.sol:48-49, 59-64`); `_onlyOwner()` resolving to
`IFactoryOwner(factory).owner()` — the factory owner, not a separate one; `lpBpsOfTreasury[a]` frozen inside
`deploy` at `:147`; consumed at `CurveDeployer.sol:79`; and `_terms` hashing `saleBps`, `virtualStock` and
`lpBps` on top of `super._terms` (`HedgeFunV2Factory.sol:74-79`), which is what makes triage's "the Safe
cannot retroactively thin a launched pool" correct and keeps this out of the High "docs promise" limb.
`_preflight` really does only check `amount ≥ 2` and `liquidity != 0` (`CurveDeployer.sol:60-65`).

I did not reproduce lane 15's `curve2.py` cascade table and I will not claim it. It is one model, one
author, agreeing with another model by the same author — which is the very defect M-4 raises about the
repository's own evidence, and the report should notice that its own M-3 price table has the same shape.
The *code* half stands on its own and is enough for Medium.

### M-4 · Medium · the v2 documents' quantitative evidence, and a 31%-wrong adversarial table
**Verdict: CONFIRMED to the digit (EXECUTED). Grade is generous but defensible.**

I ran `--mc V2AdversarialAccounting` at `03ad70e` myself:

| measurement | `docs/V2_ADVERSARIAL_REVIEW.md:55-64` | my run at `03ad70e` | drift |
|---|---:|---:|---:|
| burned, no preceding market buy | 792.0398009950 | **785.777795380060793897** | −0.79% |
| burned after the sustained price change | 507.4103585657 | **351.087042458652987126** | **−30.81%** |
| keeper token bounty | 2.5498007968 | **1.764256494767100437** | **−30.81%** |
| participant's stock after waiting and exiting | 91.6272208174 | **92.151211116568935290** | loss 8.373 → 7.849 |

Both currency orders agree to the last wei. The suite is green because the rows are `log_named_decimal_uint`
and the only assertions on them are `assertLt`/`assertGe`. All confirmed.

**Where I would push back.** The drift runs in the direction that understates the risk (the manipulation
is *more* effective and the participant's loss *smaller* than the doc says), which is what earns the Medium
disclosure limb — but `docs/V2_ADVERSARIAL_REVIEW.md:75-79` already carries an explicit, well-written
caveat that the scenario "does **not** establish that every tax rate, treasury balance, liquidity level,
holding period or coordinated strategy is unprofitable." A stale illustrative number inside a paragraph
that disclaims generality is closer to Low than the report allows. I would not fight hard for that, but the
report should quote the caveat it is grading against.

### L-1 · Low · the permissionless `graduate(id)` fallback can never fire
**Verdict: CONCLUSION SURVIVES BUT REASONING DOES NOT. Two of its three limbs are wrong.**

REASONED, from the source and the documents.

- **Unreachability: CONFIRMED.** `Status.Ready` is written in exactly one place
  (`HedgeFunBondingCurve._buy:128`), inside a `private` function whose one caller (`buy:112-115`) either
  graduates or reverts before returning, and `_graduate:139` requires `Ready`. Ready cannot survive a
  transaction. `graduate(uint256)` is dead code on the 27-byte contract. That half is right, and deleting it
  is the one fix in the report that *adds* factory margin.
- **The doc citation is wrong.** Triage cites `docs/V2_BONDING_CURVE.md:28` for the claim that "the docs …
  present a retry that does not exist". That line reads: *"The public `graduate(id)` entry point cannot
  graduate an Active curve early or release another curve's reserves."* — a correct **limitation**
  statement, not a promise. The only "fallback" claim anywhere is the NatSpec at
  `HedgeFunV2Factory.sol:133`, echoed verbatim into `docs/REFERENCE.md:1970`. `git grep 'graduate('
  03ad70e -- docs README.md` returns exactly those three lines. The finding survives on the NatSpec; the
  cited evidence does not support it.
- **"caps the curve for good with no retry" is wrong.** If `graduateCurve()` reverts, `buy()` reverts and
  the whole crossing buy rolls back; the curve is left below the cap with buys and sells open. **The
  crossing buy *is* the retry** — permissionless, repeatable by anyone, at any later time, and it will
  succeed the moment the blocking condition clears. There is no permanence beyond the blocking condition's
  own, and triage's M-1 condition 3 already records that permanence as UNMEASURED. What `graduate(id)`
  would add is graduating *without* a new buy, and there is no state in which that is needed.

Low is still the right grade, for the dead code and the NatSpec. The "permanent cap" paragraph should go.

### L-2 · Low · the scorecard numerator moves on a bare `transfer`
**Verdict: CONFIRMED, including its own load-bearing exclusion. EXECUTED on chain.**

`git diff 7c3c137 03ad70e -- src/HedgeFunTreasuryBase.sol` shows the exact change:
`bookedStock + buybackStock + _ruleStockFor(...)` → `bookedStock + buybackStock + unbookedStock() +
_ruleStockFor(...)`, with `totalStockReceived` still written in exactly one place (`_book`). The mechanism
is right.

Condition 4 is the one that keeps it Low, so I verified it on chain rather than accepting it: I read
`strategies(0..8)` off `0x58F6…A961` and took `EXTCODESIZE` of each treasury at block 73,828,153.
**All nine are 18,289 bytes** — the `main` build exactly — against `03ad70e`'s 18,344. The live
`TreasuryDeployer` embeds the 18,289 initcode, so future launches from the live factory also get 18,289.
This finding cannot reach the deployed estate, now or later. Low confirmed.

(While there I also confirmed H-1's condition 6: `buybackStock` reads **0** on all nine, and the
`bookedStock` multiset matches lane 15's exactly — 75.397 / 18.567 / 7.759 / 0.490 / 0.479, four zeros.)

### L-3 · Low · `maxBuybackImpactBps` vs the pool's round-trip friction
**Verdict: CONFIRMED as arithmetic; REASONED and single-sourced as an attack. Grade stands.**

I checked the invariant's algebra — `1 − (1−tax)²(1−lpFee)²` gives 199.0 bps at `tax = 100, lpFee = 0` and
**257.7 bps** at `lpFee = 3000`, both exactly as printed — and confirmed the live Defaults
(`minTaxBps = 100`, `maxBuybackImpactBps = 300`) from `getDefaults()` myself. I did not re-run `push.py`
and I do not endorse the per-cycle dollar figures. The structural point — that the owner sets the cap and
the creator sets the tax and nothing compares their product — is true by reading. The suggested 0-byte fix
(`minTaxBps ≥ 122` in the v2 Defaults) is the right shape and correctly avoids spending bytes on the
byte-identical v1 factory.

### L-4 · Low · unpaid, undeadlined `book()` after a failed graduation booking
**Verdict: CONFIRMED by reading.** `HedgeFunV2Factory.sol:150-153` is a real `try … book() … catch {}` whose
only output is the `treasuryBooked` boolean in `GraduationCapitalSplit`; `HedgeFunV2Treasury.book()` (`:46`)
is `public`, unpaid, no deadline; `_book` takes the health price as cost. The "caller chooses the round, not
the price" framing is right — the cost is Chainlink-gated, so capital cannot push it. Low is correct.

### L-5 · Low · vault addresses are predictable and donations are destroyed
**Verdict: CONFIRMED.** `V2LiquidityVault` sizes everything from arguments or the V4 delta and has no
function that can move a pre-existing balance — I re-read all 173 lines for this. One note: my M-1 result
proposes deleting `predictVault`, which removes the on-chain predictor but not the predictability (CREATE2
is computable off chain from `deployVault`'s initcode). L-5's substance is unaffected either way.

### L-6 · Low · the last tenth of every curve is negative-EV
**Verdict: accepted at Low; not independently re-derived.** I verified the terminal-price arithmetic
(`quoteBuy:95-101`, the `budget == capCost → newReserve = minTokenReserve` branch) and that only the
crossing buyer can graduate. The slice table is lane 15's model and I did not reproduce it. Triage's own
note — that this is the finding most likely to be re-graded by a reader who disagrees with "no leak, no
grief, no gain" — is honest and I agree with the Low.

### I-11 · Info · "`_minLpFee()` returning 1 makes the fee-only vault economically null"
**Verdict: FALSE POSITIVE on its central technical claim. EXECUTED.**

I-11 states: *"`collectFees()` returns `(0, 0)` on every call because `feeGrowthInside × L / 2^128` rounds
to zero — 7,112 bytes of settlement machinery realising nothing"*, and concludes *"at `lpFee = 1` the vault
is dead **and so is H-1's fuel line**."*

`test_ADV_lpFeeFloorStarvesTheFuelLine`, on the production contracts with `d.lpFee = 1`: a 100-stock buy
yields a collectable stock fee of **100000000000000 wei = 1e-4 stock**, and `treasury.buybackStock()` reads
exactly that. Control at `lpFee = 3000`: **3e17 wei**. Both are exactly `notional × lpFee / 1e6`. Nothing
rounds to zero.

The arithmetic I-11 starts from is right ($1M of volume on a $40k pool collects $1). The inference is not:
$1 spread over a $40k pool is a perfectly collectable fee, and the fuel threshold for H-1 simply moves from
334 wei of stock to roughly 3,000× that — about 1e6 wei, which is still 1e-12 of a share and still free.
**At the enforced floor the vault works and H-1 still has fuel.** I-11's remediation advice — "the
defensible positions are `lpFee = 1` with the vault treated as vestigial, **or** `lpFee = 3000` after H-1's
inlet is severed" — rests on a premise that does not hold, and the first of those two positions is not
defensible at all. The Info grade is unaffected (still no value impact); the content must be rewritten.

### I-13 · Info · the doc contradicts the compiler on the factory's margin
**Verdict: CONFIRMED.** `docs/V2_BONDING_CURVE.md:110-111` says "the factory sits 143 bytes under EIP-170";
my own build says 24,549, **margin 27**, which is what the same document's table at `:269` says. Every other
row of the `:258-267` table matches my build exactly, including `HedgeFunBondingCurve` 6,971 / 8,944.

### I-14 · Info · `V2LiquidityVault.seed`'s `onlyFactory` is covered by no test
**Verdict: CONFIRMED exactly. EXECUTED.** I deleted `if (msg.sender != factory) revert NotFactory();` from
`seed()` in a pristine copy and ran the whole non-fork suite: **1,410 passed / 1 failed / 1 skipped, the
same failing test, the same gas number (7,846,985)**. Byte-identically green. Zero of 1,412 tests cover the
access control on the function that seeds the permanently locked position.

**But the synthesis around it no longer holds.** I-14's punchline — "the most likely future change to this
system is the one that makes this untested control load-bearing", i.e. M-1's forced `CurveDeployer` split —
is void, because M-1's fix fits without a split (see above). The coverage gap is still real and still worth
one test; the tripwire story attached to it is not.

### I-17 · Info · "Multi-user sequences preserve … fee claims" is not tested
**Verdict: CONFIRMED on the substance; the supporting detail names the wrong file. EXECUTED.**

I rerouted 100% of the protocol fee to the creator in `HedgeFunBondingCurve.sell` (`claimable[creator] +=
creatorFee + protocolFee;`, protocol line deleted — sum-preserving, so `totalFees` and `_solvent` still
hold) and ran the review's own command:
`forge test --mc 'V2Adversarial(Accounting|Callbacks|Trading)Test' --fuzz-runs 512 --fuzz-seed 0x77`
→ **24 passed / 0 failed**. The claim at `docs/V2_ADVERSARIAL_REVIEW.md:39` is unbacked. Confirmed.

Triage adds: *"it turns 2 red in `V2CurveSecurity.t.sol`, which the review does not cite."* **That is
wrong.** `--mc V2CurveSecurity` under my mutation is **3 passed / 0 failed**. The full non-fork suite does
catch it — **2 tests in `test/BondingCurve.t.sol`** (`testClaimsIndependentAndSurviveGraduation`,
`testTaxedOutputCannotUnderpaySellerOrFeeRecipient`), 1,408/3/1. Right conclusion, wrong file.

### I-19 · Info · "roughly 100 stock of selling before the price halves"
**Verdict: CONFIRMED. I tried to kill this one and failed.**

My first reading had the pool at 200 stock × **800,000** FUN from `:77` ("a float of 800,000 FUN"), which
would have made lane 16's `k = 1.6e7` a 10× error. It is not: `:72` puts **80,000 FUN** in the pool and the
800,000 is the float held *outside* it. With `k = 1.6e7` the doc's own neighbours are exact — selling 8,000
FUN returns 18.18 stock and moves the price −17.4%; selling 80,000 returns exactly 100 stock and moves it
−75% — and the halving point is 33,137 FUN in, **58.58 stock out**, **82.84 stock of opening-price
notional**. Both below 100, and the error runs the wrong way for a disclosure. Lane 16 and triage are right.

### Other Info findings
Checked by reading at the cited lines and found accurately stated: **I-1** (`FLAGS = 0x2844` decodes to
`beforeInitialize | beforeAddLiquidity | afterSwap | afterSwapReturnsDelta` — no `BEFORE_REMOVE_LIQUIDITY`,
so the hook genuinely has no say over removals and the "immutable vault" header is doing unsupported work);
**I-2** (both suppressions confirmed, and see my ADV-4 above on how much the `:209` line is actually worth);
**I-3**; **I-4** (`seed()` before `wire()` in `executeGraduation:87-88` confirmed, so the brick is not
re-opened and only the record is false); **I-5**; **I-6**; **I-7**; **I-8** (`HedgeFunV2BuybackTreasury.book()`
at `:29-36` really does bypass `_book()`, and `V2TreasuryDeployer`'s constructor really registers only kind 0
at `:69-73`, so H-1's re-grade trigger is correctly stated); **I-9**; **I-10**; **I-12**; **I-15**; **I-16**
(my own count is 1,410/1, matching); **I-18**; **I-20**; **I-21**; **I-22** (`launchFeeAmount = 5e6` read off
chain myself); **I-23**.

---

## 2 · "Checked and found safe" — what I attacked, and what I would change

I went after the load-bearing ones by reading, and after three of them by execution.

**Hold, and I verified them myself:**

- **#1, #3, #4, #5 — the curve invariant and its rounding.** I re-derived it rather than re-running the
  fuzzer. Buy: `x' = ceil(K/(y+budget))`, `y' = y + (ceil(K/x') − y) = ceil(K/x')`. Sell:
  `y' = y − (y − ceil(K/(x+in))) = ceil(K/x')`. The invariant is re-established **exactly**, both sides, and
  `stockSpent ≤ budget` always because `x' ≥ K/(y+budget)`. Rounding pushes `y` **up**, which can only
  disadvantage a later buyer, never favour one. A same-block round trip returns at most `stockSpent`, and
  the buyer holds `gross − taxTokens` tokens, so it is strictly a loss. Safe.
- **#14, #15 — graduation cannot be double-triggered or nudged.** I checked the one thing that would break
  it: can `tokenReserve` skip past `minTokenReserve` without setting `Ready`? No. For any `budget < capCost`,
  `y + budget ≤ terminalStock − 1 < K/minTokenReserve`, so `ceil(K/(y+budget)) ≥ minTokenReserve + 1`. Only
  the `budget == capCost` branch, which hard-writes `minTokenReserve`, can hit the trigger. `release()`
  requires `msg.sender == factory` **and** `Ready` and writes `Graduated` before any effect. And
  `realStockReserve` at graduation is exactly `Rg = terminalStock − virtualStock`, path-independent — which
  is also why `_preflight`'s `lpStock` equals `executeGraduation`'s. Safe.
- **#18 — the delegatecall does not corrupt factory storage.** `BoundDeployer.factory` is `CurveDeployer`'s
  slot 0; in the factory's frame that slot is the owner. `executeGraduation` and everything it reaches
  (`_seedGraduation`, `_sendExact`, `_liquidity`) are memory-only or external; `SELF` is an immutable in
  code; `deploy`/`deployVault`/`factory()` are reached through `CurveDeployer(SELF).…`, so their storage
  reads happen in SELF's frame. There is no SSTORE on the path. Safe. *(Triage's phrasing "slot 0 … is only
  ever read, through an external call" is imprecise — in the factory's frame it is not touched at all.)*
- **#19 — `executeGraduation` is unreachable otherwise.** `address(this) != CurveDeployer(SELF).factory()`
  refuses a direct call (SELF ≠ factory) and a delegatecall from anyone else. Safe.
- **#24, #25, #26, #29 — "fee-only" is enforced by code.** `modifyLiquidity` appears exactly twice in the
  vault, once with `int256(uint256(liquidity))` where `liquidity` is a `uint128`, once with a literal `0`.
  No expression in the file can produce a negative delta; there is no owner, pause, upgrade or arbitrary-call
  surface; `_mode` is set before every external call and cleared after, so a stock callback re-entering
  `collectFees` gets `Busy`; and the hook's `FLAGS` gate `beforeAddLiquidity` through `liquidityVaultOf`, so
  no third-party position can exist to remove. Safe.

**What I would change in the safe list:**

1. **#46's "1.80% stop floor" is not a constant.** `PoolTrader.sol:56` sets `poolFeeBps = pool.fee() / 100`,
   and `V2TreasuryDeployer._validate:136` uses it. So the floor is `maxSlippageBps + poolFee/100 + bountyBps`:
   with the script defaults that is **155 bps on the seven 500-tier listings** (NVDA, SPCX, GOOGL, GME,
   AAPL, QQQ, GLD), **180 on the ten 3000-tier**, and **250 on MSTR**, whose pool is the 10000 tier — all
   eighteen `fee()` values read off chain by me. `docs/V2_DEPLOYMENT_REHEARSAL.md:33` states the condition correctly ("For a 0.30%
   V3 pool and the script's 1% slippage/0.50% bounty defaults"); **triage's restatement drops it** and prints
   "The documented 1.80% stop floor is **exact**". No live impact (KURA-MSTR runs 1200), but a creator
   reading the safe list would plan against the wrong number.
2. **The safe list does not notice that `CurveDeployer` carries 51 bytes of on-chain-dead code.**
   `predictVault` has no non-test caller anywhere in the repository; deleting it takes the margin from 176
   to **227** (EXECUTED). Given that the report's single most structural conclusion is built on that 176,
   what the 176 is really 176 *of* belongs in the safe list, not in an adversary's rebuild.
3. **#75 should state the gas-cap trap as a live CI risk, not a footnote.** `foundry.toml` at `03ad70e` still
   sets no `gas_limit` (I re-read it). Two of the three "known failures" only look like rule regressions
   because of it. That is the second round in a row this has been carried as an observation.

Everything else in the 75 I either verified or found no reason to doubt.

---

## 3 · Rejected findings I would restore

**None.** I went through all nineteen rejection rows and could not find one I would put back:

- The three test failures really are the toolchain — my pristine run reproduces 1,410/1/1 with the single
  obsolete isolation control, and the baseline's instruction not to report them is correct.
- The four size rejections (hook 18,362; `TreasuryDeployer` 2,158; vault 17,464; doc's 143) are all
  correctly rejected and I re-measured every replacement number myself.
- `registerGraduatedWithVault` → Info is right: `git grep registerGraduated -- src script deploy` returns
  one non-test call site, `CurveDeployer.sol:94`, whose `vault` is `deployVault`'s return ten lines above;
  `HedgeFunHook.bind()` (`:183-186`) is once-for-good; `_register:221` is once-only per pool and per
  treasury. There is no condition that can flip.
- `lastEventAt = 0` → Info is right, and my ADV-4 makes it *more* right: the line is worth 240 seconds.
- The four "no value impact" Lows → Info follow the rubric's own definition of Info.
- The hidden-removal-path hypothesis, the F-40 anchor-brick hypothesis and the v1-redeployment question are
  all correctly rejected, and I re-verified the last one by building both refs (`HedgeFunFactory` runtime
  **and** creation code byte-identical).

The one rejection whose *consequence* I disagree with is the `CurveDeployer` 176-byte one — not because 176
is wrong (it is exactly right) but because the report treats it as a hard wall when 51 of it is dead code.
That is a correction to M-1, not a restoration.

---

## 4 · My own suspicions, chased and disproved

1. **"Lane 16 got the curve doc's pool composition 10× wrong."** It did not — `:72` puts 80,000 FUN in the
   pool; the 800,000 at `:77` is the float held outside. I recomputed all four of the doc's figures and
   lane 16's derivation is exact. (I-19 stands.)
2. **"`tokenReserve` can skip past `minTokenReserve`, so `Ready` can be stepped over and graduation stalls
   silently."** Disproved by the inequality above: any sub-terminal buy leaves `newReserve ≥ minTokenReserve
   + 1`. The trigger is exact.
3. **"`predictVault` being external `view` on a delegatecalled module means `_at()` computes against the
   factory's address during graduation."** It would — `_at` uses `address(this)` — but `predictVault` is
   never reached inside the delegatecall, and `executeGraduation` uses `deployVault`'s return value, not a
   prediction. No bug. (It did lead me to the dead-code result, which is the M-1 kill.)
4. **"A v2 pool and the v1 pools on the same stock share the hook's per-stock `Pot`, so round 2's shared-pot
   lesson re-opens."** Disproved: v2 runs a **new hook at a new address** (19,354 bytes, different flags
   mining), so `pots` is separate storage. No cross-contamination.
5. **"The anchor pinned at `wire()` bricks the first buyback."** Disproved on the arithmetic:
   `_buybackLimitSqrtP` grows the allowance by one `maxBuybackImpactBps/2` per elapsed cooldown, and after
   ~600 s the hook's ring serves the window anyway. It delays, it does not brick. (Consistent with triage's
   rejection of the F-40 re-opening, reached by a different route.)
6. **"The curve's fee ledger can be drained by round-tripping `claimFees` across graduation."** Disproved:
   `claimFees` zeroes the entry before sending, keys on the recipient, and `_solvent()` requires
   `balanceOf(stock) ≥ realStockReserve + totalFees` before and after. `release()` moves
   `realStockReserve` only.
7. **"A blocked stock leg can be escaped by taking the fee straight to the treasury with
   `poolManager.take(currency, treasury, fee)`."** Disproved: V4's `take` is a plain ERC-20 `transfer` to
   the recipient, so it reverts on exactly the same blocklist. (This is what produced the M-1 fix-scope
   correction instead.)

---

## 5 · What I would stake my name on, and what is weakest

I would stake my name on **H-1's mechanism**, **M-2**, **I-14** and **M-4's numbers**. I drove H-1's
one-wei chain myself on the production contracts and it does exactly what triage says, down to `spent = 1,
burned = 0, sellRateBps 1000 → 9000` and a 334-wei fuel threshold; I re-measured M-2's eighteen pools on a
live fork ~32,000 blocks after the lane did and INTC still cannot supply its own raise, by a wider margin
than the report prints; I deleted `seed()`'s access control and the 1,412-test suite did not notice, to the
gas unit; and M-4's four drifted numbers reproduce to the last decimal. Those four are solid.

**The weakest finding in the report is M-1** — specifically its headline, which triage itself nominates as
"the report's single most actionable structural result." The byte table is perfect and the coupling is real,
but the conclusion drawn from them is false: the "only correct shape" is 36 bytes over only because someone
wrote `public` where `private` would do (that alone gets to −2), and deleting `CurveDeployer.predictVault`
— a view function with no caller outside one test — frees 51 bytes and lands the *unmodified* correct fix
at margin **+15**. "Requires splitting the deployer" should not survive contact with a rebuild, and it did
not. The same finding then proposes a fix that cannot help two of the three triggers in its own condition
list, because V4's `take` reverts into the vault before any delivery leg exists.

Close behind it: **I-11**, whose central sentence is simply not true of the contract it describes, and
**L-1**, two of whose three limbs are wrong (the cited doc line says the opposite of what it is cited for,
and the "permanent cap with no retry" ignores that the crossing buy is itself a permissionless retry).

And the grade I am least comfortable with is **H-1's High**. The mechanism deserves the attention; the
letter does not follow from the rubric as the report applies it. Triage says the taker is not the caller,
prices the caller's certain gain at zero, and then grants High on language that is closer to the Medium
text. There *is* a High in here — a creator operating the bot on their own pool has a certain, recurring,
permanent gain — but the report has to name that actor to claim it. As written, its own certain/option
split argues Medium, and the whole finding disappears on a zero-byte `setDefaults` call that the report
itself recommends.


---

# Part 2 — review of the rubric, framing and method

*Written without access to the source code, by design.*

# 19 · Confidence and method review — round 3 (the v2 PR), ref `03ad70e`, 2026-09-27

Scope: `BASELINE3.md`, `17-triage3.md`, `00-lead-notes3.md`, plus the lane files where a triage number had to be
traced to its source. **No source code was read.** Every finding's code path is taken as described; what is
examined is the grading, framing, emphasis, counting and method. Nothing below says a finding is wrong.

Ordered by how much each would change a reader's go/no-go decision.

---

## 1 · The rubric grades *extractability*, not *loss*, and the report never says so — which is why its largest measured buyer loss is a Medium

**What is wrong.** Count the Impact lines across all 34 findings:

| | count | severities |
|---|---:|---|
| a **certain** gain to some actor | **1** (H-1) | the only High |
| an **option** gain to some actor | **4** (M-2, L-2, L-3, L-4) | 1 Medium, 3 Low |
| **no gain to any actor** | **29** | 3 Medium, 3 Low, all 23 Info |

No finding with zero gain to any actor rises above Medium, and the one finding with a certain gain is the one
High. The report's own words do the work: M-3 is Medium because "the capital is not taken, it is *stranded*";
L-1 is Low because "**Zero value extractable by anyone**"; L-6 is Low because "the value is not taken, it is the
spread"; M-1 is Medium at "**0 / 0 — no value passes through**".

The rubric's Critical clause says "permanently **takes or destroys** … buyer funds". The report reads "destroys"
as requiring an actor who benefits from the destruction. That interpretive choice is the single most
consequential decision in the document and it is made silently, eleven times, in eleven Impact paragraphs.
Under the other reading — a buyer who loses 91% of their money does not care who got it — M-3 (up to **91.2% of
aggregate buyer capital** stranded at `MIN_LP_BPS`) is the most severe finding in the report, not the second
Medium.

This is the same structural critique a prior round of this track made when it found 32 of 41 findings reported
zero gain to any actor and concluded the rubric was the wrong instrument for a protocol with no redemption.
**It applies again, and harder**, because v2 *does* custody depositor funds: the curve holds buyer stock and the
vault holds the locked LP. The prior round's version could at least be defended as "there is nothing to take."
This round there is, and the grading still keys on whether someone takes it.

**Why it matters.** A go/no-go reader reads the severity column. That column currently answers "can someone rob
us?" — a question to which the honest answer is "essentially no, once" — and not "can a buyer lose their money?",
to which the answer in this report is "yes, in at least three distinct ways, up to 91% of capital."

**Change.** (a) Add one paragraph immediately after §1's rubric: *"'Destroys' is read throughout as requiring an
actor with a gain. Under the alternative reading — loss to the named loser regardless of who captures it — M-3
grades High, M-2's INTC limb grades High, and L-1 grades Medium. The client should say which reading it wants
before acting on the column."* (b) Add a **"buyer capital at risk"** column to §4 with a number in it, so the
ranking a reader acts on is not purely a ranking of extractability.

---

## 2 · The worst outcome for buyer funds in the whole report has no finding ID

**What is wrong.** "Buyer capital permanently locked in a curve that can never complete" appears three times,
each time as a subordinate limb of a finding about something else:

- **M-2**, Mechanism: "**INTC, where `Rg = 330.80 INTC` against a pool holding 317.71 — 104% of the entire
  inventory, so the exact-output swap reverts and an INTC curve can never graduate.**" EXECUTED, structural,
  and the one claim in M-2 the report says is independent of the depth snapshot.
- **M-4**, method defect 5: "the non-graduating state is permanent … no expiry, no refund, no owner
  cancellation … `status` stays `Active` forever … the only exit is a ~19.5% taxed round trip back into the
  curve **while the creator keeps collecting `creatorBps` of every one of those sells**." Graded as a
  *documentation* defect.
- **L-1**: "a blocked curve is **capped one wei short of the cap** … the reserve can never be released, the pool
  is never created and the treasury is never funded, with no operator and no permissionless action that
  completes it later." Graded **Low**.

There is no finding titled on this. It has no severity, no condition list with today's status, no loser line, no
fix, and it does not appear in §4's exposure table except inside M-2's row text. §5.4 even records the triage
decision that moved two of L-6's limbs out to "where they are measured" — which is how the limb became
homeless.

**Why it matters.** A reader triaging by ID and severity will never see the one outcome that would stop a launch
on a thin stock. The report's own structure hid its most consequential result.

**Change.** Promote it to its own finding — `M-5 · The non-graduating curve is a permanent, unrefundable,
uncancellable trap for buyer capital, and on at least one listed stock it is structurally unavoidable` — with
the three limbs as its mechanism, INTC as its EXECUTED instance, and its own grade. Cross-reference from M-2,
M-4 and L-1 rather than distributing it across them.

---

## 3 · M-1 (Medium) and L-1 (Low) share one precondition, and the Low is the worse outcome

**What is wrong.** The report states the shared precondition itself. M-1 condition 2: "The stock's registry
blocklists the vault or the treasury, or the stock/registry is paused." L-1 condition 2: "the realistic causes
are all the issuer's blocklist/pause on one of three external stock transfers — **same status as M-1's
condition 2**."

Same trigger. Different consequence:

| | M-1 — **Medium** | L-1 — **Low** |
|---|---|---|
| what is stranded | one fee cycle's token burn + the buyback budget | the entire curve reserve, permanently |
| recoverable if the block lifts | **yes** ("V4 fee growth is cumulative") | **no** — `Ready` cannot survive a transaction, so there is no retry |
| the treasury's ~50% of the raise | unaffected | never arrives |

M-1 is argued up to Medium on "the rubric's 'permanent brick of one non-essential path' is exactly the bitten
state." L-1 bricks the *essential* path with buyer money inside it and is graded a tier lower, on the ground
that "**Zero value extractable by anyone**" — criticism 1's bias, applied to the pair where it is most visible.

**Why it matters.** This is the cleanest demonstration in the report that the Medium/Low boundary is not
tracking consequence. If a reader believes the boundary is meaningful, they will fix M-1 (which the report says
**cannot be fixed within EIP-170**) and leave L-1 (whose fix is a *deletion* that gives bytes back).

**Change.** Either lift L-1 to Medium or add two sentences to L-1 saying explicitly why an unrecoverable
permanent cap on the essential path ranks below a recoverable freeze on a fee path. Do not leave the pair
unexplained when the report itself flags the preconditions as identical.

---

## 4 · H-1's condition 1 is stated as structural, and the report's own I-11 says it is false at the deployable floor

**What is wrong.** H-1, Conditions:

> 1. A nonzero static V4 LP fee. — **Structural, always true.** `_minLpFee()` returns 1 … so a v2 factory
>    **cannot** set it to zero.

I-11, in the same document:

> at `lpFee = 1` the vault is dead **and so is H-1's fuel line** … `collectFees()` returns `(0, 0)` on every
> call because `feeGrowthInside × L / 2^128` rounds to zero.

Both cannot be true. "Nonzero" is not the condition; "high enough that a collectable fee exists" is, and the
report's own analysis says that fails at the floor the v2 factory can actually be deployed with. The `334 wei
of stock` fuel threshold — repeated unqualified in §4's exposure table — was measured on a fixture at
`lpFee = 3000`; at `lpFee = 1` the report says the threshold is infinite.

So **both** of H-1's arming conditions are deployment-time dials:

| dial | H-1's status | the report's own recommended value |
|---|---|---|
| `spikeBps` | condition 3, **UNMEASURED** | **0** ("Zero-byte stopgap … should be the default posture") |
| `lpFee` | condition 1, "structural, always true" | `1` today, and I-11 says raise it **only after** the inlet is severed |

**Why it matters.** A reader of H-1 alone concludes the finding is unavoidable — one of its two conditions is
labelled structural and the other is buried at number 3 as UNMEASURED. The report elsewhere says both are
settable to values that delete the finding.

**Change.** Restate condition 1: *"An LP fee high enough to yield a collectable fee. **UNMEASURED** — the
deployable floor of `_minLpFee() = 1` makes `collectFees()` return `(0,0)` (I-11), which removes the fuel
entirely. All H-1 measurements were taken at the fixture's `lpFee = 3000`."* Qualify the `334 wei` figure as
fixture-and-`lpFee`-specific everywhere it appears, §4 included.

---

## 5 · Leading with a finding whose precondition does not exist — and what the report should lead with instead

**What is wrong.** The report's one High is conditional on a parameter that is not on chain, in a `Defaults`
struct nobody has written. The report says so honestly inside H-1 ("**The finding evaporates entirely at
`spikeBps = 0`**"), and then presents it as the headline severity, as §4's row 1, and as §2's count table's only
non-zero above Medium. §4's "armed when" cell reads "**block one of the first graduated pool, permanently,
recurring**" with the UNMEASURED condition dropped.

The deeper point: **the v2 `Defaults` do not exist, and they are where four of this report's eleven graded
findings actually live** — H-1 (`spikeBps`, `spikeSeconds`), L-3 (`minTaxBps` vs `maxBuybackImpactBps`), I-11
(`lpFee`), I-18 (`snipeSeconds`), plus M-3's owner dials. The single most consequential v2 artefact was not
available to audit, and the report never says that as a scope statement. It leads with a symptom of the gap
instead of naming the gap.

**Why it matters.** "There is one High" is what a go/no-go reader carries away, and it is not a statement about
the code as it will ship. Worse, it is *falsifiable by a one-line configuration choice*, which invites the
reading "ship it with `spikeBps = 0` and the audit is clean" — when the honest position is "the configuration
was not reviewable, so no configuration is certified."

**What the report should say instead.** Open with a short section before §2:

> **This round could not audit the deployment configuration.** No v2 `Defaults` are deployed. Every v2
> parameter in this report is a source constant at `03ad70e`, a live v1 value, or a rehearsal candidate. Four
> graded findings (H-1, L-3, I-11, I-18) are statements about parameters that do not yet exist. **The audit
> certifies no configuration.** Two constraints it does assert, both zero-byte and both pre-deployment:
> (i) ship `spikeBps = 0` **or** sever the LP-fee inlet into `buybackStock` — not neither;
> (ii) ship `minTaxBps ≥ 122` at `maxBuybackImpactBps = 300`.
> Re-audit is required on the Defaults, as a separate object, before launch.

Then keep H-1 where it is, with its conditional headline rewritten to carry the condition: *"**If v2 ships with
`spikeBps ≠ 0` and a real LP fee**, the sell spike becomes volume-gated and any caller re-arms it every 240 s."*

---

## 6 · Triage has no limitations section, and the lanes' own were dropped in the merge

**What is wrong.** `17-triage3.md` is 1,442 lines and contains no "what this round could not establish", no
"known weaknesses", no scope statement. Its two source lanes that wrote one had it discarded:

- Lane 15, *"What I tried to show and could not"* — seven items, including "I could not measure the sell-side
  behaviour of a real graduated launch … the single biggest gap in this lane", "I could not read the V2
  deployment's Defaults", "I did not execute E-1 end to end myself", "I could not price E-11 against a real V2
  pool", "do not size anything on this chain from active-tick liquidity, **including anything in this report
  that I did not execute**".
- Lane 16, *"What I could not measure"* — three items, the first of which is that **`test/V2LiveVenueFork.t.sol`
  was never run this round** and four documents' fork claims are therefore **UNMEASURED**.

Fragments survive (M-2's "two warnings", H-1's "what is still REASONED"), always inside a finding, never as a
statement about the round. And one dropped item comes back as evidence: **H-1's PoC line offers
`test/V2LiveVenueFork.t.sol:266-276, :333-335` as corroboration** — the test lane 16 recorded as unrun, written
by the author, which `BASELINE3.md` instructs the round to treat "as a hypothesis to test, not a settled
result."

**Why it matters.** The merge step is where an audit's honesty is usually lost, and it was lost here. A reader
sees 34 findings, 75 safe items and a reproduction command, and has no way to learn that the venue behaviour
of a real graduated launch was never observed by anyone, or that the author's fork suite was cited but not run.

**Change.** Add **§9 · What this round could not establish**, seeded verbatim from the two lane sections, plus:
the v2 Defaults; the deployment sequence and runbook; the front end that `V2_LP_DEPTH_EXPERIMENT.md:81` says
must show these numbers; the owner/Safe operational posture (no timelock on `setLpBps` / `setSaleBps`); and any
real sell-side behaviour. Strike the `V2LiveVenueFork` citation from H-1's PoC or label it "author's test, not
run this round."

---

## 7 · The report applies a standard to the author's evidence that it exempts its own from

**What is wrong.** M-4 is the report's method critique of the author's documents. Its five defects:
model-versus-model agreement "proves the same nothing"; "no price path, exogenous seller who always dumps
100%"; in-sample parameter choice; a control that is a deterministic negation of the one sample;
survivorship — every number conditions on graduation.

Now look at the report's own quantitative evidence. M-3's entire Medium rests on lane 15's `curve2.py` table —
which is a deterministic integer re-implementation of the same closed form, with no price path, an exogenous
seller who dumps 100% ("everyone dumping in the order they bought"), parameters read off the same sweep, and
every row conditional on graduation. L-6's grade, H-1's dollar impacts and I-22's "$361 per launch" come from
the same script. M-4 even names this and then does not draw the conclusion:

> "Lane 15's *third* implementation also agrees (13.38× vs 13.4×), **which proves the same nothing**."

M-3's own "What would overturn it" paragraph concedes the 100%-dump assumption honestly — which is exactly the
disclosure M-4 demands of the author and which appears in **one** of the four findings that depend on the model.

**Why it matters.** A reader will read M-4 as "the author's numbers are soft" and the Medium/High grades as
"the auditor's numbers are hard." They are the same class of number.

**Change.** Add one line to each model-derived finding (M-3, L-6, H-1's Impact, I-22): *"Model output —
deterministic, no behaviour, 100% dump, graduation-conditional. M-4's defects 2, 4 and 5 apply to this figure
too."* And soften M-4's framing from "their evidence is bad" to "neither their evidence nor ours is behavioural;
here is what would be."

---

## 8 · "0 Critical" is published with no statement of whether Critical was reachable

**What is wrong.** §2(a) leads with a table whose first cell is **0**. Nowhere does the report say whether the
tier could have been hit. It could have, this round, for the first time in the track: the rubric's Critical
clause names "**curve reserves**" and "**buyer funds**", and v2 is the first version that custodies either — the
curve holds buyer stock and `V2LiquidityVault` holds the locked LP. The Critical-candidate hypotheses were in
fact enumerated and tested, and they are sitting in §6 as safe items 1–13 (curve solvency, `virtual` stock never
payable, rounding direction, the whole float sold back, round-trip profit) and 24–33 (no negative liquidity
delta anywhere, callback data hashing, mode-2 principal assertion, donation immunity), plus 18 (delegatecall
storage integrity). That is a real negative result and the report buries it 1,100 lines below the count.

**Why it matters.** A reader cannot distinguish "we hunted for fund-taking on the curve and it is not there"
from "the instrument cannot emit a Critical." Criticisms 1 and 3 give them good reason to suspect the latter.

**Change.** One paragraph under the count table: *"Critical was reachable this round — unlike v1, v2 custodies
buyer stock (the curve) and locked liquidity (the vault), both named in the clause. The Critical hypotheses
tested and returned negative are safe items 1–13, 18 and 24–33. **0 Critical is a result, not a property of the
rubric** — subject to the two interpretive caps in criticism 1 and in H-1's 'the taker is not the caller'."*

Also flag that last phrase: "**Not Critical: the taker is not the caller**" is not in the rubric. The rubric says
an unprivileged actor takes or destroys funds; it does not require the actor to be the beneficiary. The report
adds a criterion in order to cap its own High, and should say it is interpreting rather than applying.

---

## 9 · Ten of thirty-four findings are not vulnerabilities, and nothing marks them

**What is wrong.** Graded on the same five-tier value-impact scale, with no class marker:

| what it actually is | findings |
|---|---|
| document review | **M-4**, I-13, I-15, I-16, I-19, I-23 |
| stale comments / records in code | I-4, I-5 |
| test-coverage hole with no exploit | I-14, I-17 |
| style | I-20 |
| context, not a finding | I-22 |

Plus doc-only *fixes* on L-5, and doc limbs inside M-2, M-3, L-2, I-2, I-6, I-12, I-18. One of the four Mediums
(M-4) is a review of the author's documents and modelling method. Inside Info, I-20 (an unannotated `assembly`
block, currently free) sits at the same grade as I-4, which the report itself calls "**the highest-urgency item
in the report at the lowest severity**" — three records of an invariant that are now false in *immutable*
bytecode.

The rubric offers no tier for "not a vulnerability", so everything is squeezed into value-impact tiers and Info
ends up doing four unrelated jobs.

**Why it matters.** "34 findings: 1 High, 4 Medium, 6 Low" will be quoted, in a summary, to someone who never
opens the document. They will believe those are code defects. The code-defect yield of ~1,458 new lines is
actually: **1 conditional High, 2 code Mediums, ~5 code Lows** — a good result, and the report never gets credit
for it because it is mixed with the documentation review.

**Change.** Add two fields to the finding header — `Class:` (CODE / DOC / TEST / PROCESS) and `Action:`
(BLOCKING / PRE-DEPLOY / BACKLOG), the latter independent of severity — and a second count table in §2 broken
down by class. Say the code yield in one sentence.

---

## 10 · The severity labels invert under the report's own recommended remediation

**What is wrong.** The report establishes that M-1's only correct fix is 36 bytes over EIP-170 and therefore
"**requires exactly the `CurveDeployer` split that would separate deployment from seeding**" — after which
I-14's untested `onlyFactory` guard and I-1's missing vault validation become load-bearing (I-14: "the most
likely future change to this system is the one that makes this untested control load-bearing"; §4 row 12 says
both "become load-bearing if `CurveDeployer` is split").

So the expected remediation path converts two **Info** items into live security controls. A reader triaging by
severity fixes the Medium and skips the two Infos — precisely the sequence the report warns against, invited by
the labels the report assigns.

**Why it matters.** This is the one place where acting on the report's own severity column produces the outcome
the report's own analysis says is dangerous.

**Change.** Add a short **"Conditional severities"** block after §4: *"If `CurveDeployer` is split (M-1's only
correct fix), I-1 and I-14 become Medium and must be fixed in the same change. If strategy kind 1 is ever
registered, H-1 re-grades. If `_minLpFee()` is raised above 1, H-1's condition 1 becomes true."* Three lines; it
makes the label column safe to act on.

---

## 11 · "13 prior conclusions invalidated" inflates novelty; none of the 13 changes anything about the deployed system

**What is wrong.** §2(c) is titled "Prior-round conclusions this PR invalidates — **13**". It is two different
things stacked:

- **Six "conclusions no longer true as written."** Read each one against the deployed estate. #1 — "true of
  `HedgeFunFactory` only … EXECUTED"; the v1 conclusion still holds, the *generalisation to the base* does not.
  #2, #3, #4 — all describe behaviour of **new v2 subclasses**; the v1 statements remain true of v1. #5 — true
  of the edited source, but L-2's condition 4 says it "does not reach a live treasury" because the deployed
  treasuries carry pre-PR code. #6 — "**does not carry to v2**", explicitly.
  So all six are *"the prior conclusion remains true where it was made and does not carry to new code"*, which is
  the normal consequence of adding nine contracts, not invalidation. The report confirms this itself in §4:
  "**no finding in this report reaches any of** [the nine live strategies]."
- **Six "proofs invalidated while the conclusion survives."** By their own heading, these are not conclusions
  invalidated. They are counted in the 13 anyway.

**Why it matters.** "13 prior conclusions invalidated" is the number that will justify this round's cost and
that will be read as "the prior audits are unreliable." The supportable claim is narrower and more useful: the
*proof routes* decayed, which is an argument for re-deriving rather than carrying — exactly what the report did,
and should get credit for.

**Change.** Retitle §2(c) as "**Prior-round statements re-examined — 13**" with a class column:
`does not carry to new code (6)` / `proof route replaced, conclusion re-derived (6)` / `watch-list trigger fired
(1)` / `invalidated for the deployed estate (0)`. Add the sentence: "**Zero of the thirteen changes anything
about the nine live strategies.**"

---

## 12 · The report twice warns that a prior "checked and found safe" is what nobody re-reads, then publishes 75 of them with no invalidation triggers

**What is wrong.** §2(c) opens: "These are the dangerous ones: a previous round's 'checked and found safe' is
exactly what nobody re-reads." §6's preamble is: "Every item carries the line that makes it safe. Deduplicated
across all five sources." No ref pin on the section, no decay statement, no per-item trigger.

And the report contains the proof that triggers work. Round 1's F-40 is the **only** prior-round artefact that
carried an explicit watch-list — "*any future change that mints a strategy token, adds a second liquidity path,
or seeds the anchor at `wire()` re-opens it*" — and it is the **only** prior conclusion this round caught
mechanically rather than by luck (I-4). The mechanism is demonstrated in the document and not applied to the
document's own output.

Several safe items are already one PR from false and say so implicitly: item 24 ("no expression … can produce a
negative liquidity delta" — depends on `V2LiquidityVault` not gaining a function); item 29 (depends on
`_onlySeed` routing through `liquidityVaultOf`); item 59 (byte-identity with `main`, which L-3, I-10 and I-18
each propose spending); item 62 (`_seeding` staying `private`); item 65 (no migration primitive); item 54 (the
128-lot gas bound).

**Why it matters.** This is the highest-leverage single change available to the report, because it is the defect
the report itself diagnosed in rounds 1 and 2 and then reproduced.

**Change.** Head §6 with: "**These 75 items are true at `03ad70e` and nowhere else.**" Give each item an
`invalidated by:` line in F-40's format. Where an item's guarantee rests on something becoming `virtual`,
`public`, non-unique, or on a grep count, name it — the report already knows which six those are, because they
are §2(c)'s second table.

---

## 13 · M-2's two counts do not reconcile, and the classification sits inside its own measurement noise

**What is wrong.** Inside one finding:

- Mechanism: "**Ten of eighteen** listings are thin: AAPL +72 bps, TSLA +97, MSFT +105, MU +142, META +151,
  MSTR +162 (gate 125), GME +295, USAR +1,060, AMD +1,200, plus INTC."
- Fix: "At the shipped '$10k opening FDV' convention that is **violated on seven of eighteen** listings today."

Same rule, same block, same gate, two counts, no reconciliation. It is inherited unexamined from lane 15
(`15-v2-economics.md:970` says ten, `:324` says seven) and triage carried both without noticing.

Second problem in the same finding: the report measures that **AMD's 50 bps budget fell 36.7% in ~30 minutes**
and correctly says only the *ordering* is durable — and then states the classification as a count and prescribes
per-listing open-price divisors ("on AMD … by ≈13, on USAR by ≈34") off the snapshot. A −36.7% move on the
budget is ×1.58 on price impact; the inverse move is ×0.633, which takes **AAPL from +72 bps to ~46 bps, below
the 50 bps gate**. At least one of the ten flips inside the intraday range the finding itself measured, and
TSLA (+97) and MSFT (+105) are within 2× of it.

**Why it matters.** The Fix is a **listing rule**. Someone will apply it. They cannot currently tell whether it
blocks seven listings or ten, or whether a listing near the boundary is blocked at 10:00 and permitted at 10:30.

**Change.** Reconcile the counts and publish the per-listing table (stock, `Rg`, measured 50 bps budget, impact
bps, gate, verdict) with the block **and** the wall-clock time of each swap. State the verdict as a band —
"seven listings fail at any time of day; three more fail at the measured depth and are inside the intraday
range" — and make the rule a *live* check at listing time, not a stored table.

---

## 14 · H-1's creator-impact figure contradicts the report's own I-22 by 3.3×, and its Impact section cancels itself

**What is wrong, part one.** H-1, Impact: "**creator — certain gain** (30% of a take that goes from 3% to ~27%
of gross)." Both available parses are wrong against the report's own arithmetic. I-22, same document: the hook
take at the flat 10% is 1,789 USDG, creator 534; "**Under H-1's re-armed spike those become 990 and 1,485**".
534 → 1,485 is **2.78×** — the creator goes from **2.98% of gross to 8.3% of gross**, not 3% → 27%. (27.8% is
the *hook's* time-averaged tax rate, of which the creator takes 30%. Lane 15 made the same slip at its summary
table, `15-v2-economics.md:896`, and its own Impact paragraph at `:198-201` has it right.)

The natural reading of H-1's sentence overstates the creator's gain by **3.3×**, and it is in the Impact
paragraph of the report's only High.

**What is wrong, part two.** The same Impact section says both of these:

> "Loser: **every FUN holder who sells** … measured at 1/9.0 of their proceeds inside the window, which is half
> of all wall-clock time"

> "A 120-second **soft trading halt**: a router sell with a sane `minFinalOut` **reverts rather than filling**."

If protected sells revert, no value transfers and the creator's and protocol's "**certain** gain" does not
occur; the harm is a recurring grief. If they fill, the transfer happens but only for sellers with no slippage
protection — **UNMEASURED, and unmeasurable before launch**. The report asserts both the grief and the certain
transfer and grades on the union. `sellRateBps(id)` is a public view, so the window is observable.

Third: the 50% duty cycle needs someone to call `collectFees` + `buyback` ~15 times an hour, indefinitely, for a
bounty triage itself measured as **zero at the one-wei floor** ("`spent = 1`, `burned = 0`"). The report never
names who sustains it or what pays for the gas.

**Why it matters.** These are the three sentences a summary of this report will be built from.

**Change.** Correct the creator line to "from 3.0% to 8.3% of gross (2.8×), on the 27.8% v1 time-average, which
is model-carried and not re-derived at v2 parameters." Split the Impact into **(a) certain**: a recurring
120-second soft halt at a 50% duty cycle, plus an exit-ordering option available to anyone for gas; and
**(b) conditional on unprotected sell flow existing — UNMEASURED**: the 1/9.0 transfer to protocol and creator.
Name the sustaining actor, or say that the only party with a standing incentive to pay for the re-arm is the
creator.

---

## 15 · The four-lane arrangement systematically misses ordinary bugs in the new code, and nothing in the report is a coverage claim

**What is wrong.** Three things compound.

1. **No lane was context-free.** All four received `BASELINE3.md`, including its section "**What this PR does to
   ground rounds 1 and 2 had cleared**" — four numbered pointers. Three of the four map straight onto the
   report's output: pointer 1 (`lpFee` no longer forced to zero) → H-1, I-10, I-11; pointer 2 (the hook's second
   liquidity path) → I-1, I-3, safe items 21–29; pointer 3 (the base going `virtual`/`public`) → I-6, I-7. Prior
   rounds ran a source-only lane; this round did not. The lanes differ by *scope* (v2 surface / v1 delta /
   economics / doc claims), not by *prior*, so their agreement measures visibility, not correctness — which §5.5
   says, correctly, and then does not extend to the inverse: **non-convergence on a class means nothing sampled
   there.**
2. **No source claims to have read the 1,458 new lines.** The strongest coverage sentence in the document is
   triage's "reads of every line **cited in a merged finding**" — coverage of the findings, not of the code. There
   is no coverage matrix anywhere in the round.
3. **One model family wrote the contracts, the ten `docs/V2_*.md`, the author's two reviews, all four lanes, the
   lead notes and this triage.** The report's own instruction — "*They were written by the same author with the
   same model family. Where one says something is safe, find the line*" — is applied to the author and not to
   the audit. Six correlated samples are presented as five independent sources.

**The class of problem this arrangement misses**: ordinary implementation defects in new code that nobody
hypothesised — decimal/unit mismatches between the stock token and USDG, storage packing and slot collisions
across the `virtual`-ised base, event/indexer correctness, ERC-20 non-standard return handling outside the
paths that were grepped, and initialisation/ordering in the *deployment sequence*. On that last one: the
deployment runbook is reviewed by exactly one Info (I-21, `bind()` griefing, explicitly "a restatement, not a new
class"), on a system where two contracts ship with 27 and 176 bytes of margin and cannot be fixed afterwards.
No lane audited `script/RehearseV2Launchpad.s.sol` or the deploy ordering as an artefact.

**Why it matters.** §6's 75 items will be read as coverage. They are 75 hypotheses that came back negative.

**Change.** (a) Publish a coverage matrix — nine contracts × line ranges × which lane read them — and say
plainly which ranges no lane read. (b) Before ship, run one **cold lane**: the nine contracts, the rubric, and
nothing else — no baseline pointers, no prior rounds, no author documents. (c) Add one sentence to §5.5: "All
sources in this round share one baseline and one model family; convergence is visibility, and divergence is
coverage, and neither is correctness." (d) Add a deployment-sequence lane, or say the runbook was not audited.

---

## 16 · Four things a reader will reasonably conclude that the report does not support

1. **"Fix the High and ship."** The report takes no position on go/no-go, never states what it did not review
   (criterion 6), and its High is configuration-conditional (criterion 5). Add a one-paragraph **verdict** with
   an explicit list of what must be true before deployment, and an explicit "this audit does not cover X".
2. **"75 items checked and found safe" = the code is covered.** See criterion 15. Rename §6 "**75 hypotheses
   tested and returned negative, at `03ad70e`**" and add the invalidation triggers from criterion 12.
3. **"Fix fits? — yes" (11 of 13 rows in §4) = these are cheap.** The report's own framing says the opposite:
   `HedgeFunV2Factory` at 27 bytes "can **never** receive a fix", and a change after deployment means a new
   factory, new hook, new deployers and a fresh Uniswap routing-allowlist submission, with launched strategies
   stranded. Rename the column "**fits — if applied before deployment; there is no after**".
4. **The system around the contracts was reviewed.** It was not: the Defaults, the deployment runbook, the
   launch UI that `V2_LP_DEPTH_EXPERIMENT.md:81` instructs must show M-4's graduation-conditional numbers, the
   owner posture (`setLpBps`/`setSaleBps`, **no timelock**, per M-3 condition 2), and the keeper. On an immutable
   system these are the remaining degrees of freedom, and they are where four graded findings actually live.

---

## What I would credit, since a method review that only criticises is not calibrated

- **§5 is the strongest part of the document.** Disagreements are resolved by re-running the evidence, not by
  averaging sources or by counting confirmations, and §5.3 says out loud that "two readings of the same lines are
  one route, not two" and then *executed* rather than settling. §5.4 takes four findings **down** against the
  lanes' own impact lines. That is the right direction of pressure and it is rare.
- **The byte-budget frame (§1, from R3-L6) is correct to put in front of the findings**, and the `CurveDeployer`
  trap (176 bytes hidden behind two contracts each reading ~17.5 kB free) is a genuine and repeatable result that
  changes what "the fix is easy" means everywhere in the report.
- **The deployed-estate conclusion is well supported** — three independent routes to "v2 deploys alongside v1
  and asks nothing of it", one of them byte-identity of the live factory against both refs.
- **The baseline corrected itself mid-round in public** (the hook's 18,481, `TreasuryDeployer`'s 1,020, eighteen
  listings, no v1 redeploy), and §7 carries the lead's own wrong numbers in the *rejected* table under the
  lead's name. Most reports quietly fix those.
- The report repeatedly declines to grade on preconditions it has not measured (M-1 condition 3, L-4 condition 1,
  L-5 condition 2 all say UNMEASURED rather than guessing).

---

## The two or three sentences I would add to the report's "known weaknesses", if only that much

> **This report grades extraction, not loss.** Thirty-three of its thirty-four findings identify no actor with a
> certain gain, and the tiers below High are assigned on that basis — so a Medium here can mean 91% of buyer
> capital stranded (M-3) or a curve that can never complete with buyers' money inside it (M-2, L-1), while the
> single High is a redistribution of fee revenue among the protocol's own designed recipients. **No v2 `Defaults`
> exist, so the configuration in which H-1, L-3, I-11 and I-18 actually live was not auditable; this round
> certifies no configuration, and the High evaporates at `spikeBps = 0`.** The 75 "checked and found safe" items
> are hypotheses tested at `03ad70e` by six sources that share one baseline and one model family — no lane read
> the nine new contracts cold, none claims line-by-line coverage, and the next PR will invalidate this section
> exactly as this round invalidated the last two.
