> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# The new surface at `0e39f69`

Supporting report for [external audit round 2](./00-SCOPE.md). Covers only what did not exist at `9a291aa`:
the singleton hook and its shared per-stock pot, the buy-side launch window and its transient-storage
exemption, `setVoteDelegate`, partial-fill sells, and the token metadata path. A separate lane checked the
old findings.

---

# Lane 12 — the new surface at `0e39f69`

Scope: what `git diff 9a291aa 0e39f69 -- src/` introduced. Target read-only at
`/Users/daneil/Documents/app/side_project/hedgefund` (`0e39f69`, branch `audit/round-2-external-2026-09-21`);
all building and running done in a byte-identical copy at
`…/scratchpad/new-scratch/hf` (forge 1.8.1, `forge build --sizes` reproduces the baseline table to the byte).

**Result: no Critical, no High.** Four Low, four Info. The two mechanisms I expected to carry a High —
the shared `pots[stock]` RAY index and the reversed partial-fill invariant — both hold under the conservation
laws I derived independently (see *Checked and found safe*). The binding question the baseline left open
("are the two path-independent test failures product defects or toolchain drift?") is answered: **both are
toolchain drift**, EXECUTED proof in L12-5.

---

## Findings

### L12-1 · Low · `setVoteDelegate` asserts nothing after its call, so a stock upgrade that repurposes `delegate(address)` puts the factory owner — not only the issuer — inside the blast radius

**Location** `src/str/StrategyTreasuryBase.sol:228-233`; disclosure at `docs/SECURITY.md:419-448`, `:42`.

**Status** REASONED for the exploit path; EXECUTED for the precondition (see Conditions 1).

**Conditions**
1. The live stock implements no `delegate(address)` today. **EXECUTED 2026-09-21**, mainnet
   `https://rpc.mainnet.chain.robinhood.com`, AAPL `0xaF3D76f1834A1d425780943C99Ea8A608f8a93f9`
   (token1 of the listed V3 pool `0xaae0d8…2d6d`): `cast call … "delegate(address)" 0x…dEaD` →
   `execution reverted, data: "0x"`. `delegates(address)` likewise. `oraclePaused()` → `false`,
   `uiMultiplier()` → `1000566080061092436`, code size 569 bytes (beacon proxy). So the hatch is a no-op
   today exactly as documented.
2. The stock is a beacon proxy upgradeable by one **EOA** with no timelock (`docs/STOCK_TOKEN_ASSESSMENT.md:24`,
   VERIFIED there against the registry's full role history). **Status: true today.**
3. The factory owner is the 2-of-4 protocol Safe `0x2910…1693`, nonce 1 (baseline, re-read 2026-09-21).
   **Status: true today, nothing deployed.**

**Mechanism** The call is

```solidity
try IVotesLike(address(_stock)).delegate(delegatee) { accepted = true; } catch {}
```

with no gas cap (deliberate, argued at `:226`) and **no post-condition**. The target (`_stock`) and the
selector (`0x5c19a95c`) are fixed at birth, which is the whole of the containment. If the issuer ever
deploys an implementation in which `delegate(address)` moves, approves or pledges the caller's balance —
or simply an implementation whose fallback is not a revert — then the owner, from the treasury's own
address, can reach every launched treasury's stock, one call each.

The repo's own answer (`:227`, `SECURITY.md:443`) is *"Whoever can do that can already `adminBurn` the
treasury's balance outright, so no check here would stand in its way."* That is the one line I would push
back on, and it is the finding. It collapses two different actors and two different thresholds:

- an `adminBurn` is **the issuer acting alone**, deliberately, against a named address, and it is visible
  as a `Transfer` to zero;
- a repurposed `delegate` is **the issuer enabling and the Safe executing** — and the Safe is the party
  `SECURITY.md:42` promises cannot *"move, approve, pledge or sell anything the treasury holds"*. It also
  does not require the issuer to intend anything against this protocol: an implementation that adds an
  ERC-20-Votes-shaped `delegate` alongside a permit-style approval path, or that routes unknown selectors
  to a module, is a normal upgrade, not an attack.

The treasury is immutable; the issuer's implementation is not. So the treasury is the only side that can
be made to refuse, and it declines to.

**Impact** Who loses: every launched treasury's depositors (the token holders whose buy-backs the stock
funds). Certain loss: none today — this is an **option** the design hands to the Safe, exercisable only
after an issuer upgrade nobody controls. It is permanent: a launched treasury can never gain the check.

**Fix** Bracket the call with a state assertion, ~120 bytes:

```solidity
uint256 b = _stock.balanceOf(address(this));
try IVotesLike(address(_stock)).delegate(delegatee) { accepted = true; } catch {}
if (_stock.balanceOf(address(this)) != b || _stock.allowance(address(this), delegatee) != 0) revert NotOwner();
```

**Byte cost.** The binding contract is `TreasuryDeployer` at **967** free, not `StrategyTreasury`'s 6,195:
`TreasuryDeployer`'s runtime is 23,609 and `StrategyTreasury`'s *init* code is 22,809, so every byte added
to the treasury is a byte off that 967 (EXECUTED, `forge build --sizes`). ~120 bytes fits with room. A
weaker one-line version (`balanceOf` only) is ~60. Note the check must not read `allowance(this, X)` for
every X — the balance equality is what actually binds, since an approval that is never drawn costs nothing
until a transfer, which the balance check would catch on the *next* `setVoteDelegate`; if that is not
good enough, cap the allowance check to `delegatee` as above and accept that an approval to a third party
is uncaught.

**PoC** Not written — it would require inventing the hostile implementation, which is the disclosed
precondition, not the finding. The finding is that the treasury takes the implementation's word for it.

---

### L12-2 · Low · a transfer fee on a stock — which its issuer can add in one block — turns every sweep into a pro-rata write-down of every parked claim on that stock, across every pool

**Location** `src/str/StrategyHook.sol:473-476` (`_redeem`), `:586-595` (`_pot`), `:599-615` (`_square`),
`:626-631` (`_credit`).

**Status** REASONED (derived from the code; no mock built).

**Conditions**
1. A listed stock takes a fee on transfer, or is upgraded to. **Status today: no.**
   `docs/STOCK_TOKEN_ASSESSMENT.md:24` states the issuer *"can change transfer semantics (add a callback,
   a fee, a rebase) in one block with no notice"* — VERIFIED there. Not measured per-token by me; all 194
   registry tokens share one beacon implementation, so this is a single switch for all of them.
2. At least one pool on that stock has something parked. **Status: only while a payout has failed**, which
   the design makes rare (`SECURITY.md:147-149`).

**Mechanism** `_credit` books `s - tip` into `pots[stock].parked` on the strength of having called
`_redeem`, never on the strength of what arrived:

```solidity
_redeem(Currency.wrap(stock), s);          // poolManager.burn + take -> hook receives s*(1-f)
...
_credit(p, stock, toTreasury, cut, mine);  // parked += s - tip
```

With a fee `f`, the hook's balance rises by `s(1-f)` while `parked` rises by `s - tip`. As soon as
`f*s > tip`, `balanceOf(hook) < pot.parked`, and the *next* `_square` on **any** pool on that stock reads
that as an issuer burn: `index = index * bal / parked`, `parked = bal`, and every parked claim of every
pool on that stock is written down pro rata. Each sweep repeats it. `_pay` has the same shape one level
down (`pots[stock].parked -= amount` before a transfer that delivers `amount*(1-f)`).

This is the singleton's amplification, and it is the one blast-radius question `SECURITY.md:133-157` does
**not** cover: that section enumerates deny-list, pause and `adminBurn`, all of which it handles correctly,
but not a change in transfer arithmetic. Under the old one-hook-per-launch design the same fee would have
hit one strategy's ledger; now one fee reaches every strategy on that stock, and the `WrittenDown` event
would fire with an issuer-burn label on something that is not one.

**Impact** Who loses: whoever has stock parked on that pot — creators and protocol recipients who were
undeliverable, and treasuries that were. Recurring, per sweep, bounded by `f` × swept volume. The
`WrittenDown(stock, before, after)` event makes it observable, which is the reason this is Low and not
Medium: an operator watching that event sees it on the first sweep.

**Fix** Measure the redeem: `uint256 got = IERC20(stock).balanceOf(address(this)); _redeem(...); got = balanceOf(...) - got;`
and credit `got - tip` instead of `s - tip`. ~90 bytes in `StrategyHook`, which has **6,214** free — this
one does not touch the 967. Alternatively, and cheaper: state in `SECURITY.md` that a fee-taking stock is
out of scope and add the check to the owner's listing runbook (0 bytes).

**PoC** Not built. The arithmetic above is closed-form; the fixture would be `TaxStock` with a fee in
`_update`.

---

### L12-3 · Low · the launch-transaction exemption is unbounded in count and in size; three places in the docs call it "one" / "first" buy

**Location** `src/str/StrategyHook.sol:210` (`tstore`), `:374-386` (`_buyRate`);
docs `SECURITY.md:279-287`, `SECURITY.md:676`, `docs/ARCHITECTURE.md:148`, `README.md:64-65`.

**Status** EXECUTED. PoC at `…/scratchpad/new-scratch/hf/test/L12NewSurface.t.sol`,
`test_L12_A_theExemptionIsUnlimitedInsideTheLaunchTransaction` and `test_L12_A2_…` (both PASS).

**Conditions**
1. `publicLaunch` is on, or the creator is the owner. **Status: `setPublicLaunch` ships false**
   (`DEPLOYMENT.md`), so this is a post-opening property.
2. The creator launches from a contract of their own (or via `LaunchRouter`, whose buy is the same).
   **Status: available to anyone; `LaunchRouter` makes it available without Solidity.**

**Mechanism** `register` writes `tstore(0, id) tstore(1, launcher_)` and nothing ever clears them before
the transaction ends. `_buyRate` returns the flat rate on *every* evaluation where
`launching == id && sender == launcher`. There is no counter, no size cap and no "first buy" state.

**Measured** (`d.supply = 1e27`, `snipeBps = 9900`, `snipeSeconds = 3`, `taxBps = 1000`, local v4-core):

| | tokens out | share of supply |
|---|---|---|
| launcher, 40 exempt buys × 2,000 stock, one transaction | 899,437,804.499921114779138414 | **8,994 bps** |
| launcher, **one** exempt buy of 80,000 stock | 899,437,804.499921114779138414 | **8,994 bps** |
| a stranger, same second, same 80,000 stock | 9,993,753.383332456830879316 | 99 bps |

Every one of the 40 buys is charged the flat 1,000 bps (asserted to within 64 wei of rounding across the
40 separate floor divisions). The stranger is charged the window's 9,900 bps, to the wei.

**Impact** No money moves that the disclosure does not already allow: the two launcher rows are identical,
so the *count* is economically irrelevant — one buy of any size already takes 89.94% of the supply, and
`SECURITY.md:292-296` (X5-6) discloses exactly that as *"a creator who buys a large first bag"*. What is
wrong is the wording in the other three places — *"the opening's **one** tax-exempt buy"*, *"the creator's
own **first** buy"* — which a front end could read as a property to display or cap ("the launcher's bag"
at `SECURITY.md:296` implies a single figure to show). It is not one buy and there is no bound.

**Fix** Documentation, 0 bytes: replace "one"/"first" with "every buy the launcher makes inside the launch
transaction, at any size". If a bound is actually wanted, it is a hook change (`StrategyHook` has 6,214
free) — clear the transient words on first use (`tstore(0,0)` in `_buyRate` would need `_buyRate` to stop
being `view`, ~200 bytes and a signature change), or cap the exempt notional. I do **not** recommend the
code change: the pool is seeded with the creator's whole supply and the sell spike runs from registration,
so the exempt bag is the creator buying back their own float behind a 90% exit tax.

**PoC** `forge test --mt test_L12_A -vv` in the scratch copy; log lines reproduce the table above.

---

### L12-4 · Low · the dust paths shrink a lot without selling: `takeProfit` pays a bounty for a call that moved no stock and never spends the closed-market hour

**Location** `src/str/StrategyTreasuryBase.sol:361-377` (`takeProfit`), `:390-402` (`stopLoss`).

**Status** REASONED (arithmetic derived and checked against the conservation law below; the honest-lot
half of the behaviour is already characterised by the repo's own `test_T6_2_…`).

**Conditions**
1. A lot whose value **at its own cost** is under one USDG unit: `_ruleValue(principal, p) == 0`, i.e.
   `q·cost < _SCALE`. **Status: reachable — it is the documented remainder of a chunked lot (audit R5-2),
   and `_shrink` leaves one every time a short fill lands on it.**
2. `health()` open. **Status: normal.**

**Mechanism** Both sales skip the swap when the offered amount rounds to nothing, but neither skips the
*effects*:

```solidity
uint256 got;
if (_ruleValue(principal, p) != 0) { _poolOnlyPace(); (sold, got) = _swapStock(false, principal, p); ... }
if (left != 0) { L.tp1Left = left - q; if (left == q) L.half = true; }
_shrink(id, q);
uint256 profit = q - principal;
uint256 bounty = profit * _params.bountyBps / 1e4;
buybackStock += profit - bounty;
lastSalePrice = p;
...
if (bounty != 0) _stock.safeTransfer(msg.sender, bounty);
```

So on the dust path: the lot loses `q`, `buybackStock` gains `q - principal - bounty`, the caller is paid
`bounty` in stock, `lastSalePrice` is moved, `tp1Left` is worked off — and **not one wei was sold**. The
`principal` remainder falls out of the ledger into `unbookedStock()` (`bookedStock + buybackStock` drops by
`principal + bounty` while the balance drops by only `bounty`). `stopLoss`'s dust path is the same shape
with the whole `q` falling out and nothing credited.

Three consequences, all small:
- the ledger's slack grows silently; it is recovered only by a later `book()`, which **refuses during a
  scheduled closure** (`:309`, `pricedOffPoolOnly`), so the stock sits unbooked for up to a weekend;
- a bounty is paid for a call that produced nothing (`bountyBps ≤ 200`, on a sub-unit `profit`, so the
  absolute number is dust — but the *rule* "the caller is paid out of what the call produced" is broken);
- `_poolOnlyPace()` is skipped, so a dust lot can be worked at any rate during a closure. This is
  deliberate (audit T6-2) and correct as far as it goes, but it is also the path on which `lastSalePrice`
  moves without a sale, which is the one input a closure-time pin can reach for free.

**Impact** Who loses: the treasury, by sub-USDG-unit amounts per call, plus the gas the bounty invites.
Certain loss: the bounty, bounded at `2% × (one USDG unit × p/cost)` per call. No option gain for an
attacker beyond nudging `lastSalePrice` up (which makes `buyDip` fire earlier at a price the oracle still
has to sign — the treasury buys at the real price either way).

**Fix** One condition: `if (profit != 0 && got == 0) bounty = 0;` — or move the whole dust branch to
`if (_ruleValue(principal, p) == 0) { /* fold into buybackStock, no bounty, no lastSalePrice */ }`.
~40 bytes against `TreasuryDeployer`'s **967**.

**PoC** Not built. The branch is reached by any lot with `q·cost < _SCALE`; the repo's own
`test_T6_2_aDustTailDoesNotSpendTheClosedMarketHour_…` already constructs one for the pacing half.

---

### L12-5 · Info · both path-independent suite failures are toolchain drift, not product defects — and here is the proof and the two-line fix

**Location** `foundry.toml` (no `gas_limit`, no `bytecode_hash`); `test/AuditRound6Treasury.t.sol:171-183`;
`test/AuditRound5Tax.t.sol:434-443`.

**Status** EXECUTED. Suite at my copy: **6 failed, 1,079 passed, 31 skipped, 1,116 total** — byte-for-byte
the baseline's path B.

**(1) `test_holds_statefulCampaigns_tp1LeftNeverOutlivesTheLot_noPanic_theLedgerSums_noStockUnaccounted`
— `EvmError: MemoryOOG` / `EvmError: Revert`, gas 1,073,720,760.**

That number is forge's default test `gas_limit` of `2^30 = 1,073,741,824`, less the frame. The test runs
36 campaigns in one function; `testFuzz_holds_aCampaignFromAnySeed` measures one at μ 35,924,258 gas, so
36 of them need ~1.29–1.43 G.

```
$ forge test --mt statefulCampaigns --gas-limit 90000000000
[PASS] …statefulCampaigns…() (gas: 1434977660)   # StockCurrency0
[PASS] …statefulCampaigns…() (gas: 1434554490)   # UsdgCurrency0
```

**1,434,977,660 needed against 1,073,741,824 available.** CI pins `FOUNDRY_VERSION: v1.5.0`, whose default
test gas limit is higher, which is why CI is green. Not a product defect. Fix: `gas_limit = 9223372036854775807`
in `[profile.default]`, or split the 36 campaigns across three test functions.

**(2) `test_holds_isolationIsReal_a_withoutItTheLauncherStaysExemptThroughTheWholeTest` — `9900 != 1000`.**

This test is a **negative control on the harness**, not on the product. Its own comment says so: it asserts
that *without* `isolate = true` a forge test is one transaction and the transient exemption therefore leaks
across top-level calls. Forge 1.8.1 no longer leaks it — transient storage is cleared between top-level
calls in non-isolated runs too — so the control fails while its twin passes:

```
[FAIL: non-isolated run no longer leaks the flag …: 9900 != 1000] test_holds_isolationIsReal_a_…
[PASS] test_holds_isolationIsReal_b_withItTheLaunchersNextCallPaysTheSnipeRate
```

The positive assertions the control exists to protect all still hold on 1.8.1:
`test_X5_1_…andOnlyTheLauncherIsExempt`, `test_X5_2_aCopiedLaunchIsRefusedBadRequest_…andTheCreatorsOwnLaunchLandsExempt`,
`test_X5_2_aContractLaunchingInItsOwnNameStillGetsItsExemptFirstBuy`,
`test_holds_twoLaunchesInOneTransaction_onlyTheLastKeepsTheExemption` — 23 of the 24 in that contract pass,
and my own L12-3 PoC exercises the exemption positively. Fix: delete the control, or re-express it as
"`_b` holds under both `isolate` settings".

**(3) The three `InteractRuleMev` `setUp()` failures (`CurrenciesOutOfOrderOrEqual`)** are round 1's
`bytecode_hash` path-dependence, unchanged and out of this lane's scope; they are what makes path A and
path B disagree (a `setUp()` revert removes that contract's whole test set from the totals with no notice).
Fix: `bytecode_hash = "none"` in `foundry.toml`.

**Impact** No value impact. But the suite being red on the current release is itself a hazard: the totals
move by 22 tests between two byte-identical checkouts and nothing in the output says so.

---

### L12-6 · Info · the `StrategyTreasuryV4` removal is clean in `src/`; one stale reference survives in tooling

**Location** `tools/gen_reference.py:812`.

**Status** EXECUTED (grep over the whole tree minus `lib/`, `out/`, `cache/`, `ref/`).

`Venue`, `Listing.venue`, `v4Key`, `listV4`, `setV4ListingEnabled`, `v4ListingEnabled`, `ListedV4`,
`V4ListingEnabledSet` and `TreasuryV4Deployer` are gone from `src/`, `script/`, `emergency/` and
`docs/REFERENCE.md`. `Listing` is `{oracle, v3Pool, openPriceE18, enabled}` — no one-armed enum, no way for
a listing to name V4. `PoolTrader._swapForExit` and its `PartialFill` error went with it; the only surviving
`PartialFill` is `TradeRouter`'s own (`src/str/TradeRouter.sol:62,119`), which `ARCHITECTURE.md:83` still
describes correctly. The one leftover is a code comment in the reference generator naming
`StrategyFactory.Venue` as an example of forge's internal-type keying. Cosmetic.

---

### L12-7 · Info · `sweep` opens its own `unlock`, so it cannot be composed inside another V4 unlock

**Location** `src/str/StrategyHook.sol:438-442`.

**Status** REASONED.

`sweep` calls `poolManager.unlock` unconditionally. Called from inside anyone else's unlock (an aggregator
batching a swap and a sweep, a router that wants to sweep after taxing itself) V4 answers `AlreadyUnlocked`
and the whole call reverts. Inside the hook's *own* `unlockCallback` the failure is swallowed by the
`try` at `:450`, which silently drops the token leg — self-inflicted, since only the sweeper's own tip
recipient is in a position to do it. No fix recommended; noting it so nobody treats `sweep` as composable.

---

### L12-8 · Info · `SECURITY.md`'s "it writes **no storage**" for `setVoteDelegate` is not literally true, and the closed-selector test exempts `setVoteDelegate` from the walk that would have caught it

**Location** `docs/SECURITY.md:437`; `src/str/StrategyTreasuryBase.sol:228`;
`test/TreasuryVote.t.sol:318-337`, `:359-361`.

**Status** EXECUTED (read of `_changesState`).

`setVoteDelegate` is `nonReentrant`, so it writes OpenZeppelin's `ReentrancyGuard._status` (1→2→1) —
net-zero at the end of the call but a real `SSTORE` pair, and `vm.record` sees it. The claim is true of
*net* state and false of the trace. `test_everySelectorInTheBytecodeButTheNine_sentByTheOwner_writesNothingAnywhere`
cannot catch the discrepancy because `_changesState` lists `setVoteDelegate.selector` first among the nine
it skips. Reword to "writes no storage the treasury keeps", or assert net state explicitly.

---

## Checked and found safe

Each with the line that makes it safe.

**The shared pot, index and epoch (`StrategyHook.sol:402-631`)**

- **No amount is ever inferred upward from a balance.** `_pot` (`:586-595`) reads
  `IERC20(stock).balanceOf(this)` only to *detect a shortfall*; the only writer that raises `parked` is
  `_credit` (`:626-631`), which is called exclusively from `settleStock` after the stock has physically
  arrived. The old "new revenue is `balance − totalOwed`" theft primitive is gone, and I found no residue
  of it. (Subject to L12-2, which is about the redeem lying, not about a balance being mistaken for revenue.)
- **The pro-rata index is arithmetically correct across interleaved burns and credits.** I derived the
  invariant `pot.parked ≥ Σᵢ owedᵢ · index / indexᵢ` and checked it against every writer: `_credit` adds the
  same amount to both sides at the current index; `_pay` (`:635-656`) subtracts it from both; `_pot`'s
  write-down scales both by the same `bal/parked`. Multiplicative rebasing means a pool that missed several
  write-downs lands on the same number in one step as it would have in several. Rounding is always *down* on
  the claim side, so the pot is never short — the few wei left over are the "nobody's" the docstring at `:557`
  names.
- **`_square` runs before every credit and every payout, in every path.** `settleStock:498`, `flush:525`,
  `_claim:577`. There is no write path that touches `owed*` without squaring first, which is what makes
  "a pool touched after a wipe-out it never saw" safe: `if (p.epoch != epoch)` (`:607`) zeroes its three
  amounts and re-bases it to the fresh index, and a pool *registered* after a wipe-out takes
  `pot.epoch`/`pot.index` at `register:208`, so it can never inherit the old epoch's basis.
- **The epoch cannot strand a material balance.** A wipe-out needs `index < MIN_INDEX = 1e9` starting from
  `RAY = 1e27`, i.e. a cumulative haircut of 1e-18. The residue left "nobody's" at the wipe-out step is at
  most that fraction of the original pot. `MIN_INDEX` is well chosen.
- **A donation cannot shift loss between pools except in the direction of a gift.** Stock above `parked`
  masks a shortfall (delaying a write-down) but can never create a claim; `poolManager.mint` of ERC-6909
  claims to the hook is likewise stranded, never swept (`settleToken`/`settleStock` redeem exactly
  `accruedToken`/`accruedStock`). The repo's `test_aDonationOfStockOrOfClaimsCanBeExtractedBySweepClaimOrTipFromNoPool`
  states the same property.
- **`uiMultiplier()` is not a rebase.** I worried that a corporate action would move `balanceOf(hook)` and
  be read as an issuer burn (or, upward, strand the claimants' split). `STOCK_TOKEN_ASSESSMENT.md:30`
  verifies three ways — source, archive-node reads across the NVDA flip at blocks 58,958,492→3, and a fork
  test — that `balanceOf`/`totalSupply` never read the multiplier. Confirmed live 2026-09-21: AAPL's
  `uiMultiplier()` is `1.000566080061092436e18` and its raw balances are unscaled.

**Transient slots 0 and 1 (`StrategyHook.sol:210`, `:382`)**

- **Nothing else in this contract's inheritance can reach them.** `grep -rn "tstore\|tload\|transient "`
  over `src/` and the used OpenZeppelin and v4-core files returns exactly the two assembly blocks in
  `StrategyHook`. The hook inherits only interfaces (`IHooks`, `IUnlockCallback`); it uses the non-transient
  `bool private _distributing` rather than `ReentrancyGuardTransient`; `TransientStateLibrary` reads the
  *PoolManager's* transient storage through `exttload`, never its own. Solidity emits `TSTORE` only for
  `transient` state variables (none declared) and inline assembly. No collision is possible.
- **The exemption cannot be stolen or misdirected.** `_buyRate` needs `launching == PoolId.unwrap(id)` *and*
  `sender == launcher`, where `sender` is whoever called `poolManager.swap`. A 4337 bundle, a relayer batch
  or a public multicall therefore does not carry it (X5-1's fix, re-verified by
  `test_X5_1_…andOnlyTheLauncherIsExempt` passing on 1.8.1). An EOA launcher gets no exemption at all,
  because an EOA cannot be the `sender` of a V4 swap. A second `register` in the same transaction overwrites
  both words, so the loser is the launcher's own first pool and never a third party
  (`test_holds_twoLaunchesInOneTransaction_onlyTheLastKeepsTheExemption`). A vouched launcher gets it only
  for its own swaps, and `LaunchRouter:81` (`q.creator != msg.sender → NotYourLaunch`) is what makes that
  the creator's. The size/count property is L12-3 above; the *addressing* is sound.

**Treasury resolution and pool collision (`StrategyHook.sol:193-212`, `:269-296`)**

- **Every treasury-facing entry point resolves through one function.** `noteEvent`, `meanTick` and
  `observationCount` all go through `_mine()` (`:285-288`), which reads `pools[poolOfTreasury[msg.sender]]`
  and then checks `p.treasury == msg.sender` — so an address that is no treasury lands on `pools[bytes32(0)]`
  and is refused. `poolOfTreasury` is written only in `register`, only by the factory, and only once per
  treasury (`:202`). Treasury A has no way to name pool B, and `afterSwap`'s untaxed branch (`:320`) compares
  against *that pool's* `p.treasury`, so treasury A trading in pool B pays full tax.
- **Two pools cannot collide.** `PoolId` is `keccak256(PoolKey)` and the token is CREATE2'd per launch;
  `register` refuses a second registration of either the pool (`p.treasury != 0`) or the treasury.
  A treasury address can only be produced once — CREATE2 to an occupied address returns zero and
  `TreasuryDeployFailed` fires.
- **The per-pool storage region is 1,032 slots** (a 1,024-slot `TwapRing` plus eight), placed at
  `keccak256(poolId ‖ slot)`. Two regions overlapping, or one overlapping `pots`/`poolOfTreasury`, needs a
  256-bit keccak coincidence within 1,032. Standard Solidity assumption; noted because the singleton is the
  first version where it matters.
- **Nothing still assumes per-launch isolation.** The `_distributing` latch is genuinely shared now, and the
  sharing is in the *conservative* direction: during a payout of pool A, `sweep`, `claim`, `claimFor`,
  `setProtocol`, `proposeCreator` and `acceptCreator` are refused for **every** pool on every stock. The only
  thing that costs is atomic composition inside one transaction; it can never leave the latch set, because
  `_distributing = true` and `= false` bracket a body whose every revert unwinds the write. The repo's
  `test_holds_fromInsideAPayoutOfPoolA_poolBCanBeNeitherSweptNorClaimed_…` states it. `settleToken`'s tip
  transfer (`:468`) is the one payout *outside* the latch, and it is safe only because the token is
  `StrategyToken` — a plain OpenZeppelin ERC-20 with no callback, deployed by the factory and immutable. A
  re-entrant `sweep` there hits V4's `AlreadyUnlocked` and is swallowed by the `try`.

**Blast radius of one issuer action against the shared address**

- I set out to show the docs understate this and could not. `SECURITY.md:133-157` states it exactly: a
  deny-list of the hook stops the stock leg of every sweep **on every stock** (the deny-list is shared by
  all stock tokens), a pause stops that stock's pools, an `adminBurn` writes down every claim on that stock
  pro rata across every pool, and **trading is unaffected** by all three because the tax is a 6909 claim
  minted inside the swap and no stock moves until a sweep. I verified each leg against the code: `afterSwap`
  touches no ERC-20; `_redeem`'s `take` is what a deny-list refuses; `flush` (`:521-529`) is the fallback
  that still pays whatever is parked; `claim(id, to)` (`:569`) rescues a denied *recipient* but not a denied
  *hook*, which the docs do not claim. Cross-stock contamination from a burn is **nil** — `pots` is keyed by
  stock and `_square` only ever touches one pot. Confirmed by the repo's
  `test_anIssuerBurnScalesEveryParkedClaimOnThatStockProRata_neverAnotherStocks_neverFreshRevenue`.

**Partial-fill sells — the conservation law, derived independently**

The invariant is `stockBalance ≥ bookedStock + buybackStock` with `bookedStock = Σ lots[i].qty`. I checked
every path:

| path | Δ(booked+buyback) | Δ(stock balance) |
|---|---|---|
| `_book` | `+un` | 0 (slack absorbed) |
| `takeProfit`, full fill | `−(principal + bounty)` | `−(principal + bounty)` |
| `takeProfit`, short fill | `−(sold + bounty)` | `−(sold + bounty)` |
| `takeProfit`, dust | `−(principal + bounty)` | `−bounty` (slack grows — L12-4) |
| `stopLoss` | `−q` | `−q` (proceeds in USDG) |
| `buyDip` | `+got` | `+got` |
| `buyback` | `−spent` | `−spent` |

- The short-fill re-derivation is exact: `principal := sold`, `q := ⌊sold·p/cost⌋`. `q ≤ q_old` because
  `sold ≤ ⌊q_old·cost/p⌋`, so `_shrink` can never take more than the lot holds; `q ≥ sold` because a
  take-profit is only due at `p > cost`, so `profit = q − sold ≥ 0` and the profit share cannot go negative.
  `q ≥ 1` always (`_swap` reverts `Slippage` on a zero fill and `p > cost`), so tp1 cannot stall.
- **`tp1Left` never outlives the lot.** `left ≤ L.qty` at entry, `q ≤ left`, and the writes at `:370` happen
  *before* `_shrink` pops, so a popped lot's fields are overwritten by the moved lot rather than corrupting
  it. `stopLoss`'s clamp (`:394`) uses the pre-shrink `L.qty − q`. `q == L.qty ⟹ left == q ⟹ L.half`, so
  the two can only reach zero together.
- **A short fill cannot desynchronise the ledger** — the property the old "must fill whole" rule protected.
  Every effect is sized from `spent`/`got`, the swap happens before `_shrink`, and `PoolTrader._swap`
  (`src/PoolTrader.sol:141`) reverts when nothing went in or nothing came out, so a sale that moved nothing
  cannot spend the closed-market hour, pay a bounty or leave the pool on the limit.
- **`_poolOnlyPace` is one clock for the whole treasury** (`lastPoolOnlySaleAt`), shared across lots, taken
  *before* the swap so a reverting swap does not spend it — R5-3's 64-chunks-in-one-transaction is closed.
  The residual grief (a short fill spends the hour and leaves the pool outside the deviation gate) is the
  repo's own T6-1, already characterised there as Low/Info; the singleton changes nothing about it.
- `buyDip`'s `Math.mulDiv(spent, _SCALE, got)` cannot divide by zero (`got > 0` or `_swap` reverted) and
  cannot produce `cost == 0` at any realistic price (`cost ≈ p` by construction, and `spent ≥ minLotUsdg`).

**`sellChunkUsdg` and the per-listing gates (`StrategyFactory.sol:276-292`, `:322-331`)**

- `_gates` is the single reader, and the pair falls back as a pair while the chunk falls back on its own —
  so a listing can never end up with one of the two gates from the defaults and the other from the listing.
  `_gatesOk` makes `slip == 0, dev != 0` unreachable, which is the only input that would have broken the
  `g.maxSlippageBps == 0` fallback test.
- The `band != 0 ⟹ chunk ≤ d.sellChunkUsdg` clamp is the R5-3 answer, and `_lotParams` re-asks
  `sellChunkUsdg ≥ minLotUsdg` at launch because the defaults move after a listing is set.
- `Gates.sellChunkUsdg` is `uint64`; at 6-decimal USDG that is 1.8e13 USDG, and the three fields pack in one
  slot as claimed.

**`terms` covers everything mutable that is not already in an address**

`_terms` (`:352-356`) pins token, treasury, `lpFee`, `tickSpacing`, the full `Rates`, and the fee's currency
*and* amount. Everything else the owner can move is either inside a CREATE2 address (`supply` via
`_tokenArgs`; oracle, V3 pool, both gates, the chunk, every execution bound via `_treasuryArgs`), or checked
directly in a direction that can only *revert* a pending launch (`bandCeiling`, `publicLaunch`,
`listings.enabled`, `launchers`, `minTaxBps`/`maxTaxBps`/`maxCreatorBps`), or covered by `Request.maxFee` and
`Request.expectedOpenPriceE18`. I looked for a mutable that is in none of the three and found none.

**`TokenDeployer`, `initMetadata`, the editor**

- **The one-shot guard is real.** `initMetadata` needs `msg.sender == launcher` (the factory, immutable and
  set as the mint target in `_tokenArgs`), `updatedAt == 0` and `!locked`. `_write` sets `updatedAt`
  unconditionally, so a creator who writes their page with `setMetadata` first closes the door, and the
  factory's only call site is `launchWithMetadata` on the token it just deployed.
- **Name and symbol are capped at launch and immutable after it.** `bytes(q.name).length > 64 ||
  bytes(q.symbol).length > 32` in `_launch` (`:385`, the K7-2 fix); `ERC20` exposes no setter for either, and
  nothing in the metadata half of `StrategyToken` calls `_mint`, `_burn`, `_transfer` or `_approve`.
- **The editor cannot outlive a lock or appoint a successor.** `setEditor` is deployer-only and refused once
  locked; `lock()` is deployer-only and *refused while an editor is appointed* (K7-1), so the order is forced:
  dismiss, read, lock. There is no race a deployer can lose to their own editor.
- **The one genuinely mutable thing is the page**, for ever unless the deployer locks it — disclosed at
  `StrategyToken.sol:17-19`, `SECURITY.md:480-490` and `README.md:87`, including that a link people have
  come to trust can be swapped for a phishing one. The `deployer` is the launch-time creator and is
  deliberately *not* the hook's payout creator, so an `acceptCreator` takeover of the fees does not reach
  the page.
- `TokenDeployer` is `BoundDeployer`-gated to one factory, claimed in the factory's constructor, so nobody
  can occupy a pending launch's predicted token address.

**`PoolTrader` and `LaunchRouter`**

- `PoolTrader`'s change is a deletion (`_swapForExit`, `MIN_SQRT`/`MAX_SQRT`, `PartialFill`, the
  `requireFull` parameter). What remains is the same bounded swap with the average-price check still on
  `spent`, so a short fill meets the same floor a full one does. No caller of the old five-argument
  `_swapBounded` survives.
- `LaunchRouter` gained `launchWithMetadata`, an immutable `hook` read from the factory, and `terms` in place
  of `hookSalt`. `q.creator != msg.sender → NotYourLaunch` is unchanged and is the whole of what the owner's
  `setLauncher` vouching is worth. `unlockCallback` is reachable only from the manager it just unlocked; it
  refunds `stockIn − owedIn` to the buyer on a short fill and keeps nothing (asserted by the repo's own
  `test_oneTransaction_…`: zero stock, zero token, zero allowance left behind).
- `TradeRouter` changed only in comments, and the new one is the right one: in the launch window a buy
  through it pays up to 99% and `minOut` is the caller's only protection.

**The tax itself (`StrategyHook.sol:337-361`)**

- The unspecified-currency selection is correct in all four (direction × exactness) cases, and
  `inToken = Currency.unwrap(c) == p.token` books the accrual by *currency*, not by direction — which is the
  bit an exact-output buy would otherwise get backwards.
- The V4 delta accounting closes: the hook returns `+tax` on the unspecified leg, which credits it `tax`,
  and `poolManager.mint(this, c.toId(), tax)` consumes exactly that credit, so the hook never has to settle.
- `1e4 − rate` cannot reach zero: exact-output is refused unless `rate == p.taxBps ≤ MAX_TAX_BPS = 1500`,
  and the exact-input branch divides by the constant `1e4`. `MAX_SNIPE_BPS = 9900` keeps a buyer 1% of the
  output in the worst window.
- `accruedToken`/`accruedStock` are `uint128`; overflow reverts the *swap* until somebody sweeps, which is
  the safe direction, and 2^128 wei is ~3.4e11 full-supply round trips away at a 1e27 supply.

---

*Deliverable written 2026-09-21. Scratch copy, PoC and build artifacts at
`/private/tmp/claude-501/…/scratchpad/new-scratch/hf` (`test/L12NewSurface.t.sol`). The target checkout was
not modified.*
