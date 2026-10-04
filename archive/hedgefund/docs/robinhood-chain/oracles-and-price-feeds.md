> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Oracles & Price Feeds

> Mirror of <https://docs.robinhood.com/chain/oracles-and-price-feeds/> — retrieved 2026-09-20.

Robinhood Chain uses [Chainlink](https://chain.link/) for onchain price data. Both crypto assets and Stock Tokens have Chainlink price feeds, so your contracts can read reliable prices directly onchain — including live prices for tokenized equities and ETFs.

## Reading a price feed

Chainlink price feeds implement the standard `AggregatorV3Interface`. Read the latest price with `latestRoundData()`, accessed through the feed's proxy address:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

interface AggregatorV3Interface {
   function latestRoundData()
       external
       view
       returns (
           uint80 roundId,
           int256 answer,
           uint256 startedAt,
           uint256 updatedAt,
           uint80 answeredInRound
       );
   function decimals() external view returns (uint8);
}

contract PriceConsumer {
   AggregatorV3Interface internal priceFeed;

   constructor(address feedProxy) {
       priceFeed = AggregatorV3Interface(feedProxy);
   }

   function getLatestPrice() public view returns (int256) {
       (, int256 answer, , uint256 updatedAt, ) = priceFeed.latestRoundData();
       require(answer > 0, "Invalid price");
       require(updatedAt > 0, "Round not complete");
       return answer;
   }
}
```

Decimals: prices are returned as integers — call `decimals()` to scale. Most USD feeds use 8 decimals (e.g. 30000000000 at 8 decimals = $300.00).

## Stock Token price feeds

Each Stock Token on Robinhood Chain has its own Chainlink price feed. These feeds use the same `AggregatorV3Interface` and `latestRoundData()` as crypto feeds — reading a stock price is identical to reading any other Chainlink feed. Point the consumer above at the stock's feed proxy.

The feed returns the price of one token, which is the underlying share price times the multiplier. `latestRoundData()` returns this directly, so you don't apply the multiplier yourself. The multiplier accounts for corporate actions (dividends, splits) and is also readable onchain via the token's `uiMultiplier()`.

The token price diverges from the underlying share price over time. Because dividends are reinvested into the token via the multiplier, a stock token tracks the total return of the underlying — price changes plus reinvested dividends — not just the share price. As dividends accrue, the multiplier rises and one token comes to represent more than one share, so the feed price drifts above the headline share price. This is expected.

Example: a token tracking a $100 stock starts at a multiplier of 1.0 (1 token = 1 share, feed price $100). After a dividend is reinvested, the multiplier rises to ~1.05 — one token now represents 1.05 shares. If the share price is still $100, the feed price is $105 (1.05 × $100). `latestRoundData()` always returns this full, multiplier-adjusted value.

Stock feeds update 24/5, following market hours.

### Displaying balances and prices

The feed returns the price of a single token. `uiMultiplier()` is the shares-per-token ratio, returned as an integer scaled by 1e18. Always divide by 1e18 after applying it (as shown below), otherwise the result is off by a factor of 1e18. Depending on what you want to show users:

- Token value (default): use the feed price directly.
- Underlying share price: `feedPrice * 1e18 / uiMultiplier()`
- Share-equivalent units: `balance * uiMultiplier() / 1e18`

The economic value is identical in every case — only the presentation differs.

See [Building with Stock Tokens](https://docs.robinhood.com/chain/building-with-stock-tokens) ([local mirror](./building-with-stock-tokens.md)) for end-to-end examples.

## Available feeds

Feed proxy addresses, decimals, and heartbeats are maintained by Chainlink. See the [Robinhood price feeds page](https://docs.chain.link/data-feeds/price-feeds/addresses?network=robinhood) for the current list — it's the source of truth, so always read addresses and parameters from there rather than hardcoding them.

## Checking sequencer uptime (recommended on L2)

Because Robinhood Chain is a Layer-2, verify the sequencer is up before trusting a price — during a sequencer outage, feeds can go stale. Chainlink provides an L2 Sequencer Uptime Feed for this; check it before reading any price:

```solidity
(, int256 sequencerStatus, uint256 startedAt, , ) = sequencerUptimeFeed.latestRoundData();
require(sequencerStatus == 0, "Sequencer down");            // 0 = up
require(block.timestamp - startedAt > GRACE_PERIOD, "Grace period not over");
```

## Oracle Pauses During Corporate Actions

While a corporate action is being processed, the price oracle for the affected token is **paused** — feeds are expected to stop publishing fresh prices while the token's terms or multiplier are being updated — and **unpaused** once processing completes. You can read this state on-chain via `oraclePaused()` on the token.

Integrators reading prices on-chain should treat a paused oracle as "price temporarily unavailable" for that token, rather than as a zero or stale price. The flag is advisory and not enforced on-chain, so a paused oracle may still return a value — keep your staleness check (`updatedAt` vs. heartbeat) as the primary guard rather than relying on the flag alone. These pause windows align with the trading pauses around corporate actions.

## Best practices

- Check staleness — compare `updatedAt` against the feed's heartbeat; reject stale prices.
- Validate the answer — reject zero or negative values.
- Read `decimals()` — never hard-code.
- Check sequencer uptime — see above.
- Account for the multiplier on corp actions — the feed quotes per-token price; read `uiMultiplier()` (and pending `newUIMultiplier()` / `effectiveAt()`) consistently before converting to share terms.
- Check the oracle pause flag — read `oraclePaused()`; treat `true` as "do not trust the price," but keep your staleness check as the primary guard since the flag is advisory and not enforced on-chain.

## Further reading

- [Chainlink Data Feeds](https://docs.chain.link/data-feeds)
- [Chainlink L2 Sequencer Uptime Feeds](https://docs.chain.link/data-feeds/l2-sequencer-feeds)
- [Robinhood Price Feeds](https://docs.chain.link/data-feeds/tokenized-equity-feeds/robinhood)
- [Building with Stock Tokens](https://docs.robinhood.com/chain/building-with-stock-tokens)

---

## Notes for this repo (not part of the source doc)

Three places where the doc and our production experience diverge. Ours is the operational truth; the doc is the spec.

1. **"Check sequencer uptime" is not actionable here.** The doc recommends the L2 Sequencer Uptime Feed, but no such feed is published for Robinhood Chain (`CLAUDE.md`, confirmed by probing). `updatedAt` is the only staleness guard we have, which makes the 24/5 gap below harder, not easier.
2. **Feed naming is inconsistent — resolving a feed by name is a bug waiting to happen.** `CLAUDE.md` records that equity feeds are named `RHNVDA / USD` rather than `NVDA / USD`. That is true for some tickers and not others. Read on-chain from `description()` on 2026-09-20: `RH<TICKER> / USD` for NVDA, MSFT, TSLA, SPY; `Robinhood <TICKER> / USD` for META, AAPL, AMZN, PLTR, GOOGL, AMD and most others; `Robinhood <TICKER>-USD` for DELL, SGOV, USAR. **Resolve feeds by address, never by description string** — a name match silently fails on roughly half the tickers. Separately, the doc's "the answer already includes the multiplier" is the trap `CLAUDE.md` records: multiplying by `uiMultiplier()` again double-counts every corporate action. Check any ticker with `tools/verify_feeds.py`.
3. **"24/5" is the whole weekend problem.** Overnight the feeds update rarely; across a weekend they stop entirely and `latestRoundData()` keeps returning the last value. Age alone cannot distinguish a scheduled close from an outage, so the keeper's closed-market handling is an explicit bounded heuristic, not something the doc sanctions.
4. **Not every stock has a push feed** — but `SGOV` does, contrary to one clause in `CLAUDE.md`'s list. Verified on-chain: `Robinhood SGOV-USD` at `0xa0DF4ee0fFf975306345875E3548Fcc519577A11` answers normally. AMC and HIMS genuinely have none. The rest of the clause stands: tickers without a push feed are Data-Streams-only, and Data Streams equity reports are a sales-gated entitlement (401 until enabled). Those tickers fall back to a sampled V3 TWAP (`TwapFeed.sol`), which is a materially weaker oracle — see the manipulation analysis in `CLAUDE.md`. **Push-feed coverage is therefore a hard gate on pool selection**, not a nice-to-have.
