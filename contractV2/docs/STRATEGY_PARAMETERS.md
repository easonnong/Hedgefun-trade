# Strategy parameters, keeper reward and buy-back sizing

Status: source, offline tests, a fork check and a price-series backtest. No registration, default or listing was
changed on a public chain by this document's work. Everything here is for FUTURE launches.

This covers the ordinary stock strategy (kind 0): the graduation stock is a lot at its booking price; a lot is sold
only above its cost (`tp1Bps`, then `tp2Bps`), the principal comes back as USDG and the profit stays in stock for the
buy-back; `dipBps` under the last sale, `lotBps` of the USDG buys a new lot. It never sells at graduation.

## What is recommended, and when

| Setting | Value | Who sets it |
|---|---|---|
| `tp1Bps` / `tp2Bps` / `dipBps` | 100 / 200 / 100 (1% / 2% / 1%) | the creator, per launch |
| `lotBps` | 5000 (half the cash per dip buy) | the creator, per launch |
| keeper reward `bountyBps` | 10 (0.1%) | the factory owner, `script/SetV2KeeperReward.s.sol` |
| buy-back sizing | 10% of the waiting budget per call | the kind: `HedgeFunV2PercentBuybackTreasury` |

**The 1% rule is the recommendation only where the stock trades against USDG in a 0.05% pool.** With a 0.3% pool
the same rule pays more in fees than it gains over 3% / 6% / 3%, which is then the better choice (tables below).
On chain 46630 the TSLA, AMZN, META and MSFT listings use 0.3% pools; AAPL, GME, GOOGL and NVDA use 0.05% pools.
A listing's pool is the owner's choice when the stock is listed.

Rungs under 1% are not recommended at any cost level tested: 0.5% / 1% / 0.5% returned less than half of what
1% / 2% / 1% did.

## Why: the backtest

`tools/strategy_backtest.py` replays the rule on TSLA hourly closes, regular and extended hours, 2023-11-03 to
2026-10-02 (12,077 prices over 730 trading days, TSLA +71.4%), for a treasury of 18,000 USD of stock, one keeper
visit per price. Slippage is assumed at 0.05% on top of the pool fee.

"NAV + buy-backs" adds what was spent on buy-backs back to what the treasury still holds. The rule turns the
stock's gains into buy-backs, so the treasury's own NAV falls while the stock rises; that is the rule working, not
a loss, and it is why the two are shown together.

Pool fee 0.3%, keeper 0.5% (chain 46630's TSLA listing today):

| take-profit 1 / 2 / dip, buy share | sells | buys | buy-backs | days with a buy-back | bought back, of capital | treasury NAV | NAV + buy-backs |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5% / 10% / 5%, 20% | 151 | 74 | 117 | 81 | 78% | -8.5% | +69.1% |
| 3% / 6% / 3%, 50% | 411 | 158 | 227 | 142 | 96% | -19.1% | +77.2% |
| 2% / 4% / 2%, 50% | 444 | 169 | 218 | 118 | 73% | -14.5% | +58.9% |
| 1% / 2% / 1%, 50% | 919 | 387 | 444 | 206 | 88% | -29.7% | +58.7% |
| 0.5% / 1% / 0.5%, 50% | 611 | 250 | 244 | 84 | 38% | -20.2% | +17.5% |

Pool fee 0.3%, keeper 0.1%:

| take-profit 1 / 2 / dip, buy share | sells | buys | buy-backs | days with a buy-back | bought back, of capital | treasury NAV | NAV + buy-backs |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5% / 10% / 5%, 20% | 151 | 74 | 117 | 81 | 79% | -5.2% | +74.1% |
| 3% / 6% / 3%, 50% | 411 | 158 | 228 | 142 | 100% | -13.2% | +86.6% |
| 1% / 2% / 1%, 50% | 964 | 392 | 450 | 208 | 96% | -17.2% | +78.8% |
| 0.5% / 1% / 0.5%, 50% | 640 | 251 | 244 | 84 | 40% | -11.4% | +28.5% |

Pool fee 0.05%, keeper 0.1% (the recommended setting):

| take-profit 1 / 2 / dip, buy share | sells | buys | buy-backs | days with a buy-back | bought back, of capital | treasury NAV | NAV + buy-backs |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5% / 10% / 5%, 20% | 155 | 75 | 116 | 85 | 81% | -3.0% | +78.1% |
| 3% / 6% / 3%, 50% | 373 | 131 | 197 | 118 | 101% | -2.7% | +98.4% |
| 2% / 4% / 2%, 50% | 428 | 166 | 222 | 114 | 71% | -3.2% | +67.9% |
| **1% / 2% / 1%, 50%** | 1058 | 408 | 507 | 220 | 115% | -8.8% | **+106.1%** |
| 0.5% / 1% / 0.5%, 50% | 722 | 262 | 268 | 91 | 48% | -6.5% | +41.7% |

A keeper reward of 0.05% instead of 0.1% moves these by one to three points. Most of the reward's cost is on dip
buys, where it is a share of the whole purchase; on a take-profit it is a share of the profit only.

What the rule does not do: act when the stock is under every lot's cost. Over the last 60 trading days of the
series (TSLA -8%) the 3% and 5% rules took no action at all, and the tightest rule moved about 1% of the capital
into buy-backs. No setting of the rungs makes a buy-back happen on a day the stock has not risen past a lot.

## The cycle treasury

`HedgeFunV2CycleTreasury` is the same lot rule with one more entry: after a real sale, if the stock rises
`dipBps` above that sale's price, it buys once more, up to the listing's chunk. On this series it did worse than
the ordinary rule at every setting tried (pool fee 0.05%, keeper 0.1%):

| take-profit 1 / 2 / dip, buy share | rule | sells | dip buys | recovery buys | days with a buy-back | bought back, of capital | NAV + buy-backs |
|---|---|---:|---:|---:|---:|---:|---:|
| 3% / 6% / 3%, 50% | ordinary | 373 | 131 | 0 | 118 | 101% | +98.4% |
| 3% / 6% / 3%, 50% | cycle | 430 | 188 | 6 | 187 | 78% | +55.4% |
| 1% / 2% / 1%, 50% | ordinary | 1058 | 408 | 0 | 220 | 115% | +106.1% |
| 1% / 2% / 1%, 50% | cycle | 848 | 343 | 24 | 196 | 70% | +42.9% |

A recovery buy moves the reference the next dip is measured from up to the price it bought at, so in the
declines that followed, the cycle rule started buying sooner and higher. It has more days with a buy-back and
less bought back. One stock and one period; a steadier climb would favour it more.

It is also not available as a choice today: it is not registered on chain 46630's factory, it is a direct,
non-upgradeable implementation, and it keeps the legacy rung floor of twice the slippage limit plus pool fee
(2.1% with a 0.05% pool, so the 1% row above is not launchable with it as it stands).

## The keeper reward

`bountyBps` is a factory default, frozen into each treasury at launch. `SetV2KeeperReward` changes it for future
launches in one owner transaction, sends every other default back unchanged and requires that nothing else moved.
A launch quoted before the change has to be quoted again.

At 0.1% a take-profit's reward is cents: a 2,000 USDG sale at a 3% gain carries about 0.06 USDG. Nobody outside
will call `execute()` for that, so a lower reward means running the keeper.

```sh
export OPERATOR=<owner> V2_FACTORY=<factory> KEEPER_REWARD_BPS=10
forge script script/SetV2KeeperReward.s.sol:SetV2KeeperReward --rpc-url "$RPC_URL" --sender "$OPERATOR"
```

## The percentage buy-back

Kind 0 offers the token pool `buybackChunkUsdg` (500 USDG) per `buyback()`. That is one number for every launch:
a small treasury spends a take-profit's whole gain in one or two calls, and a large one is held to it.

`HedgeFunV2PercentBuybackTreasury` is kind 0 with one difference. A call offers `BUYBACK_BPS` (1000, a tenth) of the
budget that is waiting, so a budget of any size leaves in the same number of steps, each smaller than the last, one
per `buybackCooldown`. A share that would be under the listing's minimum lot is raised to it, and a last remainder
under a lot goes whole, so the tail ends. The price limit against the pool's own mean, `maxBuybackImpactBps`, the
cooldown and the bounty are kind 0's and unchanged; `buybackChunkUsdg` is accepted and ignored. A different share
is a different kind.

Sizing changes how many buy-backs there are, not how much is bought back. On the 1% rule above:

| capital | sizing | buy-backs | per trading day | days with a buy-back | bought back (USD) |
|---:|---|---:|---:|---:|---:|
| 18,000 | fixed 500 USDG (kind 0) | 507 | 0.7 | 220 of 730 | 20,676 |
| 18,000 | 10% of the budget | 2,827 | 3.9 | 220 of 730 | 20,676 |
| 180,000 | fixed 500 USDG (kind 0) | 844 | 1.2 | 239 of 730 | 206,780 |
| 180,000 | 10% of the budget | 8,630 | 11.8 | 239 of 730 | 206,780 |

The days do not change: with a 60-second cooldown a budget is spent within the hour it arrives. Spreading it over
more days is `buybackCooldown`, another factory default.

Two ways to get it:

- **New launches**: `script/RegisterV2PercentBuyback.s.sol` appends the kind (three operator transactions; the id
  comes from the result). A creator selects it with `setStrategyKind`. The registry applies its stop check to
  every kind that is not kind 0: a stop at or inside `maxSlippageBps` + pool fee + `bountyBps` is refused.
- **A live kind-0 treasury**: `HedgeFunV2PercentBuybackTreasuryLogic` keeps kind 0's storage and identity, so the
  owner can schedule it through the upgrade controller for that treasury, with the two-day notice.

The logic's runtime is 24,536 bytes, 40 under the limit. The hook it overrides, `_buybackChunk` in
`HedgeFunTreasuryBase`, added 10 bytes to every treasury. Kind 0's creation code therefore differs from the one
the deployed registries were built with; `ReviewedTreasuryRegistry` and `tools/treasury_profile_config.py` now
accept a registry whose kind 0 is either that reviewed code, by its pinned hash, or this source's own.

## What the backtest is and is not

- It is a model of the rule, in Python. It was checked against the contracts for three price paths
  (`tools/tests/test_strategy_backtest.py`): two on a fork of chain 46630, the 5% and the 1% rule, where every
  visit took the same number of actions and stock, cash and buy-back spend ended within 0.1% to 0.3%; and the
  cycle treasury in the repository's own fixture, sixteen steps with a recovery buy, where actions, lots and
  the armed price were identical and balances within 0.001%. On the first fork path the buy-backs came to 9
  calls where the model counts 5, because the token pool's impact cap fills a call short; the model's
  buy-back counts are low.
- One visit per hour, closes only. Overnight and weekend gaps are one step. A 1% rule on a feed that prints on
  0.5% moves would see more triggers than an hourly series shows.
- No token pool, no trade tax or LP fees arriving, no user flow, no stops, and one assumed slippage number in
  place of the stock pool's depth. With slippage at 0.30% every rule returns 5 to 20 points less and the order of
  the rules does not change. The tighter the rule, the more this assumption matters.
- One stock, one period, in which it rose 71%.
- Source: `https://query1.finance.yahoo.com/v8/finance/chart/TSLA?interval=1h&range=730d&includePrePost=true`,
  fetched 2026-10-04, SHA-256 `30b30c3dadc41f36bc91a0aef88f0292633b0ac7625b2d37dceae89bd6f0a960`. Two bars whose
  close was more than 8% from both neighbours were dropped. Normalised file:
  `data/tsla-hourly-2023-11_2026-10.csv`, SHA-256
  `a5bfa433f767e94daf44a5b0bc2c1993eacb858bf1d241c9a0deccc2c4f85f04`.
- `deploy/tsla-history-2026-10-03` replays daily closes for 2022 to 2025 through the contracts themselves, one
  keeper visit a day. It cannot show intraday frequency; this cannot show the token.

```sh
python3 tools/strategy_backtest.py                    # the tables above
python3 -m unittest tools/tests/test_strategy_backtest.py
```
