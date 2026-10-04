> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Does the trade tax predict volume and graduation? A pons.family natural experiment

*Measured 2026-09-28 on Robinhood Chain (chain id 4663). Produced by `tools/pons_elasticity.py`. The bucket
tables are in `data/pons/summary.json` and one row per launch is in `data/pons/launches_extract.csv.gz`.
Read-only: every number below comes from `eth_getLogs` and `eth_call` against the public RPCs. Nothing was
signed.*

## The answer

Launches with a higher tax trade much less. But most of that gap comes from **who chooses the tax**, not from
the tax itself. Graduation does not move with the tax until it goes above 5%.

- **Graduation: no, up to 5%.** About 1% of launches graduate in each of the 1%, 1-2% and 2-5% buckets. The
  95% intervals are 0.9-1.1%, 1.0-1.3% and 1.1-1.3%. At 5-11%, 0.18% graduate, which is 11 of 6,070.
- **Volume across buckets: yes, strongly.** The median launch that traded did $1,919 at 1%, $450 at 1-2%, $324
  at 2-5% and $42 at 5-11%. The share of launches that drew three or more outside traders falls from 66% to 44%,
  37% and 23%.
- **Volume for the same creator: no, up to 5%.** When one creator launched at both 1% and a higher tax, the
  median volume ratio is 1.09x at 1-2% and 1.02x at 2-5%. The median change in outside traders is zero in both
  cases. At 5-11% the same creator gets half the volume, fewer outside traders and almost no graduations.
- **Most of the volume is churn.** In the median traded launch up to 5%, 89-100% of volume comes from
  addresses that both bought and sold. Volume from one-way traders is $132 at 1% and zero at 2-5%.
- **Creators earn more at a higher tax, up to 5%.** Estimated curve-phase creator revenue per launch is $21 at
  1%, $42 at 1-2%, $84 at 2-5% and $46 at 5-11%.

## Why pons answers a Hedgefun question

Hedgefun charges a creator-chosen 1-15% trade tax and is deciding whether to cap it at 1-2%. We have no
launches of our own to measure. [pons.family](https://pons.family) V2 runs on the same chain. It quotes against
the same assets: native ETH, USDG and the Robinhood stock tokens. Every trade pays a fixed base fee plus a tax
the creator chooses.

- **The base fee is 1% on every curve.** `feeBps()` returned 100 on all 112,553 curves in the window.
- **The creator tax is 0-10%, fixed at launch.** `creatorTaxBps()` is immutable and charged on the quote leg of
  every buy and sell. The total tax therefore runs from 1% to 11%.
- **Every launch also pays the same anti-snipe fee** in its first three seconds or so, described under
  caveats. It does not depend on the creator's choice.

Everything else about a pons launch runs on identical mechanics. That is as close to a natural experiment on
tax elasticity as this chain offers.

## The window and the sample

| | |
|---|---|
| blocks scanned | 64,884,917 to 74,521,741 |
| time | 2026-09-16 23:00:00 UTC to 2026-09-28 04:46:18 UTC, 11.2 days |
| launches in the scan | 112,553 |
| launch cohort in the tables | 106,631 launches up to 2026-09-27 04:46:18 UTC, each followed for at least 24 hours |
| cohort launches that traded | 87,093 |
| cohort launches that graduated | 1,156 |
| trades in the scan | 4,844,546 |
| creators (deployer addresses) in the cohort | 73,508, of which 65,408 launched once |
| quote assets in the cohort | native ETH 82,270, stock tokens 16,545, USDG 6,864, other tokens 952 |

Checks that passed:

- No curve and no token appears twice. The log reader refuses any repeated `(block, logIndex)`, any overlapping
  cache file and any gap between files.
- The creator tax implied by trades (`tax / quoteIn`) matched `creatorTaxBps()` on every traded launch.
- Every one of the 1,209 graduations in the scan has its `PoolGraduated` event.
- No launch was dropped for lack of a tax reading.

Creators mostly pick round numbers. A creator tax of 0% was chosen by 29.3% of launches, 2% by 28.4%, 1% by
17.1% and 3% by 7.2%. So 82.5% of launches carry a total tax of 3% or less, and 5.7% carry more than 5%.

The tax mix was stable over the window, so a trend in launch quality over time does not drive the bucket
differences. Launch counts fell by more than half.

| launch day (UTC) | launches | at 1% / 1-2% / 2-5% / 5-11% | traded | 3+ outside traders | graduated |
|---|--:|--:|--:|--:|--:|
| 2026-09-16 (from 23:00) | 431 | 25% / 28% / 43% / 4% | 66% | 39% | 1.16% |
| 2026-09-17 | 14,688 | 33% / 16% / 47% / 4% | 76% | 43% | 1.14% |
| 2026-09-18 | 13,600 | 27% / 21% / 48% / 4% | 81% | 45% | 1.12% |
| 2026-09-19 | 11,501 | 33% / 20% / 43% / 4% | 87% | 52% | 1.25% |
| 2026-09-20 | 10,113 | 30% / 24% / 40% / 6% | 83% | 47% | 0.64% |
| 2026-09-21 | 11,888 | 33% / 20% / 38% / 8% | 88% | 52% | 1.36% |
| 2026-09-22 | 9,542 | 31% / 20% / 44% / 5% | 88% | 53% | 1.11% |
| 2026-09-23 | 10,368 | 28% / 19% / 48% / 6% | 79% | 46% | 1.20% |
| 2026-09-24 | 9,989 | 21% / 13% / 56% / 10% | 73% | 35% | 0.83% |
| 2026-09-25 | 7,624 | 27% / 17% / 52% / 5% | 80% | 41% | 1.13% |
| 2026-09-26 | 6,057 | 28% / 16% / 48% / 7% | 85% | 45% | 0.91% |
| 2026-09-27 (to 04:46) | 830 | 27% / 14% / 38% / 21% | 85% | 42% | 0.60% |

## Results by tax bucket

Buckets are by **total** tax, the 1% base plus the creator tax. The 1% bucket is creator tax 0. The 1-2% bucket
is mostly creator tax 1%, and the 2-5% bucket is mostly creator tax 2% and 3%.

Medians of volume, trades and traders are over launches with at least one trade. "Outside traders" are distinct
recipient addresses other than the creator's. Each asset gets two tables: the outcomes the question asks about,
then the signals that say what kind of trading produced them.

### All launches, volume in USD at today's price

This table leaves out 465 traded launches quoted in tokens with no USD price.

| total tax | launches | traded | median volume | total volume | median trades | median traders | median traders, creator excluded | graduated | graduation rate, all | graduation rate, traded | median minutes to graduate |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 31,016 | 90.1% | $1,919 | $176,401,067 | 15 | 7 | 6 | 312 | 1.0% | 1.1% | 3.9 |
| 1-2% | 20,131 | 83.1% | $450 | $61,124,986 | 8 | 4 | 3 | 231 | 1.1% | 1.4% | 7.7 |
| 2-5% | 48,949 | 78.0% | $324 | $159,688,899 | 6 | 3 | 2 | 589 | 1.2% | 1.5% | 13.4 |
| 5-11% | 6,070 | 62.0% | $42 | $3,645,183 | 4 | 2 | 1 | 11 | 0.2% | 0.3% | 2.2 |

| total tax | 3+ outside traders | graduation rate, 3+ outside traders | median volume, 3+ outside traders | median one-way volume, traded | traded only by the creator | creator address's share of volume | top buyer's share of buys, graduated (median) | creators | launches by the 10 busiest creators | creator revenue per launch (est.) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 66.1% | 1.5% | $3,216 | $132 | 8.7% | 11.7% | 34.2% | 19,545 | 7.9% | $21 |
| 1-2% | 43.7% | 2.5% | $2,031 | $20 | 17.3% | 6.0% | 34.0% | 14,123 | 11.3% | $42 |
| 2-5% | 36.5% | 3.3% | $1,838 | $0 | 22.9% | 5.4% | 30.1% | 38,559 | 3.0% | $84 |
| 5-11% | 22.9% | 0.8% | $373 | $0 | 26.6% | 15.6% | 40.7% | 4,127 | 12.5% | $46 |

Spearman rank correlation with total tax, over the 86,628 traded launches: log volume -0.27, trades -0.21,
traders -0.23. Over all launches, tax against graduated is -0.002. Over the 48,534 launches with three or more
outside traders: log volume -0.18, traders -0.06, graduated +0.045.

### Stock-quoted launches, volume in USD at today's price

| total tax | launches | traded | median volume | total volume | median trades | median traders | median traders, creator excluded | graduated | graduation rate, all | graduation rate, traded | median minutes to graduate |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 7,658 | 90.6% | $2,479 | $41,996,740 | 16 | 8 | 7 | 114 | 1.5% | 1.6% | 3.0 |
| 1-2% | 3,027 | 67.3% | $623 | $9,518,842 | 8 | 4 | 3 | 40 | 1.3% | 2.0% | 28.8 |
| 2-5% | 4,313 | 47.5% | $291 | $9,306,571 | 6 | 3 | 2 | 56 | 1.3% | 2.7% | 15.6 |
| 5-11% | 1,547 | 26.3% | $48 | $453,646 | 2 | 2 | 1 | 3 | 0.2% | 0.7% | 3.2 |

| total tax | 3+ outside traders | graduation rate, 3+ outside traders | median volume, 3+ outside traders | median one-way volume, traded | traded only by the creator | creator address's share of volume | top buyer's share of buys, graduated (median) | creators | launches by the 10 busiest creators | creator revenue per launch (est.) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 75.7% | 1.9% | $3,119 | $862 | 4.2% | 10.4% | 46.4% | 4,283 | 17.2% | $21 |
| 1-2% | 36.9% | 3.4% | $2,450 | $225 | 17.2% | 3.7% | 28.7% | 1,419 | 35.0% | $43 |
| 2-5% | 23.4% | 5.4% | $2,213 | $68 | 14.8% | 2.6% | 29.9% | 3,355 | 7.5% | $58 |
| 5-11% | 7.7% | 2.5% | $1,209 | $1 | 31.0% | 3.8% | 32.9% | 1,040 | 20.7% | $20 |

Spearman over 11,421 traded launches: log volume -0.37, trades -0.28, traders -0.29. Over all launches, tax
against graduated is -0.025. Over the 8,042 launches with three or more outside traders: log volume -0.13,
traders -0.01, graduated +0.067.

The steepest gradient in the study is here. A stock-quoted launch at 5-11% draws three outside traders 7.7% of
the time, against 75.7% at 1%. Graduation over all launches still sits at 1.3-1.5% from 1% through 5%. Of the
three graduations at 5-11%, the 95% interval runs from 0.07% to 0.57%.

### USDG-quoted launches, volume in USDG

| total tax | launches | traded | median volume | total volume | median trades | median traders | median traders, creator excluded | graduated | graduation rate, all | graduation rate, traded | median minutes to graduate |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 4,376 | 98.4% | 2,773 | 20,304,775 | 16 | 8 | 7 | 78 | 1.8% | 1.8% | 0.4 |
| 1-2% | 1,156 | 80.1% | 494 | 2,783,100 | 6 | 3 | 3 | 9 | 0.8% | 1.0% | 7.3 |
| 2-5% | 1,255 | 80.2% | 492 | 4,054,940 | 6 | 3 | 2 | 48 | 3.8% | 4.8% | 7.2 |
| 5-11% | 77 | 71.4% | 810 | 255,561 | 15 | 6 | 5 | 0 | 0.0% | 0.0% | - |

| total tax | 3+ outside traders | graduation rate, 3+ outside traders | median volume, 3+ outside traders | median one-way volume, traded | traded only by the creator | creator address's share of volume | top buyer's share of buys, graduated (median) | creators | launches by the 10 busiest creators | creator revenue per launch (est., USDG) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 82.2% | 2.1% | 3,287 | 654 | 3.8% | 17.2% | 46.8% | 2,192 | 19.7% | 18 |
| 1-2% | 40.7% | 1.9% | 2,077 | 107 | 24.5% | 7.5% | 32.0% | 750 | 26.5% | 33 |
| 2-5% | 38.2% | 10.0% | 2,324 | 26 | 23.7% | 5.6% | 33.4% | 1,036 | 12.7% | 82 |
| 5-11% | 46.8% | 0.0% | 4,515 | 258 | 10.9% | 9.8% | - | 67 | 26.0% | 278 |

Spearman over 6,295 traded launches: log volume -0.29, trades -0.24, traders -0.26. Over all launches, tax
against graduated is +0.032. Over the 4,586 launches with three or more outside traders: log volume -0.09,
traders +0.01, graduated +0.101.

USDG is the one asset where 2-5% graduates clearly more often than 1%: 3.8% against 1.8%, with intervals
2.9-5.0% and 1.4-2.2%. The 5-11% bucket has only 77 launches and says nothing.

### Native ETH-quoted launches, volume in ETH

| total tax | launches | traded | median volume | total volume | median trades | median traders | median traders, creator excluded | graduated | graduation rate, all | graduation rate, traded | median minutes to graduate |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 18,704 | 88.1% | 0.45 | 42,488 | 13 | 6 | 5 | 116 | 0.6% | 0.7% | 8.8 |
| 1-2% | 15,858 | 86.5% | 0.16 | 18,299 | 8 | 4 | 3 | 181 | 1.1% | 1.3% | 6.4 |
| 2-5% | 43,288 | 81.1% | 0.12 | 55,141 | 6 | 3 | 2 | 484 | 1.1% | 1.4% | 13.8 |
| 5-11% | 4,420 | 74.6% | 0.01 | 1,105 | 4 | 2 | 2 | 8 | 0.2% | 0.2% | 0.5 |

| total tax | 3+ outside traders | graduation rate, 3+ outside traders | median volume, 3+ outside traders | median one-way volume, traded | traded only by the creator | creator address's share of volume | top buyer's share of buys, graduated (median) | creators | launches by the 10 busiest creators | creator revenue per launch (est., ETH) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 58.2% | 1.0% | 1.25 | 0.00 | 11.9% | 11.2% | 25.1% | 13,420 | 6.5% | 0.0085 |
| 1-2% | 45.3% | 2.5% | 0.74 | 0.00 | 16.9% | 6.3% | 34.4% | 12,217 | 9.1% | 0.0160 |
| 2-5% | 37.8% | 2.9% | 0.68 | 0.00 | 23.3% | 5.6% | 29.7% | 34,942 | 3.0% | 0.0329 |
| 5-11% | 27.8% | 0.7% | 0.12 | 0.00 | 26.3% | 17.9% | 43.0% | 3,152 | 11.3% | 0.0191 |

Spearman over 68,625 traded launches: log volume -0.20, trades -0.17, traders -0.18. Over all launches, tax
against graduated is +0.007. Over the 35,656 launches with three or more outside traders: log volume -0.16,
traders -0.09, graduated +0.045.

ETH launches are three quarters of the sample and 77% of all USD volume. At 1% they graduate *less* often than
at 1-2% or 2-5%: 0.6% against 1.1%.

### Creators with at most three launches, volume in USD

This is the one-off creator a launch form serves, with serial launchers removed. The pattern is the same.

| total tax | launches | traded | median volume | total volume | median trades | median traders | median traders, creator excluded | graduated | graduation rate, all | graduation rate, traded | median minutes to graduate |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 19,909 | 90.2% | $1,822 | $99,833,290 | 15 | 7 | 7 | 185 | 0.9% | 1.0% | 6.4 |
| 1-2% | 13,933 | 91.8% | $530 | $46,784,610 | 8 | 4 | 3 | 173 | 1.2% | 1.4% | 6.9 |
| 2-5% | 40,393 | 80.8% | $324 | $133,068,177 | 6 | 3 | 2 | 531 | 1.3% | 1.6% | 13.4 |
| 5-11% | 4,186 | 63.3% | $32 | $2,891,206 | 5 | 3 | 2 | 9 | 0.2% | 0.3% | 2.8 |

| total tax | 3+ outside traders | graduation rate, 3+ outside traders | median volume, 3+ outside traders | median one-way volume, traded | traded only by the creator | creator address's share of volume | top buyer's share of buys, graduated (median) | creators | launches by the 10 busiest creators | creator revenue per launch (est.) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% (base only) | 67.3% | 1.4% | $2,926 | $73 | 7.0% | 9.9% | 37.6% | 18,563 | 0.2% | $19 |
| 1-2% | 50.7% | 2.3% | $2,063 | $35 | 15.1% | 6.1% | 32.0% | 13,321 | 0.2% | $46 |
| 2-5% | 37.1% | 3.5% | $1,764 | $0 | 23.6% | 5.4% | 29.7% | 37,221 | 0.1% | $86 |
| 5-11% | 27.1% | 0.8% | $316 | $1 | 27.6% | 15.6% | 32.9% | 3,760 | 0.7% | $51 |

### The same creator at different taxes

The bucket tables compare different people. A creator who picks 0% creator tax is not the same creator who
picks 10%, and anything that differs between them lands in the comparison.

This table holds the creator fixed. It uses every creator who launched at 1% and also in the higher bucket. For
each creator it compares their own rate at 1% with their own rate at the higher tax, then averages across
creators. The volume and trader columns take each creator's median over their traded launches at each tax, then
the median across creators. The 2,689 creators who used more than one bucket have a median of three launches.

| comparison | creators | their launches at 1% / at the higher tax | traded | 3+ outside traders | graduated | graduated: creators better / worse / same | median volume, higher tax over 1% | median outside traders, higher minus 1% |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1% vs 1-2% | 627 | 3,581 / 2,391 | 83.1% → 81.2% (-1.9 pp) | 50.5% → 51.0% (+0.5 pp) | 0.9% → 1.4% (+0.5 pp) | 17 / 20 / 590 | 1.09x (266 more, 227 less, of 494) | +0 (231 more, 215 less, of 500) |
| 1% vs 2-5% | 894 | 3,115 / 3,567 | 75.3% → 71.3% (-4.0 pp) | 41.6% → 39.3% (-2.3 pp) | 0.4% → 1.9% (+1.6 pp) | 24 / 8 / 862 | 1.02x (299 more, 289 less, of 593) | +0 (255 more, 248 less, of 605) |
| 1% vs 5-11% | 210 | 1,120 / 523 | 75.9% → 56.6% (-19.3 pp) | 30.4% → 17.8% (-12.6 pp) | 1.7% → 0.1% (-1.6 pp) | 0 / 5 / 205 | 0.50x (38 more, 72 less, of 110) | -1 (33 more, 62 less, of 114) |

Held to the same creator, a tax of up to 5% leaves volume and outside traders where they were. It lowers the
share of launches that trade at all by 2-4 points and does not lower graduation. The fourfold volume gap in the
bucket tables does not survive. Above 5%, the effect is real and large, and no creator graduated more often at
the higher tax.

## What the volume is made of

Pons volume is dominated by trading that a tax is designed to suppress.

- **Round trips.** In the median traded launch, addresses that both bought and sold that token supply 89% of
  volume at 1%, 92% at 1-2%, 100% at 2-5% and 72% at 5-11%. The largest launches in the window are
  ETH-quoted, with 2,000-3,300 trades, 150-770 trader addresses, 85-99% round-trip volume and $240k-$395k
  each. Five of the eight largest never graduated, although a 4.2 ETH curve (about $11k) should fill long
  before that. Volume that goes in and straight back out does not fill a curve.
- **One-way volume is small.** Volume from addresses that only bought or only sold has a median of $132 at 1%
  and $0 from 2-5% up. Across all launches it is $78M of the $401M.
- **The creator's own address is a small part of it.** Its trades are 5-16% of volume. It paid 5-17% of the
  creator tax back to itself. Trading by other wallets the creator controls cannot be seen on chain.
- **Graduation is fast and often concentrated.** The median graduation took 8.6 minutes after launch. The
  quartiles are 0.9 and 43.5 minutes. Of 1,156 graduations, 303 came within a minute and 15 in the launch block
  itself. In 251 of them, one address supplied at least half of all buys.
- **A small tax filters bots before it filters people.** The share of launches that trade at all falls with
  tax, while the median number of outside traders in launches with three or more stays at 9-10 up to 5%. The
  simplest reading is that automated snipers and churners skip taxed launches, because a round trip pays the
  tax twice.

## Method

**Sources.** Factory `0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e` events `TokenLaunched`, `LaunchSwept` and
`PoolGraduated`. Curve events `CurveBuy(buyer, recipient, quoteIn, tokensOut, fee, tax)`,
`CurveSell(seller, recipient, tokensIn, quoteOut, fee, tax)` and `CurveCompleted`. Curve events are pulled by
topic across all addresses and attributed to a launch by the emitting address. 156,649 curve logs came from
addresses the factory did not launch in the window: curves launched before it, or other contracts. They are
dropped.

**Tax.** `TokenLaunched` does not carry the tax, so `creatorTaxBps()` and `feeBps()` are read from every curve
through Multicall3 at `latest`. Both are immutables, so a `latest` read is exact for any launch. As a check, the
creator tax implied by trades was compared with the read. There were no mismatches.

**Volume.** `CurveBuy.quoteIn` is the amount actually spent after any refund, gross of fee and tax.
`CurveSell.quoteOut` is net of both, so a gross sell is `quoteOut + fee + tax`. Quote volume is gross buys plus
gross sells in the quote asset's own units. One-way volume excludes every address that both received tokens
from a buy and sold tokens in the same launch.

**Traders.** Unique traders are distinct `recipient` addresses across buys and sells. `msg.sender` equals
`recipient` on 88% of trades, so most users call the curve directly.

**Graduation.** A curve graduates inside the buy that crosses its threshold, which emits `CurveCompleted` on the
curve. "Graduated" means `CurveCompleted` was observed. Time to graduation is the graduation block's timestamp
minus the launch block's. Both are read exactly; other timestamps are interpolated on a 5,000-block grid.

**USD.** USDG is taken at 1.00. ETH, cbBTC and 25 stock tokens use the Chainlink Data Feed answer read at
analysis time. The other 37 stock tokens have no push feed here and use the deepest `<stock>/USDG` V3 pool's
spot price at analysis time. Neither is the price at the time of each trade.

**Within-creator comparison.** For each creator with launches at 1% and in the higher bucket, the rate of each
outcome at each tax is computed over that creator's own launches. The tables report the mean across creators,
and how many creators did better, worse or the same. The volume ratio uses only creators with a traded launch at
both taxes.

**RPC discipline.** `eth_getLogs` runs against the official public RPC. It is limited to 15,000 blocks per
window and one request a second. The window halves on the two server-side limits the RPC enforces, a
10,000-log result cap and a query timeout, then grows back. State reads use publicnode at `latest`. About
530 MB of raw logs are cached under `data/pons/logs/`, which is git-ignored, so a rerun only pulls what is
missing.

## Caveats, in the order they matter

1. **The tax is chosen, not assigned.** The bucket tables mix the tax with who chose it. The within-creator
   table removes differences between creators. It cannot remove a creator's own choice to use a higher tax on
   the launches they care more about. It covers only creators who launched more than once at different taxes.
   Nothing here is a randomised experiment.
2. **Most volume is churn, and some of it may be wash.** Pons pays the creator tax straight to the creator,
   plus 35% of the base fee. Volume a creator buys from their own wallets therefore costs them about 0.65% per
   trade, whatever creator tax they set. The creator tax cannot deter it. Only the creator's own deployer
   address is identifiable. It carried 5-16% of volume and paid 5-17% of the creator tax. Wallets the creator
   controls under other addresses are invisible here. Three outside traders is a low bar for a sybil.
3. **The deployed pons curve charges an anti-snipe fee the vendored source does not have.** The factory and a
   sampled curve both answer `snipeTaxStartBps() = 9900` and `snipeTaxSeconds() = 3`. Charged trades pay one of
   three levels above the 1% base: 7.18%, 1.19%, or 99% of the trade including the creator tax. The 99% level is
   the rarest, at a few hundred trades. Nearly every charged trade came within 30 blocks, about three seconds,
   of the launch block, and none came later than 63. The fee goes into the `fee` field, never `tax`. It hit
   135,408 trades on 41,279 launches, about $0.59M of the $4.79M in fees. It is the same for every launch,
   whatever the creator tax, so it does not confound the buckets. But
   `ref/pons/contractsV2/src/v2/PonsV2BondingCurve.sol` contains no snipe code at all, and `ref/CLAUDE.md` calls
   the snipe tax a no-op. On the chain that is wrong. The vendored curve is older than the deployed bytecode.

   | blocks after the launch block (about 0.1 s each) | trades | charged above the base fee | median effective fee when charged | highest |
   |---|--:|--:|--:|--:|
   | 0-10 | 227,032 | 70,491 | 7.18% | 99.00% |
   | 11-30 | 111,991 | 64,766 | 1.19% | 99.00% |
   | 31-60 | 152,884 | 148 | 1.19% | 7.18% |
   | 61-150 | 267,916 | 3 | 1.19% | 1.19% |
   | 151-300 | 314,657 | 0 | - | - |
   | more than 300 | 3,770,066 | 0 | - | - |

4. **Pons locks its buybacks and pays the creator; Hedgefun does neither.** Of the pons base fee, 30% goes to
   the protocol and 35% buys the token back into a vault that vests over five years. The remaining 35% and the
   whole creator tax go to the creator. Hedgefun burns its buy tax and splits its sell tax among treasury,
   protocol and creator. Traders face the same price either way. Creators face very different incentives,
   which matters for caveat 2.
5. **One window, late in the product's life.** The factory's first activity was around 2026-08-04. This window
   covers eleven days from 2026-09-16, when launches were falling from about 14,700 a day to about 6,000. A
   hype period could rank taxes differently. The tax mix was stable from day to day within the window.
6. **Right-censoring is small.** Each launch was followed for at least 24 hours. Of the 1,209 graduations in the
   scan, 57 took longer than that, so graduations of the last day's launches are undercounted by up to 5%. That
   applies about equally to every bucket. Launches from before the window are excluded entirely.
7. **Some cells are small.** The 5-11% bucket has 11 graduations across all assets, 3 among stock-quoted
   launches and 0 among 77 USDG launches. The 95% interval for all 5-11% launches is 0.10-0.32%. Differences
   of a few tenths of a point in graduation between 1%, 1-2% and 2-5% are within noise in most tables.
8. **Graduation thresholds differ by asset but are close in dollars.** They are 4.2 ETH, 8,090 USDG, 41.6 NVDA,
   13.57 META and 72.2 SPCX, all about $8,000-$11,000 at today's prices. The tables are split by asset anyway.
9. **USD figures use today's prices.** ETH is 77% of USD volume, so the ETH price on 2026-09-28 sets most of the
   dollar totals. Stocks without a Chainlink feed are priced from V3 pool spot. They carry 20% of stock-quoted
   USD volume, mostly DJT, SGOV and AMC, and some of their pools are thin: INDA holds about $9,000 and SNOW
   about $25,000. The per-symbol appendix keeps stock units.
10. **Only the curve phase is measured.** Pons keeps taxing trades after graduation through its V4 hook. That
    volume and the post-graduation creator revenue are not in this data. Hedgefun has no curve phase, so a
    bonding curve's concentration of trading in the first minutes has no direct counterpart there.
11. **Not measured.** The pons front end's default tax is unknown, though the spikes at 0%, 1% and 2% creator
    tax suggest presets. Also not measured: off-chain promotion, whether a launch's metadata was filled in, and
    competition between launches as the daily count changed.

## What this means for Hedgefun's 1-2% proposal

On pons, a total tax of 1-2% does not beat 2-5% for the same creator. Volume, outside traders and graduation
are flat across that range, and graduation was slightly higher at 2-5%. The raw bucket tables would suggest that
a low tax brings four times the volume. That gap comes from who chooses a low tax, so it is not evidence for a
1-2% cap. What pons does show is damage above 5%: half the volume, fewer outside traders and almost no
graduations for the same creator. Hedgefun's current range runs to 15%, beyond anything pons offers, so the
region pons shows to hurt is inside our range. Estimated creator revenue per pons launch was about twice as
high at 2-5% as at 1-2%, while the same creators traded as much. If Hedgefun launches behaved like these, a 1-2%
cap would give up about half the tax per launch without a measured gain in volume or graduation. The data
supports a cap at or below 5%. It does not single out 1-2%. Two differences limit the transfer: Hedgefun has no
bonding curve, and its tax does not go back to the creator.

## Appendix A: stock-quoted launches by symbol, in stock units

Symbols with at least 100 launches in the cohort. The other 41 symbols had 1,222 launches and 18 graduations
between them; all are in `summary.json` under `quotes`.

| stock | launches | at 1% / 1-2% / 2-5% / 5-11% | traded | graduated, total (by bucket) | volume, stock units | price used |
|---|--:|--:|--:|--:|--:|--:|
| NVDA | 5,478 | 1,742 / 604 / 2,117 / 1,015 | 2,890 | 35 (24 / 3 / 8 / 0) | 47,360 | $224.14 |
| META | 2,160 | 778 / 782 / 535 / 65 | 1,479 | 49 (15 / 16 / 18 / 0) | 15,962 | $735.44 |
| SPCX | 2,156 | 1,330 / 380 / 394 / 52 | 1,777 | 16 (7 / 4 / 5 / 0) | 61,796 | $149.36 |
| SPY | 716 | 499 / 90 / 104 / 23 | 642 | 23 (18 / 0 / 5 / 0) | 5,806 | $771.21 |
| DJT | 662 | 499 / 105 / 43 / 15 | 609 | 10 (10 / 0 / 0 / 0) | 363,976 | $9.13 |
| GME | 594 | 382 / 81 / 115 / 16 | 504 | 8 (6 / 1 / 1 / 0) | 127,514 | $23.25 |
| GLD | 409 | 163 / 89 / 135 / 22 | 334 | 9 (4 / 1 / 4 / 0) | 3,860 | $385.59 |
| SGOV | 398 | 317 / 58 / 13 / 10 | 363 | 9 (7 / 2 / 0 / 0) | 27,782 | $100.98 |
| TSLA | 395 | 199 / 73 / 101 / 22 | 262 | 3 (2 / 0 / 1 / 0) | 2,896 | $371.02 |
| GOOGL | 354 | 202 / 69 / 71 / 12 | 275 | 7 (5 / 1 / 1 / 0) | 4,564 | $343.25 |
| AAPL | 334 | 134 / 68 / 114 / 18 | 238 | 5 (2 / 0 / 3 / 0) | 3,200 | $340.43 |
| QQQ | 282 | 189 / 52 / 31 / 10 | 235 | 3 (1 / 1 / 0 / 1) | 1,542 | $740.33 |
| MSFT | 211 | 117 / 39 / 46 / 9 | 172 | 4 (3 / 0 / 1 / 0) | 2,135 | $517.72 |
| AMZN | 208 | 93 / 54 / 45 / 16 | 149 | 6 (1 / 2 / 1 / 2) | 2,879 | $248.97 |
| MSTR | 149 | 78 / 29 / 34 / 8 | 102 | 1 (1 / 0 / 0 / 0) | 1,700 | $156.88 |
| RDDT | 133 | 45 / 60 / 23 / 5 | 114 | 2 (2 / 0 / 0 / 0) | 1,535 | $150.98 |
| PLTR | 125 | 73 / 28 / 15 / 9 | 98 | 3 (1 / 1 / 1 / 0) | 3,207 | $188.39 |
| BABA | 120 | 73 / 26 / 14 / 7 | 97 | 0 (0 / 0 / 0 / 0) | 5,260 | $109.01 |
| COIN | 117 | 62 / 30 / 19 / 6 | 82 | 0 (0 / 0 / 0 / 0) | 1,352 | $192.62 |
| AMC | 114 | 53 / 37 / 19 / 5 | 77 | 1 (0 / 1 / 0 / 0) | 255,437 | $2.92 |
| AMD | 104 | 42 / 26 / 26 / 10 | 74 | 0 (0 / 0 / 0 / 0) | 782 | $616.57 |
| RBLX | 104 | 45 / 25 / 26 / 8 | 87 | 1 (0 / 0 / 1 / 0) | 11,020 | $45.71 |

## Appendix B: files and how to reproduce

| file | in git | what it is |
|---|---|---|
| `tools/pons_elasticity.py` | yes | scanner, enricher and analysis |
| `data/pons/summary.json` | yes | every table above, the checks, the snipe profile, the within-creator comparison, the per-symbol tables |
| `data/pons/launches_extract.csv.gz` | yes, 6.4 MB | one row per launch in the scan, the columns the tables are computed from. The creator appears as an integer id in first-launch order |
| `data/pons/quote_tokens.json`, `quote_prices.json` | yes | quote-asset symbols and decimals, and the USD prices this run used, with their sources |
| `data/pons/launches.csv` | no, about 75 MB | the full per-launch table with every address; `analyze` rebuilds it |
| `data/pons/logs/`, `curve_meta.json`, `block_times.json` | no, about 540 MB | raw log cache, per-curve fee reads, block timestamps |

```
python3 tools/pons_elasticity.py scan --from-block 64884917 --to-block 74521741   # about 1 request a second
python3 tools/pons_elasticity.py enrich                                           # re-reads prices at latest
git checkout data/pons/quote_prices.json                                          # restore this run's prices
python3 tools/pons_elasticity.py analyze
```

`enrich` reads quote prices at `latest`, so restoring the committed `quote_prices.json` before `analyze` is what
reproduces the USD figures exactly. Everything in stock, ETH or USDG units reproduces without it.
