# V2 release runbook: testnet redeploy, mainnet deployment, front-end hand-off

The ordered procedure for the release on `main` as of 2026-10-05, for both chains. It says what each step runs, what
it must read back, and what gets recorded. The older documents stay as history and background:
[V2_DEPLOYMENT_REHEARSAL.md](./V2_DEPLOYMENT_REHEARSAL.md) (the mainnet rehearsal and the listing check's first
runs), [TESTNET_V2.md](./TESTNET_V2.md) (the testnet venue and its test doubles),
[TESTNET_V2_FEE_UPGRADE.md](./TESTNET_V2_FEE_UPGRADE.md) (the deployment path the release reuses) and
[../script/README.md](../script/README.md) (what each script does).

## What this release is

| | Decision | Where it lives |
|---|---|---|
| V4 buy fee | taken in stock in `beforeSwap`; nothing accrues in the strategy token; one permissionless `sweep` pays every fee; no owner conversion | `HedgeFunV2Hook` version **3**, flags `0x28CC` |
| Sale share | **79.31%** of supply sold on the curve, fixed when the curve deployer is constructed; `setCurveConfig` refuses any other; the creator chooses only the opening window | `CurveDeployer.DEFAULT_SALE_BPS`, `V2MainnetDefaults.SALE_BPS` |
| LP share of a raise | **70%** to the locked pool, 30% to the treasury, by default; owner may set per stock for future launches | `V2TreasuryDeployer.DEFAULT_LP_BPS`, `setLpBps` |
| Pool LP fee | **0.20%**, owner-settable 0.0001%–0.30% for future launches, frozen per pool | `Defaults.lpFee` |
| Tax | 1%–15%, the creator's; protocol 20% of it, creator up to 10%, treasury the rest | `Defaults` |
| Keeper reward | **0.1%** | `Defaults.bountyBps` |
| Launch fee | 0.0005 ETH, native | `Defaults.launchFeeCurrency/Amount` |
| Engine cooldown floor | 60 seconds (kinds 2 and 3) | `SpotEngineConfig`, `TradablePercentEngineConfig` |
| Strategy kinds | 0 ordinary lots, 1 buy-back, 2 spot engine (schema 1), 3 rebalance (schema 3), 4 percentage buy-back, 5 cycle; all owner-upgradeable through the two-day controller | registry |
| Opening price rule | each listing's `openPriceE18` is set so that the opening FDV is **$2,140.38**: then 79.31% sold raises about **$8,205** and graduates near a **$50,000** FDV | `DeployV2Testnet.referenceOpenPriceE18`, `CalibrateV2Listings` |

Everything above is on `main`; none of it is on a chain yet. The testnet release factory
`0x7BbaAb5d1426650FaaAEB0214D5a045A80FD2621` runs the version-2 hook, a creator-chosen sale share and a 0.30% LP fee,
and must be replaced.

Defaults hash: take it from the rehearsal's output on the release commit. The recorded `0x598daa6f…e506fe` belongs to
the 0.30% LP fee and is no longer valid.

## A. Testnet: redeploy the core

Chain 46630, RPC `https://rpc.testnet.chain.robinhood.com`, deployer `0x36437b878415EdA1a24186CF79AFffBc9ecEd298`
(`cast wallet` account `deployer`). The venue (test stocks, feeds, market, V3 pools) is reused; nothing of it changes.

1. **Build from the release commit** and run the suite: `forge test --gas-limit 4000000000` (local Foundry 1.8.4;
   CI pins 1.5.0). Expect 0 failures.
2. **Deploy the core**: `script/testnet/DeployV2ReleaseTestnet.s.sol:DeployV2ReleaseTestnet`, `--account deployer
   --broadcast`, with `GIT_COMMIT=<commit>`. Forty transactions: registry (kind 0), deployers, hook, factory, routers,
   kinds 1 and 2 with the schema-1 policy, the eight listings copied from the base venue, public launch open. It
   writes `deploy/testnet-v2-release.candidate.json`, which is unverified by construction.
3. **Append kinds 3, 4, 5**, each with `OPERATOR=<deployer> V2_FACTORY=<new factory>`: `RegisterV2TradablePercent`
   (kind 3 and the schema-3 policy), `RegisterV2PercentBuyback` (kind 4), `RegisterV2UpgradeableCycle` (kind 5), in
   that order so the ids come out as on the previous release. Run each one's `Verify*` afterwards. These scripts pin
   the reviewed registry template and refuse a registry built from other source.
4. **Keeper reward**: read `getDefaults().bountyBps`; if it is not 10, `SetV2KeeperReward` with
   `KEEPER_REWARD_BPS=10 EXPECTED_CHAIN_ID=46630` and the defaults hash it asks for, then `VerifyV2KeeperReward`.
5. **Calibrate the listings**: the deployment copies the base venue's opening prices (about a $10,000 opening FDV,
   a $38,000 raise). `CalibrateV2Listings` brings each stock to the release rule. `plan()` first, read-only, with
   `V2_FACTORY OPERATOR TESTNET_MARKET=0xc1AF2f52980F8A7AA4E90A8E30D5c3FaF0375f21`; review the rows and the printed
   `EXPECTED_PLAN_HASH`; then `run()` with that hash, `--account deployer --broadcast`; then `plan()` again and expect
   every row to show nothing to change. The deployment copies the base venue's LP share (5000) as well as its
   opening prices, so the calibration moves both: opening price to the reference, `lpBps` to 7000.
6. **Read back and record**, with `python3 tools/verify_testnet_release.py`: it checks every transaction of the six
   broadcasts against its canonical receipt, reads the live state back at one block, and writes the book only when
   everything matches. Verify roles, defaults (and their hash), the six kinds' stored creation code, the nine
   runtime codes, both policies, the eight listings (opening price equal to the reference formula, `lpBps` 7000),
   `hook.version() == 3`, `curveDeployer.DEFAULT_SALE_BPS() == 7931`, `treasuryDeployer.DEFAULT_LP_BPS() == 7000`,
   `getDefaults().lpFee == 2000`. Write `deploy/testnet-v2-release.json` with every transaction hash and the
   readback block. The previous book is the template.
7. **Lifecycle on the new factory**: `TestnetV2ReleaseKindsForkTest`, `TestnetV2TreasuryUpgradeForkTest`,
   `TestnetV2TradablePercentForkTest` with `V2_FACTORY=<new factory>` on a fresh fork block. Eight tests, all kinds.
8. **CI**: point `V2_FACTORY` in `.github/workflows/contract-v2.yml` at the new factory. The deployed-core fork job
   has been red since the hook changed and goes green here.
9. **Front end**: see section D.

## B. Mainnet: deployment

Chain 4663. Roles: owner Safe and protocol Safe (`0x2910117dd2cB431173Ae9Fb6eAF30726321d1693` is the V1 record;
confirm threshold ≥ 2 and intended control before use), calendar `0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5`,
WETH `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`. The deployer sets up and hands over (`DEPLOYER_SETS_UP=true`),
as decided.

1. **Rehearse on a fork** of a recent block with `--chain-id 31337`: `RehearseV2Launchpad` with `OWNER PROTOCOL
   CALENDAR WETH DEPLOYER_SETS_UP=true`. It deploys the same core, registers kind 1 in simulation, reads back the
   fixed sale share (refusing six other values) and prints the **defaults hash** and the sale share. Record both.
   Both ownership modes passed on a fork taken 2026-10-05 (about 52.6M gas including the simulated kind-1
   registration).
2. **Run the end-to-end fork suite** on the release commit: `MAINNET_E2E=1 RH_RPC=<archive RPC> forge test --mc
   MainnetV2EndToEndForkTest`. Nine tests: the production deployment, the four registration scripts, a real NVDA
   listing, and one launch per kind through graduation and every strategy action against the real pool and oracle.
   It passed on the release's hook, sale share, LP default, 0.20% LP fee and 60-second floor.
3. **Deploy the core**: `DeployV2MainnetCore` with `OWNER PROTOCOL WETH DEPLOYER_SETS_UP=true
   EXPECTED_DEFAULTS_HASH=<from step 1> EXPECTED_SALE_BPS=7931 GIT_COMMIT=<commit>`, `--account deployer
   --broadcast`. Seven transactions, about 0.002 ETH at the gas prices seen. The readback refuses a curve deployer
   whose sale share or a registry whose LP default differ from the defaults file. Then `VerifyV2MainnetCore` with
   `FIRST_OWNER=<deployer>` and the same expectations.
4. **Register the kinds**, as owner, with `OPERATOR=<deployer> V2_FACTORY=<factory>`: `RegisterV2UpgradeableKinds`
   (kinds 1 and 2), `RegisterV2TradablePercent` (kind 3 and its policy), `RegisterV2PercentBuyback` (kind 4),
   `RegisterV2UpgradeableCycle` (kind 5); each `Verify*`. **Kind 2 also needs a schema-1 policy** (`V2RebalancePolicy`
   registered with `registerPolicy`); no mainnet script does this yet, the testnet deployment and the end-to-end test
   make the owner call directly. Without it kind 2 cannot be launched.
5. **List the stocks** (section C). No script exists yet; until one does, each listing is an owner `factory.list` plus,
   on 0.05% pools, `setListingGates` for the chunk, prepared and checked as section C says.
6. **Native launch**: `ActivateV2NativeLaunch` with `WETH WETH_USDG_POOL=0x52e65B17fB6E5BA00Ed806f37Afcd2DaA50271Ca
   LAUNCH_FEE_WEI=500000000000000 LAUNCH_ROUTER=<native router>`, then its `Verify*`. ETH-paired launches are v2.1
   (PR #41) and not part of this release.
7. **Hand over**: `HandOverV2Mainnet`, the Safe's `acceptOwnership()`, `VerifyV2MainnetHandOver`.
8. **Open**: the Safe sets `publicLaunch` true after one complete stock-specific fork replay has been reviewed and
   the front end points at the mainnet factory.
9. **Record** the mainnet address book (addresses, transactions, defaults hash, code hashes, kinds, policies,
   listings) in `deploy/`, as the testnet book does.

## C. Listing a stock

Inputs per stock: token, `PriceOracle`, stock/USDG V3 pool, `openPriceE18`, gates.

- **Oracles.** The eighteen V1 listings' oracles (`deploy/v2-listings-plan.json`) are the same contract the release
  uses and are reused as they are. Five more were deployed on 2026-10-05 for stocks V1 never listed:
  [`deploy/mainnet-v2-oracles.json`](../deploy/mainnet-v2-oracles.json) (SGOV, SPY, DELL, PLTR, SLV).
- **Opening price.** `openPriceE18 = floor(openingFdv * 1e18 / (price * 1e9))` with `openingFdv = 50_000e18 *
  2069^2 / 1e8` (= $2,140.3805) and `price` the oracle's **live** `tryPrice()` in USDG per stock, 18 decimals. This is
  `DeployV2Testnet.referenceOpenPriceE18`. A closed market or a stale feed is a reason to wait, not to use
  `lastPriceAt`. The price drifts with the stock afterwards; re-list to recalibrate (future launches only).
- **LP share.** 70% by default; `setLpBps(stock, …)` only to deviate.
- **Gates.** `maxDeviationBps` 50 (125 on 1% pools), `maxSlippageBps` 100, `sellChunkUsdg` 2,000 USDG, or on a
  0.05% pool at most the `max chunk` the listing check prints.
- **The check, before every listing and again before a first launch:** `python3 tools/v2_launch_check.py --factory
  <factory> --stock <T>` on a fork at a recent block, which reads the fixed 79.31% from the deployer. Do not run it
  without `--factory`: the plan file is the historical 44% plan, pinned by tests, and judges a raise a fifth of the
  real one. Run it on a market day: the oracle must be healthy.
- **Day-one set.** At block 81,045,661 (2026-10-05, US session), with the release rule, 18 of 24 candidates passed:
  NVDA, SPCX, CRCL, GOOGL, AMZN, GME (0.05% pool), META, MSTR, MU, AAPL, QQQ, MSFT, TSLA, USO, GLD, SGOV, SPY,
  DELL. PLTR and SLV missed the deviation gate by a few basis points; INTC and AMD by more; USAR and TSM have pools
  too thin for the raise. One block's numbers: re-run before listing.
- **Treasury venue.** A listing's pool is where the treasury trades and what its health gate reads. A deep pool
  against another asset (TSM/SPY on V4, for example) does not help: the factory requires a stock/USDG V3 pool, and
  the treasuries trade only there.

## D. Front-end hand-off

The site reads one address book per deployment and verifies it against the chain. After step A.6 regenerate it
(`npm run publish:testnet-release-book` in the site repository) from the new `deploy/testnet-v2-release.json`; after
B.9, the same for mainnet. What changed for the site in this release, beyond addresses:

1. **Sale share is the contract's.** No raise-size input; `DEFAULT_SALE_BPS()` read from the curve deployer; a
   `setCurveConfig` only when the creator picks a non-default window, carrying that share. (Done in the testnet
   PR of 2026-10-05.)
2. **Graduation target** shown from live values: listing `openPriceE18`, the share, supply, `lpBps(stock)`, the
   oracle price. Owner-settable listing values are read live, never pinned.
3. **Engine strategies** (kinds 2, 3): cooldown floor is 60 seconds, not 600; defaults may stay at 600.
4. **Fees shown to a buyer**: tax (creator's, 1%–15%) plus the pool's LP fee 0.20% on a graduated pool, both in
   stock; total about 1.2% at the minimum tax. The buy fee is taken before the swap, so a quote must come from a
   simulation of the actual route, not from the pool price alone.
5. **Hook version 3**: no `pendingTokenFees`, no `convertFees`; any owner-conversion UI from the fee factories does
   not apply to this core. `Taxed.moved` is the stock the swap moved, on both buy types.
6. **Exact-input V4 buys fill or revert**: a buy stopped by a price limit reverts (`PartialFillRefused`, wrapped by
   v4). Our router uses minimum output, which still works; third-party routers using price limits do not.
7. **Mainnet addresses** are distinct from testnet's even where they coincide (the deployer's early nonces produce
   the same addresses on both chains; `0x7BbaAb5d…` is the testnet factory and the mainnet SLV oracle).

## E. Open items before mainnet

- No mainnet listing script; no mainnet script for kind 2's policy (B.4, B.5).
- `tools/v2_launch_check.py` without `--factory` still judges at 44%; the historical plan is kept on purpose.
- `test/V2LiveVenueFork.t.sol` (GME on a mainnet fork) has stale assertions and does not pass; the end-to-end suite
  supersedes it.
- CI's deployed-core fork job is red until A.8.
- The hook's `version()` stayed 3 through PR #43's follow-up; books distinguish cores by feature version.
