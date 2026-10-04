> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Findings — external audit round 3: the v2 pull request

Branch `codex/v2-main-integration` @ `03ad70e`, audited 2026-09-27. Scope, the live deployment, the
remediation budget and the test-state trap: [`00-SCOPE.md`](./00-SCOPE.md). Method and corrections:
[`README.md`](./README.md). The adversarial pass and the no-source method review, in full:
[`VERIFICATION.md`](./VERIFICATION.md). Every finding written out in full, with the rubric, the safe list and
the rejected list: [`FINDINGS-FULL.md`](./FINDINGS-FULL.md). Everything marked EXECUTED below is reproducible from
[`poc/`](./poc/) — `poc/run.sh` runs 32 offline tests against a checkout of the PR, and
`poc/fork/run-fork.sh` re-measures the live pools behind M-2 and M-3.

---

## Read this before the counts

**1. The rubric measures whether anyone *took* money, and the thing worth worrying about here is whether
anyone *loses* it.** Of the 35 findings, **29 report zero gain to any actor, and not one of those reaches
above Medium.** The Critical clause reads "takes **or destroys**", and this report has repeatedly been
reading "destroys" as requiring a beneficiary — "stranded, not taken", "it is a spread, not a transfer".

Round 2 raised the same objection and it was softer then. **V2 is the first thing in this protocol that
custodies other people's assets**: the bonding curve holds buyers' stock until graduation, and the vault
holds the locked LP. V1's treasury never had a claimant. So the tier that cannot be reached is now the tier
that matters, and **"0 Critical" this round means less than a reader will assume** — not because the code is
bad, but because the instrument does not measure the failure mode this product actually has.

**2. The deployment configuration was not audited and cannot be.** No v2 `Defaults` exist on chain. Four
graded findings live inside parameters that have never been set, including the one whose mechanism is the
most interesting in the round. **This audit certifies no configuration.**

**3. Roughly ten of the 35 are not vulnerabilities** — documentation that contradicts the code, stale source
comments, test-coverage holes with no exploit, a byte budget. They are graded on the same scale for their
consequence on an unpatchable system, and each is marked. The code-defect count is **four Mediums and about
five Lows**.

## Counts

| | Critical | High | Medium | Low | Info | total |
|---|---|---|---|---|---|---|
| **everything in the PR** | **0** | **0** | **6** | **6** | **23** | **35** |
| only new in `src/v2/` | 0 | 0 | 4 | 4 | 8 | 16 |

Derivation, so it can be checked: triage merged the four lanes and the lead's notes into 34 (0/1/4/6/23). The
adversarial pass and the method review then moved two things and the lead settled both — **H-1 from High to
Medium**, and **buyer funds stranded on a curve that can never graduate promoted from three scattered
sub-branches to its own ID, M-3.**

**There is no High.** The one candidate is written up in full below because its mechanism is the most worth
reading in the round; it is graded Medium because its grade mapped onto no limb of the rubric as written, and
because both of its arming conditions are deployment-time parameters that do not exist yet.

---

## M-0 · Medium · The LP fee turns the 90% sell spike from profit-gated into volume-gated, re-armable by anyone every 240 s

*Filed as High by the economics lane, executed end to end by triage, re-derived independently by the
adversarial pass, and re-graded to Medium by the lead. The mechanism is not in doubt; the grade was.*

**Location** `src/v2/V2LiquidityVault.sol:91`, `src/v2/HedgeFunV2Treasury.sol:168-172`,
`src/HedgeFunTreasuryBase.sol:451,464,474,484`, `src/hooks/HedgeFunHook.sol:289-293,320-327`.

**Status** EXECUTED, twice, independently.

**Mechanism.** Every link is permissionless:

```
V2LiquidityVault.collectFees()          :91    no access control — first line is `if (!seeded)`
  -> HedgeFunV2Treasury.creditLiquidityFee     msg.sender must be the vault, but the entry above is open
       buybackStock += amount                  LP fees become buy-back ammunition directly
  -> HedgeFunTreasuryBase.buyback()     :451   external, not virtual, permissionless
       :474  dust floor is `spent < min(amountIn, _ruleStockFor(minLotUsdg, p))`
       :484  noteEvent()                       arms the sell spike
```

The break is at `:474`. That `min` is v1's deliberate carve-out — its own comment says the floor must not
apply "when so little profit is left that the whole remainder is smaller than it". **In v1 that was safe
because `buybackStock` could only ever be filled by `takeProfit`, i.e. by realised profit.** Fill the same
variable from 0.30% of anyone's buy volume and the carve-out becomes "any nonzero pot arms the spike". The
hook's own comment names this premise as the reason the `2 × spikeSeconds` re-arm bound was tolerable.

**Measured.** With `buybackStock = 1 wei`, `buyback()` returns **`spent = 1, burned = 0`** and `sellRateBps`
goes **1000 → 9000**. The arming "buy-back" buys nothing and burns nothing — and that is forced, not lucky:
a 1-wei exact-input at `lpFee = 3000` gives `amountRemainingLessFee = 1·997000/1e6 = 0`, so the pool takes 0
in, returns 0 out, and the whole wei becomes `feeAmount`. Fuel threshold measured at **334 wei of stock**; a
seller inside the window measured keeping **1/9.0** of their proceeds; re-arm at +241 s for one wei.

**Impact.** Loser: sellers caught inside the window, and through them the product's credibility. Certain gain
to the caller: **zero** — the bounty is a share of `burned`, which is 0. The gain accrues to the creator and
the protocol as a larger tax share, which is why the High did not fit: the rubric asks what an *actor* takes,
and the actor who acts takes nothing.

**Conditions.** (1) v2 ships `spikeBps != 0` — **UNMEASURED, no v2 Defaults exist**; at 0 the finding
evaporates entirely, EXECUTED. (2) a nonzero LP fee — structural once `_maxLpFee() > 0`; a claim that
`lpFee = 1` starves it was tested and is **false** (a 100-stock buy yields 1e14 wei of collectable fee).
(3) someone pays gas ~15×/hour to hold the duty cycle — nobody is paid to.

**Fix** Two pre-deployment constraints, **zero bytes**: ship `spikeBps = 0` on v2, or gate `noteEvent()` on a
nonzero `burned`. The second is one comparison in `HedgeFunTreasuryBase`, scored against `TreasuryDeployer`'s
1,020.

---

## M-1 · Medium · `collectFees()` couples the stock leg to the token burn

**Location** `src/v2/V2LiquidityVault.sol:91-114`; contrast `src/hooks/HedgeFunHook.sol:460-469`.

**Status** EXECUTED (coupling). **Its headline structural conclusion was a false positive — see below.**

One `unlock` takes both fee currencies, then delivers them in one straight line: `creditLiquidityFee` at
`:106` runs before an unconditional `HedgeFunToken(token).burn(tokenBurned)` at `:111`, with no `try` and no
`collectTokenFeesOnly()`. A stock leg the issuer refuses therefore also reverts a token burn that has no
dependence on the stock at all. The hook in the same repository splits exactly these two legs with `try/catch`
and a parked ledger, and says in a comment why. V2 adds a fifth custody point to the four
`docs/STOCK_TOKEN_ASSESSMENT.md` enumerates, and it is the only one whose currencies are coupled.

**What this report got wrong, corrected here.** An earlier layer concluded — and the lead relayed to the
client — that the only correct fix was **36 bytes over EIP-170** and therefore required splitting
`CurveDeployer` in two. The adversarial pass rebuilt all three candidate variants, **reproduced the byte
table exactly**, and killed the conclusion: making the retry accumulator `private` rather than `public`
lands at **−2**, and **`CurveDeployer.predictVault` is dead code on chain** (one caller in the tree, a test),
whose deletion frees **51 bytes** and lands the unmodified correct fix at margin **+15. It fits.**

A second correction, also from the adversarial pass: the proposed fix **cannot help two of this finding's own
three triggers.** V4's `take` is a plain ERC-20 transfer into the vault, so a blocklisted vault or a global
pause reverts inside the `unlock`, before any delivery leg exists.

**Fix** Deliver the stock leg through a self-call with a `pendingStockFee` retry, and delete `predictVault`
to pay for it. ~176 bytes available on `CurveDeployer`, +15 after the deletion. Do **not** use
catch-and-abandon: `_take` has already pulled the stock into a contract with no function that can move a
pre-existing balance, so that variant turns a recoverable freeze into a permanent loss.

---

## M-2 · Medium · A full v2 raise is a one-directional buy through the stock's only V3 pool

**Location** `src/v2/HedgeFunV2Factory.sol` (`Rg = 4 · openPriceE18 · supply / 1e18`); the v1 health gate at
`src/HedgeFunTreasury.sol`.

**Status** EXECUTED, and re-measured at a second block ~32k later by the adversarial pass.

V2's quote asset is the listed stock token, so every buyer's payment passes through the **same**
`<stock>/USDG` V3 pool the v1 treasuries use both for execution and for their health gate — and the curve has
no pacing, so one buyer can fill it in one transaction. At the shipped "$10k opening FDV" convention every
raise is ≈$40k.

**Ten of eighteen listings are thin**: AAPL +72 bps, TSLA +97, MSFT +105, MU +142, META +151, MSTR +162
(gate 125), GME +295, USAR +1,060, AMD +1,200 — against a 50 bps gate — plus INTC, below.

**Two honesty notes.** The source material carried a second figure, "seven of eighteen", in its Fix
paragraph; the two were measured at different moments and were **never reconciled**. And depth on this chain
is not a durable quantity: one lane measured AMD's budget moving **36.7% in thirty minutes**, and the
adversarial pass measured it falling a further **10.9% inside its own session** ($3,350 → $2,984), with GOOGL
drifting +36 → **+49 bps, one basis point from the gate**. **The deliverable is the rule, not the count.**

**Fix** A listing rule, **0 bytes**: require `4 · openPriceE18 · supply / 1e18 ≤` the measured USDG that
moves that stock's V3 pool by `maxDeviationBps`, re-measured at listing time and re-checked before each v2
launch. `saleBps` is the other lever.

---

## M-3 · Medium · Buyer funds can be permanently stranded on a curve that can never graduate

*Promoted to its own ID by the lead. It appeared three times as somebody else's sub-branch, and it is the
largest buyer loss in the report.*

**Status** EXECUTED (the structural instance).

**INTC cannot graduate at all.** Its curve needs `Rg = 330.80 INTC`; the pool holds less than that, so the
exact-output swap reverts, the curve fills, reaches `Ready`, and the graduation that is supposed to follow in
the same transaction cannot complete.

**The requirement is a fixed 330.80; what the pool holds is falling.** Three readings of the same pool, all
on 2026-09-27, hours apart, by three different layers of this round — each reproducible with
[`poc/fork/All18.t.sol`](./poc/fork/All18.t.sol), which walks all 18 listings:

| read by | INTC the pool can deliver | requirement as % of it |
|---|---|---|
| economics lane | 317.71 | 104.1% |
| adversarial pass | 285.48 | 115.9% |
| lead, closing the round | **262.32** | **126.1%** |

The earlier figures are not errors to be corrected to the last one — they are what the chain held when each
was read, which is why the probe asserts only on what is deterministic and reports the rest. **The shortfall
widened by 22 points in a single day**, so treat any single number here as the read date's and re-run before
relying on it. INTC was the only one of the 18 that could not fill at any of the three reads.

What buyers hold at that point is a token on a capped curve with **no refund, no cancellation and no owner
rescue** — by design; the protocol has no such primitive anywhere. The only exit is selling back into the
curve at the ~19.5% round-trip tax, while the creator continues to take a share of it.

**This is the finding the rubric cannot express.** Nobody takes the money. Under the clause's "destroys" limb
it is the most serious thing in the report; under the "an unprivileged actor takes" reading that this report
has been applying, it is a Medium. Graded Medium and flagged, rather than quietly filed.

**Fix** The M-2 listing rule prevents the structural case. Beyond that: a graduation that fails should leave
the curve in a state a later call can retry, and the failure should be observable.

---

## M-4 · Medium · The enforced parameter floors are far wider than the project's own conclusion

`MIN_LP_BPS = 1000` and `MAX_SALE_BPS = 9000` against the author's own `V2_LP_DEPTH_EXPERIMENT.md`
recommendation of LP 60 / sale 70 — and the shipped defaults of 50/80 are not the recommendation either. At
LP 10% a full dump returns **8.8 cents on the dollar**. The code limb is CONFIRMED; the price limb is a
single-sourced closed-form model, which this report flags rather than hides (see M-6 and `README.md`).

## M-5 · Medium · The v2 documents' quantitative evidence does not reproduce at the audited ref

CONFIRMED to the digit. `V2_ADVERSARIAL_REVIEW.md`'s mature-TWAP table reproduces exactly at `01e515a`, the
commit that wrote it, and **four of its eight rows are wrong at `03ad70e`** — tokens burned 507.410 → 351.087
(**−31%**), keeper bounty likewise. Nothing caught it because those figures are `emit log_named_decimal_uint`
only; the assertions are a comparison and a floor. Its reproduction evidence also does not reproduce: the
cited suite counts, the cited fork blocks and one quoted return value do not match the tree. And its **GO
verdict is scoped to `885123e`, a ref at which two of the nine v2 contracts did not exist** — including
`V2LiquidityVault`, which now owns every graduated LP position.

## M-6 · Medium · Two shipped documents disagree with the code and with each other on who sets the LP split

`V2_DUAL_ENGINE_REVIEW.md` states `floor(reserve / 2)` as the LP budget. The code uses `lpBpsOfTreasury`,
an **owner dial with a 10–100% range**; at 10000 the treasury's graduation share is zero.
`V2_BONDING_CURVE.md` describes it correctly five lines from where the other document does not. The recurring
distinction this track keeps finding — a **bound** versus a **policy** — again resolves as policy.

---

## The Low and Info tiers

All six Lows and 23 Infos are written out in [`FINDINGS-FULL.md`](./FINDINGS-FULL.md). The ones worth a
reader's attention:

- **L-1** the documented permissionless `graduate(id)` fallback can never fire — `Ready` never survives a
  transaction. Two of its three stated limbs were wrong and are corrected in `VERIFICATION.md`; the
  unreachability holds. The preferred fix is a deletion, which *adds* margin to the 27-byte factory.
- **L-2** the v1 scorecard numerator now moves on a bare `transfer`; a 1-wei donation inflates it permanently.
- **L-5** vault addresses are publicly predictable before graduation and anything sent there is destroyed.
- **I-14** `V2LiquidityVault.seed`'s `onlyFactory` is covered by **no test** — deleting it leaves all 1,412
  green. Not exploitable: graduation deploys and seeds the vault in one transaction and the price is computed
  from the curve's own reserves, not supplied by the caller. *The lead attached a causal story to this — that
  the byte budget made the splitting refactor likely, which would make the guard load-bearing. The
  adversarial pass showed the fix fits without splitting. The story is withdrawn; the coverage hole stands.*
- **I-13** `V2_BONDING_CURVE.md` says the factory sits "143 bytes" under EIP-170. It is **27**, and the same
  document says 27 elsewhere.

## Prior-round conclusions this PR changes

Thirteen, of which **none changes any judgement about the nine live strategies.** Stated that way rather than
as a headline, because round 2 was rightly criticised for inflating the same number. Six no longer hold as
written — `lpFee` forced to 0 is false of the base; "lots is never iterated" is false in v2; the sell spike is
not live at a graduated open; the scorecard clearances; and rounds 1-2's measured **90.99%** shove cost, which
is **19.485%** on a v2 pool, a 4.7× fall, because a v1 launch pool opens inside a decaying spike and a v2
graduated pool opens flat. Six more lose their proof while keeping their conclusion. And round 1's F-40
watch-list **fired on both of its named triggers** — the one prior conclusion that was caught mechanically,
which is the argument for attaching triggers to a safe list rather than just publishing one.

## Checked and found safe

Seventy-five items with the line that makes each one safe, listed in
[`FINDINGS-FULL.md`](./FINDINGS-FULL.md) section 6 and attacked by the adversarial pass, which overturned
**one**: the documented 1.80% stop floor is pool-tier dependent
(155 bps on the 500-tier listings, 180 on the 3000-tier, **250 on MSTR**) — the document states the condition
and the restatement dropped it. The load-bearing ones that held: the curve's invariant is exact and its
rounding never favours a later trader (fuzz-verified over 256 mixed sequences, re-run independently);
**"fee-only" is enforced by the code** — no expression in the vault can produce a negative liquidity delta,
and the callback data is hash-bound to constants the vault built; graduation cannot be double-triggered and
its price is derived, not supplied; and the `delegatecall` provably does not touch factory slot 0.

**This section will be invalidated by the next PR the same way this one invalidated its predecessors.** Every
item carries the ref it was proved at.
