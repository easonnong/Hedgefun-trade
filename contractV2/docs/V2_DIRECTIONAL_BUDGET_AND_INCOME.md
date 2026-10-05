# Directional daily budgets, LP allocation and earned FUN buybacks

This candidate integrates PR #28 hardening and follows the weekend TWAP repair in PR #29. It changes only the schema-3 strategy treasury's
budget/income behavior. The registry identity fix is reused from PR #30 so the candidate recognizes the reviewed existing registry
as well as one deployed from the current build. The public testnet contracts and asset LP settings have not
been changed by this work.

## Daily budget

Buy and sell each have a configurable percentage budget. On the date's first **successful** execution, the
contract fixes the basis to booked/bookable stock at the live stock oracle plus available USDG, immediately
before that action. Locked LP and reserved buyback stock are excluded. Each successful action charges its
actual inventory consumption to its own direction. Partial fills charge actual amounts; failed fills roll back.

A 50% buy / 20% sell configuration on 10,000 USDG tradable capital permits up to 5,000 USDG buys and 2,000 USDG
sells that date. A sale does not consume buy capacity. A later price move or deposit cannot change those caps.
The combined ceiling can therefore exceed the old shared ceiling: 50% / 50% permits up to 100% combined turnover.
Per-action input percentages (at most 25%), the listing-dependent minimum band, target gap, cooldown,
minimum size, price and slippage guards still apply.

The date remains the oracle calendar's US equity trading date (20:00 New York boundary, including DST), not
UTC midnight or a rolling 24-hour window. This is a throttle, not a guarantee of a daily dip purchase: healthy
live pricing, sufficient cash, the allocation trigger and executable pool liquidity are still required.

`dailyRiskLimits()` exposes epoch, basis, buy/sell caps and charged buy/sell usage. Before the first successful
action the basis is a live preview. The original `turnoverInEpoch()` remains the actual aggregate turnover.
The original `riskLimits()` ABI remains available, but its daily cap/remaining/used values aggregate the two
directions; a client must use the new getter to display spendable capacity for a particular direction.

Storage uses a separate namespace; no inherited/proxy/successor slots move. When upgrading an old treasury
mid-date, the old aggregate cannot reveal which side traded. It is conservatively charged to **both** directions
until the next date. This can temporarily leave less headroom; it never silently resets prior spend. Legacy
configs apply their one daily percentage independently to both sides. Newly packed, unequal percentages need
the new policy/kind registration and strict configuration adapter described in TREASURY_PROFILES.md.
An older config must also meet #28's 25% action ceiling and listing-dependent band floor to use this replacement;
older configs outside those bounds require a separately reviewed migration, not an unconditional upgrade.

## Controlled LP comparison

`test/V2DirectionalLpComparison.t.sol` runs the production curve, V4 manager, hook, locked liquidity vault,
router and buyback. The external stock/USDG venue/feed is a local mock fixed at 100 USDG per stock. Both runs
use 1 million FUN initial supply, a 79.31% curve sale, identical curve parameters, 1% hook tax and 0.3% LP fee.
Each order-size scenario starts from the same graduation state; sell cases use existing holders' FUN.
These are contract simulations, not live returns, USD quotes, or promises of a future market price.

| Measurement | 50% into LP | 70% into LP |
|---|---:|---:|
| Raised stock value (USDG) | 19,166.26 | 19,166.26 |
| Initial LP stock value (USDG) | 9,583.13 | 13,416.38 |
| Initial treasury principal (USDG) | 9,583.13 | 5,749.88 |
| 1,000 USDG buy: FUN received | 8,102.65 | 8,106.09 |
| 1,000 USDG buy: ending price change | +8.59% | +8.55% |
| 10,000 FUN sell: net USDG received | 1,027.95 | 1,060.79 |
| 10,000 FUN sell: ending price change | -20.50% | -15.34% |
| 50,000 FUN sell: net USDG received | 3,585.71 | 4,019.79 |
| 50,000 FUN sell: ending price change | -61.31% | -51.37% |
| Actual LP stock fees from identical 10,000 USDG buy volume | 30.00 | 30.00 |
| Following FUN buyback: earned USDG value spent | 30.00 | 30.00 |
| Following FUN buyback: FUN burned after keeper reward | 127.4951 | 127.5185 |
| Following FUN buyback: price increase | about 0.17% | about 0.17% |

70% improves sell-side liquidity but reduces strategy principal by 40% relative to 50%. It barely changes the
buy-side results in this fixture: the existing additional single-sided FUN position already supplies much of
the upward liquidity. A simple 70/50 depth multiplier would misrepresent the actual V4 layout. Both locked LP
positions retain their liquidity through fee collection and buyback, and graduation never burns the unsold FUN.

Recommendation: use 70% for **future launches** when sell-side depth is the priority, with the reduced strategy
capital made explicit. No registry default or existing frozen LP allocation was changed here. An existing
pool cannot move treasury principal into its immutable seed allocation merely by changing the registry setting.

## Net realized-income payout

A gross oracle-marked gain is insufficient evidence of profit. Schema 3 now uses actual sale proceeds **after
venue fees and the execution reward**, subtracts sold inventory cost, and recovers tracked realized strategy
losses before reserving anything for FUN buyback. The loss ledger persists across dates and compatible upgrades.
Stock acquired by the strategy already carries a cost including its acquisition fees and execution reward.

For sold stock A, retained stock B, average cost C, live mark P, net sale cash N, carried loss L, and payout
fraction f: positive excess cash is G = max(N - A*C - L, 0). The eligible reserve is conservatively bounded by
`B <= f*G / (P - f*(P-C))` and by the amount initially withheld. This includes the retained stock's own cost and
marked gain rather than classifying the whole retained amount as free profit. Rounding favors the treasury.
When net sale cash is below sold cost, the difference adds to the loss ledger and the reserve is zero.
Any withheld stock that is not eligible remains booked strategy inventory.

The minimum size is checked on the fill, A plus the stock withheld beside it, both scaled by a short fill. It is
not checked on what finally leaves inventory, A + B. With a loss still to recover B is zero, so a complete fill
whose swapped part alone is under `minLotUsdg` would otherwise be refused as dust, on every attempt, for as long
as the loss stood; and the loss could not be recovered because no sale could execute. Such a sale now executes,
charges A to the sell budget and applies its gain to the loss. `preview()` reports the same sale as due.

The tests independently compare the reserved stock's value against the configured fraction of actual net
portfolio gain; they also cover partial fills, tiny marked gains erased by fees, losses carried into later dates,
subsequent recovery, and ledger preservation through the real upgrade controller.

`StrategyIncomeAccounted` reports eligible excess cash, remaining loss carryforward and actual stock reserved.
The retained `GainToBuyback` compatibility event's `gain` field is explicitly gross/oracle-marked; consumers
must not treat it as the net distributable income. `unrecoveredLossUsdg()` exposes the new ledger.

Historical realized losses before this upgrade are not reconstructable from current storage and are **not
backfilled**. This ledger covers sales from activation onward; it is not a whole-fund NAV high-water mark and
does not offset unrealized losses or LP impermanent loss. Earned LP fees remain independently eligible for
buyback and do not erase strategy loss history.

The separate buyback still buys **FUN with income stock**, burns FUN, preserves principal, and retains its
existing fixed maximum chunk, cooldown, FUN/stock TWAP/anchor and impact limit. It does not guarantee a price
increase. Percentage-based buyback pacing is a separate product change; this candidate tightens which income
can fund the existing bounded execution rather than relaxing its price defenses.

## Verification and deployment boundary

The immutable read-only component holds preview calculations, bounded policy reads and sale-income arithmetic
so the treasury remains deployable within EIP-170. It has no custody, approvals or state-writing entry points.
Preview and execution call the policy through the same component; neither a policy nor a keeper supplies
recipients, pools or execution bounds. Each trade still enforces directional budgets in the treasury itself.
The component is replaced only by the existing delayed implementation upgrade, not a separate mutable pointer.
The policy now sees this component as `msg.sender` on both paths. The supported stateless rebalance policy does
not inspect the caller; a custom policy that depends on the old caller needs a separate compatibility review.

Tests and evidence: `docs/fuzz/directional-income-2026-10-04/`. The local fork tests use the deployed 48-hour
controller, actual testnet V3 pool and TestnetMarket price swaps. They never broadcast transactions, etch code,
or override token balances in the directional-budget scenarios. Applying this behavior publicly still requires
candidate registration for new launches or a reviewed compatible upgrade for an existing schema-3 proxy.
