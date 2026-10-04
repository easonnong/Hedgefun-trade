> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Findings — external audit round 2

Ref `0e39f69`, audited 2026-09-21. Scope, sizes and the measured test state:
[`00-SCOPE.md`](./00-SCOPE.md). Full supporting reports: [`DISPOSITION.md`](./DISPOSITION.md) (every round-1
finding re-checked) and [`NEW-SURFACE.md`](./NEW-SURFACE.md) (the code that did not exist before).

---

## The answer to the question that was asked

**"He fixed some things — check."**

He did, but that is not what happened. `2b6bfc1` is a rewrite, not a patch set: the hook became a singleton
serving every strategy, the V4 stock venue was deleted, and a documented invariant ("a sell must fully
fill") was deliberately reversed. Against round 1's list of 59:

| | count |
|---|---|
| **WORSE** | **7** (6 findings + 1 Info) |
| STILL OPEN | 42 (28 + 14 Info) |
| CHANGED SHAPE | 5 |
| **FIXED** | **3** — F-17, F-28, I-2 |
| MOOT | 2 — F-27, F-30, both specific to the deleted `StrategyTreasuryV4` |

**Nothing was closed by the rewrite alone.** All three fixes are deliberate code, and all three were already
in the author's own `R5-*` ledger. Net effect of the release on round 1's findings: **six got worse, three
closed.**

And the new code is clean. Two lanes attacked the singleton's shared `pots[stock]` RAY index and the
reversed fill invariant — the two places most likely to carry a High — and **both hold**, with the
conservation law derived independently rather than taken from the source comments.

| | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|
| **new in round 2** | **0** | **0** | **0** | 4 | 4 |

So: **no, nothing in this release introduced a serious security problem, and the two hardest new mechanisms
are correctly built.** What the release did was leave round 1's list largely untouched while making six
entries worse, and ship a test suite that is red out of the box on any current toolchain.

---

## What got worse

**The one that matters: the path-dependence finding is now a real bug, not just a metadata artefact.**
`StrategyToken`'s constructor gained a fifth argument (`creator`) in this release. Four of the five test
mining helpers were updated. `test/InteractRuleMev.t.sol:152-153` was not — it hashes **four** arguments
against a **five**-argument deploy, so `vm.computeCreate2Address` is computed against an init-code hash that
does not exist, the mining loop is a no-op, and where the token lands is decided by the real init code's
trailing metadata bytes — which is to say by the directory the repository sits in. When it lands wrong,
`setUp()` reverts `CurrenciesOutOfOrderOrEqual` and that contract's **22 tests silently do not run**.

The author's own change to this area (`test/LaunchRouter.t.sol:88`) mines a nonce so two tokens land on the
same side. It closes that one test's reproduction and is itself another CREATE2 brute force. Both original
search helpers survive verbatim and `bytecode_hash` is still unset.

The other six: **F-23** (`bind()` still permissionless, and a squat now forces re-mining a hook address
*and* re-submitting it to Uniswap's per-address routing allowlist — no longer just a redeploy); **F-03**
(the constant did **not** change — `MAX_BAND_BPS_PER_HOUR = 200` and `if (bps > 200)` are untouched, and
`19d3faf` is docs-only with zero `src/` changes; the depth table is **uncorrected in five places**, including
the factory comment that cites it, while `bandCeiling` going non-zero moved from "nobody has done it" to a
scripted pre-launch step); **F-33** (14 of 22 defaults still unprinted, the mislabel verbatim); **F-39**
(`setListingGates` is a second lever onto the same unmirrored `tp1Bps` floor); **F-31** (one deny-list entry
now stops every strategy's stock leg, not one); **I-9** (a rebase now mis-values a *shared* pot).

## The named round-1 findings, checked

- **The 100% split.** All three boundary comparisons are still non-strict (`StrategyFactory.sol:247`,
  `:389`, `StrategyHook.sol:196`). `register:196` moves the old constructor bounds somewhere the revert
  reason survives — better diagnosis, **no new bound**. And it is now slightly worse in fact: at
  `protocolBps = 1e4` the treasury receives **exactly 0**, where before rounding left it ≤ 1 wei.
- **`_setDefaults` under-bounds.** `spikeSeconds` still unchecked in both validators.
- **`maxBuybackImpactBps` floor.** Both surviving validators still `== 0 || > 1000`; `half = impact/2`
  unchanged. The new dust floor reaches the same `NotDue` one line earlier.
- **The sell spike's 50% unprotected window.** `noteEvent`'s `2 × spikeSeconds` bound is verbatim.
- **A dead oracle freezes the treasury.** Outflow enumeration re-run on the new treasury: exactly nine
  lines, four bounties plus settle plus the V3 callback plus one `take` inward. `sellChunkUsdg` and partial
  fills add no exit. Still open.
- **The calendar override and `AUDIT.md`'s FA-1 record.** `TradingCalendar` is byte-identical at every cited
  line; `docs/SECURITY.md:36` still promises what `:37` grants; `AUDIT.md:206` still records FA-1 as fixed.

## Round 1's "checked and found safe" list — five entries no longer hold

This is the section a future round is told not to re-derive, so a rewrite invalidating part of it matters
more than a new Low. Five went: the per-hook ledger clearance (the shared escrow round 1 cleared *because*
it was per-hook is now exactly what exists); "no assembly in any V4 callback path" (false — `tload` in
`_buyRate`); the mined-salt restatement guard; the `StrategyToken` description; and "no `vm.addr`/`vm.sign`".
Ten survive, including the most load-bearing one — that at `bandBpsPerHour == 0` the pool is only ever a
veto — byte for byte.

**One of those is the round's best outcome.** Round 1 found that the mined hook salt was an *accidental*
complete restatement guard over all nineteen `Defaults` fields, and wrote: *"Worth saying out loud in the
docs, because it is load-bearing and nothing names it."* They refactored it away — and replaced it
explicitly with `_terms` (`StrategyFactory.sol:352-356`), whose coverage was walked field by field and found
complete. An accidental guarantee became a deliberate one.

---

## New findings — 0 Critical, 0 High, 0 Medium, 4 Low, 4 Info

**L2-1 · Low · `setVoteDelegate` asserts nothing after its call.** One uncapped
`try IVotesLike(_stock).delegate(delegatee)`, no state checked afterwards. The source's defence — *"whoever
can [repurpose that selector] can already `adminBurn`"* — collapses two actors. An `adminBurn` is the issuer
alone, deliberate, and visible as a `Transfer` to zero. A repurposed `delegate` is the issuer **enabling**
and the protocol Safe **executing**, and the Safe is the party `docs/SECURITY.md:42` promises cannot move,
approve or pledge anything. The treasury is the only side that can be made to refuse, and it declines to.
*Measured:* live AAPL `0xaF3D…93f9` reverts on `delegate(address)` today, so the hatch is the no-op the docs
say it is. Fix ≈ 120 bytes against `TreasuryDeployer`'s 967.

**L2-2 · Low · a transfer fee on a stock breaks the shared pot.** `_credit` books `s − tip` on the strength
of having *called* `_redeem`, not on what arrived. Once `f·s > tip`, `balanceOf(hook) < pot.parked`, and the
next `_square` on **any** pool reads the shortfall as an issuer burn and writes down every parked claim on
that stock pro rata — every sweep, forever. `docs/SECURITY.md:133-157` enumerates deny-list, pause and
`adminBurn` correctly and does not cover a change in transfer arithmetic; `docs/STOCK_TOKEN_ASSESSMENT.md:24`
says the issuer can add a fee in one block. ≈ 90 bytes in `StrategyHook`, which has 6,214 free.

**L2-3 · Low · the launch-transaction exemption is unbounded in count and size, and three places in the docs
say "one" / "first" buy.** *Measured:* the launcher takes **89.94% of supply at the flat rate** against
**0.99%** for a stranger with the same 80,000 stock in the same second — and identically whether taken as one
buy or forty, so the count is economically irrelevant and the security model's "a large first bag" is the
accurate description. The three places that say "the opening's **one** tax-exempt buy" are not, and a front
end could read them as a cap. Documentation, 0 bytes.

**L2-4 · Low · the dust paths shrink a lot without selling**, so `takeProfit` can pay a bounty for a call
that moved no stock and never spends the closed-market hour.

**Info:** the toolchain analysis (below); one stale `StrategyTreasuryV4` reference surviving in tooling;
`sweep` opening its own `unlock` so it cannot be composed inside another; and `docs/SECURITY.md`'s
"it writes **no storage**" for `setVoteDelegate` being literally false — `nonReentrant` is OpenZeppelin's
**non-transient** guard and writes `_status` twice per call. The claim's *intent* holds (nothing persistent
is left to fall out of step with the token); the sentence does not. The closed-selector bytecode walk that
would have caught it exempts `setVoteDelegate`.

### Two things attacked hard that did not break

Worth recording, because they are the two places a High would have lived. The shared `pots[stock]` RAY index
with epoch-on-wipeout: **cross-stock contamination from a burn is nil** — `pots` is keyed by stock — and the
per-pool rebase arithmetic closes. Transient slots 0 and 1 are **provably unreachable by anything else**: a
grep over the full inheritance and both library sets returns exactly the two assembly blocks, there are no
`transient` variables anywhere, and `TransientStateLibrary` reads the *PoolManager's* storage via `exttload`,
not the hook's. A suspicion that `uiMultiplier()` was a rebase `_pot` would misread as an issuer burn was
chased and closed against archive reads across the NVDA flip.

---

## The test suite: three lines, no contract change

| # | fix | effect, measured |
|---|---|---|
| 1 | `test/InteractRuleMev.t.sol:153` — add the missing `, address(0)` | path dependence **gone**: byte-identical at two deliberately different paths, 1126 passed / 3 failed / **1130 ran** at both |
| 2 | `foundry.toml` — set `gas_limit` (needs ≥ 1.44e9) | with (1): **1128 passed, 1 failed** |
| 3 | rewrite `test_holds_isolationIsReal_a_…` against what the current tool does, correct `docs/DEVELOPMENT.md:186-189`, raise `FOUNDRY_VERSION` from `v1.5.0` | the last red goes |

`bytecode_hash = "none"` is still worth setting **for reproducible on-chain verification** — a protocol
pitched as "immutable, verify it yourself" should build byte-identically from any clone — but it is **not**
the fix here, and on its own it makes the suite worse.

Separately and unchanged from round 1: **12 of 24 one-line mutations survive a green run**, including a
one-wei understatement of `buybackStock` that **no test detects**. The treasury's only conservation
assertion is still an inequality pointing the way the error moves.

---

## Corrections this round made to itself and to round 1

- **Round 1's remediation for the path dependence is withdrawn for this ref.** It was verified correct at
  `9a291aa` and is wrong at `0e39f69`; the release introduced a second, different root cause on top of the
  first. Checked rather than carried forward.
- **The lead concluded the launch-window exemption was untested and was wrong.** Deleting
  `tstore(0, id) tstore(1, launcher_)` outright turns **seven additional tests red** — the feature is
  genuinely covered, because the launch and the first buy happen inside one top-level call, which is also
  the production path. What is actually lost is only the ability to test the *boundary*. The strong version
  is not published.
- **The lead repeated the source's "writes no storage" for `setVoteDelegate` without checking it.** It is
  false. Recorded as Info above.
- **Both "red everywhere" test failures were checked before being reported as defects.** Neither is one.
