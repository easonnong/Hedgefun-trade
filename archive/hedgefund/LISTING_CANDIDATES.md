> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Which stocks the launchpad can list — measured

For the strategy-token launchpad (PR #2, merged to `main` 2026-09-20 as `3e40069`;
`forge test` on merged main: 236 passed, 0 failed). Measured 2026-09-20 against Robinhood
Chain mainnet and Chainlink's own feed directory. All read-only `eth_call`; nothing signed.

Reproduce: `python3 tools/listability.py` → `data/listability.json`.

---

## The answer

**194 registry tokens → 35 have a Chainlink push feed → 25 are listable on V3 today.**

The binding gate is the oracle, and it is not close. `PriceOracle`'s constructor needs a
Chainlink stock feed; `HedgeFunFactory.list` needs an oracle bound to the stock and a
`<stock>/USDG` **V3** pool. **There is no V4 stock venue**: it shipped switched off and
was removed on 2026-09-21, because a V4 pool keeps no observations, so its stock leg had
spot against Chainlink and nothing else and could not trade through a closure. (A
strategy token's own pool is V4; that is a different pool.) So this table is the whole
v1 universe. **82% of the token registry can never be listed** as the contracts are written,
because Chainlink does not publish a feed for it.

That number is not a stale snapshot. Chainlink's own directory
(`reference-data-directory.vercel.app/feeds-robinhood-mainnet.json`) returns 57 entries
of which 35 are equities, matching `rh/data/chainlink_rh_feeds.json` entry for entry. The
"95 tokenized equities have Chainlink feeds" figure that circulates in launch coverage is
not what the directory publishes.

### First wave — decided 2026-09-20: deep pools only

**NVDA, AAPL, GOOGL, and SPCX if a pre-IPO proxy is wanted.** This is where the listability
table below meets the security review ([`AUDIT.md`](./AUDIT.md), PR #4), which adds two
filters the chain data alone does not:

> **SUPERSEDED, 2026-09-21.** The first batch is no longer what this file argued for. It picked **NVDA, AAPL,
> GOOGL and optionally SPCX** on the strength of the "+30% walk" depth table, and that table is wrong by 8-25x (see
> the CORRECTION below): no listed pool is deep enough for depth to be the defence, so depth cannot be the filter.
> **The first batch, decided by the owner 2026-09-21, is nine: NVDA, SPCX, CRCL, GOOGL, AMZN, GME, META, USAR,
> MSTR** --
> the four deepest books with frequent feeds, plus the meme names the product exists for. **Updated 2026-09-22:**
> the owner approved adding **AMD, MU and INTC**, making twelve planned stocks; **NVDA + AMD + MU + INTC** is the
> semiconductor group. This changes the planned roster, not the on-chain listings. AAPL is not in it. The
> single authoritative version of the list, with each stock's `setBandCeiling` and the reason it is in, is
> [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) 7.2. This file is kept for the measurements and the TR-4 feed-cadence
> work, which still stand.

> **CORRECTION, 2026-09-21 (external audit round 1, F-03).** The +30% figures below are **overstated by 8-25x**. They
> assume the active tick's liquidity extends across the whole move; it does not, and every figure exceeds its pool's
> ENTIRE TVL in `data/listability.json` (NVDA $6.2M against "$54M"). A walk up can never cost more than 1.3x the stock
> the pool holds. The audit's exact tick-walk: NVDA ~$2.33M, SPCX ~$0.76M, GOOGL ~$0.47M, AAPL ~$0.24M, SPY ~$0.20M.
> The ORDER of the pools survives and the figures are kept as the record of what was decided on; do not size anything
> from them. What bounds a pin's take is the band and the pace (docs/DEPLOYMENT.md 7.4), and no band is set above 10.

- **TR-1 — the closed-market path can be pinned on a thin pool.** After a real weekend gap
  an attacker who can hold the pool for 600 seconds chooses the price the rule trades at:
  +3,311 USDG on an AMD-sized pool for ~$218k round-tripped. Cost to walk each pool +30%:
  NVDA ~$54M, SPCX ~$13M, AAPL ~$5.9M, GOOGL ~$3.9M — against META ~$595k, AMD ~$309k,
  INTC ~$139k. Anything under ~$500k is out until that path is narrowed.
- **TR-4 — a quiet feed parks the rule.** Chainlink updates on a 0.5% move only, and SPY
  went 15 hours into a Monday without one. A legitimate 0.6% pool move against a feed
  that old closes `health()` until the next print. QQQ, SPY, SGOV and USO are deep enough
  but will spend hours a day doing nothing.

| | deep enough (TR-1) | feed ticks often (TR-4) | |
|---|---|---|---|
| **NVDA** | ✔ $54M | ✔ | **first** |
| **AAPL** | ✔ $5.9M | ✔ | **first** |
| **GOOGL** | ✔ $3.9M | ✔ | **first** |
| SPCX | ✔ $13M | ✔ | first, optional |
| QQQ, SPY, SGOV, USO | ✔ | ✘ | later — expect downtime |
| AMZN | borderline $3.1M | ✔ | after TR-1 is fixed |
| MSFT, TSLA, MU, META, AMD, PLTR, INTC … | ✘ | ✔ | not until TR-1 is fixed |

**What "deep pools only" does not buy: permanence.** Depth is a property of today. A
listing is forever for every strategy launched against it, and liquidity leaves as easily
as it arrives — the same measurement that shows these pools 2–9× deeper than on
2026-09-03 shows how fast the number moves. If NVDA's pool thins to AMD's size a year
from now, every NVDA strategy launched this month inherits TR-1 with no way to patch it.
Listing deep pools is the right call for the first wave; it is a reason to take the time
to narrow the closed-market path, not a substitute for doing so. Re-run
`tools/listability.py` and the depth table before each new listing, and treat the code
fix as owed.

### Listable on V3 today

Observation ring is **not** a constraint — every candidate is between 1,400 and 6,000
slots against the 660 `PoolTrader` requires (`TWAP_WINDOW + 60`), so
`ShortObservationRing` will not fire on any of these. The figures agree with the
independent measurement recorded in `PoolTrader.sol`'s constructor comment (NVDA 6000,
SPCX 3100, MU and GME 1860, most others 1801).

| ticker | best V3 `<stock>/USDG` | fee | TVL | obs ring | feed `description()` |
|---|---|---|---|---|---|
| NVDA | `0xd4eb2120…` | 0.05% | $6,195,860 | 6000 | `Robinhood NVDA / USD` |
| SGOV | `0xfab52005…` | 0.30% | $3,765,818 | 1800 | `Robinhood SGOV-USD` |
| SPCX | `0xc61284332…` | 0.05% | $2,561,917 | 3100 | `Robinhood SPCX / USD` |
| USO | | 0.30% | $1,839,732 | 1801 | `Robinhood USO / USD` |
| CRCL | | 0.30% | $1,705,849 | 1801 | `Robinhood CRCL / USD` |
| QQQ | | 0.05% | $1,466,041 | 1800 | `Robinhood QQQ / USD` |
| GOOGL | `0x34d0dc12…` | 0.05% | $1,270,957 | 1801 | `Robinhood GOOGL / USD` |
| MU | | 0.30% | $1,032,001 | 1860 | `Robinhood MU / USD` |
| GME | | 1.00% | $975,832 | 1860 | `Robinhood GME / USD` |
| AMZN | `0x8ac92da7…` | 0.30% | $971,152 | 1801 | `Robinhood AMZN / USD` |
| MSFT | `0xeb60bcd1…` | 0.30% | $765,522 | 1801 | `RHMSFT / USD` |
| TSLA | `0xf4acdaee…` | 0.30% | $760,451 | 1801 | `RHTSLA / USD` |
| AAPL | `0xaae0d815…` | 0.05% | $592,837 | 1801 | `Robinhood AAPL / USD` |
| MSTR | | 1.00% | $475,347 | 1500 | `Robinhood MSTR / USD` |
| SLV | | 0.30% | $437,264 | 1801 | `Robinhood SLV / USD` |
| SPY | `0xa7bb1ac6…` | 0.05% | $433,513 | 1801 | `RHSPY / USD` |
| AMD | `0x48d284a2…` | 0.30% | $264,451 | 1400 | `Robinhood AMD / USD` |
| DELL | | 1.00% | $263,132 | 1500 | `Robinhood DELL-USD` |
| INTC | | 0.30% | $219,552 | 1500 | `Robinhood INTC / USD` |
| META | `0x107a7cb4…` | 0.30% | $218,608 | 1400 | `Robinhood META / USD` |
| BABA | | 0.30% | $157,057 | 1800 | `Robinhood BABA / USD` |
| PLTR | `0x85168041…` | 0.30% | $145,281 | 1801 | `Robinhood PLTR / USD` |
| TSM | | 1.00% | $115,110 | 1801 | `Robinhood TSM / USD` |
| USAR | | 0.30% | $80,318 | 1400 | `Robinhood USAR-USD` |
| SNDK | | 1.00% | $66,621 | 1400 | `Robinhood SNDK / USD` |

Full rows, including fee tier and both cardinality values, in `data/listability.json`.

**Feed-description correction, 2026-09-22:** the historical table above and naming examples below retain the
earlier labels. An address-based read at block 69,466,392 returned `RHNVDA / USD`, `RHAMD / USD`, `RHMU / USD`
and `RHINTC / USD`, while the directory names use `Robinhood <ticker> / USD`. Use the verified proxy addresses
and current descriptions in [the deployment guide](./docs/DEPLOYMENT.md#71-a-priceoracle-per-stock), not a name match.

### Has a feed but is not V3-listable

| ticker | why |
|---|---|
| ASML | pool holds $33k — a lot would move it |
| IONQ, RKLB | observation ring 1 and 64 slots, and the pools hold $2 and $1 |
| COIN, ORCL, CRWV, CLSK, NBIS, RGTI, EWY | **no live `<stock>/USDG` V3 pool at any fee tier** |

Those last seven are exactly the case a V4 stock venue existed for (PR #2's survey
records `COIN` as V3-empty/V4-only), and they are **out of v1 by design** now that the
venue has been removed. It is a v2 item (`docs/ROADMAP.md`, item 11: a new treasury type, a
new factory and therefore a new hook address); when it is on the table, a scan for
hookless `<stock>/USDG` V4 pools is the missing half of this document — `ORCL` and `COIN`
are better-known names than half the V3 list.

---

## Three findings that bear on the code

### 1. A listing script must resolve feeds by address, never by name

The on-chain `description()` uses three different conventions on this chain, verified by
calling it:

| form | tickers |
|---|---|
| `RH<TICKER> / USD` | NVDA, MSFT, TSLA, SPY |
| `Robinhood <TICKER> / USD` | META, AAPL, AMZN, PLTR, GOOGL, AMD, INTC, MU, … |
| `Robinhood <TICKER>-USD` | DELL, SGOV, USAR |

`PriceOracle`'s own docstring says the feeds are named `"RHNVDA / USD"`. True for NVDA,
false for most of the roster. Nothing in the contracts matches on the string — the
oracle takes the feed address — so this is not a bug in the PR. It is a trap for the
listing scripts and the front end. `tools/verify_feeds.py` tolerates all three.

### 2. The 24h heartbeat is a session heartbeat — measured across a full weekend

Chainlink's directory publishes `heartbeat: 86400`, `threshold: 0.5`,
`marketHours: "us_equities_24/5"` for every equity feed. Under this repo's
`TradingCalendar` the session runs **Sunday 20:00 ET → Friday 20:00 ET**, so a weekend
closure is 52 hours. Feed state sampled from archive blocks across the
2026-09-11 → 09-14 weekend (`latestRoundData().updatedAt`, UTC):

| sampled at | SPY | AAPL | NVDA | META |
|---|---|---|---|---|
| Fri 20:05 | Fri 12:56 | Fri 19:51 | Fri 20:03 | Fri 19:50 |
| Sun 22:05 | Fri 12:56 | Fri 19:51 | Fri 20:03 | Fri 19:50 |
| **Mon 00:05** | **Mon 00:00** | **Mon 00:00** | **Mon 00:00** | **Mon 00:00** |
| Mon 08:00 | Mon 00:00 | Mon 02:24 | Mon 07:10 | Mon 07:58 |
| Mon 13:40 | Mon 00:00 | Mon 13:36 | Mon 13:33 | Mon 13:38 |
| Mon 15:00 | Mon 00:00 | Mon 13:42 | Mon 13:47 | Mon 14:21 |

What that says:

- **No feed updates during the closure.** The 24h heartbeat does not fire off-hours,
  exactly as the Robinhood docs warn. By Sunday evening every feed is ~52h old, past
  the 48h `maxStockAge` cap — so across a weekend **the calendar gate is what holds the
  line, not the age gate**, and a banded treasury's closed-market path (pool 600s mean,
  anchored within 30% of Friday's frozen close) is what trades.
- **Every feed refreshed at the session open, to the second** — Mon 00:00 UTC is Sunday
  20:00 ET. The first version of this document speculated that a feed which went quiet
  Friday midday would leave `tryPrice()` `Unhealthy` at Monday's open until it ticked.
  **Retracted:** Chainlink refreshes at the boundary, and the hand-over from the
  calendar path to the feed path is seconds, not hours.
- **SPY then did not update again for at least 15 hours** (still the Mon 00:00 round at
  15:00 UTC, through the 13:30 cash open), while AAPL/NVDA/META ticked through the
  overnight and again at the cash open. A 0.5% deviation threshold on a low-volatility
  index means long stretches *inside* the 48h age window where the feed is hours old and
  the pool is not. That is a `maxDeviationBps` question, not an age one, and it is the
  test worth writing before listing SGOV, SPY or QQQ: the deviation gate rejecting a
  correctly-priced pool because the feed has not moved.

Parameter consequence: `maxStockAge ≤ 48h` is right, because the calendar covers the
whole 52h closure and the feed refreshes at open. The "65 hours" in
`HedgeFunTreasury.sol` and "72h" in `PriceOracle.sol` are cash-hours arithmetic
(Fri 16:00 ET → Mon 09:30 ET); under this calendar the frozen span is 52h.

### 3. The pool the treasury trades and the pool the depth was measured on can differ

PR #2's survey reports NVDA V3 depth of $1.85M within ±1%. My census puts NVDA's 0.05%
pool at $6.2M TVL — consistent (depth within a band is a fraction of TVL), and the two
measurements agree on the ranking. But note that for AAPL the deepest `<stock>/USDG` V3
pool is the **0.05%** one (`0xaae0d815…`, $593k), while `rh`'s production watchlist
(`collector.py`) tracks AAPL at **0.30%** (`0x783c9bbb…`, $138k). Whichever pool gets
listed is the one the treasury trades forever — listings apply to future launches only
and there is no re-list for an existing strategy. Pick it off a fresh depth measurement,
not off the watchlist.

---

## What this does not answer

- **V4 listability.** Not scanned here, and not possible in v1: the V4 stock venue was
  removed from the factory (2026-09-21). A V4 stock leg would need a hookless
  `<stock>/USDG` pool, and PR #2 already records that 249 of NVDA's 304 V4 pools carry a
  hook. The hookless subset per ticker is the missing half of this table for v2.
- **How big a sell chunk each pool takes.** A listing now carries its own `sellChunkUsdg`
  (`setListingGates`), sized to no more than the pool's measured depth between the
  deviation edge and the slippage limit (`docs/OPERATIONS.md`, audit T6-1). Depth here is
  TVL-level; that number has to be measured per pool at listing time.
- **Which stock makes a good *strategy*.** This measures whether a stock *can* be listed,
  not whether a treasury trading it under a lot rule makes money. Volatility drives both
  the sell tax that funds the treasury and the `tp1`/`tp2` fills that realise it; SGOV at
  ~0% annualised volatility is listable and almost certainly pointless.
- **Anything about the four open findings in the PR.** Untouched here.

## Related

- [`POOL_SELECTION.md`](./POOL_SELECTION.md) — a different product. That document ranks
  pools for a delta-neutral LP hedged with a Lighter perp (the `rh` keeper line), where
  hedgeability is the binding gate. The launchpad has no hedge, so its gate is the oracle
  instead. The underlying pool census (`data/v3_pool_census.json`) is shared.
- [`docs/robinhood-chain/`](./docs/robinhood-chain/) — mirrored Robinhood Chain docs.
