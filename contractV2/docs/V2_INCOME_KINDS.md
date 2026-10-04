# V2 dividend kinds: a staking dividend for the stock strategy, chosen at launch

Status: source, local tests and fork rehearsals only. Nothing in this document is a deployment receipt. The
registration below is an operator action that has not been broadcast.

## What a creator can now choose

A creator names a strategy kind for their own `(symbol, nonce)` before `predict`/`launch`, with the existing
`V2TreasuryDeployer.setStrategyKind(symbol, nonce, kind)`. The kind is in the launch terms and in the treasury's
CREATE2 address, and cannot be changed after launch.

| Kind | Contract | Stock strategy | Tax share | Realised strategy profit | LP stock fees |
|---|---|---|---|---|---|
| 0 (default) | `HedgeFunV2AllInTreasury` | take-profit / dip / stop | booked as a new lot | buy-back | buy-back |
| strategy + 25% dividend | `HedgeFunV2StrategyDividend25Treasury` | the same rungs | 25% stakers, 75% buy-back | 25% stakers, 75% buy-back | buy-back |
| strategy + 50% dividend | `HedgeFunV2StrategyDividend50Treasury` | the same rungs | 50% / 50% | 50% / 50% | buy-back |
| buy-back | `HedgeFunV2BuybackTreasury` | none | buy-back | none | buy-back |
| dividend | `HedgeFunV2DividendTreasury` | none | 100% stakers | none | 100% stakers |
| buy-back + dividend | `HedgeFunV2BuybackDividendTreasury` | none | 50% / 50% | none | 50% / 50% |

Four are new: the two strategy kinds and the two without a strategy. Kind ids are assigned by registration order
on each registry: read them from the registration output, do not hard-code them. The ratio is a constant of each
kind's code. A different ratio is a new kind, registered the same way.

## The strategy kinds

`HedgeFunV2StrategyIncomeTreasury` is `HedgeFunV2AllInTreasury` with three differences.

- **The graduation principal is the only stock that becomes strategy capital.** The factory books in the
  transaction that transfers it; the treasury records it as `principalStock` and opens its lot as kind 0 does. If
  graduation happens while the stock market is shut, the lot opens at the first live price, and it is exactly the
  principal: income that arrived in between is not in it.
- **The tax share is income, not a new lot.** Kind 0 books every arrival as a lot, so trading fees accumulate as
  strategy principal. Here `book()` splits them: `stakingBps()` to the staking pool, the rest to the buy-back
  budget.
- **Realised profit is split the same way.** When a take-profit sells above cost, the profit kept after the
  keeper's bounty is split, instead of all of it funding the buy-back.

Stock-side LP fees are unchanged and all fund the buy-back. The liquidity vault requires the treasury's balance to
rise by exactly the fee it credits, so that path is left as it is.

Lots open only for the principal and for the strategy's own dip buys. While arrived stock is still unclassified
the treasury refuses to open a lot, so `execute()` cannot turn tax into principal on its way to another action,
and a dip waits for `book()`. A keeper calls `book()` before `execute()`.

If the stock token refuses the transfer to the staking pool, that share stays in the buy-back budget. A
take-profit is never blocked by the dividend.

The staking pool's `totalFunded` and its `IncomeFunded` event are the record of what was paid; the treasury keeps
no second counter. Its runtime is 24,531 bytes, 45 under the limit.

The registry applies its legacy stop check to every kind that is not kind 0: a stop at or inside
`maxSlippageBps + pool fee + bountyBps` is refused at `predict`.

## The kinds without a strategy

`HedgeFunV2DividendTreasury` and `HedgeFunV2BuybackDividendTreasury` hold the graduation principal and pay out
everything that arrives afterwards. The sections below describe them.

## Income, and what is not income (kinds without a strategy)

Income is the stock that reaches the treasury **after** graduation:

- the treasury's share of the trade tax: claimed from the curve, and paid by the hook's sweep;
- the stock side of the locked position's LP fees, credited by `V2LiquidityVault.collectFees()`;
- any stock sent to it.

The stock the treasury holds when the factory books it at graduation is the launch's principal. An income kind
records it as `protectedGraduationStock` and never spends it: not on a dividend, not on a buy-back. It stays in the
treasury. A dividend paid out of the raise would be a return of the buyers' own capital under another name.

Stock claimed from the curve before graduation is in the treasury when the factory books it, so it is counted as
principal, not income. Claiming after graduation makes it income.

## The split (kinds without a strategy)

```text
stakers' share of income so far = totalIncomeStock * stakingBps / 10000   (cumulative)
of which transferred             = totalDividendStock
of which still in the treasury   = pendingDividendStock
buy-back budget                  = the rest, in buybackStock
```

The share is computed on the cumulative total, so rounding never drifts toward either side. The stakers' share
never enters `buybackStock`, so the inherited `buyback()` cannot spend it.

`book()` books arrived stock and transfers what is pending. The liquidity vault requires the treasury's balance to
rise by exactly the LP fee it credits, so `creditLiquidityFee` only records the split; `distribute()`, or the next
`book()`, transfers it. Anyone may call either. Between an LP-fee collection and that transfer, the base's
`unbookedStock()` view includes `pendingDividendStock`; `unbookedIncome()` is the figure that excludes it.

If the transfer to the staking pool fails, for a paused or blocking stock token, the call reverts and nothing is
relabelled: the stock stays unbooked in the treasury, or parked in the vault, until a later call succeeds.

## The staking pool

Each dividend-kind treasury, with or without a strategy, deploys its own `V2StakingIncome` in its constructor and is that pool's only funding
source. `treasury.staking()` returns it.

- Stake the launch token; earn the listed stock token. The reward is the stock, not USDG and not ETH.
- Each funding streams over 7 days. A new funding restarts a 7-day stream over the new amount plus whatever had
  not yet streamed.
- A stake is locked for 7 days from the staker's most recent deposit. Adding to a stake restarts that staker's lock.
- `withdraw` returns principal and never attempts a reward transfer, so a blocked reward token cannot trap staked
  tokens. `claim` pays accrued rewards separately.
- Income funded while nothing is staked is queued and starts streaming with the first stake.
- No administrator can withdraw staked tokens, rewards or donations.

The pool is a port of `FunStakingIncome` from the realised-income experiments, with one change: its income source
is the treasury, on chain, instead of a separately funded sponsor.

## What this does not do

- It does not make the launch token a claim on the treasury's principal. Stakers receive income as it arrives.
- It does not promise income. With no trading there is no tax share and no LP fee, and a strategy that never
  takes a profit pays no profit share.
- The two kinds without a strategy run none: `execute()` reverts `UseBuyback`; tp/dip/stop parameters are
  accepted and ignored.
- The dividend is paid in the stock token. Its USD value moves with the stock, and a stock token that pauses or
  blocks transfers pauses the dividend with it.
- Token-side tax from V4 buys still has to be converted by the factory owner (`convertFees`) before the hook can
  pay it out. Until then it is not income.
- Staked tokens are still in `totalSupply`. A dividend kind burns nothing; only the buy-back share burns.

## Keeper actions

```text
curve.claimFees(treasury)          once after graduation, and whenever the curve still owes the treasury
hook.sweep(poolId)                 pays the treasury its stock-side tax share
treasury.book()                    classifies arrivals as income and pays the stakers' share; call before execute()
treasury.execute()                 strategy kinds only: stop, take-profit (splits the profit), dip
vault.collectFees()                credits LP stock fees to the treasury, burns LP token fees
treasury.distribute()              kinds without a strategy only: pays the stakers' share of LP fees just credited
treasury.buyback()                 buy-back share only, when the budget and cooldown allow
```

All are permissionless.

## Enabling on an existing deployment

Three independent operator actions. Each is a script that checks its bindings before its first transaction;
simulate without `--broadcast` first.

1. **Dividend kinds.** `OPERATOR` must be the factory owner. Eight transactions.

   ```sh
   OPERATOR=<owner> V2_FACTORY=<factory> forge script script/RegisterV2IncomeKinds.s.sol:RegisterV2IncomeKinds \
     --rpc-url "$RPC_URL" --sender "$OPERATOR"
   # review the four logged kind ids, then repeat with: --account <keystore> --broadcast --slow
   V2_FACTORY=<factory> STRATEGY25_KIND=<id> STRATEGY50_KIND=<id> DIVIDEND_KIND=<id> SPLIT_KIND=<id> \
     forge script script/RegisterV2IncomeKinds.s.sol:VerifyV2IncomeKinds --rpc-url "$RPC_URL"
   ```

   Existing kinds and launched treasuries are unchanged. Pending quotes stay valid: registration does not touch
   launch terms.

2. **ETH payment route.** [TESTNET_V2_ETH_BRIDGE.md](./TESTNET_V2_ETH_BRIDGE.md): seeds the WETH/tUSDG pool that
   routes native ETH to a listed stock.

3. **ETH launch fee and launch-and-buy.** [V2_NATIVE_LAUNCH.md](./V2_NATIVE_LAUNCH.md):
   `ActivateV2NativeLaunch` deploys the native launch router, authorises it, and switches the factory's launch fee
   to a fixed amount of wei. `LAUNCH_FEE_WEI` is chosen by the operator; the script has no default.

Steps 2 and 3 are existing source. Their order matters: activation refuses an empty or missing WETH/USDG pool.

## Evidence

Local, offline:

- `forge test --offline --match-path test/V2StrategyIncome.t.sol`: the strategy kind against a real
  concentrated-liquidity stock venue, in both currency orders. Principal lot, tax as income, a take-profit whose
  profit is split, a dip that waits for unclassified stock, LP fees to the buy-back, a refused staking transfer,
  a graduation during a market closure, a staker's claim, and a fuzz of the ledger.
- `forge test --offline --match-contract V2IncomeKindsTest`: the kinds without a strategy, the registration
  script against the fixture factory, and a strategy kind launched and graduated through the real factory, curve,
  hook and vault.

Fork, no key and no broadcast, against the deployed testnet factory
`0xACEB03aAeE5494Aa54929Ec840630ae32A9ade0A` at block 128498681, six tests:

- the registration script run as the factory's owner, then a launch of each of the four kinds through the
  deployed factory, hook and vault, graduation, trades both ways, and the income split at the kind's ratio;
- with the clock moved to a Tuesday session and the deployed test market's owner moving the stock's V3 pool and
  feed: a strategy kind opens its principal lot at graduation, takes profit on the deployed venue with the profit
  split 25/75, refuses a dip while arrived tax is unclassified, splits that tax on `book()` and then buys the dip;
- a strategy kind with a stop sells at the stop and pays no dividend.

```sh
INCOME_KINDS_FORK=true INCOME_KINDS_FORK_BLOCK=$(cast block-number --rpc-url https://rpc.testnet.chain.robinhood.com) \
  forge test --threads 1 --match-contract TestnetV2IncomeKindsForkTest -vv
```

On 2026-10-03, `TestnetV2EthBridgeForkTest` passed at block 128456854: bridge seeding from the operator's actual
balance, native-launch activation, and a launch-and-buy from a wallet holding only ETH. The public RPC prunes old
state, so both commands need a fresh block.

The existing kinds' creation code is byte-identical before and after this change. `creditLiquidityFee` and
`HedgeFunV2AllInTreasury._takeProfit` gained the `virtual` keyword, which emits no code.

## Front end

- Launch form: offer the kind, show the ratio, and state that the choice is permanent and that an income kind runs
  no stock strategy.
- Token page for an income kind: `staking()`, then on the pool `balanceOf`, `unlockAt`, `earned`, `totalStaked`,
  `periodFinish`; actions `approve` + `stake`, `claim`, `withdraw`. Show that adding to a stake restarts the lock.
- Kinds without a strategy: `totalIncomeStock`, `totalDividendStock`, `pendingDividendStock`, `buybackStock`,
  `protectedGraduationStock`. Show principal separately from income.
- Strategy kinds: `principalStock`, `buybackStock`, the lot views kind 0 already has, and the pool's
  `totalFunded` for dividends paid.
- ABIs: `abi/HedgeFunV2StrategyDividend25Treasury.json` (both strategy kinds share it),
  `abi/HedgeFunV2DividendTreasury.json` (both kinds without a strategy share it) and `abi/V2StakingIncome.json`.
