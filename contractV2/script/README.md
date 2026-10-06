# Scripts

Three groups, by the chain a script may touch. A mainnet script imports nothing from `testnet/`.

| Directory | Chain | What is there |
|---|---|---|
| `mainnet/` | Robinhood Chain, **4663** | `DeployV2MainnetCore` deploys the V2 core and refuses every other chain; `VerifyV2MainnetCore`, `HandOverV2Mainnet` and `VerifyV2MainnetHandOver` are in the same file. `RehearseV2Launchpad` runs the same code (`V2MainnetCore`, with `V2MainnetDefaults`) on a local fork, chain 31337, and refuses to broadcast. `RegisterV2SpotPolicy` registers the schema-1 policy kind 2 needs (`VerifyV2SpotPolicy`); `ListV2MainnetStocks` lists the stocks of `deploy/mainnet-v2-listings.json` at the release's opening rule (`VerifyV2MainnetListings`). Both are owner operations bound to this chain. |
| `testnet/` | Robinhood testnet, **46630** | Every script bound to the testnet and its stand-ins: the test tokens, feeds, market and oracles (`Testnet*.sol`), the deployments built on them, the journeys and demos, and `ConfigureV2LaunchFees`. Each one checks the chain ID and refuses another. |
| this directory | whichever chain the factory is on | Owner operations that take the factory from the environment: `RegisterV2*` (strategy kinds and policies), `SetV2KeeperReward`, `ActivateV2NativeLaunch`, and the listing check `CheckV2Listings`. `helpers/` holds the guards the registrations share. They broadcast as the factory owner. |

Start from [docs/V2_DEPLOYMENT_REHEARSAL.md](../docs/V2_DEPLOYMENT_REHEARSAL.md) for mainnet and
[docs/TESTNET_V2.md](../docs/TESTNET_V2.md) for the testnet.

## What the mainnet core does and does not do

`DeployV2MainnetCore` sends seven transactions: the treasury registry (which creates kind 0 and the upgrade
controller), the token deployer, the curve deployer, the hook at a mined address, the factory, the trade router
and the native router. The factory is born with public launch closed, nothing listed, and kind 0 only.

It does not register a strategy kind or a policy, list a stock, whitelist a launch router or open public launch.
Those are the factory owner's: the `RegisterV2*` scripts for the kinds, `mainnet/RegisterV2SpotPolicy` for kind 2's
policy, `mainnet/ListV2MainnetStocks` for the listings, `ActivateV2NativeLaunch` for the native router.

## Listing stocks on mainnet

`mainnet/ListV2MainnetStocks` reads `deploy/mainnet-v2-listings.json` (token, oracle, pool, fee tier and gates per
stock; the historical `deploy/v2-listings-plan.json` is not an input). `plan()` is read-only, with `V2_FACTORY`: it
prices every stock off its oracle's live `tryPrice()` with the release rule (`referenceOpenPriceE18`, an opening FDV
of $2,140.38 for the 1e27 supply and the fixed 79.31% sale), checks each pool is the V3 factory's for (USDG, token,
fee) and each oracle prices that token against the pinned USDG feed and calendar, prints the rows and
`EXPECTED_PLAN_HASH`. A stock whose oracle is not healthy is reported and left out, so a closed market lists nothing.
`run()`, with `OPERATOR` (the owner) and that hash, refuses any other plan, sends `factory.list` per row and
`setListingGates` only where the effective gates differ from the plan's, reads everything back and writes
`deploy/mainnet-v2-listings.candidate.json` (unverified by construction: the block and the price each opening came
from). It refuses a factory whose `DEFAULT_SALE_BPS` is not 7931 or whose `DEFAULT_LP_BPS` is not 7000.
`VerifyV2MainnetListings` checks every listed stock against the file and a block's prices, with `PRICE_TOLERANCE_BPS`
for a feed that has since moved. Run `plan()` again after the broadcast: every row must show nothing to send. The
listing check (`CheckV2Listings` through `tools/v2_launch_check.py --factory`) is a separate step before and after.

## Order of operations

1. `RehearseV2Launchpad` on a fork at a recent block, with the real Safes and wrapped native token, in the
   ownership mode you will use. Review the defaults and take their hash from its output.
2. `DeployV2MainnetCore`, then `VerifyV2MainnetCore` against the confirmed chain.
3. Owner setup: the `RegisterV2*` scripts for the kinds to offer, listings, and `ActivateV2NativeLaunch` if a
   launch is to buy with the native currency in one transaction. Each has its own `Verify*`.
4. If the deploying key did the setup: `HandOverV2Mainnet`, the Safe's `acceptOwnership()`, then
   `VerifyV2MainnetHandOver`.
5. The Safe opens public launch.

A strategy kind is permanent once registered and cannot be replaced. Register a kind only when its code is final.

## The whole sequence on a mainnet fork

`test/MainnetV2EndToEndFork.t.sol` runs steps 2 and 3 on a fork of chain 4663 and then uses what they built:
`DeployV2MainnetCore.deploy`, the four `RegisterV2*` scripts in the order above (kinds 1 to 5), a listing of the
real NVDA token, and one launch per kind taken through graduation and every action its strategy has, against the
real NVDA/USDG pool and oracle. A price move is a real swap on that pool plus a mocked report from the NVDA feed;
the file's header lists everything that is simulated. It is skipped unless asked for, and CI does not run it:

```sh
MAINNET_E2E=1 RH_RPC=<archive RPC URL> forge test --mc MainnetV2EndToEndForkTest -vv
```

It forks block 81,045,655 (2026-10-05, US session); `MAINNET_E2E_BLOCK` overrides that, and another block's pool
depth and prices may not fit the scenarios. It registers the spot engine's policy (`V2RebalancePolicy`) with the
owner's direct `registerPolicy` call; `mainnet/RegisterV2SpotPolicy` makes the same call.

`test/MainnetV2ListingsFork.t.sol` runs the two listing-step scripts the same way: the core, kinds 1 to 5 and the
policy from `RegisterV2SpotPolicy`, then `ListV2MainnetStocks.plan()` and `run()` from the committed plan file
through an invoker at the operator's address, `VerifyV2MainnetListings` on every listing, and one launch each on
NVDA (kind 2) and SPY (kind 0, one of the oracles of 2026-10-05) through graduation on the real pools:

```sh
MAINNET_E2E=1 RH_RPC=<archive RPC URL> forge test --mc MainnetV2ListingsForkTest -vv
```

It forks block 81,125,000 (the same session, after the five new oracles were verified at 81,124,188; they do not
exist at the end-to-end suite's block). On a block with the market closed every stock is left out of the plan and
the suite fails on purpose.
