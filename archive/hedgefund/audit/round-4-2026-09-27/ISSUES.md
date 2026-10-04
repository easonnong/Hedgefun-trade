> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Findings — external audit round 4: the strategy-engine tip

`origin/codex/v2-strategy-engine` @ `5aedceb` (PR #84 tip `9679614` + PR #91), audited 2026-09-27/28. Scope, the
deployment reality, the remediation budget and the test state: [`00-SCOPE.md`](./00-SCOPE.md). Method and what
the round got wrong: [`README.md`](./README.md). How to re-run everything: [`VERIFICATION.md`](./VERIFICATION.md).
The four lane reports in full, which are the evidence under every line here: [`lanes/engine.md`](./lanes/engine.md),
[`lanes/delta.md`](./lanes/delta.md), [`lanes/claims.md`](./lanes/claims.md), [`lanes/econ.md`](./lanes/econ.md).
Everything marked EXECUTED runs from [`poc/`](./poc/) — four runners, 58 tests, 41 mutation diffs, two Python
models, no network.

**IDs.** Round-4 findings are `M4-n` / `L4-n` / `I4-n`. Round 3's are cited as they were (`M-0`, `L-3`, `I-8`).
Lane IDs (`E-1`, `D-4`, `C-2`, `X-5`) are kept as cross-references; each round-4 ID names the lane IDs it merged.

---

## Read this before the counts

**1. The rubric measures whether anyone *took* money, and the thing worth worrying about is still whether
anyone *loses* it.** Round 3 said this of the curve and the vault, the first contracts here to custody other
people's assets. The engine is the first contract here to *trade* them: after graduation it holds the
treasury's share of the raise, which buyers paid for, and it sells and buys that share on a schedule anyone
can read and anyone can call. Of the 26 findings, **one reports a certain gain to an unprivileged caller**
(M4-1, and only on 0.05%-tier listings). The other 25 report zero gain to any actor. Every graded finding
names the treasury — token holders through it — as the loser. So, as in round 3, "0 Critical, 0 High" is a
statement about the instrument as much as about the code.

**2. Where two lanes graded the same mechanism, the lane that read the code graded lower than the lane that
modelled the economics — three times out of three.** The deadband with no friction floor (E-2 Low / X-5
Medium), the missing bounty (E-3 Info / X-6 Low) and the UTC-day cap (E-4 Info / X-2 Low). Triage sided with
the economics lane each time, for reasons given at each finding, and says so here so a reader who thinks the
code-reading lane was right can subtract one Medium and two Lows and see what remains. No adversarial pass ran
this round to break the tie; round 3's did, and it moved the round's only High. **On one of the three the
code-reading lane also had the better number**: the economics lane's worst day for a 1 bp band ($1,300–$3,400
on a $10,000 treasury) is two orders of magnitude too high, and the engine lane's ≈0.08% of value a day is right
(M4-2 carries the correction). The Medium survives the correction; the headline figure does not.

**3. The deployment configuration was not audited and cannot be.** No V2 `Defaults`, no engine kind, no
policy exist on chain. Two of the three Mediums (M4-1, M4-2) and four of the nine Lows (L4-1, L4-2, L4-3, and
L4-5 through the choice to register kind 1) live inside parameters or registrations nobody has made yet. **This
audit certifies no configuration.** Round 3's L-3 — the buy-back's impact cap against round-trip
friction — is the one place the candidate configuration (the rehearsal script's) is on the wrong side of a
line round 3 drew, and it is still there.

**4. Sixteen of the 26 are not vulnerabilities.** Seven are test-coverage holes (L4-6 to L4-9, I4-11 to
I4-13: every guard is present; the repository's suite would not notice its removal), seven are documentation or
disclosure (M4-3, L4-3, I4-7 to I4-10, I4-14), two are diagnosability (I4-1, I4-6). They are graded on the same
scale for their consequence on a system whose treasuries are immutable once launched, and each is marked. **The
code-defect count is two Mediums (M4-1, M4-2) and four Lows (L4-1, L4-2, L4-4, L4-5)**; the remaining four
(I4-2 to I4-5) are documented limitations and design constraints.
The four coverage-hole Lows (L4-6 to L4-9) would be Info under the rubric alone, as round 3 graded I-14; they
are Low under round 3's own "grade the fix path" rule, because the fixes this report recommends for M4-1 and
M4-2 edit exactly the lines those holes leave unpinned.

## Counts

| | Critical | High | Medium | Low | Info | total |
|---|---|---|---|---|---|---|
| **everything found at `5aedceb`** | **0** | **0** | **3** | **9** | **14** | **26** |
| only new in PR #91 (engine, policy, registry, `STRATEGY_ENGINE.md`, PR #91's body) | 0 | 0 | 3 | 8 | 8 | 19 |
| only on PR #84's delta since round 3 (vault fix, spike freeze, base line, kind-1 relabel, the merge) | 0 | 0 | 0 | 1 | 6 | 7 |

By ID: PR #91 is M4-1 to M4-3, L4-1 to L4-4, L4-6 to L4-9, I4-1 to I4-5, I4-11, I4-13 and I4-14. PR #84's side
is L4-5, I4-6 to I4-10 and I4-12 — the last a check `HedgeFunV2Treasury` already had at round 3's ref, untested
then and now, so strictly PR #84's code rather than its delta. Mixed items are counted where most of them live.

**Round 3's findings at the tip** (the ledger is below). Round 3's counts table says 35 with six Mediums, but
its report files seven Medium IDs (M-0 to M-6; its PR body lists "M-5 / M-6" as one bullet), so the ledger tracks
36 IDs. Mediums — 3 FIXED (M-1, M-6, M-5's table), 1 FIXED for V2 with residue (M-0), 3 PARTIALLY (M-2, M-3,
M-4). Lows — **0 of 6 addressed**. Infos (23) — 2 FIXED (I-13, I-15), 2 PARTIALLY (I-2, I-16), 1 worsened into a
Low here (I-8 → L4-5), 1 regressed (I-23 → I4-9), 13 NOT ADDRESSED, 3 ACCEPTED-BY-DESIGN, 1 moot (I-22).

**Derivation, so it can be checked.** The four lanes reported 37 items: engine 11 (0/0/0/2/9), delta 6
(0/0/0/1/5), claims 12 (0/0/0/4/8), economics 8 (0/0/3/3/2, the two Infos being "safe" verdicts). Two safe
verdicts (X-3, X-8) go to the safe list, and the engine lane's byte-budget item (E-9) is scope, not a finding —
34 graded items. Six merge groups remove eight items: E-3 = X-6 (no bounty); E-4 = X-2 (UTC day); E-2 + E-6 +
X-5 (the floors and the setter, three items into one); E-5 = C-8 (the dead action check); D-5 + C-6 + C-7 (stale
numbers, three into one); C-12 into C-2 (the invariant-coverage sentence is the documentation limb of the
untested health gate). 34 − 8 = **26**. Two lane items are split across findings without changing the count:
E-4's "no ceiling" half is argued inside M4-2, and C-11's provenance bullet is carried by I4-9. The economics
PoC `test_X9_*` is the setter limb of X-5, not a separate lane item. Grades that moved in triage: E-2 Low → part
of M4-2; E-6 Info → part of M4-2; E-4 Info → L4-2; E-3 Info → L4-4; C-12 Info → part of L4-7. Nothing was
raised above what any lane graded it.

| lane | reported (C/H/M/L/I) | to the safe list or scope | merged into another lane's item | round-4 IDs it heads |
|---|---|---|---|---|
| engine | 11 (0/0/0/2/9) | 1: E-9 (scope) | 2: E-2, E-6 → X-5 | 8: L4-1, L4-4, L4-2, I4-1, I4-2, I4-3, I4-4, I4-5 |
| delta | 6 (0/0/0/1/5) | 0 | 0 | 6: I4-6, I4-7, I4-8, L4-5, I4-9, I4-10 |
| claims | 12 (0/0/0/4/8) | 0 | 4: C-6, C-7 → D-5; C-8 → E-5; C-12 → C-2 | 8: L4-6, L4-7, L4-8, L4-9, I4-11, I4-12, I4-13, I4-14 |
| economics | 8 (0/0/3/3/2) | 2: X-3, X-8 (safe) | 2: X-2 → E-4; X-6 → E-3 | 4: M4-1, M4-2, M4-3, L4-3 |
| **total** | **37** | **3** | **8** | **26 (0/0/3/9/14)** |

---

# Medium

## M4-1 · Medium · The rebalance is a predictable, unpaid order that can be sandwiched inside the gates, and on 0.05% listings the sandwich pays

*Merges X-1. The engine lane lists the same bound as safe (its item 25: "inside the gate, at most
`maxSlippageBps` — the same bound as V1") and names the sandwicher as the only paid caller in E-2 and E-3.
Graded Medium by the economics lane. Triage keeps Medium: the rubric's "bounded or recurring leak" limb is
exactly this — the bound the engine lane calls safe is the room the sandwich lives in, and inside it there is a
certain gain to an unprivileged caller on one class of listing. Not High: nothing takes principal, no TWAP
manipulation, no Safe misbehaviour.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:250` (`execute()`, permissionless, no bounty);
`src/PoolTrader.sol:104-129` (`_health`, `_swapBounded`); `src/HedgeFunTreasury.sol:138-140` (`_swapStock`,
not `virtual`); `docs/ADDRESSES.md:50-63` (fee tiers and gates of the recorded listings).

**Status** EXECUTED (`poc/econ/AuditEcon4.t.sol::test_X1_*`, three tests) and modelled
(`poc/econ/sandwich_model.py`).

**Mechanism.** The pool cannot make the engine act — the deadband is measured at the Chainlink price — but
anyone can choose *when* it acts, because `execute()` is open and the moment it is due is public. The attacker
pushes spot to the edge of the deviation gate (49 bps under the oracle for a treasury sell), calls `execute()`
in the same transaction, and unwinds. `health()` passes (49 < 50 against the oracle, 49 ticks against a 600 s
mean that has not moved). The treasury's exact-input swap then fills from −49 bps down to the −100 bps limit.
The treasury pays the same extra ~50 bps whoever sits at the gate's edge; **who collects it is decided by the
fee tier**, because the attacker's push round-trips two pool fees: the capture is
`(maxDeviationBps − 2 × poolFeeBps) × turnover − impact`.

Measured on a constant-liquidity V3 step, $10,000 of USDG per 1% of depth, one $2,000 action:

| tier, gates | treasury cost vs oracle, no push | pushed | (slip + fee) floor | attacker P&L |
|---|---|---|---|---|
| 0.30%, 50/100 | 39 bps | **88 bps** | 130 bps | −$19.86 |
| 0.05%, 50/100 | 14 bps | **63 bps** | 105 bps | **+$4.86** |

On a 0.30% pool the model finds no profitable cell across $3.3k–$250k per 1% of depth and $100–$10,000 per
action. On a 0.05% pool it turns positive at **`maxTradeUsdg` ≈ 10.1% of the pool's USDG-per-1% depth**,
independent of the depth (the lane's breakeven sweep; the shipped `sandwich_model.py` does not print that sweep,
and its grid brackets the breakeven between 5% and 15% of depth at every depth it tries — triage re-run,
2026-09-28), and grows with the action (+$0.84 at $500 on $3.3k; +$4.96 at $2,000 on $10k;
+$22.30 at $10,000 on $55k). The 20/50 gates of `docs/V2_SANDWICH_FORK.md` move the breakeven nowhere (20 > 2 × 5).
The project's own fork test in that document lost money for the bot because it pushed 10 bps against a 20 bps
gate on a $5.85 order — one cell of this grid, and the one the document itself says not to generalise from.

**Why the gate cannot simply be tightened.** Chainlink equity feeds print on a 0.5% move, so between prints
the pool legitimately wanders up to ~50 bps from the feed; a 20 bps gate shuts `health()` for most of the
session (the repository's own note in `LISTING_CANDIDATES.md:60`). The 50 bps room is structural on this
oracle. The levers are size against depth, and frequency.

**Impact.** Loser: the treasury. Per action, up to `maxDeviationBps` extra on the action's turnover; **25 bps
of treasury value on graduation day**, when half the treasury turns over (L4-3); per day, at most `50 ×
min(maxDaily, maxTrade × 86400 / cooldown) / value` bps from the configuration — and, whatever the configuration,
no more than the turnover the oracle's moves force, because the engine only trades back toward its target (the
engine lane's E-4 point: at 50/50 each 0.5% print forces about 0.13% of value; see M4-2). Certain gain to an
unprivileged caller: the capture above, on 0.05% listings only; at most ~$20 per action on a $10k-deep pool.

**Conditions.** (1) A kind-2 launch on a 0.05% listing — none exists, UNMEASURED. (2) `maxTradeUsdg ≥ ~10%` of
the pool's USDG-per-1% depth at call time — **true for GME at the default 2,000 chunk on round 3's read**
(+295 bps for $40k, ≈ $13.5k per 1%, 2026-09-27; re-measure), false for GOOGL (≈ $90k per 1%) and NVDA at that
chunk. `docs/ADDRESSES.md` records NVDA, SPCX, GOOGL and GME on 0.05% pools out of the twelve it lists; the chain
has eighteen listings and the tier of the other six is unmeasured here. (3) The treasury outside its band with
the cooldown expired — certain for the first minutes after graduation and on every band-crossing after that.
(4) An attacker willing to hold the push for one block — atomic, no ordering privilege needed on a sequencer chain.

**Fix.**
- **0 bytes, owner, per listing:** size `sellChunkUsdg` on every 0.05% listing at **≤ 10% of the measured
  USDG-per-1% depth**, re-read at listing time exactly like round 3's M-2 rule (GME: ≤ ~$1,300 on round 3's read).
  This makes the sandwich a loss everywhere. Because the 10.1% point is not reproducible from the shipped model
  (above) and depth moved 10–37% inside round 3's own day, leave margin: the grid's 5% is the conservative line. It belongs beside step 3 of `docs/V2_DEPLOYMENT_REHEARSAL.md`.
- **~150 bytes, engine (against 3,002 runtime):** bound the fill from the pre-call spot as well as from the
  oracle — `limit = min(oracle × (1 − slip), spot × (1 − impactCap))`, same cap on the realised average — so the
  attacker's room is `impactCap`, which can be set under `2 × poolFeeBps`. Needs `HedgeFunTreasury._swapStock`
  to become `virtual` and an override in the engine; `HedgeFunTreasury` already differs from the live V1 build
  in this PR, so the byte-identity argument against touching it is gone (it is scored against `TreasuryDeployer`'s
  1,001 for the `virtual` keyword, which costs nothing).
- Do not rely on a bounty for this (L4-4): a bounty makes an honest keeper race the bot; it does not shrink
  the room.

## M4-2 · Medium · The engine's configuration floors admit anything, the creator-side setter validates nothing, and the choice is the creator's

*Merges X-5 (Medium; its setter limb is the economics PoC `test_X9_*`), E-2 (Low: the deadband), E-6 (Info:
the setter) and E-4's "no ceiling" half (Info). Graded Medium by the economics lane on round 3's M-4 pattern; the
engine lane graded the deadband limb Low because "only for a launch whose creator set the band inside friction,
and visible in the frozen config" — the bound-versus-policy argument round 3 rejected for M-4. Triage keeps
Medium: taken together, a 1 bp band, a 1 s cooldown and a day with no ceiling make one creator choice (or one
decimals slip) into a leak with no end date — on the corrected figure below, up to about a quarter of the
treasury a year on a volatile name — and V1's constructor refuses to launch exactly this. The rubric's Medium
limb is "bounded or recurring leak"; this is recurring. The claims lane's C-4 — that the bounds which *do* exist
are untested — is kept separate as L4-9.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:119-141` (`_validateEngineConfig`: `deadbandBps == 0`,
`deadbandBps >= targetBps`, `target + deadband >= BPS`, `cooldown == 0`, `maxTradeUsdg == 0`,
`maxTradeUsdg > p.sellChunkUsdg`, `maxDailyTurnoverUsdg < maxTradeUsdg` are the whole list);
`src/v2/V2TreasuryDeployer.sol:303-319` (`setEngineConfig`: validates the policy key and the kind, not one
word) and `:394-397` (`predict` builds the initcode without running the constructor);
`src/v2/strategy/V2RebalancePolicy.sol:86-106` (accepts `deadband == 0`). Contrast `src/HedgeFunTreasury.sol:39-42`
("the rule must clear its own execution cost, twice over": `tp1Bps` and `dipBps` below
`2 × (maxSlippageBps + poolFeeBps)` are refused) and `src/HedgeFunFactory.sol:193-196` (V1 mirrors every
constructor check in the factory because "a constructor's revert reason does not survive CREATE2").

**Status** EXECUTED — `poc/econ/AuditEcon4.t.sol::test_X5_*`, `::test_X9_*`;
`poc/engine/AuditEngineConfig.t.sol::test_E2_*`, `::test_E4_*`, `::test_E6_*`.

**Mechanism, three limbs.**

*The deadband has no floor against the friction the engine itself allows.* A sell fires above `target +
deadband`, a buy below `target − deadband`, at a price the venue may set anywhere inside `maxSlippageBps` of the
oracle plus the pool fee. At a 50/50 target a relative price move `r` moves the weight by about `r/4`, so a
band `δ` is crossed by a move of `4δ`: **1 bp is crossed by every 0.5% Chainlink print** (any band under ~12 bps
is), and each crossing pays up to `maxSlippageBps + poolFeeBps` to capture 0.5%; the next print the other way
reverses it at the same cost. Measured on the flat mock (fee only): 20 round trips of ±0.5% prints → **40
trades** on a 1 bp band, **20,000.000000 → 19,999.492120 USDG**; the 5% band beside it traded zero times.
Measured by the economics lane with cooldown 1 s and no daily cap, on a $9,980 treasury: after the sell-down, one
+0.5% print sells **$14.24** and the reverting print buys **$12.42** — 0.12–0.14% of value each, each paying
35–130 bps — at every print, forever.

*What that costs a day (triage's correction of the economics lane's figure).* Each print costs at most 130 bps
of about 0.13% of value, ≈ 0.18 bps of value. At the economics lane's 20–50 band-crossing prints a day on a
volatile name that is **≈ 0.03–0.09% of treasury value a day ($3–$9 on $10,000)** — about 9–24% a year over
260 trading days if every crossing fills at the 130 bps limit, about 2–6% a year at the ~35 bps typical cost
(a sandwich of a $14 trade loses the attacker money, so the limit is reached by where spot happens to sit, not by
an attacker). It
agrees with the engine lane's ≈ 0.08% a day. No configured number stops it, because with `cooldown = 1` and no
daily cap the day is bounded only by the feed. The economics lane wrote the bound as `130 bps × maxTrade ×
prints/day` and priced it at **$1,300–$3,400 a day "on a treasury that need not be larger than $10,000"**; that
assumes every print forces a full `maxTrade`, but a 0.5% print forces `maxTrade = $2,000` of turnover only on a
treasury of about $1.4M, where it is the same fraction of value. The engine only trades back toward its target,
so the print's size, not the chunk, sets the trade — the sandwich model's own deadband table sizes the action
the same way (1 bp of value for the smallest move that crosses a 1 bp band).

*The other floors admit anything too.* `cooldown = 1 s` deploys. `maxDailyTurnoverUsdg = 2^256 − 1` deploys (the
only owner-set bound on the engine's turnover is `maxTradeUsdg ≤ sellChunkUsdg` per call). A target of 2 bp
deploys and means "sell 99.98% of the lot at graduation" (L4-3). *(The economics lane wrote "1 bp"; the
constructor requires `0 < deadband < target`, so 2 bp is the floor — see `README.md`.)*

*The setter validates nothing and `predict()` quotes what `launch()` refuses.* `setEngineConfig` checks the
policy and the schema and not one of the three words: `target = deadband = cooldown = maxTrade = maxDaily = 0`
is accepted, `predict` returns an address and terms, and `launch` reverts with an opaque `TreasuryDeployFailed`;
likewise `maxTradeUsdg` one wei over `sellChunkUsdg`. Nothing is lost (the launch fee transfer is inside the
reverted transaction); the creator learns which of three packed words it was by bisection. No test in the tree
exercises the `maxTradeUsdg > p.sellChunkUsdg` limb — every fixture sets `sellChunkUsdg = uint128.max`; the
engine lane's PoC is the first to hit it, and it works.

**Impact.** Loser: the treasury (so the token's narrative and scorecard). Certain gain to a sandwicher on
0.05% listings only: `maxDeviationBps − 2 × poolFeeBps` of each trade less impact (M4-1) — not `maxSlippageBps`,
which is what the engine lane's E-2 wrote and is the treasury's cost bound, not the attacker's take. On 0.30%
and 1% listings the treasury still pays the extra and the pool's LPs and arbs take it. No attacker can
shrink a band after launch, and a donation that crosses the band costs its donor more than the sandwich returns
(economics lane X-8, engine lane item 7 — on the safe list).

**Conditions.** A creator chooses the numbers; the config is three raw `bytes32` words set in a separate call
from the launch, with no front end yet. UNMEASURED (no V2 deployment). Status of the candidate configuration:
the rehearsal script sets no engine config at all.

**Fix.** Five comparisons in `_validateEngineConfig` — the floors in the table at the end of this document
(`deadbandBps ≥ maxSlippageBps + poolFeeBps` at minimum, where `poolFeeBps` is already an immutable of
`PoolTrader`; `cooldown ≥ 600`; `maxDaily ≤ 24 × maxTrade`; `target ∈ [2000, 9000]`). **Measured cost of two of
them (with L4-1's): 0 runtime bytes, +47 initcode** against the engine's 21,286 of initcode margin — constructor-only
code is not runtime. Mirror the word checks in `setEngineConfig` so a quote is never given for an unlaunchable
config; the schema and range limbs are free there, and the `minLotUsdg`/`sellChunkUsdg` limbs need the factory's
defaults or a `view` on the engine chunk (deployer: 13,839 runtime / 11,128 initcode free). **Both halves have
a deployment deadline** — see the go/no-go in `pr-body.txt`: engine kinds are append-only with no disable, and
the factory binds its deployer once.

## M4-3 · Medium · Strategy gains never reach the burn, and nothing a buyer reads says so

*Merges X-7. Graded Medium by the economics lane on the rubric's disclosure limb. The engine lane records the
same fact on its safe list (item 8: "stated in the engine's header, `:160-161`"). Both are right: the fact is
in the source, and it is in no document a buyer reads — `docs/STRATEGY_ENGINE.md` is silent and the launch
terms do not exist yet. Triage keeps Medium on the disclosure limb, because the burn is the product's one
holder-facing claim and the modelled gap is an order of magnitude. It is a coherent design; the finding is
that nobody is told.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:335-337, 355-357` (proceeds stay inventory);
`src/v2/HedgeFunV2Treasury.sol:170-174` (`creditLiquidityFee`, the only writer of `buybackStock` reachable from
kind 2); `docs/STRATEGY_ENGINE.md` (silent); the engine's own header (`:160-161`, which does say it).

**Status** EXECUTED (`poc/econ/AuditEcon4.t.sol::test_X7_rebalanceGainsNeverReachTheBurn`) and modelled
(`poc/econ/constant_mix.py`, tables A and B).

**Mechanism.** Kind 0 routes the profit share of every take-profit to `buybackStock`; the engine routes
nothing — a sell's proceeds are USDG inventory, a buy's are stock inventory, and the only thing that ever feeds
the buy-back is the LP fee. Executed: sell-down at $100, buys at $80, sells at $100; USDG reserve $4,988 → $5,050
and 50.5 stock kept; `buybackStock == 0`, `totalBurned == 0`, `buyback()` reverts `NotDue`. Modelled on the
project's own `lab/trend.py` paths over 90 days: **kind 2 burns +0.19% of supply on every path for every
config** (the LP fee alone) against kind 0's **+2.20%** at +3%/day, +1.27% at +1%/day, +0.49% flat at 4% vol. In
dollars at +3%/day: kind 0 burned $47,390 of stock, kind 2 $5,419. The full kind-2-versus-kind-0 model is in
`lanes/econ.md`; the short version is that a constant mix does what a constant mix does — worse than kind 0 in
stock terms on every rising path, three times better on a −3%/day path, about σ²/8 on a range — and on none of
them does any of it reach holders.

**Impact.** Loser: the buyer of a kind-2 token, relative to what the same documents lead them to expect of a
V2 token. Gains accumulate as USDG in a treasury with no redemption and no claim. No gain to anyone.

**Fix.** 0 bytes: say it, in `STRATEGY_ENGINE.md` and in the launch page's terms, with the 0.19% figure. Or
~250 bytes (against 3,002): a high-water mark on total value at the oracle, and on each sell that lifts the
reserve above it, credit a config share of the excess in stock to `buybackStock` — which re-couples holders to
the strategy without lots or cost bases.

---

# Low

## L4-1 · Low · `maxTradeUsdg` below `minLotUsdg` launches, and the treasury is permanently inert

*E-1, engine lane, Low. Only lane. Stands, on the lane's own reasoning: the bricked path is the essential one,
but only for one launch, chosen by that launch's creator, in a config readable on chain before anyone buys —
nearer the rubric's "permanent brick of one non-essential path" than to a leak, and nothing moves. A reader who
weights "buyers paid for a strategy that cannot fire" above "the creator chose it" will call it Medium, as the
lane says. Kept separate from M4-2 because the mechanism (a validity bound
against the core's own dust floor) and the consequence (a strategy that can never fire, not one that bleeds)
are different, though the fix rides in the same constructor.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:119-141` (`:139`), `:334`, `:354`, `:271` (the three
`minLotUsdg` floors). Contrast `src/HedgeFunFactory.sol:199,277` (`sellChunkUsdg < minLotUsdg` refused twice).
**Status** EXECUTED — `poc/engine/AuditEngineConfig.t.sol::test_E1_*`. **Code defect.**

Every executable path requires `≥ minLotUsdg` of notional and every path's notional is `≤ maxTradeUsdg`; with
`maxTradeUsdg < minLotUsdg` the two cannot both hold, so `execute()` ends in `NotDue` in every state — over-
and under-weight, after a doubling, a halving, a week, a fresh epoch — and `preview()` says "not due", which is
also what a healthy in-band treasury says. The repository's own
`test_previewDoesNotClaimDustBelowTheCoreMinimumIsExecutable` launches exactly this configuration
(`maxTrade 1e6` against `minLotUsdg 5e6`) and asserts the not-due, documenting the symptom as intended preview
behaviour. Loser: buyers of that token, who paid the curve for a strategy that will never act; the treasury's
share sits idle forever. Nothing taken, nothing destroyed. A decimals slip (`100` for `100e6`) is enough.
**Fix** `|| maxTradeUsdg < p.minLotUsdg` in `_validateEngineConfig`, mirrored in `setEngineConfig`.
**Measured: 0 runtime bytes** (initcode 27,866 → 27,913 together with E-2's floor).

## L4-2 · Low · The daily turnover cap is a UTC calendar day: twice the budget across midnight

*E-4 (engine, Info: "documented, and structurally the engine only trades toward the target") = X-2
(economics, Low). Triage: Low. It doubles every per-day bound in this report, including M4-1's and M4-2's, it
is immutable per treasury, and `docs/STRATEGY_ENGINE.md:38-40` calls the choice an open release decision — a
documented open item is not "no value impact".*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:296-299` (`uint64(block.timestamp / 1 days)`).
**Status** EXECUTED — `poc/engine/AuditEngineConfig.t.sol::test_E4_*` (the full cap clears at 23:59:58, is
refused at 23:59:59, clears again at 00:00:00: 2 × `maxDaily` two seconds apart);
`poc/econ/AuditEcon4.t.sol::test_X2_*` (five $100 actions at 23:54–23:58, a sixth refused, five more from 00:00:
**$1,000 of a $500/day cap in ten minutes**, the 60 s cooldown the only thing between them).
**Fix** A rolling limiter (a small ring of the last actions' timestamps and sizes, ~300 bytes of 3,002), or
accept it and halve `maxDailyTurnoverUsdg` in the floors. Decide before a kind-2 launch, as the document says.

## L4-3 · Low · The graduation lot is sold down to target within minutes, into the pool the raise just bought through, and nothing says so

*X-4, economics lane, Low. The engine lane names the same sequence in E-3 as "a predictable, MEV-visible
sequence". Stands: the cost is bounded per action by the (slip + fee) floor and happens once per launch; what is
unbounded is the flow into one pool, which is a disclosure and listing-rule gap, not a recurring leak.*

**Location** `src/v2/HedgeFunV2Factory.sol:153-156` (graduation sends stock only);
`src/v2/HedgeFunV2EngineTreasury.sol:321-339`. **Status** EXECUTED
(`poc/econ/AuditEcon4.t.sol::test_X4_graduationLotIsSoldDownToTargetImmediately`) and modelled
(`constant_mix.py`, table C).

The treasury opens at 100% stock and 0 USDG. At target 50% / band 5% / `maxTrade` 2,000 / no daily cap, on a
pool as thin as AMD's ($3.3k per 1%): **3 actions, 3 minutes, $5,012 of a $10,000 treasury sold, $4,983
received, 56 bps** — every fill short at the −1% limit, the pool refilled by arbs between cooldowns. The cost is
bounded per action by the (slip + fee) floor; what nothing in the engine bounds is the *flow*: a quarter of the
raise sold into the same V3 pool that just absorbed the whole raise as buys, minutes after graduation, typically
while arbs are still unwinding that push. This is round 3's M-2 in reverse at a quarter of the size, and
`docs/STRATEGY_ENGINE.md` does not say the engine starts fully invested and liquidates to target at once.
**Fix** 0 bytes: state it, and extend round 3's M-2 listing rule to `(1 − target) × treasuryStock × price ≤ the
USDG that moves the stock's V3 pool by maxDeviationBps`. Or ~100 bytes: an opening grace in the config (no
sells until `cooldown × N` after `wire()`), or initialise `target` from the graduation composition and let the
creator's target take over at the first oracle move of more than the band. M4-2's `target ≥ 2000` caps the
worst case at 80% of the lot.

## L4-4 · Low · `execute()` pays no bounty; the only party paid to call it is the counterparty of its fill

*E-3 (engine, Info: "a design decision, not a defect, recorded because V1's own comment states the risk this
design accepts") = X-6 (economics, Low). Triage: Low, on round 3's precedent — L-4 graded an unpaid,
undeadlined `book()` Low — and because the consequence is permanent per launch: a treasury whose rebalance is
never worth sandwiching never rebalances, and on a rising stock drifts to 100% stock while its holders were
sold a constant mix.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:250-289, 321-359` (no transfer to `msg.sender`);
`Params.bountyBps` is carried, validated and never read by the engine; contrast `HedgeFunTreasuryBase.sol:369-373,
396-399, 418-422` (kind 0 pays `bountyBps` on every action) and the comment at `:394-395`. **Status** EXECUTED
(`test_E3_executePaysNoBounty`, `test_X6_executePaysNoBounty`: a stranger's balances unchanged after a
successful `execute()`; `params().bountyBps == 50`). **Fix** Pay `bountyBps` of the action's turnover in the
output asset, sized from the actual fill as kind 0 does (~120 bytes of 3,002); or document that kind 2 ships
with no keeper economics. Either way, it does not fix M4-1.

## L4-5 · Low · Kind 1 is now an opt-in production strategy whose published score divides by zero for life

*D-4, delta lane, Low; round 3's I-8 with its "no impact" condition gone. Round 3 graded it Info because "kind 1
is marked DRAFT and registered by nobody". `d5218ee` relabels it "Opt-in: production must register its exact
code chunks", the rehearsal script registers it, the CI fork job requires its lifecycle test, and the runbook
wires keepers for it. Stands, by analogy with round 3's L-2 (a scorecard that reads wrong, no value moved).*

**Location** `src/v2/HedgeFunV2BuybackTreasury.sol:30-37` (`book()` never writes `totalStockReceived`) against
`src/HedgeFunTreasuryBase.sol:152,300`; the formula at `README.md:385` and `docs/REFERENCE.md:1063`.
**Status** EXECUTED (`poc/delta/AuditDelta4Kind1.t.sol::test_kindOneScorecardDividesByZeroForLife`: after
graduation, one buy-back and one later booking, numerator 1.015e20 stock-wei, denominator 0). Loser: a reader
of the token page — a front end computing the score as `README.md` says shows Infinity, NaN or nothing. Option
gain: a creator who prefers an unscorable strategy to a scored one. **Fix** `totalStockReceived += pending;` in
`book()` — ~20 bytes against kind 1's **own** 9,717 (its own chunked initcode; 0 on the factory, 0 on
`CurveDeployer`); or state in `README.md` and `LAUNCH_KIT.md` that the score is undefined for kind 1 and give the
front end the substitute (`totalStockSpentOnBuybacks + buybackStock` against `GraduationCapitalSplit.treasuryStock`).
**Must land before kind 1 is registered** — the registration records the exact code chunks.

## L4-6 · Low · Five of the engine's twelve documented execution-time checks are pinned by no test

*C-1, claims lane, Low. The engine lane's safe list items 12, 16, 17 and 18 cover four of the same five checks
and prove them present with its own PoCs; the claims lane's mutations prove the repository's suite would not
notice their removal. Both true. Low under round 3's "grade the fix path" rule (the M4-1 engine-side fix edits
`execute()`'s path); Info under the rubric alone.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:375` (nonce), `:394` (codehash at execution), `:400` (gas),
`:328,348` (capability and direction). **Status** EXECUTED — mutations `E01`, `E03`, `E04`, `E08`, `E10` all
GREEN (`E01` under the full 104-suite run too): an engine that forwarded all its gas to the policy, accepted a
stale nonce, skipped the runtime codehash, ignored the registered capability, or sold inside its own deadband
would pass every test in the tree. The mocks for four of the five already exist in
`test/mocks/StrategyPolicyMocks.sol`; the adversarial-mocks file's own header says the engine tests "should
reuse these policies", and for these they do not. (On a Cancun chain the execution-time codehash re-check
guards a path that is not reachable — EIP-6780 — so its absence from the tests is the least of the five.)
**Fix** `C2`–`C5` from `poc/claims/AuditClaims4.t.sol` into `test/V2StrategyEngine.t.sol`, and a corrected `C1`;
~90 lines, 0 bytes. **`C1` as shipped does not pin the nonce** (triage replay, 2026-09-28): with `E01` applied it
still passes, because `WrongNonceStrategyPolicy` proposes a buy of `amountIn = 1` (a millionth of a USDG), and with the nonce check gone the
engine refuses that on the minimum-lot floor with the same `NotDue` that `C1` expects. A pin that does turn red
under `E01` — a wrong-nonce policy proposing an *executable* 50 USDG buy at a 25% stock share, asserting `NotDue`
with nonce, USDG and booked stock unchanged — was run by triage and is written out in `VERIFICATION.md`. `C2`–`C5`
were replayed against `E03`, `E04`, `E08` and `E10` and each turns red as claimed.

## L4-7 · Low · The oracle/venue health gate of `execute()` is untested, the invariant suite cannot see it, and PR #91's coverage sentence is wider than what the invariants assert

*C-2 (Low) with C-12 (Info) folded in as its documentation limb. Low on the fix-path rule; the engine lane's
safe item 24 proves the gate present with PoCs that move feed and venue together.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:252-255`. **Status** EXECUTED — mutations `E06` (drop
`if (!ok) revert Unhealthy()`) and `E07` (drop the `live` check) GREEN, **including the 256 × 500 invariant
campaign** whose handler shoves the venue ±50% and pauses the oracle — because the four invariants assert that
state stays consistent (nonce = successes, buckets ≤ balance, turnover ≤ cap, digest unchanged on failure), not
that the gate closed. The swap's own `maxSlippageBps` bound masks large deviations; a deviation between the
50 bps gate and the 100 bps slippage bound executes under the mutation (`C13`). PR #91's sentence that the
invariants "cover … stale-feed recovery, oracle pause, venue deviation" describes what the handler *does*, not
what any invariant *asserts*: the engine is shown to survive them, not to stop for them. The `live` limb is
reachable only with `bandBpsPerHour > 0` during a scheduled closure, which no engine fixture sets up; no PoC was
written for it. **Fix** `C13` for the deviation gate; a closed-market fixture with a band for the `live` limb;
one invariant asserting `failedExecutions` grew whenever the handler's last action left `health()` false; and
"survives", not "covers", in the PR text. 0 bytes.

## L4-8 · Low · The three new owner-only registry entry points and `deploy()`'s factory-only guard are unpinned

*C-3, claims lane, Low. Low on the fix-path rule (M4-2's setter mirror edits `V2TreasuryDeployer`); Info under
the rubric alone, exactly as round 3 graded I-14.*

**Location** `src/v2/V2TreasuryDeployer.sol:218` (`registerPolicy`), `:197` (`registerEngineKind`), `:281`
(`disablePolicy`), `:369` (`deploy`). **Status** EXECUTED — mutations `D01`, `D02`, `D03`, `D05` GREEN (`D01`
under the full suite too); the legacy `registerKind` is pinned (`D04` RED, the control) by a test that was
evidently not extended when the three entry points were added beside it. `registerPolicy` is the "policy
admission" gate `STRATEGY_ENGINE.md` describes — the one place governance rejects a mutable or proxy policy
(I4-2) before a creator can launch under it; an open registry admits the `MutableDecisionStrategyPolicy` and
`MutableStrategyPolicyProxy` the fixture tests prove the codehash cannot catch. The engine's caps bound what such
a policy can do; they do not bound who chose it. `deploy()` without `_onlyFactory()` would let anyone create
treasuries through the deployer and emit `TreasuryCodeBound` for them. **Fix** `C9`, `C10`; ~25 lines, 0 bytes.

## L4-9 · Low · The engine's configuration bounds are enforced and untested, except the reserved bits

*C-4, claims lane, Low. Low on the fix-path rule — M4-2 and L4-1 add lines to exactly this function, and a fix
PR that touched it with nothing pinning the six existing bounds could drop one silently.*

**Location** `src/v2/HedgeFunV2EngineTreasury.sol:137-139`. **Status** EXECUTED — mutation `E17` deletes all six
bounds (`deadband < target`, `target + deadband < 10000`, `cooldown ≠ 0`, `maxTrade ≠ 0`, `maxTrade ≤
sellChunkUsdg`, `maxDaily ≥ maxTrade`) together with the suite green; only `packed >> 64 == 0` is pinned (`E16`
RED). A treasury launched with `deadband == target` never buys and one with `target + deadband ≥ 10000` never
sells: a dead engine whose capital sits where graduation left it, immutable. `V2RebalancePolicy._validate`
re-checks a subset, but a policy is advisory and a different policy need not. The fixture's `sellChunkUsdg =
uint128.max` means the chunk limb has never been binding in any test. **Fix** `C12` (six launches, each
expecting `TreasuryDeployFailed`); 0 bytes.

---

# Info

**How these were settled.** Every item below was graded Info by each lane that reported it, and triage kept the
grade on the rubric's own line — "no value impact" at the tip. The four coverage holes that were raised to Low
(L4-6 to L4-9) were raised because this report's own fixes edit the lines they leave unpinned with nothing
behind them; the coverage holes here either sit off every recommended fix path (I4-12, I4-13) or have a second
check that still holds if one regresses (I4-11). Each item's own settling sentence is marked *Grade.*

**I4-1 · The out-of-range action word is refused by the decoder with an empty revert; the engine's own range
check is dead, and the mock that documents it is wrong** (E-5 = C-8; both lanes Info). `abi.decode(result,
(StrategyIntent))` at `:407` validates the enum before `_basicIntentValid` runs, so a policy returning action
word 64 reverts with *empty* data — not `BadIntent`, not `Panic(0x21)` — and the comparison at `:376` can never
be false (`E18` GREEN; `test_E5_*`, `C6`). Fails closed; nonce, cooldown, epoch, state and balances unchanged.
What is lost is a named error a keeper could tell from out-of-gas. `test/mocks/StrategyPolicyMocks.sol:160`
describes a check the engine does not perform. Two diagnosability notes of the same status: `preview()`
reverts `PolicyFailure` rather than answering `(false, Hold, 0)` when the policy reverts or runs out of gas;
and the policy is called (up to 500k gas) *before* the cooldown check, so a keeper calling during a cooldown
pays the policy's gas to be told `NotDue`. *Grade.* Info from both lanes: it fails closed with nothing
committed; what is lost is an error's name. Fix: decode the raw word before the enum cast (then `C6` expects
`BadIntent`) or delete the dead comparison and fix the comment.

**I4-2 · Codehash pinning does not pin semantics: mutable-storage, proxy and EIP-7702 policies all pass
registration, configuration and the constructor** (E-7; the claims lane's K-21/K-26 find the limitation
correctly documented in `STRATEGY_ENGINE.md:29-32`). EXECUTED (`test_E7_*`): a policy with a public `setAction`
sells one bounded chunk, is switched to `Hold` by an arbitrary caller, and the strategy is off; a proxy passes
`registerPolicy` (its fallback delegates `policyMetadata()`), launches, and is re-pointed afterwards — same
address, same codehash. The blast radius, which is the point of executing it: a switched policy can only choose
*when* to act among the moments the engine already permits; it cannot pick a route, recipient, pool or amount
beyond the cap. Worst case is a strategy that stops. EIP-7702 (REASONED, tests run at Cancun): a delegated EOA
has 23 bytes of code and a codehash that is stable while the *delegate* changes; this chain's low-key EOAs
already carry such code. The governance rule should say "no EOA, no proxy, no mutable storage" explicitly —
and L4-8 is the test that the rule has a gate to stand behind. *Grade.* Info: a limitation the document states
correctly, whose worst case is a strategy that stops.

**I4-3 · A launched salt's deployer record stays writable** (E-8). EXECUTED (`test_E8_*`): after launch,
`setEngineConfig` on the same `(symbol, nonce)` rewrites `engineConfigOf(salt)` and re-emits `EngineConfigSet`;
`setStrategyKind` rewrites `strategyKindOf(salt)`. The treasury's `engineConfig()` and immutables are unchanged
and a relaunch on the salt cannot happen. An indexer reading the deployer's record or its events instead of
`treasury.engineConfig()` can be made to disagree with the chain by the creator. Read the treasury. *Grade.*
Info: the treasury's state is untouched; only an indexer reading the wrong source is misled.

**I4-4 · Unused V1 rule parameters still gate an engine launch, and a launcher contract cannot set the
config for a creator** (E-10, REASONED). `Request` carries `tp1/tp2/dip/stop/lot/band`; the engine reads none
of them, yet `HedgeFunTreasury.sol:35-42` and `V2TreasuryDeployer.sol:360-366` still refuse a launch whose
*ignored* rule does not clear friction. The engine config is keyed by the creator's own `msg.sender`
(`:314`), so a vouched launcher launching "on behalf of" a creator cannot set it. `HedgeFunV2BuybackTreasury`
has the same shape and says so in its header; the engine's header does not. *Grade.* Info: a launch constraint
and a UX gap; no value moves.

**I4-5 · `policyGasLimit` is frozen** (E-11, REASONED). The manifest's `maxGas` becomes an immutable and is the
exact gas handed to every `decide()`; a hard fork that reprices the opcodes `decide()` uses past it turns every
`execute()` into `PolicyFailure` for good (`buyback()` survives). The fixtures register 150,000 for a policy that
needs a small fraction; the ceiling is 500,000. Register with headroom. *Grade.* Info: it needs a future hard
fork that reprices `decide()` past its registered gas, the buy-back survives it, and the same holds for every
frozen constant in this protocol.

**I4-6 · A parked stock fee is unobservable on chain, and `FeesCollected` now means "delivered", not
"earned"** (D-1). EXECUTED (`AuditDelta4Vault`): while the issuer refuses delivery, `collectFees()` returns and
emits `stockFee = 0` although stock was taken from V4; when the refusal lifts, one call reports the whole
backlog. The stream still *sums* correctly (four collections, Σ `stockToTreasury` == the treasury's budget
delta), so a summing indexer is not misled; a per-period one is, and an alert on "no stock fee" sees nothing
unusual in a zero. The only view of the parked amount is `stock.balanceOf(vault)`, which also counts donations
(round 3's L-5) and cannot be split. Fix, 0 bytes: a runbook alert on `FeesCollected(0, >0)` and a
balance-based monitor. A getter is ~40 bytes on `CurveDeployer`'s 12 and does not fit. *Grade.* Info: the fee
is delivered in full once the refusal lifts; only its timing is invisible.

**I4-7 · The arming buy-back is untouched; only the rate it arms is zero, and only on this factory** (D-2).
EXECUTED (`AuditDelta4Spike::test_oneWeiBuybackArmsNothing_butStillConsumesTheCooldown`). One wei of LP fee
still lets anyone call `buyback()`: `spent = 1, burned = 0`, `noteEvent()` still writes `lastEventAt`, and
`lastBuybackAt` is set, so a real pot arriving next waits one `buybackCooldown` (60 s). Round 3 offered two
fixes; the first (`spikeBps = 0`, structural in `HedgeFunV2Factory._openAndSeed`) was taken and the second
(gate `noteEvent()` on `burned != 0`, base-side) was not. The hook still honours any nonzero `spikeBps`, the
base still fires, and a third factory — or a V2 factory whose `_openAndSeed` is overridden again — registering a
graduated pool with `spikeBps != 0` has round 3's M-0 back in full. Fix: write the invariant into
`docs/SECURITY.md` ("graduated V2 pools carry `spikeBps = 0`; a nonzero rate on a pool whose `buybackStock` is fed
by anything but realised profit re-opens M-0"), or spend ~15 bytes of `TreasuryDeployer`'s 1,001 on
`if (burned != 0) IHedgeFunHook(hook).noteEvent();`, which forfeits nothing since `HedgeFunTreasury` already
differs from `main`. *Grade.* Info: on this factory the rate it arms is zero and a 60-second delay per wei of
fee is not a loss; the residue is a condition on any future factory, which is why it is written down.

**I4-8 · `buyback()` is now a writer of the sizing cache, gated by `tryPrice()` alone; every earlier writer went
through `health()`** (D-3). EXECUTED (`AuditDelta4Buyback`, three tests): with the mocked stock venue shoved 20%
off the oracle, `health()` is shut and `buyback()` still notes the feed's price into `lastGoodPrice`. What
holds: the write happens only on a *successful* buy-back; a closed-market buy-back sized off the cache cannot
refresh it; the five-day window cannot be extended from inside a closure (27 h into a stale feed the cache
stays put; at 5 d + 1 s it reverts `Unhealthy`); the sole reader is the buy-back's own sizing fallback, whose
execution price is bounded by the token pool's TWAP/anchor, not by this number. Loser: none. Recorded because
it is the one delta line that changes V1 semantics for any future V1 deployment (`HedgeFunTreasury` +19,
`TreasuryDeployer` 1,020 → 1,001) and the deviation-gate asymmetry is what a later reader would assume away.
*Grade.* Info: its sole reader's execution price is bounded elsewhere. Fix: one sentence at
`HedgeFunTreasuryBase.sol:141-145`. 0 bytes.

**I4-9 · Round 3's M-5 recurs one round later on the PR that fixed it: numbers regenerated at one ref and
shipped at another** (D-5 = C-6 = C-7 = C-11's provenance bullet; round 3's I-23 regressed). EXECUTED (clean
builds of `9679614` and `5aedceb`, full suites, ABI regeneration). (a) PR #84's body says 1,399 passed / 51
skipped and a factory at 24,433 bytes with 143 free; at its own tip the suite is **1,422 / 52** and the factory
**24,551 / 25** — the 143 is the figure round 3's I-13 already flagged, and `DEVELOPMENT.md:98` says 1,420 /
51 (1,471 tests), so three counts for one tip inside one PR. (b) `docs/V2_BONDING_CURVE.md:265-274`'s size table
lists `V2TreasuryDeployer` at 4,773 / 31,947; the tip builds **10,737 / 38,024**, and `HedgeFunV2EngineTreasury`
(21,574 / 27,866), `V2RebalancePolicy`, `TreasuryDeployer` and kind 1 are absent — I-23 asked for the last two
and the table lost a row instead. (c) `docs/V2_ADVERSARIAL_REVIEW.md:99`'s "1,422 / 0 / 52" and `README.md:169`'s
"1,420" were written before the merge; the tip measures **1,474 / 0 / 52**. (d) `abi/SURFACE.md:3` and
`docs/REFERENCE.md:7` say "generated at `7027539`", a tree with no `creditPendingStock`, while their content is
the merged tree's; `tools/check_docs.py` compares the reference's content and evidently not its commit line.
*Grade.* Everything load-bearing at the tip itself reproduces (PR #91's own 104 / 1,474 / 0 / 52, 21,574 / 27,866, 30 lab
tests, 369 links) — which is why this is Info where round 3's M-5, with a GO verdict scoped to a ref two
contracts predate, was Medium. Loser: the next auditor. Fix: regenerate at the merge commit; have
`check_docs.py` require the provenance hash to be an ancestor-or-equal of `HEAD` whose tree matches; drop the
counts from PR bodies in favour of the generated document.

**I4-10 · `"editor": null` in a metadata plan now means "revoke", and the one committed plan carries it**
(D-6, REASONED; one read-only `eth_call` on 2026-09-28: `editor()` on `0xF5501c0D…F332` returns `address(0)`).
`tools/metadata_batch.py:218-226` (d5218ee): before, a falsy `editor` was skipped; now an explicit `null` emits
`setEditor(address(0))` unless the chain already reads zero. `deploy/metadata-crclgrid-2026-09-22.json:20` says
`"editor": null` with an intent line consistent with revoke, and the token's editor is zero, so re-running the
tool today is a no-op. A future plan copied from this one with an editor since appointed would revoke it, in a
batch the operator reads before signing. `OPERATIONS.md:249` documents appointing an editor, not that `null`
revokes. *Grade.* Info: re-running the committed plan today is a no-op, and a future revoke would sit in a batch
the operator reads before signing. Fix: one sentence. 0 bytes.

**I4-11 · "Disabling a policy prevents new predictions/launches" is pinned only for new configurations** (C-5).
EXECUTED (`E24` GREEN): a salt configured *before* the owner disabled its policy is blocked from predicting and
launching by two checks (`V2TreasuryDeployer.sol:347` and the engine constructor at `:133`), and both delete
together with the suite green; the existing test disables and then tries to *configure* a new salt. *Grade.*
Info, and not Low under the fix-path rule even though M4-2's fix edits the constructor function that holds one of
the two checks: each check blocks the launch on its own (the deployer's `_code` reverts `BadPolicy`; the
constructor fails the deploy), so a single regression changes nothing — `E24` had to delete both. Fix: `C7`,
which turns red under `E24` (triage replay).

**I4-12 · `creditLiquidityFee`'s vault-only check is untested** (C-9). EXECUTED (`T01` GREEN): the only test
pranks *as* the vault. If the check were lost, a stranger could push their own stock into `buybackStock` — a
donation into the buy-back bucket, which is not a loss. *Grade.* Info: off every recommended fix path, and its
failure is a donation. Fix: one negative test.

**I4-13 · Defensive checks with no observable behaviour and no test** (C-10). EXECUTED (`E14`, `E20`, `E22`,
`D06`, `D07`, `D10`, `D12` GREEN). Listed so the next round need not re-run them: the post-fill daily check
(`:272`, unreachable because `offered` is already capped); the pre-swap minimum-lot check (`:334,354`; the
post-fill check at `:271` catches the same case); `deploy()`'s introspection (`:384-387`; the constructor fails
first); `registerPolicy`'s gas/return/hash bounds (`:219-223`, re-checked by the engine constructor); the
duplicate-key guard (`:253`; the key is the hash of the manifest); the zero-metadata guard (`:237`). And
`execute()`'s own `_bookInventory()` (`:251`), whose deletion means a donation is booked by the next explicit
`book()` rather than being part of *this* observation — a narrower reading of `STRATEGY_ENGINE.md`'s "becomes
part of the next strategy observation" than the sentence gives. *Grade.* Info: each check is shadowed by one
that catches the same case first, and the `_bookInventory` call changes when a donation is booked, not whether.

**I4-14 · Documentation narrower than the code** (C-11 less its provenance bullet, which is I4-9).
`STRATEGY_ENGINE.md` ¶3 says the limits are stored "as immutables"; the identity fields are, the limits are a
private storage struct written once with no setter (`:33,96`). `abi/SURFACE.md` lists `buyDip()`,
`stopLoss(uint256)`, `takeProfit(uint256)` under `read` for the engine; they are `pure` and always revert
`UseExecute`, and a front end reading SURFACE alone would offer them. PR #84's body says "50/50 split"; it is
`lpBps`, an owner dial (round 3's M-6, since fixed in the documents but not the body). *Grade.* Info: each
document says less than the code does, and the worst consequence is a front end offering three calls that revert.

---

## The round-3 ledger at `5aedceb`

Compiled by the delta lane; evidence is `file:line` at the tip, and where a round-3 PoC exists, what it does
now. Vocabulary: **FIXED** (the mechanism is gone), **PARTIALLY** (one limb, or process/disclosure only),
**NOT ADDRESSED**, **ACCEPTED** (the delta chose not to, for a reason round 3 itself gave).

### Mediums

| ID | status | evidence |
|---|---|---|
| **M-0** LP fee re-arms the 90% sell spike | **FIXED for V2, with residue.** `HedgeFunV2Factory._openAndSeed` freezes `rates.spikeBps = 0` (`:104-106`) for every V2 pool whatever the Defaults say; the rehearsal Defaults also zero it. Round 3's four arming PoCs now fail on `1000 != 9000`. The residue is I4-7: the fuel line still exists, the zero-burn one-wei buy-back still calls `noteEvent()`, and the base-side gate was not taken, so any factory that registers a graduated pool with `spikeBps != 0` has M-0 back. | `src/v2/HedgeFunV2Factory.sol:104-106`; `poc/delta/AuditDelta4Spike.t.sol` |
| **M-1** `collectFees()` couples the stock leg to the token burn | **FIXED**, in the shape round 3's adversarial pass proposed: private `pendingStockFee` + `try this.creditPendingStock()`, `predictVault` deleted to pay for it. Cost: `CurveDeployer` 176 → **12** (the pass predicted +15). Round 3's coupling PoC now fails "did not revert" — the burn goes through. The two triggers no fix can reach (a blocklisted vault, a global pause, inside V4's `take`) still stand by design and the docs now say so. Regression hunt: none found; I4-6 is the observability residue. | `src/v2/V2LiquidityVault.sol:105-127`; `poc/delta/AuditDelta4Vault.t.sol` |
| **M-2** a full raise is a one-directional buy through the stock's only V3 pool | **PARTIALLY (process, 0 bytes).** The listing rule is now step 3 of `docs/V2_DEPLOYMENT_REHEARSAL.md:38`: compute `Rg`, fork-simulate sourcing it as a single buyer, check the post-swap spot against the oracle and V3 TWAP at the tightest live V1 gate, replay each affected V1 treasury's `health()`, keep the listing disabled until it passes. No code enforces it and the doc says so. The ten-of-eighteen count is UNMEASURED at the tip. L4-3 is the same rule needed in reverse. | `docs/V2_DEPLOYMENT_REHEARSAL.md:38-39` |
| **M-3** buyer funds stranded on a curve that cannot graduate | **PARTIALLY.** The structural instance (INTC) is covered by the same runbook rule, with the correct caveat that direct-stock buys remain possible. The other limb — a failed graduation should leave a retryable, observable state — is NOT ADDRESSED: `graduate(uint256)` is still dead code (L-1), a reverting graduation still rolls `Ready` back inside the final buy, and the factory has 25 bytes. | `src/v2/HedgeFunV2Factory.sol:129-142` |
| **M-4** parameter floors wider than the project's own conclusion | **PARTIALLY (disclosure only).** `MIN_LP_BPS = 1000` and `MAX_SALE_BPS = 9000` unchanged. The rehearsal now says the code's bounds "are validity bounds, not recommended settings; the experiment's 70% / 60% is a hypothesis", requires `saleBps` and `lpBps` written explicitly into the Safe proposal, and forbids relying on an unset default. Bound-versus-policy resolves as policy, now labelled. M4-2 is the same pattern on the engine. | `docs/V2_DEPLOYMENT_REHEARSAL.md:39` |
| **M-5** the documents' numbers do not reproduce | **FIXED for the table, re-staled by the merge for the counts.** The mature-TWAP table now reproduces at the tip (785.7778 / 351.0870 / 1.7643 / 92.1512, EXECUTED 2026-09-28) and names its tests and date; the GO verdict is re-scoped as historical (I-15). The counts and provenance are stale again — I4-9. The fork block `70,717,634` and the "6.450877 GME" figure round 3 could find in no test are still cited. | `docs/V2_ADVERSARIAL_REVIEW.md` |
| **M-6** documents disagree on who sets the LP split | **FIXED.** `V2_DUAL_ENGINE_REVIEW.md:11-12` now reads `floor(reserve × lpBps / 10000)`, owner-set per stock, 10–100%, default 50%, frozen per treasury — what the code does. | |

### Lows — none addressed

| ID | status |
|---|---|
| **L-1** `graduate(id)` fallback can never fire | NOT ADDRESSED. Still at `HedgeFunV2Factory.sol:136-137` with its "Permissionless fallback" comment; PoC passes at the tip. Still the one fix that would *add* margin to a 25-byte contract. |
| **L-2** scorecard numerator moves on a bare `transfer` | NOT ADDRESSED. `docs/SECURITY.md` unchanged; no V1 test with `unbookedStock() > 0` added; PoC passes. `TreasuryDeployer` is now 1,001. |
| **L-3** `maxBuybackImpactBps` never checked against round-trip friction | **NOT ADDRESSED, and the candidate configuration sits on the wrong side of it.** `V2TreasuryDeployer._validate` (`:360-366`) still checks only the stop. The rehearsal's Defaults are `minTaxBps 100`, `maxBuybackImpactBps 300`, `lpFee 3000`; round 3's threshold at those values is 257.7 bps, so 300 is inside the window it measured as profitable (+0.02 USDG per cycle — real, tiny, the reason it was Low). The zero-byte fix, `minTaxBps ≥ 122` in the Defaults, was not taken. |
| **L-4** unpaid, undeadlined `book()` sets the cost basis of the whole treasury share | NOT ADDRESSED. `HedgeFunV2Treasury.book()` (`:48`) unchanged; the factory's `try … book() … catch {}` at `:155` unchanged. L4-4 is the same shape on the engine. |
| **L-5** vault addresses predictable before graduation; anything sent there is destroyed | NOT ADDRESSED in substance; the on-chain helper was deleted. The address is still a public CREATE2 function of public inputs (the repository's own test now computes it locally, `test/V2DualEngine.t.sol:57-60`); no document says the vault has no recovery path. The deletion bought 51 bytes and removed the one `@notice` slot that could have carried the warning. |
| **L-6** the last tenth of every curve is negative-EV at purchase | NOT ADDRESSED (design); disclosure improved — the rehearsal demands early-buyer exit scenarios at the chosen `saleBps`/`lpBps`. |

### Infos

FIXED: **I-13** (the "143 bytes" is gone; the doc says 25), **I-15** (the GO verdict is re-scoped: "at `885123e`
only … this verdict does not approve its deployment"). PARTIALLY: **I-2** (`lastEventAt = 0` still uncommented
but no longer matters — the rate is 0 and three documents say so), **I-16** (counts restated and stale again;
the stale block and the GME figure remain). Worsened: **I-8** → L4-5. Regressed: **I-23** → I4-9 (the size table
lost a row and gained a stale one). ACCEPTED-BY-DESIGN: **I-10**, **I-18**, **I-21** (`HedgeFunFactory` byte
identity; `bind()` permissionless with the rehearsal binding in one run). NOT ADDRESSED: **I-1** (the hook
validates nothing about the vault; PoC passes), **I-3**, **I-4** (round 3 ranked it first for remediation — the
base comments still say the anchor is not seeded at `wire()` while `HedgeFunV2Treasury.wire()` seeds it; the one
zero-byte item nobody touched), **I-5**, **I-6**, **I-7**, **I-9**, **I-11** (`_minLpFee() = 1` unchanged; the
rehearsal ships 3000, and M-0's inlet is now severed by the rate, one of round 3's two defensible positions),
**I-12**, **I-14** (**re-EXECUTED**: with `V2LiquidityVault.sol:71`'s `onlyFactory` deleted the full suite is
still 1,474 / 0 / 52 — and with 12 bytes on `CurveDeployer`, the split that round 3 withdrew as a causal story is
now the only way to add anything to the curve or the vault, which puts the story back), **I-17**, **I-19**,
**I-20**. **I-22** is moot (the spiked-case revenue line).

### Round 3's PoCs at the tip

`audit/round-3-2026-09-27/poc/run.sh` staged verbatim fails to compile (`AuditLane13V2b.t.sol:92,189` calls the
deleted `predictVault`). With that file patched to compute the CREATE2 address locally — the same four lines the
author added to `test/V2DualEngine.t.sol` — 6 suites, 32 tests: **27 pass, 5 fail, all five being fixes landing.**

| test | at `03ad70e` | at `5aedceb` | meaning |
|---|---|---|---|
| `test_T3_oneWeiPotArmsTheNinetyPercentSpike`, `test_T3_oneWeiSpikeIsReArmableEvery240s`, `test_T3_e1EndToEndByAnUnprivilegedCaller`, `test_ADV_h1DoesNotNeedLastEventAtZero` | pass (bug shown) | FAIL `1000 != 9000` | M-0 fixed |
| `test_L13_blockedStockLegAlsoStrandsTheTokenBurn` | pass | FAIL "did not revert" | M-1 fixed |
| `test_L13_blockedVaultAlsoStopsTheTokenBurn` | pass | pass | the unfixable trigger, as round 3 said |
| `test_T3_smallestRealFeeThatFundsThePot`, `test_T3_smallestBuyThatRefillsThePot` | pass | pass | the fuel line still exists (I4-7) |
| `test_ADV_spikeBpsZeroKillsH1` | pass | pass | now the shipped state |
| `test_L13_graduateFallbackIsUnreachable`, `test_L13_vaultDonationsArePermanentlyLocked` (patched), the two L-2 tests, `test_theHookAcceptsAnyContractAsTheVault` | pass | pass | L-1, L-5, L-2, I-1 unchanged |
| the other 15 (curve invariant fuzz, vault principal, graduation split, delegatecall isolation, last seller, V1 `lpFee`, snipe window, registration uniqueness, opening burn, pool depth, crossing buyer) | pass | pass | round 3's safe list holds where it was executed |

---

## Checked and found safe

Merged from all four lanes; each carries the line that makes it safe and the lane item it came from (engine
1–32, delta 1–21, economics, claims by mutation). Proved at `5aedceb`. **Two qualifiers a reader needs.** First,
"present" and "pinned" are different claims: items marked † are proved present by the engine lane's own PoCs
but would *not* be caught by the repository's suite if removed (L4-6, L4-7). Second, item marked ‡ is the bound
that M4-1 lives inside: the bound holds; what is inside it is the finding.

**Custody and authority.** The only outward stock/USDG movement is the V3 swap callback paying the listed pool
(`PoolTrader.sol:141-145`: `msg.sender == pool && _swapping`); the engine adds no transfer, no `approve`, no new
callback; allowances to the venue, the policy and the caller are zero after a sell and a buy (engine 1). The
buy-back's stock leaves only through `poolManager.settle()` inside `unlockCallback` (engine 2). The policy has no
custody: `STATICCALL`ed (`:400`; `E19` RED), cannot write state, holds no allowance; 159-byte return, gas bomb,
dirty nonce word and action word 64 each fail closed with nonce, cooldown, epoch, state and balances unchanged
(engine 3). Re-entry from inside the swap is refused — `execute`, `book`, `buyback`, `creditLiquidityFee` share one
guard; a venue calling all three from inside `swap()` gets 0 of 3 (engine 4). The hook never calls into a
treasury (engine 5). Sells cannot reach the buy-back bucket: offered `≤ bookedStock`, `creditLiquidityFee`
credits `buybackStock` only, `buyback()` spends `≤ buybackStock`; `bookedStock + buybackStock == balance` holds in
the invariant suite and every PoC (engine 6, economics). Donations are swept with no oracle and no lot;
`unbookedStock()` floors at 0 so an issuer burn cannot underflow it (engine 7). A donation that crosses the
band costs its donor ten times the most a sandwich of that action could return — $1,110 donated for a $555 sale
of which at most $7.21 is capturable (economics X-8, EXECUTED). The pool cannot make the treasury act: inventory
is priced at `health()`'s oracle price; spot enters only as a gate (a 51 bps push shuts, 49 opens, neither
changes `preview()`'s action) (economics, engine 25 ‡).

**Commitment integrity.** Config → initcode → CREATE2 → terms: `_code` appends the 192-byte `abi.encode(config)`,
the address is in `_terms`, a config change after `predict` reverts `Restated` (`E02` RED), and a stranger's
`setEngineConfig` lives under a salt containing *their* `msg.sender` and cannot touch the creator's prediction
(engine 9). Post-launch immutability: `policyImplementation`, `policyRuntimeCodeHash`, `policyCapabilities`,
`policyGasLimit`, `policyReturnLimit`, `configHash` are immutables; `_engineConfig` has no setter;
`disablePolicy` flips one bool for *future* launches (engine 10; I4-11 for what is pinned). Registry append-only:
`_kinds` is only pushed, a policy key is set once and is the hash of every manifest field (engine 11; `D10` is
unpinned, I4-13). Codehash pinned four times — constructor, `setEngineConfig` (`D09` RED), `_code`, every
`_policyIntent` † — and post-Cancun there is no `SELFDESTRUCT` that outlives its transaction, so the runtime
re-check is defensive (engine 12). `deploy()`'s post-check reads back `engineVersion`, `strategyId` and a
non-zero `configHash` so a non-engine kind registered as an engine fails closed (engine 13). `makeChunks` is open
and inert: only the owner registers, and registration records `keccak(a.code ++ b.code)` (engine 14). Options,
buy-back and unknown capabilities are rejected in the constructor (`E15` RED, three tests) and at configuration
(`D08` RED); the legacy setter is refused on engine kinds (`D11` RED); a pre-registry PR #84 factory cannot
acquire the engine APIs through `registerKind` (claims K-20).

**Limits and state.** Return bound: `returndatasize()` is read before anything is copied; 64 KiB and 159 bytes
both refused (`E05` RED) (engine 15). Gas bound: `staticcall(gasLimit, …)` with `gasLimit ≤ 500,000` at
registration and construction; the bomb costs about the manifest, not the block † (engine 16). Capabilities
enforced at execution, not only at registration: a sell-only policy proposing a buy, a spot policy proposing
`BuybackBurn` → `BadIntent` † (engine 17). Direction gates: no policy can sell an under-weight book or buy an
over-weight one † (engine 18). Sizing: sell `≤ min(maxTrade, remainingDaily, excess)`, buy `≤ min(requested,
maxTrade, remainingDaily, deficit, usdgInventory)` (`E11` RED two tests, `E12` RED); a `uint256.max` request is
capped; rounding never sells through the target (engine 19). Dust floors before and on the actual fill; the
post-fill revert unwinds the swap, its transfers, `_notePrice` and `_noteTokenSpot` atomically (`E13` RED, four
tests including the invariant replay) (engine 20; delta 14 for the `BadIntent → NotDue` change in 7027539). Partial
fills debit `actualInput` and credit `actualOutput` (`E23` RED) (engine 21). Cooldown enforced independently of
the policy (`E09` RED), inclusive boundary, no overflow, and it survives the UTC epoch boundary (claims K-23,
pinned by `C8`) (engine 22). Nonce and state advance only after everything; no `try/catch` anywhere in `execute()`;
`strategyNonce == successfulExecutions` is an invariant (engine 23). Oracle and venue health: `health()` plus a
live `tryPrice()`, which is false on any calendar closure and on `oraclePaused()` — **across a weekend the
rebalance cannot execute at any price**, even where kind 0's band path is open; `oraclePaused()` reverts the same
way (economics X-3, EXECUTED; engine 24 †). What is open, and its bound: a print inside `maxStockAge` is traded on
while the pool sits within 50 bps of it; worst fill relative to the true price is `stale gap + maxDeviationBps +
maxSlippageBps + poolFeeBps` ≈ 2.3% while the oracle network prints — the same shape as kind 0, inherited, and
`CLAUDE.md` already states there is no secondary oracle (economics X-3). The context is priced by the oracle, not
the venue; the fill is bounded by `oracle ± maxSlippageBps` with the realised average re-checked ‡ (engine 25).
Arithmetic: 512-bit `mulDiv` throughout; `stockValue + usdg` overflow guarded; `totalValue == 0 → NotDue`;
`targetBps ∈ [deadband+1, BPS−deadband−1]` so no underflow at `:347` and no overshoot past BPS; the policy divides
by `stockValueUsdg` only where it is positive (engine 26). The policy's looser validator is harmless: for any
launched config its `BadConfig` is unreachable (engine 27). Token ordering and decimals: stock-as-token0 and
USDG-as-token0, at 18 and 6 stock decimals, each moving exactly the pool's reported amounts in the right direction
— the engine suite covers one of the four (engine 28). Graduation → wire → book order holds, and `execute()`
before graduation is `Unhealthy` (engine 29). `preview()` and `execute()` agree on inventory, limits and dust
floors (engine 30; `E21` RED). Execution loss cannot ping-pong the band: a sell to target loses at most 1.3% of
`band × value`, which moves the share by under 1.3% of the band (economics, REASONED). Corporate actions do not
unbalance the ledger: raw balances never rebase and the feed carries the multiplier (economics, REASONED from the
project's own assessment; not re-verified on chain). Reserved config bits refused (`E16` RED).

**The delta.** The parked fee cannot be lost — it is the vault's own balance, `pendingStockFee` resets only in
the success branch, `creditPendingStock` transfers exactly it and checks both balances moved by exactly that
(delta 1). It cannot be double-counted (delta 2). The self-call guard holds — outsider, treasury, pool manager
and factory all revert `Busy` (`V03` RED) (delta 3). Gas starvation cannot force a park: success is monotone in
gas (largest failure 227,000, smallest success 228,000) and no budget yields `(0, >0)` (delta 4). The catch cannot
block the burn, which is outside the `try` and burns the vault's own balance (`V01` RED) (delta 5). A delivered
fee is cleared (`V02` RED — caught by an adversarial fuzz in `V2AdversarialTrading`, not by the vault's unit tests;
`C11` pins it directly). Reentrancy during `creditLiquidityFee` → `Busy` → caught → parked, state consistent
(delta 6). A blocklisted vault and a global pause still revert both legs inside V4's `take`, as round 3 said no
fix could avoid (delta 8). `predictVault` has no remaining reference anywhere (delta 9). `spikeBps = 0` is flat at
every `dt` (`_sellRate` returns `taxBps` whenever the decayed spike is at or below it); nothing else reads
`spikeBps`; V1 launches are unaffected (`F01` RED, six tests) (delta 10–12). The buy-back cache is written only on
success, never inside a closure, never past five days (delta 13). The merge is exactly the union of both sides
(delta 15). The hardening commit's CI fork job, rehearsal script (refuses broadcast contexts and any chain but
31337; `vm.prank`, not a signing path), `lab/fork_runner.py` (no shell, allow-listed RPC alias, bounded inputs)
and the kind-1 fork test's 0.25 USDG lot (for that fork only) hold as written (delta 16–19). The vault's
"fee-only" property: `unlockCallback` is unchanged and the new code runs after the unlock returns, moving only
stock the unlock already took; round 3's curve-invariant fuzz, vault-principal, graduation-split, delegatecall
isolation, last-seller, opening-burn, pool-depth and crossing-buyer PoCs all pass unchanged (delta 21).

**Nothing here touches V1.** `HedgeFunFactory` and the six other V1 contracts are byte-identical to `main`
(delta §4; engine 32 for the two branches). The nine live strategies are unreachable from any of this. The one
delta line that changes V1 semantics for a future V1 deployment is I4-8.

**This section will be invalidated by the next PR the same way this one invalidated its predecessors.** Every
item carries the ref it was proved at, and the † items carry the warning that the repository would not notice.

---

## Recommended floors, and who enforces them today

From the economics lane, with triage's correction of the byte cost (constructor checks are initcode). Every
row is round 3's M-4 pattern: a floor that exists, is wide enough to be no floor, and is left to the party who
does not bear the loss.

| parameter | today | enforced by | recommended | why that number |
|---|---|---|---|---|
| `deadbandBps` | ≥ 1 | constructor | **≥ 100**, and never below `maxSlippageBps + poolFeeBps` | the first crossing then needs a 4.1% move at target 50%; a single 0.5% print (the feed's own trigger) can never act alone (that needs ≥ 12); V1's own rule is "clear the friction twice over" |
| `cooldown` | ≥ 1 s | constructor | **≥ 600 s** (one TWAP window), 3,600 preferred | two actions never share one pinned 600 s mean; bounds a day at 24–144 actions without relying on `maxDaily` |
| `maxDailyTurnoverUsdg` | ≥ `maxTrade`, no ceiling | constructor | **≤ 24 × `maxTradeUsdg`**, and halve it if L4-2 stays | worst day 130 bps × 24 × chunk; with the 2,000 chunk, $624/day, $1,248 across midnight |
| `maxTradeUsdg` | ≤ `sellChunkUsdg` (2,000 / 1,000) | constructor, from the owner's per-listing chunk | **`sellChunkUsdg` ≤ 10% of the pool's USDG-per-1% depth on 0.05% listings**, re-read at listing | the sandwich breakeven (M4-1); GME needs ~1,300 on round 3's read, NVDA/GOOGL are fine at 2,000 |
| `maxTradeUsdg` (floor) | ≥ 1 | constructor | **≥ `minLotUsdg`** | L4-1: below it the treasury can never act |
| `targetBps` | 2..9998 | constructor | **2,000..9,000** | under 20% the engine is "liquidate the lot at graduation" (L4-3); over 90% the band has no room |
| `setEngineConfig` | checks the policy key only | deployer | run the constructor's word checks | `predict()` must not quote a config `launch()` refuses (M4-2) |

Cost: the constructor rows are initcode only (two of them measured at 0 runtime / +47 initcode against 21,286);
the setter row is deployer runtime (13,839 free; initcode 11,128). All of these are creator-chosen today except
the chunk. Round 3's L-3 belongs in the same table on the buy-back side: `minTaxBps ≥ 122` or
`maxBuybackImpactBps < 257` in the V2 Defaults, 0 bytes, and the rehearsal's candidate has neither.
