# V2 dividend kinds: a staking dividend for the stock strategy, chosen at launch

Status: source, local tests and fork rehearsals only. Nothing in this document is a deployment receipt. The
registration below is an operator action that has not been broadcast.

## What a creator can now choose

A creator names a strategy kind for their own `(symbol, nonce)` before `predict`/`launch`, with the existing
`V2TreasuryDeployer.setStrategyKind(symbol, nonce, kind)`. The kind is in the launch terms and in the treasury's
CREATE2 address, and cannot be changed after launch.

| Kind | Contract | Stock strategy | Tax share | Realised strategy profit | LP stock fees |
|---|---|---|---|---|---|
| 0 (default) | `HedgeFunV2UpgradeableTreasury` | take-profit / dip / stop | booked as a new lot | buy-back | buy-back |
| strategy + 25% dividend | `HedgeFunV2StrategyDividend25Treasury` | the same rungs | 25% stakers, 75% buy-back | 25% stakers, 75% buy-back | buy-back |
| strategy + 50% dividend | `HedgeFunV2StrategyDividend50Treasury` | the same rungs | 50% / 50% | 50% / 50% | buy-back |
| buy-back | `HedgeFunV2BuybackTreasury` | none | buy-back | none | buy-back |
| dividend | `HedgeFunV2DividendTreasury` | none | 100% stakers | none | 100% stakers |
| buy-back + dividend | `HedgeFunV2BuybackDividendTreasury` | none | 50% / 50% | none | 50% / 50% |

Four are new: the two strategy kinds and the two without a strategy. Kind ids are assigned by registration order
on each registry: read them from the registration output, do not hard-code them. The ratio is a constant of each
kind's code. A different ratio is a new kind, registered the same way.

The four dividend kinds are still directly deployed immutable treasuries. They do not inherit kind 0's upgrade
controller. Their staking pool fixes its income source at deployment, so using them behind a proxy requires a
separate initialization and storage design; registering these kinds does not make them upgradeable.

## The strategy kinds

`HedgeFunV2StrategyIncomeTreasury` is `HedgeFunV2AllInTreasury` with three differences.

- **The graduation principal is the only stock that becomes strategy capital.** The factory initializes the
  exact transfer with `wireWithGraduation` before sending it; the treasury records it as `principalStock`.
  Optional `book()` then opens its lot as kind 0 does. If that booking reverts, the principal stays protected. If
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
no second counter. Run `forge build --sizes` on the candidate commit to check the limited runtime headroom.

The registry applies its legacy stop check to every kind that is not kind 0: a stop at or inside
`maxSlippageBps + pool fee + bountyBps` is refused at `predict`.

## The kinds without a strategy

`HedgeFunV2DividendTreasury` and `HedgeFunV2BuybackDividendTreasury` hold the exact graduation principal and split
other income, including fees claimed before graduation. The sections below describe them.

## Income, and what is not income (kinds without a strategy)

Income is stock other than the factory's exact graduation-capital transfer:

- the treasury's share of the trade tax: claimed from the curve, and paid by the hook's sweep;
- the stock side of the locked position's LP fees, credited by `V2LiquidityVault.collectFees()`;
- any stock sent to it.

The factory measures the raise remaining after LP seeding and initializes that exact amount through
`wireWithGraduation`. An income kind records it as `protectedGraduationStock` and never spends it: not on a dividend,
not on a buy-back. It stays in the
treasury. A dividend paid out of the raise would be a return of the buyers' own capital under another name.

Claiming curve fees before or after graduation leaves them income. Pre-graduation fees and gifts wait until
the pool is wired. If the factory's optional `book()` fails, a later permissionless call classifies only this
income; it cannot reclassify graduation capital. The initializer is factory-only and once-only. A failed capital
transfer rolls it back with the graduation; a failed initializer cannot fall back to legacy `wire()`.

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
- Global allocation and each account's fractional reward carry across checkpoints. Empty claims and frequent
  claims cannot repeatedly discard those fractions; personal fractions remain with the account after exit.
  The effective index precision is `1e45`. Only unassigned global dust can follow a change in the stake set:
  less than `3.5e-7` raw reward units at the factory's maximum `uint128` launch-token supply.
- `MAX_TOTAL_FUNDED = floor(uint256.max / 1e45)` caps lifetime funding, including amounts already claimed.
  It is about `1.1579e32` raw units (about `115.8 trillion` tokens at 18 decimals). Funding above that limit
  reverts before transferring funds, so even a one-wei stake cannot overflow the cumulative reward index.
- No administrator can withdraw staked tokens, rewards or donations.

The pool originated from `FunStakingIncome`. Its income source is the treasury on chain; the accounting above
also preserves division remainders and bounds lifetime funding.

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
curve.claimFees(treasury)          whenever the curve owes the treasury; claim timing does not change income
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

These revised kinds require a factory whose graduation path calls `wireWithGraduation`, as introduced in #25.
They intentionally reject legacy `wire()`. Registering them on an older factory that lacks this path would make
their launches unable to graduate. Registration and readback now reject incompatible factories. The script
reconstructs the complete reviewed #25 factory and graduation-module runtimes from pinned build templates,
checks every immutable binding, and verifies curve/vault creation-code identities before any broadcast.
Different addresses running that reviewed build are supported. A new implementation or compiler build needs
a fresh compatibility review and updated template identities; a selector match or operator-supplied hash is
not sufficient. The fork suite targets compatible testnet factory
`0xc9610d4A749b2A62a7327a0f40B59013D8fC415a` and rejects legacy factory
`0xACEB03aAeE5494Aa54929Ec840630ae32A9ade0A`.

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

The revised kinds passed 16 in-memory fork tests against testnet factory
`0xc9610d4A749b2A62a7327a0f40B59013D8fC415a` at block 128583570 on 2026-10-04, with no key or broadcast:

- the registration script run as the factory's owner, then a launch of each of the four kinds through the
  deployed factory, hook and vault, graduation, trades both ways, and the income split at the kind's ratio;
- with the clock moved to a Tuesday session and the deployed test market's owner moving the stock's V3 pool and
  feed: a strategy kind opens its principal lot at graduation, takes profit on the deployed venue with the profit
  split 25/75, refuses a dip while arrived tax is unclassified, splits that tax on `book()` and then buys the dip;
- both strategy ratios execute take-profit, dip and stop; a stop pays no dividend;
- all four kinds preserve principal after an injected optional-book failure and classify preclaimed fees as
  income; the lifecycle checks also exercise a buy-back, locked-withdrawal rejection and complete staking exit.

`V2IncomeGraduation.t.sol` fuzzes all four kinds, 6/18-decimal stock, LP shares from 10% through 100%, claim
timing, early/late gifts, optional booking failure and initializer/transfer rollback. Its capital oracle is the
factory's measured `GraduationCapitalSplit` event, not the treasury's own principal counter.
`V2StakingIncomeInvariant.t.sol` sequences four users' funding, stakes, withdrawals, claims, time advances,
donations and transfer failures against a separate transfer ledger. It checks asset backing and exits after
each sequence. CI runs three recorded seeds and a distinct fork job, and rejects skipped fork results.

The follow-up repair on 2026-10-04 passed 1,008 offline tests (42 opt-in skips), 56 tests for each of the same
three seeds (1,024 runs per fuzz property and 65,536 stateful calls per seed), and 18 fork tests at block
128756765 with no skips. `V2StakingAllocationRegression.t.sol` compares identical funding and stakes with
different claim frequencies; `V2StakingRemainderBoundary.t.sol` checks stake-set changes, retained personal
fractions, empty-pool re-entry and the exact funding ceiling. `V2IncomeKindCompatibility.t.sol` checks valid
deployments at different addresses, forged getters, every immutable reference, and the old/new testnet factories.
Recorded commands, hashes and logs are in [the repair results](./fuzz/income-2026-10-04-repair/results.json).

```sh
block=$(cast block-number --rpc-url https://rpc.testnet.chain.robinhood.com)
INCOME_KINDS_FORK=true INCOME_COMPAT_FORK=true INCOME_KINDS_FORK_BLOCK="$block" INCOME_COMPAT_FORK_BLOCK="$block" \
  forge test --threads 1 --match-contract 'TestnetV2IncomeKindsForkTest|TestnetV2IncomeCompatibilityForkTest' -vv
```

On 2026-10-03, `TestnetV2EthBridgeForkTest` passed at block 128456854: bridge seeding from the operator's actual
balance, native-launch activation, and a launch-and-buy from a wallet holding only ETH. The public RPC prunes old
state, so both commands need a fresh block.

Relative to the merged #25 base, the existing kinds' creation code is unaffected by the new income kinds. `creditLiquidityFee` and
`HedgeFunV2AllInTreasury._takeProfit` gained the `virtual` keyword, which emits no code.

## Front end

The baseline V2 launch uses kind 0 from #25 and does not require these optional income kinds. A first release
that exposes dividends does require this PR, a separately reviewed upgradeable income-treasury design, frontend
integration and a complete launch/stake/claim/withdraw rehearsal. The current direct-deployment kinds cannot
inherit kind 0's upgradeability through registration alone. The following frontend work is still outstanding.

- Launch form: offer the kind, show the ratio, and state that the choice is permanent. Explain which kinds run
  the stock strategy and which only distribute income or buy back tokens.
- Token page for an income kind: `staking()`, then on the pool `balanceOf`, `unlockAt`, `earned`, `totalStaked`,
  `periodFinish`; actions `approve` + `stake`, `claim`, `withdraw`. Show that adding to a stake restarts the lock.
- Kinds without a strategy: `totalIncomeStock`, `totalDividendStock`, `pendingDividendStock`, `buybackStock`,
  `protectedGraduationStock`. Show principal separately from income.
- Strategy kinds: `principalStock`, `buybackStock`, the lot views kind 0 already has, and the pool's
  `totalFunded` for dividends paid.
- ABIs: `abi/HedgeFunV2StrategyDividend25Treasury.json` (both strategy kinds share it),
  `abi/HedgeFunV2DividendTreasury.json` (both kinds without a strategy share it) and `abi/V2StakingIncome.json`.
