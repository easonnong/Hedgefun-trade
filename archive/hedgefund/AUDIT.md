> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Security review — strategy-token launchpad on `main` (3e40069)

Reviewed 2026-09-20 against the merged code. Three parallel adversarial passes (V4 hook;
treasury rule + oracle + calendar; factory + launch + deploy), each required to back
every finding with a Foundry PoC under `test/Audit*.t.sol` or label it PLAUSIBLE.
Synthesis, cross-verification and the go/no-go below are the lead's.

`forge test` on merged main before review: **236 passed, 0 failed** (no network).

> **After round 5, 2026-09-21 — four changes, and the round over them (round 6): GO, nothing Critical, High or Medium.
> Its outcome is below the list. One later addition, the token's metadata, is in a short pass still in progress.**
> Everything below this note, the fifth-round banner included, is as written against the code it reviewed and is not
> rewritten. Read it with these in mind:
>
> 1. **Sales fill partially.** A `takeProfit` / `stopLoss` sale no longer has to fill whole or revert. It is an
>    exact-input swap limited at `oracle × (1 − maxSlippageBps)` — the pool computes its own depth — and the lot, the
>    event and the bounty are sized from what sold; a sale that sells nothing reverts `Slippage`. `PoolTrader` lost
>    `requireFull`, `PartialFill` and `_swapForExit`. So "sells must fully fill" wherever it appears below (the
>    original findings' closing list, R5-3's reasoning about what capped a pin) describes the old code.
>    `sellChunkUsdg` became a price-quality knob on an open market — measured with no effective chunk, a 2,400-stock lot
>    against ~500 stock of depth inside 1%: treasury shortfall 55–104 bps, never above slippage + pool fee; a caller back-running their own
>    call +107 USDG on a 0.3% pool, +240 on a 0.05% one — and stays a safety knob on the closed-market path, where a
>    short-filling sale gives a pinned pool `min(chunk, depth)` an hour; a banded launch is therefore born with no more
>    than the default chunk. A short fill leaves the pool on the limit, outside the deviation gate, until it is re-pegged.
>    TR-1 stays bounded, not solved. Tests: `test/PartialFill.t.sol`, `test/SellChunk.t.sol`.
> 2. **`sellChunkUsdg` per listing.** `setListingGates(stock, dev, slip, sellChunkUsdg)` (selector `0xc8ed517d`);
>    `listingGates()` returns three values; `ListingGatesSet` gained the chunk. `0` = the default; otherwise ≥
>    `minLotUsdg`, checked when set and again at launch (`BadRequest`). It is a constructor argument, so `terms` pins it.
> 3. **The treasury has an owner, for one thing.** `owner()` is the factory's, read live; `setVoteDelegate(address)`
>    makes one `try`ed `stock.delegate(d)`, is `nonReentrant`, writes no storage, emits
>    `VoteDelegateSet(by, delegatee, accepted)`. A hatch, reserved and not live: the stock token has no vote surface
>    today. So "no owner on the treasury" below, and every "the Safe's handle on anything launched is the two payout
>    addresses", is now "…and where each treasury's votes point". No `declare()`, by decision.
>    Tests: `test/TreasuryVote.t.sol`.
> 4. **The V4 stock venue is removed** (delete, don't add): `StrategyTreasuryV4`, `TreasuryV4Deployer`, `listV4`,
>    `setV4ListingEnabled` / `v4ListingEnabled`, `Venue`, `Listing.venue` / `v4Key`, `ListedV4`, `V4ListingEnabledSet`
>    are gone; the factory's constructor takes 8 arguments, `listings()` returns `(oracle, v3Pool, openPriceE18,
>    enabled)`, `Listed` has a new topic0. Every finding below about "both venues", FA-* notes on `v4ListingEnabled`,
>    and R5-2's "the venues diverged" describe code that no longer exists. The strategy token's own pool is still V4.
>
> Also since the banner: a treasury the constructor refuses now surfaces as the custom error `TreasuryDeployFailed()`
> (`0xb94a14a6`), not the string `"treasury deploy"` (R5-5's message; its substance is unchanged); the
> `takeProfit`-side `tp1Left` clamp the banner calls "defence in depth" was removed as unreachable, the `stopLoss`
> clamp that fixes R5-1 stays; `pricedOffPoolOnly()` is abstract in the base. Kept by decision: the launch-fee
> currencies and closed-market band trading (off per stock until the Safe raises `bandCeiling`).
> At the round-6 commit: `forge test` 1,017 passed, 0 failed, 31 skipped; `HedgeFunFactory` 21,002 B (margin 3,574),
> `TreasuryDeployer` 23,607 B (969).
>
> **Round 6 outcome: GO. No Critical, High or Medium.** Reproductions, characterisations and what-holds checks:
> `test/AuditRound6Treasury.t.sol`.
>
> | id | what | outcome |
> |---|---|---|
> | **T6-1** Low/Info | **A short fill parks the rule, and pays the caller who parked it.** A sale that fills short leaves the pool on the slippage limit, outside the deviation gate, so every rule call on that treasury is `Unhealthy` until someone re-pegs. Before partial fills, reaching that state with your own swap cost −416 USDG in the PoC; now the treasury's stock does the walking and the caller is paid a bounty (+15.6). Self-heals through a ~50 bps arbitrage | **documented; the fix is operational.** Size a listing's `sellChunkUsdg` to no more than the measured depth *between the deviation edge and the slippage limit* (`docs/OPERATIONS.md`). `test_T6_1_aShortFillParksEveryRuleCall_andTheCallerIsPaidForIt_characterised` |
> | **T6-2** Info | **The closed-market hour was spent by a call that sold nothing.** `_poolOnlyPace()` ran before the dust-tail branch (R5-2) and the one-wei-lot return, so a dust tail took the closure's hourly slot and the honest lot beside it waited an hour | **fixed**: the pace is taken only on the path that reaches the pool. `test_T6_2_aDustTailDoesNotSpendTheClosedMarketHour_theHonestLotBesideItStillSells` |
> | **T6-3** Info, pre-existing | **The hourly pace keys on `pricedOffPoolOnly()`**, which is false while the pool's mean sits within `maxDeviationBps` of the *stale* feed. A lot already due at Friday's last print sells across the closure unpaced — at a price Chainlink signed | **documented.** "One sale an hour" bounds what a pin can take at a **pulled** price, not every closed-market sale (`docs/SECURITY.md`, TR-1). `test_T6_3_onAClosure_aLotDueAtTheStalePrintSellsUnpaced_whenThePoolIsHeldOnTheFeed_characterised` |
> | **T6-4** Info, tests | **The selector-closure "bytecode walk" samples `PUSH4` only**, and cannot see a selector with a leading zero byte (the compiler pushes it as `PUSH3`) | the treasury's ABI is pinned instead: `test_holds_theAbiIs52Selectors_allVisibleToThePush4Walk_nineNonView_ownerPrivilegedInOne`. Adding any external function to the treasury must update that pin deliberately (`docs/DEVELOPMENT.md`) |
> | **T6-5** kit | a finding against `emergency/`, not the contracts | fixed in the docs-and-kit pass that preceded this one (commit `2464664`) |
>
> **Measured, self-sandwich** (`test_holds_loopedShortFillsPlusOwnRepeg_…_measured`, `test_holds_aShovedStop…_measured`:
> a 600-stock lot, ~500 stock of depth inside 1%, a 0.30% pool, slippage 100 / deviation 50 bps, the attacker is the
> caller and shoves the pool to −49 bps before every call):
>
> | chunk | calls (take-profit / stop) | treasury's shortfall | attacker, before bounty |
> |---|---|---|---|
> | oversized | 3 | 102 bps | **+100** USDG / **+89** |
> | 2,000 USDG | 34 / 27 | 80 bps | **−31.6** / **−27** |
>
> The shortfall never passed slippage + pool fee (130 bps). A right-sized chunk turns the sandwich into a loss; an
> oversized one does not brick anything and does pay the sandwicher, which is why the sizing rule is in the runbook.
>
> **TR-1, bounded with the shipped numbers** (`test_holds_TR1_aPinnedWeekendSellsAtMostOneDefaultChunkAnHour_49SalesIn48Hours`):
> a 48-hour closure, the pool pinned throughout, a caller every hour, the band at its 3000 bps cap, a 2,000 USDG chunk —
> 49 sales, at most 98,000 USDG of notional given up at the rule's price (146,000 on a 72-hour closure). The loss is
> `notional × (real ÷ pin − 1)` plus slippage plus fee: real 130 against a pin of 106 is about 22.8k USDG.
>
> **The vote hatch, on trust:** it gives power to nobody but the stock's issuer, who can already burn the treasury's
> balance. `setVoteDelegate` reaches nothing the issuer's own admin functions do not.
>
> **Since round 6**, one addition, on the token and not the treasury: the strategy token carries its creator's
> metadata, pons-shaped, and its creation code moved to a `TokenDeployer` (the factory's constructor takes 9 arguments).
> The T6-2 fix is in the same commit. `forge test`: 1,064 passed, 0 failed, 31 skipped. `HedgeFunFactory` 18,107 B
> (margin 6,469), `TreasuryDeployer` 23,609 B (967), `HedgeFunToken` 6,847 B, `TokenDeployer` 8,844 B. A short pass on
> the token and `TokenDeployer` ("round 7") followed.
>
> **Round 7, 2026-09-21 (token metadata + `TokenDeployer`) -- outcome: GO, no Critical, High or Medium; nothing reaches
> funds.** K7-1 Low, **FIXED**: `lock()` froze whatever entry landed before it, so an appointed editor (or whoever stole
> its key) could write a drainer link in front of the deployer's lock, in the same block, and nobody could ever repair
> it. A lock is now refused while an editor is appointed: dismiss, re-read, lock
> (`test_K7_1_anEditorCannotWriteInFrontOfALock_becauseALockNeedsTheEditorGone`). K7-2 Low, **FIXED**: `q.name` and
> `q.symbol` had no cap -- a 20,000-byte name of `0xff` bytes launched (34M gas) and rode out in `Launched`; now 64 and
> 32 bytes at the door (`test_K7_2_…` in `test/InteractFactory.t.sol`). K7-3 Info, by design, **DOCUMENTED**: after a
> payout takeover the launch-time creator still writes the page; front ends show both addresses. K7-4 Info (tests): the
> "pons selectors" test compares a selector with its own signature and `ref/pons` on this branch does not contain pons'
> token, so **pons compatibility is verified only against the tuple shapes pinned in `test/AuditRound7Token.t.sol`**
> until the full pons sources (PR #31) are in. (They are now, on `main`: read against
> `ref/pons/contractsV2/src/v2/PonsV2LauncherToken.sol`, `Socials` has the same five fields in the same order, and
> `logo()`, `description()`, `socials()`, `getTokenInfo()` and `deployer()` have the same signatures and return tuples.) Checked and holds: a max-size locked entry changes no burn, tax, balance,
> name or decimals; no selector collision with ERC-20; only a creator can collide with their own launch
> (`TokenDeployFailed`); the owner cannot swap the token under a quote (`Restated`); through `HedgeFunLaunchRouter` the token's
> `deployer()` is the human creator, not the router. **Added after round 7, reviewed by the lead only (no separate
> adversarial pass):** the launch can carry the page -- `launchWithMetadata` on the factory and the router, written through
> the token's one-shot `initMetadata` (launcher-only, only while `updatedAt == 0` and unlocked, event names the creator).
> Five mutants killed (any caller; a second write; init after a lock; the event naming the factory; the factory not
> writing). **Round 8, 2026-09-21, over exactly that addition -- outcome: GO, no blockers.** P8-1 Info, documented: an empty
> page stamps `updatedAt`, so front ends check the fields. P8-2 Low (owner trust), documented: a vouched launcher that does
> not insist `q.creator` is its caller would also write the first page in the victim's name; `HedgeFunLaunchRouter` does insist,
> before the factory call, at both entries. Checked and holds: a plain launch's one write can never be spent later; no
> attacker-influenced call sits between the token's creation and `initMetadata` (fees are paid before the token exists);
> the launch-window exemption and every `msg.sender`/`msg.value` path survive the refactor; a max-size page round-trips
> byte for byte through the router (8.90M gas with capital; the page adds 2.20M). Tests: `test/AuditRound8LaunchPage.t.sol`.
> After the fixes and that addition: `forge test` 1,135 passed / 31 skipped; `HedgeFunFactory` 18,950 B (margin
> 5,626), `HedgeFunToken` 7,301 B, `HedgeFunLaunchRouter` 7,525 B.
>
> **After #29, 2026-09-21: the first booked lot sets the dip reference, and `HedgeFunLaunchRouter` can seed USDG.** One line in
> `_book` (`if (lastSalePrice == 0) lastSalePrice = p;`) and one `safeTransferFrom` in the router, so that a strategy whose
> stock falls before it ever rises can buy that dip. Tests `test/DipReference.t.sol`; three mutants killed (no first-lot
> reference; every lot moving it; the router ignoring `seedUsdg`). **Round 9 over it: GO, no blockers.** D9-1 Low, **FIXED**:
> a stale Friday print, booked while the pool was held onto it during a closure, became the reference and the same closure
> bought against it at a pin (−377.7 of a 10,000 reserve; at 100,000 the attacker made +578.2) -- `_book` now acts only on a
> LIVE Chainlink print, which replaces the pool-only check it subsumes. D9-2 Info, measured: a seeded reserve is laddered at
> a pin from its first weekend, 1–3 rungs at first-batch numbers, worst 766 of 10,000. D9-3 Low (docs), fixed: a rung loses
> the real gap, not the band width. D9-4 Info: with `stop == dip` both are due at one print and the caller's order decides;
> no loop, the next cycle needs a further real move. No hourly pace on closed-market dip buys: it removed no rung in any
> cell. Also fixed, found by the auditor's checkout: `InteractRuleMev`'s token salt was mined against a 4-argument init code
> and deployed with 5, so its currency ordering came out by chance. Tests: `test/AuditRound9DipReference.t.sol`.
>
> **The refactor, 2026-09-21 (#44: `src/hooks`, `src/interfaces`, `src/libraries`, `HedgeFun*` names, `HedgeFunMath`,
> `HedgeFunLimits`).** Public ABIs compared entry by entry against the release: identical. It was described as "no rule
> changes" and there is exactly ONE, found by the peer review. M10-1 Low, **FIXED by the refactor**: the take-profit
> threshold was written `L.cost * (1e4 + _params.tp1Bps)` with `tp1Bps` a uint16, so the sum was checked uint16 arithmetic
> and any tp above 55,535 bps made every `takeProfit` of that treasury panic (0x11) at any price -- and nothing bounds tp
> from above, so a creator could launch a treasury that could never take profit. `HedgeFunMath.reached` takes the rate as
> a uint256. The library's own fuzz test had cast the rate to uint256 before comparing, so it could not see this. The
> other sites were read for the same shape and do not have it: `1e4 - stopBps` / `1e4 - dipBps` are bounded below `BPS`
> at birth, and the hook's, the buy-back's and the pool trader's operands were already uint256. A take-profit was then
> reachable up to 65,535 bps (7.55x cost); the owner asked for 100x, so `tp1Bps`/`tp2Bps` became `uint32` in `Params` and
> `Request` (the `launch`/`predict` selectors changed with the tuple), unbounded above on purpose. Tests: `test_aTakeProfitAbove55535Bps_isDueWhenThePriceIsThere_notAPanic`,
> `test_theLargestTakeProfitAUint16CanAsk_isDueAt7_55TimesCost` (`test/StrategyTreasuryUnit.t.sol`); both fail with the
> panic when the old expression is put back.
>
> **Status, fifth round, 2026-09-21** — what changed since round 4, and what a round over it found. Since round 4:
> `HedgeFunHook` became **one singleton** for every strategy (per-pool state by `PoolId`, per-pool accrual, a per-stock
> pot with a write-down index; `HookDeployer` and per-launch salt mining gone; `launch(q, terms)` commits the launcher
> to what `predict(q)` quoted), exact-output swaps were accepted, buys got a launch window with a transient
> launch-transaction exemption, sales got `sellChunkUsdg`, listings got their own gates (`setListingGates`), and
> `HedgeFunTradeRouter` was added (its own pass, ids T5-*, lives in `test/AuditTradeRouter.t.sol`). Three parallel passes over
> that: the singleton and its ledger (S5-*), the tax and the launch window (X5-*), the treasury and the factory (R5-*).
> The findings below are described in the body of this file **nowhere else**: the historical sections that follow are
> as written against older code (one hook per launch, `sweep()` with no pool id, exact-output refused) and are not
> rewritten. Reproductions and what-holds checks: `test/AuditRound5{Singleton,Tax,Treasury}.t.sol`.
>
> | id | what | outcome |
> |---|---|---|
> | S5-1 | the launch exemption was keyed on the pool's launch *transaction* alone, so whoever relayed a creator's signed launch bought inside it at the flat rate | **fixed** by the X5-1 and X5-2 changes |
> | S5-2 | a payout recipient that returns normally but leaves an open delta in the PoolManager reverted every sweep of its pool, for good (`CurrencyNotSettled`) | **fixed**: `payStock` reverts its own frame if the manager's nonzero-delta count changed; that cut is parked |
> | S5-3 | after a write-down, `owed(id, who)` for an address holding two roles could differ by a wei from what its claim pays | **fixed**: summed role by role, as a claim rounds it |
> | X5-1 | a 4337 bundle, relayer batch or public multicall puts strangers' calls in the launch transaction: 8% of supply bought at the flat rate | **fixed**: exempt only if it is this pool's launch transaction **and** the swap's sender is the contract that called the factory (`register` takes the launcher) |
> | X5-2 | anyone could launch in anyone's name; a copied launch took the only exempt buy and made the victim's own collide (supersedes R4-2's reading) | **fixed**: `launch` reverts `BadRequest` unless the sender is `q.creator` or a launcher the owner vouched for (`setLauncher`) |
> | X5-3 | a grossed-up exact-output tax never meets the pool's curve: 31% fewer tokens for a 500k-token sale at the 90% spike, 44% less for a 40-share buy in the 99% window | **fixed**: an exact-output buy is refused whenever the buy rate is above the flat tax, i.e. inside the launch window (`ExactOutputRefused`) |
> | X5-4 | an exact-output sell is taxed in the token, which burns: every role's revenue was something a seller opted into, at no cost | **fixed**: exact-output sells refused; only a flat-rate exact-output buy remains, and its tax (stock) is split |
> | X5-5 | `HedgeFunTradeRouter`'s NatSpec described the hook's old exact-output behaviour | **fixed** (comment only) |
> | X5-6 | for the length of the launch window the launch-transaction buyer is the only source of tokens that did not pay the premium | **accepted, disclosed**: [`docs/SECURITY.md`](./docs/SECURITY.md#the-launch-window-is-a-speed-bump-not-a-fence); front ends show the launcher's bag |
> | R5-1 | a `stopLoss` chunk mid-tp1 left `tp1Left > qty`; `takeProfit` then panicked forever on that lot | **fixed**: `tp1Left` clamped to the lot in both functions |
> | R5-2 | on V3 a dust remainder whose principal is worth under one unit of USDG could never be sold; the venues diverged | **fixed**: such a principal skips the swap |
> | R5-3 | chunk loops removed the cap pool depth put on a closed-market pin (TR-1): 64 chunks sold 1,137 stock at the pin in one transaction | **fixed**: on the pool-only path, one take-profit chunk per `POOL_ONLY_SALE_INTERVAL` (1 h). TR-1 itself stays bounded, not solved: one pinned sale measured −775 USDG for the attacker on one venue, +249 on the other |
> | R5-4 | `terms` pinned no fee currency: a `maxFee` quoted in stock units became USDG units under a standing approval | **fixed**: `terms` hashes `launchFeeCurrency` and `launchFeeAmount` |
> | R5-5 | gates loosened past a creator's rule floor make a quoted launch die as the opaque `"treasury deploy"`, not `Restated` | **accepted**: same outcome, worse message; front ends must read `listingGates` |
> | R5-6 | the deploy script's bare narrowing casts wrapped (`SNIPE_SECONDS=300` → 44, `PROTOCOL_BPS=67536` → 2000) into values the factory accepts | **fixed**: every env var range-checked, `OutOfRange`; `TICK_SPACING` ≤ 32767 |
>
> **Severities and outcomes. No Critical or High was found.**
>
> | id | severity | outcome |
> |---|---|---|
> | S5-1 = X5-1 | Medium | **fixed**: the exemption is bound to the launcher — the pool's launch transaction **and** a sender that is the factory's caller |
> | X5-2 | Medium | **fixed**: launch only by `q.creator` or an owner-vouched launcher (`setLauncher`) |
> | X5-3 | Medium/Low | **fixed by narrowing**, with X5-4: exact-output is accepted only for a **buy at the flat rate**. Exact-output sells, and exact-output buys inside the launch window, revert `ExactOutputRefused`. An exact-output buy during a **sell** spike is accepted: the spike is on sells, and the buy rate is flat then |
> | X5-4 | Low (design) | **fixed by narrowing**, as X5-3 |
> | S5-2 | Low today; High if the issuer adds a recipient callback | **fixed**: `payStock` delta-count guard; the cut is parked |
> | S5-3 | Info | **fixed** |
> | R5-1 | Medium | **fixed**: `tp1Left` clamped in `stopLoss` and in `takeProfit`. The `takeProfit` clamp is defence in depth: with the `stopLoss` clamp in, mutation shows it unreachable |
> | R5-2 | Low/Info | **fixed** on both the take-profit and the stop path: dust worth under one unit of USDG skips the swap |
> | R5-3 | Low (Medium once a band ceiling is raised) | **mitigated**: the pool-only path is paced, one take-profit sale per hour per treasury. TR-1 remains bounded, not solved |
> | R5-4 | Low | **fixed**: fee currency and amount are in `terms` |
> | R5-5 | Info | **documented**: the opaque `"treasury deploy"` when gates are loosened past a creator's floor. Also: the fee is pulled before `terms` are compared, so a flipped currency the launcher cannot pay surfaces as an ERC-20 allowance/balance error rather than `Restated`. Nothing moves either way |
> | R5-6 | Low | **fixed**: `_u` range guard. The regression exercises `_u` through a harness, not the script's `run()`: `vm.setEnv` is process-wide and would race `DeployScriptGuards` |
> | X5-5 | Info | **fixed** (`HedgeFunTradeRouter` NatSpec) |
> | X5-6 | Info | **disclosed** |
> | T5-1 | Medium | **fixed** (`HedgeFunTradeRouter`, merged earlier as PR #26) |
> | T5-2 | Low/Medium | **fixed** (same) |
>
> **Regressions.** Every fix marked fixed above has a regression test in
> `test/AuditRound5{Singleton,Tax,Treasury}.t.sol` or `test/AuditTradeRouter.t.sol` that was confirmed to **fail with
> that fix reverted** (the mutation tables are in the PR). Two exceptions, stated rather than papered over: the
> `takeProfit`-side R5-1 clamp, which is unreachable once the `stopLoss` clamp is in, and R5-6's wiring into `run()`.
> `forge test --mc AuditRound5`: 254 passed — a large number because each file inherits its harness's tests.
>
> **Go/no-go: go for merge.** For mainnet the standing list applies — a hardware key on the Safe, one real Safe
> transaction, CI billing, a per-pool basis check before each listing — plus three from this round: the Safe must
> `setLauncher(launchRouter, true)` **before** `setPublicLaunch(true)`; deploy and bind before submitting the hook
> for routing; and never leave a fully signed Safe launch in a public transaction service before this release is
> what is deployed (S5-1: on the older code whoever relays it buys inside it at the flat rate).
>
> Current model: [`docs/SECURITY.md`](./docs/SECURITY.md). Still true: no external review.
>
> **Note, 2026-09-20, after this review:** the report below describes a hook whose `creator` and `protocol` were
> immutable and which had no owner. That is no longer so. By product decision the factory's owner, read live by each
> hook, can now move the protocol's payout (`setProtocol`, instant) and a vanished creator's payout (`proposeCreator`
> → 14 days, one-call `vetoCreator()` from the creator → `acceptCreator`), and nothing else; no rate, rule, treasury
> or liquidity is reachable and there is no rescue of stock. Not covered by the passes below. Current model:
> [`docs/SECURITY.md`](./docs/SECURITY.md#who-is-trusted-and-with-exactly-what).
>
> **Status, fourth round, 2026-09-20** (`fix/audit-round4`): three parallel passes over what that note says was not
> covered — the fee ledger (L4-*), the hook owner (O4-*) and `HedgeFunLaunchRouter` (R4-*). **No Critical, High or, against
> the stock token as it behaves today, Medium.** L4-1 and O4-1 become High the day the issuer gives the stock a
> recipient callback, which it can and this code cannot answer later, so both are **fixed** (ledger debited before
> the transfer; `sweep` and the owner functions refuse from inside a payout). Also fixed: L4-2 (treasury credited
> like everyone else, `owedTreasury`), O4-2 (a proposal lapses 14 days after maturing and belongs to the owner who
> made it), O4-3 (the creator's veto works with nothing pending, as proof of life), R4-2 (through the router the
> launcher is the creator), R4-3 (the buy-back anchor is not noted before the pool's first swap). Documented, not
> changed: L4-3 (a low-gas sweep succeeds and pays nothing), O4-4 (a creator that cannot call cannot veto), R4-1
> (what a first-buy bag does to the next buyer; the spike protects for 120 s). Regression tests:
> `test/Audit{Ledger,Owner,Router}Round4.t.sol`, the owner file including a stateful invariant over the ledger.
>
> **Status, third round** (`fix/audit-round-3`): TR-2, TR-3, FA-4 and FA-5 are **fixed**. TR-1 is **switched off
> rather than fixed** — closure trading is a per-treasury flag that ships `false`; the lead's analysis is that neither
> of this report's two suggested fixes changes the attacker's break-even, which depends on traded size against depth
> and not on pin distance. One regression from round two was found and fixed here: moving the closed path onto
> `isClosedByRule` stopped an override opening it on a live day but also stopped one shutting it on a weekend, so the
> owner's brake failed two days in seven. FA-7, FA-11, CI and the stock-token assessment are handled on sibling
> branches. Every regression test confirmed to fail with its fix reverted.
>
> **Status, second round:** blockers 5 (the calendar owner, FA-1 / TR-6), 8 (the two owner front-runs, FA-2) and
> the rest of HK-4 are **fixed** on `fix/audit-pre-launch-2`, each with a regression test confirmed to fail with
> the fix reverted. Blocker 6 (TR-1) was answered by decision — deep pools only — and is otherwise still open, as
> are 7, 9 and 10. One correction to FA-2's suggested fix: two extra parameters on `launch()` do **not compile**
> (`Stack too deep`); carried in the `Request` struct they cost 87 bytes.
>
> **Status, same day:** blockers 1–4 (HK-1, HK-2, HK-3 and FA-3) are **fixed on the branch that carries this
> file** — `fix/audit-hook-blockers`. Their reproductions became the regression tests in
> `test/AuditHookRegression.t.sol`, `test/InteractHookTax.t.sol` and `test/InteractFactory.t.sol`, each confirmed to
> fail with the fix reverted. Blockers 5–10 are open. The verdict below is as written against `3e40069`.
>
> **Verdict: NO-GO for the first launch until three hook fixes land; NO-GO for public
> launch until two more.** No Critical. One High, six Medium. 43 PoCs, all re-run by the
> lead. Go/no-go and the blocker list are at the end; the section below is the measured
> environment every finding is sized against.

---

## Measured inputs every finding is sized against

These are chain facts, not assumptions. All from read-only calls on 2026-09-20.

**Chain.** id 4663, ~0.1005 s/block (≈860k blocks/day). USDG 6 decimals; every stock
token 18. Every one of the 194 registry tokens implements `oraclePaused()`.

**Oracle.** 35 of 194 registry tokens have a Chainlink push feed; Chainlink's own
directory confirms 35, not the "95" in launch coverage. Feeds: 0.5% deviation threshold,
`heartbeat: 86400` advertised — **but no heartbeat fires off-hours.** Measured across the
2026-09-11→14 weekend: no feed updated for the whole ~52h closure; all refreshed at the
session open (Sun 20:00 ET = Mon 00:00 UTC) to the second; SPY then did not update for
≥15h into Monday while AAPL/NVDA/META ticked through the overnight and cash open.
`PriceOracle` caps `maxStockAge` at 48h; under this repo's `TradingCalendar`
(Sun 20:00 ET → Fri 20:00 ET) the frozen span is 52h, so **across a weekend the calendar
gate, not the age gate, is what holds** and the V3 closed-market path
(`_closedMarketHealth`, pool 600s mean anchored within `MAX_CLOSED_DRIFT_BPS = 3000` of
Friday's frozen close) is what trades.

Feed `description()` uses three formats on this chain (`RH<T> / USD`,
`Robinhood <T> / USD`, `Robinhood <T>-USD`); nothing in the contracts matches on it, but
listing scripts must resolve by address.

**V3 pools.** 317 `<stock>/USDG` pools exist, 154 hold liquidity, **25 are listable
today** (feed + live pool + ring ≥ 660; V4 listings ship disabled). Observation rings on
those 25: 1,400–6,000 slots. Pool prices track Lighter marks within ±0.6% in normal
conditions.

> **CORRECTION, 2026-09-21 (external audit round 1, F-03).** The +30% figures below are **overstated by 8-25x**. They
> assume the active tick's liquidity extends across the whole move; it does not, and every figure exceeds its pool's
> ENTIRE TVL in `data/listability.json` (NVDA $6.2M against "$54M"). A walk up can never cost more than 1.3x the stock
> the pool holds. The audit's exact tick-walk: NVDA ~$2.33M, SPCX ~$0.76M, GOOGL ~$0.47M, AAPL ~$0.24M, SPY ~$0.20M.
> The ORDER of the pools survives and the figures are kept as the record of what was decided on; do not size anything
> from them. What bounds a pin's take is the band and the pace (docs/DEPLOYMENT.md 7.4), and no band is set above 10.

**Cost to move a listed pool.** USDG to push spot +30% using the pool's current
active-tick liquidity (assumes it extends across the move; concentrated pools thin out
away from price, so real cost is likely *lower*). Round-tripped by the attacker, so net
cost ≈ 2× pool fee + counter-flow absorbed during the hold.

| under $500k | $0.5–2M | $2–20M | >$50M |
|---|---|---|---|
| SNDK $70k, USAR $111k, INTC $139k, TSM $201k, AMD $309k, DELL $314k, BABA $466k, PLTR $497k, MSTR $497k | META $595k, SLV $1.3M, GME $1.4M, CRCL $1.4M, TSLA $1.6M, MU $1.85M, MSFT $1.85M | AMZN $3.1M, SPY $3.2M, GOOGL $3.9M, USO $5.3M, AAPL $5.9M, SPCX $13M, QQQ $16M | NVDA $54M, SGOV $102M |

**The reference market never closes.** Lighter's equity perps on Robinhood Chain trade
24/7 (`trading_hours` unrestricted; Sunday 2026-09-20 volume: SPY $60M, QQQ $38M, NVDA
$2.7M, AAPL $1.5M, META $0.7M). Two consequences for the closed-market path: a pumped
V3 pool during a closure invites arbitrage by anyone who can sell stock tokens into it
and hedge on Lighter (bounded by finite, AP-minted on-chain stock supply); and the pool
legitimately re-prices over a weekend while the Chainlink feed does not, so the 30%
anchor to Friday's close is a bound on a *real* weekend move, not only on a broken pool.

**Author-disclosed open findings (PR #2), to be verified rather than re-discovered:**
(1) CREATE2 launch squatting; (2) `buyback` sandwichable, launch token has no oracle;
(3) a pausable/blocklisting stock bricks the sweep; (4) the sell spike can be held
above half indefinitely while `burnStock` lasts.

---

## Findings

Severity is the lead's after cross-verification; every CONFIRMED PoC below was re-run by
the lead, not taken from the auditor's report.

### Factory, launch, deploy — no Critical/High. 10/10 PoCs re-run green (`test/AuditFactory.t.sol`)

**FA-1 · Medium · A launched strategy *does* have a mutable parameter: the trading
calendar.** `TradingCalendar` is `Ownable2Step` with `setOverride(day, closed|open)`
(`src/TradingCalendar.sol:21,28`), and every `PriceOracle` consults it first
(`src/PriceOracle.sol:48`). Whoever owns the calendar holds a live switch over every
strategy priced through it, forever — contradicting the README's "no owner, no keeper, and
no parameter that can change". Forced-closed: `health()` false, `takeProfit`/`buyDip`
revert, strategy halted indefinitely (PoC holds it 300 days). On the V3 venue a forced
"closed" on a real trading day instead routes the rule onto the pool-only path and
switches `stopLoss` off. Forced-open on a Saturday makes Friday's print a live price
(bounded by the 48h cap and the spot-deviation gate). Regime control and DoS, not theft.
*Fix:* renounce calendar ownership before the first listing, or have `list()` refuse an
oracle whose calendar has a non-zero owner; at minimum correct the README.
CONFIRMED — `test_audit_calendarOwnerCanHaltOrReopenEveryLaunchedStrategy`.

**FA-2 · Medium · Two owner front-runs against a pending launch — present on main as
passing `test_BUG_*` tests, absent from the README's "all fixed" list.**
`launchFeeCurrency/Amount` and `openPriceE18` are the only launch inputs in no
constructor's args, so changing them does not invalidate a mined salt
(`HedgeFunFactory.sol:337,346-357,366-373`). (a) Creator with the usual infinite USDG
approval mines against a 25 USDG fee; owner raises it to 1,000,000 first; the launch
succeeds and takes it all. (b) Owner re-lists the open price 1000× lower under a pending
launch and buys half the supply for ~5 USDG instead of ~5,000. *Fix that keeps launches
permissionless:* add `maxFee` and `expectedOpenPriceE18` to `launch()` and revert on
mismatch. With the owner a Safe this is a trust statement rather than a live exploit —
but it should be stated, and it is two arguments to close.
CONFIRMED — `forge test --mt test_BUG_owner` (both pass on `3e40069`).

**FA-3 · Low · Pool pre-initialisation squat — what is actually left of disclosed
finding (1).** The PR text says the CREATE2 deployers have no access control; on main
that is already fixed (`BoundDeployer`, factory-only `deploy`). What remains: V4 lets
anyone `initialize` a key whose hook has no code, so a squatter who sees the mined
`hookSalt` makes the launch revert `PoolAlreadyInitialized`. One call, not permanent
(retry under a new nonce, ~16k hashes), cannot be looped over future symbols, and cannot
land a look-alike on the predicted addresses. *Mitigation, PoC'd:* mine for `0x2044`
(add `BEFORE_INITIALIZE`, same 14 bits of work) — V4 reverts `InvalidHookResponse` on a
codeless hook, so nobody can initialise before the hook exists.
CONFIRMED — `test_audit_mitigation_beforeInitializeFlagClosesThePreInitSquat`.

**FA-4 · Low · `setDefaults` checks far fewer bounds than the constructors it feeds**
(`HedgeFunFactory.sol:239-242`). It accepts `sweepTipBps=101`, `spikeBps>9000`,
`minLotUsdg=0`, bad `tickSpacing`… and every subsequent launch dies as an opaque
`"hook deploy"` because CREATE2 swallows the reason. Recoverable. Mirror the constructor
bounds. CONFIRMED — `test_audit_setDefaultsAcceptsValuesThatBrickEveryLaunch`.

**FA-5 · Low · A non-zero `lpFee` strands LP fees in the seed forever**
(`HedgeFunFactory.sol:369-370,391`). Fees accrue to a position nobody can ever touch —
not burned, not paid to the treasury. Default is 0 but nothing refuses non-zero and the
deploy script reads `LP_FEE` from env. Require `lpFee == 0`.
CONFIRMED — `test_audit_lpFeeOnTheSeedIsStrandedForever`.

**FA-6 · Low · EIP-170 headroom is 1,887 bytes with the optimiser already at
`runs = 1`.** `HedgeFunFactory` 22,689 B, `TreasuryDeployer` 21,622 B. FA-2's and FA-4's
fixes both add factory bytecode — measure before merging either.

**FA-7 · Low · Deploy script: a loud bind race, and permanent addresses that default to
the deployer key** (`script/DeployStrategyLaunchpad.s.sol:40-41,77-83`). `PROTOCOL`
defaults to `OWNER` defaults to the broadcasting EOA, and `protocol` is immutable in the
factory and in every hook — a forgotten env var makes a hot key the permanent tax
recipient of every strategy ever launched. Require both explicitly on chain 4663.

**Info.** `v4ListingEnabled` gates `listV4` only — it is not a kill switch for launches
against an existing V4 listing (FA-8). A look-alike treasury can report
`factory() == <real factory>`; front ends must authenticate via `factory.strategies(id)`
or the `Launched` event, never via self-report (FA-9). Inherited `renounceOwnership`
bricks the factory if `publicLaunch` is off (FA-10). **The "fork-proven" tests return
early and report PASS unless `RH_FORK=1`, and this repo has no CI** (FA-11). First buyer
gets 45% of supply for `supply × openPrice` stock — priced by the curve, not a drain, but
it is what FA-2(b) exploits (FA-12).

### Hook, token, ring — one High (lead's rating), two Medium, one Low. 15/15 PoCs re-run green (`test/AuditHook.t.sol`, `test/AuditHookLaunch.t.sol`)

None of these is on the author's disclosed list.

**HK-1 · High · The tax is on swaps only: a range order exits through the sell tax and
the 90% launch spike completely untaxed.** The hook's permission bits are `0x0044`
(afterSwap + returnsDelta) and it takes no liquidity callback
(`src/hooks/HedgeFunHook.sol:108,232-241`), so anyone may add a position to the launch
pool. A holder who wants out places tokens as a one-spacing single-sided range just past
spot; the next buyer's swap converts them to stock. The buyer pays the buy tax as usual;
the seller pays nothing, and removing the position is untaxed too. Measured exiting
100,000 tokens at launch with `sellRateBps() == 9000`:

| route | seller receives | stock tax booked |
|---|---|---|
| swap | 9,977 stock | 89,796 |
| range order | **111,070 stock** | **0** |

The auditor rated this Medium; the lead rates it **High**, because the stock-side sell
tax is the *only* revenue the protocol, the creator and the treasury have, and the spike
is the stated defence against opening-block snipers ("cannot simply dump it"). It needs
counterparty buy flow — which is heaviest exactly when the spike is on, so the sniper's
range order fills fastest when selling is meant to be most expensive. It also works
just-in-time in front of the treasury's own `buyback()`. Independent of disclosed
finding (4): that one pins the spike, this one does not pay it.
*Fix:* take `BEFORE_ADD_LIQUIDITY` and refuse every adder except the factory's one-time
seed; `lpFee` ships at 0 so third-party LPs have no honest reason to be here. Combined
with FA-3's mitigation the mined mask becomes `0x2844` — still 14 bits, same work.
CONFIRMED — `test_audit_F3_aRangeOrderExitsThroughTheSpikeUntaxed` (both orderings).

**HK-2 · Medium · The TWAP ring records a shove held for zero seconds; the file header's
"you must hold the price across real time" is false.** Unlike V3, this ring stores the
*post*-swap tick, drops any further write in the same second
(`src/libraries/TwapRing.sol:47`: `if (nowTs == last.ts) return;` — without updating the stored
tick), and extrapolates with the stored tick. Shove, swap back in the same second (ten
blocks on this chain — it need not even be atomic): the live tick returns, the ring
believes the shoved tick held until somebody else swaps. Poison weight =
(seconds until the next swap by anyone)/600 — set by how quiet the pool is, not by how
long the attacker held. Measured: after one same-second +6% round trip and 600 quiet
seconds `meanTick(600)` returns 100% of the shove, and a +6% pre-pushed `buyback()` that
an honest ring refuses now fills, burning 5.7% fewer tokens. **Not profitable at shipped
parameters** (attacker's own swaps pay the hook tax: −11.9 stock at 10%, −0.85 at the 1%
floor, to destroy 0.28 stock of buy-back value per chunk), and poisoning the other way
makes every `buyback()` revert `NotDue`. Paid griefing plus a false security claim now;
High the day anything else reads `meanTick` as a price.
*Fix (trialled by the auditor, all 236 original tests still pass):* in the same-second
branch, `r.obs[r.index].tick = tick; return;`.
CONFIRMED — `test_audit_F1_sameSecondRoundTripPoisonsTheMeanWithZeroHoldingTime`,
`…F1b_poisonWeightIsTheGapUntilTheNextHonestSwap`,
`…F1_endToEnd_poisonedRingLetsTheShovedBuybackFill`.

**HK-3 · Medium · One permanently unpayable recipient strands 100% of stock-side revenue,
forever.** `distributeStock` pays tip, protocol, creator and treasury in one atomic leg
(`HedgeFunHook.sol:217-229`); `creator` and `protocol` are immutable. Disclosed finding
(3) frames this as "waits for the block to lift" — but nothing on chain can make it lift
for a blocklisted creator, a creator contract that reverts, or an abandoned protocol
address. The treasury is then never funded, no lot is ever booked, no buy-back ever
happens, while the token keeps trading and buyers keep paying tax. A launcher can create
that state on purpose at launch, indistinguishable on the form; a creator contract that
reverts *conditionally* also chooses when the treasury's tax is booked, and so at which
oracle price its lots are costed. Measured: 497.5 stock stranded, treasury and protocol
receive 0. *Fix:* pay the treasury first, then each other recipient in its own `try` (or
credit pull-balances).
CONFIRMED — `test_audit_F4_aPermanentlyUnpayableCreatorStrandsAllStockRevenueForever`.

**HK-4 · Low · Zero-amount swaps through the empty side of the single-sided seed write
any tick out to MIN/MAX into the ring for free.** The ring write precedes the `tax == 0`
return (`HedgeFunHook.sol:154-155,168-169`), and every launch opens one spacing outside a
range with zero liquidity behind it. An attacker holding nothing wrote tick ∓887272 in
the launch second; ten minutes in `meanTick(600)` was `ok = true` and ~36× off in price.
Low because the treasury has no `buybackStock` that early and the available direction can
only make buy-backs refuse, not overpay. HK-2's fix removes the free same-second
walk-back but not the one-second hold; skip the tick update when in-range liquidity is 0.
CONFIRMED — `test_audit_F2_atLaunch_{tokenIs0,stockIs0}`.

**Disclosed (4), quantified:** re-arming the spike every 240s holds the rate ≥45% for 25%
of the time — not "indefinitely above half" — for a time-averaged 27.8% sell tax against
10% flat, at one 500-USDG chunk per cycle with the bounty paid back to the griefer. HK-1
is the way around the spike for anyone who knows about it.

### Treasury rule, oracle, calendar — no Critical/High; one Medium, in the newest code. 18/18 PoCs re-run green (`test/AuditTreasury.t.sol`)

Harness limit on every attacker number here: the pool is a real v4-core pool behind the
V3 ABI, so fills and impact are Uniswap's, but there is **no counter-flow during the
hold** — every attacker PnL is a best case for the attacker.

**TR-1 · Medium · On the closed-market path, whoever holds the pool for 600s chooses the
rule's price anywhere between the trigger and the real price**
(`src/HedgeFunTreasury.sol:90-112`; the author's argument at
`HedgeFunTreasuryBase.sol:211-218`). The author's defence — a shover is the counterparty
to the trade the shove triggers — holds only for a shove *away* from the real price.
After a **real** closure gap through a trigger, an attacker pins the pool between the
trigger and the real price: `takeProfit` sells at the pin what is worth the real price,
`buyDip` buys at the pin what is worth less. Re-pinning after each treasury sale is just
the attacker buying what the treasury sold, so every due lot is walked in one hold — the
per-call depth cap does not bound the total. **The 30% anchor is not a bound on loss**;
it only parks the rule on moves larger than 30%. Per operation: `stopLoss` correctly
shut; `takeProfit` exploitable (pin low after a gap up); `buyDip` exploitable (pin high
after a gap down).

Measured on a pool calibrated to AMD (~$309k to walk +30%), ten 50-stock lots at cost
100, a real weekend move to 125, pin at 105.5:

| | fee tier | attacker | treasury vs real price | capital (round-tripped) |
|---|---|---|---|---|
| pinned `takeProfit`, all lots | 0.30% | **+3,311 USDG** | −4,732 | ~$218k of stock |
| same | 0.05% | **+4,433 USDG** | −4,669 | ~$218k |
| pinned `buyDip` | 0.05% | +819 | −1,049 | USDG |
| deep $1.2M pool, $10–20k treasury | 0.30% | −5,689 / −3,751 | −419 / −1,890 | — |

Profitability rule (independent of gap size): the attack pays only if treasury size
traded exceeds ~6.7 × pool fee × D30 — 2% of D30 at the 0.30% tier, 0.33% at 0.05%,
**never at 1%**. Using the measured D30 table above: attackable with under $500k at a
~16% pin — META, MSTR, PLTR, BABA, DELL, AMD, TSM, INTC, USAR, SNDK; at a 5% pin add
MSFT, MU, TSLA, CRCL, GME, SLV. **Out of reach: NVDA, QQQ, SPCX, SGOV, AAPL, USO, GOOGL.**
Limits: it needs a real closure move through a trigger (with none, pinning loses money,
as the author's own test shows); Lighter trades weekends so a *low* pin is attacked by
unconstrained USDG buyers, while a *high* pin is defended only by holders of
supply-limited on-chain stock — `buyDip` is the harder direction to defend.
*Fix direction:* two non-overlapping 600s means that agree, or a much narrower band
(~5%) around the frozen feed, accepting that larger gaps wait for the open.
CONFIRMED — `test_F1c_thinPool_pinnedTakeProfitAcrossAllLots_isProfitable`,
`test_F1d_thinPool_pinnedBuyDip_measured`.

**TR-2 · Low · `book()` on the closed path makes a pinned price a permanent cost basis**
(`HedgeFunTreasuryBase.sol:228-237`). Public, unpaid, prices the lot at `health()`. Pin
at +29% during a closure, call `book()`, unwind: with no stop the lot cannot sell until
the real price exceeds 135.5 and that tax never reaches the buy-back. Attacker gains
nothing; ~$300–1.8k in fees on an AMD-sized pool. *Fix:* do not book while
`pricedOffPoolOnly()`. CONFIRMED — `test_F2_…bookAtPinnedHigh_makesTheLotUnsellable`.

**TR-3 · Low · The creator's rule has no floor against execution cost**, so "a lot never
sells below its own cost" is false net of execution
(`HedgeFunTreasury.sol:33`, `StrategyTreasuryV4.sol:65`, `HedgeFunFactory.sol:289`). With
`tp1 = 1bp` a lot returned 9,923.88 USDG against a 10,000.00 basis while `buybackStock`
recorded a profit; with `tp1 = dip = 1bp`, `lotBps = 100%` the whole treasury flips on
every Chainlink print (sandwiched: 9,196 of 10,000 after 20 prints). Drain, not yet
theft. *Fix:* factory floor `tp1Bps, dipBps ≥ 2 × (maxSlippageBps + poolFeeBps)`.
CONFIRMED (invariant break and drain); attacker profit PLAUSIBLE only.

**TR-4 · Low · The 0.5% deviation gate parks the rule on ordinary basis when the feed is
quiet** (`PoolTrader.sol:113-126`). This is the on-chain consequence of the SPY
measurement above: a valid 15h-old feed plus a legitimate 0.6% pool move closes
`health()`; the calendar says open so the closed path does not apply; everything but
`buyback` reverts until the next print. A griefer reproduces it per call for ~$37 (AMD
0.30%) to ~$1,080 (NVDA 0.05%). No funds lost. **Expect material downtime on
low-volatility listings even with no attacker.**
CONFIRMED — `test_F4_staleButValidFeed_plusLegitPoolMove_parksTheRule`.

**TR-5 · Info.** `takeProfit` writes state after the bounty transfer and `book()` is not
`nonReentrant`; a stock token with a transfer callback could have profit booked twice
(ledger 111.26 vs balance 105.63). Not exploitable unless a listed stock calls its
recipient — the repo has no stock-token source to check against, so **verify on the real
ERC-8056 token before listing**. Also: under the `2 × spikeSeconds` rule, buy-backs
landing 120–240s after the last event arm no spike, so for half of them the 600s mean is
the only sandwich defence — which is HK-2's ring.

**Convergent finding.** Two auditors independently reached the calendar-owner issue
(FA-1 here as TR F-6). The treasury pass adds the sharper half: `setOverride(day, closed)`
on a **live** trading day replaces the 0.5% gate with the 30% band and disables
`stopLoss` for every launched treasury — PoC: a pool 20% off a live feed is refused, then
accepted at 120 in the same block. Calendar owner + TR-1's pin works on any day, not
only weekends. *Additional fix:* on the closed path also require the feed to be older
than some minimum. CONFIRMED — `test_F6_calendarOwnerWidensTheGateOnALiveDay`.

## Coverage — checked and found sound

**"The seeded liquidity cannot be removed by anyone" — survived.** V4 keys the position
to `msg.sender` = the factory; the factory's only `modifyLiquidity` sits inside
`unlockCallback`, gated on `msg.sender == poolManager && _seeding`, with a positive
delta; `_seeding` is set only in `_openAndSeed`; after seeding the factory holds zero
token, zero stock and zero ERC-6909 claims; V4 forces all deltas settled before `unlock`
returns, so there is no stale delta to `take`; `donate` and LP fees only add. No owner
path, and an ownership transfer gains nothing.

**"No owner, no parameter that can change" — holds for token, hook and treasury; fails
for the calendar (FA-1).** PoC changed all 19 `Defaults` fields, re-listed the stock to a
hostile oracle pricing it at 1 USDG, closed `publicLaunch`, disabled V4, transferred
ownership to an attacker who re-listed again: ten hook observables and seven treasury
observables byte-identical, `health()` still answering from the birth oracle.

**"Holders have no claim on the treasury" — survived.** The only outflows are caller
bounties, the rule's own swaps, and burns.

**Cross-contract trust.** `bind()` once-only and called by the factory constructor;
`wire()` factory-only, once-only, same transaction; hook's `treasury`/`protocol`/`creator`
immutable; nothing can be re-pointed. **Seeding:** no attacker code runs inside the
window (hook flags `0x0044` only; plain OZ ERC20); single-sided in both token orderings
including a tick exactly on a spacing boundary; `uint160(sqrt)` cannot truncate.
**Adversarial `Request`:** `creator` recorded and never called; `hookSalt` cannot select
different bytecode; stale/reused salt, disabled listing, changed oracle or pool all
revert loudly. **Fees:** None/Native/Usdg, stray `msg.value`, reverting and re-entering
`protocol` (`nonReentrant` holds), false-returning token all covered.

**Hook — tax leg, sign and currency: all 8 cases (exact-in/out × buy/sell × ordering)
sound.** `unspecifiedIsCurrency1` matches `Hooks.afterSwap`; the taxed currency is always
the output; exact-output is refused after the ring write and the treasury exemption,
which is correct because the treasury only swaps exact-in. Delta accounting nets the hook
to zero inside the unlock; `tax ≤ 0.9 × moved` so output cannot go negative; int128 casts
cannot overflow. `afterSwap`/`unlockCallback` PoolManager-only; `afterSwap` pins
`poolId`, so a second pool on the same hook reverts on every swap and cannot write the
ring. The treasury exemption keys on the unlocker and cannot be borrowed. One mint, in
the constructor; `burn` self-only; no route sends token-side take anywhere but tip or
burn, or stock-side take anywhere but the four recipients. Ring arithmetic: int56
cumulative safe ~1,400 years, wraparound and binary search correct, the "griefer spends
the ring" case is unreachable at 1024 slots / 600s.

**Treasury — lot accounting sound** (halves, odd quantities, swap-and-pop incl. last
index, `bookedStock == Σ lots`). Units consistent under `_SCALE = 1e30`; cost basis is
USDG per raw token and the feed already carries `uiMultiplier()`, so a corporate action
does not rescale a lot. Open-path `takeProfit` never returns less than principal minus
slippage and fee for any shove inside the gate (fuzz, 257 runs).
`uniswapV3SwapCallback` accepts only the pool, only mid-swap; swap limits derive from
oracle or mean, never spot. Closed-path gates all fail closed individually (calendar
must say shut, so an open-hours outage fails closed; `oraclePaused()` honoured;
unserviceable ring refuses; `stopLoss` refused). `PriceOracle`: stale, zero, future-dated
and reverting rounds all fail closed. **`TradingCalendar` is rule-based and never runs
out**: all 20 NYSE closures for 2026–2027 match day by day over 733 days, DST flips exact
to the second, the 20:00 ET boundary exact in EDT and EST. The two previously-fixed bugs
(dip bounty sized off fill; sells must fully fill on both venues) stay fixed.

**Not assessed by anyone:** the real stock token. The repo has no model of the ERC-8056
contract — transfer callbacks, blocklist behaviour, and what `uiMultiplier()` changes do
to raw balances held by the PoolManager are all assumed, not verified.

---

## Go / no-go

**NO-GO for `setPublicLaunch(true)`. NO-GO for the first launch of any kind until the
three hook fixes land** — not because any single finding is catastrophic, but because
**everything launched is immutable by design, so a fix shipped after the first launch
never reaches it.** The bar for launch #1 is the bar for the protocol.

Overall the code is in better shape than its finding count suggests: no Critical, no way
found to remove the seed, mint tokens, re-point a launched strategy, or take treasury
funds directly; the tax accounting survived all 8 swap cases; the calendar survived a
733-day brute check. 43 PoCs, all reproducing, all re-run by the lead.

### Blockers — before the first launch (each is baked into immutable bytecode)

| # | finding | fix | size |
|---|---|---|---|
| 1 | **HK-1 High** — range orders exit untaxed through the sell tax and the 90% spike; voids the protocol's only revenue and the anti-snipe claim | take `BEFORE_ADD_LIQUIDITY`, refuse all adders but the factory seed | hook + mined mask |
| 2 | **HK-3 Medium** — one unpayable recipient strands 100% of stock revenue forever; a launcher can do it on purpose | pay treasury first, `try` each other recipient (or pull-balances) | hook |
| 3 | **HK-2 Medium** — same-second round trip poisons the 600s mean with zero holding time | one line in `TwapRing.write` (trialled: original 236 still pass) | hook |
| 4 | **FA-3 Low, but free here** — since the mask is changing anyway, add `BEFORE_INITIALIZE` to close the pre-init squat: `0x0044 → 0x2844`, still 14 bits | | mined mask |

### Blockers — before the first *listing*

| # | finding | decision needed |
|---|---|---|
| 5 | **FA-1 / TR-6 Medium** — the calendar owner holds a permanent switch over every launched strategy, and can widen the gate to 30% on a live day | renounce calendar ownership, or have `list()` refuse an owned calendar, or accept it and **correct the README's "no parameter that can change"** |
| 6 | **TR-1 Medium** — closed-market pin is profitable on thin pools | fix the path (two agreeing means / ~5% band), **or list only pools it cannot reach** — see below |
| 7 | **TR-5** — verify the real ERC-8056 stock token has no transfer callback and see what a blocklist does to the sweep | a fork test against the real token |

### Blockers — before `setPublicLaunch(true)`

| # | finding | fix |
|---|---|---|
| 8 | **FA-2 Medium** — owner can raise the fee or restate the open price under a pending launch; on main as passing `test_BUG_*` tests, absent from the README | `maxFee` + `expectedOpenPriceE18` on `launch()` |
| 9 | **TR-3 Low** — creator rule has no floor against execution cost; breaks "never sells below cost" | factory floor on `tp1Bps`, `dipBps` |
| 10 | **FA-7 Low** — `PROTOCOL` silently defaults to the deployer EOA and is immutable everywhere | require both env vars on chain 4663 |

**Constraint on all of the above:** `HedgeFunFactory` has **1,887 bytes** of EIP-170
headroom with the optimiser already at `runs = 1`. Fixes 8, 9 and FA-4 all add factory
bytecode. Run `forge build --sizes` on each; this may force a split before it forces a
redesign.

### Not blockers

FA-4 (`setDefaults` bounds), FA-5 (`lpFee` must be 0), FA-6, HK-4, TR-2, TR-4, the Info
items. Two process items worth doing regardless: **the "fork-proven" tests return early
and report PASS unless `RH_FORK=1`**, and **the repo has no CI** — so nothing currently
stops a regression in the permanence proof from merging green.

### What this means for the first listings

> The depth column below carries the overstated +30% figures: see the CORRECTION under "Cost to move a listed pool".

The audit and the listability measurement point at the same short list. TR-1 says list
only pools an attacker cannot pin for under ~$500k; TR-4 says a quiet feed parks the rule
for hours. Intersecting the 25 listable tickers with both:

| | deep enough (TR-1) | feed ticks often (TR-4) | verdict |
|---|---|---|---|
| **NVDA** | ✔ $54M | ✔ | **first** |
| **AAPL** | ✔ $5.9M | ✔ | **first** |
| **GOOGL** | ✔ $3.9M | ✔ | **first** |
| SPCX | ✔ $13M | ✔ | first, if a pre-IPO proxy is wanted on the front page |
| QQQ, SPY, SGOV, USO | ✔ | ✘ low-vol, sparse feed — expect downtime | later |
| AMZN | borderline $3.1M | ✔ | after TR-1 is fixed |
| MSFT, TSLA, MU, META, AMD, PLTR, INTC … | ✘ pinnable | ✔ | **not until TR-1 is fixed** |

## Reproducing

On this branch the factory and treasury reproductions are in `test/AuditFactory.t.sol` (9) and
`test/AuditTreasury.t.sol` (18). The hook reproductions no longer reproduce, by design; they and the three
auditors' full reports remain in the auditor worktrees under `.claude/worktrees/`, uncommitted:

```bash
# factory  (10)   agent-a66b012f572613057
forge test --mc AuditFactory -vv
# hook     (15)   agent-afe1af007aff69e38
forge test --mc AuditHook --mt test_audit -vv
forge test --mc AuditHookLaunch --mt test_audit -vv
# treasury (18)   agent-a6e812d983a5cea8c
forge test --mc AuditTreasury -vv
```

Each worktree also holds the auditor's own full report (`AUDIT_FACTORY.md`,
`AUDIT_HOOK.md`, `AUDIT_TREASURY.md`). Those worktrees were scratch space and were never
committed; this file is the record.

**Where the reproductions are on `main` now.** A reproduction asserts the bug, so it stops
passing the moment the bug is fixed. Each was therefore rewritten to assert the fixed
behaviour, naming the test it used to be, and confirmed to fail with the fix reverted:
`test/AuditHook.t.sol` and `test/AuditHookLaunch.t.sol` became
`test/AuditHookRegression.t.sol` (plus cases in `test/InteractHookTax.t.sol` and
`test/InteractFactory.t.sol`); `test/AuditFactory.t.sol` and `test/AuditTreasury.t.sol`
still exist, with the fixed findings inverted in place. Test counts quoted in this file
are as of the day it was written.
