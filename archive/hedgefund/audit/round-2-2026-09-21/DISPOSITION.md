> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Disposition of every round-1 finding at `0e39f69`

Supporting report for [external audit round 2](./00-SCOPE.md). Produced by a lane whose only task was to
work through round 1's list finding by finding against the rewritten code. Summary and the entries that
matter are in [`ISSUES.md`](./ISSUES.md); this is the full table and the evidence.

---

# Round-1 disposition against `0e39f69`

Every round-1 ID (F-01 … F-41, I-1 … I-18), plus the "checked and found safe" section and the rejected list,
carried forward to the singleton rewrite. Line numbers are at `0e39f69`. Every conclusion is labelled
**EXECUTED** (I ran or read it myself this round) or **REASONED**.

**Standing caveat, from BASELINE2.** The author's commits are dated after round 1's branch was pushed but
`AUDIT.md:177` still reads "Still true: no external review" and `audit/` is not on `main`. Nothing below
should be read as the author responding to round 1. Where a mechanism closed I say whether it looks
intended or incidental; I do not claim motive.

## Counts

| state | findings | Info | total |
|---|---|---|---|
| **WORSE** | 6 | 1 | **7** |
| STILL OPEN | 28 | 14 | 42 |
| CHANGED SHAPE | 3 | 2 | 5 |
| FIXED | 2 | 1 | 3 |
| MOOT | 2 | 0 | 2 |
| FIXED INCIDENTALLY | 0 | 0 | 0 |
| | 41 | 18 | 59 |

Nothing in round 1 was closed by the rewrite alone: the two genuine fixes (F-17, F-28) and the one Info fix
(I-2) are all deliberate code, and each was already an explicit `audit R5-*` / `X5-*` item in the author's
own ledger. The rewrite's net effect on round 1's list is **six findings made worse and three closed.**

---

## The table

| ID | state | one-line evidence at `0e39f69` |
|---|---|---|
| **F-14** | **WORSE** | `test/InteractRuleMev.t.sol:152-153` hashes **4** constructor args against a **5**-arg `StrategyToken`; the mined side is a coin flip, `setUp()` dies `CurrenciesOutOfOrderOrEqual` and 22 tests vanish. `bytecode_hash="none"` **no longer fixes it** — EXECUTED |
| **F-23** | **WORSE** | `StrategyFactory.sol:45-48` `bind()` still open, now with **three** targets incl. `hook.bind()` (`:240`); the hook's address is **mined** (`StrategyHook.sol:175`), so a squat forces a re-mine, not a redeploy |
| **F-03** | **WORSE** | `StrategyTreasuryBase.sol:109` `MAX_BAND_BPS_PER_HOUR = 200` and `StrategyFactory.sol:265` `bps > 200` **unchanged**; `19d3faf` is docs-only and turns condition 1 into a scripted pre-launch step |
| **F-33** | **WORSE** | `script/DeployStrategyLaunchpad.s.sol:258-264` prints 8 of **22** defaults (was 8 of 19); `:259`'s `"supply / lpFee / tickSpacing:"` mislabel passing two values is verbatim |
| **F-39** | **WORSE** | `StrategyTreasury.sol:42`'s `tp1Bps >= 2*(maxSlippage+poolFee)` floor still unmirrored, and `StrategyFactory.sol:276` `setListingGates` is a **second** lever that moves `maxSlippageBps` per stock |
| **F-31** | **WORSE** | one hook address for every strategy (`StrategyHook.sol:59` says so): one issuer deny-list entry stops every strategy's stock leg; `docs/SECURITY.md:71` still says "recovers fully" |
| **I-9** | **WORSE** | a rebasing / fee-on-transfer stock now mis-values a **shared** pot: `StrategyHook._pot:590` reads `balanceOf(hook)` for every pool on that stock at once |
| F-01 | STILL OPEN | `AUDIT.md:259`, `LISTING_CANDIDATES.md:39,48`, `docs/DEPLOYMENT.md:641`, `docs/REFERENCE.md:277` and `StrategyFactory.sol:261-262` all carry "$54M / $309k" verbatim |
| F-02 | STILL OPEN | `TradingCalendar.sol:15-16,29,130-135,163` byte-identical; `docs/SECURITY.md:36` still promises what `:37` grants; heading `:572` unchanged |
| F-04 | STILL OPEN | `StrategyTreasuryBase.sol:105` `MAX_SIZING_AGE = 5 days`; outflow re-enumeration finds only 4 bounties + settle + V3 callback + 1 `take` inward — EXECUTED |
| F-05 | STILL OPEN | `StrategyFactory.sol:247-256` and `StrategyHook.sol:196`: `spikeSeconds`, `buybackCooldown`, `sweepTipBps=0`, `bountyBps=0`, `minTaxBps=0`, upper `minLotUsdg`/`tickSpacing`, `supply=1` all still accepted; the 1e4 sum is still a strict `>` |
| F-06 | STILL OPEN | `StrategyTreasuryBase.sol:553` `half = impact/2`; `StrategyFactory.sol:254` and `StrategyTreasury.sol:38` both still `== 0 \|\| > 1000` |
| F-07 | STILL OPEN | `StrategyHook.sol:271` `block.timestamp < lastEventAt + 2 * spikeSeconds` — verbatim |
| F-08 | STILL OPEN | `StrategyTreasuryBase.sol:238-241` `unbookedStock()` still floors at 0; no treasury reconcile; `stockEquivalentHeld:252` still reads the ledger |
| F-09 | CHANGED SHAPE | size half **fixed** by chunked partial-fill sells (`:335`, `:367`); cost-basis half and the unpaid `book()` (`:302-314`) untouched |
| F-10 | STILL OPEN | `StrategyTreasuryBase.sol:132` one `lastSalePrice`, written at `:375`, `:400`, `:422`, read at `:408` |
| F-11 | STILL OPEN | `README.md:370,379` still "beat holding the stock" / **1.0278**; `grep -c rule-backtest README.md` = **0** — EXECUTED |
| F-12 | STILL OPEN | `tools/rule_backtest.py` unchanged since `9a291aa`; `docs/rule-backtest/README.md` moved 5 lines — EXECUTED (`git diff --stat`) |
| F-13 | STILL OPEN | `:373` profit-based, `:399` whole proceeds, `:420` whole spend; `MAX_BOUNTY_BPS = 200` at `:107` |
| F-15 | STILL OPEN | the exact assertion round 1 named is still `assertGe`: `InteractRuleMev.t.sol:268,1072`, `InteractVenueParity.t.sol:345`, `SellChunk.t.sol:43`; `invariant_callSummary:1105` still `view`, `runs = 12` at `:1049` |
| F-16 | STILL OPEN | `StrategyTreasuryBase.sol:446` swap-and-pop; `lots[id]` at `:334`/`:385` still panics OOB; chunking makes the race *more* frequent |
| **F-17** | **FIXED** | `StrategyFactory.sol:382` `if (msg.sender != q.creator && !launchers[msg.sender]) revert BadRequest()` — round 1's own proposed fix, closes the **mechanism** |
| F-18 | STILL OPEN | `PriceOracle.sol:42` `maxStockAge_ <= 48 hours && maxUsdgAge_ != 0` — verbatim |
| F-19 | STILL OPEN | `grep -rn renounceOwnership src/ script/` → **no match**; `StrategyFactory:108` and `TradingCalendar:22` still bare `Ownable2Step` — EXECUTED |
| F-20 | STILL OPEN | `StrategyTreasuryBase.sol:412` spends net of bounty, `:421` books `mulDiv(spent, _SCALE, got)` — bounty still excluded |
| F-21 | STILL OPEN | `:571` `uint160(fromSpot)` and `:585-586` `uint160(lim)` — three unchecked casts, unchanged |
| F-22 | STILL OPEN | `TwapRing.sol:52` `int56(uint56(nowTs - last.ts))` checked; `meanTick:66` has the guard `write` lacks |
| F-24 | STILL OPEN | `TradeRouter.sol:150` refunds the **stock** to `refundTo`; `:76` `minTokensOut` covers only `tokensOut` |
| F-25 | STILL OPEN | `_notePrice` unconditional in `takeProfit:354` and `buyDip:411`; only `_book:309` and `stopLoss:382` gate on `pricedOffPoolOnly()` |
| F-26 | STILL OPEN | `:562-567` mean branch has no widening term; `:573` anchor branch still grows one cap per cooldown |
| F-27 | **MOOT** | `StrategyTreasuryV4`, `TreasuryV4Deployer`, `listV4`, `v4ListingEnabled` all deleted (`AUDIT.md:35-39`); there is no V4 stock venue to have a spot-only `health()` |
| **F-28** | **FIXED** | `LaunchRouter.sol:107-108` returns early for `None`/`Native`, which was the variant round 1 called "worse in kind"; `_terms:355` now also pins fee **currency and amount** |
| F-29 | STILL OPEN | `StrategyHook.sol:470` and `:515` still report credits, still two `Swept` per sweep, tip still in **no** event |
| F-30 | **MOOT** | `StrategyTreasuryV4` no longer exists. (`StrategyTreasury` inherits `PoolTrader`, whose `oracle` is `public immutable` at `PoolTrader.sol:35`, so the surviving venue answers.) |
| F-32 | STILL OPEN | `PriceOracle.sol:31,43` calendar immutable; `StrategyTreasuryBase.sol:113` `_oracle` immutable; `StrategyFactory.sol:335` bakes it into the treasury args |
| F-34 | CHANGED SHAPE | `MAX_SLIPPAGE_BPS = 300` (`:108`) unchanged, but `setListingGates` (`StrategyFactory.sol:276-292`) implements round 1's "per-listing" recommendation and adds F-39's second lever |
| F-35 | STILL OPEN | `minLotUsdg` still a `Default` with no floor tied to gas; the native token is still unnamed in `docs/OPERATIONS.md` |
| F-36 | CHANGED SHAPE | sell side closed by partial fills; buy side unchanged — `:409` `spend = reserve * lotBps`, `:419` dust refusal, `:422` `lastSalePrice = p` ratchet |
| F-37 | STILL OPEN | `StrategyHook.sol:509-511` creator paid `creatorBps` of every stock-side take incl. their own; `StrategyFactory.sol:116` "forever" |
| F-38 | STILL OPEN | `StrategyHook.sol:508-511` split unchanged; `StrategyTreasuryBase.sol:372-374` only profit becomes `buybackStock` |
| F-40 | STILL OPEN | `_noteTokenSpot:431-442` still has no `getLiquidity(id) != 0` — the guard `_observe:396` does have; `docs/SECURITY.md:168` still claims it for both |
| F-41 | STILL OPEN | `AUDIT.md:206` still lists blocker 5 (FA-1 / TR-6) among items **"fixed"**; `:604` still offers the three options — verbatim |
| I-1 | STILL OPEN | `StrategyHook.sol:175` `0x2844` unchanged; `beforeDonate`/`afterDonate:753-754` still unreachable reverting stubs |
| **I-2** | **FIXED** | `StrategyFactory.sol:352-355` — `_terms` includes `d.launchFeeCurrency` **and** `d.launchFeeAmount`, with the R5-4 rationale in the comment |
| I-3 | STILL OPEN | `StrategyFactory.sol:440` `uint160(Math.sqrt(...))` with no MIN/MAX_SQRT_PRICE bound |
| I-4 | STILL OPEN | `StrategyTreasuryBase.wire:199-205` never rejects `key.hooks == 0`, and `hook != 0` is still the wired sentinel (`:201`) |
| I-5 | STILL OPEN | `PriceOracle._read:82-87` has no `minAnswer`/`maxAnswer` clamp check |
| I-6 | STILL OPEN | `StrategyFactory.list:300-305` still checks only pool canonicality and `oracle.stock()`; `PoolTrader:57`'s `cardinality >= 660` is unmirrored |
| I-7 | STILL OPEN | `Launched` (`:208`, emitted `:402`) still carries no economic term. Mitigated: `terms` is now in `launch`'s calldata, so it is recoverable from the transaction |
| I-8 | STILL OPEN | `StrategyTreasury.sol:35-42` still rejects the creator's half in a constructor; now surfaces as the named `TreasuryDeployFailed()` (`StrategyFactory.sol:59`) rather than a string |
| I-10 | STILL OPEN | `StrategyFactory.sol:462` still the one raw `IERC20.transfer`; still safe for the same reason |
| I-11 | CHANGED SHAPE | `listV4` half **moot**; `_SCALE` half still open — `StrategyTreasury.sol:32` computes it with no guard against `usdgDec > 18 + stockDec` |
| I-12 | STILL OPEN | `BUYBACK_TWAP_WINDOW = 600` (`:101`) still ten times `buybackCooldown`'s shipped value, and the cap is still cumulative against the mean (`:561-567`) |
| I-13 | STILL OPEN | fee model unchanged; buying still pays the protocol nothing (`StrategyHook.sol:357-358` burns the token leg) |
| I-14 | STILL OPEN | `docs/SECURITY.md:639` still states "time-averaged sell tax 27.8% against 10% flat" |
| I-15 | CHANGED SHAPE | `PoolTrader._swapForExit` is **gone**; `TradingCalendar.nextOpen:172` / `nextClose:180` still have **zero** consumers anywhere, tests included — EXECUTED grep |
| I-16 | STILL OPEN | the accounting still holds; the number moved — `TreasuryDeployer` is 23,609 with **967 B** margin — EXECUTED (`forge build --sizes`) |
| I-17 | STILL OPEN | every `vm.createSelectFork("publicnode")` (11 sites) is still unpinned — EXECUTED grep |
| I-18 | STILL OPEN | `foundry.toml` has no `via_ir` key; 967 B on `TreasuryDeployer` makes it a more tempting lever than it was at 2,158 |

---

## WORSE, in full

### F-14 · the suite's result is still a function of the checkout path, the cause is now a concrete bug, and round 1's confirmed fix no longer works

**State** WORSE. **Status** EXECUTED — four full suite runs at two byte-identical checkouts, forge 1.8.1.

**Location** `test/InteractRuleMev.t.sol:152-153`; `foundry.toml` (still no `bytecode_hash`);
`test/AuditRouterRound4.t.sol:83-90` and `test/InteractFactory.t.sol:919-926` (both round-1 brute-force
helpers survive verbatim); `test/LaunchRouter.t.sol:88` (the author's change).

**What the author changed, exactly.** One line, in one test. `test/LaunchRouter.t.sol:88`:

```solidity
for (; (factory.predictToken(q2) < address(stockA)) != (tok1 < address(stockA)); q2.nonce++) {}
```

That mines a nonce until the second token lands on the **same side** of the stock as the first, so the
5-wei rounding difference between the two orderings cannot break the exact equality at `:92`. It closes
**that one test's reproduction** and nothing else. It is itself another brute-force search over a predicted
CREATE2 address — the pattern F-14 said was the disease — and it is unbounded (no iteration cap, no
assertion that it found anything).

**What it does not close, and this is the finding.** `foundry.toml` still sets no `bytecode_hash`, so
`type(StrategyToken).creationCode` still carries a CBOR metadata hash of the source **paths**, and every
predicted CREATE2 address still moves with the checkout directory. Both of round 1's other two
reproductions are untouched: `revert("no nonce")` at `test/AuditRouterRound4.t.sol:90` and
`revert("no ordering")` at `test/InteractFactory.t.sol:926`.

**And the rewrite added a new, worse member of the class.** `StrategyToken`'s constructor took four
arguments at `9a291aa`; the singleton release gave it a fifth (`address creator`, `StrategyToken.sol:59`).
Three of the four test helpers that predict its address were updated. The fourth was not:

```solidity
// test/InteractRuleMev.t.sol:152-153   — FOUR arguments
bytes32 h = keccak256(abi.encodePacked(type(StrategyToken).creationCode,
    abi.encode("Strategy", "STR", uint256(1_000_000_000e18), address(this))));
...
// :156 — deployed with FIVE
return new StrategyToken{salt: bytes32(i)}("Strategy", "STR", 1_000_000_000e18, address(this), address(0));
```

`h` is not the init-code hash of what gets deployed, so `vm.computeCreate2Address` answers an address
unrelated to where the token lands. The mining loop at `:154-158` therefore picks a salt against noise and
the token's side of the stock is a **coin flip**, decided by the metadata CBOR — i.e. by the checkout path.
When the flip goes the wrong way, `tokenKey` is built with `currency0 >= currency1` and `pm.initialize`
reverts inside `setUp()`.

That is strictly worse than round 1's three cases in three ways:
1. **It is in `setUp()`**, so it does not fail one test — it silently removes a whole contract's tests from
   the run. The totals move with no comment. This is exactly BASELINE2's "22 tests did not execute at path
   B at all".
2. **`bytecode_hash = "none"` does not fix it.** Round 1 verified that one-line change green in the
   directory that was red. At `0e39f69` it only re-rolls the dice — measured below.
3. **It lands on `InteractRuleMev.t.sol`**, which is both the both-currency-orderings suite (the class
   `CLAUDE.md` records as "shipped twice") and the file round 1's tests lane called the best work in the
   repo, for `_shrink` coverage. Round 1's safe-list entry "the `_shrink` swap-and-pop is genuinely well
   tested" is therefore conditional on an address lottery.

**Measurements** (EXECUTED, forge 1.8.1, `--no-match-path 'test/*Fork*'`, two byte-identical copies with
`lib` symlinked, at `…/disp-scratch/pA` and `…/disp-scratch/pB_longer_path_here`):

| configuration | path A | path B |
|---|---|---|
| as shipped | 1125 passed / **4 failed**, 1130 ran. `CurrenciesOutOfOrderOrEqual(0x7557…, 0x3778…)` in `InteractRuleMevInvariantTest.setUp()` | 1125 / **4**, 1130 ran. Same failure, **different addresses** `(0xDbf7…, 0x834f…)` |
| `+ bytecode_hash="none", cbor_metadata=false` | 1103 passed / **4 failed**, **1108 ran** — the failure **moved** to `InteractRuleMevBTest.setUp()` and **22 tests disappeared** | — |
| `+` the one-argument fix at `:153`, no `foundry.toml` change | **1126 / 3, 1130 ran** | **1126 / 3, 1130 ran** — identical sets, identical gas |

**Fix** Two, and both are needed.
(a) `abi.encode("Strategy", "STR", uint256(1_000_000_000e18), address(this), address(0))` at
`test/InteractRuleMev.t.sol:153`. **Verified green at both paths, by me.** One argument. No contract bytes.
(b) `bytecode_hash = "none"` and `cbor_metadata = false` in `[profile.default]`. This is still the right
root fix — for reproducible verified bytecode, and because the two `revert("no …")` search loops remain —
but note it is **no longer sufficient on its own**, and applying it alone at `0e39f69` makes the run
*smaller* without saying so. Apply (a) first.
Independently: both search helpers should assert rather than `revert` with a string, and the new loop at
`test/LaunchRouter.t.sol:88` should have a bound.

**Both remaining failures are toolchain, not product — EXECUTED, and this answers BASELINE2's open question.**
- `test_holds_statefulCampaigns_…` (`test/AuditRound6Treasury.t.sol:171`) fails `MemoryOOG` / `Revert` at
  gas `1,073,720,xxx` — one thousandth under forge's default per-test limit of 2^30. Re-run with
  `--gas-limit 90000000000 --memory-limit 4294967296` it **passes in both orderings**, needing
  1,434,554,490 and 1,434,977,660 gas. The test outgrew the default budget; nothing about the contracts is
  wrong. Fix: raise `gas_limit` in `foundry.toml` or cut the campaign count at `:172`.
- `test_holds_isolationIsReal_a_…` (`test/AuditRound5Tax.t.sol:434`) is a **negative control on the
  harness**, not on the product: it asserts that *without* `isolate` the transient launch-exemption words
  leak into a later top-level call. On forge 1.8.1 they no longer do, so the launcher reads `SNIPE` (9900)
  where the test expects `TAX` (1000). Its sibling `…_b_` (`:445`, `isolate = true`) — the one that
  asserts the *product's* guarantee — **passes**. This is transient-storage-clearing semantics changing
  between forge 1.5.0 and 1.8.1. The control is now vacuous and should be rewritten or deleted; no product
  claim moves.

---

### F-23 · the bind race now includes the mined hook address

**State** WORSE. **Status** EXECUTED (source read) + REASONED for the escalation.

**Location** `StrategyFactory.sol:45-48` (`bind()`, still no access control), `:238-240` (the constructor
binds **three**: `treasuryDeployer`, `tokenDeployer`, **and `hook`**), `StrategyHook.sol:183-187`
(`bind()`, likewise open), `StrategyHook.sol:175` (`uint160(address(this)) & 0x3FFF != 0x2844`).

**Mechanism, unchanged** A stranger calls `bind()` on any of the three before the factory's constructor
does; the constructor reverts `AlreadyBound` and the deployment must start again.

**What got worse.** At `9a291aa` the squattable objects were two (later three) stateless deployers: round 1
priced the grief at "the gas of three redeploys per attempt". At `0e39f69` one of them is the **hook**, and
the hook's address is not fungible:

1. Its low 14 bits must be exactly `0x2844` (`StrategyHook.sol:175`), so replacing it means **re-mining** a
   CREATE2 address, not just sending another transaction.
2. `StrategyHook.sol:54-58` states the reason the hook is a singleton at all: *"Uniswap Labs' routing
   allowlist is per hook ADDRESS, and a hook carrying a returns-delta flag is reviewed one address at a
   time."* `AUDIT.md:172-174` makes it a launch step: *"deploy and bind before submitting the hook for
   routing"*. So a squat that lands between deployment and the factory's constructor burns an address that
   may already be in a third party's review queue — a cost measured in that queue's latency, not in gas.
3. The `forge script` shape round 1 identified is unchanged: `script/DeployStrategyLaunchpad.s.sol` still
   `new`s the helpers and the factory inside one `broadcast`, which `forge script` submits as separate
   transactions.

**Impact** Loser: the **team**, repeatably, and now with a schedule dependency on an outside reviewer. No
user funds. Certain gain 0, option gain 0.

**Fix** Unchanged and now more clearly worth it: deploy the three helpers and the factory from one helper
contract's constructor, so no block boundary exists between them; or give `bind()` a deployer-set expected
factory. Neither touches `StrategyFactory`'s 5,626 B or `StrategyHook`'s 6,214 B. At minimum the runbook
must state it, and must state it for the hook specifically.

---

### F-03 · the constant did not change; only the values an owner is now instructed to set

**State** WORSE (on reachability, not on mechanism). **Status** EXECUTED.

**The client's question, answered directly: the constant did not change.**
- `src/str/StrategyTreasuryBase.sol:109` — `uint256 public constant MAX_BAND_BPS_PER_HOUR = 200;`
- `src/str/StrategyFactory.sol:265` — `if (bps > 200) revert BadRequest();`
- `src/str/StrategyTreasury.sol:47` — `MAX_BAND_BPS = 3000` for the cap.
- `git show --stat 19d3faf` touches **`docs/` only** — `docs/DEPLOYMENT.md`, `docs/ROADMAP.md` and four
  CSV/PNG band reports. **Zero `src/` changes.** (EXECUTED.)

So `19d3faf` sets per-stock *values* an owner is told to pass, inside a ceiling that still permits 20× the
largest of them.

**And the depth table is not corrected.** The number the ceiling's own source comment cites is still there,
in five places, verbatim (EXECUTED grep):

| file:line | text |
|---|---|
| `src/str/StrategyFactory.sol:261-262` | "NVDA takes $54M to walk 30%, AMD $309k" |
| `AUDIT.md:259` | the whole D30 table, "NVDA $54M, SGOV $102M" |
| `LISTING_CANDIDATES.md:39` and `:48` | "NVDA ~$54M …", "**NVDA** ✔ $54M ✔ **first**" |
| `docs/DEPLOYMENT.md:641` | "roughly $54M (NVDA), $13M (SPCX), $5.9M (AAPL), $3.9M (GOOGL)" |
| `docs/REFERENCE.md:277` | the factory comment, mirrored into the generated reference |

Round 1's exact tick-walk put NVDA at **$2.33M**. Nothing in the repository reflects that.

**Why this is WORSE rather than STILL OPEN.** Round 1's condition 1 — *"`bandCeiling` is zero for every
stock today, and this is the gate that makes the finding inert"* — was the reason F-03 was not top of the
urgency table. `19d3faf` converts that gate into a documented, scripted pre-launch action: bands are to be
set on CRCL (10 bps/h), USAR / GME / AMZN / META (5). The mitigating fact round 1 relied on is being
deliberately removed.

Two smaller things, both worth one line in the runbook:
- The values chosen (5–10 bps/h) are **inside round 1's recommended `MAX_BAND_BPS_PER_HOUR = 10`**. The
  measurement discipline in `19d3faf`'s message ("availability saturates at once and a larger band buys
  only a wider pin") is exactly round 1's argument. The gap is entirely between practice and the constant.
- `script/DeployStrategyLaunchpad.s.sol:271` still instructs `setBandCeiling(stock, 25)` for "DEEP POOLS
  ONLY (NVDA, AAPL, GOOGL: > $3M to walk 30%)" — a **third** number, contradicting both `19d3faf`'s 5–10
  and the `$3M` threshold it cites, which is itself below the corrected NVDA figure of $2.33M.

**Fix** Unchanged: `MAX_BAND_BPS_PER_HOUR = 10` (a changed literal, no byte cost) and `if (bps > 10)` at
`StrategyFactory.sol:265` (a changed literal, no net bytes). Then correct the five documents and the
script's `25`.

---

### F-33 · fourteen of twenty-two defaults are never printed, and the mislabelled line is verbatim

**State** WORSE. **Status** EXECUTED (read `:258-264` against the `Defaults` struct at
`StrategyFactory.sol:152-175`).

`Defaults` grew from 19 fields to 22 — `snipeBps`, `snipeSeconds`, `sellChunkUsdg` — and the read-back
block did not grow at all. It still prints `supply`, `lpFee`, `minTaxBps`, `maxTaxBps`, `protocolBps`,
`maxCreatorBps`, `launchFeeCurrency`, `launchFeeAmount`, `publicLaunch` — eight values plus the boolean.

**Not printed (14):** `tickSpacing`, `spikeBps`, `spikeSeconds`, `sweepTipBps`, **`snipeBps`**,
**`snipeSeconds`**, `bountyBps`, `maxSlippageBps`, `maxDeviationBps`, `maxBuybackImpactBps`,
`buybackCooldown`, `minLotUsdg`, `buybackChunkUsdg`, **`sellChunkUsdg`**.

Every silent kill switch in F-05 is still in that list, and two of the three new fields are new kill
switches of the same kind: `snipeBps` is a **99% buy tax** (`StrategyHook.sol:138`, `MAX_SNIPE_BPS = 9900`)
and `sellChunkUsdg` is upper-unbounded. Neither is printed. The line round 1 flagged as mislabelled is
unchanged to the character:

```solidity
// script/DeployStrategyLaunchpad.s.sol:259
console2.log("supply / lpFee / tickSpacing:", factory.getDefaults().supply, factory.getDefaults().lpFee);
```

Three names, two values, `tickSpacing` printed nowhere in the script. An operator following the script's own
"read the printed plan, then sign it yourself" still believes they verified it.

**Fix** Print all twenty-two and fix the label. Script only, no byte budget.

---

### F-39 · the unmirrorable floor now has a second lever

**State** WORSE. **Status** EXECUTED (source read; round 1's PoC path re-read against the new code).

**Location** `StrategyTreasury.sol:42` (`if (p.tp1Bps < 2*(p.maxSlippageBps + poolFeeBps) || p.dipBps < …)
revert BadConfig()`), against `StrategyFactory._setDefaults:246-258`; the new lever at
`StrategyFactory.setListingGates:276-279`; the failure at `TreasuryDeployer.deploy:61-66`.

The root is unchanged: the floor depends on a creator input (`tp1Bps`), a default (`maxSlippageBps`) **and**
the listed pool's fee, so `_setDefaults` cannot mirror it and does not. Raising `maxSlippageBps` from 100 to
300 still moves the floor from 260 to 660 bps and still kills every pending launch with `tp1Bps < 660`.

**What got worse.** `setListingGates(stock, dev, slip, chunk)` is a **second** way to move `maxSlippageBps`,
per stock, and its only validation is `_gatesOk` (`:280`: `slip <= 300 && dev != 0 && dev < slip`) plus
`chunk >= defaults.minLotUsdg`. It is checked against nothing pending. So the owner now has two independent
levers onto the same unmirrored floor, and the per-stock one is the one the runbook expects to be used often.

**One thing got better, and it is worth recording.** The failure is now the named custom error
`TreasuryDeployFailed()` (`StrategyFactory.sol:59`, selector `0xb94a14a6`) instead of
`require(a != address(0), "treasury deploy")`. It is still opaque about *which* of two dozen numbers it was
— FA-4's original complaint — but it is at least decodable.

**Note on ordering, because it changes the diagnosis.** `_launch` deploys the treasury at `:396` and only
then checks `terms` at `:397`. So a `setListingGates` that lands between a `predict` and a `launch` and
happens to break the floor fails as `TreasuryDeployFailed` — **not** as the `Restated` that the `terms`
mechanism exists to produce. Swapping those two lines would turn most of this class into a clear error for
free. (REASONED; not run.)

**Fix** Move the floor check into `launch()` with a named error (~40 B against the factory's **5,626 B**,
which is now comfortable where round 1's 945 B was not), and/or reorder `:396`/`:397`.

---

### F-31 · one hook address, one deny-list entry, every strategy

**State** WORSE. **Status** REASONED, from the hook's own source and the issuer powers in
`docs/STOCK_TOKEN_ASSESSMENT.md`.

**Location** `StrategyHook.sol:56-59` (the hook says this itself), `:668-673` (`payStock`), `:586-595`
(`_pot`), `:599-615` (`_square`); `docs/SECURITY.md:60-71`.

Round 1's F-31 was "the issuer's pause is the only halt that shuts a holder's exit". That is still true and
the mitigation is still real (`TradeRouter.sell:87-90` takes the stock to itself, so a deny-listed
*individual* still exits; a pause blocks the router's leg too).

**What the singleton adds.** The hook's own header states it: *"tax claims and parked stock of different
pools now sit at one address … an issuer who deny-lists THIS address stops every strategy's stock leg at
once."* That is a real, one-transaction, third-party kill switch over the **whole launchpad's** stock-side
revenue, where at `9a291aa` it was one launch at a time. The code is honest about it; `docs/SECURITY.md`
is not — `:71` still reads *"A blocked PoolManager, treasury or hook, or a paused token, **recovers
fully** when [lifted]"*, which is true of the *ledger* (the `owed`/`parked` bookkeeping survives and
`claim(id, to)` pays elsewhere) and says nothing about the scope.

**And the pot is shared.** `pots[stock]` (`:423-424`) is one record per **stock**, not per pool. `_pot:590`
reads `IERC20(stock).balanceOf(address(this))` and, if the balance is short of `parked`, `_square:599-615`
lowers the index for **every pool on that stock**. Pro rata is the correct response — but round 1 cleared
this ledger partly *because* it was per-hook, and the clearance no longer covers the blast radius: one
issuer `adminBurn` against the hook now writes down parked claims belonging to strategies that have nothing
to do with each other. `MIN_INDEX = 1e9` (`:430`) turns a large enough burn into an epoch bump that zeroes
every parked claim on that stock at once (`:593`, `:607-609`).

**Fix** No code fix is available (this is the price of the routing allowlist, and the trade is defensible).
Two sentences in `docs/SECURITY.md`: that a deny-list on the hook address stops every strategy's stock leg
simultaneously, and that an issuer burn against the hook is shared pro rata across every pool on that stock.

---

### I-9 · a fee-on-transfer or rebasing stock now mis-values a shared pot

**State** WORSE. **Status** REASONED.

Round 1 recorded I-9 as a **requirement on the listed asset**: V4 settlement assumes `paid == delta`, so a
transfer fee bricks `buyback()`, both `TradeRouter` legs and `LaunchRouter`'s first buy simultaneously, and
a rebase desyncs the treasury's `bookedStock`/`buybackStock`.

All of that still holds (`StrategyTreasuryBase.sol:518-520`, `TradeRouter.sol:144-146`,
`LaunchRouter.sol:123-125`). What is new is the hook side: `_pot` (`StrategyHook.sol:586-595`) now derives
a write-down index from `balanceOf(hook)` against `parked`, and that pot is **shared across every pool on
the stock**. A negative rebase is indistinguishable from an issuer burn and is applied to all of them; a
positive rebase lands in the "nobody's" band described at `:419-420` and is unreachable forever.

The repository's own note that the stock is a beacon proxy one address can upgrade with no timelock
(`docs/STOCK_TOKEN_ASSESSMENT.md`, cited at `StrategyTreasuryBase.sol:299`) is what makes this a live
requirement rather than a hypothetical. It is unchanged, and the consequence of breaking it is now
protocol-wide.

**Fix** Documentation, plus the fork test `AUDIT.md:606` (blocker 7 / TR-5) already asks for and which is
still open.

---

## STILL OPEN, in full

The twenty-eight findings and fourteen Infos above are open with the evidence in the table. The ones the
client named, and the ones where I have something to add beyond "unchanged", are below. The rest are
unchanged at the cited lines and need no further text.

### F-05 · `_setDefaults` and the new `register` check — all three boundaries re-verified

**State** STILL OPEN. **Status** EXECUTED (both validation blocks read line by line).

**The two blocks, in full.**

```solidity
// StrategyFactory.sol:246-258
function _setDefaults(Defaults memory d) internal {
    if (d.supply == 0 || d.minTaxBps > d.maxTaxBps || uint256(d.protocolBps) + d.maxCreatorBps > 1e4) revert BadRequest();      // :247
    if (d.maxTaxBps > 1500 || d.spikeBps > 9000 || d.sweepTipBps > 100 || d.bountyBps > 200 || d.snipeBps > 9900) revert BadRequest();
    if (!_gatesOk(d.maxDeviationBps, d.maxSlippageBps)) revert BadRequest();
    if (d.maxBuybackImpactBps == 0 || d.maxBuybackImpactBps > 1000 || d.minLotUsdg == 0 || d.buybackChunkUsdg == 0 || d.sellChunkUsdg < d.minLotUsdg) revert BadRequest();
    if (d.lpFee != 0 || d.tickSpacing < 1) revert BadRequest();
    defaults = d; emit DefaultsSet(d);
}

// StrategyHook.sol:196   — the new `register` check the client asked about
if (r.taxBps > MAX_TAX_BPS || r.spikeBps > MAX_SPIKE_BPS || uint256(r.protocolBps) + r.creatorBps > 1e4
    || r.sweepTipBps > MAX_TIP_BPS || r.snipeBps > MAX_SNIPE_BPS) revert BadConfig();
```

**What `register:196` adds over the old per-launch hook constructor: nothing that closes F-05.** It is the
same five bounds, moved from a constructor (whose revert reason died in CREATE2) to an `onlyFactory`
external call (whose reason survives). That is a real improvement in *diagnosis* and the comment at
`StrategyFactory.sol:250-251` says so honestly. It is not a new bound.

**Round 1's eight unbounded fields, re-checked one by one:**

| field | round-1 state | at `0e39f69` |
|---|---|---|
| `spikeSeconds` (uint32) | no check anywhere | **no check anywhere.** Not in `_setDefaults`, not in `register:196`. Round 1's recommended mirror was not added. `_sellRate:300-307` decays identically, so `spikeSeconds = type(uint32).max` still gives ~90% for 136 years |
| `buybackCooldown` (uint32) | none | **none** |
| `protocolBps` | only the `> 1e4` sum | **only the `> 1e4` sum** — see below |
| `minLotUsdg` | `!= 0` | `!= 0` at `:254`, upper still unbounded |
| `sweepTipBps` | `> 100` only, so 0 accepted | `> 100` only, 0 accepted. `sweep(PoolId)` at `:438` is still permissionless and still has **no caller in `src/`** |
| `bountyBps` | `> 200` only, 0 accepted | `> 200` only, 0 accepted |
| `minTaxBps` | `<= maxTaxBps` only, 0 accepted | `<= maxTaxBps` only, 0 accepted |
| `tickSpacing` / `supply` | `>= 1` / `!= 0` | `>= 1` / `!= 0` |

**Plus one new field of the same kind:** `sellChunkUsdg` is checked only `>= d.minLotUsdg` (`:254`) with no
upper bound. An oversized chunk no longer bricks a sale (partial fills, F-09), so its consequence is
bounded at "about half the slippage per call" — the source says so at `StrategyTreasuryBase.sol:76-81`.
Recorded for completeness, not as a brick.

### The 100% split — all three comparisons, and the answer is now *exactly* zero

**State** STILL OPEN. **Status** EXECUTED (three comparisons read) + REASONED (the arithmetic, which is
exact integer division and needs no run).

The three places the split is bounded, all non-strict at the boundary:

1. `StrategyFactory.sol:247` — `uint256(d.protocolBps) + d.maxCreatorBps > 1e4` → **`== 1e4` is legal**.
2. `StrategyFactory.sol:389` — `q.creatorBps > d.maxCreatorBps` → a creator may take the whole ceiling.
3. `StrategyHook.sol:196` — `uint256(r.protocolBps) + r.creatorBps > 1e4` → the mirror, likewise strict.

So `protocolBps + creatorBps == 1e4` reaches `settleStock` (`StrategyHook.sol:508-511`):

```solidity
uint256 tip  = s * p.sweepTipBps / 1e4;
uint256 cut  = (s - tip) * p.protocolBps / 1e4;
uint256 mine = (s - tip) * p.creatorBps  / 1e4;
uint256 toTreasury = s - tip - cut - mine;
```

At `protocolBps = 10000, creatorBps = 0`: `cut = s - tip`, `mine = 0`, **`toTreasury = 0` exactly.** Round
1 said "≤ 1 wei"; the singleton's split arithmetic makes it a clean zero at that corner, and 0 or 1 wei
elsewhere on the boundary (e.g. 5000/5000 leaves `(s-tip) mod 2`). `README.md` still promises "the
remainder to the treasury".

This is frozen at launch — `p.protocolBps` / `p.creatorBps` are written once in `register:205` and there is
no setter — so every strategy launched under such a default is permanently a token whose treasury receives
none of the sell tax while the page says otherwise.

**Fix** Make one of the three strict, or put a real bound on `protocolBps`:
`if (d.protocolBps > 5000) revert BadRequest();` at `StrategyFactory.sol:247`. The factory now has
**5,626 B** of margin (it had 945 at round 1), so round 1's §5.12 "the whole factory-side fix set must be
written and sized in one build" is no longer a real constraint — the whole F-05 block plus F-06's and
F-17's fits several times over. **The binding budget is `TreasuryDeployer`'s 967 B** (EXECUTED,
`forge build --sizes`), which is where F-04's, F-06's, F-10's, F-13's, F-20's, F-21's and F-40's fixes land.

### F-06 · `maxBuybackImpactBps` below ~20 still bricks the buy-back

**State** STILL OPEN. **Status** EXECUTED (acceptance path) + REASONED (the arithmetic, unchanged).

Both surviving validators still test `== 0 || > 1000` and neither requires `>= 2`, let alone `>= 20`:
- `StrategyFactory.sol:254` — `d.maxBuybackImpactBps == 0 || d.maxBuybackImpactBps > 1000`
- `StrategyTreasury.sol:38` — `p.maxBuybackImpactBps == 0 || p.maxBuybackImpactBps > 1000`
(the third, `StrategyTreasuryV4.sol:68`, is gone with the V4 venue.)

`_buybackLimitSqrtP:553` still computes `uint256 half = uint256(_params.maxBuybackImpactBps) / 2`, so at 1
`half == 0` and `fromSpot == sqrtP` exactly. Both branches then end in `_clampToSpot:584-586`, which
returns `sqrtP ± 1`:
- ring serves (`:562-567`): `bound = max/min(fromMean, fromSpot)`; whichever wins, the clamp fires.
- ring does not serve (`:570-578`): `drift = half * (1 + …) = 0`, `anchored == anchor`, same clamp.

A limit one wei past spot fills nothing, `spent == 0`, and `:476` — the new dust floor — turns it into
`NotDue` rather than the old zero-fill path. Same outcome, reached one line earlier. Every buy-back,
forever; `buybackStock` accrues dead and `totalBurned` stays at zero.

CL-2's correction stands: the effective floor is ~20, not 2, because at 2 or 3 `half == 1` is one basis
point of *sqrt* — inside one tick at most spacings.

**Fix** Unchanged and still the cheapest in the set: change `== 0` to `< 20` at `StrategyFactory.sol:254`
and `StrategyTreasury.sol:38` — a replaced comparison, **no net bytes**, and the factory has 5,626 B either
way. Better: compute the limit as `mulDiv(sqrtP, 2e4 ± maxBuybackImpactBps, 2e4)` at `:554`/`:564` so odd
values cannot truncate — a few bytes against `TreasuryDeployer`'s **967 B**.

### F-07 · `noteEvent`'s `2 × spikeSeconds` re-arm bound

**State** STILL OPEN, verbatim. **Status** EXECUTED (read).

```solidity
// StrategyHook.sol:269-273
function noteEvent() external {
    Pool storage p = _mine();
    if (block.timestamp < p.lastEventAt + 2 * uint256(p.spikeSeconds)) return;
    p.lastEventAt = uint40(block.timestamp);
}
```

Unchanged but for the `uint256` cast and the per-pool lookup. `_sellRate:300-307` returns `taxBps` once
`dt >= secs`, so the unprotected share is still `spikeSeconds / (2 × spikeSeconds)` = **exactly one half**,
independent of every parameter, and a seller still chooses which half by calling `buyback()` themselves at
T and selling at T+`spikeSeconds`. `buyback()` is still permissionless (`StrategyTreasuryBase.sol:453`) and
still calls `noteEvent()` last (`:486`).

Two second-order notes:
- `register:205` now sets `p.lastEventAt = block.timestamp`, so the launch itself arms the spike — which is
  the property round 1's safe-list credited ("the sell spike's clock starts at deployment"). It survives.
- `docs/SECURITY.md:638` still documents the `2 × spikeSeconds` re-arm and `:639` still states the 27.8%
  time-averaged figure I-14 re-graded down by two orders of magnitude. Both unchanged.

### F-04 · a dead oracle still freezes the treasury, and the new paths do not add an exit

**State** STILL OPEN. **Status** EXECUTED — I re-ran the outflow enumeration the client asked for.

`grep -n "safeTransfer|\.transfer\(|poolManager.take|settle\(\)|forceApprove|approve\("` over
`StrategyTreasuryBase.sol`, `StrategyTreasury.sol` and `PoolTrader.sol` returns **exactly nine lines**:

| line | what |
|---|---|
| `StrategyTreasuryBase.sol:377` | `takeProfit` bounty, in stock |
| `StrategyTreasuryBase.sol:402` | `stopLoss` bounty, in USDG |
| `StrategyTreasuryBase.sol:424` | `buyDip` bounty, in USDG |
| `StrategyTreasuryBase.sol:482` | `buyback` bounty, in the strategy token |
| `StrategyTreasuryBase.sol:519-520` | the V4 buy-back's `sync`/transfer/`settle` |
| `StrategyTreasuryBase.sol:521` | `poolManager.take` — **into** the treasury |
| `PoolTrader.sol:147-148` | the V3 swap callback |

There is no owner withdrawal, no rescue, no proxy. `setVoteDelegate` (`:228-233`) is the only new owner
power and it makes one `try`ed `delegate(address)` call, writes no storage and moves nothing — its own
docstring is accurate.

The four value-moving entry points are all gated on `health()`: `_book:305`, `takeProfit:331`,
`stopLoss:383`, `buyDip:406`. `buyback:460-465` is still the sole exception and still only for sizing: it
tries `tryPrice()`, falls back to `lastGoodPrice`, and reverts `Unhealthy` once that is over
`MAX_SIZING_AGE = 5 days` (`:105`). `lastGoodPrice` is still written only by `_notePrice:255`, called only
from the four gated functions — so the cache still ages from the last **rule action**, not the last oracle
print.

**The two new mechanisms the client asked about do not change this.** `sellChunkUsdg` and partial-fill
sells change *how much* a sale moves, not *whether* it is reachable: `takeProfit:331` and `stopLoss:383`
still revert `Unhealthy` first. `_poolOnlyPace:278-282` only adds a further refusal.

So the conclusion is unchanged and EXECUTED rather than REASONED this round: once `tryPrice()` is
permanently false, five days later **100% of `bookedStock + buybackStock + reserveUsdg` is frozen
forever**, with no actor gaining anything.

**Fix** Unchanged: denominate the buy-back chunk in stock (`buybackChunkStock`) so `buyback` needs no stock
oracle at all — its execution price is already bounded by the token pool's own 600 s mean, which has
nothing to do with Chainlink. A struct field swap plus two changed expressions at `:466` and `:476`, against
`TreasuryDeployer`'s **967 B** (not round 1's 2,158 — the budget more than halved, so this must be sized
before it is written).

### F-02 · the calendar override, and F-41 · `AUDIT.md`'s ledger

**State** both STILL OPEN, both verbatim. **Status** EXECUTED.

F-02: `TradingCalendar.sol` is byte-identical at every line round 1 cited — the header claim at `:15-16`
("an override can only ever stop trading, never widen what trades"), `setOverride`'s `require(mode <= 2)`
at `:29`, `dateClosed`'s `if (o == 2) return false;` at `:130-135`, the contradictory second claim at
`:143`'s docstring ("The owner can stop the rule trading, and cannot change what price it trades at"),
`isScheduledClosure:157-160` and `isClosed:163`. `PriceOracle.tryPrice:51` still asks `isClosed`.
`git diff 9a291aa..0e39f69 -- src/TradingCalendar.sol` is two lines.

The rubric's third High clause is still triggered, at the same two lines one row apart:
- `docs/SECURITY.md:36` — the **"It cannot"** column: *"change the price the rule trades at, or open the
  closed-market path"*.
- `docs/SECURITY.md:37` — the **"It can"** column: *"force a day **open** (`setOverride(day, 2)`)"*.
- `docs/SECURITY.md:572` — the section heading *"The calendar owner can halt and only halt"*.

One small improvement: `:37` now adds *"the live-feed path then applies, behind the 48 h age cap and the
deviation gate"*, which is an accurate description of what mode 2 does. The promise at `:36` is unchanged,
so the contradiction — and the grade — stand.

F-41: `AUDIT.md:206` still reads *"blockers 5 (the calendar owner, FA-1 / TR-6), 8 … and the rest of HK-4
are **fixed** on `fix/audit-pre-launch-2`"*, and `:604` still carries blocker 5's own row offering the three
options of which the third (accept and correct the README) is what shipped. One word in a status header,
still wrong, and it is the row a go/no-go reader checks.

### F-09 / F-36 / F-34 · what the partial-fill rewrite did close

**State** CHANGED SHAPE. **Status** EXECUTED (source read).

The rewrite genuinely closed one half of F-09 and one half of F-36, and it is worth being precise about
which half, because the other half is untouched.

**Closed — the oversized-lot brick.** At `9a291aa` a sale demanded a full fill
(`requireFull = !buy`, `PoolTrader.sol:138` `if (requireFull && spent != amountIn) revert PartialFill`) and
`_book` made the whole unbooked balance one `Lot`, so a lot larger than the pool's depth inside
`maxSlippageBps` was **permanently unsellable** and a stranger could freeze the pile with a marginal
donation. Now:
- `takeProfit:335` offers at most `sellChunkUsdg` worth, and `:367` adjusts the lot by what actually sold:
  `if (sold != principal) { principal = sold; q = Math.mulDiv(sold, p, cost); }`
- `stopLoss:393` does the same, with the R5-1 `tp1Left` clamp at `:394`.
- `PoolTrader._swapBounded:126-133` no longer takes a `requireFull` flag at all; a short fill meets the same
  average-price floor a full one does.

The grief — donate the marginal difference, call `book()`, freeze the pile — is closed at its mechanism, not
just at round 1's reproduction. Same for F-36's sell side.

**Open — everything else in F-09.** `book()` (`:300-314`) still pays **no bounty** while all four other
rule calls do (`:377`, `:402`, `:424`, `:482`); `_book:303` still takes the **whole** `unbookedStock()` as
one lot; whoever calls still picks which healthy Chainlink print becomes that lot's permanent cost; and the
only automatic booking is still `_book()` inside `takeProfit:333`, which by construction runs at a local
high. Round 1's cost-basis half is untouched.

**Open — F-36's buy side.** `buyDip:409` still spends `reserveUsdg() * lotBps / 1e4`, still refuses a
sub-`minLotUsdg` fill at `:419`, and `:422` still ratchets `lastSalePrice = p` after **any** dip, so the
reserve still cannot be topped into the same rung.

**F-34** is CHANGED SHAPE for a different reason: `setListingGates` (`StrategyFactory.sol:276-292`) is
exactly round 1's recommendation to publish and set the gates per listing, and `_gates:284-292` is the one
place they are read. `MAX_SLIPPAGE_BPS = 300` and the depth instability are unchanged.

### F-15 · the treasury's assertions are unchanged, though the suite tripled

**State** STILL OPEN. **Status** EXECUTED (grep against round 1's named sites).

The suite went from 620 tests to 1,130 and round 1's specific diagnosis is untouched. The single assertion
round 1 named as the reason the one-wei `buybackStock` mutant survived —
`assertGe(balance, booked + buyback)`, an inequality in the one direction the bug moves — is still an
`assertGe` at every site: `test/InteractRuleMev.t.sol:268` and `:1072`,
`test/InteractVenueParity.t.sol:345`, `test/SellChunk.t.sol:43`. Fix #1 on round 1's list was not taken.
Fix #6 likewise: `invariant_callSummary` (`test/InteractRuleMev.t.sol:1105`) is still `view` and still
asserts nothing, `runs = 12` at `:1049`, `fail-on-revert = false` at `:1051`.
Fix #7 moved partway: bare `vm.expectRevert()` is down from 29 to **25**.

I did not re-run a mutation harness this round. The claim above is about the assertions round 1 named, not a
fresh survival count.

---

## MOOT, with the reason

- **F-27** — *the V4 `health()` reads spot alone*. `StrategyTreasuryV4.sol` is deleted (−145 lines), and with
  it `TreasuryV4Deployer`, `listV4`, `setV4ListingEnabled`/`v4ListingEnabled`, `Venue`, `Listing.venue`,
  `Listing.v4Key`, `ListedV4` and `V4ListingEnabledSet` (`AUDIT.md:35-39`, and the factory constructor is
  now 8 arguments). There is no venue on which a treasury prices its stock leg off a single V4 spot read.
  The surviving `StrategyTreasury` requires oracle **and** spot **and** the 600 s mean
  (`PoolTrader._health:108-121`), which is the path round 1 called the better one.
  **The `v4ListingEnabled == false` default that made F-27 inert is gone because the feature is gone, not
  because a flag is off** — that is the difference between moot and inert, and it is the good direction.
- **F-30** — *`StrategyTreasuryV4` exposes no getter for its `PriceOracle`*. Same deletion. The surviving
  treasury inherits `PoolTrader`, whose `oracle` is `public immutable` (`PoolTrader.sol:35`), so the
  question round 1 asked ("which oracle prices this strategy?") is answerable on chain for every strategy
  that can now exist.

I checked both rather than assuming: neither string appears anywhere in `src/`.

---

## "Checked and found safe" — re-examined against the singleton

The client is right that a singleton invalidates several of these by construction. I walked every item.
**Five no longer hold as written; ten survive, two of them for a different reason than round 1 gave.**

### Broken or narrowed

1. **"The ledger is kept by ROLE, not by address … `_reconcile` restores `bal >= totalOwed` by writing
   down pro rata."** Round 1 cleared the per-hook ledger partly *because* it was per-hook, and its own
   source said a shared escrow "would hold every creator's stock in one address the issuer can deny-list,
   pause or `adminBurn`". **That is now exactly what exists.** `pots[stock]` (`StrategyHook.sol:423-424`)
   is one record per stock across every pool; `_pot:586-595` derives the write-down index from
   `balanceOf(hook)`; `_square:599-615` applies it to every pool on that stock, with `MIN_INDEX = 1e9`
   (`:430`) escalating to an epoch bump that zeroes all of them (`:593`, `:607-609`).
   **The mechanism is well built** — the write-down runs *before* new revenue is redeemed (`:500`, and the
   comment at `:497-499` gives the measured reason), fresh credits are taken at the current index, and
   donations above `parked` are nobody's and can only stand between parked claims and a burn (`:419-420`).
   I found no arithmetic error. What changed is the **blast radius**, and round 1's clearance did not cover
   it. See F-31 and I-9.
2. **"No assembly in any V4 callback path — every decode is `abi.decode`. The only assembly in scope is the
   three `create2` blocks."** **False at `0e39f69`.** `_buyRate:382` does
   `assembly ("memory-safe") { launching := tload(0) launcher := tload(1) }` and is reached from
   `afterSwap:326 → _tax:343`; `register:210` does the matching `tstore`. Both are `memory-safe`-annotated
   and I could not break them (`tstore` is per-contract so no cross-contract slot collision; a second
   `register` in the same transaction overwrites slot 0 and *removes* an exemption rather than granting
   one; `launching == id && sender == launcher` is conjunctive). But the blanket statement must be
   restated, and raw slots 0/1 are a claim on transient storage that any future code in this contract
   silently inherits.
3. **"The mined hook salt is a complete restatement guard over all nineteen `Defaults` fields — load-
   bearing, accidental, and named nowhere. **It should be written down before someone refactors it away.**"**
   They refactored it away — there is no hook salt any more — **and replaced it deliberately and
   explicitly**: `_terms` (`StrategyFactory.sol:352-356`) hashes `(token, treasury, lpFee, tickSpacing,
   _rates(q,d), launchFeeCurrency, launchFeeAmount)`, checked at `:397`, with the reasoning round 1 asked
   for written into the docstring at `:346-351`. I walked the coverage: `supply`/name/symbol/creator ride in
   the token's CREATE2 address; oracle, v3Pool, the listing gates and all fourteen `Params` ride in the
   treasury's; the eight rates ride in `_rates`; the fee pair is explicit (I-2); `openPriceE18` is restated
   separately at `:391`; and the three remaining fields (`minTaxBps`, `maxTaxBps`, `maxCreatorBps`) are
   bounds on the launcher's own inputs, so moving them can only make the launch revert. **This is the one
   place the rewrite did exactly what round 1 asked.** Recorded prominently because it is the counter-
   example to everything above.
4. **"`StrategyToken` has no owner, no mint, no pause, and a burn restricted to the caller's own
   balance."** Still true of *balances* — `_write:89-97` touches only strings, `burn:64` is
   `_burn(msg.sender, …)`, there is no mint after construction. But the token now has `deployer` (`:34`),
   `launcher` (`:36`), a mutable `editor` (`:39`), `setMetadata`, `setEditor`, `lock` and a factory-only
   one-shot `initMetadata:83-86`. The sentence needs restating: no power over supply, balances or
   allowances; a real power over what the token's page says, held by an address that can be changed.
5. **"No low-integer private keys anywhere in `test/` — no `vm.addr`, no `vm.sign`, no `makeAddrAndKey`."**
   Literally false: `test/AuditRound5Singleton.t.sol:482` and `:487`. **Substantively still safe, and done
   correctly** — the key is `uint256(keccak256("audit round 5: a creator's smart-account key"))`
   (`:481`), which is the exact pattern `CLAUDE.md` prescribes against the EIP-7702 delegation hazard on
   this chain. The clearance should be restated as "every key is keccak-derived", not "there are none".

### Survives, and worth saying so

6. **"With `bandBpsPerHour = 0` no amount of pool manipulation can create or suppress a trigger. The pool
   is only ever a veto, never the price."** Round 1 called this the single most important safety property.
   It **holds byte for byte** at `StrategyTreasury.sol:97-98`:
   `(bool ok0, uint256 p0) = _health(_params.maxDeviationBps); if (ok0 || _params.bandBpsPerHour == 0)
   return (ok0, p0, false);` — and `_health`'s `p` is still Chainlink's (`PoolTrader.sol:109`). EXECUTED.
7. **"No treasury outflow other than the four bounties and swap settlement."** Re-enumerated this round,
   EXECUTED — see F-04. Still exactly nine lines.
8. **"The seed cannot be withdrawn / no third party can add liquidity."** Holds, by a different route:
   `modifyLiquidity` is still one call (`StrategyFactory.sol:459`) with a positive delta, inside
   `unlockCallback` gated `msg.sender == poolManager && _seeding` (`:454`), `_seeding` set only around the
   one `unlock` at `:444-446`, `launch` `nonReentrant`. `beforeAddLiquidity → _onlySeed:224-228` now
   requires the pool to be **registered** and `sender == factory`, where it used to compare an immutable
   `poolId`. Equivalent guarantee, and `register:202` (`AlreadyRegistered`, one pool per treasury) is what
   replaces "exactly one pool per hook".
9. **"Every state-mutating payout entry point is behind the `_distributing` latch."** Holds and was
   extended to the new shape: `sweep:439`, `settleStock:495`, `flush:523`, `_claim:575`, `setProtocol:700`,
   `proposeCreator:709`, `acceptCreator:736`, and `payStock:669` still requires the latch to be **set**.
   `payStock:670-672` additionally re-checks `getNonzeroDeltaCount` around the transfer (the S5-2 fix),
   which is a genuinely good addition round 1 could not have seen.
10. **"The observation ring cannot be starved at the window actually used."** `TwapRing.sol` is unchanged;
    `SLOTS = 1024` (`:26`) against `BUYBACK_TWAP_WINDOW = 600` (`StrategyTreasuryBase.sol:101`), at most
    one write per second (`:51`). The consequence round 1 drew — the `buybackAnchorSqrtP` drift branch is
    effectively dead after the first 600 s — still follows.
11. **"The treasury's tax exemption cannot be borrowed."** Holds, and the singleton narrows it correctly:
    `afterSwap:317-320` reads `p.treasury` for **that pool**, so treasury A swapping in pool B is taxed.
12. **"The creator takeover cannot be run on no notice."** `TAKEOVER_DELAY` 14 d (`:681`), `VETO_QUIET`
    180 d (`:684`), `ACCEPT_WINDOW` 14 d (`:687`), `pendingBy != msg.sender` (`:741`), creator proof of
    life with nothing pending (`:728`). All four survive, now per pool.
13. **"`owner()` reverting does not brick the hook."** Holds: `afterSwap`, `sweep`, `claim`, `claimFor` do
    not call `owner()`, and `vetoCreator:726-727` short-circuits on `isCreator` before reaching it.
14. **"`hookData` is ignored entirely by `afterSwap`."** Holds — `:310`'s last parameter is still unnamed.
15. **"Nothing in `src/` is upgradeable."** Holds (EXECUTED grep, zero matches across all eleven files).

---

## The rejected list

- **R-1 · the one-wei lot.** The rejection stands, and the code now defends it explicitly rather than
  accidentally: `takeProfit:345-347` has `if (left == 0) { L.half = true; return; }` with the comment "a
  one-wei lot has no half to sell". `_book:306` still refuses below `minLotUsdg`. **Upgraded from
  unreachable-by-accident to guarded.**
- **R-2 · "the owner can substitute defaults underneath a pending launch."** The rejection **still stands,
  but every word of its evidence is obsolete.** It was falsified twice by the mined hook salt; there is no
  salt. It is now closed by `_terms`/`Restated` at `StrategyFactory.sol:352-356` and `:397`. Anyone citing
  R-2 must re-cite it, and a future refactor that touches `_terms` re-opens it. See safe-list item 3.
- **R-3 · `TreasuryDeployer` embeds the treasury's creation code twice.** Still rejected, still I-16. The
  number moved: `TreasuryDeployer` is 23,609 with **967 B** margin against `StrategyTreasury`'s 18,381
  (EXECUTED). Dropping `predict` would still save only the deployer-logic delta.
- **R-4 … R-9** are measurement and grading judgements about round 1's own work, not about the code. None
  is affected by the rewrite. R-9 in particular (the F-01 correction rescales only the +30% column) still
  governs how F-01's numbers may be used.
- **U-1 … U-10** were unproven, not rejected, and remain unproven. Two are now cheaper to settle: **U-1**
  (`supply < 1e12` breaks the seed) is one test against `StrategyFactory.sol:457`'s
  `supply - supply / 1e12`, and `test/InteractFactory.t.sol` already has
  `test_tinySupplyBricksEveryLaunchWithAnOpaqueV4Error` and `test_theDustHaircutIsNegligibleAtARealisticSupply`
  — worth reading before re-deriving it. **U-7** (the buy-back's impact on a genuinely single-sided seeded
  pool) is still the first measurement the next round should run.

---

## Byte budget, restated — because it moved and it changes which fixes are cheap

EXECUTED, `forge build --sizes` at `0e39f69`, matching BASELINE2:

| contract | runtime | margin | round-1 margin |
|---|---|---|---|
| **TreasuryDeployer** | 23,609 | **967** | 2,158 |
| StrategyTreasury | 18,381 | 6,195 | 7,372 |
| StrategyFactory | 18,950 | **5,626** | 945 |
| StrategyHook | 18,362 | 6,214 | 10,854 |
| TokenDeployer | 9,327 | 15,249 | — |
| TradingCalendar | 4,792 | 19,784 | 19,784 |
| PriceOracle | 2,211 | 22,365 | 22,365 |

Two consequences for round 1's fix list:
- **The factory-side contention is gone.** Round 1's §5.12 required F-05's, F-06's, F-17's and I-6's fixes
  to be written and sized in one build against 945 B. At 5,626 B they all fit several times over. F-17 was
  taken; the rest have no budget excuse left.
- **The treasury-side budget more than halved**, and it binds through `TreasuryDeployer`, not through
  `StrategyTreasury`'s 6,195. Every fix for F-04, F-06 (the better form), F-08, F-10, F-13, F-16, F-20,
  F-21, F-25 and F-40 lands there, against **967 B**. They must be sized together before any is committed —
  which is round 1's §5.12 advice, now applying to the other end of the system.
