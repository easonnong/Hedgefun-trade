> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# The five author rounds, re-verified

Part of [external audit round 1](./00-SCOPE.md), 2026-09-21, against ref `9a291aa`.

`AUDIT.md` records five rounds of review. This document reconstructs every finding they ever raised, checks
each stated disposition against the code **as it actually stands at the audited ref**, and then asks the
question the rounds could not ask themselves: what does a review structured that way structurally miss?

## Why this was worth doing

The five rounds are good work. They are thorough, they quantify, they keep their own negative results, and
they disclose things most projects would bury. Nothing below is a criticism of their rigour.

They are, however, **one reviewer's five passes.** Every commit in this repository is authored by the same
person (24 as `0xfff`, one as `Keyu Yuan`), co-authored by Claude models (`Fable 5.1` on 59, `Opus 5 (1M
context)` on 19, `Sonnet 5` on 2), and `AUDIT.md` describes the synthesis and go/no-go as "the lead's" —
the same author. `docs/SECURITY.md` says so plainly: "No external security review has been done."

So where the rounds agree with each other, that is one model of the protocol agreeing with itself. Three
things follow, and all three showed up:

1. **A disposition can drift from what shipped.** `AUDIT.md` records FA-1/TR-6 as fixed. It is not — see
   §2.2 — and the repository's own passing test asserts the behaviour the fix was supposed to remove.
2. **Fixes from different rounds can contradict each other**, because each round reasoned in isolation. The
   repo already found one instance of this itself (round 3, the weekend brake). §3.1 is a second, and the
   two halves of it shipped **in the same commit**.
3. **A shared axiom is never tested.** §3.4 lists three the rounds treat as settled and never revisit.

## What is in here

| part | what it answers |
|---|---|
| Part 1 | the ledger: all 34 findings, their round, the author's severity, the stated disposition, and the verified state at `9a291aa` |
| Part 2 | the disposition-by-disposition verification, including the three that do not hold as recorded |
| Part 3 | what the five rounds structurally could not reach, and the severity re-grades under this audit's rubric |
| Part 4 | author round 5 (`9a291aa`) graded on its own, including reverting each fix to confirm its regression test really fails |

Findings **new in this round** are not here — they are in [`ISSUES.md`](./ISSUES.md). Where one of them
overlaps a prior finding, `ISSUES.md` says which.

---

## Part 1 — the ledger: every finding ever raised, and its stated disposition

Sources: `AUDIT.md` (the whole file, statuses at lines 10–51 included), and commit bodies of
`5d70434` (round 1 fixes), `96728ec` (round 2), `4deb193` (round 3), `e1c35bb` (round 4), `9a291aa` (round 5).
Round structure, as the repo actually records it:

| round | commit(s) | what it was |
|---|---|---|
| 1 | report in `5d70434`; fixes in `5d70434` | three parallel adversarial passes over `3e40069` (hook / treasury+oracle+calendar / factory+launch+deploy). **All IDs HK-*, FA-*, TR-\* come from here.** |
| 2 | `96728ec` | remediation wave, no new IDs raised |
| 3 | `4deb193` | remediation wave; **found one regression introduced by round 2** (no ID) |
| 4 | `1015b5c`, `864735a`, `399856a` (code) + `e1c35bb` (audit) | three parallel passes over the fee ledger, the new hook owner, and `LaunchRouter`. IDs L4-*, O4-*, R4-* |
| 5 | `3b9682f` (code) + `9a291aa` (audit) | one pass over `TradeRouter`, written two commits earlier by the same author. IDs T5-* |

**Severity column = as the author assigned it.** My re-grade under the BASELINE rubric is in Part 3, §3.5.

| ID | Round | Author's severity | Stated disposition | Verified state at `9a291aa` (Part 2) |
|---|---|---|---|---|
| **HK-1** range order exits untaxed through the sell tax and the 90% spike | 1 | High (lead's re-rate from Medium) | **fixed** (`5d70434`) | **Closes the mechanism.** `StrategyHook.sol:129,459-468` |
| **HK-2** same-second round trip poisons the 600 s mean, zero holding time | 1 | Medium | **fixed** (`5d70434`) | **Closes the mechanism.** `TwapRing.sol:51` |
| **HK-3** one unpayable recipient strands 100 % of stock revenue forever | 1 | Medium | **fixed** (`5d70434`), rebuilt round 4 | **Closes the mechanism**, twice over. `StrategyHook.sol:274-295,299-369` |
| **HK-4** zero-amount swaps through the empty side write MIN/MAX ticks free | 1 | Low | same-second half fixed r1; **rest fixed r2** (`96728ec`) | Closes it *for the ring*. `StrategyHook.sol:182-185`. **Not carried into `_noteTokenSpot`, added in r4** — §3.2 |
| **FA-1 / TR-6** calendar owner holds a live switch over every launched strategy | 1 | Medium (convergent, two passes) | AUDIT.md says **"fixed"** (r2) | **NOT fixed — narrowed and documented.** Both the halt and the force-open remain live and are asserted by the repo's own passing test. §2.2 |
| **FA-2** owner front-runs a pending launch: fee, and opening price | 1 | Medium | **fixed** (r2, `96728ec`) | Closes the two named levers. **Does not bind the fee *currency*** — §2.3 |
| **FA-3** V4 pool pre-initialisation squat | 1 | Low | **fixed** (r1) | **Closes the mechanism.** `StrategyHook.sol:129,454-457` |
| **FA-4** `setDefaults` checks far fewer bounds than the constructors | 1 | Low | **fixed** (r3, `4deb193`) | Closes the 14 bounds named. **The floor the *same commit* added is not mirrorable and is not mirrored** — §3.1, EXECUTED |
| **FA-5** non-zero `lpFee` strands LP fees in the seed forever | 1 | Low | **fixed** (r3) | Closes the parameter (`StrategyFactory.sol:261`). Not the mechanism (`donate`) — §3.4 |
| **FA-6** EIP-170 headroom 1,887 B at `runs = 1` | 1 | Low (info) | tracked, not a fix | **Worse now: 945 B.** EXECUTED, `forge build --sizes` |
| **FA-7** deploy script: `PROTOCOL`/`OWNER` default to the broadcasting EOA | 1 | Low | **fixed** (`87e2ed3`, `7b904ec`) | Closes it on chain 4663 only. `script/DeployStrategyLaunchpad.s.sol:91-121` |
| **FA-8** `v4ListingEnabled` gates `listV4`, not launches | 1 | Info | **documented, not changed** | Still true. Test `AuditFactory.t.sol:327` |
| **FA-9** look-alike treasury can self-report the real factory | 1 | Info | **documented, not changed** | Still true; front-end guidance only |
| **FA-10** inherited `renounceOwnership` bricks the factory if `publicLaunch` is off | 1 | Info | **documented, not changed** | Still true. `StrategyFactory.sol:359` |
| **FA-11** "fork-proven" tests return early and report PASS; no CI | 1 | Info | **fixed** (`086f7c0`) | Closed. `vm.skip(...)` in each fork test; `.github/workflows/test.yml` with a separate `fork` job |
| **FA-12** first buyer gets ~45 % of supply | 1 | Info | **documented**; re-measured as R4-1 | Still true, quantified in `docs/SECURITY.md` |
| **TR-1** closed-market pin: the pinner chooses the rule's price | 1 | Medium | **switched off by default, explicitly not fixed** | Off *by two defaults an owner can turn back on* — §2.4 |
| **TR-2** `book()` makes a pinned price a permanent cost basis | 1 | Low | **fixed** (r3) | Closes the *pool-priced* variant only. `StrategyTreasuryBase.sol:253`. The oracle-priced variant is open — §3.3, EXECUTED |
| **TR-3** the rule has no floor against execution cost | 1 | Low | **fixed** (r3) | **Closes the mechanism.** `StrategyTreasury.sol:41`, `StrategyTreasuryV4.sol:78` |
| **TR-4** 0.5 % deviation gate parks the rule on a quiet feed | 1 | Low | **documented, not changed** | Still true. `PoolTrader.sol:113-126` |
| **TR-5** `takeProfit` writes state after the bounty; `book()` not `nonReentrant` | 1 | Info | **fixed** (`nonReentrant` + bounty last) + stock-token assessment + daily CI | Closed as far as this repo can close it. `StrategyTreasuryBase.sol:244,285,305,327` |
| **(no ID)** r2's `isClosedByRule` fix stopped an override *shutting* the closed path on a weekend | 3 | — (self-found regression) | **fixed** (r3) | Closed. `TradingCalendar.sol:157-160`, `StrategyTreasury.sol:129-131` |
| **L4-1** sweep mid-payout reconciles against a balance short by the payment in flight | 4 | High *the day the stock gains a callback* | **fixed** | **Closes the mechanism.** `StrategyHook.sol:211-213,361-367` |
| **L4-2** treasury paid by bare transfer ahead of the credits | 4 | Medium-class | **fixed** | **Closes the mechanism.** `StrategyHook.sol:285-288` |
| **L4-3** a low-gas sweep succeeds and pays nothing | 4 | Info | **documented, not changed** | Still true; characterised by `AuditLedgerRound4.t.sol:234,267` |
| **O4-1** owner functions reachable from inside a payout | 4 | High *the day the stock gains a callback* | **fixed** | **Closes the mechanism.** `StrategyHook.sol:401,409,434` |
| **O4-2** a matured proposal never lapsed and any owner could use it | 4 | Medium-class | **fixed** | **Closes the mechanism.** `StrategyHook.sol:383,437` |
| **O4-3** the creator's veto needed a live proposal to earn the quiet period | 4 | Medium-class | **fixed** | **Closes the mechanism.** `StrategyHook.sol:423-430` |
| **O4-4** a creator contract that cannot call cannot veto | 4 | Info, by design | **documented, not changed** | Still true. `AuditOwnerRound4.t.sol:242` |
| **R4-1** what a first-buy bag does to the next buyer | 4 | Info/disclosure | **documented, not changed** | Still true; numbers in `docs/SECURITY.md` |
| **R4-2** through the router a copier could take the launcher's first buy | 4 | Medium-class | **fixed** | **Closes the mechanism.** `LaunchRouter.sol:64` |
| **R4-3** the buy-back anchor was noted before the pool's first swap | 4 | Medium-class | **fixed** | **Closes the mechanism.** `StrategyTreasuryBase.sol:339` |
| **T5-1** a V3 partial fill stranded the unspent input | 5 | (unlabelled; value loss) | **fixed** | **Closes the mechanism.** `TradeRouter.sol:116-117`. Regression genuinely fails reverted — Part 4, EXECUTED |
| **T5-2** the PoolKey came from mutable defaults | 5 | (unlabelled; permanent DoS of the router) | **fixed** | **Closes the mechanism.** `TradeRouter.sol:96-98`. Regression genuinely fails reverted — Part 4, EXECUTED |

Totals as raised: **34 distinct IDs** (22 in round 1, 10 in round 4, 2 in round 5) plus one unnumbered
self-found regression. As disposed: 20 fixed, 1 switched off by default, 10 documented-not-changed,
1 fixed-by-decision-then-partially-implemented (FA-1), 2 tracked-as-info (FA-6, FA-12).

---

## Part 2 — verifying the dispositions against `9a291aa`

### 2.1 Fixes that close the mechanism, not just the reproduction — REASONED (code), with build/test EXECUTED

I read each fix against the *mechanism sentence* in AUDIT.md, not the PoC. These close the mechanism:

| ID | fix | why it closes the mechanism and not just the PoC |
|---|---|---|
| HK-1 | `StrategyHook.sol:129` mask `0x2844`; `:459-468` `beforeAddLiquidity` → `_onlySeed` | It is not "reject a one-spacing range order"; it is **reject every adder that is not `seeder`**, and `seeder` is `IBoundDeployer(msg.sender).factory()` fixed at construction (`:130`). The factory has exactly one `modifyLiquidity`, inside `unlockCallback` gated on `_seeding` with a positive delta (`StrategyFactory.sol:417-429`). Every untaxed-exit shape — range order, full-range, JIT in front of `buyback()` — dies at the same line. `beforeRemoveLiquidity` is left reverting `HookNotImplemented` and the flag is *not* taken, which is correct: with no third party able to add, there is nothing to remove. |
| HK-2 | `TwapRing.sol:51` `if (nowTs == last.ts) { r.obs[r.index].tick = tick; return; }` | The bug was "the first write of a second wins". The fix makes the *last* write of a second win, which is V3's rule. It is the mechanism, not the 6 % round trip. |
| HK-3 | `StrategyHook.sol:274-295` + ledger `:299-369` | Round 1 paid the treasury first and `try`ed the rest; round 4 replaced that with credit-then-pay plus a role-keyed ledger and `_reconcile` write-down. The invariant that actually matters — *no recipient's failure can stop another's payment, and no undelivered cut is re-split* — is enforced structurally: new revenue is `bal - totalOwed` (`:277`), `_pay` moves the ledger before the token and restores it on failure (`:361-367`), `payStock` is callable only from inside a payout (`:448-451`). |
| FA-3 | `beforeInitialize` + `_onlySeed` (`:454-457`) | V4 refuses a codeless hook's silence, so the pool key cannot be occupied before the hook exists, for any symbol, not just the PoC's. |
| FA-4 | `StrategyFactory.sol:252-262` | Mirrors 14 constructor bounds. See §3.1 for the one it cannot mirror. |
| FA-5 | `StrategyFactory.sol:261` `if (d.lpFee != 0 …) revert BadRequest()` | The parameter can never be non-zero again, on any launch. See §3.4 for what this does *not* close. |
| TR-3 | `StrategyTreasury.sol:41`, `StrategyTreasuryV4.sol:78` | `tp1Bps, dipBps ≥ 2·(maxSlippageBps + poolFeeBps)` in **both** constructors, reading the pool's own fee. Mechanism, not the 1 bp PoC. |
| L4-1, L4-2, O4-1, O4-2, O4-3 | `StrategyHook.sol:211-213, 285-288, 361-367, 383, 401, 409, 423-430, 434, 437` | Each is a structural reordering or a new invariant, not a guard against the specific reproduction. `AuditOwnerRound4.t.sol` also carries a stateful invariant over the ledger (`owedProtocol+owedCreator+owedTreasury == totalOwed`, and `balance ≥ totalOwed`). |
| R4-2 | `LaunchRouter.sol:64` `if (q.creator != msg.sender) revert NotYourLaunch()` | Mechanism. **Accidental bonus, REASONED:** it also blocks a re-entrant `launch()` from a stock token with a transfer callback, because inside the re-entry `msg.sender` is the token and `q.creator` is not. `LaunchRouter` has no `nonReentrant` of its own. |
| R4-3 | `StrategyTreasuryBase.sol:339` `if (observationCount() == 0) return` | Mechanism, and it happens to also cover the launch-instant case of §3.2. |
| T5-1, T5-2 | `TradeRouter.sol:116-117, 96-98` | See Part 4. |
| FA-7 | `script/…:91-121` | On chain 4663 `OWNER`, `PROTOCOL` and the calendar owner must each be set, differ from the broadcaster, have code that is not an EIP-7702 designator, and answer `getThreshold()`/`getOwners()` with threshold ≥ 2. **Bounded:** the guard is against a mistake, as the script's own comment says; any contract can answer those two calls, and it is inert on any chain id but 4663. |
| FA-11 | `.github/workflows/test.yml`; `vm.skip(vm.envOr("RH_FORK",0)==0, …)` in each fork test | EXECUTED: `grep -rn "test_BUG_" test/` returns **0 function definitions** (2 comments only), so the repo's own rule 4 ("never leave a `test_BUG_*`") holds. |
| TR-5 | `StrategyTreasuryBase.sol:244` (`book()` `nonReentrant`), `:285, :305, :327` (bounty last) | Plus `test/StockTokenFork.t.sol` pinning today's implementation and a daily CI cron. This is as closed as an unpatchable contract can get against a beacon-proxy token. |

**Build/test state I measured (EXECUTED, 2026-09-21, forge 1.8.1 at `~/.foundry/bin`):**
`forge build --sizes` clean — StrategyFactory **23,631 / 945 B margin**, StrategyHook 13,722, StrategyTreasury 17,204,
StrategyTreasuryV4 14,532, TradeRouter 5,668, LaunchRouter 5,995, TreasuryDeployer 22,418 (**2,158 B margin**).
`forge test --no-match-path 'test/*Fork*'`: **619 passed, 1 failed** — see §3.7. BASELINE.md records
620/0/1 for the same ref; CI pins `FOUNDRY_VERSION: v1.5.0` and I ran 1.8.1, which is the difference.

### 2.2 FA-1 / TR-6 — AUDIT.md says "fixed". It is not. — EXECUTED

`AUDIT.md:39` lists blocker 5 (FA-1/TR-6) among the items "**fixed** on `fix/audit-pre-launch-2`".
Blocker 5's own row (`AUDIT.md:435`) offered three options: renounce calendar ownership, have `list()` refuse an
owned calendar, or **accept it and correct the README**. What shipped (`96728ec`) is the third option plus a
narrowing. Calling that "fixed" in the status header, while the row says it is a decision, is the single largest
discrepancy in the ledger.

What is reachable today, and under what settings:

1. **Halt.** `TradingCalendar.setOverride(day, 1)` → `dateClosed` true → `PriceOracle.tryPrice()` returns
   `(false, 0)` (`PriceOracle.sol:51`) → `health()` false in both treasuries → `takeProfit`/`buyDip`/`stopLoss`
   revert `Unhealthy`, `book()` returns false. Round 3 extended this to weekends via `isScheduledClosure`
   (`TradingCalendar.sol:157-160`), so the halt now works **seven days in seven**, including on the band path.
   Round 3 made the owner's brake *stronger*, which is the right trade, but it is still an unbounded switch over
   every strategy priced through that calendar, forever, with no timelock and no expiry.
2. **Force open.** `setOverride(day, 2)` on a weekend → `isClosed` false → `tryPrice()` serves **Friday's frozen
   Chainlink print** as a live price, behind the 48 h cap (`PriceOracle.sol:42`) and the deviation gate. The rule
   then trades on a Saturday at Friday's close. **EXECUTED:** `forge test --mt
   test_audit_calendarOwnerCanHaltOrReopenEveryLaunchedStrategy` passes at `9a291aa`; its part (b)
   (`test/AuditFactory.t.sol:209-217`) asserts exactly this, ending
   `assertTrue(ok, "the launched treasury trades on a Saturday at Friday's close")`.
3. **The contract comment added by the fix is false.** `TradingCalendar.sol:15-16` (introduced in `96728ec`):
   *"an override can only ever stop trading, never widen what trades"*. `PriceOracle.sol:51` consults
   `isClosed`, which honours override 2 — so an override **does** widen what trades. `docs/SECURITY.md`
   contradicts itself on the same page: the owner table's left column admits *"force a day open … the live-feed
   path then applies"*, while the section heading four paragraphs later reads **"The calendar owner can halt and
   only halt"**. The narrow claim that survives is: *an override cannot open the pool-only closed-market path*
   (true — `StrategyTreasury.sol:129-131` asks `isScheduledClosure`).

**Verdict:** FA-1 is **open and disclosed**, not fixed. Under the BASELINE rubric it is **Medium** (a disclosed
risk; the disclosure understates it in two named places), not the **High** it would be if `docs/SECURITY.md`
alone were read, because the "It can" column does state the force-open power.

### 2.3 FA-2 — fixed for the two levers named; the fee *currency* is a third — REASONED

`StrategyFactory.sol:365`: `if (d.launchFeeAmount > q.maxFee || L.openPriceE18 != q.expectedOpenPriceE18) revert Restated();`

I enumerated every launch input and asked which are *not* in a constructor's arguments (the property FA-2 is
about). The full set is `{launchFeeCurrency, launchFeeAmount, openPriceE18, bandCeiling[stock], publicLaunch,
listing.enabled}`. Of these:
- `launchFeeAmount`, `openPriceE18` — **bound** by the fix.
- `bandCeiling`, `publicLaunch`, `enabled` — a change makes `launch()` revert **loudly** (`BadRequest`,
  `NotOpen`, `NotListed`); no silent loss.
- **`launchFeeCurrency` — unbound.** `maxFee` pins the number, not the asset. `docs/SECURITY.md` states
  *"`Request.maxFee` and `Request.expectedOpenPriceE18` exist so that the owner cannot restate the fee … underneath
  a pending launch"*, which is stronger than what the code does.

**How far this actually goes (the honest bound).** I worked every flip:
`Usdg→Stock`, `Stock→Usdg`: USDG is 6 decimals, every stock 18, so "25" becomes either 25 wei of a share
(≈2.5 × 10⁻¹¹ shares — the *owner* loses) or 10¹² USDG (the creator cannot pay — loud revert).
`*→Native` / `Native→*`: `_chargeLaunchFee` requires `msg.value == d.launchFeeAmount` or `msg.value == 0`
(`StrategyFactory.sol:379-386`) — loud revert either way.
`None→Usdg/Stock`: takes the fee where the creator agreed to none, but only up to `maxFee`, and only if the
creator happens to hold a standing approval for that asset. Under the shipped defaults
(`script/…:180-181`: Usdg / 25e6) that is 25 USDG.
Launching through `LaunchRouter` is immune: `_fundFee` reads `factory.getDefaults()` and `factory.launch()`
re-reads `defaults` in the same transaction (`LaunchRouter.sol:65-67`), so they cannot disagree.

**Verdict: Info/Low**, not a funds finding — but the SECURITY.md sentence is an overclaim, and the *class*
FA-2 named ("inputs in no constructor's args") was enumerated one member short.

### 2.4 TR-1 — "switched off by default": exactly which defaults, and who can turn them back on — REASONED

Closure trading is off behind **two** independent gates, both owner-settable, both future-launches-only:

1. `StrategyFactory.setBandCeiling(stock, bps)` (`:269-272`), hard-capped at 200, **zero for every stock until
   the Safe raises it**. `launch()` refuses `q.bandBpsPerHour > bandCeiling[q.stock]` (`:364`).
2. The creator's own `q.bandBpsPerHour`, frozen into `Params` at birth. With 0,
   `StrategyTreasury._priced` short-circuits at line 97 and the band code is unreachable for that treasury,
   byte for byte.

So the *statement that holds* is: **a treasury launched today can never trade a closure**, because its band is
immutable at 0. The statement that does **not** hold is "the protocol cannot turn TR-1 on": one Safe transaction
(`setBandCeiling`) plus one creator who asks for it, and every launch after that point is permanently exposed —
with no way to patch it, ever. `docs/SECURITY.md` states this honestly ("Raising a ceiling is a Safe transaction,
reaches future launches only"). The residual risk is **process, not code**: the ceiling is per-stock and depth is
"a property of today while a launch is forever", which the doc also says. I found nothing that re-opens the band
without a `setBandCeiling` call. **Confirmed off; confirmed re-enablable; the disclosure is accurate.**

### 2.5 Dispositions I could not fully verify, and what I would need

| item | why not verifiable here | what I would need |
|---|---|---|
| AUDIT.md's 43 round-1 PoCs "all re-run by the lead" | the auditor worktrees under `.claude/worktrees/` were never committed (`AUDIT.md:479,492`). Only the *inverted* regression tests survive. | the original `AUDIT_FACTORY.md` / `AUDIT_HOOK.md` / `AUDIT_TREASURY.md` and the `test/AuditHook*.t.sol` files as they were at `3e40069` |
| "every regression test confirmed to fail with its fix reverted" (rounds 1–4) | I executed this for round 5 only (Part 4). Rounds 1–4 assert it in commit bodies with no artifact. | re-revert each fix in a scratch tree and re-run; ~12 separate reverts. Round 5 held, which is weak positive evidence for the process |
| the TR-1 attacker numbers (+3,311 USDG on an AMD-sized pool, the 6.7 × pool fee × D30 break-even) | the harness that produced them is in an uncommitted worktree; the D30 table is a 2026-09-20 chain read | re-derive against live pool depth |
| the chain facts the findings are sized against (35 of 194 feeds, 25 listable, D30 table) | read on 2026-09-20; BASELINE re-reads the chain on 2026-09-21 and already finds `docs/DEPLOYMENT.md`'s Safe description stale (2-of-4, nonce 1, vs the doc's 2-of-3, nonce 0) | a fresh survey |
| the stock token's behaviour | `docs/STOCK_TOKEN_ASSESSMENT.md` + `test/StockTokenFork.t.sol` pin *today's* beacon implementation, upgradeable by one code-less address with no timelock | nothing this repo can do; the daily CI cron is the right answer |

---

## Part 3 — what the five rounds structurally could not find

### 3.1 FA-4's mirror and TR-3's floor shipped in the same commit and contradict each other — **EXECUTED**, Info

**Location** `StrategyFactory.sol:252-262` (`_setDefaults`) vs `StrategyTreasury.sol:41` and
`StrategyTreasuryV4.sol:78`. Both landed in `4deb193`.

FA-4's fix is described in `docs/SECURITY.md` as *"`setDefaults` mirrors every constructor bound. Because a
constructor's revert reason does not survive CREATE2."* TR-3's fix, in the same commit, added a constructor
bound that **depends on a creator input**: `tp1Bps, dipBps ≥ 2·(maxSlippageBps + poolFeeBps)`. `maxSlippageBps`
is a *default*; `tp1Bps` is in the `Request`; `poolFeeBps` comes from the listed pool. `_setDefaults` therefore
cannot mirror it and does not — and neither does `launch()` pre-check it (`StrategyFactory.sol:358-374`).

Raising `maxSlippageBps` from 100 to 300 (both inside every bound `_setDefaults` checks, and both inside
`MAX_SLIPPAGE_BPS`) moves the floor from 260 bps to 660 bps and makes every pending launch with
`tp1Bps < 660` die as an opaque `require(a != address(0), "treasury deploy")` — **precisely the FA-4 symptom**,
reintroduced by its sibling fix.

**EXECUTED:** `test_probe_raisingMaxSlippageBricksAPendingLaunchWithAnOpaqueReason`
(`scratchpad/prior-scratch/hf/test/PriorRoundsProbe.t.sol`) launches the shipped request successfully, then
`setDefaults` with `maxSlippageBps = 300`, then `vm.expectRevert(bytes("treasury deploy"))` on the identical
request and salt. Passes.

**Impact** No funds. A creator who has spent 16 k hashes mining a salt gets an unnamed failure, and must
diff nineteen defaults to find out why — the exact cost FA-4 was raised to remove. **Loser:** the creator (gas
and time). **Fix:** move the floor check into `launch()` with a named error, or state in SECURITY.md that the
mirror covers default-only bounds. Costs ~40 bytes of the factory's remaining 945.

**Why no round found it:** round 3 fixed both in one commit and each pass verified its own finding's test.
No round re-read FA-4's *claim* after TR-3 changed what "every constructor bound" means.

### 3.2 HK-4's lesson was never carried into `_noteTokenSpot`, added two rounds later — REASONED, Info

**Location** `StrategyHook.sol:182-185` (HK-4's fix) vs `StrategyTreasuryBase.sol:334-345` (`_noteTokenSpot`,
introduced with the buy-back anchor and guarded in round 4 by R4-3).

HK-4 established: *the seed is single-sided, so a swap can slide through the empty side to MIN/MAX moving no
tokens and paying no tax; that is not a price anyone can trade at.* The fix was applied to exactly one reader of
`getSlot0` — the ring. `_noteTokenSpot` reads `getSlot0(poolKey.toId())` with **no liquidity check**
(`:340-344`), and it is a **one-way ratchet** (`buybackAnchorSqrtP` only ever moves toward "token cheaper").
A single observation at the empty-side extreme would pin the anchor at MIN/MAX sqrt price for the life of the
strategy, and `_buybackLimitSqrtP`'s anchor branch (`:473-481`) would then clamp every future buy-back to
`sqrtP ± 1` — `buyback()` reverts `NotDue` forever on that branch.

**It is not reachable today, and the reasons are all accidental.** I chased it to the end:
- R4-3's guard (`:339`, `observationCount() == 0 → return`) covers the launch instant, which is HK-4's own
  reproduction window.
- After the first in-range swap, returning to the empty side requires selling back **more tokens than the pool
  ever issued**. It cannot happen: `StrategyToken` has no mint (`StrategyToken.sol:10`), the hook's token-side
  take is burned (`StrategyHook.sol:253`) and the treasury burns what it buys back
  (`StrategyTreasuryBase.sol:388`). Circulating supply is monotonically decreasing.
- The anchor branch is itself near-dead: `TwapRing.meanTick` can only fail to serve 600 s in the first
  600 s of the pool's life (a full 1,024-slot ring spans ≥ 1,023 s at one write per second, so the window is
  always inside it once filled), and `buybackStock` is ~0 then.

**Why this is still worth writing down.** Three separate accidents defend it, none of them stated as an
invariant anywhere, and one of them (`observationCount()`) was put there for an unrelated reason. The line
`docs/SECURITY.md` offers — *"It also refuses to record a tick with no liquidity behind it"* — is true of the
ring and false of the anchor. Any future change that mints a strategy token, adds a second liquidity path, or
seeds the anchor at `wire()` re-opens it into a permanent brick of `buyback()`. **Fix:** one line,
`if (poolManager.getLiquidity(poolKey.toId()) == 0) return;` at `StrategyTreasuryBase.sol:340`.

### 3.3 `book()` is unpaid, has no deadline, and fixes a permanent number — **EXECUTED**, Low

**Location** `StrategyTreasuryBase.sol:244-258` (`book`/`_book`), `:263` (the only automatic trigger),
`:294` (`stopLoss`'s comparison against `L.cost`), `:281` and `:302` (the bounties).

TR-2 closed the case where a *pinned pool* sets a lot's cost basis (`:253`, `if (pricedOffPoolOnly()) return false`).
Nobody examined the other half of the same sentence — *a lot's cost is permanent* — on the **oracle** path.

- `book()` pays **no bounty**. It is the only rule function that does not: `takeProfit` pays `bountyBps` of the
  profit (`:281`), `stopLoss` pays `bountyBps` of the proceeds (`:302`), `buyDip` pays `bountyBps` of the spend
  (`:323`), `buyback` pays `bountyBps` of what it burned (`:385`). So **nothing pays anyone to book promptly.**
- The tax stock accrues continuously and stays unbooked until someone volunteers. Whoever calls `book()` chooses
  which healthy Chainlink print becomes the lot's permanent cost — anywhere in the range the feed visits in
  between. No manipulation is required; the price is honest.
- The only *automatic* booking is `_book()` inside `takeProfit` (`:263`), which by construction runs at a price
  that just cleared a take-profit trigger — i.e. a local high. So the default behaviour of an unattended
  strategy is to cost new lots at highs.
- A high basis is what arms `stopLoss` (`:294`, `p·1e4 > L.cost·(1e4 − stopBps)` → `NotDue`). With
  `stopBps` configured, a lot booked at a peak is stopped out on a normal retrace that a fairly-booked lot would
  survive — and the caller who books high and then stops it is paid `bountyBps` of the **whole** sale proceeds,
  not of profit.

**EXECUTED:** `test_probe_theCallerOfBookChoosesTheLotsPermanentCostBasis` — the same 100 stock, the same
treasury (`off`, `bandBpsPerHour = 0`, i.e. the audited Chainlink-only path), booked at two moments an hour
apart on honest feeds, produces `cost = 100e18` or `cost = 130e18`. The lot is identical in every other respect.

**Conditions** (1) tax stock is sitting unbooked — **status: normal, it is the default state**;
(2) the caller is first to call `book()` — **UNMEASURED off-chain competition, but nobody is paid to compete**;
(3) for the loss half, `stopBps != 0` — **status: creator's choice, `0` in the deploy script's
`_req` shape but `2000` in the repo's own test harness; UNMEASURED what creators will pick.**

**Impact** **Loser: the treasury.** *Certain gain* to the caller: `bountyBps` (≤ 200, shipped 50) of an inflated
profit or of a whole stopped lot. *Option gain*: the reclassification of principal into `buybackStock` changes
what the treasury holds versus burns, which only becomes a loss if the price later moves. Not theft; a steerable
number the protocol believed was not steerable.

**Fix** Pay `book()` a bounty like every other rule call (it is the cheapest of them), or cost a lot at the
price at which the tax *arrived* rather than at which someone noticed — the hook knows that moment. Neither
fits without touching immutable treasury bytecode, so it is a pre-launch decision.

**Why no round found it:** TR-2 was framed as "a *pinned* price must not become a cost basis", and round 3 fixed
exactly that. The generalisation — *any* permissionless writer of a permanent number picks it — was never stated,
and round 4 and 5 were scoped to the hook owner, the ledger and the two routers.

### 3.4 The three axioms nobody tested

**(a) "The seeded liquidity is unremovable."** I re-derived it rather than trusting AUDIT.md, and it holds:
V4 keys a position to `msg.sender`; the factory's only `modifyLiquidity` is at `StrategyFactory.sol:423` inside
`unlockCallback` gated on `msg.sender == poolManager && _seeding` (`:418`) with `int256(liq) > 0`; `_seeding` is
set only around one `unlock` in `_openAndSeed` (`:408-410`) and `launch()` is `nonReentrant`; **no attacker code
runs inside that window** (the hook is freshly CREATE2'd from the factory's own initcode, the token is a plain
OZ ERC20, and the seed is single-sided so the issuer's stock is never touched); dust is burned (`:411-412`).
`test_fork_liquidityIsUnremovable_byAnyone` (`test/StrategyFork.t.sol:125`) is real and correctly `vm.skip`s
without `RH_FORK=1` — **but note what it proves**: one `Rugger` calling `modifyLiquidity` with the exact ticks,
plus four guessed selectors (`removeLiquidity`, `withdrawLiquidity`, `rug`, `pull`) against the factory. That is
a spot check, not an enumeration; the real proof is the `_seeding` latch, which the test does not exercise.
**Unremovable ≠ untouchable:** the hook takes no `BEFORE_DONATE`/`AFTER_DONATE` flag, so once the price is inside
the seed range anyone may `poolManager.donate` into it, and those tokens are stranded forever in exactly the way
FA-5 described. FA-5's fix pinned the *parameter* (`lpFee == 0`) and left the *mechanism* ("value that reaches
the seed position is gone") open. Self-harm only — **Info**.

**(b) "Chainlink is the only price."** True as a fact about the chain, and `PriceOracle` fails closed on
calendar-shut, `oraclePaused()`, zero/negative/future/over-age rounds (`PriceOracle.sol:51-57,82-87`). Two
consequences no round stated: there is **no secondary source to disagree with a wrong-but-signed print**, and
`lastPriceAt()` (`:67-75`) deliberately drops the calendar *and* the stock-age gate, keeping only the USDG-leg
age check. That is exactly the number the band path trades off (`StrategyTreasury.sol:121`), so with the band on,
**a stock feed that is stuck rather than closed is indistinguishable from a weekend** — the calendar is doing all
the work. Disclosed in substance; the asymmetry between the two `_read` calls in `lastPriceAt` is not.

**(c) "A bounded owner power is a safe owner power."** The bound on `setProtocol` is "it moves only the
protocol's own money". It is enforced by role-keyed ledger lookups (`StrategyHook.sol:356-358`), which means
**`setProtocol(x)` also hands `x` everything already accrued and unpaid to the old protocol** — stated in
SECURITY.md, and correct by design, but it makes the power instant and retroactive with no delay while the
creator-side equivalent has 14 + 14 days and a veto. And the "and nothing else" in
`test_audit_theOwnerReachesTheTwoRecipientsOfALaunchedHook_andNothingElse` is proven by snapshotting **8 hook
getters and 6 treasury getters** (`test/AuditFactory.t.sol:289-296`), not by enumerating the hook's surface.
It omits `owedProtocol`/`owedCreator`/`owedTreasury`/`totalOwed`, `lastEventAt`, `pendingCreator*`, and it does
not notice the **third** owner-reachable function, `vetoCreator()` (`StrategyHook.sol:425`, `msg.sender ==
owner()` branch). See §3.6.

### 3.5 Severity re-grades under the BASELINE rubric

The author graded round 1 against "can we fix it before mainnet". BASELINE grades the **state of a launched
strategy**, immutable and unpatchable. Two re-grades follow, both upward, plus one downward:

- **FA-1 / TR-6 — author Medium, BASELINE Medium, but the *disposition* is mis-stated.** The rubric's
  Medium includes "a disclosed risk whose disclosure materially understates it". `TradingCalendar.sol:15-16`
  and `docs/SECURITY.md`'s "The calendar owner can halt and only halt" heading both understate it, while the
  same doc's table states it correctly. It sits at the Medium/High boundary purely because the table is honest;
  had only the heading and the contract comment existed, rubric bullet 3 ("the protocol Safe can do something
  docs/SECURITY.md explicitly promises it cannot") would make it **High**.
- **HK-4 — author Low, and Low is right for the ring, but the finding was scoped to the ring.** Under a rubric
  that grades permanence, "a free write of an untradeable price into a permanent one-way ratchet" is Medium;
  it is Info here only because §3.2 shows it unreachable, and only by accident.
- **TR-2 — author Low, and the *fixed* half is closed. The unfixed half (§3.3) is a separate Low** that was
  never raised, because TR-2's title contained the word "pinned".
- **FA-6 — author Low/info; it has got worse**, 1,887 B → **945 B**. Every finding in this audit whose fix
  touches `StrategyFactory` now competes for those 945 bytes, and `TreasuryDeployer` has only 2,158 B of
  *initcode-carrying* runtime left. This is a constraint on remediation, and it should be stated in the
  go/no-go rather than as a finding.

### 3.6 Claims asserted but not evidenced by the test named

I read every named test body rather than trusting the name.

| claim (source) | named test | what the test actually asserts |
|---|---|---|
| "Nothing the owner does *on the factory* reaches a launched strategy" (`docs/SECURITY.md`) | `test_audit_nothingTheOwnerDoesReachesALaunchedStrategy` (`AuditFactory.t.sol:224`) | **Real and strong.** Changes all 19 defaults, re-lists to a hostile oracle pricing the stock at 1 USDG, closes `publicLaunch`, disables V4, transfers ownership, re-lists again — then compares a keccak snapshot of 10 hook getters + 7 treasury getters and the token supply, and confirms `health()` still answers from the birth oracle. **Scope is exactly what the sentence says: the factory.** The *calendar* — owned by the same Safe — is a different contract and is where the launched strategy is reachable (§2.2). The doc splits these correctly; a reader skimming does not. |
| "what it can do *on a hook* is those two functions and nothing else" (`docs/SECURITY.md`) | `test_audit_theOwnerReachesTheTwoRecipientsOfALaunchedHook_andNothingElse` (`AuditFactory.t.sol:283`) | **Under-evidences its own name.** It exercises `setProtocol`, `proposeCreator`, `vetoCreator` by the creator, the 180-day quiet period, an ownership handover mid-proposal, O4-2's proposer-binding and `Expired` — all genuinely good. But "nothing else" is a snapshot of **8 hook getters and 6 treasury getters**, with no enumeration of the hook's function set and no coverage of the four ledger variables. It also never notices that `vetoCreator()` (`StrategyHook.sol:425`) is a **third** function the owner may call, which the prose admits in passing but the table does not list. |
| "the permanence proof" (`docs/SECURITY.md` rule 5) | `test_fork_liquidityIsUnremovable_byAnyone` (`StrategyFork.t.sol:125`) | **Real, correctly skipped off-fork, and narrower than its name.** One `Rugger` with the exact ticks + four guessed selectors. It does not touch the `_seeding` latch, which is what actually makes the claim true. See §3.4(a). |
| "The first buy pays exactly what a stranger's buy pays" | `test_theFirstBuyPaysExactlyWhatAStrangersBuyPays` (`LaunchRouter.t.sol:56`) | Exists. |
| "`setDefaults` mirrors every constructor bound" (`docs/SECURITY.md`) | — (no test named) | **False as written** — §3.1, EXECUTED. |
| "an override can only ever stop trading, never widen what trades" (`TradingCalendar.sol:15`) | — (no test named) | **False** — §2.2, EXECUTED via the repo's own passing test. |
| "It also refuses to record a tick with no liquidity behind it" (`docs/SECURITY.md`) | — | True of `TwapRing`, false of `_noteTokenSpot` — §3.2. |

### 3.7 The suite is red at HEAD on a non-pinned toolchain — **EXECUTED**, Info

`forge test --no-match-path 'test/*Fork*'` at `9a291aa` with forge **1.8.1**: **619 passed, 1 failed**.
`test_seedRangeIsSingleSided_tokenIsCurrency0` (`test/InteractFactory.t.sol:826`) fails
`revert("no ordering")` at `:862`. I confirmed it fails with my own probe file removed, and that `src/`,
`test/` and `foundry.toml` are byte-identical to the target.

Cause: the test brute-forces 200 symbols looking for one whose **CREATE2 token address** sorts on the wanted
side of the stock (`_reqWithOrdering`, `:855-862`). That address depends on `StrategyToken`'s creation code,
which carries compiler/toolchain metadata. CI pins `FOUNDRY_VERSION: v1.5.0`; BASELINE measured 620/0/1.

**Why it matters beyond the red mark:** the *both-orderings* coverage that backs the single-sided-seed and
USDG-ordering claims — the bug class `CLAUDE.md` says "has been shipped twice" — is supplied by a brute-force
address search. Here it fails loudly, which is the safe direction. A search that found a *different* subset
would silently reduce coverage instead. **Fix:** derive the ordering deterministically (mine the stock mock's
address, as `_mineToken` already does) rather than searching the token's.

---

## Checked and found safe

Each with the line that makes it so. This section is as important as the findings.

- **`LaunchRouter` derives the PoolKey from `factory.getDefaults()` — the exact shape of T5-2 — and is safe,
  by atomicity.** `LaunchRouter.sol:65` reads the defaults and `:67` calls `factory.launch` in the same
  transaction; `setDefaults` is `onlyOwner` and `launch` is `nonReentrant`, so the two cannot disagree.
  **Safe for a different reason than the fix round 5 applied**, and nothing records that.
- **`TradeRouter._checkPool`** (`:100-102`) resolves the caller's pool through `v3Factory.getPool(usdg, stock,
  pool.fee())` and compares identity, so a posing pool cannot reach the callback. Covered by
  `test_holds_callbacksFromOutside_andPosingPools_areRefused` across three fee tiers.
- **`TradeRouter.uniswapV3SwapCallback`** (`:121-124`) is gated on `msg.sender == _v3Pool`, a latch open only
  inside `_v3` (`:107,110`), and `buy`/`sell` are `nonReentrant`. `test_holds_strangerWithControlMidSwap_
  latchOpen_cannotMoveAnyonesApproval` drives a stock token with a `_update` callback through every door and
  asserts the selector each one answers with. This is the best-built test in the repo.
- **The `_seeding` latch** (`StrategyFactory.sol:408-418`) — no attacker code executes inside the one window in
  which the factory may add liquidity. §3.4(a).
- **Circulating strategy-token supply is monotonically non-increasing** — no mint after construction
  (`StrategyToken.sol:10`), token-side tax burned (`StrategyHook.sol:253`), buy-backs burned
  (`StrategyTreasuryBase.sol:388`). This is the unstated invariant that makes the empty side unreachable
  (§3.2) and it is not asserted anywhere.
- **`owner()` reverting does not brick the hook.** `test_holds_nothingButTheOwnerFunctionsDependsOnOwner`
  (`AuditOwnerRound4.t.sol:256`) mocks the factory's `owner()` to revert and shows `afterSwap`, `sweep`,
  `claim`, `claimFor` and the creator's `vetoCreator` all still work.
- **A renounced factory kills both hook powers.** `test_holds_renouncedFactory_killsBothPowers_
  evenWithAMaturedProposal` (`AuditOwnerRound4.t.sol:271`).
- **Ledger arithmetic cannot underflow.** `_reconcile` (`StrategyHook.sol:343-351`) returns with
  `totalOwed ≤ bal` in every branch (the `bal ≥ totalOwed` early return, or a pro-rata write-down whose parts
  each floor below `bal`), so `bal - totalOwed` at `:277` is safe; `totalOwed -= amount` at `:366` is preceded
  by `amount = p + c + t` drawn from the same three variables.
- **Round 3's `isScheduledClosure` regression is closed in both directions.**
  `TradingCalendar.sol:157-160` requires `override_[day] == 0 && dateClosedByRule(day)`, so
  `setOverride(day, 1)` halts on a weekend and `setOverride(day, 2)` cannot open the band path on a live day.
  `test_halt_stopsTheRuleOnAWeekdayAndOnASaturday_andStopsNothingElse` — EXECUTED, passes.
- **No `test_BUG_*` function remains** (EXECUTED: `grep -rn "test_BUG_" test/` → two comments, zero
  definitions), so `docs/SECURITY.md` rule 4 holds.
- **Fork tests skip rather than vacuously pass** (`vm.skip(vm.envOr("RH_FORK", uint256(0)) == 0, …)`), and CI
  runs them in a separate job. FA-11 is genuinely closed.

---

## Part 4 — grading `9a291aa` (round 5) on its own

`git show 9a291aa` touches 4 files: `src/str/TradeRouter.sol` (+28/−10), `test/AuditTradeRouter.t.sol` (+253),
`docs/REFERENCE.md` (1 line), `test/TradeRouterFork.t.sol` (1 line). **No other `src/` file changes.**

### T5-1 — the V3 hop is now all or nothing

`TradeRouter.sol:116-117`:
```
uint256 spent = uint256(zeroForOne ? a0 : a1);
if (spent != amountIn) revert PartialFill(spent);
```
**Does it close the mechanism?** Yes, for the stated mechanism. The V3 hop is the only balance-blind leg in the
contract: `_v3`'s `out` is derived from the swap delta, not from a balance, so unspent input had nowhere to go.
Both call sites route every unit of input through `_v3` (`:72` for `buy`, `:86` for `sell`), so the single check
covers both directions. The sign convention is right in both orderings (`a0` when `zeroForOne`, `a1` otherwise
— for an exact-input V3 swap the input-side delta is positive and equals what the callback was asked for).

**What it does not close, and should be said:** the *V4* hop is still allowed to fill short
(`:148`, `if (owedIn < amountIn) safeTransfer(refundTo, amountIn - owedIn)`). That is not a loss — the refund is
real and `test_holds_v4PartialFill_refundsTheUnabsorbedTokensToTheCaller` checks the arithmetic — but on `buy`
the refund arrives as **stock**, not the USDG the caller brought, so a `buy` can return fewer tokens plus an
unexpected stock balance. The contract is now inconsistent between its two hops, deliberately and undocumented.

**Does it introduce anything?** It converts a silent value loss into a revert, which is the right trade, and it
adds a denial surface the round 5 note acknowledges ("the caller picks a fee tier that can take the trade").
On `sell` the caller cannot fully control this: `stockGot` is produced by the V4 hop and must then be absorbed
whole by the chosen V3 tier, so a thin tier makes `sell` unusable rather than lossy. Acceptable; worth a
front-end note. No new state, no new external call, no change to the latch or to `nonReentrant`.

**Latent, unchanged by this round (REASONED, Info):** `int256(amountIn)` at `:108` and `-int256(amountIn)` at
`:138` are unchecked explicit casts. A `usdgIn ≥ 2²⁵⁵` would flip an exact-input swap into an exact-output one.
Unreachable at any plausible USDG supply and the `safeTransferFrom` would fail first, but it is one `require`
away and the round did not note it.

### T5-2 — the key comes from the strategy's own treasury

`TradeRouter.sol:96-98` reads `IKeyed(treasury).poolKey()` — the `PoolKey public poolKey` the factory wired once
(`StrategyTreasuryBase.sol:184-190`, `wire()` is factory-only and once-only). `treasury` comes from
`factory.strategies(id)` (`:69`, `:82`), so it is not caller-supplied. **Closes the mechanism completely**: no
factory-mutable value is left in the derived key, which is what the finding said.

### Is the regression test one that fails with the fix reverted? — **EXECUTED, both**

Scratch copy `scratchpad/prior-scratch/hf`, forge 1.8.1.

Baseline: `forge test --mc AuditTradeRouterTest` → **17 passed, 0 failed**.

**T5-1 reverted** (deleted the two added lines):
```
[FAIL: next call did not revert as expected] test_T5_1_aV3HopThatCannotTakeTheWholeInputReverts_andNothingIsStranded()
[FAIL: next call did not revert as expected] test_T5_1_aSellWhoseV3HopCannotTakeTheStockReverts_andTheSellerKeepsTheirTokens()
6 passed; 2 failed
```
**T5-2 reverted** (restored a defaults-derived `_key`, resolving the id from the treasury so the signature holds):
```
[FAIL: PoolNotInitialized()] test_T5_2_aDefaultsChangeDoesNotReachTheRouterForAStrategyAlreadyLaunched()
0 passed; 1 failed
```
Both claims in the commit body hold. **The commit's own process discipline is real, not asserted.**

**One caveat on the T5-1 tests (REASONED).** They are `vm.expectPartialRevert(PartialFill.selector)` tests.
When the fix is reverted the failure is at the `expectRevert`, so the two lines that matter for the *finding* —
`assertEq(usdg.balanceOf(alice), had)` and `assertEq(usdg.balanceOf(address(router)), 0)` — are only ever
evaluated on the path where the transaction reverted, where they are trivially true. The tests pin the
*behaviour chosen* (revert) rather than the *property claimed* (nothing is stranded). A refund-instead-of-revert
fix would fail them too. That is a fair choice, but the 512-of-1,000 stranding the commit message quotes is
**not** asserted anywhere in the committed suite.

### Round 5's own scope gap

Round 5 audited `TradeRouter`, added in `3b9682f` — the immediately preceding commit, by the same author, with
the same model. It did **not** re-examine `LaunchRouter`, which was added in `399856a`, audited in round 4, and
carries the *identical* defaults-derived-PoolKey pattern (`LaunchRouter.sol:72-74`). Round 5 found that pattern
in one router and never looked at the other. It is safe there (see *Checked and found safe*), but by atomicity,
not by the fix — and nobody checked. That is the shape of this whole ledger: **each round audits the thing the
previous round added, and re-reads neither the previous round's claims nor its siblings.**

---

## What I would tell the next round to do differently

1. **Re-read the *claim* after every fix, not just the test.** §3.1 and §2.2 are both fixes whose accompanying
   prose became false the day they shipped.
2. **Grade the disposition, not the finding.** "Fixed" in `AUDIT.md:39` for FA-1 means "decided and documented".
   One word in the status header, and the ledger is wrong forever.
3. **When a fix names a class ("inputs in no constructor's args", "every constructor bound", "a tick with no
   liquidity behind it"), enumerate the class.** All three were enumerated one member short (§2.3, §3.1, §3.2).
4. **A test whose name is a universal ("…andNothingElse", "…byAnyone") must enumerate, not snapshot.** §3.6.
5. **Nobody is paid to call `book()`.** More generally: for each permissionless function, ask who is paid to
   call it *promptly*, and what a late call is worth to the caller. §3.3 is the only place in the rule where
   that question has no answer.
