> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Security model

What this protocol trusts, what it defends against, what it knowingly does not, and the
rules for changing it without reopening something that was closed. The evidence behind
every claim here is in [`AUDIT.md`](../AUDIT.md) (three adversarial passes, 43 Foundry
reproductions) and [STOCK_TOKEN_ASSESSMENT.md](./STOCK_TOKEN_ASSESSMENT.md).

No external security review has been done. The singleton hook, the launch window, the sell
chunk and per-listing gates went through a fifth internal round on 2026-09-21 (findings
S5-*, X5-*, R5-*; see the banner at the top of [`AUDIT.md`](../AUDIT.md)), and several
sections below exist because of it.

## The one rule that governs everything else

**Everything launched is immutable code.** A fix shipped after the first launch never reaches
it. (Two *addresses* per launched pool can move — who is paid the protocol's cut and, slowly
and vetoably, who is paid a vanished creator's; see the Safe's table below. No code, rate, rule
or treasury can.) So the review bar depends on where a change lands:

| Change lands in | Reaches | Bar |
|---|---|---|
| `HedgeFunHook` | **every strategy at once**, forever, unpatchable: there is one hook, its address is what a router allowlists, and the factory's `hook` is immutable — a changed hook means a new hook, a new factory and a new allowlist review | highest, and then some |
| `HedgeFunTreasury*`, `HedgeFunToken`, `TwapRing`, `PoolTrader` | every launch made after it ships, **forever, unpatchable** | highest: adversarial review, a regression test confirmed to fail without the fix, fork suite |
| `PriceOracle`, `TradingCalendar` | every strategy priced through that instance, forever | same |
| `HedgeFunFactory` logic | future launches; existing ones are untouched | high; and check `forge build --sizes` first |
| Listings, defaults, band ceilings, per-listing gates | future launches only | a Safe transaction, reviewed by its signers; loosening a gate needs a measured basis report attached ([OPERATIONS.md](./OPERATIONS.md#loosening-a-listings-gates)) |
| `script/`, `tools/`, `emergency/`, docs | nothing on chain | normal review |

## Who is trusted, and with exactly what

### The protocol Safe (owner of `HedgeFunFactory` and `TradingCalendar`)

| It can | It cannot |
|---|---|
| stop public launches; delist a stock; change defaults, listings, each stock's `bandCeiling` (≤ 200 bps/h) and each stock's execution gates and sell chunk (`setListingGates(stock, dev, slip, sellChunkUsdg)`, `0 < dev < slip ≤ 300`, chunk `0` or ≥ `minLotUsdg`) **for future launches** | touch any launched token, a launched treasury's assets, allowances or rule, the seeded liquidity, or anything about a launched pool beyond the two payout addresses below. On a launched treasury it has one call, the vote delegate (last row but one). It also cannot restate any of those under a launch already quoted: `terms` makes that launch revert `Restated` |
| halt the rule in every treasury on a given calendar, on any day (`setOverride(day, 1)`) | change the price the rule trades at, or open the closed-market path |
| force a day **open** (`setOverride(day, 2)`) — the live-feed path then applies, behind the 48 h age cap and the deviation gate | move treasury funds, change a tax rate, the split, the tip, the treasury a hook pays, the rule or the pool |
| list any contract as a stock's oracle for **future** launches | — that one is pure trust: a hostile owner can launch-trap new creators. Existing launches keep their birth oracle |
| vouch for a periphery contract that may call `launch` for its own caller (`setLauncher(launcher, ok)`; `HedgeFunLaunchRouter` needs it) | launch in a creator's name itself, or let a vouched launcher do more than a creator could: a launcher gets the launch-transaction exemption for **its own** swaps only. Pure trust in one respect: a vouched launcher that does not insist `q.creator` is its caller reopens X5-2 |
| move **the protocol's own payout** in a launched pool: `setProtocol(id, next)`, instant, one pool per call, and what is parked for the protocol in that pool goes with it | withdraw or rescue stock from the hook — not parked stock, not a donation. There is no such function; money leaves the hook only to a pool's treasury, its two recipients and the sweeper's tip. Nor can it re-bind the hook to another factory, or register a pool by hand |
| move **a vanished creator's payout**: `proposeCreator(id, next)`, then `acceptCreator(id)` no sooner than `TAKEOVER_DELAY` = 14 days later and no later than `ACCEPT_WINDOW` = 14 days after that, by the same owner that proposed (else `Expired`). The proposal is public (`pendingCreator(id)`, `pendingCreatorAt(id)`, `CreatorProposed`) | take the cut of a creator who is still there: one `vetoCreator(id)` from the creator's address kills the proposal. It moves no stock, so it works even for a creator the issuer has deny-listed, and it buys `VETO_QUIET` = 180 days (`noProposalBefore`) in which `proposeCreator` reverts `TooEarly` — a veto proves the creator is there, and without the quiet period an owner could re-propose the same minute and hold a creator to a transaction every 14 days for life. The owner withdrawing its own proposal buys no quiet. Anything the creator claims before `acceptCreator` is theirs |
| point **a launched treasury's votes**: `setVoteDelegate(delegatee)` — one `try`ed `stock.delegate(delegatee)`, `nonReentrant`, event `VoteDelegateSet(by, delegatee, accepted)`. **Reserved, not live**: the stock token has no vote surface today and the call emits `accepted = false` | move, approve, pledge or sell anything the treasury holds, write any of its storage, or reach the rule. There is no generic call, no setter and no `declare()` ([below](#the-treasurys-owner-can-only-point-its-votes)) |
| transfer ownership of the factory or calendar through `transferOwnership` → `acceptOwnership`; renounce the calendar's ownership | renounce the factory's ownership: `renounceOwnership` reverts `OwnershipRenunciationDisabled`. Calendar renunciation remains irreversible |

The hook has no owner of its own: `owner()` reads the **factory's** owner live, so the two
payout powers follow an `Ownable2Step` handover. The factory disables `renounceOwnership`,
so these powers remain with its owner. Nothing the owner does *on the factory* reaches a launched strategy
(`test_audit_nothingTheOwnerDoesReachesALaunchedStrategy`); what it can do *on the hook* is
those two functions, one pool at a time, and nothing else
(`test_audit_theOwnerReachesTheTwoRecipientsOfALaunchedHook_andNothingElse`,
`test_theOwnersPayoutPowersReachOnePoolAtATime`); and what it can do *on a treasury* is
`setVoteDelegate` and nothing else
(`test_theOwnerHasNoOtherCallOnATreasury_noGenericCallNoApproveNoWithdrawNoSetter`). The trust this
adds: a hostile or compromised Safe can redirect the protocol's cut at once, and a creator's
cut after 14 days if the creator does not watch for `CreatorProposed`. It cannot reach the
treasury's share, a rate, or the split between the three.

`terms` — the hash `predict(q)` returns and `launch(q, terms)` checks — exists so that the
owner cannot restate a rate, the tick spacing, a gate, a chunk, the listing's oracle or its
pool underneath a pending launch; `Request.maxFee` and `Request.expectedOpenPriceE18` cover
the two inputs that are in no address and no rate, the fee and the opening price.

### The stock token's issuer — outside anyone's control here

Every Robinhood stock token is a `BeaconProxy` on **one** beacon. `BEACON_UPGRADER_ROLE` is
held by a single address with no code and no on-chain timelock: one transaction changes
the code of all 194 tokens. The issuer also holds a deny-list shared by every stock
(checked on `to`, `from` and the `transferFrom` operator), a per-token and a chain-wide
pause, and `adminBurn(from, amount)`, which ignores both the pause and the deny-list.

- A blocked PoolManager, treasury or hook, or a paused token, **recovers fully** when
  lifted. An `adminBurn` does not, and nothing here can detect one.
- Today's implementation makes no transfer callback, charges no fee, and leaves raw
  balances alone when `uiMultiplier()` changes. **Those are facts about the implementation
  pinned in `test/StockTokenFork.t.sol`, not about the token.** CI runs that snapshot
  daily and goes red the day the issuer upgrades — at which point every conclusion in the
  assessment needs re-checking before the next listing.
- Code here is written as if the stock *could* call back: every treasury entry point is
  `nonReentrant` and pays its bounty after all effects are written.

### Chainlink

The only price source on this chain. Feeds are 24/5, update on a 0.5% move, and publish
**no heartbeat off-hours**. `PriceOracle` fails closed on: calendar shut, `oraclePaused()`,
a zero/negative/future round, or a round older than `maxStockAge` (capped at 48 h).
`oraclePaused()` is an advisory flag the token itself does not enforce — this oracle is
the only thing honouring it. There is no sequencer-uptime feed for this chain.

### Creators

Untrusted. A creator chooses name, symbol, a *listed* stock, the tax rate and their own
cut (both bounded by the factory), the rule's numbers (bounded by the treasury
constructors), and a staleness band no larger than the owner's ceiling for that stock. A creator **cannot** choose the oracle, the trading pool, the supply, the
opening price, the protocol's cut, the launch window or the execution bounds (slippage,
deviation, the sell and buy-back chunks) — each was a way to rob buyers.
The `creator` address is recorded and paid, never called in a way that can block others.
The same address is the token's `deployer`: it writes the token's page and nothing else
([below](#the-tokens-page-belongs-to-whoever-launched-it)). Treat every byte of that page
as hostile input.

### Callers

Every rule function is permissionless and paid by bounty. The caller picks neither price
nor size; bounties come out of what the call produced.

## Defences, and the attack each one answers

### The hook admits only its seeder

The tax lives in `afterSwap` and nowhere else. V4 lets anyone add a position to a pool, so
a holder could place tokens as a one-spacing range just past spot, be filled by the next
buyer, and exit **untaxed** — measured through the 90% launch spike at 111,070 stock
against 9,977 by swap. The hook therefore takes `BEFORE_ADD_LIQUIDITY` and
`BEFORE_INITIALIZE` and admits only `factory` — whoever called `bind()`, which the factory
does from its own constructor, once, for good — and only for a pool the factory has
`register`ed. The factory has exactly one code path that registers, initialises or adds
liquidity: a launch. So nobody can open a pool on this hook that the factory did not
launch (`WrongPool`), nobody can initialise a pending launch's pool first, and a swap in an
unregistered pool reverts
(`test_aPoolTheFactoryNeverRegisteredCannotBeOpenedOnThisHook_andItsSwapsRevert`).

`bind()` is open to whoever calls first. That is safe for a *factory* — its constructor
reverts `AlreadyBound` on a hook somebody else got to — and it is a deployment hazard for the
*address*: a hook squatted between its deployment and the factory's is dead, and the next
one lands somewhere else. Hence the order in
[DEPLOYMENT.md](./DEPLOYMENT.md#10-getting-the-hook-routed-by-uniswap): deploy and bind before
the address is shown to anyone. Binding is once because a second factory could register
pools that pay whom it likes, under an address that was reviewed for the first.

**Do not remove either flag, do not give the factory a second liquidity path, and do not
give the hook a second way to be bound or a pool a second way to be registered.**

### One hook address holds every strategy's stock-side payouts

This file used to argue the opposite: that the ledger was "per hook on purpose", because a
shared escrow "would hold every creator's stock at one address the issuer can deny-list,
pause or `adminBurn`". The singleton **is** that address, and the consequence is accepted,
not engineered away:

- An issuer who **deny-lists** the hook's address stops the stock leg of every sweep, for
  every strategy on every stock (the deny-list is shared by all stock tokens). Tax keeps
  accruing as ERC-6909 claims in the PoolManager, each pool's own, and is paid when the
  block is lifted. A **pause** of one stock does the same for the pools on that stock.
- An **`adminBurn`** of the hook's balance of a stock writes down every claim parked on
  that stock, across every pool, pro rata. Before, a burn had to be aimed at one hook per
  strategy.
- A **transfer fee** is a fourth thing the issuer could add by upgrade, and the hook does not measure what
  arrives: it credits what it redeemed. With a fee the hook's balance of that stock falls short of what is
  parked, the next sweep on ANY pool of that stock reads the shortfall as a burn, and every parked claim on
  that stock is written down pro rata -- the fee is socialised across that stock's pools instead of landing
  on the pool that swept (external round 2, L2-2; accepted, no stock token charges one today).
- **Trading is not affected** by any of the three: the tax is a claim minted inside the
  swap and no stock moves to or from the hook until a sweep. And what the hook holds at
  rest is small — only payouts that could not be delivered are parked; an ordinary sweep
  redeems and pays out in the same call.

Why the trade was made: Uniswap Labs' routing allowlist is per hook address, and a hook
with a returns-delta flag is reviewed individually. A hook per launch could never be
routed by the default interface; one hook can be reviewed once. And the issuer already had
the same single point one level down — every strategy's pool liquidity and every unswept
claim sits in the one PoolManager, which the same deny-list entry would stop outright,
trading included. The singleton adds the payout leg to a dependency that was already total.

What had to change so that a shared address is safe against its *own* pools is in
[the ledger section](#the-split-pays-the-treasury-first-and-keeps-a-ledger-nobody-has-to-rescue)
below: no amount is ever inferred from a balance.

### The TWAP ring keeps the last write of a second

The ring stores post-swap ticks. If it kept the *first* write of a second, a shove and its
unwind inside one second (ten blocks here) would leave the shove in force until someone
else traded — 100% of it in the 600 s mean for a price held for no time. It also refuses
to record a tick with no liquidity behind it: the seed is single-sided, so a swap can
slide through the empty side moving nothing and paying nothing.

### The split pays the treasury first, and keeps a ledger nobody has to rescue

`creator` and `protocol` were immutable when this was built, and are still not something a
recipient's failure can change. When the split was one atomic leg, a creator the
issuer blocklists — or a creator contract built to revert — stopped the treasury being
funded forever while buyers kept paying tax. Paying each recipient in a `try` fixed that
but left an undelivered cut in the balance, where the next sweep split it again (the
recipient forfeited most of it) and anyone could skim a tip off it, repeatedly.

So the hook keeps a small ledger **per pool, by role, not by address**: `owedProtocol(id)`,
`owedCreator(id)`, `owedTreasury(id)` (`owed(id, who)` is a view that sums the roles an
address holds in that pool), and per **stock** a pot: `totalOwed(stock)` is everything parked
in that stock over every pool on it. All three roles are **credited before anyone is paid** and the ledger is **debited
before the stock moves**, put back if it did not (audit round 4, L4-1/L4-2/O4-1): seen from
inside a transfer the balance is never short of the ledger, so nothing that re-enters —
`sweep(id)`, `claim`, `claimFor` and the three owner functions refuse to anyway — can mistake a payment in flight for
an issuer burn. The stock has no recipient callback today; its issuer can add one, and this
code cannot be changed. `owedTreasury` is zero except while the treasury itself cannot be paid
(deny-listed); its share then waits for it instead of reverting the whole split.
By role because the owner can now move the protocol's payout (`setProtocol`): keyed by
address, one address holding both roles would have had the creator's cut carried off with
the protocol's. What is parked goes with the role, to whoever holds it when it is paid.

The ledger was per hook when there was a hook per launch, and "new revenue is
`balance − totalOwed`" was its first rule. **Under a shared address that rule is a theft
primitive** — one pool's sweep would split its neighbour's parked stock — so it is gone, and
there is still nobody who can rescue anything: the owner can repoint the two payout
addresses and was deliberately given no way to withdraw stock. The rules that must survive
any change to this code are now:

- **no amount is ever inferred from a balance.** Tax accrues per pool (`accrued(id)`; the
  PoolManager keeps claims per `(hook, currency)`, so this is the only record of whose they
  are). A sweep redeems exactly its pool's accrual and splits exactly what it redeemed
  (`test_aSweepOfOnePoolRedeemsAndPaysOnlyItsOwn_leavingItsNeighboursTaxAndParkedStockUntouched`);
- **redeem, credit and pay are one `try`ed leg.** As separate legs, a caller who chose the
  gas so that the split died after the redeem had succeeded would orphan that pool's revenue
  for good — a per-launch hook could re-read it off the balance, a shared one cannot. At
  every gas limit a sweep either leaves the tax where it was, as claims that are still this
  pool's, or accounts for every wei of it, paid or parked (audit L4-3,
  `test_L4_3_atNoGasLimitDoesASweepLeaveTaxRedeemedAndOwnedByNobody_andALaterSweepPaysEverything`);
- a payout moves the ledger **only if the stock moved**, and never reverts. A tip that
  cannot be delivered is parked for that pool's treasury: left in the balance it would now
  be nobody's. "Cannot be delivered" includes a recipient that returns normally but leaves
  an open delta in the PoolManager (`pm.mint(self, id, 1)` from a transfer callback is
  enough): the payout runs inside the hook's own `unlock`, which would then revert
  `CurrencyNotSettled` and take every leg of every sweep of that pool with it, for good
  (audit S5-2). `payStock` compares the manager's nonzero-delta count before and after the
  transfer and reverts its own frame on a difference, so that cut is parked like any other;
- **stock above what is parked is nobody's.** A donation, or the wei a rebase rounds away,
  is never split, never tipped and cannot be claimed by any pool
  (`test_aDonationOfStockOrOfClaimsCanBeExtractedBySweepClaimOrTipFromNoPool`). All it can
  do is stand between parked claims and a burn;
- the pot is squared with the balance **before** new revenue is redeemed into it. The
  balance can fall below `parked` only if the issuer burns the hook's stock. The pot then
  drops to what is left and the stock's write-down `index` by the same proportion — two
  writes, no loop over pools — and every parked amount of every pool on **that stock** is
  read through `index now / index when last touched`, so the loss lands pro rata on the
  claims that were there when it happened. Each rebase rounds **down**, at most one wei per
  role per write-down, and the wei stays in the hook. Fresh credits are taken at the current
  index, so a later sweep's split and a treasury's fresh share are never charged, and another
  stock's pot is never touched
  (`test_anIssuerBurnScalesEveryParkedClaimOnThatStockProRata_neverAnotherStocks_neverFreshRevenue`).
  Do it after the redeem and the new tax hides the hole — the treasury's share then quietly
  refills a debt the issuer burned (measured: 64.25 paid where 69.44 was due);
- a burn of everything (or a cumulative haircut past 10¹⁸ to 1) is a wipe-out: the stock's
  `epoch` moves on, every amount of the old epoch reads zero, the index starts over, and
  later revenue does not revive the old claims.

### Exact-output is accepted for a buy at the flat rate, and nothing else

V4 lets `afterSwap` return a delta on the unspecified currency and no other, and on an
exact-output swap that is the **input**, which inverts the design. This has had four states:

1. **Taxed at face value on the input.** A rate `r` there leaves the trader `1/(1+r)` where
   the same rate on the output leaves `1−r`: 0.526 against 0.100 at the 90% spike — 5.3×
   cheaper for exactly the dump the spike exists to deter.
2. **Refused outright** (`ExactOutputUnsupported`). Safe, and every router that quotes exact
   output failed here.
3. **Accepted everywhere at `r / (1 − r)` of the input**, which leaves `1 − r` again. Round 5
   took that apart twice. A grossed-up tax is still `r` of everything the trader pays, but
   it never meets the pool's curve — only `(1 − r)` of the payment moves the price — so at
   spike rates and size the route was materially cheaper: a 500k-token sale at the 90% spike
   cost 31% fewer tokens, a 40-share buy in the 99% window 44% less (X5-3). And an
   exact-output **sell** is taxed in the token, which burns: the treasury, the creator and
   the protocol were paid only by sellers who chose to pay them (X5-4).
4. **Now:** an exact-output **buy** at the **flat** rate is accepted, taxed `r / (1 − r)` of
   the stock going in, rounded up — and because that tax is stock it is **split** like a
   sell's, not burned. An exact-output sell at any rate, and an exact-output buy while the
   launch window holds the buy rate above `taxBps`, reverts `ExactOutputRefused`; an
   exact-output buy during a sell spike is accepted, because the spike is on sells and the
   buy rate is flat then
   (`test_anExactOutputSellIsRefused_atTheSpikeAndAtTheFlatRate`).

Accrual is booked by currency, not by direction, for that one case. **Do not widen this
without re-reading X5-3 and X5-4**: the flat-rate buy is safe because at ≤ 15% the curve
effect is small and because its tax lands where a sell's would.

### The launch window is a speed bump, not a fence

A pool opens at a price where a few shares buy a tenth of the supply, and this chain makes
a block every 0.1 s: without a window the opening is a latency race that a bot wins. So for
`snipeSeconds` after `register` the **buy** rate starts at `snipeBps` (≤ 9,900: a buyer
always keeps at least 1%) and falls in a straight line to the flat tax. Both are factory
defaults frozen per pool; shipped as 9,900 over 3 s, and because `block.timestamp` moves in
whole seconds that is 99% / 66% / 33% / flat. The premium is taken in the token and
**burned** — nobody is paid by it, so nobody gains by triggering it. `buyRateBps(id)` is
the live rate. Sells and the treasury's buy-back never see it.

One buyer is exempt: **the contract that called the factory, inside the launch
transaction.** `register` writes two transient words — the pool id and the launcher's
address — and the EVM clears both when the transaction ends; a buy pays the flat tax only
if it is this pool's launch transaction **and** the swap's `sender` is that launcher. No
address list. The transaction alone is not enough (audit X5-1): a 4337 bundle, a relayer
batch or a public multicall puts strangers' calls in the creator's transaction, and whoever
ordered the bundle bought 8% of the supply at the flat rate. And the launcher is the creator
(X5-2, above), so the exemption is the creator's own first buy through `HedgeFunLaunchRouter`, and
their next transaction does not have it. Launching strategy B exempts nothing on strategy A.
`buyRateBps(id)` applies the same test to *its* caller, so off chain it reads the rate a
stranger pays.

**Accepted, and to be disclosed (X5-6):** for the length of the window the launch-transaction
buyer is the only source of tokens that did not pay the premium. A creator who buys a large
first bag can sell into demand that is paying up to 99% to buy from the pool — behind the
sell spike, which is 90% for those same seconds and still above the flat rate for 120. A
front end shows the launcher's bag for this reason too.

What it does **not** do: it does not stop a patient bot, which buys at second 3 for the flat
tax like everyone else, and it does not stop many wallets. It turns "first block wins" into
a falling-price auction over three seconds, and that is all it claims.

### A sale fills what the pool can take; the chunk is a price knob, except across a closure

The ledger moves by what the pool **actually took**, never by what it was offered. A sale is
an exact-input V3 swap whose price limit is `oracle × (1 − maxSlippageBps)`: the pool
computes its own depth, fills what fits above the limit and returns the rest, silently —
no revert, no flag. So the treasury swaps first and sizes every effect from the fill: the
lot shrinks by what sold (on `takeProfit`, by `sold × p / cost`, which is never more than
was offered and never less than `sold`, so the profit share cannot go negative), tp1 owes
what it has not yet **given up** and is done only at zero, the event and the bounty are on
what sold, and what did not sell stays in the lot at its cost
(`test_aLotBiggerThanThePoolSellsWhatFits_keepsTheRestAtCost_andSellsOutAcrossRepegs_matchingOneDeepSale`,
`test_tp1UnderShortFills_owesWhatItHasNotGivenUp_andIsDoneOnlyAtZero`). Two promises hold
on whatever filled: no part of it past the limit, and the whole of it no worse than
slippage-plus-pool-fee on average (`Slippage` otherwise). A sale the pool takes **none** of
reverts `Slippage` — a swap through an empty book still drags the pool to its limit, and a
call that sold nothing must not leave that behind, spend the closed-market pace or pay
anyone (`test_aSaleThePoolTakesNoneOfReverts_nothingChanges_noBounty`).

It used to be the opposite: a sale had to fill whole or revert, so a lot larger than the
pool's depth inside the band could **never** sell (measured 2026-09-21 at ~0.85% of room:
about $4.4k on USAR, $19k on META, $51k on CRCL, $83k on GME's 0.05% pool, $120k on AMZN)
and `sellChunkUsdg` existed to keep each sale under that depth. With partial fills the chunk
cannot brick a sale any more. **On an open market it is a price-quality knob**: it caps what
one call *offers*, and an oversized one walks the pool to the limit on every call. Measured
(`test_sandwichOfAShortFill_measured_theTreasurysShortfallIsBoundedBySlippagePlusFee`; a
2,400-stock lot, ~500 stock of depth inside 1%, no effective chunk): the treasury's
shortfall was 55–104 bps, always ≤ slippage + pool fee, and a caller who merely back-ran
their own call earned +107 USDG on a 0.3% pool and +240 on a 0.05% one; pushing first earned
less. That is why the chunk became per listing (next section).

**The operator's rule (round 6, T6-1): a listing's chunk is no more than the measured depth
between the deviation edge and the slippage limit**
([OPERATIONS.md](./OPERATIONS.md#sizing-a-listings-sell-chunk)). The caller may shove the
pool to the gate's edge before calling, so that — not the depth from the peg — is the room
a call can count on. Measured as a self-sandwich
(`test_holds_loopedShortFillsPlusOwnRepeg_neverTakeMoreThanSlippagePlusFeePerUnit_measured`
and its stop-loss twin: a 600-stock lot, ~500 stock inside 1%, a 0.30% pool, slippage 100 /
deviation 50, the attacker shoves to −49 bps before every call): with an oversized chunk
the lot went in 3 calls, the treasury fell 102 bps short and the attacker made +100 USDG
before bounty on a take-profit, +89 on a stop; with a 2,000 USDG chunk it took 34 / 27
calls, the shortfall was 80 bps and the attacker **lost** 31.6 / 27. The shortfall never
passed slippage + pool fee (130 bps) either way.

While the market is open there is no cooldown, because none is needed: nothing fills below
an *absolute* price, `oracle × (1 − maxSlippageBps)`, not one relative to where the pool
stood when the call began, and `health()`'s deviation gate — tighter by construction — is
asked before every call. A caller who loops chunks in one transaction walks the pool down
until the gate refuses, about the depth inside `maxDeviationBps`, no lower than a single
sale could ever have gone
(`test_loopingChunksInOneTransactionStopsAtTheDeviationGate_andNothingIsLost`). (The
buy-back keeps its cooldown for the opposite reason: the launch token has no oracle, so its
limit is relative to the pool.) The honest limit: **a short fill leaves the pool on the
limit, outside the deviation gate, so every rule call on that treasury reads `Unhealthy`
until someone re-pegs the pool.** A big lot still needs arbitrage between runs. Round 6
(T6-1, Low/Info) priced the griefing side of that: the caller whose oversized call parked
the rule was **paid** for it — a +15.6 USDG bounty in the PoC — where reaching the same
state with their own swap cost them −416
(`test_T6_1_aShortFillParksEveryRuleCall_andTheCallerIsPaidForIt_characterised`). It
self-heals through a ~50 bps arbitrage, nothing is lost, and no code change fixes it
without bringing back fill-whole-or-revert; the fix is the sizing rule above.

**Across a closure the chunk is still a safety knob**, and round 5 found why (R5-3). On a
banded treasury the price is then the pool's own, inside the band, and a pool can be pinned
(TR-1). 64 chunks in one transaction once sold 1,137 stock at the pin. So while
`pricedOffPoolOnly()`, and only then, `takeProfit` sells at most one chunk per
`POOL_ONLY_SALE_INTERVAL` = 1 hour (`lastPoolOnlySaleAt`; `NotDue` otherwise), and the pace
is spent only by a sale that happened
(`test_acrossAClosure_thePaceIsSpentOnlyByASaleThatHappened_andIsStillOneAnHour`) — since
round 6 that includes a call that returns normally having sold nothing: a dust tail or a
one-wei lot used to take the hour and make the honest lot beside it wait (T6-2, fixed:
`_poolOnlyPace()` runs only on the path that reaches the pool;
`test_T6_2_aDustTailDoesNotSpendTheClosedMarketHour_theHonestLotBesideItStillSells`). Partial
fills changed the arithmetic here too: while a sale had to fill whole, an oversized chunk
sold *nothing* at a pinned pool; filling short, each hourly sale is `min(chunk, depth)` —
~770 stock in the R5-3 fixture. So a launch with `bandBpsPerHour > 0` is born with
`min(listing's chunk or the default, the default)`
(`test_aBandedLaunchIsBornWithNoMoreThanTheDefaultSellChunk_anUnbandedOneWithItsListings`):
a listing can lower a banded treasury's chunk, never raise it. `stopLoss` already refuses a
pool-only price. TR-1 is still open; this keeps its per-event cap.

Two smaller repairs from round 5, both in `HedgeFunTreasuryBase`: a `stopLoss` that shrinks
a lot mid-tp1 clamps `tp1Left` to what the lot still holds (R5-1: it used to leave
`tp1Left > qty` and freeze the lot on a panic; the matching clamp on the `takeProfit` side
was unreachable once the stop clamps, and has been removed), and a principal worth less than
one unit of USDG skips the swap (R5-2: the V3 pool refuses a sale that brings back nothing,
and a chunked lot's remainder could land there and never leave).

### Execution gates are per listing, and the owner's — never the creator's

One `maxDeviationBps`/`maxSlippageBps` pair for every listing forced every stock onto
whichever pool happened to fit it: measured, a 1% fee-tier pool sits a median 56 bps from
Chainlink and a 0.05% or 0.3% one about 15. `setListingGates(stock, dev, slip,
sellChunkUsdg)` gives a stock its own pair for **future** launches; `(0, 0)` clears it back
to the defaults; anything else meets the same bounds the defaults meet
(`0 < dev < slip ≤ 300`), which are the treasury constructor's own. The fourth argument is
the stock's own `sellChunkUsdg`, falling back on its own: `0` is the default, anything else
is at least `minLotUsdg` — checked when set and again at launch, because `minLotUsdg` can be
raised afterwards (`predict` and `launch` then revert `BadRequest` rather than give birth to
a treasury whose chunk is under a lot). `listingGates(stock)` returns all three.

It is owner-only on purpose. `maxSlippageBps` is the most a sandwich takes from the
holders' treasury on **every trade it ever makes**; a creator who could pick it could sell
that to a searcher. Loosening it is therefore the most consequential thing the Safe can do
to future holders of one stock, and the operational rule is that no such transaction is
signed without a measured basis report from `tools/band_backtest.py` attached
([OPERATIONS.md](./OPERATIONS.md#loosening-a-listings-gates)).

Two side effects. It moves the creator's rule floor — `tp1`, `dip` ≥ `2 × (slip + pool
fee)` is enforced in the treasury constructor, so a rule that was launchable yesterday
fails today as an opaque `TreasuryDeployFailed()`; **front ends must read `listingGates`**.
And it cannot be used against a launch already quoted: the gates and the chunk are
constructor arguments, so they are in the treasury's address, which is in `terms` — that
launch reverts `Restated`
(`test_gatesOrChunkMovedBetweenTheQuoteAndTheLaunchRevertRestated`). (Accepted, R5-5: when
the new slippage lifts the floor past the quoted rule, the treasury constructor fails
*before* the terms are compared, so that launch dies as `TreasuryDeployFailed()`
(`0xb94a14a6`; it was the string `"treasury deploy"` until 2026-09-21), not `Restated`.
Same outcome, worse message — one more reason the front end reads the gates.)

### The treasury's owner can only point its votes

A launched treasury used to have no owner at all. It now has `owner()` — the factory's
owner, read live, so it follows an `Ownable2Step` handover. Factory renunciation is
disabled, and that owner has exactly one call: `setVoteDelegate(delegatee)`, which makes
one `try`ed `stock.delegate(delegatee)` to the one target fixed at birth and emits
`VoteDelegateSet(by, delegatee, accepted)`.

**It is a hatch, reserved and not live.** The stock token has no vote or delegate surface
today, so the call emits `accepted = false` and nothing else happens; nobody can vote
tokenised stock on this chain, and front ends must say so. It ships anyway because the
token is upgradeable by its issuer ([STOCK_TOKEN_ASSESSMENT.md](./STOCK_TOKEN_ASSESSMENT.md))
and a launched treasury is not: a hatch that is not there at birth can never be added, and
shares the protocol holds should be voted through the protocol, not stranded.

What it cannot do: it keeps **no state of its own** -- the token is the record, and the only slot it touches is the
reentrancy guard's, set and restored within the call (external round 2); it moves, approves,
pledges and sells nothing; the rule never reads `owner()`. It is `nonReentrant` because the
callee is that same upgradeable token — a `delegate` that calls back finds every entry
point shut. The call is contained: a revert, garbage, a self-destruct or a `delegate` that
burns all its gas leaves `accepted = false` and the 1/64 the EVM holds back, which covers
the event. There is no gas cap on purpose — a real checkpointing `delegate` writes several
fresh slots, and a number frozen here could make the hatch useless for good; uncapped, a gas
bomb costs only the owner who chose to call. **Not defended:** an upgrade that makes
`delegate(address)` itself approve-like. Whoever can do that can already `adminBurn` the
treasury's balance outright. There is no `declare()` by decision: a statement of voting
intent can be made off chain or by a separate notice contract. Proven in
`test/TreasuryVote.t.sol`, including
`test_everySelectorInTheBytecodeButTheNine_sentByTheOwner_writesNothingAnywhere`.

Not a lawyer's note: exercising the votes of pooled securities is a legal question, to be
settled before the hatch is ever *used*.

Round 6's conclusion on trust: the hatch gives power to nobody but the stock's issuer, who
can already burn the treasury's balance.

### The token's page belongs to whoever launched it

`HedgeFunToken` carries a logo, a description, five links (`twitter`, `telegram`,
`discord`, `website`, `farcaster`) and an `extraURI`, in the shape of pons' launch token:
`logo()`, `description()`, `socials()` and `getTokenInfo()` have pons' selectors and return
tuples, so a tool written for a pons token reads ours unchanged
(`test_theReadersHavePonsSelectors`). It is on the token and not in a registry because a
launched token is immutable, third-party tools read the token, and a v1 token born without
it could never gain it.

Who may write, and nobody else (`testFuzz_nobodyButTheDeployerAndTheEditorMayWriteAnything`,
`test_theFactoryThatMintedItHasNoSayInTheEntry`):

- **`launcher`** — immutable, whoever the supply was minted to: the factory. ONE call,
  `initMetadata(info)`, which works only while `updatedAt == 0` and the entry is unlocked, and
  which the factory makes only inside `launchWithMetadata` -- a launch that `q.creator` sent,
  or a vouched launcher that insists `q.creator` is its caller. So the first entry is the
  creator's words, written in the launch transaction, and the event names the creator. A
  plain `launch` leaves that one write unspent and unreachable: nothing else in the factory
  calls it (`test_aPlainLaunchLeavesTheCardEmpty_andNobodyCanSpendTheFactorysWriteAfterwards`).
  A field over the caps reverts the WHOLE launch (`TooLong`): a launch form validates byte
  lengths before sending.
  Two things round 8 of the audit asks a reader to keep in mind. **`updatedAt != 0` does not
  mean "has a card"**: a launch may carry an empty page, which stamps the time and emits an
  empty `MetadataSet` (P8-1) -- a front end checks the fields. And **"the first entry is the
  creator's words" is only as true as every vouched launcher** (P8-2): `HedgeFunLaunchRouter` refuses
  any `q.creator` but its caller; a launcher the owner vouched for that did not would write a
  first page in a victim's name, once, with the event naming the victim (the victim can
  overwrite it; an indexer that reads a page once would keep the forgery). Read a launcher for
  that one line before `setLauncher`.
- **`deployer`** — immutable, the launch's `q.creator`. `setMetadata`, `setEditor`, `lock()`.
- **`editor`** — one address the deployer appoints (a Safe does not want to sign for a
  Telegram link). `setMetadata` only; it can neither appoint nor lock.
- **`lock()` is irreversible.** After it all three calls revert `IsLocked`, the editor
  included, and the entry is exactly as immutable as pons'. An empty entry can be locked
  empty.

**There is no protocol power here.** Not the factory, not its owner, not the hook. And
nothing in the metadata half calls `_mint`, `_burn`, `_transfer` or `_approve`: `deployer`
confers nothing over supply, balances or allowances
(`test_noMetadataCallMovesABalanceAnAllowanceOrTheSupply`,
`test_theDeployerHasNoHandleOnAnyonesTokens`). There is no external call, so nothing to
re-enter. Every string is capped in **bytes** — 256 per link, 1024 for the description —
and every cap is checked before anything is written. A maximum-size first write costs about
2.2M gas, a typical one 35–220k; the writer pays.

**It is keyed to the launch-time creator on purpose**, not the hook's payout `creator`. The
owner's 14-day vetoable takeover moves where a vanished creator's fees go; moving fees must
not rewrite a page. So after a takeover the page's editor and the payee are different
addresses. A creator that is a contract which cannot make the call (or `address(0)`) leaves
the entry empty for ever (`test_aCreatorContractThatCannotCall_…`); the token is otherwise
unaffected.

**What this does not defend:** the strings can change until locked, and a link people
trust can be swapped for a phishing one. The contract's answer is visibility — every change
is a `MetadataSet` event carrying the whole new value, `updatedAt` is on chain, `locked` is
readable — and **nobody can remove an entry on chain**, the protocol included. The rest is
the front end's job. A front end MUST:

- **escape everything**, and never render any field as raw HTML or Markdown-with-HTML. The
  description is 1 KB of attacker-chosen bytes; the caps count bytes, not characters, so
  expect malformed UTF-8 too;
- **allowlist URL schemes** — `https` and `ipfs`, nothing else. No `javascript:`, `data:`,
  `http:`, `file:`; a link that fails the check is shown as text or not at all;
- **never fetch `logo` or `extraURI` server-side without a host allowlist** (SSRF: the
  string can name your metadata endpoint or an internal host). Fetch through an allowlisted
  IPFS gateway or an image proxy that refuses private ranges and redirects into them;
- **show `locked` and `updatedAt`**, so a page that changed an hour ago looks like one;
- **show that the page's editor is the launch-time creator** (`token.deployer()`, and
  `token.editor()` if set), and that it **may differ from the payout creator**
  (`hook.creatorOf(poolId)`) after a takeover — show both when they differ;
- **keep an off-chain hide list** for phishing entries. Nobody can delete one on chain, so
  taking a page down is a decision the front end makes and owns.

From the token's audit (round 7), on top of the above:

- treat **all nine strings** as hostile bytes -- `name` and `symbol` too (capped at 64 and 32
  bytes at launch, not validated): decode as UTF-8 replacing invalid sequences, strip control
  characters, bidi overrides (U+202A-E, U+2066-9) and zero-width characters;
- reject protocol-relative URLs and URLs with embedded credentials; render links with
  `rel="noopener noreferrer nofollow"`; show the real hostname with punycode decoded and
  flagged; check each social link's host against its field (x.com, t.me, discord.gg,
  warpcast.com);
- on a server-side fetch: block private and link-local ranges AFTER DNS resolution, follow no
  redirects, cap size, time and content type, never serve SVG inline, and parse `extraURI`'s
  JSON against a schema;
- index `MetadataSet`, `EditorSet` and `MetadataLocked` and show the change history; flag a
  link that changed recently;
- **a lock needs the editor gone** (K7-1): the UI walks a creator through dismiss -> re-read
  -> lock, as three deliberate steps.

Proven in `test/StrategyTokenMetadata.t.sol`.

### The deviation gate checks spot **and** the 600 s mean

Against Chainlink while the market is open. Swap limits derive from the oracle or the
mean, never from spot, so an atomic shove cannot become the execution price.

### A lot's cost is never taken from the pool alone

`book()` is public and unpaid. Pinned through a closure it once costed a lot 29% high for
good. `book()` and `stopLoss()` refuse while `pricedOffPoolOnly()`.

### The rule must clear its own execution cost

`tp1`, `dip` ≥ `2 × (maxSlippageBps + poolFeeBps)`. Below that a lot "sold above cost"
returned less than it paid.

### `setDefaults` mirrors every constructor bound

Because a constructor's revert reason does not survive CREATE2 (`setListingGates` mirrors
the same gate bounds; the hook's bounds are checked by `register`, whose reason does
survive, and are mirrored anyway because a default that fails there fails every launch).
Also `sellChunkUsdg ≥ minLotUsdg`: a chunk under a lot is thousands of calls with bounties
that floor to zero. Also `lpFee` must be 0: an
LP fee accrues to the seeded position, which nobody can ever touch.

### The calendar owner can halt and only halt

The closed-market path asks `isScheduledClosure`: shut by the schedule **and** untouched
by the owner. An override can therefore neither open that path on a live day nor leave it
running on a weekend.

## Known and accepted

These are open by decision. Do not "fix" one without reading its entry in `AUDIT.md`.

### TR-1: the staleness band bounds the pin, it does not remove it

While the market is shut the pool is the only live price. After a **real** gap through a
trigger, whoever can hold the pool for one TWAP window chooses where the rule trades
between its trigger and the real price (+3,311 USDG on an AMD-sized pool, ~$218k
round-tripped). The attacker's break-even is `traded size > ~6.7 × pool fee × D30`, where
D30 is the cost to walk the pool 30% — **the pin distance cancels**, so no band width makes
the attack unprofitable; a band only caps the loss per event, at `bandBpsPerHour × feed
age`. A depth-scaled cap would read active liquidity, which a narrow position inflates for
nothing.

So closure trading is opt-in twice over. A creator picks `bandBpsPerHour` at launch, but
only up to `factory.bandCeiling[stock]`, which is **0 for every stock until the Safe raises
it** (hard cap 200). With 0 the treasury is Chainlink-only, byte for byte the audited path,
and sleeps through closures. Raising a ceiling is a Safe transaction, reaches future
launches only, and belongs only on pools that cannot be held cheaply — and depth is a
property of today while a launch is forever. Replay a candidate first with
`tools/band_backtest.py`; see [`LISTING_CANDIDATES.md`](../LISTING_CANDIDATES.md).

Since round 5 the loss per event has a second bound: on the pool-only path `takeProfit`
sells at most one chunk per `POOL_ONLY_SALE_INTERVAL` (1 hour) per treasury (R5-3). The
thin-pool pin test that used to walk all ten due lots through the pinned price in one go
(`test_F1c_thinPool_aPinnedTakeProfitSellsOneLotAnHour_notEveryLot`) now sells one, and
what the pin costs to set up is no longer spread over ten sales. Whether that single sale
still pays for the pin depends on the pool's fees — measured −775 USDG for the attacker on
one fee tier, +249 on the other (the thin-pool fixture runs at 0.30% and at 0.05%). So TR-1 stays **bounded, not solved**: what a treasury can
lose to a **pulled** price is one sale an hour.

"Pulled" is the whole of that claim (round 6, T6-3, pre-existing). The pace keys on
`pricedOffPoolOnly()`, which is false while the pool's mean sits within `maxDeviationBps`
of the *stale* feed. A lot that was already due at Friday's last print therefore sells
across the closure **unpaced**, chunk after chunk — at a price Chainlink signed, through the
audited open-market gate, which is why it is documented and not changed
(`test_T6_3_onAClosure_aLotDueAtTheStalePrintSellsUnpaced_whenThePoolIsHeldOnTheFeed_characterised`).

The bound, with the shipped numbers
(`test_holds_TR1_aPinnedWeekendSellsAtMostOneDefaultChunkAnHour_49SalesIn48Hours`): a
48-hour closure, the pool pinned throughout, a caller every hour, the band at its 3000 bps
cap, a 2,000 USDG chunk — **49 sales, at most 98,000 USDG of notional given up at the rule's
price** (146,000 on a 72-hour closure). The loss is `notional × (real ÷ pin − 1)` plus
slippage plus pool fee: a real price of 130 against a pin of 106 is about 22.8k USDG. It
scales with the default chunk, which is why a banded launch can never be born with more.

Two properties of the band that must survive any change to it: it exists **only** under
`isScheduledClosure` (never on an open day, never on a day the owner forced shut — that is
the emergency brake), and the audited open-market gate runs first for any band.

### TR-4: a quiet feed parks the rule

A valid 15-hour-old feed plus a legitimate 0.6% pool move closes `health()` until the next
print. No funds at risk; expect downtime on low-volatility listings (SPY, QQQ, SGOV).
Note the asymmetry before "fixing" this with an age-scaled tolerance: in open hours a
quiet *deviation-triggered* feed is evidence the price has **not** moved.

### The buy-back can be griefed, not robbed

Bounded by the hook's 600 s mean. The sell spike can be re-armed every `2 × spikeSeconds`
at the cost of a buy-back chunk: time-averaged sell tax 27.8% against 10% flat.

### First-buyer economics

The seed is a constant-product curve with virtual stock reserve `supply × openPrice`:
spending that much stock buys ~45% of supply. Priced by the curve, not a drain — and the
reason `expectedOpenPriceE18` exists.

### Launching with capital is periphery, and cannot be anything else

`HedgeFunLaunchRouter` does three things in one transaction: launches, buys the token for the
launcher with `buyStock`, and sends `seedStock` to the treasury and books it as the first
lot. It is not in the factory, and that is the security decision rather than the bytecode
one: a launch, a swap and a transfer are each permissionless, so anyone with a contract of
their own has always been able to do them atomically. A first buy therefore cannot be
capped or forbidden by the factory; putting it there would only have added a second code
path through the contract that seeds every pool. What a buyer of a new token should read
is on chain either way: `LaunchedWithCapital(id, launcher, buyStock, tokensBought,
seedStock, booked)`, or simply the first swap in the pool.

- The first buy pays the ordinary buy tax and is priced by the same curve as anyone's
  (`test_theFirstBuyPaysExactlyWhatAStrangersBuyPays`). The launch starts the sell spike,
  so selling it straight back is the most expensive trade the pool offers — **for
  `spikeSeconds` (120 s), and not a second longer.** Measured (audit R4-1; 10% tax, opening
  FDV 50 shares): a first buy of 6.25 shares takes 10% of supply and the next buyer gets 79%
  of the tokens per share they would have; 50 shares takes 45% and leaves 25%; 450 takes 81%
  and leaves 1% — the multiple is `1/(1-f)²`. With 50 in from the launcher and 50 from the
  public, the launcher's bag sells 121 s later for 77.55. None of this is new — a contract
  could always do it — but a front end **must show the launcher's bag** next to the token
  (`tokensBought / supply` from `LaunchedWithCapital`, or the launcher's balance), because
  it is the single most important number about a new launch.
- Through the router the launcher **is** the creator (`q.creator == msg.sender`, else
  `NotYourLaunch`), and since round 5 the factory asks the same of everyone: `launch`
  reverts `BadRequest` unless the sender is `q.creator` or a launcher the owner has vouched
  for (`setLauncher`) — which the router must be, or it cannot launch at all. The salt is
  `(symbol, creator, nonce)`, so a copied launch used to collide with the original; round 4
  thought that only bought the copier a strategy that pays the victim (R4-2), round 5 found
  it also bought them the opening's tax-exempt buying (X5-2).
- The seed is **one-way**. The treasury has no withdrawal; what the lot earns buys the
  token back for every holder. That is why the two are offered together: a creator who
  funds the treasury and holds no tokens has made a gift.
- **A strategy whose stock falls before it ever rises can act.** A dip is measured from
  `lastSalePrice`, which used to exist only after a sale: a treasury that started with stock
  and watched it fall could do nothing, USDG or not. The FIRST lot ever booked now sets it
  (`test/DipReference.t.sol`); a sale or a dip buy replaces it as before, and no later lot
  moves it. `seedUsdg` is a plain transfer -- the reserve is the treasury's USDG balance -- so
  a creator may start with stock, with both, in any ratio. Three things that follow:
  (1) on a treasury nobody seeded, a stranger can choose the MOMENT of the first booking by
  donating a minimum lot; the reference is still the oracle's price at that moment and the dip
  is still bought at the oracle's price, so they move when a dip is due and nothing else;
  (2) on a BANDED treasury a seeded reserve is exposed to a closure from its first weekend
  rather than after its first sale. One rung spends at most `lotBps` of the reserve, and what
  it loses is the REAL gap, not the band: loss per rung ≈ `lotBps × reserve × (pin − real) / pin`
  -- the band only bounds which rungs a pin can reach (measured at 5 bps/h, real gap −10%:
  7.5% of the spend with Friday's print as the reference, 10.4% with the first rung adjacent
  to the feed; 20.4% at a −20% gap). Each further rung needs another `dipBps` down, so a
  closure is a ladder of `min(band × age, real gap) / dipBps` rungs: 1–3 at the first batch's
  numbers, worst measured 766 of a 10,000 reserve (band 10, `lotBps` 5000, dip 300). An hourly
  pace would not remove one rung (audit round 9 tried it), so there is none; what bounds the
  loss is `lotBps` and the reserve against pool depth -- in the test pool a pin only paid its
  holder at `lotBps` 5000 with dip ≤ 500. **And a lot is booked only at a LIVE Chainlink
  print** (D9-1): while a pool is held onto Friday's frozen feed `health()` answers with that
  feed, and a lot booked there planted a 48-hour-old dip reference after the real gap, which
  the same closure then bought against. Out of hours `book()` waits, and `HedgeFunLaunchRouter`'s
  `mustBook` unwinds a weekend launch; (3) **the on-chain score can be
  bought, so a page must not compute it from balances.** `stockEquivalentHeld()` counts the
  treasury's whole USDG balance and `totalStockReceived` counts booked stock only, and anyone
  may send USDG to any treasury at any time: a creator who sends 100 USDG to a treasury that
  has received 100 USDG of stock doubles its "held / received". Donations were always possible;
  seeding makes USDG-before-any-sale an ordinary state, so it will be seen. No contract change
  is wanted. A front end derives the rule's score from EVENTS -- reserve the rule earned =
  Σ take-profit and stop proceeds − Σ dip spends − bounties -- and shows whatever
  `reserveUsdg()` holds above that separately, as seeded or donated, outside the score
  (`LaunchedWithCapital.seedUsdg` names the launch's part of it). The same is true of stock: a
  donated lot and a tax lot are indistinguishable on chain (`LotBooked` flags both alike). And a
  label: `lastSalePrice` is "the dip reference" now; it is no longer always a sale.
- `book()` declines when the oracle is unhealthy (a weekend) or the seed is under
  `minLotUsdg`. The stock is the treasury's regardless and anyone may book it later, at
  that day's price; `mustBook = true` unwinds the whole launch instead.
- The router pulls only from `msg.sender`, keeps no balance and leaves no approval behind
  (the fee approval to the factory is exact and consumed). An unlimited approval TO the
  router cannot be spent by anyone but the approver. It confers nothing when
  `publicLaunch` is off: the factory sees the router as a stranger.

### Operational limits

- `HedgeFunFactory` has 6,469 bytes of EIP-170 headroom with the optimiser at `runs = 1`,
  and `TreasuryDeployer` 967 — the deployer carries the treasury's creation code, so that is
  what the treasury has left to grow. (`TokenDeployer`, which carries the token's, has room
  to spare: 8,844 B.)
- The stock leg is V3 only. A stock whose depth is V4-only (COIN has no V3 liquidity; SPY is
  ~13x deeper on V4) cannot be listed until v2 ([ROADMAP.md](./ROADMAP.md)).
- A look-alike treasury can report `factory() == <the real factory>`. Front ends must
  authenticate a strategy via `factory.strategies(id)` or the `Launched` event, never via
  what a contract says about itself.
- The deploy script's "has code" check is a proxy for "is a Safe": any contract passes,
  and so does an EOA carrying EIP-7702 delegation code — which low-entropy keys on this
  chain often do. A human still reads the printed addresses.

## Rules for changing the code

1. **Reproduce first.** Write the test that demonstrates the problem and watch it fail the
   right way before touching `src/`.
2. **Then fix, and turn the reproduction into a regression test** that names what it used
   to reproduce.
3. **Revert the fix and confirm the test fails.** A regression test that passes both ways
   is worthless. Every fix from the audit was checked this way.
4. **Never leave a `test_BUG_*`.** That prefix means "passes while a known bug is present";
   CI fails on any such function.
5. Run `forge build --sizes`, `forge test`, `RH_FORK=1 forge test --mc "StrategyForkTest|StrategyMultiPartyFork|StockTokenFork|DeployGuardsForkTest"`
   and `FOUNDRY_PROFILE=emergency forge test --mc EmergencyTest`. The fork suite holds
   `test_fork_liquidityIsUnremovable_byAnyone`, the permanence proof.
6. If the change touches an owner lever, a calendar, or `health()`: update
   [`emergency/`](../emergency/README.md) and its test in the same PR. A runbook that
   drifts from the contracts it drives is worse than none.
7. Say in the PR what is **not** fixed.

## Reporting

Report a suspected vulnerability privately to the repository owner before opening an
issue. If funds or users are at risk right now, go straight to
[`emergency/README.md`](../emergency/README.md) — and read its "do not halt" rows first.
