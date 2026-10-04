> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Production addresses — Robinhood Chain (4663)

The one page to copy addresses from. Everything here was read back on chain after it landed; the record the emergency
kit reads is [`emergency/addresses.json`](../emergency/addresses.json), and the listing parameters come from
[`deploy/first-batch-2026-09-22.json`](../deploy/first-batch-2026-09-22.json). **Do not use any sandbox address**
(the sandbox hook is `0x45783cf9…E844`; see [SANDBOX.md](./SANDBOX.md)).

State on 2026-09-22: twelve stocks listed, public launch opened (`publicLaunch = true`, Safe nonce 8); launch fee 5 USDG.
State on 2026-09-24: eighteen stocks listed -- AAPL, QQQ, MSFT, TSLA, USO and GLD added at block 71,689,915 (Safe nonces 9 and 10, from
[`deploy/second-batch-2026-09-24.json`](../deploy/second-batch-2026-09-24.json)).

## Owner

| role | address |
|---|---|
| Factory owner, protocol fee recipient, calendar owner | `0x2910117dd2cB431173Ae9Fb6eAF30726321d1693` — Safe 1.4.1, 3-of-4 |

## Launchpad contracts

Deployed from commit `3dc07eb`; all verified on Sourcify (creation and runtime `match`).

| contract | address | deployed |
|---|---|---|
| `HedgeFunFactory` | `0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961` | block 69,454,565 |
| `HedgeFunHook` (the one hook every strategy pool uses) | `0x2A16d0973385952cFBE750D37f803d0958472844` | block 69,454,565 |
| `TradingCalendar` | `0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5` | block 69,454,565 |
| `HedgeFunLaunchRouter` (vouched: `launchers = true`) | `0x470F5DeB0897118F6575F72183781C6a0610E1FA` | block 69,454,565 |
| `HedgeFunTradeRouter` (buy / sell with USDG) | `0xb281F7D91325A3A386A00cA0F6010BC8B1491c8C` | tx `0x015f0524…b16e` |
| `TreasuryDeployer` | `0x05BC7875a7d61C3bbA2D7737D40C81aF5fD10DBE` | block 69,454,565 |
| `TokenDeployer` | `0x9C0440dCc1b651C4707aa44E0eA083Fa4E0E8A6b` | block 69,454,565 |

### Created per launch

Every launch creates a new token and a new treasury, from the same code, through the two deployers above. They are not
singletons, so no single address stands for them; read a strategy's from `factory.strategies(id)`. The addresses below
are strategy 0's, as a verified example of each.

| contract | source | created by | example (strategy 0, CRCLGRID) |
|---|---|---|---|
| `HedgeFunToken` | `src/HedgeFunToken.sol` | `TokenDeployer`, CREATE2 | `0xF5501c0D85992dD59371e15e3e7b60654ebaF332` |
| `HedgeFunTreasury` (inherits `HedgeFunTreasuryBase` and `PoolTrader`) | `src/HedgeFunTreasury.sol`, `src/HedgeFunTreasuryBase.sol`, `src/PoolTrader.sol` | `TreasuryDeployer`, CREATE2 | `0xc21873529515990C80BACe0931141e6B9D5A4fe0` |
| `PriceOracle` | `src/PriceOracle.sol` | the operator, one per listed stock (not per launch) | the twelve in [Listed stocks](#listed-stocks) |

Both examples are Sourcify `match`. Every token has the same bytecode apart from its constructor arguments
(name, symbol, supply, factory, creator), and every treasury the same apart from its own; a verified one lets an
explorer match the rest.

### Where each source file lives on chain

Every V1 file under `src/` is in the deployed code (`src/v2/` is V2, merged but not deployed); the ones with no address of their own are compiled into the
contracts that use them, and published with those contracts' verified source.

| file | on chain as |
|---|---|
| `HedgeFunFactory.sol` | the factory |
| `hooks/HedgeFunHook.sol` | the hook |
| `TradingCalendar.sol` | the calendar |
| `HedgeFunLaunchRouter.sol`, `HedgeFunTradeRouter.sol` | the two routers |
| `HedgeFunDeployers.sol` | two contracts: `TreasuryDeployer` and `TokenDeployer` |
| `HedgeFunToken.sol` | each strategy's token |
| `HedgeFunTreasury.sol` | each strategy's treasury |
| `HedgeFunTreasuryBase.sol` | no address: the abstract base of `HedgeFunTreasury` (lots, booking, take-profit, dip, buy-back) |
| `PoolTrader.sol` | no address: the base of `HedgeFunTreasury` that prices and swaps against the stock's V3 pool |
| `PriceOracle.sol` | the twelve oracles |
| `libraries/HedgeFunMath.sol`, `libraries/HedgeFunLimits.sol` | no address: inlined into the factory, hook and treasury |
| `libraries/TwapRing.sol` | no address: inlined into the hook |
| `interfaces/*.sol` | no address: declarations only |

## Covered-call desk

| contract | address | deployed |
|---|---|---|
| `CoveredCallDesk` (`src/options/CoveredCallDesk.sol`; owner = the Safe; USDG and the production calendar as immutables) | `0xb28Aa6ADE3f4504B5554dc1BDb23EBa2FE1afD87` | block 77,098,456, tx `0xd73c0dfa…65fda`, 2026-10-01 |

Deployed by `script/DeployCoveredCallDesk.s.sol` from the deployer `0x97FB…c48B`, which holds no role. Until the Safe
signs the setup batch (`tools/cc_desk_batch.py setup`: `list`, `setWriter`, `setBuyer`) nothing is listed and nobody may
offer or fill. The weekly runbook is in [COVERED_CALL_DESK.md](./COVERED_CALL_DESK.md).

## Strategies

Not listed here: since `setPublicLaunch(true)` anyone can launch, so the only complete index is the chain. Read
`factory.strategyCount()` and `factory.strategies(i)` -> `(token, treasury, hook, stock, creator)`, or follow the
factory's `Launched(id, symbol, token, treasury, hook, stock, creator)` events from block 69,454,565; a strategy's
pool id is `hook.poolOfTreasury(treasury)`. `tools/dashboard.py` and `emergency/build.py status` both enumerate this way.

One strategy is named here only because it is the pool given to Uniswap's routing review: id 0, CRCLGRID, launched by
the Safe, pool id `0xfe98797b4dc2e5008712f812f3d90acba5adb216f8aa32e412fa377fb90b0b64`.

## Listed stocks

Oracles deployed at block 69,486,810 (`PriceOracle`, production calendar, `maxStockAge = maxUsdgAge = 26 h`), all
Sourcify `match`. Open price is stock per strategy token (1e18), set to about **$10k opening FDV** at 2026-09-22
prices; it is fixed in stock units, so the dollar figure moves with the stock. Band ceiling is bps per hour of closure;
0 means the stock's strategies follow Chainlink only and sleep through closures. Gates are `maxDeviationBps /
maxSlippageBps`; the sell chunk is in USDG.

| stock | token | `PriceOracle` | V3 `<stock>/USDG` pool | fee | Chainlink feed | `openPriceE18` | band ceiling | gates | sell chunk |
|---|---|---|---|---|---|---|---|---|---|
| NVDA | `0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC` | `0x03c77f527Aa1B0B304602e3fB9Ac994dd1c157f8` | `0xD4EB21209c4d6093F80B5b84f5C45cC093eA14A3` | 0.05% | `0x379EC4f7C378F34a1B47E4F3cbeBCbAC3E8E9F15` | 44200000000 | 0 | default (50 / 100) | default (2,000) |
| SPCX | `0x4a0E65A3EcceC6dBe60AE065F2e7bb85Fae35eEa` | `0xC109426706b9D01719ED82e8cd027fA91fBcdC0b` | `0xc61284332117c3fB23A2a56ccEfFD07F7aF60029` | 0.05% | `0xB265810950ba6c5C0Ff821c9963014a56fD8Bffb` | 65600000000 | 0 | default (50 / 100) | default (2,000) |
| CRCL | `0xdF0992E440dD0be65BD8439b609d6D4366bf1CB5` | `0x3bd2c093948D38A5eC2D945C5b065e5Db89aaB36` | `0x654E4143e82a5824445Ade0824351C2A9ACD95a8` | 0.30% | `0x6652eDf64bA3731C4F2D3ce821A0Fb1f1f6b482a` | 109000000000 | 10 | default (50 / 100) | default (2,000) |
| GOOGL | `0x2e0847E8910a9732eB3fb1bb4b70a580ADAD4FE3` | `0x15400359B0D14B4151FAe80b837abF3fA1977256` | `0x34D0dC122CF9A8Eb296fC5e0D3A233625D7d19b7` | 0.05% | `0xF6f373a037c30F0e5010d854385cA89185AE638b` | 28000000000 | 0 | default (50 / 100) | default (2,000) |
| AMZN | `0x12f190a9F9d7D37a250758b26824B97CE941bF54` | `0xb34d278D2c792B7C48252C5eB8130Db45e35294e` | `0x8AC92DA74AB5F3b1d024Dc1943Ad7e15Dc4179Ef` | 0.30% | `0xD5a1508ceD74c084eBf3cBe853e2C968fB2a651C` | 38500000000 | 5 | default (50 / 100) | default (2,000) |
| GME | `0x1b0E319c6A659F002271B69dB8A7df2F911c153E` | `0x7548A343D06E45507Dd8F546D9d9Fdf684575ecE` | `0xE2b46c905E12Ab8E2f864e4821a4325884C1B126` | 0.05% | `0x27C71df6A64fB476468EdF256CF72c038baB5B67` | 423000000000 | 5 | default (50 / 100) | default (2,000) |
| META | `0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35` | `0x699E34068b8975bE113eD5fF12e429c69BCf1011` | `0x107a7Cb40d8665360ba10E59471Af06150A50922` | 0.30% | `0x7C38C00C30BEe9378381E7B6135d7283356D71b1` | 13400000000 | 5 | default (50 / 100) | default (2,000) |
| USAR | `0xd917B029C761D264c6A312BBbcDA868658eF86a6` | `0x02dE419166CED89fc9FCe2687CdBcBbc9eDe2612` | `0x04391780F519B7d3ba59c9590459D76e23d225C4` | 0.30% | `0xA994d3684e8400A6c8078226925779FdeE682DD9` | 596000000000 | 5 | default (50 / 100) | 1,000 |
| MSTR | `0xec262a75e413fAfD0dF80480274532C79D42da09` | `0x19d0328F3152d1361db7B3Dd7708Cc36A779d612` | `0x17578C0e0D15da44f31677263114F71aE76653EA` | 1.00% | `0x396118bdFB181e6240E74D243F266B061c0edc3D` | 61100000000 | 0 | 125 / 175 | default (2,000) |
| AMD | `0x86923f96303D656E4aa86D9d42D1e57ad2023fdC` | `0xc809bDf7E31E4830de2b03e6f809869Fb99f2246` | `0x48D284A2A4d3DC1b3Da08231Fe44317e7e7Aa51f` | 0.30% | `0x943A29E7ae51A4798823ca9eEd2ed533B2A22C72` | 16300000000 | 0 | default (50 / 100) | 1,000 |
| MU | `0xfF080c8ce2E5feadaCa0Da81314Ae59D232d4afD` | `0x4D15A4A1028f001800774A3d2DC31d77945399a4` | `0xd057B1Bc54917855BBee58eAd58647f47caB35E5` | 0.30% | `0x425EEFdCf05ed6526C3cE61Af99429A228a6d596` | 9620000000 | 0 | default (50 / 100) | default (2,000) |
| INTC | `0xc72b96e0E48ecd4DC75E1e45396e26300BC39681` | `0xd399113f3196044A001614Ca9dda9cD8c9424264` | `0x2e5a92f5013a64661A49312111be2e8aBd33F56a` | 0.30% | `0x3f390C5C24628Ac7C489515402235FeAD71D1913` | 82700000000 | 0 | default (50 / 100) | 1,000 |
| AAPL | `0xaF3D76f1834A1d425780943C99Ea8A608f8a93f9` | `0x8fe64bCD251f35750a98d3f1E089a383399e10d4` | `0xAae0d815EE56e4092a5E5C2911E676Fea50B2d6D` | 0.05% | `0x6B22A786bAa607d76728168703a39Ea9C99f2cD0` | 29800000000 | 0 | default (50 / 100) | default (2,000) |
| QQQ | `0xD5f3879160bc7c32ebb4dC785F8a4F505888de68` | `0x8d4bE55bD1B4ded24065c3891239D9084B659055` | `0xD60A5d14dB690B7Afad71F76B108071D7175597d` | 0.05% | `0x80901d846d5D7B030F26B480776EE3b29374C2ae` | 13500000000 | 0 | default (50 / 100) | default (2,000) |
| MSFT | `0xe93237C50D904957Cf27E7B1133b510C669c2e74` | `0xB7634eE6ac2eeD7Ed85D2f927eB483eFC9e9215b` | `0xeb60bCD1D920ad6E102690CCFC6fB488899E1510` | 0.30% | `0x45C3C877C15E6BA2EBB19eA114Ea508d14C1Af2E` | 20000000000 | 0 | default (50 / 100) | default (2,000) |
| TSLA | `0x322F0929c4625eD5bAd873c95208D54E1c003b2d` | `0xe7bca6Aa83560CFD8f1aC3b8e27Eb4Ba9661F62C` | `0xf4ACdAEEB7022862A763C9B1B885e11191c889E3` | 0.30% | `0x4A1166a659A55625345e9515b32adECea5547C38` | 26500000000 | 0 | default (50 / 100) | default (2,000) |
| USO | `0xa30FA36Db767ad9eD3f7a60fC79526fB4d56D344` | `0xBD130A4A18dBedFc69592FC3bfd474094354db32` | `0x02175608F1b5E6b5ed221cCFdC7Be197D111D915` | 0.30% | `0x75a9c76Ef439e2C7c2E5a34Ab105EcFe3766431c` | 68000000000 | 0 | default (50 / 100) | default (2,000) |
| GLD | `0xC9a981FEE1F9DEc688bb123ccDeCc63D0deBFC4e` | `0x32a2E01E7DffDDdE29112531aE20340100f9DBe5` | `0xBA2f1ed4cEB2169D538d1e614D847E83C5A55913` | 0.05% | `0x470A51258068043bd43dC0a56245625C9fE86eB0` | 25400000000 | 0 | default (50 / 100) | default (2,000) |

The six added on 2026-09-24 have their `PriceOracle` created by the Safe through Safe's CreateCall
(`0x9b35Af71d77eaf8d7e40252370304687390A1A52`, `performCreate2`), in the same block as their listing. Sourcify shows
runtime `match` for each; it records no creation match, because the creation is an internal call of CreateCall rather
than a transaction of its own. The code is byte-identical to the first batch's oracles (immutables aside), which
`tools/oracle_batch.py` checked before the batch was built. GLD's feed answers `GLD / USD`; it is the ETF share price.

MSTR's 1% pool and wider gates mean its strategies need take-profit and dip of at least **5.5%**
(`2 × (slippage + pool fee)`); on the other stocks the floor is 2.1% (0.05% pools) or 2.6% (0.30% pools).

## Chain dependencies

| | address |
|---|---|
| Uniswap V4 `PoolManager` | `0x8366a39CC670B4001A1121B8F6A443A643e40951` |
| Uniswap V3 factory | `0x1f7d7550B1b028f7571E69A784071F0205FD2EfA` |
| USDG (6 decimals) | `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168` |
| Chainlink USDG / USD | `0x61B7e5650328764B076A108EFF5fa7282a1B9aD2` |
