> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Where to put the first tranche — delta-neutral LP line

> **Scope.** This ranks pools for a **delta-neutral LP hedged with a Lighter perp** — the
> `rh` keeper product — where the binding gate is whether the ticker can be hedged at all.
> It is *not* the gating analysis for the strategy-token launchpad in PR #2, which has no
> hedge and is gated by Chainlink oracle coverage instead: see
> [`LISTING_CANDIDATES.md`](./LISTING_CANDIDATES.md). Both share the pool census in
> `data/v3_pool_census.json`.

Measured 2026-09-20 against Robinhood Chain mainnet. Sample window is the last full
trading week, **Mon 2026-09-14 13:30 UTC → Fri 2026-09-18 20:00 UTC**, blocks
62,844,531 → 66,493,888.

Everything below comes from `eth_call` against the chain and read-only GETs against
Lighter's public market API. Nothing was signed. Reproduce with the four scripts in
`tools/`; raw outputs are in `data/`.

---

## The answer first

For a first tranche of **$5,000**, in order:

| # | Pool | Fee tier | Band you actually get | Share of in-range liquidity | fees ÷ LVR | Capacity before we own 15% |
|---|---|---|---|---|---|---|
| 1 | **META/USDG** | 0.30% | ±1.50% | 6.5% | **3.5×** | $12,800 |
| 2 | **MSFT/USDG** | 0.30% | ±1.50% | 2.2% | **2.9×** | $39,700 |
| 3 | **AAPL/USDG** | 0.05% | ±1.05% | 1.0% | **3.0×** | $88,500 |
| 4 | TSLA/USDG | 0.30% | ±1.50% | 2.5% | 1.8× | $34,100 |
| 5 | AMZN/USDG | 0.30% | ±1.20% | 1.6% | 2.0× | $52,900 |
| — | PLTR/USDG | 0.30% | ±1.20% | 9.4% | 1.8× | $8,500 |
| — | SPY/USDG | 0.05% | ±1.05% | 1.8% | 2.1× | $48,300 |

**Start with META/USDG 0.30%** (`0x107a7cb40d8665360ba10e59471af06150a50922`). It has the
best margin over adverse selection of any pool we can actually hedge (3.5×), a 6.5%
liquidity share at $5k — large enough that fees are not noise, small enough that we are
not quoting to ourselves — a Lighter META perp (market 13) with $678k/day of volume, a
Lighter META spot book as an alternative unwind path, and a pool-vs-mark basis of 0.00%
at the time of measurement.

**Then MSFT and AAPL, as the two controls.** MSFT is the same shape as META at half the
volatility (17% vs 29% annualised) and 3× the capacity. AAPL is the opposite test: a
0.05% pool with 40× more flow ($33.4M/week) but 6× less share per dollar. Running all
three at once separates "does the edge come from the fee tier or from the flow" in one
week instead of three.

Do **not** start with NVDA, and do not start at $100.

---

## How the decision was made

### The comparison that actually decides it

For a delta-hedged concentrated LP, both sides of the P&L are proportional to the
liquidity `L` you mint:

```
fee income over a window   =  feesPerL × L
adverse selection (LVR)    =  ¼ · √P · RV × L
```

`L` cancels. Whether a pool makes money does not depend on how much we deploy — capital
size only sets the liquidity share, whether the hedge can be sized at all, and how badly
the exit moves the price. So the ranking metric is the scale-free ratio:

```
fees ÷ LVR  =  (feesPerL × fraction of time in range) ÷ (¼ · √P · RV)
```

`feesPerL` comes from the change in `feeGrowthGlobal0/1X128` across the window.
`RV` is the realised variance of the pool's own tick path — 60 archive samples per pool
across the five sessions. The pool tick, not the oracle, because the pool tick is what
the position is actually exposed to.

A ratio of 1.0 means fees exactly pay for adverse selection and the strategy earns
nothing for the risk. Everything on the shortlist is ≥ 1.8×; everything below 1.5× was
cut.

### The gates, in the order they eliminated things

1. **Hedgeable.** There must be a Lighter perp for the ticker. This is the harshest
   filter by far and it kills the entire top of the raw fee ranking: GLXY (3033% raw fee
   APR), BA, RBLX, FIG, MRNA, F, WETH, MSTR, DELL, GME, HIMS, LULU, IBM, DJT, RDDT,
   NFLX, LLY, COST — no perp, no delta-neutral position, however good the pool looks.
   This independently reproduces what the repo already learned the expensive way: the
   GME line was closed on 2026-09-07 rather than migrated off Hyperliquid, precisely
   because Lighter's Robinhood Chain instance lists no GME perp
   (`rh/config/addresses.json`, `rh/docs/MEME_TREASURY.md:19`). Note that GME, MSTR and
   others *do* trade on Lighter's main zkLighter exchange — a different venue with
   different collateral, not a substitute.
2. **Alive.** Pool volume ≥ $250k/week. Below that there is no flow to earn from, and
   the fee ÷ LVR ratio stops meaning anything because the variance sample sees no moves
   (TSM 1% reported a ratio of 162 on $59k of weekly volume — that is a dead pool, not an
   opportunity).
3. **Not the pool ourselves.** Share capped at 15% of in-range liquidity. Past that our
   own fee estimate stops being a measurement of somebody else's flow, and the exit moves
   the price we exit at. This is what caps META at $12.8k and PLTR at $8.5k.
4. **Hedgeable at size.** Lighter's minimum is $10 notional and a per-market minimum base
   size ($5–13 for the shortlist). Fine at $5k; at $500 one minimum order is a large
   fraction of the whole delta range and the hedge cannot track inventory.
5. **Edge.** fees ÷ LVR ≥ 1.5, because realised gamma is *worse* than the
   continuously-hedged LVR limit — the keeper hedges on a 60s poll against a minimum
   order size, not continuously.

Full rejection list with reasons: `python3 tools/shortlist.py`.

---

## Three findings that change the plan

### 1. The window is closing, fast

Pool liquidity measured now against 2026-09-03, the day of the live 14-hour run:

| Pool | in-range L on 2026-09-03 | now | growth in 17 days |
|---|---|---|---|
| AMC 0.30% | 1.23e21 | 1.07e22 | **8.7×** |
| NVDA 0.05% | 4.61e21 | 2.97e22 | **6.4×** |
| AAPL 0.05% | 5.72e20 | 2.62e21 | **4.6×** |
| HIMS 0.30% | 3.61e21 | 8.91e21 | 2.5× |
| GOOGL 0.05% | 7.20e20 | 1.68e21 | 2.3× |
| AMD 0.30% | 4.85e19 | 1.06e20 | 2.2× |
| TSLA 0.30% | 3.36e20 | 6.78e20 | 2.0× |

Fee share per dollar is inversely proportional to this. The same $100 in NVDA/USDG now
buys **0.002%** of in-range liquidity where `CLAUDE.md` recorded 0.2% on 2026-09-03 —
liquidity growth accounts for 6.4× of that gap and the rest is band and measurement
definition, but the direction is unambiguous and it is the whole story. Modelled fee
income for $100 in NVDA 0.05% is now $0.16/14h against the **$1.38/14h actually
measured** on 2026-09-03.

The deep pools are being commoditised. The decision this forces: **size up now or accept
a decaying edge.** A $100 pilot in a pool this deep is no longer a measurement of
anything — it is below the noise floor of its own hedge.

### 2. Lighter removes the cost Hyperliquid imposed

From `api.rh.lighter.xyz/api/v1/orderBookDetails`, 57 active perp markets, 27 spot books:

- **Maker and taker fees are 0.0000 on every market.** On Hyperliquid, exchange fees were
  $1.00 against $76 of LP fee income. That line goes to zero. The sweep result in
  `CLAUDE.md` — that rebalancing frequency is inert because 87% of hedging loss is gamma
  and only 1.3% was exchange fees — becomes *more* true, not less.
- **Minimum $10 notional per order**, confirmed on the venue itself (`min_quote_amount`
  = 10.000000 on all 57 markets). Same constraint that made `--band 0.02` inert.
- **Leverage is inferred, not confirmed.** `min_initial_margin_fraction` reads 500 on the
  shortlist tickers and `default_initial_margin_fraction` 5000 on every market, which
  gives 20× and 2× *if* the denominator is 10,000. Lighter's API reference documents
  these only as `uint16` with no units. The one piece of hard evidence we have is
  operational, not inferred: `update_leverage(NVDA, cross, 5x)` was tested against the
  live venue on 2026-09-05 and accepted (`rh/docs/MEME_TREASURY.md:136`), so NVDA at
  least supports cross margin. Set leverage deliberately before the first hedge — the
  Hyperliquid lesson in `CLAUDE.md` about leverage-set-after-open applies to any venue
  with a margin fraction.
- **Margin mode is unknown per market.** `market_config.market_margin_mode` reads 0 on
  all 57 markets with no documented mapping, so the API cannot tell us which markets are
  isolated-only the way several Hyperliquid `xyz` markets were. Given what that
  assumption cost on Hyperliquid (`CLAUDE.md`, 2026-09-04), verify on the venue before
  sizing, do not infer from the field.
- **No open-interest cap is published.** `orderBookDetails` returns a running
  `open_interest` but no ceiling — there is no Lighter equivalent of Hyperliquid's
  `assetToStreamingOiCap` to check headroom against.
- Lighter's mark prices agree with the pool prices I derived independently to within
  0.02–0.21% across the shortlist. That is a full cross-validation of the price pipeline
  (`sqrtPriceX96` → decimals → USDG), and it is also the live pool-vs-venue gate.

### 3. Most of the chain is not investable

317 `<stock>/USDG` V3 pools exist across the four fee tiers. **154 carry any active
liquidity at all**; the other 163 were created and initialised at `MAX_SQRT_RATIO` and
hold nothing. Total live TVL across all 154 is **$75.2M**, and it is concentrated: WETH
1% alone is $24.1M, the top ten pools are ~70% of it.

Of the 154, after the hedgeability gate and the volume gate, **nine pool/fee-tier
combinations survive**. The chain looks broad and is narrow.

---

## What would change this answer

- **It is one week, and one that did not crash.** `CLAUDE.md` records that sweeping a
  parameter over a single directional window measures the direction. The same applies
  here: rank stability needs a second window, ideally a down one.
- **`feesPerL` assumes the position was in range the whole time.** It is corrected by the
  measured in-range fraction (90–100% on the shortlist, from the same tick path), but the
  correction is coarse — when out of range you earn nothing *and* hold a one-sided
  position the hedge has to carry.
- **LVR is the continuously-hedged floor.** Real gamma cost is higher. A ratio of 1.8×
  is not an 80% margin of safety; treat 1.5× as break-even-ish and 3× as thin.
- **RV is sampled 60× across five sessions**, so it sees session-level moves and misses
  intraday noise — it understates RV, which flatters every ratio. Uniformly, so the
  ordering survives, but the levels do not.
- **The fee-growth method was validated against raw `Swap` logs** on three pools over the
  same 10,000 blocks: implied volume came in at 0.70–0.80× of log volume, the gap being
  liquidity moving within the window. Ranking-grade, not accounting-grade.
- Triple-digit modelled APRs look wrong and are not obviously wrong: the 2026-09-03 live
  run realised +$0.64 net on $100 in 14 hours, which annualises to the same regime. Both
  numbers should be distrusted equally.

## Oracle coverage — confirmed on-chain

Every shortlist ticker has a live Chainlink push feed, read directly from the chain
rather than from the docs (whose tables render client-side and are not machine-readable).
Prices agree three ways — feed, pool and Lighter mark — to within 0.6%:

| Ticker | Feed proxy | `description()` | Feed ÷ USDG | Pool | Lighter mark |
|---|---|---|---|---|---|
| META | `0x7C38C00C30BEe9378381E7B6135d7283356D71b1` | `Robinhood META / USD` | 666.77 | +0.58% | +0.59% |
| MSFT | `0x45C3C877C15E6BA2EBB19eA114Ea508d14C1Af2E` | `RHMSFT / USD` | 495.83 | −0.28% | −0.34% |
| AAPL | `0x6B22A786bAa607d76728168703a39Ea9C99f2cD0` | `Robinhood AAPL / USD` | 335.38 | −0.27% | −0.29% |
| TSLA | `0x4A1166a659A55625345e9515b32adECea5547C38` | `RHTSLA / USD` | 363.80 | +0.00% | +0.20% |
| AMZN | `0xD5a1508ceD74c084eBf3cBe853e2C968fB2a651C` | `Robinhood AMZN / USD` | 253.86 | −0.33% | −0.23% |
| PLTR | `0x820ABedFF239034956B7A9d2F0a331f9F075eB4c` | `Robinhood PLTR / USD` | 177.60 | −0.06% | −0.14% |
| SPY | `0x319724394D3A0e3669269846abE664Cd621f9f6A` | `RHSPY / USD` | 761.56 | +0.25% | +0.09% |
| SGOV | `0xa0DF4ee0fFf975306345875E3548Fcc519577A11` | `Robinhood SGOV-USD` | 101.11 | −0.12% | −0.64% |

`USDG / USD` = `0x61B7e5650328764B076A108EFF5fa7282a1B9aD2`, reading 0.999991.

**The feed `description()` string is not uniformly formatted, and `CLAUDE.md` is only
half right about it.** NVDA, MSFT, TSLA and SPY return the `RH<TICKER> / USD` form;
META, AAPL, AMZN, PLTR return `Robinhood <TICKER> / USD`; DELL, SGOV and USAR return a
hyphenated `Robinhood <TICKER>-USD`. Any code that resolves a feed by matching the
description string will silently fail on roughly half the tickers. **Resolve feeds by
address, never by name.**

Also worth recording: at the time of measurement every equity feed was **43–55 hours
stale**, because it was Sunday evening and the feeds are 24/5. That is the weekend hole
working as designed, and it means a keeper started outside market hours fails closed on
the staleness gate before it does anything else.

No L2 Sequencer Uptime Feed is published for this chain. The Robinhood docs carry a
"Checking sequencer uptime (recommended on L2)" section, but it is generic Chainlink
boilerplate with no address for this chain — it recommends checking a feed it never
names. `updatedAt` remains the only staleness guard.

## Two things to settle before funding

- **The keeper must run from AWS ap-northeast-1.** Lighter's order and account endpoints
  are geo-fenced by request IP and answer error 20558 ("restricted jurisdiction")
  otherwise; read endpoints work from anywhere, which is why all the measurement above
  was possible from a laptop and none of the trading would be
  (`rh/docs/MEME_TREASURY.md:136`).
- **AMC is already the de facto next line, and nothing written justifies it.** The repo
  shows AMC deployed 2026-09-07 (`config/addresses.json` `meme_treasury.lines.AMC`,
  market 56, 6% maintenance, min 3 shares, Safe batch pending signature) with no recorded
  comparison against alternatives. On this week's data AMC 0.30% scores fee ÷ LVR of
  **1.32** — below the 1.5 cut — on 44% annualised volatility, and it has no Chainlink
  push feed, so it prices off `TwapFeed.sol` over its own pool. It is the weakest kind of
  candidate on both axes this analysis measures. That may still be the right call for
  reasons outside this analysis, but it should be an argued decision rather than an
  inherited one.

## Scope limits

- **Uniswap V3 only.** Other AMMs on this chain also run `<stock>/USDG` pools — alandale-v3
  (SPY-USDG, USAR-USDG) and ekubo (SPY-USDG, STONX-USDG) among them. They were not
  scanned, so this is a ranking within Uniswap V3, not across the chain.
- **Uniswap V4 was not scanned and should not be dismissed.** DefiLlama puts Uniswap V4
  on this chain at **$185.6M TVL against V3's $68.6M** — V4 is nearly 3× larger in
  aggregate. What `CLAUDE.md` records is narrower and still true: the specific hookless
  V4 1% AMC/USDG pool holds nothing, and V4 has no observation ring so a V4 line needs
  `V4TwapFeed.sol` sampling or a hook oracle. Where the V4 TVL actually sits on this
  chain is an open question worth its own scan.
- **A TVL discrepancy I could not resolve.** My census totals **$75.2M** across 154 live
  `<stock|WETH>/USDG` V3 pools, measured as raw token balances. DefiLlama reports
  Uniswap V3's entire chain TVL at **$68.6M**. Mine should be a subset of theirs and is
  larger. One of the two is wrong; the ranking uses per-pool liquidity rather than these
  totals, so it does not depend on the answer, but do not quote either figure as
  authoritative until it is chased down.
- **`collector.py`'s watchlist does not cover the AAPL 0.05% pool.** The production
  watchlist tracks AAPL at 0.30% (`0x783c9bbb…`); the pool on this shortlist is the
  0.05% one (`0xaae0d815…`), which carries 200× the weekly volume. If AAPL is funded,
  the watchlist needs the pool added or the collector will not be recording it.
- **Anything that moves money.** No transaction was prepared or signed.

---

## Reproducing

```bash
python3 tools/scan_v3_pools.py    # 317 pools -> data/v3_pool_census.json
python3 tools/sample_fees.py      # feeGrowth at both window ends (cached, resumable)
python3 tools/sample_vol.py       # 60 tick samples/pool -> realised variance
python3 tools/rank_pools.py       # join -> data/pool_ranking.json
TRANCHE=5000 python3 tools/shortlist.py
python3 tools/verify_feeds.py META MSFT AAPL   # run this before funding anything
```

Infrastructure constants, all verified live:

| | |
|---|---|
| Chain id | 4663 (`0x1237`), ~0.1005 s/block |
| Uniswap V3 factory | `0x1f7d7550b1b028f7571e69a784071f0205fd2efa` |
| USDG | `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168` — **6 decimals**, stock tokens are 18 |
| State RPC | `https://robinhood-rpc.publicnode.com` |
| Archive RPC | `https://rpc-robinhood.blockmachine.io` — the only one serving historical state; `eth_getLogs` capped at 10,000 blocks inclusive |
| Lighter API | `https://api.rh.lighter.xyz` (read-only endpoints used: `/api/v1/orderBooks`, `/api/v1/orderBookDetails`) |

Token address map: `data/rh_stock_tokens.json` (194 stock tokens plus USDG and WETH), which matches the mirrored
[Token Contracts](docs/robinhood-chain/contracts.md) page.
