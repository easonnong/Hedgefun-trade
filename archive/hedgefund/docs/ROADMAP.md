> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Roadmap

The current agreed direction comes first. The later sections retain the original release rationale and research;
they are not evidence that a feature is deployed. Nothing below is a commitment to a date. Historical backtest
numbers come from [`rule-backtest/`](./rule-backtest/README.md) or [`band/`](./band/).

## Current plan — agreed 2026-10-01

### 1. Consolidate and verify the current V2 release

- Review and reconcile the stacked frontend, protocol and keeper PRs before merging their final release branches.
  A successful preview build is not a strategy audit, and merging into another feature branch does not put code
  on the default branch or activate a deployment.
- Keep the current launch, bonding curve, graduation, permanent LP, fee accounting and actual-fill keeper rewards.
  Creator-parameter, ETH-market and percentage-engine changes each retain their own source and deployment gates.
- Rehearse the final combined testnet version: launch, multiple buyers/sellers, execute, partial fills, graduation,
  liquidity fees and buyback. Test sniping, concentrated ownership, sudden selling and insufficient liquidity.
  Publish only the capabilities established by the corresponding deployment proof.

### 2. Add Covered Call as a new immutable strategy kind

**Decision: build a dedicated options strategy, rather than upgrade existing strategies or their fund-holding
Treasuries.** The protocol Safe governs admission of new engine, policy and adapter versions; a creator selects a
registered version when launching. The launched strategy binds its execution code, configuration and dependencies.
Registering a later version does not replace an earlier strategy, move its funds or rewrite its parameters.

The existing `V2TreasuryDeployer.registerEngineKind` path accepts a new engine version, configuration schema and
capabilities. Its constructor/configuration layout and the Factory/Hook/LP interfaces must remain compatible.
The current spot engine explicitly rejects options; reserved capability bits are not an options implementation.
Use a separate options policy/intent interface with bounded calls and return data.

First delivery:

- A single-underlying, fully collateralised Covered Call engine, fixed policy and versioned market adapter.
  Reuse launch/graduation and LP infrastructure where interface and bytecode-size checks permit.
- Separate available stock, locked collateral, outstanding options, premium and settlement proceeds. No naked
  calls, duplicate pledges or spending collateral through a spot sale, buyback or dividend.
- Commit coverage, strike/expiry bounds, minimum net premium, settlement rules, fees and keeper rewards at launch.
  Record each position's actual terms and account from actual transfers/fills, not a requested notional.
- Make expiry, exercise, lapse/cancel where supported, settlement and release paths callable independently of
  the strategy decision loop. A closed spot market must not itself strand an expired position.
- Initially route net option income through a disclosed, fixed buyback allocation; holder cash dividends are a
  separate capability, not an implied claim on existing treasury assets.
- Extend the launcher and keeper with the options kind's own configuration, positions, actions and events.

There is already a standalone RFQ escrow in
[CoveredCallDesk PR #105](https://github.com/keyuyuan/hedgefund/pull/105). Review its latest source, settlement-price
authority, feed/unit assumptions and deployment evidence as a candidate option leg. Its existence does not make
an existing Treasury an options writer, establish a live market-maker counterparty or complete strategy integration.
Do not replace its concrete settlement design with an invented AMM option interface.
The candidate Desk includes a trusted owner backstop after expiry plus 14 days: the Safe can choose the settlement
price and force NetShare settlement. Binding the adapter/engine code does not remove that pricing authority;
disclose it in the launch terms or design and audit a different settlement model before admission.

Release gates: settle on the actual desk/market, adapter, counterparties and testnet settlement setup; audit the
engine and escrow together; test partial/no fill, double collateral use, in/out-of-money settlement, early/late
exercise, price-source failure, market closure, issuer transfer restrictions and actual-fill keeper payment.
Enforce EIP-170/EIP-3860 without raising local limits. Existing V1/V2 behavior must remain intact.

### 3. Extend assets and income capabilities one integration at a time

- Add vault/share assets through audited ERC20 share, oracle and venue adapters. Native NFTs need an explicit
  custody, valuation and redemption model; an NFT address is not the current strategy's ERC20 underlying.
- Current asset execution and payment hops use canonical V3 pools. Another AMM needs its own audited execution
  adapter/core; adding a pool address to a catalogue does not make it compatible.
- Any future upgradeable integration catalogue stays outside strategy custody and existing Factory ownership.
  Already-launched strategies use their creation-bound dependencies rather than following a mutable catalogue.
- Cash dividends need a defined income bucket and verifiable eligibility/claim mechanism. A new immutable
  strategy type may include them; existing tokens do not acquire historical balance checkpoints or withdrawal
  rights merely because a new module is registered.

The protocol Safe is the agreed governance authority. Before release, verify the real chain-specific Safe and
its threshold, register only audited versions, and expose the strategy's selected version and risk terms to users.
The proposed whole-Treasury proxy / generic feature-vault refactor is deferred. These governance and asset plans
are not an instruction to retrofit upgrade authority into existing strategies.

## Original release positioning

A **strategy meme-stock launchpad**. On this chain the defining trade is already a memecoin quoted in a tokenised
stock (pons: 26 equity and ETF quote assets, about a quarter of its curve volume; see [`../ref/CLAUDE.md`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/ref/CLAUDE.md)
for what was verified from its source). The difference here is where a trade's fee goes and what it does next:

| | pons V2 (read from source) | this launchpad |
|---|---|---|
| fee on a trade | 1% (+ up to 10% creator tax) | the creator's `taxBps`, 1-15%, both ways; a decaying sell spike at the open |
| where it goes | 30% protocol / 35% creator / 35% "buy-back" | buy side: burned. Sell side, in the stock: ~70% treasury / 20% protocol / 10% creator |
| the buy-back | bought tokens are **locked**, vesting over 5 years to fee payers | bought tokens are **burned** |
| what sits behind the token | the locked pool | the locked pool AND a treasury nobody can withdraw from, trading that stock under a rule the creator published at launch and nobody can change |

What the narrative may claim is what a reader can check on chain: every sale adds real stock to a treasury with no
withdrawal function, liquidity is locked for good, supply only falls, and a rule with no stop never sells a lot below
its cost. What it may NOT claim: that the rule beats holding the stock (across 193 stocks the backtest puts most at
about 1.00), a NAV or per-token value (nothing is redeemable), or the words ETF and fund. Value depends on volume --
no trades, no tax, nothing turns.

## v1 -- this release

v1 is no longer "the contracts as they were on 2026-09-20". Seven things that were v2 candidates or did not exist went
in before the first launch, because each either cannot be retrofitted to an immutable strategy or decides whether
anyone can trade it at all -- and one thing came out:

- **One `HedgeFunHook` for every strategy**, at one mined address, because Uniswap Labs' routing allowlist is per hook
  address and a delta-returning hook is reviewed individually. What it costs — one address the stock's issuer can
  deny-list or burn for every strategy at once — is in [SECURITY.md](./SECURITY.md#one-hook-address-holds-every-strategys-stock-side-payouts);
  getting it routed is [DEPLOYMENT.md](./DEPLOYMENT.md#10-getting-the-hook-routed-by-uniswap).
- **`terms`**: `launch(q, terms)` takes the hash `predict(q)` returned, so nothing the launcher was quoted can move
  underneath them. And a launch is sent by its own creator (or `HedgeFunLaunchRouter`, once the owner vouches for it).
- **A buy-side launch window** (99% falling to the flat tax over 3 s, burned; the launcher's own in-transaction buy
  exempt). A speed bump against first-block sniping, not a fence against patient bots or many wallets.
- **Exact-output buys at the flat rate**, so a router that quotes exact output does not simply fail. Everything else
  exact-output is refused, for the reasons round 5 measured.
- **Sales that fill partially, and `sellChunkUsdg`** -- was v2 item 7. A sale used to have to fill whole inside the
  slippage band or revert, so a lot larger than the pool's depth there could never sell (measured 2026-09-21: about
  $4.4k on USAR, $19k on META, $51k on CRCL, $83k on GME's 0.05% pool, $120k on AMZN). Now the pool computes its own
  depth: a sale fills up to `oracle x (1 - maxSlippageBps)`, the lot gives up only what sold, and a sale that sells
  nothing reverts. The chunk caps what one call OFFERS. On an open market that makes it a price-quality knob (an
  oversized chunk sells every call at the limit and parks the rule until the pool is re-pegged; size it to no more
  than the measured depth between the deviation edge and the slippage limit -- audit T6-1); on the
  closed-market path it is still the safety knob -- one chunk an hour, and a banded launch never gets more than the
  default 2,000 USDG.
- **Per-listing gates and sell chunk** (`setListingGates(stock, dev, slip, sellChunkUsdg)`) -- was v2 item 8. The
  owner's, never the creator's. Loosening a gate needs a measured basis report
  ([OPERATIONS.md](./OPERATIONS.md#loosening-a-listings-gates)); the chunk is sized from measured depth
  ([OPERATIONS.md](./OPERATIONS.md#sizing-a-listings-sell-chunk)).
- **A vote-only owner on the treasury** (`setVoteDelegate`). The stock token has no vote surface today and is
  upgradeable by its issuer; a launched treasury is not, so the hatch had to be there at birth or never. It points
  votes and does nothing else: no asset, no allowance, no part of the rule. **Reserved, not live** -- nobody can vote
  tokenised stock on this chain today, and the token page must not suggest otherwise.
- **The creator's page, on the token** (`setMetadata`, `setEditor`, `lock`). Logo, description, five links and an
  `extraURI`, with pons' reader names and selectors so a tool written for a pons token reads ours unchanged. Written
  in the launch transaction (`launchWithMetadata`) or after it, by the launch-time creator (`deployer`, immutable) or its one editor, until the creator locks it for
  good. No protocol power over it, and it can reach no balance and no supply. Keyed to the launch-time creator and
  not the payout creator, because the owner's takeover moves fees and must not rewrite a page. It is on the token and
  not in a registry because a launched token is immutable, third-party tools read the token, and a v1 token born
  without it could never gain it (the standalone registry of PR #32 is superseded). The token's creation code moved
  to a `TokenDeployer` to make room.
- **One stock venue, V3.** The V4 *stock* venue (`StrategyTreasuryV4`, `listV4`) was deleted rather than finished: it
  shipped disabled, the first batch is all V3, and it was the weaker treasury (spot-only health, no closure trading).
  The strategy token's own pool is still Uniswap V4 on our hook. Cost: stocks whose depth is V4-only cannot list --
  COIN has no V3 liquidity, SPY is ~13x deeper on V4 -- until v2 item 11.

- **First batch: GME, CRCL, USAR, AMZN, META**, each with the rule [`rule-backtest/`](./rule-backtest/README.md) picked
  and `test/FirstBatchFork.t.sol` launches against the live chain. GME is listed on its 0.05% pool, not its deepest:
  the 1% pool sits a median 56 bps off Chainlink and would leave the treasury asleep half the day.
- **`bandCeiling`** per stock, 0 by default. First batch (decided 2026-09-21 from each pool's own 14 days, see
  [`DEPLOYMENT.md` §7.4](./DEPLOYMENT.md#74-every-stocks-bandceiling-ships-0)): CRCL 10 bps/h, USAR / GME / AMZN / META 5 -- just above what their
  closures needed (5.9, 3.8, 1.8, 2.4, 0.9); a bigger number buys no more trading hours, only a wider pin. Frozen at birth.
- **`HedgeFunTradeRouter`**: USDG in, strategy token out (and back), one transaction; the V3 hop is all-or-nothing and the V4
  key is read from the treasury. Without it only holders of the tokenised stock can buy -- and until the hook is on
  Uniswap's allowlist it is also the only one-click route.
- A token page that shows four numbers the contracts already expose -- stock held (`stockEquivalentHeld`), stock
  received (`totalStockReceived`), share of supply burned, the last buy-back -- and the line "no owner on the token (its page is its creator's, and says whether it is locked);
  the treasury's owner can only point its votes (reserved, not live); liquidity locked; the rule cannot change". The launcher's own first-buy share is shown too (audit R4-1).
- Before mainnet, unchanged from the audits: a hardware key on the Safe, one real Safe transaction, CI billing, a
  basis check (`tools/band_backtest.py`) on every pool that is listed. New with this release: the deployment
  rehearsal re-run on the final code (done 2026-09-21; DEPLOYMENT.md section 4 lists what it did not exercise), the hook's source
  verified on Blockscout, `setLauncher(launchRouter, true)` signed, and the hooklist / allowlist submission made
  only **after** the hook is deployed and bound.

## Historical research backlog

These are earlier research candidates, not the current release order or a commitment to implement all of them.
The former clone/factory-split prerequisites and one-release-only assumption are superseded by the append-only
V2 engine registry for compatible strategy kinds. A kind that requires a different venue or launch surface must
still establish whether it can reuse the current Factory and Hook. Bytecode headroom is measured on each exact
candidate; historical size estimates are not a release gate.

| # | item | what it is | why it is here and not in v1 |
|---|---|---|---|
| 1 | **Rule modules** | the treasury keeps the books, the execution gates and the guard rails; "sell now? how much? buy now? how much?" moves to a rule contract chosen at launch from a factory allowlist and never changed after | new shapes (below) without touching the factory again, and it is the natural way to do the split |
| 2 | **Blocks, not code** | the creator composes three blocks, each with floors: SELL (two steps as today, or an N-step ladder <= 6), BUY (x% of what is left as today, equal N, or martingale x m with m <= 3 and every rung summing to <= 100% of the reserve), STOP (none, or x%) | uploaded strategy code is unauditable by a buyer and is a rug in one line. Backtest: a ladder or a never-sold core does NOT beat choosing the right step width inside today's shape; martingale lifts the median on range-bound names (USAR 1.12 -> 1.18-1.22) and deepens the worst window on one with a squeeze in its past (GME 0.81 -> 0.67) -- an option, never the default |
| 3 | **A price table** | up to ~8 rows of "at launch price x k, buy/sell y%" -- absolute levels fixed at the launch-day Chainlink price, each level firing once until price re-crosses; **outside the table the relative rule takes over**, so a stock that leaves the range does not strand the treasury | a table of absolute prices frozen forever is a dead strategy the day the stock leaves it, and a table a creator may edit is a managed fund |
| 4 | **Separate buy and sell tax; a configurable spike** | `buyTaxBps` may differ from `sellTaxBps` (0 is allowed); spike height and length per launch, above a floor | the buy tax is taken in the TOKEN, so it can only be burned -- paying it to anyone is a standing seller. A spike of zero is an open door for the first block |
| 5 | **A payout ratio** | a frozen x% of each take-profit's PRINCIPAL joins the profit in the buy-back | today only profit buys the token back and principal cycles stock <-> USDG for ever. This is how a large treasury returns value by rule, with no withdrawal right for anyone |
| 6 | **Terminal redemption** | after N months with no trade, a one-time pro-rata claim on the treasury opens | a dead token should not strand its treasury. Standing redemption is rejected: circulating supply is manipulable inside a transaction, arbitrage drains the treasury the rule needs to hold, and it turns the product into a fund |
| 7 | ~~A per-call size cap on sells~~ | **shipped in v1** as `sellChunkUsdg`, with sales that fill partially | -- |
| 8 | ~~Per-listing gates~~ | **shipped in v1** as `setListingGates`, which also carries the listing's own sell chunk | -- |
| 9 | **Pool-priced treasuries** | for stocks with a pool and no Chainlink feed: the rule's price may move toward the pool's TWAP by at most r% per hour of wall clock, acts only within 3% of the pool, one action and a frozen size cap per window, no `stopLoss` | the friendliest stocks in the backtest are mostly these (COST, IBM, TTWO, RDDT, GLXY: 50-79% of rules beat 1.00 both ways, against a 4% median). Replayed on ten names a 1%/h limit costs the rule nothing measurable. It is weaker than a second price source and says so: list only where an outside market (Lighter perps) arbitrages the pool |
| 10 | **Other assets** | an oracle wrapper with the same interface that skips `oraclePaused()` and the calendar lets WETH (ETH/USD feed, a $17.8M 0.01% pool) list with NO treasury or factory change; a feedless memecoin needs item 9 and has no outside market at all | the rule likes volatile and range-bound, which is a fair description of ETH. No canonical wrapped BTC was found on this chain (every "BTC" paired with USDG is a lookalike) |
| 11 | **A V4 stock venue** | list a stock whose depth is on Uniswap V4 (COIN has no V3 liquidity at all; SPY is ~13x deeper on V4) | removed from v1 on 2026-09-21, not postponed by accident: a V4 pool keeps no observations, so the old V4 treasury had spot against Chainlink and nothing else, and no closure trading. Doing it properly needs a new treasury type with a real TWAP source (or an honest open-market-only one), a new factory, **and therefore a new hook address and a new allowlist review** |
| 12 | **A creator-set share of the sell tax straight to the buy-back** (`directBuybackBps`) | a frozen share of the stock-side tax skips the lot book and goes to `buybackStock`; the buy-back is then due only at a full chunk or after 24 h, so the sell spike is not re-armed constantly | decided and deferred 2026-09-21. In v1 only realised **profit** buys the token back, so a rule that never takes profit burns only through the buy tax -- nobody may say "the fee buys the coin back" of it. Attack notes for the design: the pot crossing a chunk is predictable; sub-`minLotUsdg` lots at high bps; `lastBuybackAt == 0` at birth |
| 13 | **Dividend buy-back** | spend what a dividend adds on the token | decided and deferred 2026-09-21. Dividends arrive as `uiMultiplier()` appreciation, not cash: shares held = raw balance x `uiMultiplier` / 1e18. Chainlink's price already includes the multiplier, so an ex-dividend day does not gap the rule. There is nothing to collect; the design question is how much of the appreciation counts as profit |
| 14 | **A "never sells, still buys back" template** | today a rule that never sells never buys back (the buy-back is fed only by take-profit), so "the vault only grows" and "the fee buys the coin back" cannot both be true of one token | it is items 5, 12 or 13 applied to a rule with an unreachable take-profit; the v1 "Diamond hands" template burns through the buy tax alone and its copy must say so |
| 15 | **Holders direct the treasury's votes** | the vote-only treasury owner (`setVoteDelegate`, v1) is the protocol Safe; the role is read live from the factory's owner, so it can become a contract in which a strategy's token holders choose the delegate | there is nothing to vote with on this chain today -- the stock token has no delegate surface -- so v1 only reserves the right; a governor is worth building the day the issuer opens one |

Rejected outright, in any version: withdrawal by an owner or a creator; standing redemption; creator-editable
parameters; a trailing take-profit (it needs an on-chain running high that only moves when someone calls, which is a
new thing to push around -- the same mistake the first buy-back anchor made).

## Order

1. Consolidate the current V2 release and its verified testnet launch/trading journey.
2. Design and audit the Covered Call kind with its real escrow/market adapter, then integrate launcher and keeper.
3. Admit further share assets, venues and income strategies with their own custody and settlement reviews.
4. Evaluate deployed volume and execution evidence before expanding the historical research backlog.
