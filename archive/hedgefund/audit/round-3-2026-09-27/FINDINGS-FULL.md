> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Full merged findings, the rubric, the safe list and the rejected list

Part of [external audit round 3](./00-SCOPE.md). [`ISSUES.md`](./ISSUES.md) is the report; this is the
document underneath it — every one of the 35 findings written out, all 75 "checked and found safe" items with
the line that makes each one safe, the rejected list, and the binding severity rubric reproduced in full.

**Read the grades here as superseded.** This is triage's merged document exactly as written, at the moment it
merged the four lanes and the lead's notes and *before* the adversarial pass and the method review ran. Its
counts are **34 (0 Critical / 1 High / 4 Medium / 6 Low / 23 Info)**; the report's are **35 (0/0/6/6/23)**.
Three things moved afterwards, and each is argued where it happened:

| what moved | where it is argued |
|---|---|
| H-1 → Medium (**M-0**), the round's only High | [`ISSUES.md`](./ISSUES.md) M-0, [`VERIFICATION.md`](./VERIFICATION.md) part 1 |
| buyer funds stranded on an ungraduatable curve, three scattered sub-branches → its own ID **M-3** | [`ISSUES.md`](./ISSUES.md) M-3 |
| "the correct fix for `collectFees()` is 36 bytes over EIP-170, so `CurveDeployer` must be split" — **false**, the fix lands at +15 | [`VERIFICATION.md`](./VERIFICATION.md) part 1 |

Also corrected after this document was written: I-11's central sentence (`collectFees()` does **not** return
(0,0) at `lpFee = 1`), and one item of section 6's safe list (the 1.80% stop floor is pool-tier dependent —
155 bps on the 500-tier listings, 250 on MSTR). Where this document and `ISSUES.md` disagree, `ISSUES.md` is
the report.

**Names used inside the document below.** It is reproduced exactly as written, so it still refers to this
round's working papers by their internal names. This file itself is `17-triage3.md`. `BASELINE3.md` is the
pinned baseline the four lanes worked from; its scope, size table and rubric are in
[`00-SCOPE.md`](./00-SCOPE.md) and in section 1 below. `00-lead-notes3.md` is the lead's running notes, and
`13-v2-surface.md`, `14-v1-delta.md`, `15-v2-economics.md` and `16-v2-claims.md` are the four lanes' reports;
none of those is shipped — anything any of them is cited for is restated where it is used.

---

# Triage — external audit round 3 (the v2 PR), ref `03ad70e`, 2026-09-27

Five sources merged: `BASELINE3.md`, `00-lead-notes3.md` (one source of five, no special authority), and lanes
13 / 14 / 15 / 16. Every finding below was re-graded against the rubric reproduced in §1, not against the
severity the originating lane assigned. Where a grade moved, §5 says so and why.

Verification done by triage itself, in a clean copy of the PR at
`…/scratchpad/triage3-scratch/w1` (`~/.foundry/bin/forge`, `--gas-limit 9999999999`):
new evidence `test/AuditTriage3.t.sol` (3 tests) and `test/AuditTriage3b.t.sol` (2 tests), **5 passed / 0
failed**; `forge build --sizes`; and reads of every line cited in a merged finding.
**The round's only High was executed end to end here for the first time** — see H-1's Status.

---

## 1 · Severity rubric — binding, reproduced from `BASELINE3.md`

Grade the **post-deployment state of an immutable contract**. V1 is live with nine launched strategies; v2 is
not deployed, so nothing in `src/v2/` is at risk today.

- **Critical** — an unprivileged actor permanently takes or destroys treasury funds, buyer funds, curve
  reserves or locked liquidity, on the normal path, without a long-window TWAP manipulation and without the
  Safe misbehaving.
- **High** — the same needing favourable conditions, capital or a race; OR needing a ≥600 s TWAP manipulation
  (**hard cap: High, never Critical**); OR the Safe can do something the docs explicitly promise it cannot.
- **Medium** — bounded or recurring leak, a grief that degrades the product, a permanent brick of one
  non-essential path, or a disclosure that materially understates a risk.
- **Low** — small or needs an implausible precondition, but real and permanent.
- **Info** — no value impact.

Rules, in order: grade the post-deployment state, not the diff; name the loser (protocol / creator / buyer /
treasury / curve depositor / caller); split **certain** gain from **option** gain; give every finding a
condition list with today's status or UNMEASURED; date every on-chain number **including ones you argue
against**; label **EXECUTED** or **REASONED**; and **confirmation count is never evidence** — a single-source
finding with a real call path ranks equal to a five-source one.

### The frame that goes in front of the findings: the real remediation budget

The lead's R3-L6 table, **re-measured by triage in a clean build of `03ad70e`** (`forge build --sizes`,
2026-09-27). It holds exactly. Two of the six numbers are effectively zero while each contract's own size
line reads comfortable:

| a fix here | is really scored against | bytes | triage's own measurement |
|---|---|---:|---|
| `HedgeFunV2Factory` | itself | **27** | runtime 24,549 ✓ |
| `HedgeFunBondingCurve` **or** `V2LiquidityVault` | **`CurveDeployer`** | **176** | CurveDeployer 24,400; curve initcode **8,944**, vault initcode **8,233**, sum 17,177 → 7,223 of deployer logic ✓ |
| `HedgeFunV2Treasury` | itself (initcode chunked) | 2,993 | runtime 21,583, **initcode 26,197 — past EIP-170**, which is why `V2TreasuryDeployer` chunks it ✓ |
| `HedgeFunHook` (v2's new one) | itself | 5,222 | runtime 19,354 ✓ |
| `HedgeFunTreasury` (v1) | **`TreasuryDeployer`** | **1,020** | TreasuryDeployer 23,556 ✓ |
| `HedgeFunFactory` (v1) | itself | 5,647 | runtime 18,929 ✓ |

`V2TreasuryDeployer` runtime 4,773, **creation 31,928** of the 49,152 initcode limit — so a treasury-side fix
of a few hundred bytes fits three times over, and the binding number really is the treasury's own 2,993.

**27 bytes is less than one `PUSH32`.** Nothing in this report proposes adding a byte to `HedgeFunV2Factory`.

**Does this PR imply redeploying v1? No.** Settled, three independent routes: `HedgeFunFactory`'s runtime
(18,929) and creation code (22,676) are **byte-identical** at `7c3c137` and `03ad70e` and the live factory
`0x58F6…A961` verifies against both refs identically (lane 14, EXECUTED — same 44 differing runs, 607 bytes,
same offsets, all immutable placeholders); `HedgeFunV2Factory` constructs its own base with its own mined hook
(lane 15); and v2's `_openAndSeed` never calls `super`, so the inherited v1 seeding path is dead in v2 (lane
13). V2 deploys **alongside** v1 and asks nothing of it. The cost is a second hook address on Uniswap's
per-address routing allowlist and two id spaces for every front end.

---

## 2 · Counts, three ways

### (a) Everything in this PR — 34 findings

| Critical | High | Medium | Low | Info |
|---:|---:|---:|---:|---:|
| **0** | **1** | **4** | **6** | **23** |

### (b) Only what is new in `src/v2/` (locus is one of the nine new contracts) — 16 findings

| Critical | High | Medium | Low | Info |
|---:|---:|---:|---:|---:|
| **0** | **1** | **3** | **4** | **8** |

H-1 · M-1, M-2, M-3 · L-1, L-4, L-5, L-6 · I-5, I-8, I-9, I-11, I-12, I-14, I-20, I-21.
The other 18 sit on the four edited v1 files, on `docs/`, or on the test surface.

### (c) Prior-round conclusions this PR invalidates — 13, plus one watch-list that fired

**Conclusions no longer true as written (6).** These are the dangerous ones: a previous round's "checked and
found safe" is exactly what nobody re-reads.

| # | prior conclusion | what this PR does to it |
|---|---|---|
| 1 | R1: "**`lpFee` is forced to 0**, so nothing accrues to the uncollectable position" | true of `HedgeFunFactory` only (`_minLpFee()=_maxLpFee()=0` makes the new predicate exactly `lpFee == 0`, EXECUTED across 1–10, 100, 500, 3000, `0x800000`, `type(uint24).max`). **As a statement about the base it is now false**, and it is the premise H-1 lands on |
| 2 | R1: "**`lots` is never iterated on chain** — spamming lots buys an attacker nothing but their own gas" | **false in v2**: `_dueStop`, `_dueProfit`, `_coalesceLots` all iterate. `_canAddLot()`'s 128 cap re-bounds it — and the base's own default is `return true` |
| 3 | R1: "the sell spike's clock starts at **deployment**, so the opening-block sniper cannot dump" | **not true of graduated pools**: `registerGraduated*` set `lastEventAt = 0` and `_sellRate` reads that as flat |
| 4 | R1/R2 `_terms` coverage "walked field by field and found **complete**" | now **per-subclass**; `_terms` is `virtual` and `pure → view`, so `predict()` can revert instead of quoting |
| 5 | R1: "the scorecard's construction is honest and does not flatter" / "**no ratio anywhere for a donation to inflate**" | `stockEquivalentHeld()` now telescopes to the whole stock balance; a bare `transfer` moves the numerator while `totalStockReceived` stands still |
| 6 | R1/R2 measured **90.99%** cost of shoving a freshly-opened pool | **does not carry to v2**: a graduated pool opens with neither the snipe window nor the spike, so the only rate that has ever applied to a v2 manipulator is **19.485%** — a 4.7× fall |

**Proofs invalidated while the conclusion survives (6).** Re-derived, not carried.

| # | prior proof | why it no longer proves it |
|---|---|---|
| 7 | "`grep -rn modifyLiquidity src/` returns **exactly one hit**" | three hits now; the two new ones are `int256(uint256(uint128))` and a literal `0` |
| 8 | "no third party can add liquidity … **`seeder` immutable**" | `seeder` is `liquidityVaultOf[id]` — *storage*, write-once at registration |
| 9 | "**no `unlockCallback` in this repo can be invoked by a third party**" (enumerated per file) | the enumeration is outdated; `HedgeFunFactory.unlockCallback` is `virtual` and there is a new implementation the list does not name |
| 10 | "**every rule entry point is `nonReentrant`**" (five line numbers) | the guard moved to the public wrappers; `_takeProfit`/`_stopLoss`/`_buyDip` are unguarded internals |
| 11 | "**no treasury outflow exists other than the four bounties and swap settlement**" (by grep) | no longer a property of one file; must be re-run per subclass |
| 12 | R1's seed-manipulation cost arithmetic (concentrated, single-sided) | the v2 position is **full-range and two-sided**, so constant-`L` is exact and none of the concentrated reasoning transfers |

**And round 1's F-40 watch-list fired on both of its named triggers.** F-40 said: *"any future change that
mints a strategy token, **adds a second liquidity path**, or **seeds the anchor at `wire()`** re-opens it."*
This PR does both. It does **not** re-open the brick (I-4 has the reason), but the three places that record
the invariant — `HedgeFunTreasuryBase.sol:431-433`, `:537-541` and `docs/SECURITY.md:130` — were not updated
and are now false. That is I-4, and it is the highest-urgency item in the report at the lowest severity.

---

## 3 · Merged findings, most severe first

---

### H-1 · High · The LP fee turns the 90% sell spike from a profit-gated event into a volume-gated one that any caller re-arms every 240 s — and the arming buyback burns nothing

**Location** `src/v2/V2LiquidityVault.sol:91` (`collectFees()`, no access control) →
`src/v2/HedgeFunV2Treasury.sol:168-172` (`creditLiquidityFee` → `buybackStock += amount`) →
`src/HedgeFunTreasuryBase.sol:452` (`buyback()`, `external`, **not `virtual`**, permissionless), `:464`
(`amountIn = min(buybackStock, chunk)`), **`:474`** (the dust floor is `Math.min(amountIn, …)`), `:484`
(`noteEvent()`). Spike shape: `src/hooks/HedgeFunHook.sol:289-293`, `:320-327`.

**Lanes that reached it, and how** — lane 15 (E-1, economics; the only lane to file it, REASONED off the
author's own fork assertions at `test/V2LiveVenueFork.t.sol:266-276`); the **lead** walked every link by
reading (R3-L8) and identified the `Math.min` carve-out at `:474` as the break. Lanes 13, 14 and 16 did not
reach it — **a single-source finding with a real call path, which the rubric ranks equal to a five-source
one.** Lane 13 independently measured the enabling condition (`lastEventAt = 0` at graduation) and filed it
safe; lane 15 independently measured the same and filed it as exposure. That convergence says the surface is
easy to see, not that either reading is right.

**Status** **EXECUTED by triage, end to end, for the first time in this round.**
`test/AuditTriage3.t.sol` + `test/AuditTriage3b.t.sol`, real `PoolManager`, production hook / factory /
`CurveDeployer` / `V2LiquidityVault` / `HedgeFunV2Treasury` via `test/utils/V2FactoryFixture.sol`; only the
external stock/USDG venue and the price feeds are mocked. **What was actually run:**

1. **The lead's open question — the one-wei floor — is settled, and the answer is worse than interpolated.**
   With `buybackStock` driven to exactly **1 wei** through the real inlet (pranked as the registered vault,
   with the real `msg.sender == liquidityVault` check satisfied), an unprivileged caller's `buyback()`
   returns **`spent = 1`, `burned = 0`** and `hook.sellRateBps(id)` goes **1000 → 9000**. The V4 exact-input
   swap of one wei is entirely consumed as LP fee, so the "buy-back" buys nothing and burns nothing — and
   still arms the 90% sell tax. `:474`'s carve-out (`min(amountIn, minLot)`) degenerates to `min(1, …) = 1`
   and a full 1-wei fill passes. *(`test_T3_oneWeiPotArmsTheNinetyPercentSpike`)*
2. **The whole chain, with no privileged party anywhere.** A stranger buys 1 stock of FUN on V4 → LP fee
   **0.003 stock** (0.30% exactly) → the same stranger calls `vault.collectFees()` → `buybackStock` rises by
   exactly the fee → the same stranger calls `treasury.buyback()` → `sellRateBps == 9000`.
   *(`test_T3_e1EndToEndByAnUnprivilegedCaller`)*
3. **Priced, on the fixture.** A holder of 10% of the float selling into the spike receives
   **0.1007 stock**; the identical sell after the spike decays receives **0.9062 stock** — the seller keeps
   **1/9.0 of their proceeds**, and the difference goes to the hook's protocol / creator / treasury split.
4. **The re-arm cadence.** `noteEvent()` is a no-op inside `2 × spikeSeconds` and re-arms at **+240 s**, for
   one wei again. *(`test_T3_oneWeiSpikeIsReArmableEvery240s`)*
5. **The fuel is free.** Binary search over buy size: the smallest buy producing a collectable stock fee is
   **334 wei of stock** (3.34e-16 stock), yielding a 1-wei fee. *(`test_T3_smallestBuyThatRefillsThePot`)*
   So the marginal cost of a re-arm is gas, and the caller is paid `bountyBps` for it.

**What is still REASONED, stated plainly.**
- **`spikeBps` and `spikeSeconds` for the v2 factory do not exist on chain.** No v2 Defaults are deployed.
  My execution used the repository's own fixture values, 9000 / 120, which equal the **live v1** Defaults read
  2026-09-27 (block 73,765,417) and the candidates in `script/RehearseV2Launchpad.s.sol`. **The finding
  evaporates entirely at `spikeBps = 0`.** This is the single condition that decides it.
- The dollar pricing — creator's take 534 → **1,485 USDG (2.8×)** on a full NVDA cascade, protocol 356 → 990 —
  is lane 15's integer model (`curve2.py`) at the live NVDA listing, not an executed measurement.
- The **27.8% time-average** sell tax is rounds 1–2's V1 figure (AUDIT.md:461) carried forward; the duty cycle
  it rests on (`spikeSeconds / 2·spikeSeconds`) is executed above, the average is not.

**Conditions**
1. A nonzero static V4 LP fee. — **Structural, always true.** `_minLpFee()` returns 1
   (`src/v2/HedgeFunV2Factory.sol:54`), so a v2 factory **cannot** set it to zero. Verified by reading; v1's
   virtuals both return 0 (`src/HedgeFunFactory.sol:205-206`).
2. Any buy flow on a graduated pool. — **True by construction after the first buy**; threshold measured at
   **334 wei of stock**.
3. `spikeBps`/`spikeSeconds` nonzero in the v2 Defaults. — **UNMEASURED** (no v2 deployment). Live v1 is
   9000/120, read 2026-09-27.
4. `collectFees()` and `buyback()` permissionless. — **True at `03ad70e`**, both read and executed.
5. `creatorBps > 0`. — Creator's choice, ≤ 3000. Live v1 pools run 500–2000, read 2026-09-27.
6. `buybackStock` has no other unmetered inlet in v1. — **True**: all nine live v1 treasuries read
   `buybackStock = 0` on 2026-09-27, because `_takeProfit` (`src/HedgeFunTreasuryBase.sol:370`) is its only
   filler there.

**Mechanism** `noteEvent()`'s comment (`src/hooks/HedgeFunHook.sol:283-287`) states the design premise in so
many words: *"`buyback()` is permissionless and its cooldown is shorter than the spike is long, so anyone
willing to spend **the treasury's own realised profit** could re-arm a 90% sell tax forever."* The
`2 × spikeSeconds` bound does not stop that; it caps it at a 50% duty cycle. What made it tolerable in v1 was
the **budget** — realised, oracle-gated, rare profit. V2 adds a second, unmetered inlet fed by other people's
buy volume at 0.30% of notional, forever, and `:474`'s carve-out means **any nonzero pot arms the spike**.
V2 does not remove the spike; it changes who decides when it fires, from *"whoever realised a profit"* to
*"whoever calls first"*.

**Impact** Loser: **every FUN holder who sells**, permanently and recurrently — measured at 1/9.0 of their
proceeds inside the window, which is half of all wall-clock time at the attacker's choosing.
- **creator — certain gain** (30% of a take that goes from 3% to ~27% of gross).
- **protocol — certain gain**, and it need not act.
- **caller — certain gain** of `bountyBps` (0.5% of the burn; **zero at the one-wei floor, because nothing is
  burned**) plus an **option gain** that is worth more: the spike is symmetric *unless you sell first*.
  `sell at the flat rate` → `collectFees()` → `buyback()` in one block leaves the attacker out at 10% with a
  90% door shut behind them for 120 s. That is an exit-ordering privilege available to anyone, for gas.
- A 120-second **soft trading halt**: a router sell with a sane `minFinalOut` reverts rather than filling.

**Not Critical: the taker is not the caller.** The value lands on the protocol's own designed recipients and
the caller collects a bounty. Nothing takes principal, curve reserves or locked liquidity. **High** because it
is a recurring, unprivileged, permanent transfer that needs only timing — the rubric's "needing favourable
conditions … or a race".

**Fix, against the correct budget**
- *Preferred.* Give `HedgeFunV2Treasury` its own `lpFeeStock` accumulator and a v2-only `burnLpFees()` that
  swaps and burns **without** `noteEvent()`. `buyback()` is `external` and **not `virtual`**
  (`src/HedgeFunTreasuryBase.sol:451`, verified by reading), so v2 cannot override it — the fee stream has to
  be kept out of `buybackStock` rather than changing `buyback`. **+450–700 bytes on `HedgeFunV2Treasury`,
  whose own margin is 2,993 — it fits.** Knock-on: +700 runtime → +~700 in `V2TreasuryDeployer`'s initcode,
  31,928 → 32,628 against 49,152, and ~+350 per chunk against 24,576. Both fit wide. **0 bytes on
  `HedgeFunV2Factory` (27) and 0 on `CurveDeployer` (176).** `TreasuryDeployer`'s 1,020 does **not** bind —
  that is the v1 deployer.
- *Cheapest, but a real trade.* Delete `creditLiquidityFee` and have the vault `safeTransfer` the stock fee to
  the treasury, where it becomes `unbookedStock()` and books as ordinary principal. **Net −300 bytes.**
  `docs/V2_DUAL_ENGINE_REVIEW.md` row 2 deliberately rejected this, so it is a decision, not a free win.
- *Zero-byte stopgap.* Ship the v2 Defaults with `spikeBps = 0`. Removes the finding entirely and should be
  the default posture until one of the above lands.
- *Do not* attempt a `noteEvent(minimumNotional)` variant: the deployed v1 `HedgeFunTreasuryBase` calls the
  zero-argument selector at `:484` and the v2 treasury inherits that call site.

**PoC** `cd …/scratchpad/triage3-scratch/w1 && ~/.foundry/bin/forge test --mc AuditTriage3 --gas-limit
9999999999 -vv` and `--mc AuditTriage3b`. 5 passed. The author's own
`test/V2LiveVenueFork.t.sol:266-276, :333-335` asserts the same chain on a live-venue fork.

**Re-grade trigger** Registering strategy kind 1 (`HedgeFunV2BuybackTreasury`) books the treasury's *entire*
graduation share as `buybackStock` — ~$19,886 at the live NVDA listing — from block one. Kind 1 is marked
DRAFT and registered by nobody today (`V2TreasuryDeployer`'s constructor registers only kind 0). **If it is
ever registered, re-grade this finding.**

---

### M-1 · Medium · `V2LiquidityVault.collectFees()` couples its two legs, so a stock leg the issuer refuses also strands the token-side burn — and the correct fix is 36 bytes over EIP-170

**Location** `src/v2/V2LiquidityVault.sol:91-114` (the whole function). Contrast
`src/hooks/HedgeFunHook.sol:460-469` and its comment at `:463-465`.

**Lanes** Lane 13 (V2-01), sole source, EXECUTED with two purpose-built PoCs. Triage re-read the function and
confirms the coupling at the line: `creditLiquidityFee` at `:106` runs **before** the unconditional
`HedgeFunToken(token).burn(tokenBurned)` at `:111`, inside one function with no `try`.

**Status** EXECUTED (lane 13: `test_L13_blockedStockLegAlsoStrandsTheTokenBurn`,
`test_L13_blockedVaultAlsoStopsTheTokenBurn`); the code reading re-verified by triage.

**Conditions**
1. A graduated v2 pool has accrued fees on both currencies. — **Normal.** `_minLpFee() = 1` means a v2 pool
   *cannot* run a zero fee, so both sides always accrue.
2. The stock's registry blocklists the vault or the treasury, or the stock/registry is paused. — **Capability
   VERIFIED, use against a contract unprecedented.** `docs/STOCK_TOKEN_ASSESSMENT.md` (chain reads
   2026-09-20, block ≈68.28M): `BLOCKER_ROLE` on an EOA, 246 `Blocked` events over 177 addresses, **none with
   code**, all between blocks 43,543 and 495,841, nothing since; two pause switches, the global one used once
   for 142 blocks. `transferFrom` checks `from`, `to` **and the operator**.
3. For the loss to be permanent the block must be permanent. — **UNMEASURED.** The issuer publishes no policy.

**Mechanism** One `poolManager.unlock` takes **both** fee currencies into the vault (`_take` at `:142-143`),
then delivers them in one straight line. Any revert in the stock leg reverts the function, the `unlock`, and
therefore *both* fee balances back into the pool — including the token side, which has no dependence on the
stock issuer at all. There is no `collectTokenFeesOnly()`, no per-leg `try`. The hook, in the same
repository, does the opposite and says why: *"Every leg is independent… that must not strand the TOKEN side,
which had nothing to do with it."* (`src/hooks/HedgeFunHook.sol:463-465`), then runs
`try this.settleToken(…) {} catch {}` and carries a whole `parked`/`index`/`epoch` machine. The vault inherits
none of that discipline, and is the only one of v2's five custody points whose two currencies are coupled.

**Impact** Loser: every FUN holder (the token-side burn is their share of the 0.30% fee) and the treasury (the
stock side is its buyback budget). **Certain gain 0 to any actor; option gain 0** — nobody can take value
*through* this. A **temporary** block is a recoverable freeze (V4 fee growth is cumulative). A **permanent**
block permanently bricks a path that has nothing to do with the stock.

**Why Medium and not Low, stated openly.** On preconditions alone, Low is defensible: an issuer has never
blocked a contract, and permanence is unmeasured. Medium because the rubric's "permanent brick of one
non-essential path" is exactly the bitten state, and because **the repository's own threat model treats this
precondition as in scope** — the hook's `try/catch` machinery and round 2's L12-2 exist for it. Grading it
below the protocol's own assessment of the same risk would be inconsistent.

**Fix — and this is the report's single most actionable structural result: the correct fix does not fit.**
The vault's own 17,464 bytes are not the budget; `CurveDeployer` embeds `type(V2LiquidityVault).creationCode`
(`:118,123`) alongside the curve's (`:109,114`), so **every byte added to the vault or the curve is a byte on
`CurveDeployer`, which has 176**. Lane 13 built and measured three variants:

| variant | vault runtime | `CurveDeployer` | margin | correct? |
|---|---:|---:|---:|---|
| as shipped | 7,112 | 24,400 | **176** | — |
| inline `try … catch { stockFee = 0; }` | 7,118 | 24,406 | 170 | **no** |
| `try this.deliverStockFee(…)`, no retry | 7,274 | 24,562 | 14 | **no** |
| self-call **+ `pendingStockFee` retry** | 7,324 | 24,612 | **−36 · over EIP-170** | **yes** |

Both cheap variants are **strictly worse than shipping as-is**: `_take` has already pulled the stock into the
vault, and the vault has **no function that can move a pre-existing balance** (L-5), so catching and
abandoning converts a recoverable freeze into a permanent loss. The self-call (not an inline `try`) is
required because a stock *pause* stops `approve` as well as `transfer`, so the `forceApprove` must be inside
the frame that rolls back. **The only correct shape is 36 bytes over the limit.**
**Therefore: split `CurveDeployer` into a curve module and a vault module** (~8 kB each). They are used at
different moments and `executeGraduation` already reaches the deployer through `CurveDeployer(SELF)`; the
second module's address must be read from the first, because the factory has **27** bytes. That is a
structural change to the graduation path and must be reviewed as one — and see I-14: it is also the change
that would make an untested access control load-bearing.

---

### M-2 · Medium · A full v2 raise is a ~$40k one-directional buy through the stock's only V3 pool; on ten of eighteen listings it blows past the gate that halts the live v1 strategies on that stock, and on one the pool cannot supply the raise at all

**Location** `src/v2/HedgeFunBondingCurve.sol:12` (the curve is stock-denominated),
`docs/V2_BONDING_CURVE.md:159-177` (buy routing is `payment → ≤3 V3 hops → stock → curve`),
`src/HedgeFunTreasury.sol:94-108` (`health()` requires spot and the 600 s mean within `maxDeviationBps`),
`src/v2/HedgeFunV2Factory.sol:111-124` (`_preflight` validates the V4 seed and nothing about where the stock
comes from).

**Lanes** Lane 15 (E-2), sole source. Lane 13 independently established the closed-form raise
(`Rg = 4V`, the `(1/(1−sale))²` multiple) without drawing the venue consequence.

**Status** **EXECUTED for the depth** — 18 real pool `swap()` calls on a fork of Robinhood Chain at block
**73,785,844, 2026-09-27**, exact-output for `Rg` plus a 16-step binary search for the 50 bps threshold.
**REASONED for the coupling** (v2 is not deployed, so no v1 halt has occurred).

**Which parameters are not on chain.** `supply = 1e27`, `openPriceE18` per listing, `maxDeviationBps = 50`
(125 on KURA-MSTR) and the nine strategies' `params()` are **live v1 chain reads, 2026-09-27**.
`DEFAULT_SALE_BPS = 8000` is a **v2 source constant** at `03ad70e`, not a deployed value — the raise size
moves with it (`Rg = 4V` at 8000, `2.33V` at 7000).

**Conditions**
1. A v2 launch on a stock that already carries a live v1 strategy. — Nothing prevents it. **Eight of eighteen
   listings already carry one; four of those eight are in the thin set** (GME, META, MSTR, AMD). UNMEASURED
   whether the owner intends the overlap.
2. Buyers pay in USDG rather than sourcing stock elsewhere. — The router's whole purpose; the natural path.
3. The v1 treasury on that stock holds stock worth losing. — **Measured 2026-09-27 at same-block pool prices:
   total v1 stock exposure across all nine ≈ $10,224** (CRCLGRID $6,801, LOVEELON $2,761, SWING $370, GMEME
   $184, SI-NVDA $108; four hold zero). **The coupling and the exposure are anti-correlated** — the two
   largest holders sit on comfortable pools (CRCL +38 bps, SPCX +7 bps) while the thinnest pools (AMD, USAR,
   INTC) carry $0 of v1 stock between them. **This is what keeps it Medium rather than High.**
4. A v1 strategy with `stopBps != 0`, so a halt blocks a loss-cut. — **Three of nine**: SI-NVDA and
   SPACE-NVDA (2000) on the one pool a full raise moves only **+4 bps**, and **KURA-MSTR (1200)**, whose
   wider 125 bps gate a full raise still breaches at **+162 bps**. KURA holds 0 stock today.

**Mechanism** V2's quote asset is the listed stock token. Every USDG buyer's payment passes through the *same*
`<stock>/USDG` V3 pool the v1 treasuries use for execution **and** for their health gate. `Rg` is fixed and
the curve has **no pacing** — one buyer can fill it in one transaction. Ten of eighteen listings are thin:
AAPL +72 bps, TSLA +97, MSFT +105, MU +142, META +151, MSTR +162 (gate 125), **GME +295 (5.9× the gate),
USAR +1,060 (21×), AMD +1,200 (24×)**, plus **INTC, where `Rg = 330.80 INTC` against a pool holding 317.71 —
104% of the entire inventory, so the exact-output swap reverts and an INTC curve can never graduate.** One GME
graduation is 45% of that whole pool; one AMD graduation is 77%.

**Impact** Loser: the **v1 treasury** on the same stock (a halt during which a due stop cannot fire) and its
holders; and on INTC, every buyer of a curve that can never complete. **Certain gain: none** — this is a
negative externality of the normal path, not an extraction. **Option gain**: an attacker who wants a v1
strategy halted can already buy the pool directly for $3,350 (AMD) or $1,107 (USAR) *without* v2; v2 does not
make it cheaper, it makes it **routine and pays for it with other people's money**.

**Two warnings that travel with these numbers.** (a) An analytic constant-liquidity depth estimate was
**2.8× wrong** against the executed swap on NVDA, so only executed numbers are used. (b) **Depth moved inside
the session**: AMD's 50 bps budget fell **36.7% in ~30 minutes** on 2026-09-27. The *levels* are a same-day
snapshot; only the *ordering* is durable, and even that should be re-run before a listing decision. The one
structural claim independent of the level is INTC's.

**Fix** A listing rule, **0 bytes against the factory's 27**: require
`4 · openPriceE18 · supply / 1e18 ≤` the measured USDG that moves that stock's V3 pool by `maxDeviationBps`.
At the shipped "$10k opening FDV" convention (`docs/ADDRESSES.md:44-45`) that is violated on seven of eighteen
listings today; on AMD it means dividing the listed open price by ≈13, on USAR by ≈34, and on INTC no launch
is supportable at current depth. `saleBps` is the other lever and cuts the same way (M-3).
Also: `docs/ADDRESSES.md` is stale by six listings — 18 `Listed` events, 18 distinct stocks, EXECUTED
2026-09-27, not the twelve it records.

**Disclosure limb** The document titled `docs/V2_DUAL_ENGINE_REVIEW.md` reviews the *LP-versus-treasury*
capital split and says nothing about the two engines competing for the same stock's only venue. A reader who
goes there for the question the title promises does not find it answered.

---

### M-3 · Medium · The parameter floors the code enforces are 6× and 11× wider than the author's own conclusion, and a shipped document still describes the split as a constant

**Location** `src/v2/HedgeFunV2Factory.sol:22-24` (`DEFAULT_SALE_BPS = 8000`, `MIN_SALE_BPS = 1000`,
`MAX_SALE_BPS = 9000`); `src/v2/V2TreasuryDeployer.sol:48-49,61` (`DEFAULT_LP_BPS = 5000`,
`MIN_LP_BPS = 1000`, ceiling 10000), frozen at `:147`, consumed at `src/v2/CurveDeployer.sol:79`.
Author's own conclusion: `docs/V2_LP_DEPTH_EXPERIMENT.md:65-68`. Stale prose:
`docs/V2_DUAL_ENGINE_REVIEW.md:11` and `:17`.

**Lanes** Two routes to one fact. Lane 15 (E-3) priced the parameter range with an independent integer model;
lane 16 (F-02 / C16) caught that `docs/V2_DUAL_ENGINE_REVIEW.md` still states the split as `floor(reserve/2)`
and "a fixed test baseline", when `5df2942` made it an owner dial. **Merged: same mechanism, two faces.**

**Status** EXECUTED (lane 15's `curve2.py` independently reproduces the author's 13.4× at 13.38×; lane 16 read
the code and confirmed with `git log -S`). Triage verified `CurveDeployer.sol:79` reads
`lpBpsOfTreasury(g.treasury)` by reading the line.

**Not on chain.** No v2 Defaults exist. `MIN_LP_BPS` / `MAX_SALE_BPS` are source constants that *will* be in
the deployed bytecode; the per-stock `lpBps` / `saleBps` values are owner calls that have not happened.

**Conditions**
1. A launch at the shipped defaults (80 / 50) — the default path.
2. The owner sets a value near a floor — permitted today, **no timelock**; `setLpBps` accepts 1000.
3. V2 deployed — not today.

**Mechanism and price** (lane 15's model, live NVDA listing, everyone dumping in the order they bought):

| config | open→terminal | first-5%-of-sale buyer | cascade returns | price after the first seller |
|---|---:|---:|---:|---:|
| sale 80 / LP 100 | 25× | 15.83× | 73.6% | 66.7% |
| sale 80 / LP 50 (**shipped**) | 25× | 13.38× | **40.5%** | 47.7% |
| sale 80 / **LP 10** (`MIN_LP_BPS`) | 25× | 5.98× | **8.8%** | **9.5%** |
| **sale 90** (`MAX_SALE_BPS`) / LP 50 | **100×** | **40.65×** | 42.6% | 27.8% |
| **sale 10** (`MIN_SALE_BPS`) / LP 50 | 1.23× | **0.90×** | — | 82.7% |

| parameter | safe bound implied | code enforces | gap |
|---|---|---|---|
| `lpBps` | ≥ 6000 (author's own `:67`) | ≥ **1000** | **6× too loose** |
| `saleBps` | ≤ 7000 (same line) | ≤ **9000** | 11× vs 100× multiple |
| `saleBps` | ≥ ~5000, below which no buyer clears the round trip | ≥ **1000** | admits a dead curve |

`MIN_SALE_BPS = 1000` produces a curve where **nobody** profits and 85.5% of supply is burned at graduation;
`_preflight` passes it, because it only checks `amount ≥ 2` and `liquidity != 0`.

**Impact** Loser: **curve buyers**, in proportion to how late they bought — at `MIN_LP_BPS`, 91.2% of
aggregate buyer capital. **Certain gain: none to any actor** — the capital is not taken, it is *stranded*
(locked LP that nobody owns, plus treasury principal with **no redemption claim**,
`docs/V2_BONDING_CURVE.md:147`). **Option gain: none.** Medium as a bounded, per-launch, parameter-driven
leak. **Not High**: the value is frozen at launch, bound into the `terms` hash, and readable before a buy, so
the Safe cannot retroactively thin a launched pool and the "docs promise something the Safe cannot do" limb
does not apply — `V2_BONDING_CURVE.md:63-66` describes `lpBps` correctly; it is `V2_DUAL_ENGINE_REVIEW.md`
that is stale, and the two shipped documents disagree with each other.

**Fix** Two constant edits: `MIN_LP_BPS → 5000`, `MAX_SALE_BPS → 7000`. **0 bytes net** on
`V2TreasuryDeployer` (19,803) and on `HedgeFunV2Factory` — but note the factory cannot absorb any *added*
check at 27 bytes, so the `saleBps` bound must stay a constant compare. Plus a doc fix: restate
`V2_DUAL_ENGINE_REVIEW.md:11,:17` in terms of `lpBps`, its 10–100% range and its owner. **0 bytes.**

**What would overturn it** A real post-graduation sell curve showing only a fraction of the float ever sells;
the cascade assumes 100%, which is the worst case and is labelled as such. Nobody has that measurement, and
`V2_LP_DEPTH_EXPERIMENT.md:60-63` says so.

---

### M-4 · Medium · The v2 documents' quantitative evidence is graduation-conditional and model-versus-model, and their one adversarial evidence table is 31% wrong at the audited ref

**Location** `docs/V2_LP_DEPTH_EXPERIMENT.md` (whole file; `:30`, `:65-68`, `:81`), `lab/model.py:1-8,44-52`,
`test/V2LpDepthExperiment.t.sol`; and `docs/V2_ADVERSARIAL_REVIEW.md:50-81` (the table at `:55-64`) against
`test/V2AdversarialAccounting.t.sol:248-347`.

**Lanes** Two independent routes to one disclosure defect. Lane 15 (E-4) attacked the *method*; lane 16
(F-01 / C9) attacked the *numbers* by re-running the named test at two refs. **Merged.**

**Status** EXECUTED at both refs by lane 16; EXECUTED by lane 15 for the model re-derivation.

| measurement | doc says | `01e515a` | `03ad70e` | drift |
|---|---:|---:|---:|---:|
| tokens burned, no preceding market buy | 792.0398009950 | 792.039800995 ✓ | **785.777795380** | −0.8% |
| tokens burned after the sustained price change | 507.4103585657 | 507.410358566 ✓ | **351.087042459** | **−30.8%** |
| keeper token bounty | 2.5498007968 | 2.549800797 ✓ | **1.764256495** | **−30.8%** |
| participant's stock after waiting and exiting | 91.6272208174 | 91.627220817 ✓ | **92.151211117** | loss 8.373 → 7.849 |

The suite stayed green through a 31% move because the only assertions on those quantities are an inequality
and a floor (`assertLt(burned, controlBurned)` at `:336`, `assertGe(burned + bounty, minimumGross)` at `:326`)
— the rows are `emit log_named_decimal_uint`, not assertions. The cause is this PR's own graduation capital
split halving the depth the test graduates into.

**The method defects, each checked**
1. *"The contract run reproduces the model to the percent"* (`:30`) is **not corroboration**: `lab/model.py`
   is deterministic `x·y=k` with no market (its own docstring says so) and the fixture is the production
   contracts implementing the same closed form. Agreement is a unit-consistency check. Lane 15's *third*
   implementation also agrees (13.38× vs 13.4×), which proves the same nothing.
2. **No price path, exogenous seller who always dumps 100%** — admitted at `:60`, but a behavioural
   conclusion is then drawn from a model with no behaviour in it.
3. **In-sample parameter choice** — "Sale 70%, LP 60%" (`:65-68`) is read straight off the sweep that produced
   the table, with no holdout, **and it did not reach the code** (shipped 80/50 — M-3).
4. **Control is a deterministic negation of the one sample** (the "no bot" column is the same call sequence
   with two calls deleted).
5. **Survivorship, the one that matters.** Every number conditions on the curve reaching `Tmin`. The
   pump.fun-class public graduation rate is low single digits, and **here the non-graduating state is
   permanent**: no expiry, no refund, no owner cancellation (`docs/V2_BONDING_CURVE.md:20-21`), `status` stays
   `Active` forever, `health()` returns `(false, 0)` forever, and the only exit is a ~19.5% taxed round trip
   back into the curve **while the creator keeps collecting `creatorBps` of every one of those sells**.
   M-2 supplies a case where the stall is not sentiment at all: an **INTC curve cannot be completed**.
6. **The one measured input nobody took** — no v2 document measures the V3 pool the raise comes out of. That
   is a chain read of 18 addresses and it changes the answer (M-2).

**Impact** Loser: whoever sets `lpBps`/`saleBps` believing the sweep is empirical, and every buyer of the
resulting launch. `docs/V2_LP_DEPTH_EXPERIMENT.md:81` instructs that *"a launch UI must show these numbers"* —
graduation-conditional numbers, on a launch page, with no unconditional counterpart. **Medium under "a
disclosure that materially understates a risk."** Nobody loses funds to the document itself.

**Fix** **0 bytes.** (a) An explicit "conditional on graduation" banner; (b) a section on the non-graduating
state and its permanence; (c) delete or requalify the "reproduces the model to the percent" sentence;
(d) reconcile `:67` with the shipped defaults; (e) re-run and restate the adversarial table, pinned to the ref
it was measured at, and pin `burned` and `bounty` with `assertEq` so the next capital-split change fails
loudly. Note `:67-68`'s claim that the test checks "**exact** treasury spend, bounty, burn" is true only as
internal consistency: `:308` asserts `assertLe(spent, 1 ether)`, a bound.

---

### L-1 · Low · The documented permissionless `graduate(id)` fallback can never fire, and a graduation that reverts caps the curve for good with no retry

**Location** `src/v2/HedgeFunV2Factory.sol:133-134` and `:136-139`, against
`src/v2/HedgeFunBondingCurve.sol:106-116` and `:128` (the only write of `Status.Ready`).
Docs: `docs/V2_BONDING_CURVE.md:28`, and the source comment *"Permissionless fallback; successful final buys
graduate atomically through graduateCurve."*

**Lanes** Lane 13 (V2-02, EXECUTED: `test_L13_graduateFallbackIsUnreachable`); lane 15 reached the same
unreachability independently inside E-9. Triage re-read `_graduate:139` (`status != Ready → NotReady`) and
`buy():112-115` and confirms `Ready` cannot survive a transaction.

**Status** EXECUTED.

**Conditions** 1. `Ready` is written in exactly one place, in a `private` function with one caller that
graduates or reverts before returning — **true at this ref**. 2. Graduation must be able to fail for a
non-transient reason — the seed arithmetic cannot fail (`_preflight` runs the *identical* `sqrtPrice` /
`liquidity` calls at launch on identical inputs), so the realistic causes are all the issuer's
blocklist/pause on one of three external stock transfers — **same status as M-1's condition 2**.

**Mechanism** If `graduateCurve()` reverts, the revert bubbles through `buy()` and `Ready` rolls back. So
`graduate(id)` observes `Active` forever and reverts `NotReady`. It is dead code on the one contract with
**27 bytes** of margin. The consequence: a blocked curve is **capped one wei short of the cap** — buys below
`capCost` still work, sells still work, but the reserve can never be released, the pool is never created and
the treasury is never funded, with no operator and no permissionless action that completes it later. That last
part is defensible; what is wrong is that the docs and the function *name* present a retry that does not
exist, and a reader asking "can a stuck curve be finished?" finds `graduate(id)` and concludes yes.

**Impact** Loser: curve buyers and the creator. Their only exit is a taxed sell back into the curve; the 50%
of the raise earmarked for the treasury never arrives. **Option** loss, not certain. **Zero value extractable
by anyone.**

**Fix** (a) **Delete `graduate(uint256)`** — the rare fix that *adds* margin to the 27-byte factory (an
`external nonReentrant` wrapper plus its dispatch entry is on the order of 100+ bytes); (b) correct
`docs/V2_BONDING_CURVE.md` to say `Ready` is unobservable across transactions and a blocked graduation is a
permanent cap, which `test_RevertGraduationRollsBackFinalBuyAndKeepsSellsOpen` already proves and the prose
does not say. A real retry is a design change (persisting `Ready`, with its own reentrancy and ordering
surface) and does not fit in 27 bytes.

---

### L-2 · Low · The published scorecard's numerator now moves on a bare `transfer` while its denominator does not, and a sub-lot donation moves it permanently

**Location** `src/HedgeFunTreasuryBase.sol:235-241` (`stockEquivalentHeld`), against `:157` and `:300`
(`totalStockReceived`, written in exactly one place, inside `_book`) and the formula the same file publishes
at `:152`.

**Lanes** Lane 14 (V1D-03), sole source, EXECUTED to the wei.

**Status** EXECUTED.

**Conditions** 1. A front end computes the score as the comment says — **true**: `README.md:384`,
`docs/REFERENCE.md:1061`, `docs/ROADMAP.md:81`, `docs/LAUNCH_KIT.md:102` all name it. 2. Anyone can send stock
to a treasury — **true, unconditionally**. 3. The donation cannot be booked away — **true for any donation
whose oracle value is below `minLotUsdg`**. 4. It reaches a live treasury — **false**: the nine deployed
treasuries carry pre-PR code, and `HedgeFunTreasury` 18,289 → 18,344 moves `TreasuryDeployer` to a new
address, so future launches from `0x58F6…A961` keep the old code. The live treasury `0xc218…4fe0` is 18,289
bytes and matches the `main` build exactly; it does not match `03ad70e`.

**Mechanism** `bookedStock + buybackStock + unbookedStock() + _ruleStockFor(reserveUsdg(), p)` telescopes to
**exactly the whole stock balance plus USDG at the oracle**. In the normal case that is *more* honest. The new
exposure is the other way: before, the only way to move the numerator with stock was `book()`, which moves
`totalStockReceived` equally and so pulls a score above 1.0 *down*. Now a bare `transfer` moves the numerator
alone — one wei suffices, `book()` returns `false`, and `totalStockReceived` does not move.

**Untested in v1, and that is the sharp part.** The PR's `test/` diff is **+5,889 / −0**. All four pre-existing
call sites happen to have `unbookedStock() == 0`, so the whole 559-test v1 set is green at both refs with the
term added and no assertion changed. The only test that exercises it is on a **v2** treasury.

**Impact** Loser: a reader of the token page. **Certain gain to any actor: 0** — the donor is out the stock
permanently (round 1's outflow enumeration re-verified). **Option gain**: a creator or the protocol can make
their own strategy read better than it performed, for the price of the donation, permanently if they keep it
under `minLotUsdg`.

**Fix** None in the contract — the change is a net improvement. **0 bytes.** Two sentences in
`docs/SECURITY.md`'s "the on-chain score can be bought" paragraph (`:710-717`) saying the stock leg now
behaves the same way and needs no `book()` and no minimum, plus one v1 test with `unbookedStock() > 0`.
Separately: **round 1's F-40 fix must be re-costed against `TreasuryDeployer`'s 1,020 bytes, not the 2,158
round 1 quoted.**

---

### L-3 · Low · `maxBuybackImpactBps` is never checked against the pool's own round-trip friction, and at `minTaxBps = 100` the live cap of 300 is on the wrong side of the invariant

**Location** `src/libraries/HedgeFunLimits.sol:13` (`MAX_BUYBACK_IMPACT_BPS = 1000`),
`src/HedgeFunTreasuryBase.sol:545-572` (`_buybackLimitSqrtP`), `src/v2/HedgeFunV2Factory.sol:54-55`.

**Lanes** Lane 15 (E-5), sole source, EXECUTED by simulation (`push.py`).

**Not on chain.** `minTaxBps = 100` and `maxBuybackImpactBps = 300` are the **live v1** Defaults read
2026-09-27; the v2 Defaults do not exist. The invariant itself is parameter-free.

**The invariant** The pre-push-then-buyback attack is not depth-limited; depth, chunk size and the push all
cancel. It is profitable iff
**`maxBuybackImpactBps ≥ 10000 · (1 − (1 − taxBps/1e4)² · (1 − lpFee/1e6)²)`**.
At `taxBps = 100`: 199.0 bps at lpFee 0, **257.7 bps** at lpFee 3000. Simulated attacker net per cycle: +0.02
USDG at the live 300 cap and 100 bps tax; −0.01 at 122 bps; **+4.58 USDG** if the cap is ever raised to the
enforced ceiling of 1000 (≈$275/hour).

**Safe vs enforced** Safe: `maxBuybackImpactBps < 258` at the live minimum tax, equivalently `taxBps ≥ 122` at
the live cap. Enforced: a flat global 1000, with the cap set by the **owner** and the tax chosen by the
**creator** — two different parties whose product is never checked anywhere.

**Impact** Loser: the treasury's `buybackStock`. **Option gain** to the attacker, +0.02 USDG per 60 s cooldown
at live settings. Low today; Medium if the cap is raised or a launch ships `taxBps < 122`.

**The one place the LP fee helps.** A 0.30% V4 fee raises the friction floor from 199 to 258 bps and shrinks
the unsafe tax window from `[100,150]` to `[100,121]`. **The same LP fee widens the budget the attack drains
(H-1). Both directions, one parameter — and the second effect is worth vastly more.**

**Fix** The structural version adds `if (p.maxBuybackImpactBps >= frictionBps(taxBps, lpFee)) revert;` to
`V2TreasuryDeployer._validate:133-138` — which already rejects a stop inside execution friction, the identical
shape. **≈120 bytes on `V2TreasuryDeployer` (runtime 19,803 free; initcode 31,928 of 49,152 — fits)**, but the
deployer does not receive `taxBps`/`lpFee` and passing them costs ~40 bytes at the call site inside
`HedgeFunFactory._launch`, **which is v1-shared deployed source — spending bytes there forfeits the factory's
byte-identity with `main`, which is currently its best property.** So the practical version is **0 bytes**:
hard-raise `minTaxBps` to 122 in the v2 Defaults.

---

### L-4 · Low · After a failed graduation booking, an unpaid and undeadlined `book()` sets the cost basis of the entire treasury share of the raise at a Chainlink round of the caller's choosing

**Location** `src/v2/HedgeFunV2Factory.sol:150-153` (`try … book() … catch {}`, the result only emitted as
`GraduationCapitalSplit.treasuryBooked`), `src/v2/HedgeFunV2Treasury.sol:46-57` (`book()` public, unpaid, no
deadline), `src/HedgeFunTreasuryBase.sol:289-317` (`_book` takes the health price as cost).

**Lanes** Lane 15 (E-7), sole source; the open `book()` finding from rounds 1–2 re-sized for v2.

**Status** REASONED. Triage confirmed the `try/catch` and the unpaid public `book()` by reading.

**Conditions** 1. Graduation lands while the stock oracle is unavailable or the market is shut — the equity
feeds are 24/5 and the weekend freeze is ~52 h, and a curve fills whenever buyers show up, so **a graduation
is more likely than not to land outside the session**. 2. Nobody with a stake calls `book()` first — it is
unpaid, so there is no keeper incentive to be first.

**Mechanism** V2 books the treasury's whole share in one `_book()` — ~$19,886 at the live NVDA listing and
LP 50%, against v1's tax-sweep-sized bookings. The cost recorded is the health-gated **Chainlink** price, not
the pool, so the caller cannot push the basis with capital — they can only **choose which round**, with no
deadline. Across a 52-hour freeze and a Monday gap that is an unbounded American option on a ±2–5% window.

**Impact** Loser: the treasury and its holders, via a mis-set trigger rather than a transfer. Seven of the
nine live v1 strategies have `stopBps = 0`, so a high basis means the lot simply never sells. **Option gain**
to whoever wants the lot frozen or unfrozen; **no certain gain to anyone.**

**Fix** Pay `book()` a bounty out of what it books, as every other permissionless entry point already is
(`bountyBps` exists and is 50) — **≈100 bytes on `HedgeFunV2Treasury` (2,993)**. Or refuse a booking whose
price differs from the graduation anchor by more than `maxDeviationBps` — ≈150 bytes, same contract.

---

### L-5 · Low · Vault addresses are publicly predictable before graduation and anything sent to one is destroyed, with no sweep and no event

**Location** `src/v2/CurveDeployer.sol:116-124` (`deployVault` / `predictVault`, salt `bytes32(id)`),
`src/v2/V2LiquidityVault.sol:66-67` (*"Donations already held here remain here"*).

**Lanes** Lane 13 (V2-03), sole source, EXECUTED.

**Status** EXECUTED. **Conditions** 1. Every input to the vault's initcode is readable the moment a launch
lands (`graduationConfig`/`strategies` public, `predictVault` `external view`) — **true**. 2. Someone sends
assets there — **UNMEASURED**; the plausible sender is a front end or keeper that pre-funds a computed
address.

**Mechanism** `seed` sizes everything from its `(max0, max1)` arguments and `collectFees` from the V4 delta —
never a balance. That is exactly right and is what makes `test_predonatedVaultTokensNeverIncreaseLpBudget…`
pass. The flip side is that the vault has **no function that can move a pre-existing balance** and no event
reporting one.

**Impact** Loser: whoever sends. **Certain, permanent, self-inflicted. No attacker gain.**

**Fix** None in the contract — a sweep is exactly the surface that makes "fee-only" stop being structurally
true, and M-1 shows what happens when a fix touches the vault (176-byte budget). Docs and ABI surface only:
say plainly that the vault has no recovery path, and give `predictVault` a `@notice` saying the address is for
verification only. **0 bytes.**

---

### L-6 · Low · The last tenth of every curve is negative-EV at the moment of purchase, and that tenth is a third of the money the mechanism needs

**Location** `src/v2/HedgeFunBondingCurve.sol:71-72, 89-104` (the terminal price), `src/v2/CurveDeployer.sol:79`
(only `lpBps` of the raise seeds the pool), `src/v2/HedgeFunV2Factory.sol:127-131` (graduation is atomic inside
the final buy).

**Lanes** Lane 15 (E-9, filed Medium — re-graded, see §5). Lane 13 measured the same shape from the other end
and filed it safe: with 90% of the curve funded by a third party, the crossing buy spent **20.0 stock** and an
immediate dump of everything it received returned **14.69**.

**Status** EXECUTED (`curve2.py`; lane 13's `test_L13_crossingBuyerCannotProfitByDumpingIntoTheFreshPool`),
and consistent with the author's own disclosure at `docs/V2_LP_DEPTH_EXPERIMENT.md:33`.

**Mechanism** Only the crossing buyer can graduate (L-1). At the live NVDA listing, 20 equal-inventory slices,
LP 50%, immediate exit: slice 18 → **1.25×**, slice 19 → **0.94×**, slice 20 → **0.67×**. Break-even sits at
about **90% of the sale**, and the last two slices are **35.7% of the entire raise**. The design places its
largest negative externality on precisely the agent whose action it requires; the rational strategy near the
end is to wait for someone else to cross, which nobody has an incentive to do.

**Impact** Loser: the last third of the raise, at the instant of purchase. **Certain gain: none to any actor**
— the value is not taken, it is the spread between the terminal curve price and a pool holding `lpBps` of the
raise. Marked at graduation: buyers paid 176.8 NVDA ($39,772) and hold a **4.5× paper gain** of which the pool
can return **40.5%**. Graduation marks the book up 4.5× and marks the cash down 59.5% in the same instruction.

**Low, not Medium** — see §5. Its two consequential limbs are carried at Medium elsewhere: **INTC cannot
graduate at all** is in M-2 (executed against the real pool), and **the non-graduating state is permanent and
unmodelled** is in M-4.

**Fix** The lever that works is `saleBps` (M-3): at 70% the terminal multiple is 11× and break-even moves
later. Filling the crossing buyer's slice at the average rather than the terminal price, or a batch close, is
a new contract, not an edit — `HedgeFunV2Factory` has **27 bytes**.

---

### Info findings

**I-1 · Info · `registerGraduatedWithVault` validates nothing about the vault beyond `code.length != 0`, and from the hook alone the "permanently locked liquidity" claim is not checkable in either direction.**
`src/hooks/HedgeFunHook.sol:205-210`, `:130` (`FLAGS = 0x2844`), `:243-249`. **This is the resolved
disagreement — see §5.1.** Lane 14 (V1D-02, Low) EXECUTED a two-line `NotAVault` contract into the seeder
slot; lane 13 (V2-05b, Info) EXECUTED that no reachable path exists. **Triage: Info.** Verified by triage
(`git grep registerGraduated -- src script deploy`): the only non-test call site anywhere is
`src/v2/CurveDeployer.sol:94`, whose `g.vault` is the return of `CurveDeployer(SELF).deployVault(…)` **ten
lines above at `:84`**, `_register:213` is `msg.sender == factory`, `bind()` is once-for-good so a hook obeys
exactly one factory forever, and `_register:221` makes registration once-only.
**Lane 13's separate point is kept and is the reason to fix it anyway:** the hook carries no
`BEFORE_REMOVE_LIQUIDITY` flag, so it has no say over liquidity leaving a pool and no check that the seeder
lacks removal code. **A reviewer of the hook alone — which is exactly what a Uniswap per-address
routing-allowlist reviewer sees — cannot conclude the position is locked.** The hook's own header already
says *"its registered **immutable** vault (V2)"*, which is doing work the code does not support. **Fix**:
require `V2LiquidityVault(vault).poolKey().toId() == key.toId()` (the vault already exposes `poolKey()` at
`:63`) — **~90 bytes on the hook, which has 5,222 free and is being redeployed at a new mined address
anyway; 0 on `CurveDeployer` (176) and 0 on the factory (27).** It closes no hole today; it makes the claim
checkable from the artefact the reviewer reads.

**I-2 · Info · A graduated pool opens with the sell spike off as well as the snipe window, and only the snipe half is explained anywhere.**
`src/hooks/HedgeFunHook.sol:209` (`lastEventAt = 0`) and `:320-327` (`_sellRate` reads `last == 0` as flat),
against `src/v2/HedgeFunV2Factory.sol:101-103`. **This is the resolved disagreement — see §5.2.** Lane 13
(V2-05c, Info) and lane 15 (E-11, Medium) both reached it; lane 15 expected the opposite to be the headline
and filed the "no spike at graduation" claim **correct as written** in its own safe list. **Triage: Info** for
the choice, with the re-arming half merged into **H-1** (same mechanism) and the disclosure half merged into
H-1's disclosure limb. EXECUTED (lane 13): immediately after a real graduation `sellRateBps == 1000`,
`buyRateBps == 1000`, `lastEventAt == 0`, with `spikeBps == 9000 / spikeSeconds == 120` sitting unused in the
same `Rates`; re-confirmed by triage's own `test_T3_oneWeiPotArmsTheNinetyPercentSpike` ("graduated pool opens
flat"). Two *separate* suppressions happen: `_openAndSeed:101-103` zeroes the snipe rates **with a comment
justifying it**, and `registerGraduatedWithVault:209` zeroes the spike **with no comment at all**. Lane 15's
price for the choice, kept: the same early dump returns 1.5× at spike+0 s against 13.4× flat, a **9.0×
swing between the dumper and the fee recipients — while the pool price lands at 47% in all three cases.**
**Fix**: either delete the `:209` assignment (**−5 bytes on the hook**) so a graduated pool opens inside the
decaying spike, or add a comment at `:209` and correct the three documents. At minimum, comment the line.

**I-3 · Info · `registerGraduated` (the vault-less variant) is unreachable, and calling it would burn a treasury's only registration slot on a pool nobody can seed.**
`src/hooks/HedgeFunHook.sol:196-202`. Lane 13 (V2-05) + lane 14 (V1D-05), both EXECUTED by grep; triage
re-ran the grep — the only reference outside the definition is `test/V2Factory.t.sol:172`. It would leave
`liquidityVaultOf` unset, `_onlySeed` would fall back to `factory`, and the v2 factory's `_openAndSeed` never
sets `_seeding`, so the inherited `unlockCallback` reverts `NotPoolManager` for everyone — a registered pool
that is **seedable by nobody**, while `_register`'s `AlreadyRegistered` makes both `pools[id]` and
`poolOfTreasury[treasury_]` one-way. That is precisely the v1 condition that forced `lpFee = 0`, re-created on
a factory where `_minLpFee()` is 1. **Fix**: delete it (gives bytes back) or give it the same `vault`
requirement its sibling has.

**I-4 · Info (highest remediation urgency in the report) · Round 1 named "adds a second liquidity path" and "seeds the anchor at `wire()`" as the two changes that re-open F-40; this PR does both, and the three places that record the invariant were not updated.**
`src/HedgeFunTreasuryBase.sol:429-433` and `:537-541`, `docs/SECURITY.md:130`, against
`src/v2/HedgeFunV2Treasury.sol:183-189`. Lane 14 (V1D-04) + lane 16 (F-04 / C26). **It does not re-open the
brick**: `CurveDeployer.executeGraduation` runs `V2LiquidityVault.seed()` (initialize + full-range
`modifyLiquidity`) *before* `wire()` in one atomic call, and `seed()` reverts on zero liquidity, so `getSlot0`
at `wire()` is the terminal curve price with balanced depth behind it — not F-40's MIN/MAX-sqrt-price pin.
**What is wrong is the record.** Two comments in an immutable base assert the opposite of what the shipped
subclass does, and `docs/SECURITY.md:130` still states as an invariant something this PR deliberately ends —
and `docs/SECURITY.md` has **zero changed lines in this PR**. **The grade and the urgency disagree on
purpose**: the rubric grades post-deployment value impact and there is none, so Info; but round 1 wrote the
precondition down *specifically* so a future round would catch this, the PR met it, and nobody updated the
records. **Rank it first for remediation and last for severity. 0 bytes.**

**I-5 · Info · The v2 anchor override's stated justification names a condition that cannot occur.**
`src/v2/HedgeFunV2Treasury.sol:180-182` ("even if high-frequency swaps **exhaust** the hook's observation
ring") against `src/libraries/TwapRing.sol:24` (`SLOTS = 1024`), `src/HedgeFunTreasuryBase.sol:96`
(`BUYBACK_TWAP_WINDOW = 600`) and at most one write per second. Lane 14 + lane 16 (F-10 / C27), and
`TwapRing.sol` is untouched by this PR. A full ring always spans ≥1,023 s, so it cannot be exhausted; the
anchor fallback is reachable only in the pool's first 600 seconds — which is the *other*, correct half of the
same comment. The decision is right; the reason given is not. **Fix: delete the clause. 0 bytes.**

**I-6 · Info · `_terms` went from `pure` to `view`, so `predict()` is no longer a total function.**
`src/HedgeFunFactory.sol:298` and `:287-291` against `src/v2/HedgeFunV2Factory.sol:74-79` →`_preflight` →
`revert Unseedable()`. Lane 14 (V1D-07), EXECUTED. `pure` was a structural promise that the terms hash is a
function of its four arguments alone. The v2 override reads storage deliberately and correctly, and *widens*
the restatement guard round 2 verified (it calls `super._terms` and appends `saleBps`, `virtualStock`,
`lpBps`). The cost: `predict(q)` — a `view` a front end calls to quote — now reverts for any request whose
curve geometry does not close. **0/0.** **Fix**: one doc line saying `predict` may revert `Unseedable` and a
front end must treat that as "these parameters cannot launch", not an RPC failure. 0 bytes.

**I-7 · Info · `nonReentrant` moved to the wrappers and `_canAddLot`'s base default is `true`, so two properties round 1 proved with one grep each now depend on every override.**
`src/HedgeFunTreasuryBase.sol:285`, `:324`/`:326`, `:376`/`:378`, `:402`/`:404`, `:287`. Lane 14 (V1D-08),
EXECUTED for the current call graph: every live caller is guarded, and in `HedgeFunTreasury` the
`_canAddLot` gate is provably inert (statically bound to the base `return true`) — **16 bytes of unreachable
code**, measured by differential build (18,344 → 18,328 with the gate deleted; → 18,326 also reverting
`stockEquivalentHeld`, so that change is 18 bytes, and the remaining ~21 of the +55 is plumbing). **0/0.**
**Fix**: two sentences in the base — that `_takeProfit`/`_stopLoss`/`_buyDip` assume a guarded caller, and
that a subclass which iterates `lots` must override `_canAddLot`. 0 bytes.

**I-8 · Info · `HedgeFunV2BuybackTreasury.book()` never reaches `_book()`, so the scorecard the v1 base publishes divides by zero for strategy kind 1.**
`src/v2/HedgeFunV2BuybackTreasury.sol:30-37` against `src/HedgeFunTreasuryBase.sol:152` and `:300`. Lane 14
(V1D-06), EXECUTED by grep (`totalStockReceived` has exactly one write, inside `_book`). Kind 1 does
`buybackStock += unbookedStock()` and returns, so the formula has a growing numerator over a permanent zero,
while `totalStockSpentOnBuybacks` keeps incrementing. **No impact: kind 1 is marked DRAFT and registered by
nobody** (`V2TreasuryDeployer`'s constructor registers only kind 0). Recorded as the cleanest instance in the
PR of an override breaking an invariant a prior round proved on the base — and the number it breaks is the
product's headline. **Fix**: `totalStockReceived += pending;` — ~20 bytes against the contract's **9,736**
free, **0** on the v2 factory. **This is also H-1's re-grade trigger.**

**I-9 · Info · V2 moves the choice of the treasury's entire bytecode to the creator, and the factory emits nothing that names it.**
`src/v2/V2TreasuryDeployer.sol:100-131` against `src/HedgeFunFactory.sol:37-47` (*"what a creator can NOT
choose, because each one is a way to rob the people who buy the token"*). Lane 13 (V2-04). The *integrity*
side is sound — the chosen code is in the CREATE2 address, which is in `terms`, so the choice cannot change
under a quote, and `setStrategyKind` keys on `msg.sender` so nobody picks for anyone else. What changes is the
**trust model**: v1's promise was that a creator fills in numbers inside owner-set bounds; v2 lets them pick
the contract from an owner-curated menu. **No value impact today (one-element menu).** Two consequences worth
recording: a kind-1 treasury accepts and displays tp/stop/dip parameters it ignores, so an indexer rendering
`params()` shows a rule that does not exist; and because `setStrategyKind` keys on `msg.sender` while
`_launch` permits a **vouched launcher** to launch with someone else's `q.creator`, **no periphery contract
can ever select a kind on its user's behalf**. **Fix**: cheapest is to document that kind resolution is
`V2TreasuryDeployer.strategyKindOf(salt)` and emit nothing new — an extra event field is **not affordable at
27 bytes** on the factory.

**I-10 · Info · `lpFee` left the base with no ceiling of its own; only a subclass overriding two unrelated virtuals consistently keeps fees out of a position nobody can reach.**
`src/HedgeFunFactory.sol:202`, `:205-206` against `:375-411` and `src/v2/HedgeFunV2Factory.sol:54-55`, `:91`.
Lane 14 (V1D-01, filed Low — re-graded, see §5). EXECUTED: v1 still refuses every nonzero `lpFee` (1–10, 100,
500, 3000, `0x800000`, `type(uint24).max` all revert `BadRequest`; 0 passes), and v2 accepts exactly 1…3000.
**Certain gain 0, option gain 0, no actor, no exposure in v1 or v2.** What is gone is the *structural*
guarantee: a third factory that raised `_maxLpFee()` without replacing `_openAndSeed` would seed a
factory-owned position accruing fees forever — the exact state round 1 cleared *because it could not happen*.
At `_maxLpFee() = 1_000_000` the pool is additionally a brick (a 100% swap fee). **Fix**: one line in
`unlockCallback` before `modifyLiquidity` — `if (key.fee != 0) revert BadRequest();` — **~15 bytes against
`HedgeFunFactory`'s 5,647**, 0 on the v2 factory and 0 on `CurveDeployer`; plus ~5 bytes bounding
`_maxLpFee()` against `LPFeeLibrary.MAX_LP_FEE`. **Note the trade**: spending bytes there forfeits
`HedgeFunFactory`'s byte-identity with `main` (same caveat as L-3).

**I-11 · Info · `_minLpFee()` returning 1 makes the "nonzero LP fee" the fee-only vault exists for economically null.**
`src/v2/HedgeFunV2Factory.sol:54`. Lane 15 (E-6, filed Low — re-graded). V4 `lpFee` is hundredths of a bip, so
1 is **0.0001%**: a $40k pool doing $1M of volume collects $1, and `collectFees()` returns `(0, 0)` on every
call because `feeGrowthInside × L / 2^128` rounds to zero — 7,112 bytes of settlement machinery realising
nothing. **No value loss.** The interest is that **one parameter secretly controls two unrelated behaviours**:
at `lpFee = 1` the vault is dead **and so is H-1's fuel line**, and whoever sets it will be reasoning about
yield rather than about how fast a griefer can re-arm a 90% sell tax. **Fix**: `_minLpFee() → 500` (the tier
of the live NVDA/GME/SPCX V3 pools) or 3000. **0 bytes** — a constant in an already-present function. The
defensible positions are `lpFee = 1` with the vault treated as vestigial, **or** `lpFee = 3000` *after* H-1's
inlet is severed; setting it in between for yield buys 0.485 pp of manipulation cost and sells a permanent
90% sell tax.

**I-12 · Info · The curve's opening burn transfers nothing to anyone, and the author's own scenarios show the sandwich survives it.**
`src/v2/HedgeFunBondingCurve.sol:79-87`, `:126-131`; `docs/V2_MARKET_SCENARIOS.md`. Lane 15 (E-8, filed Low —
re-graded; its own impact line reads "no new loss"). The buy tax is a **burn of the buyer's own tokens**, not
revenue: `newReserve` depends only on the stock input, so the tax changes nothing about price or about the
cost of reaching graduation — it only decides how many gross tokens reach the buyer. So the 99/66/33 schedule
is a **3-second delay, not an auction**; nothing is raised and nobody is paid (the one thing it buys is a
smaller float at graduation). And it does not stop sandwiching: the author's own measured results give the bot
**−17.76 / +34.77 / +64.23 / +78.13 STOCK** at seconds 0/1/2/3; a 0.1-STOCK leg against a 99% `minOut` still
nets **+0.34**, and 0.01 against 99.9% still nets **+0.034** — and the document itself ends *"仍有狙击风险阻断项"*.
**Recorded so the report says plainly that a burn is not a fee and a fee is not ordering protection.** The
batch/uniform-price work in `docs/V2_BATCH_OPENING_EXPERIMENT.md` is the right direction and is correctly
marked not-for-production — note its own finding that direct aggregation is **worse** than the status quo at
large sizes.

**I-13 · Info · `docs/V2_BONDING_CURVE.md` contradicts itself and the compiler on the factory's remaining margin.**
`:111` ("the factory sits **143 bytes** under EIP-170") against `:269` ("only **27** runtime bytes free").
Lane 13 (V2-06) + lane 16 (F-03 / C13), both EXECUTED; **triage re-measured: 24,549 runtime, margin 27.**
`:111` is the sentence a reader hits while reading *why* strategy kinds live in the deployer — i.e. exactly
the decision the margin justifies — and it overstates the headroom 5.3×. Every other row of the `:258-267`
size table matches the build exactly: the table was regenerated, the prose was not. **Fix**: delete the figure
at `:111` and point at the table. 0 bytes.

**I-14 · Info · `V2LiquidityVault.seed`'s `onlyFactory` guard is covered by no test in the repository, and it is a tripwire for the refactor the byte budget makes likely.**
`src/v2/V2LiquidityVault.sol:70`. Lane 16 (F-08) EXECUTED the mutation and the **lead reproduced it
independently** (R3-L9): deleting the guard leaves the entire non-fork suite **byte-identically green** —
1,410 passed / 1 failed (the known control) / 51 skipped. **Zero of ~1,412 tests cover the access control on
the function that seeds the permanently locked position.** It is not exploitable today, and that was checked
rather than assumed: `_graduate` computes the opening price itself from the curve's own reserves (**not**
caller-supplied), and `deployVault` + `seed` happen in the same call with no block boundary, after which
`seeded` makes `seed()` revert `AlreadySeeded`. **The synthesis is the point, and it links to M-1**: the guard
is dormant *because* graduation is atomic, and the two contracts that would have to change to make it
non-atomic — `HedgeFunV2Factory` and `CurveDeployer` — have **27 and 176 bytes**, so M-1's only correct fix
(36 bytes over) requires exactly the `CurveDeployer` split that would separate deployment from seeding. **The
most likely future change to this system is the one that makes this untested control load-bearing.** The
sibling guard in the same doc claim, `HedgeFunBondingCurve.release`'s `NotFactory`, is also weakly covered:
the test calls it on an **Active** curve where `status != Ready` refuses first. **Fix**: one test calling
`seed()` from a non-factory address and one calling `release()` from a non-factory address while the curve is
genuinely `Ready`. 0 bytes.

**I-15 · Info · The adversarial review's GO is scoped to a ref at which two of the nine v2 contracts did not exist.**
`docs/V2_ADVERSARIAL_REVIEW.md:3-10`. Lane 16 (F-06 / C12), EXECUTED: `git ls-tree 885123e src/v2/` returns
seven files — `V2LiquidityVault.sol` (173 lines) and `HedgeFunV2BuybackTreasury.sol` (44) **did not exist**,
and `HedgeFunV2Treasury.sol` is +161, `V2TreasuryDeployer.sol` +137, `CurveDeployer.sol` +108 since.
`V2LiquidityVault` is now the owner of **every graduated LP position** — the single most consequential
contract in the v2 lifecycle — and it post-dates the review that declares GO. The tests moved forward while
the review text did not. `V2_BONDING_CURVE.md:251-254` does disclose this, but that sentence is in a
different document. **Fix**: a two-line header naming the commits that post-date the round. 0 bytes.

**I-16 · Info · The adversarial review's reproduction evidence does not reproduce, and its live-venue figure is in no test.**
`docs/V2_ADVERSARIAL_REVIEW.md:83-106`. Lane 16 (F-05 / C10), EXECUTED for the local counts. `:95` claims
"1,355 passed / 0 failed / 36 skipped"; measured at `03ad70e`: **1,410 / 1 / 51**. `:83`, `:98` and `:105` cite
fork blocks 70,717,634 and 70,721,724; the test's own pin is **70,786,980** — and four sibling documents cite
70,786,980 correctly, so this is the only one that does not. `:86`'s "returned **6.450877074340927318 GME**"
appears **nowhere** in any test file at either ref, and the file contains no `log_named_*` call. The
reproduction command at `:102` itself is fine: re-run at `03ad70e` it gives **24 passed / 0 failed** with all
four fuzz targets at `runs: 512`, confirming the 3 × 512 × 48 = 73,728 arithmetic and the 8/9/7/1 suite
counts. **Fix**: restate the counts at the release commit, use the pinned block, and either assert the GME
figure or stop citing it. `docs/V2_PROFIT_FORK.md:14` shows the right disclosure to copy.

**I-17 · Info · "Multi-user sequences preserve … fee claims" does not test the fee split; a 100% reroute leaves the adversarial suite green.**
`docs/V2_ADVERSARIAL_REVIEW.md:39`; `src/v2/HedgeFunBondingCurve.sol:157-162`. Lane 16 (F-07), EXECUTED by
mutation: rerouting **100% of the protocol fee to the creator** leaves all 24 adversarial tests passing (it
turns 2 red in `V2CurveSecurity.t.sol`, which the review does not cite). Both suites check the fee *total* and
the *sum* of the three claimables, never a claimable against `protocolBps`/`creatorBps`. The other three nouns
in that sentence are real — a one-wei `realStockReserve` understatement turns 13 of 24 red with the
purpose-built message. **Fix**: say "fee totals and delivery", or add per-role assertions. 0 bytes.

**I-18 · Info · `snipeSeconds` has no upper bound; the docs present 3 seconds as the mechanism.**
`src/HedgeFunFactory.sol:197` (`_setDefaults` validates `snipeBps` and nothing about `snipeSeconds`), `:103`
(`uint8`); `src/v2/HedgeFunBondingCurve.sol:64`. Lane 16 (F-09 / C25). The owner may set a **255-second**
window at up to 99% burn for future launches. The schedule itself is exactly right (9900/6600/3300/flat at
elapsed 0/1/2/≥3), and the docs correctly label the values "defaults"/"candidate settings" — this is the
bound-vs-policy distinction again. Worth crediting on the other side: the **`uint8` type is itself the bound
round 1 asked for on v1's `uint32 spikeSeconds` and never got.** **Fix**: a ceiling in `_setDefaults` would
cost bytes on `HedgeFunFactory` (5,647 free, ample) **but would forfeit its byte-identity with `main` — not
worth it.** Docs only. 0 bytes.

**I-19 · Info · "roughly 100 stock of selling before the price halves" overstates the pool's depth.**
`docs/V2_BONDING_CURVE.md:77-81`. Lane 16 (F-11 / C17), REASONED on the doc's own worked example: the pool
opens with 200 stock against 80,000 FUN, `k = 1.6e7`, so `P' = P/2` at `x' = 141.42` — **33,137 FUN in,
58.6 stock out, 82.8 stock of opening-price notional**, not 100. The two neighbouring figures are exact. The
paragraph exists to disclose how thin the post-split pool is, and it is 17–41% thinner than the sentence says
— **the error runs the wrong way for a disclosure.** 0 bytes.

**I-20 · Info · `CurveDeployer.deploy` uses an unannotated `assembly` block where `deployVault` two lines below uses `assembly ("memory-safe")`.**
`src/v2/CurveDeployer.sol:110` vs `:119`. Lane 13 (V2-07), REASONED. `foundry.toml` sets no `via_ir` at this
ref, so today this costs only the memory-safe optimiser passes and nothing is unsafe. It stops being cosmetic
the day IR is turned on — which is the obvious next lever when `HedgeFunV2Factory` next needs a byte, and
which the sibling `rh` repo already had to do for an EIP-170 squeeze. Make it consistent now, while it is
free.

**I-21 · Info · `bind()` remains permissionless on both new deployers; the deployment-day griefing vector from rounds 1–2 now covers four contracts.**
`src/HedgeFunDeployers.sol:23-26` (inherited by `CurveDeployer` and `V2TreasuryDeployer`),
`src/v2/HedgeFunV2Factory.sol:44-46`. Lane 13 (V2-08), a restatement, not a new class: anyone watching the
mempool can `bind()` a freshly deployed deployer first, after which the factory's constructor reverts
`AlreadyBound` and the deployer is landfill. Same loud, pre-live failure rounds 1–2 recorded, still the right
trade — but a v2 deployment now binds **four deployers plus the hook**, and the new hook is squattable between
deploy and bind (round 1 F-23, worsened in round 2). Two v2-specific facts recorded as **safe**:
`V2TreasuryDeployer._onlyOwner()` (`:65-67`) fails closed while `factory == address(0)`, so a squatter cannot
`registerKind` or move `lpBps`; and `setStrategyKind` on an unbound deployer can only select kind 0, because
`_kinds.length` is 1 from the constructor.

**I-22 · Info · The protocol's revenue from one complete v2 lifecycle is ~$361.**
`launchFeeAmount` = **5 USDG** (read 2026-09-27). On a full NVDA curve plus a full exit cascade the hook take
at the flat 10% is 1,789 USDG, of which the protocol's 2000 bps after the 0.5% sweep tip is **356 USDG** —
≈**$361 per launch against a $39,772 raise**; the creator takes 534. Under H-1's re-armed spike those become
990 and 1,485. Lane 15 (E-10). No value impact; recorded because **every parameter in H-1, M-3 and L-3 is a
trade between this number and buyer outcomes, and the number is small enough that the trade is not close.**

**I-23 · Info · The shipped size table is incomplete in the two places that matter most.**
`docs/V2_BONDING_CURVE.md:258-269`. Lane 16 (C14): every listed row is exact, but `HedgeFunV2BuybackTreasury`
(14,840) and — the important one — **`TreasuryDeployer` (23,556 / margin 1,020)** are absent. `BASELINE3.md`'s
own first size table made the same omission and had to be corrected mid-round. A table that omits the
embedding deployers is the exact trap R3-L6 describes. **Fix**: add both rows and a column naming, for each
contract, the deployer that embeds it. 0 bytes.

---

## 4 · Exposure at first v2 deployment — the ranking that matters

Nothing in `src/v2/` is deployed. **Nine v1 strategies are live** (`strategyCount() = 9`, `publicLaunch()
= true`, 18 stocks listed, chain reads 2026-09-27) and **no finding in this report reaches any of them** — the
only v1 artefact whose bytecode moves is `HedgeFunTreasury`, which the live factory will never deploy. So the
column below is "what is exposed on day one of a v2 deployment", not today.

| # | finding | severity | armed when | who loses | certain / option | fix fits? |
|---:|---|---|---|---|---|---|
| 1 | **H-1** spike re-armable by anyone | High | **block one of the first graduated pool**, permanently, recurring; fuel costs 334 wei of stock | every FUN seller (measured 1/9.0 of proceeds) | creator + protocol **certain**; caller bounty certain (zero at the 1-wei floor) + exit-ordering **option** | **yes** — 450–700 B on the treasury (2,993). Zero-byte stopgap: `spikeBps = 0` |
| 2 | **M-3** `MIN_LP_BPS` / `MAX_SALE_BPS` | Medium | **the moment the bytecode is deployed** — the constants are immutable; one owner call per stock, no timelock | curve buyers, up to 91.2% of aggregate capital | none certain, none option — **stranded, not taken** | **yes** — two constant edits, 0 bytes |
| 3 | **M-2** raise through the stock's only V3 pool | Medium | **the first launch on a thin stock**; INTC cannot graduate at all | the v1 treasury on the same stock (≈$10,224 of exposure today, anti-correlated with the thin pools) | none certain; **option** to anyone wanting a v1 halt | **yes** — a listing rule, 0 bytes |
| 4 | **M-1** `collectFees` couples its legs | Medium | only on an issuer block of a contract (never observed); permanence UNMEASURED | FUN holders (the burn) + the treasury (its budget) | 0 / 0 — **no value passes through** | **NO — 36 bytes over EIP-170 on `CurveDeployer`. Requires splitting it in two** |
| 5 | **M-4** doc evidence conditional / one table 31% wrong | Medium | the day a launch UI shows the numbers `:81` says to show | whoever sets `lpBps`/`saleBps`, and every buyer of that launch | 0 / 0 | yes — 0 bytes |
| 6 | **L-3** impact cap vs round-trip friction | Low | any launch with `taxBps < 122`, or the day the cap is raised | the treasury's `buybackStock`, +0.02 USDG/cycle live, +4.58 at the ceiling | **option** to the attacker | yes at 0 bytes (`minTaxBps ≥ 122`); the structural version costs bytes on **v1-shared** source |
| 7 | **L-4** unpaid, undeadlined `book()` | Low | **every graduation outside the equity session** — more likely than not | the treasury, via a mis-set trigger on ~$19,886 | **option** only | yes — ~100 B on the treasury (2,993) |
| 8 | **L-6** negative-EV last tenth | Low | every curve, by construction | the last third of the raise, at the instant of purchase | none — it is a spread, not a transfer | design change only; **27 bytes** on the factory |
| 9 | **L-1** dead `graduate(id)` + permanent cap | Low | only on a blocked graduation (M-1's condition) | curve buyers + the creator | **option** | yes — the fix is a **deletion** that *adds* factory margin |
| 10 | **L-2** scorecard numerator | Low | never on the nine live strategies; only on a rebuilt v1 or a v2 treasury | a reader of the token page | 0 certain / **option** to flatter | yes — 0 bytes (docs + one test) |
| 11 | **L-5** vault donations | Low | only if someone sends to a predicted address | whoever sends | certain, **self-inflicted**, no attacker | none in the contract (a sweep would break "fee-only") |
| 12 | **I-1 / I-14** hook accepts any vault; `seed`'s guard untested | Info | not reachable today; **both become load-bearing if `CurveDeployer` is split** (M-1's fix) | — | 0 / 0 | yes — ~90 B on the hook (5,222), and one test |
| 13 | **I-4** three records of an invariant this PR ends | Info | **already wrong, in an immutable base** | the next reviewer | 0 / 0 | yes — 0 bytes. **Rank first for remediation** |
| 14 | the remaining Infos | Info | — | — | 0 / 0 | mostly 0 bytes |

**Two facts to state before the findings, not inside one.** (a) A v2 factory deployed at **27 bytes** can
never receive a fix; every finding against it is permanent by construction, and a change means a **new
factory, a new hook, new deployers and a fresh Uniswap routing-allowlist submission**, with already-launched
strategies stranded on the old code exactly as the nine v1 ones are. (b) `CurveDeployer`'s **176 bytes** are a
hidden second budget on two other contracts that each read as having ~17.5 kB free. Anyone costing a v2 fix
must check which deployer embeds the contract they are changing.

---

## 5 · Disagreements, and how each was resolved

### 5.1 `registerGraduatedWithVault` validating nothing — lane 14 **Low** vs lane 13 **Info** → **Info**

Both lanes ran code and neither was wrong about what it ran. Lane 14 EXECUTED a two-line `NotAVault` contract
into a pool's `liquidityVaultOf`; lane 13 EXECUTED that no path reaches that state.

**Resolved on reachability, as instructed, and triage re-verified the chain itself rather than taking either
lane's word:** `git grep registerGraduated -- src script deploy` at `03ad70e` returns the two definitions and
**exactly one call site**, `src/v2/CurveDeployer.sol:94`, whose `vault` argument is the return value of
`CurveDeployer(SELF).deployVault(…)` ten lines above at `:84`; `_register:213` requires `msg.sender ==
factory`; `bind()` is once-for-good, so a deployed hook obeys exactly **one** factory for its entire life;
and `_register:221` makes registration once-only per pool and per treasury.

**So the condition list has no entry that can ever flip to true for a deployed (hook, factory) pair.** Lane
14's own conditions 2 and 3 say as much. Its Low rests on "a *future* factory could name an attacker-controlled
vault" — but a future factory needs a future hook, and that hook's check is code that does not exist yet.
Grading a property of unwritten code as a Low against this immutable artefact is not what the rubric's
"post-deployment state" means. **Info.**

**Lane 13's separate point is kept, and it is why the check should be added anyway:** the hook carries no
`BEFORE_REMOVE_LIQUIDITY` flag (`FLAGS = 0x2844`) and no check that the seeder lacks removal code, so from
**the hook alone — the artefact a Uniswap per-address allowlist reviewer reads — the "liquidity is permanently
locked" claim is not checkable in either direction.** It is true by construction of `deployVault`, which that
reviewer never opens. The hook's own header calls the vault "immutable", which the code does not support. The
fix is **~90 bytes on a hook with 5,222 free that is being redeployed at a new mined address regardless** —
cheap, and it converts a construction property into a checkable one. Carried as **I-1**.

### 5.2 `lastEventAt = 0` on graduated pools — lane 13 **Info** vs lane 15 **Medium (E-11)** → **Info**, with the re-arming half merged into H-1

Lane 13 measured that the **crossing buyer cannot profit** from the combination (20.0 stock in, 14.69 back on
an atomic dump). Lane 15 priced the exposure to **earlier curve buyers** and to the fee recipients, and graded
it Medium on a revenue-leak plus disclosure basis. **Both measurements are right. The rubric selects lane
13's framing, for three reasons, and I resolve this against lane 15:**

1. **Forgone tax is not a leak.** Lane 15 names the losers as "the protocol, creator and treasury, in their
   own fee revenue". Choosing not to apply the spike at the open is the same *class* of decision as a creator
   choosing `taxBps = 500` instead of 1500. If a below-maximum tax at one moment is a Medium "bounded leak",
   then every tax parameter in the system is a Medium. The rubric grades value impact of a defect; this is a
   deliberate, documented choice with a stated rationale in the adjacent line of code.
2. **The "grief that degrades the product" limb fails on lane 15's own evidence.** Its cited measurement says
   *"the pool price lands at 47% in all three"* cases. The spike does **not** protect later holders' price; it
   only decides whether the dumper or the fee recipients get the 9×. So no product outcome degrades.
3. **Nobody extracts.** Lane 13 measured the natural candidate — the graduating buyer — and found it
   unprofitable. There is no actor with a certain or option gain from the line itself.

**What was genuinely Medium in E-11 is its re-arming half, and that is H-1's mechanism, not a second
finding.** Deduplicating by mechanism rather than wording: `lastEventAt = 0` makes `noteEvent()`'s
`block.timestamp < lastEventAt + 2·spikeSeconds` guard pass trivially, so **the first `buyback()` after
graduation arms the spike** — which is exactly the chain triage executed in H-1, and the doc claim it
falsifies (`V2_LP_DEPTH_EXPERIMENT.md:49-50`, "the first minutes after graduation are the flat 10%") is
carried as H-1's disclosure limb. Filing it twice would double-count one mechanism.

**What survives as Info (I-2), because lane 13 is right that it is worth a line:** the suppression is **two
separate lines in two different contracts**, and only the snipe half carries a comment. A future reader
patching `_openAndSeed` will not learn from that comment that a second, independent suppression lives on the
hook. Lane 15's 9.0× price for the choice is kept in I-2 as the number any reversal should be argued on.

### 5.3 The one High — does a REASONED lane finding plus a lead code-walk support a High? → **Yes, and it is no longer REASONED**

Lane 15 did not execute E-1; it relied on the author's own fork assertions. The lead walked the call path and
confirmed the mechanism by reading, and flagged the **one-wei floor** as the specific open question — the lane
interpolated from a 0.0012 GME measurement rather than driving `buybackStock` to 1.

**Triage's position on the method:** a REASONED finding plus an independent code-walk is *not* sufficient for a
High under a rubric whose own rule is "a claim is only as good as the line that settles it" — confirmation
count is never evidence, and two readings of the same lines are one route, not two. So triage executed it
rather than averaging the two sources. **The result upgrades the evidence and sharpens the mechanism**: with
`buybackStock = 1 wei`, `buyback()` returns `spent = 1, burned = 0` and the spike arms — the one-wei
"buy-back" buys nothing and burns nothing, so it is a pure spike-arming primitive, which is *stronger* than
the lane's claim that "any nonzero pot arms the spike". The full three-leg chain was then executed with an
unprivileged caller, the seller's loss measured at 9.0×, the 240 s re-arm cadence measured, and the fuel
threshold measured at **334 wei of stock**.

**High, not Critical**, because the taker is not the caller: the value lands on the protocol's designed
recipients and the caller collects a bounty (zero at the floor) plus an exit-ordering option. **High, not
Medium**, because it is unprivileged, recurring, permanent and needs only timing.

**What remains REASONED and must be said in the report body, which H-1 does:** the v2 `spikeBps`/
`spikeSeconds` do not exist on chain — the finding evaporates at `spikeBps = 0` — and the dollar pricing and
the 27.8% time-average are model and v1-carried figures respectively.

### 5.4 Grades taken down from the lanes, against the rubric's "Info = no value impact"

Four findings whose own Impact sections state zero value impact were filed Low by their lanes. Re-graded to
Info; all four retain their remediation notes and two of them rank high for action:

| finding | lane's grade | the lane's own impact line | triage |
|---|---|---|---|
| `lpFee` base has no ceiling (I-10) | lane 14 Low | "No exposure today, V1 or V2. **Certain gain 0, option gain 0. No actor.**" | **Info** |
| creator picks the treasury bytecode (I-9) | lane 13 Low | "**No value impact today** (one-element menu)." | **Info** |
| `_minLpFee() = 1` (I-11) | lane 15 Low | "**No value loss.**" | **Info** |
| the opening burn / sandwich (I-12) | lane 15 Low | "**No new loss** beyond what rounds 1–2 already covered." | **Info** |

And one taken down from Medium: **E-9 → L-6 (Low)**. Lane 15 graded the negative-EV last tenth Medium. Under
the rubric there is no leak (nobody gains; the capital is the spread between a terminal curve price and a pool
holding `lpBps` of the raise), no grief (nobody operates it), and the disclosure limb fails because the author
*does* disclose it at `docs/V2_LP_DEPTH_EXPERIMENT.md:33` ("a last buyer who dumps loses 20–68%"). Its two
genuinely Medium limbs were moved to where they are measured: **INTC cannot graduate → M-2** (executed against
the real pool) and **the non-graduating state is permanent and unmodelled → M-4**. I record that the rubric
has no clean slot for "the design places a certain loss on the agent whose action it requires when nobody
gains", and that this is the finding most likely to be re-graded by a reader who disagrees with that reading.

### 5.5 Findings merged because they are one mechanism reached by two routes

| merged as | routes |
|---|---|
| **M-3** | lane 15 E-3 (the floors are 6×/11× too wide) + lane 16 F-02/C16 (a shipped doc still calls the split a constant) — one owner dial, two faces |
| **M-4** | lane 15 E-4 (the method: model-vs-model, in-sample, graduation-conditional) + lane 16 F-01/C9 (the numbers: 31% wrong at this ref) |
| **I-1** | lane 14 V1D-02 + lane 13 V2-05b (§5.1) |
| **I-2** | lane 13 V2-05c + lane 15 E-11 (§5.2) |
| **I-3** | lane 13 V2-05 + lane 14 V1D-05 |
| **I-4** | lane 14 V1D-04 + lane 16 F-04/C26 |
| **I-5** | lane 14 V1D-04's last paragraph + lane 16 F-10/C27 |
| **I-13** | lane 13 V2-06 + lane 16 F-03/C13, both EXECUTED, and re-measured by triage |
| **I-14** | lane 16 F-08 + the lead's R3-L9, which adds the `CurveDeployer`-split tripwire |
| **L-1** | lane 13 V2-02 + lane 15's independent finding of the same unreachability inside E-9 |
| **H-1** | lane 15 E-1 + lead R3-L8 + **triage's execution**; absorbs E-11's re-arming half |

**Where a context-free route and a full-context route landed on the same thing.** Lane 13 was scoped to the
nine new contracts with no prior-round history; lane 14 carried rounds 1–2's conclusions. They converged
independently on (a) the seeder-validation gap, (b) `registerGraduated` being dead code, and (c)
`V2LiquidityVault` having no removal path — and the lead reached (c) a third time (R3-L2). **That tells us the
surface is highly visible to any reader, which is a fact about reachability. It is not evidence that the
conclusion is right**, and in case (a) the two routes reached *opposite grades* from the same code.

---

## 6 · Consolidated "checked and found safe"

Every item carries the line that makes it safe. Deduplicated across all five sources; where more than one lane
reached an item independently, that is noted — as a reachability observation, never as evidence.

### The bonding curve

1. **The invariant is exact, not approximate.** `y == ceilDiv(k, x)` holds at construction and is
   re-established by every trade: `HedgeFunBondingCurve.sol:97,101` (buy), `:141` (sell). EXECUTED — 256-run
   fuzz over 24 mixed steps asserts it after every step, plus `tokenBalance == tokenReserve` and
   `stockBalance ≥ realStockReserve + totalFees`. The author's own 48-step fuzz asserts the same at
   `test/V2AdversarialAccounting.t.sol:75`.
2. **Virtual stock is never spendable.** `quoteSell` computes `gross` then `if (gross > realStockReserve)
   revert Insolvent()` (`:142`); `release()` sends `realStockReserve` only (`:185-188`); `_solvent()`
   (`:214-218`) checks the balance against `realStockReserve + totalFees`, excluding `virtualStock`, and is
   asserted before and after every state-changing path. *(Reached independently by lane 13, lane 15 and the
   lead.)*
3. **Rounding favours the reserve or the current trader, never a later one.** Buy rounds the new reserve up
   and charges only `ceilDiv(k, newReserve) − y ≤ budget`, so the dust is **refunded** rather than banked where
   a later trader could harvest it (`:99-100`); sell rounds the payout down. `paidOut ≤ paidIn` over every
   fuzzed sequence.
4. **A sequence of buys and sells cannot leave the reserve short of what the remaining supply can redeem.**
   `quoteSell:139` caps `tokenIn` at `initialSupply − tokenReserve`, which with the invariant makes
   `gross ≤ realStockReserve` always and `Insolvent` unreachable. EXECUTED — the **entire** float sold back in
   one call still satisfies `out + tax ≤ realStockReserve`.
5. **The curve cannot be round-tripped for profit.** Buy and sell canonicalise to the same `ceil(K/x)`, so an
   integer-rounding surplus cannot be harvested; the burn improves a seller's price by at most 1.087× on a
   whole-curve round trip, against a 19% tax. Never positive. The author's own
   `testFuzz_sameBlockRoundTripCannotExtractStockWithoutAnExternalTrade` asserts it strictly, and lane 16
   extended it past its range: a 25-stock curve round trip after the opening window loses 4.136 stock, the
   same on V4 after full spike decay loses 4.450, and **the creator**, round-tripping and claiming their own
   share of their own sell tax, still loses 3.819.
6. **Fees never eat the reserve and survive graduation.** `sell` moves exactly `tax` into
   `claimable`/`totalFees` (`:156-162`); `release()` moves only `realStockReserve`; `claimFees` has no status
   gate; `constructor:65` refuses `protocolBps + creatorBps > 10000`.
7. **Fee claims cannot be redirected or blocked.** `claimFees` (`:171`) zeroes the entry before sending and
   keys on the recipient, so anyone may deliver and nobody may redirect, and a reverting recipient rolls back
   only its own claim — the native fix for the "one unpayable recipient strands everyone" shape the v1 hook
   had to grow a ledger for.
8. **First-buyer and zero-size edges.** `_buy:124` refuses `stockSpent == 0 || tokensOut == 0`; `quoteBuy:91`
   returns zeros for `maxStockIn == 0`; `capCost` cannot underflow because `x ≥ minTokenReserve` always.
9. **Donations move nothing.** Every quote reads `tokenReserve`/`realStockReserve`, never a balance; `_receive`
   and `_sendStock` (`:198-213`) check both sides of every transfer, so a fee-on-transfer stock reverts
   `UnsupportedTransfer` instead of short-paying a user.
10. **Reentrancy around the Ready→Graduated seam.** `buy()` leaves the curve's lock before calling the factory,
    `graduateCurve` carries its own `nonReentrant`, and `release()` sets `Graduated` **before** either transfer
    (`:186`), so any stock-callback re-entry hits `Closed()` or the curve's guard.
11. **`snipeSeconds` on the curve is `uint8`**, so the opening window is bounded at 255 s **by the type** —
    the bound round 1 asked for on v1's `uint32 spikeSeconds` and never got. (Its *absence of a `_setDefaults`
    check* is I-18; the type bound is the safe half.)
12. **The 99/66/33 opening schedule is exactly as documented.** `buyRateBps()` (`:79-87`) computes
    `snipeBps·(secs−elapsed)/secs` floored at `taxBps`.
13. **The curve-math identities match the docs term for term.** `V = ceil(openPriceE18·S/1e18)`
    (`HedgeFunV2Factory.sol:86`), `Tmin = floor(S(10000−saleBps)/10000)` (`:69`), `Yg = ceil(K/Tmin)` (`:72`);
    the worked example at `V2_BONDING_CURVE.md:71-75` is exact.

### Graduation

14. **It cannot be triggered twice, or on a curve that already moved.** `_graduate:139` requires `Ready`;
    `release():182-183` requires `msg.sender == factory` **and** `Ready` and writes `Graduated` before any
    effect; `graduateCurve():128-129` identifies its caller through `_curveIds`/`curves` and cannot be spoofed.
15. **Nothing about the graduated pool depends on a caller-supplied value.** The opening price is computed by
    the factory from the curve's own terminal reserves (`HedgeFunV2Factory.sol:141`), the liquidity from the
    frozen tick spacing and that price, and the LP budget from `lpBpsOfTreasury`, frozen at deploy. The
    terminal state itself is forced by the `budget == capCost` branch. None of price, depth or owner is
    nudgeable by ordering, size or donation. *(Lane 13 and the lead reached this independently.)*
16. **A graduation cannot fail on arithmetic.** `_preflight` runs the *identical* `sqrtPrice` and `liquidity`
    calls at launch on identical inputs, so an unseedable configuration reverts `Unseedable` at
    `predict`/`launch`, not at the cap.
17. **A half-failed graduation is impossible.** Every leg is one transaction; `_graduate:145` re-raises the
    delegatecall's revert data verbatim and `buy():114` re-asserts `Graduated`; `_release` and `_sendExact`
    check both sides of every transfer. The author's own rollback test goes red if the failure is swallowed.
18. **The delegatecall does not corrupt factory storage.** `executeGraduation` and everything it calls are
    memory-only or external; `SELF` is an immutable in code; slot 0 (`Ownable._owner` in the factory's frame)
    is only ever *read*, through an external call. There is exactly one `delegatecall` in `src/v2/`, with a
    fixed `encodeCall` selector. EXECUTED — owner, `publicLaunch`, `strategyCount`, `strategies[id]` and
    `curves[id]` are byte-identical across a graduation.
19. **`executeGraduation` cannot be reached any other way.** `CurveDeployer.sol:74` refuses both a direct call
    and a delegatecall from anyone but the bound factory; `deployVault` and `deploy` are `_onlyFactory`.
20. **The graduation trigger is not a free option.** EXECUTED — with 90% of the curve funded by a third party,
    the crossing buy spent 20.0 stock and an immediate dump returned 14.69.
21. **The pool cannot be pre-initialised out from under the seed.** `_onlySeed:243-249` refuses
    `beforeInitialize` while `pools[id].treasury == 0`, and once registered accepts only `liquidityVaultOf[id]`;
    `registerGraduatedWithVault` sets both in the same call with no external call between them.
22. **Graduated pools do not restart the launch taxes and cannot be made to.** `registerGraduated*` revert
    `BadConfig` unless `snipeBps == snipeSeconds == 0` (`:199`, `:206`), and `_openAndSeed:101-103` zeroes them
    before they ever get there. *(Lanes 13, 14 and 15 all reached this.)*
23. **The hook's launch-transaction exemption cannot leak into a graduated pool.** `_register:229` stores the
    `launcher_` that `registerGraduatedWithVault` passes as `address(0)`, which no `afterSwap` sender can
    equal, and `_buyRate:393-405` short-circuits on `snipeSeconds == 0` anyway.

### `V2LiquidityVault` — the locked position

24. **"Fee-only" is enforced by the code, not by the shape of the calls it happens to make.** This is the
    load-bearing conclusion and it holds. `unlockCallback:118-145` builds `liquidityDelta` from
    `int256(uint256(liquidity))` where `liquidity` is a `uint128` (mode 1) or from the literal `0` (mode 2).
    **There is no expression anywhere in the contract that can produce a negative liquidity delta.** No other
    `modifyLiquidity`, no `poolManager.burn`, no `take` outside mode 2's exact fee amounts, no owner, upgrade,
    pause or arbitrary-call surface. *(Reached independently by lane 13, lane 14 and the lead — three routes;
    a reachability fact, not a correctness proof.)*
25. **The callback cannot be driven with attacker-chosen data.** `:117` requires `msg.sender == poolManager`
    **and** `_mode != 0` **and** `keccak256(data) == _unlockHash`, which only `seed` and `collectFees` set,
    both from constants — mode 2's is the fixed `abi.encode(uint8(2), uint128(0), uint256(0), uint256(0))`.
26. **Mode 2 cannot pay out principal.** `:138-139` asserts `delta == feeDelta` and both non-negative: if
    `modifyLiquidity(0)` ever returned a principal delta it reverts rather than paying it.
27. **Only fees, and only to fixed recipients.** `token`, `stock`, `treasury` and `factory` are immutables; the
    constructor pins the currency pair to the key; the allowance is `forceApprove`'d to exactly `stockFee`,
    zeroed, and checked on both balances. `collectFees` is permissionless — anyone may *realise* the fees —
    but cannot redirect a wei. (That permissionlessness is H-1's first leg; realisation itself is safe.)
28. **Every transfer verifies the exact balance movement on both sides** (`:149-172`) — a deliberate defence
    against a fee-on-transfer or rebasing stock, which is precisely round 2's L12-2 against the v1 hook's
    shared pot. Someone carried that lesson.
29. **No third-party position can exist in a v2 pool to remove.** `_onlySeed` routes `beforeAddLiquidity`
    through `liquidityVaultOf[id]`, so the vault is the only LP. EXECUTED — a stranger's `modifyLiquidity` is
    refused both adding and removing, **and so is the factory's own**, crafted callback data is refused,
    re-seeding is `AlreadySeeded`, and `getLiquidity` is unchanged afterwards. (The dependency on the seeder
    having no removal code is I-1.)
30. **`_mode` is a real reentrancy guard.** `collectFees` has no `nonReentrant`, but `_mode` is set before
    every external call and cleared after, including across `seed`'s refunds, so a stock callback re-entering
    gets `Busy` — the author's own test asserts that exact selector.
31. **Seed cannot overspend or strand budget.** `Overspent` is checked inside the callback *and* again in
    `seed`, `_liquidity` subtracts 1 from each side before dividing to cover V4's round-up, and `max − used`
    is refunded with both-sides checks.
32. **The graduated position is full-range and genuinely two-sided.** `unlockCallback` mints at
    `minUsableTick(tickSpacing)..maxUsableTick(tickSpacing)` (`:122`) and `seed` refuses
    `liquidity == 0 || max0 == 0 || max1 == 0` (`:73`), so a single-sided graduated pool cannot be created. At
    spacing 60 the range is ±887,220 ticks, so **constant-`L` is exact** for this pool — the opposite of the
    concentrated V3 stock pools, where an analytic estimate was 2.8× wrong against an executed swap.
33. **Donations to the vault cannot inflate the LP budget or the collected fees.** Everything is sized from
    arguments or from the V4 delta, never from a balance; the author's own
    `test_predonatedVaultTokensNeverIncreaseLpBudgetOrCollectedFees` and a 1-wei over-refund mutation (15 of
    24 adversarial tests red) both hold this. (The flip side is L-5.)

### The two routers

34. **No persistent approvals, no arbitrary target, no custody.** `_curveBuy`/`_curveSell` approve exactly
    `amount` to `factory.curves(id)` and zero it in the same call; `_v4` takes its key from
    `IHedgeFunTreasury(treasury).poolKey()`, never from calldata; `_checkPath` refuses any pool that is not
    `v3Factory.getPool(current, tokenOut, pool.fee())`.
35. **Neither router can be made to spend an allowance given for something else.** The only `transferFrom` is
    `_pull`, always from `msg.sender`; the native router's approvals are set and zeroed inside one call and it
    ends every path on `wrappedNative.balanceOf(this) == beforeWrapped`.
36. **V3 callbacks can be charged once, in one direction, up to one maximum.** The callback reads pool, token,
    direction and maximum from the router's own pending swap, `delete`s the record **before** paying, and `_v3`
    then requires `deltaIn == _v3Paid == amount`. One `unlock` yields one callback.
37. **Slippage, deadline and stage bounds are complete.** The deadline is checked before anything is pulled;
    `expectedStage ∈ {ACTIVE, GRADUATED}` **and** equal to the curve's live status (so `Ready == 1` always
    reverts `StageChanged`); `minFinalOut` is absolute, never prorated, and a refund needs `allowPartialFill`.
    Removing the stage check turns 3 tests red and the revert then comes from the curve's own `Closed()` — a
    second, independent gate.
38. **Dust and partial fills.** Every leg is sized from the swap's own delta and re-checked against both
    balances, so pre-existing balances are never swept to the next caller.
39. **Path validation.** `_checkPath` forbids the strategy token anywhere in the path, forbids
    `tokenOut == start`, forbids repeated intermediates, caps at `MAX_HOPS = 3`, and requires the chain to land
    exactly on `end`.
40. **Native currency.** One `call{value:}` exists, to `msg.sender`, after an exact `withdraw` delta check;
    `receive()` refuses every sender but the wrapper; `buy` requires `msg.value == p.amountIn`; both entry
    points are `nonReentrant` and the wrapper approval is zeroed before any payout.
41. **Callback claims hold under mutation.** Removing `nonReentrant` from either router turns a purpose-built
    test red, and leaving a residual 1-wei approval turns 2 red, so `_assertTemporaryApprovalsClear` is live.

### The deployers

42. **`predict` matches what `deploy` produces, on both.** Both build the address from the same
    `creationCode ++ args` expression; `Init` and `PoolKey` are fully static structs, so `abi.encode` produces
    an identical constructor tail. EXECUTED against a real graduation.
43. **No address a launch depends on can be occupied first.** Token, treasury, curve and vault are all CREATE2
    from a bound deployer whose `deploy`/`deployVault` are `_onlyFactory`. A salt collision between curve and
    vault is additionally impossible because the initcodes differ.
44. **Kinds cannot be confused, and nobody can choose for anyone else.** `strategyKindOf` is keyed on the
    factory's own salt derivation with `msg.sender` substituted for `q.creator`; the kind is in the treasury's
    address, which is in `terms`, so a change after `predict` reverts `Restated`; `_kinds` is append-only and
    capped at 255. *(Lane 13 and lane 16 independently.)*
45. **Neither `saleBps`, `lpBps` nor the defaults can slip under a quote.** `_terms:74-79` hashes `saleBps`,
    `virtualStock` and `lpBps` on top of `super._terms`, and `_launch` re-derives it from the **actual**
    deployed treasury address, so any owner move between quote and launch reverts `Restated`. **The Safe
    cannot retroactively thin a launched pool.**
46. **`V2TreasuryDeployer._validate:133-138` correctly mirrors the treasury's own constructor check** on
    `stopBps` vs execution friction, so a rule the treasury would refuse fails with a named error. The
    documented **1.80% stop floor** is exact: 100 + 30 + 50 = 180 and the comparison is `<=`, enforced from
    both `deploy` and `predict`, and repeated in the constructor.
47. **A squatter on an unbound deployer can do nothing.** `_onlyOwner()` fails closed while
    `factory == address(0)`, and `setStrategyKind` can only select kind 0 because `_kinds.length` is 1 from the
    constructor. `makeChunks` is permissionless by design and the blobs are inert until `registerKind` names
    them.

### Treasuries

48. **The v2 treasury is inert for the whole curve era.** `health():175-178` returns `(false, 0)` while
    `hook == address(0)`, gating `_book`, `execute` and every stock trade; `buyback()` checks `hook` directly;
    `creditLiquidityFee:169` requires `msg.sender == liquidityVault`, which is zero until graduation.
49. **Stock-side LP fees are budget, never cost basis.** `creditLiquidityFee:168-172` adds to `buybackStock`
    under the treasury's own `nonReentrant`, so a token callback cannot have the fee booked as a strategy lot,
    and the vault's two-sided balance check means an over-credit cannot happen. *(The accounting is safe; what
    the budget then **does** is H-1.)*
50. **The rule's price invariant survives `health()` becoming virtual.** `HedgeFunV2Treasury.health()` calls
    `super.health()` and only **adds** a refusal, so round 1's most load-bearing clearance — at
    `bandBpsPerHour == 0` the pool is a veto and Chainlink is the price — is intact.
51. **`wire()` is still once, still factory-only, still pair-checked**, because the v2 override calls
    `super.wire(key)` first, so `NotFactory` / `AlreadyWired` / `BadPair` all still run before it touches the
    anchor — and pinning the graduation price there stops a young observation ring being the only reference
    for the first buyback. (The *comments* about it are I-4; the *justification* is I-5.)
52. **`execute()`'s ordering does what it claims.** Stop before take-profit before dip; a lot booked at price
    `p` cannot itself be stop-due or profit-due at `p` (`tp1Bps == 0` refused by the constructor,
    `tp1Bps ≥ 2·(slippage+fee)`); `!live && stopBps != 0` refuses to add risk during a closure.
53. **`_coalesceLots` preserves every lot's triggers.** It merges only on equal `cost`, equal `half` and equal
    `tp1Left == 0`-ness, and `cost` — the only field `_dueStop`/`_dueProfit` compare — is never averaged.
54. **The 128-lot cap is not a gas brick on this chain.** A full-capacity `execute()` is bounded under 10M
    gas, against a block `gasLimit` read **1,125,899,906,842,624** at block 73,774,495, 2026-09-27.
55. **Buyback kind 1 cannot reach a stock lot.** `_canAddLot()` is `false`, `book()` is replaced, `execute()`
    reverts `UseBuyback`, and the parent already reverts `takeProfit`/`stopLoss`/`buyDip` with `UseExecute`.
56. **A pre-push does not let the buyback be over-filled at the live settings.** `_clampToSpot` turns an
    over-push into a zero fill and `:474` turns a zero fill into `NotDue` **without consuming the cooldown or
    firing the spike**; the 300 bps cap sits below the 1,948 bps round-trip friction at a 10% tax (simulated:
    −0.85 USDG for the attacker). *(The `NotDue`-on-zero-fill property is what makes H-1 need a real fill —
    and triage measured that a **one-wei** fill is a real fill.)*
57. **No undue lot can ever be sold**, and **no zero-quantity lot can exist** — the eligibility test still
    reads `lots[id]` *after* every mutation, and `_canAddLot()` only ever adds a refusal.
58. **`stockEquivalentHeld()` does not double-count and does not change round 1's F-08.** The sum telescopes
    to the balance, asserted to the wei, and after an issuer `adminBurn` the `b > held` guard floors
    `unbookedStock()` at 0. (What it *does* change is L-2.)

### V2 → v1 and the deployed estate

59. **`HedgeFunFactory` is behaviourally unchanged by this PR, at the byte.** Runtime 18,929 and creation
    22,676 identical at both refs; the live factory verifies against `03ad70e` and `main` identically. Every
    factory-side change in this PR optimises away. **EXECUTED.** *(This is the happy exception and should be
    said out loud — it is also why L-3's and I-10's and I-18's structural fixes have a real cost.)*
60. **The v1 `lpFee` bound is still exactly `== 0`.** `_minLpFee() = _maxLpFee() = 0` and `d.lpFee` is
    `uint24`, EXECUTED across 1–10, 100, 500, 3000, `0x800000`, `type(uint24).max` and 0.
61. **`_onlySeed` still admits exactly one party per pool.** `liquidityVaultOf[id]` is written in one place, at
    registration, and `_register` reverts `AlreadyRegistered` on both `p.treasury != 0` and
    `poolOfTreasury[treasury_] != 0`.
62. **The v1 `unlockCallback` the v2 factory inherits is dead and fails closed.** `_seeding` is `private` in
    `HedgeFunFactory` and never set by v2's `_openAndSeed`, so `HedgeFunFactory.sol:398` always reverts
    `NotPoolManager`.
63. **The `_observe` liquidity gate behaves better on v2, not worse.** The hook writes the ring only when
    `getLiquidity(id) != 0`; a v2 pool's full-range position means that is always true, so the v1 concern about
    a swap sliding through the empty side of a single-sided seed does not arise.
64. **No v1 rule behaviour changed.** 559 tests across 19 v1 test contracts, 0 failures, **identical pass sets
    at both refs**; the only diff is fuzz gas numbers. And **the PR changed no existing test**: `test/` is
    +5,889 / −0 across 22 new files. EXECUTED.
65. **The nine live strategies cannot be moved even if v1 were redeployed.** Their hook is bound, their
    `wire()` is consumed, their pool ids are fixed, and their seeded positions are owned by the old factory
    with no withdrawal path. There is no migration primitive in `src/`, and adding one would mean a factory
    that can move a position — the thing the whole design refuses.
66. **Entries untouched by this diff and still standing byte for byte:** the hook's delta convention,
    exact-output refusal, the treasury tax exemption, the ledger's `bal >= totalOwed`, the `_distributing`
    latch, the creator-takeover timing, every observation-ring property, `TwapRing` failing closed, the
    "manipulating the mean can only tighten the bound" result, `tryPrice` failing closed on all four legs, the
    holiday rules, `bandCeiling`'s four enforcement sites, and the `StrategyToken`/router clearances.

### The documents and the test surface

67. **`docs/V2_LP_DEPTH_EXPERIMENT.md`'s every number reproduces** — the contract column by execution (LP 50%
    early dumper 13.37× with the price at 47%; LP 75% 14.91×/58%; sale 70 + LP 75 7.21×/69%; the spike sweep
    3.097 / 8.17× / 13.37× with the price at **47% in all three**), and the model column by hand. (Whether the
    *method* supports the conclusions drawn from it is M-4.)
68. **`docs/V2_MARKET_SCENARIOS.md`'s thirteen figures reproduce to the wei**, and its mechanism claims hold in
    code.
69. **`docs/V2_BATCH_OPENING_EXPERIMENT.md`** is correctly scoped: its two contract-comparable figures match
    exactly and the rest is labelled a continuous-math model with no contract counterpart.
70. **"No owner reserve withdrawal, rescue or discretionary cancellation"** is true: the complete `onlyOwner`
    surface is `setDefaults`, `setPublicLaunch`, `setBandCeiling`, `setListingGates`, `setLauncher`, `list`,
    `setSaleBps`, and on the deployer `setLpBps` and `registerKind`. **None moves funds.**
71. **"Nonzero static V4 LP fee capped at 3000"** is a bound, not a policy: `_minLpFee()` 1, `_maxLpFee()` 3000,
    both `internal pure override`. (What the bound's floor means is I-11.)
72. **Unsolicited balances cannot fund settlement or become another trader's refund.** A 1-wei over-send at
    either the factory or the vault turns 15 of 24 adversarial tests red, including the purpose-built
    "factory cannot use donations to settle".
73. **The anchor claims are genuinely tested**, including the test asserting its own precondition
    (`assertTrue(treasury.book(), …)` before asserting the anchor is unchanged); breaking the monotone ratchet
    turns 4 red. This is the one place in the adversarial document where the author states the test's own
    weakness-check and the test actually contains it.
74. **`docs/V2_DEPLOYMENT_REHEARSAL.md:22`'s caveat is the right one** — "not assertions of current control" —
    and the Safe address it cites does match the 2026-09-27 reading. **No v2 document makes a stale claim about
    v1's nine live strategies or `publicLaunch = true`.**
75. **The known test failures are the toolchain, not regressions.** At the default gas cap
    `test_holds_statefulCampaigns_…` fails `MemoryOOG` (and in another ordering with a message that *looks*
    like a rule regression); with `--gas-limit` raised it **passes on both refs**, and `InteractRuleMev` is
    **47/47 on both**, every invariant included. The third is the obsolete isolation harness control. Triage's
    own baseline at `03ad70e`: 1,410 passed / 1 failed / 51 skipped. **`foundry.toml` still sets no
    `gas_limit`, which is why this trap is still armed** — round 2's `bytecode_hash = "none"` landed and this
    did not.

---

## 7 · Findings rejected, and why

| claim | source | why it is not carried |
|---|---|---|
| The 3–4 `forge test` failures at `03ad70e` are rule regressions introduced by this PR | first reading of the suite | **Rejected, EXECUTED both ways.** With `--gas-limit` raised, `test_holds_statefulCampaigns_…` passes at `origin/main` **and** `03ad70e`, and `InteractRuleMev` is 47/47 on both. The third is the obsolete harness control. The baseline says not to report these; triage confirms and instead carries the *cause* — no `gas_limit` in `foundry.toml` — in safe-item 75 |
| The base hook is 18,362 bytes, growth +992 | `BASELINE3.md` and `00-lead-notes3.md` as first published | **Rejected** in favour of the lane-14 re-measurement the baseline itself adopted: **18,481 at `7c3c137`, growth +873**. 18,362 was round 2's figure at `0e39f69`, carried forward without re-measuring |
| A treasury-side fix has `TreasuryDeployer`'s 2,158 bytes (round 1 F-40's costing), or `HedgeFunTreasury`'s own 6,232 | round 1, carried forward | **Rejected, re-measured by triage: 1,020.** `TreasuryDeployer` embeds the treasury's initcode, so it is the ceiling. Every treasury-side v1 fix in this report is costed against 1,020 |
| A fix to `V2LiquidityVault` has the vault's own 17,464 bytes (or the curve's 17,605) | the natural first reading of `forge build --sizes` | **Rejected, re-measured by triage: 176.** `CurveDeployer` embeds both creation codes (8,944 + 8,233 of its 24,400). Lane 13 got this wrong in a first draft and measured its way out; the trap is the report's most repeatable lesson |
| `docs/V2_BONDING_CURVE.md`'s "the factory sits 143 bytes under EIP-170" | the document itself | **Rejected, re-measured by triage: 24,549 runtime, margin 27.** The same document's own size table says 27 |
| `registerGraduatedWithVault`'s missing validation is a **Low** | lane 14 (V1D-02) | **Rejected → Info.** No reachable path for a deployed (hook, factory) pair; `bind()` is once-for-good. §5.1. The disclosure half is kept as I-1 and the fix is still recommended |
| `lastEventAt = 0` is a **Medium** revenue leak | lane 15 (E-11) | **Rejected → Info.** Forgone tax on the protocol's own recipients is a parameter choice, not a leak; the "degrades the product" limb fails on lane 15's own measurement that the price lands at 47% either way; nobody extracts. §5.2. The re-arming half is not rejected — it is **H-1** |
| The negative-EV last tenth is a **Medium** | lane 15 (E-9) | **Rejected → Low (L-6).** No leak, no grief, no gain to any actor, and the author *does* disclose it. Its two Medium limbs moved to M-2 (INTC) and M-4 (the permanent non-graduating state). §5.4 |
| Four findings whose own impact lines read "no value impact" filed as **Low** | lanes 13, 14, 15 | **Rejected → Info** (I-9, I-10, I-11, I-12). The rubric defines Info as no value impact and each lane's own text says there is none. §5.4 |
| "The contract run reproduces the model to the percent", offered as corroboration | `docs/V2_LP_DEPTH_EXPERIMENT.md:30` | **Rejected as evidence** (it is carried as part of M-4). Two implementations of one closed form agreeing is a unit-consistency check. Lane 15's third implementation also agrees, which proves the same nothing |
| "Multi-user sequences preserve … **fee claims**" | `docs/V2_ADVERSARIAL_REVIEW.md:39` | **Rejected as a coverage claim** (carried as I-17): a 100% reroute of the protocol fee to the creator leaves all 24 adversarial tests green. The other three nouns in the sentence are real |
| The adversarial review's **GO**, as covering the shipped v2 | `docs/V2_ADVERSARIAL_REVIEW.md:8` | **Rejected as scoped evidence** (carried as I-15): two of the nine contracts, including the owner of every LP position, did not exist at the reviewed ref |
| "Unauthorized release, pool initialization and callbacks fail", as a statement about `V2LiquidityVault.seed` | `docs/V2_ADVERSARIAL_REVIEW.md:42` | **Rejected as a coverage claim** (carried as I-14): deleting `seed`'s `onlyFactory` leaves the whole non-fork suite byte-identically green. The property is still *true* — just untested |
| `V2LiquidityVault` might have a hidden liquidity-removal path | the hypothesis three sources set out to test | **Rejected on the code**: `modifyLiquidity` appears exactly twice, once with a `uint128` widened to `int256` and once with a literal `0`, and no expression in the contract can produce a negative delta. Safe-item 24 |
| The v2 anchor at `wire()` re-opens round 1's F-40 permanent `buyback()` brick | round 1's own watch-list, which this PR triggers | **Rejected on the sequencing**: `seed()` runs *before* `wire()` in the same atomic call, so `getSlot0` at `wire()` is the terminal curve price with balanced depth, not an empty-side extreme. What survives is the false *record* — I-4 |
| This PR implies redeploying v1 | the open question `BASELINE3.md` asks | **Rejected, three independent routes.** `HedgeFunFactory` is byte-identical at both refs and the live factory verifies against both. V2 deploys alongside v1 |
| "Twelve-plus listings" / `docs/ADDRESSES.md`'s twelve stocks | the baseline as first published, and the doc | **Rejected, EXECUTED: 18 `Listed` events, 18 distinct stocks, all enabled** — twelve at block 69,501,427 and six more (AAPL, QQQ, MSFT, TSLA, USO, GLD) at 71,689,915, read 2026-09-27 |
| Analytic constant-liquidity depth figures for the V3 stock pools | lane 15's own first pass (`depth.py`) | **Rejected by its own author and by triage**: 2.8× wrong against the executed swap on NVDA. Only executed swap numbers are used. (The estimate *is* exact for the full-range v2 pool — safe-item 32) |
| E-2's depth *levels* as durable | lane 15's table | **Not rejected, but explicitly time-boxed**: AMD's 50 bps budget moved **−36.7% in ~30 minutes** on 2026-09-27. Only the *ordering* is durable, and the one level-independent claim is INTC's |

---

## 8 · Reproducing triage's own work

```
cp -R <PR checkout at 03ad70e> …/scratchpad/triage3-scratch/w1
cd …/scratchpad/triage3-scratch/w1
~/.foundry/bin/forge test --mc AuditTriage3  --gas-limit 9999999999 -vv   # 3 passed
~/.foundry/bin/forge test --mc AuditTriage3b --gas-limit 9999999999 -vv   # 2 passed
~/.foundry/bin/forge build --sizes
```

`test/AuditTriage3.t.sol` and `test/AuditTriage3b.t.sol` use the repository's own
`test/utils/V2FactoryFixture.sol`: a genuine `PoolManager`, the production hook, factory, `CurveDeployer`,
`V2LiquidityVault` and `HedgeFunV2Treasury`; only the external stock/USDG venue and the price feeds are
mocked. The fixture's Defaults (`spikeBps 9000`, `spikeSeconds 120`, `lpFee 3000`, `minLotUsdg 5e6`,
`buybackChunkUsdg 500e6`, `bountyBps 50`) equal the **live v1** values read on chain 2026-09-27, block
73,765,417 — which is the closest available stand-in for v2 Defaults that **do not exist**.
