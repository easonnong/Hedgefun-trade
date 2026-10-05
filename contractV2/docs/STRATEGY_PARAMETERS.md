# Strategy parameters, keeper reward and buy-back sizing

Status: source, offline tests, a fork check and a price-series backtest. No registration, default or listing was
changed on a public chain by this document's work. Everything here is for FUTURE launches.

This covers the three rules a strategy treasury can run on its stock, and what to set on each:

- **ordinary** (kind 0): the graduation stock is a lot at its booking price; a lot is sold only above its cost
  (`tp1Bps`, then `tp2Bps`), the principal comes back as USDG and the profit stays in stock for the buy-back;
  `dipBps` under the last sale, `lotBps` of the USDG buys a new lot. It never sells at graduation.
- **cycle**: the ordinary rule plus one entry. After a real sale, a rise of `dipBps` over that sale's price buys
  once more, up to the listing's chunk.
- **rebalance** (schema 3): keep a target share of the tradable value in stock, trade back to it outside a band,
  and reserve a share of each sale's realised net gain for the buy-back.

"1% / 2% / 1%" below means `tp1Bps` 100, `tp2Bps` 200, `dipBps` 100; the share after it is `lotBps`.

## What is recommended, and when

| Choice | Recommendation |
|---|---|
| Rule for a stock that trends | **cycle**, 3% / 6% / 3%, half the cash per buy: `HedgeFunV2UpgradeableCycleTreasury` |
| Rule for a long horizon | **rebalance**, target 70%, band 1%, all of a net gain to the buy-back |
| Rule for a stock that ranges | ordinary, 3% / 6% / 3%, half the cash per buy |
| keeper reward `bountyBps` | 10 (0.1%), set by the factory owner with `script/SetV2KeeperReward.s.sol` |
| buy-back sizing | a tenth of the waiting budget per call (the cycle kind, and `HedgeFunV2PercentBuybackTreasury`) |

The ordinary rule is the wrong default. After it takes profit it buys again only under its last sale price, and a
stock that keeps climbing never comes back there: on NVDA it took ten actions in three years while the stock rose
440%, and on eight of the ten stocks below it bought back a fifth of what the cycle rule did. It was the best rule
on one stock of ten, TSLA, the one that ranged, which is the stock this document first looked at alone.

No rule here helps in a falling stock without a stop: all three hold what they bought. And every number below is
a model on past prices of stocks chosen because they are volatile, most of which rose several-fold.

## Every rule on ten stocks

`python3 tools/strategy_backtest.py --matrix`. Treasury of 18,000 USD of stock, pool fee 0.05%, keeper 0.1%,
slippage assumed at 0.05%. Rebalance rows use a 1% band and reserve all of a net gain. Each cell is **bought back
as a share of capital / NAV + buy-backs / actions**.

Hourly closes including extended hours, 2023-11-03 to 2026-10-02 (SNDK from 2025-02-24, CRWV from 2025-03-28):

| stock | days | stock change | ordinary 3/6/3 | ordinary 1/2/1 | cycle 3/6/3 | cycle 5/10/5 | rebalance 70% | rebalance 90% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TSLA | 730 | +71% | 101% / +98% / 504 | 115% / +106% / 1466 | 78% / +55% / 624 | 76% / +64% / 369 | 47% / +59% / 285 | 18% / +69% / 60 |
| ORCL | 730 | +33% | 12% / +11% / 32 | 7% / +7% / 79 | 92% / +37% / 357 | 63% / +17% / 276 | 49% / +42% / 212 | 26% / +42% / 58 |
| COIN | 730 | +121% | 8% / +8% / 17 | 6% / +5% / 34 | 136% / +79% / 899 | 112% / +63% / 658 | 124% / +111% / 481 | 109% / +143% / 126 |
| CRWV | 381 | +136% | 39% / +38% / 96 | 58% / +56% / 292 | 123% / +74% / 502 | 85% / +46% / 535 | 123% / +123% / 426 | 106% / +152% / 126 |
| MSTR | 730 | +260% | 35% / +34% / 121 | 12% / +11% / 76 | 156% / +89% / 1008 | 137% / +80% / 712 | 226% / +199% / 584 | 299% / +332% / 189 |
| NVDA | 730 | +440% | 5% / +5% / 10 | 2% / +2% / 10 | 118% / +115% / 754 | 86% / +85% / 276 | 120% / +179% / 222 | 89% / +320% / 68 |
| AMD | 730 | +490% | 24% / +24% / 129 | 22% / +20% / 306 | 124% / +121% / 697 | 101% / +99% / 394 | 128% / +198% / 299 | 94% / +357% / 84 |
| PLTR | 730 | +955% | 20% / +20% / 75 | 19% / +18% / 226 | 188% / +178% / 989 | 120% / +117% / 422 | 239% / +285% / 359 | 303% / +584% / 131 |
| MU | 730 | +1428% | 29% / +28% / 92 | 25% / +23% / 165 | 196% / +182% / 879 | 113% / +108% / 446 | 283% / +344% / 397 | 434% / +788% / 154 |
| SNDK | 405 | +3309% | 30% / +29% / 196 | 37% / +34% / 498 | 245% / +218% / 1117 | 163% / +147% / 546 | 457% / +492% / 499 | 924% / +1297% / 224 |

Across the ten: the ordinary rule bought back a median 20% to 29% of capital whatever its rungs, and as little as
2%; cycle 3% / 6% / 3% a median 130% and never under 78%; rebalance at a 70% target a median 126% and never under
47%. A 90% target keeps more of the stock and bought back the most where the stock rose most, and the least where
it did not.

Every print of each stock's mainnet Chainlink feed, 2026-06-21 to 2026-10-05, about 105 days: these are the prices
the contracts themselves would have read.

| stock | days | stock change | ordinary 3/6/3 | ordinary 1/2/1 | cycle 3/6/3 | cycle 5/10/5 | rebalance 70% | rebalance 90% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TSLA | 74 | -6% | 8% / +2% / 77 | 6% / -2% / 96 | 8% / -2% / 69 | 10% / +7% / 28 | 0% / -4% / 27 | 0% / -5% / 4 |
| ORCL | 74 | -21% | 0% / -21% / 0 | 0% / -21% / 0 | 0% / -21% / 0 | 0% / -21% / 0 | 0% / -15% / 49 | 0% / -19% / 10 |
| COIN | 74 | +14% | 40% / +35% / 208 | 35% / +27% / 729 | 36% / +31% / 213 | 24% / +23% / 61 | 2% / +11% / 51 | 1% / +13% / 10 |
| CRWV | 74 | -22% | 0% / -22% / 0 | 4% / -19% / 175 | 0% / -22% / 0 | 0% / -22% / 0 | 0% / -14% / 91 | 0% / -19% / 24 |
| MSTR | 74 | +46% | 27% / +26% / 203 | 33% / +29% / 510 | 29% / +29% / 262 | 18% / +19% / 39 | 3% / +32% / 83 | 0% / +41% / 14 |
| NVDA | 74 | +14% | 14% / +14% / 43 | 20% / +18% / 358 | 14% / +14% / 43 | 9% / +11% / 17 | 0% / +10% / 16 | 0% / +12% / 2 |
| AMD | 75 | +22% | 20% / +20% / 189 | 18% / +16% / 480 | 22% / +23% / 200 | 25% / +25% / 82 | 0% / +16% / 52 | 0% / +20% / 8 |
| PLTR | 74 | +49% | 17% / +17% / 68 | 13% / +11% / 256 | 38% / +37% / 146 | 16% / +16% / 39 | 3% / +32% / 30 | 1% / +43% / 7 |
| MU | 74 | -4% | 13% / +5% / 133 | 13% / +3% / 283 | 10% / +0% / 103 | 22% / +19% / 125 | 0% / -1% / 87 | 0% / -3% / 14 |
| SNDK | 75 | -21% | 11% / -11% / 103 | 9% / -17% / 219 | 11% / -11% / 103 | 10% / -7% / 195 | 0% / -12% / 139 | 0% / -17% / 28 |

Over three and a half months the picture is the other way round for the rebalance rule: it reserved almost nothing,
because it only ever sells the slice above its target and its buy-backs build with the trend. The lot rules paid
from the first take-profit. Between the two lot rules at 3% / 6% / 3% this window does not pick a winner: the
cycle rule bought back more on MSTR, AMD and PLTR, the ordinary rule bought back more or ended higher on COIN,
TSLA and MU, and the two were equal on the other four. Where the stock only fell (ORCL, CRWV) neither lot rule
acted at all and the rebalance rule lost less for the cash it held. The case for the cycle rule rests on the
three-year table above, whose stocks were picked for being volatile and mostly rose several-fold.

## The ordinary rule's rungs, on TSLA

TSLA is the one stock of the ten where the ordinary rule did best, so read this as what its rungs do in a
stock that ranges, not as a case for the rule.

`tools/strategy_backtest.py` replays the ordinary rule on TSLA hourly closes, regular and extended hours, 2023-11-03 to
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

Pool fee 0.05%, keeper 0.1%:

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

## The upgradeable cycle kind

`HedgeFunV2UpgradeableCycleTreasury` is the cycle rule behind the upgrade controller, with the percentage buy-back.
Its logic is `HedgeFunV2CycleTreasury`'s rule unchanged: the whole of that contract's test suite, and the
scheduler suite it inherits, runs against the new logic in both asset orders.

- A `buyback()` offers a tenth of the waiting budget, as `HedgeFunV2PercentBuybackTreasury` does.
- The rungs keep the legacy floor: `tp1Bps` and `dipBps` at least twice the listing's slippage limit plus pool fee
  (2.1% with a 1% limit and a 0.05% pool). 3% / 6% / 3% is launchable; 1% / 2% / 1% is not.
- `reentryPending()` and `recoveryDue()` are not in it. `reentrySaleAt != 0` is the first; a keeper simulates
  `execute()` for the second.
- **The logic's runtime is 24,532 bytes, 44 under the limit.** To get there the proxy's parameters are written as
  five raw storage words that the proxy's constructor packs, in place of a struct copy in the logic (about 550
  bytes), and the two views above were left in the directly deployed contract only. A fuzz test deploys the proxy
  with every parameter at arbitrary values and compares all of them. Anything added to this logic has to take
  something out.
- `script/RegisterV2UpgradeableCycle.s.sol` appends the kind in three operator transactions, behind the
  reviewed-registry guard. The registry applies its stop check to it as to every kind that is not kind 0.
- The registry checks a creator's rungs by name only for kind 0. For this kind, rungs under the floor above (or
  any other parameter its constructor refuses) still get an address and terms from `predict`, and the launch
  then reverts `TreasuryDeployFailed`. A front end has to apply the floor itself before quoting.

### What the recovery entry does to the rest of the rule

Three properties of the rule as it is written. They are tested behaviour, not defects, and they are not what
"buys once more, up to the listing's chunk" suggests on its own.

- **The recovery buy moves the dip ladder up.** Every buy, the recovery buy included, sets the price the next dip
  is measured from. The chunk caps the recovery buy; it does not cap the dip that follows. With 3% / 6% / 3%,
  half the cash per buy, a 2,000 USDG chunk and 100,000 USDG in reserve after a take-profit at 106.00: the
  recovery buy fires at 109.18 and spends 2,000; a pull-back to 105.90 is then an ordinary dip, 3% under 109.18,
  and spends half of the remaining 98,000. One failed 3% break-out puts about half the reserve back into stock
  just under the price it was sold at. The ordinary rule would have waited for 102.82.
- **The recovery anchor does not expire.** It is the price of the last live-market sale of at least `minLotUsdg`.
  It stays until the next buy of either kind consumes it, a closed-market sale cancels it, or another such sale
  replaces it. A later stop under `minLotUsdg` renews the wait but does not replace the anchor, so a recovery can
  fire at a price unrelated to the most recent sale.
- **A closed-market sale of at least `minLotUsdg` cancels a pending entry.** On a treasury with a band, a
  take-profit at the pool's price during a scheduled closure clears the anchor a live sale set. If the stock then
  opens higher there is no recovery entry, and the next buy is a dip under that closed-market sale.

The directly deployed `HedgeFunV2CycleTreasury` is still not registered anywhere and is not upgradeable.

## The keeper reward

`bountyBps` is a factory default, frozen into each treasury at launch. `SetV2KeeperReward` changes it for future
launches in one owner transaction. `setDefaults` replaces the whole struct, so the script sends every other
default back as it read it, and it refuses to build the transaction unless the factory's defaults hash to
`EXPECTED_DEFAULTS_HASH`, the snapshot that was reviewed. That check is the simulation's: a `setDefaults` that
lands between the simulation and the broadcast is still overwritten, so do not run this beside another owner
operation, and run `VerifyV2KeeperReward` against the confirmed chain afterwards. A launch quoted before the
change has to be quoted again.

At 0.1% a take-profit's reward is cents: a 2,000 USDG sale at a 3% gain carries about 0.06 USDG. Nobody outside
will call `execute()` for that, so a lower reward means running the keeper.

```sh
export OPERATOR=<owner> V2_FACTORY=<factory> KEEPER_REWARD_BPS=10 EXPECTED_CHAIN_ID=<chain id>
# keccak256(abi.encode(factory.getDefaults())) of the defaults that were read and reviewed
export EXPECTED_DEFAULTS_HASH=<hash>
forge script script/SetV2KeeperReward.s.sol:SetV2KeeperReward --rpc-url "$RPC_URL" --sender "$OPERATOR"
# after the transaction is confirmed, with the hash the run above logged
export EXPECTED_DEFAULTS_HASH_AFTER=<hash>
forge script script/SetV2KeeperReward.s.sol:VerifyV2KeeperReward --rpc-url "$RPC_URL"
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

The logic's runtime is 24,520 bytes, 56 under the limit. The hook it overrides, `_buybackChunk` in
`HedgeFunTreasuryBase`, added 10 bytes to every treasury. Kind 0's creation code therefore differs from the one
the deployed registries were built with; `ReviewedTreasuryRegistry` and `tools/treasury_profile_config.py` now
accept a registry whose kind 0 is either that reviewed code, by its pinned hash, or this source's own.

## What the backtest is and is not

- It is three models of the rules, in Python, not the contracts. Each was checked against its contract for
  recorded price paths, which `tools/tests/test_strategy_backtest.py` replays: the ordinary rule on a fork of
  chain 46630 for the 5% and the 1% rungs (same actions every visit; stock, cash and buy-back spend within 0.1% to
  0.3%); the cycle rule through `HedgeFunV2CycleTreasury` in the repository's fixture, sixteen steps with a
  recovery buy (same actions, lots and armed price; balances within 0.001%); the rebalance rule through the
  schema-3 treasury with realised-net-income accounting, fourteen steps (same actions; stock, cash, reserve and
  loss carry within one part in ten million). On the first fork path the buy-backs came to 9 calls where the
  model counts 5, because the token pool's impact cap fills a call short; the model's buy-back counts are low.
- The rebalance model follows the schema-3 treasury's accounting as merged from #31 (separate daily budgets, net
  income after costs and recovered losses).
- The ten-stock tables use one cost setting, a 0.05% pool fee and a 0.1% keeper reward. Chain 46630's TSLA listing
  charges 0.3% and 0.5% today. Only the TSLA tables are repeated at those costs.
- The ten stocks were picked for being volatile, and in these three years most of them rose several-fold. A
  sample like that flatters every rule that stays invested. It says which rule copes with a trend; it says
  nothing about a bear market, where all three follow the stock down.
- One visit per price, closes only for the hourly series. No token pool, no trade tax or LP fees arriving, no
  user flow, no stops, and one assumed slippage number in place of the stock pool's depth. A treasury whose
  stock has risen thirty-fold sells amounts no test pool here has; real fills would be worse than modelled.
- The feeds are 24/5: no print on a weekend or an NYSE holiday, the first print of the week at Sunday 20:00 New
  York time, about an eighth of prints overnight. That is the contract calendar's own week. A print is a move of
  0.5% or a 24-hour heartbeat, so a rung under 1% asks for a step the feed barely resolves.
- Each feed's first rounds, 2026-06-21 to 2026-06-23, carry answers 1e8 times the scale of the rest. They are
  rescaled here. `PriceOracle` fixes a feed's decimals when it is constructed: a stock should not be listed
  against a feed until its scale has settled.
- Sources, row counts and SHA-256 of every file: `data/backtest/MANIFEST.json`. Hourly closes are from Yahoo's
  chart endpoint, fetched 2026-10-05, with any bar whose close is more than 8% from both neighbours dropped; the
  last hourly close of each stock is within 0.33% of the feed print at that time. Feed prints are every round of
  each aggregator proxy on chain 4663.
- `deploy/tsla-history-2026-10-03` replays daily closes for 2022 to 2025 through the contracts themselves, one
  keeper visit a day. It cannot show intraday frequency; this cannot show the token.

```sh
python3 tools/strategy_backtest.py                    # the TSLA tables
python3 tools/strategy_backtest.py --matrix           # every rule on every stock
python3 -m unittest tools/tests/test_strategy_backtest.py
```
