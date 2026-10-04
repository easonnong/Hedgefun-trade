> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Robinhood Chain docs — local mirror

Retrieved 2026-09-20 from <https://docs.robinhood.com/chain>. These are mirrors, not
sources of truth — the contracts page in particular is generated live from the on-chain
asset registry. Re-scrape before trusting an address.

| File | Source | What it is |
|---|---|---|
| [building-with-stock-tokens.md](./building-with-stock-tokens.md) | `/chain/building-with-stock-tokens/` | ERC-20 + ERC-8056 integration, the `uiMultiplier()` model, the liquidity-venue map (RFQ / AMM / propAMM / Lighter / mint-burn), and the use-case table our product name comes from |
| [oracles-and-price-feeds.md](./oracles-and-price-feeds.md) | `/chain/oracles-and-price-feeds/` | Chainlink `AggregatorV3Interface` usage, total-return pricing, `oraclePaused()`, staleness and sequencer guidance |
| [contracts.md](./contracts.md) | `/chain/contracts/` | Every stock token and tokenized ETF address (196 tokens), plus WETH and USDG |

Each mirrored page ends with a **"Notes for this repo"** section that is *not* part of
the source document. That is where the doc's claims are reconciled against what we have
actually observed in production — the missing L2 sequencer feed, the `RH<TICKER> / USD`
feed naming, the 24/5 weekend hole, and the tickers with no push feed at all.

Parsed for machine use:

- `../../data/rh_stock_tokens.json` — symbol → address for all 194 stock tokens plus USDG and WETH. Tracked since PR #2;
  it agrees address-for-address with the table in `contracts.md`.

## Why these three pages

The product is **Price-aware contracts**, which is Robinhood's own name for the category
— it is one of the eight use cases listed in `building-with-stock-tokens.md`:

> **Price-aware contracts** — logic that reacts to equity prices. A contract that
> executes when a stock token crosses a threshold — onchain conditional logic.

The three pages are the complete integration surface for that: what the token is
(contracts), how it is priced (oracles), and what you may do with it (building with).
The pool-selection work that builds on them is in
[`../../POOL_SELECTION.md`](../../POOL_SELECTION.md).
