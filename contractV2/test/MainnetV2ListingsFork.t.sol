// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";
import {HedgeFunToken} from "../src/HedgeFunToken.sol";
import {HedgeFunBondingCurve as Curve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {CurveDeployer} from "../src/v2/CurveDeployer.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {HedgeFunV2EngineTreasuryCore} from "../src/v2/HedgeFunV2EngineTreasury.sol";
import {HedgeFunV2TradeRouter as Router} from "../src/v2/HedgeFunV2TradeRouter.sol";
import {EngineConfig, StrategyAction} from "../src/v2/strategy/IStrategyPolicy.sol";
import {V2MainnetCore} from "../script/mainnet/V2MainnetCore.sol";
import {V2MainnetDefaults} from "../script/mainnet/V2MainnetDefaults.sol";
import {DeployV2MainnetCore} from "../script/mainnet/DeployV2MainnetCore.s.sol";
import {RegisterV2SpotPolicy} from "../script/mainnet/RegisterV2SpotPolicy.s.sol";
import {V2MainnetListingPlan, ListV2MainnetStocks, VerifyV2MainnetListings} from "../script/mainnet/ListV2MainnetStocks.s.sol";
import {RegisterV2UpgradeableKinds} from "../script/RegisterV2UpgradeableKinds.s.sol";
import {RegisterV2TradablePercent} from "../script/RegisterV2TradablePercent.s.sol";
import {RegisterV2PercentBuyback} from "../script/RegisterV2PercentBuyback.s.sol";
import {RegisterV2UpgradeableCycle} from "../script/RegisterV2UpgradeableCycle.s.sol";

/// Stands at the operator's address, so that `run()` sees the operator as its caller, as `forge script --sender` would.
contract ListingInvoker {
    function run(ListV2MainnetStocks script) external returns (ListV2MainnetStocks.Row[] memory) {
        return script.run();
    }
}

/// The mainnet listing scripts on a fork of Robinhood Chain (4663): the core deployed by `DeployV2MainnetCore.deploy`,
/// kinds 1 to 5 by their production scripts and the spot engine's policy by `RegisterV2SpotPolicy`, then
/// `ListV2MainnetStocks.plan()` and `run()` from the committed plan file through an invoker at the operator's address,
/// `VerifyV2MainnetListings` on the result, and one launch each on two of the listings taken through graduation:
/// a kind-2 spot engine on NVDA (a V1 oracle) and a kind-0 strategy on SPY (one of the oracles of 2026-10-05).
///
/// REAL: the chain's tokens, oracles, feeds, calendar, V3 pools, USDG and the V4 PoolManager; the core, the kinds,
/// the policy and every listing, from this repository's own mainnet scripts; every launch, curve buy, graduation and
/// strategy action. SIMULATED: accounts funded by impersonated USDG transfers out of the WETH/USDG pool; the
/// deploying key is a test address that has the invoker's code; time moves with `vm.warp`.
///
/// Skipped unless asked for; CI does not run it (it needs an archive RPC). Nothing is broadcast.
///   MAINNET_E2E=1 RH_RPC=<archive RPC URL> forge test --mc MainnetV2ListingsForkTest -vv
/// The pinned block is on 2026-10-05, in the session, after the five new oracles were verified (block 81,124,188):
/// the end-to-end suite's 81,045,655 is before they were deployed. MAINNET_E2E_BLOCK overrides it; on another
/// block a closed market leaves every stock out of the plan, and this suite then fails on purpose.
contract MainnetV2ListingsForkTest is Test {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    uint256 internal constant PINNED_BLOCK = 81_125_000;
    IPoolManager internal constant PM = IPoolManager(0x8366a39CC670B4001A1121B8F6A443A643e40951);
    address internal constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address internal constant WETH = 0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73;
    address internal constant SAFE = 0x2910117dd2cB431173Ae9Fb6eAF30726321d1693;
    address internal constant USDG_SOURCE = 0x52e65B17fB6E5BA00Ed806f37Afcd2DaA50271Ca; // WETH/USDG pool, funding only
    address internal constant DEPLOYER = address(0xD3910E);
    address internal constant CREATOR = address(0xC4EA704);
    address internal constant ALICE = address(0xA11);
    address internal constant BOB = address(0xB0B);
    address internal constant KEEPER = address(0xB07);
    uint256 internal constant SCALE = 1e30;
    bytes32 internal constant DEPENDENCIES = keccak256("mainnet-listings-fork: policy dependencies");
    bytes32 internal constant AUDIT = keccak256("mainnet-listings-fork: policy audit manifest");

    HedgeFunV2Factory internal factory;
    V2TreasuryDeployer internal registry;
    CurveDeployer internal curveDeployer;
    Router internal router;
    ListV2MainnetStocks internal lister;
    VerifyV2MainnetListings internal verifier;
    V2MainnetListingPlan.Entry[] internal entries;
    ListV2MainnetStocks.Row[] internal rows;
    uint8 internal engineKind;
    bytes32 internal spotPolicyKey;

    // the launch under test
    V2MainnetListingPlan.Entry internal listing;
    uint256 internal openPriceE18;
    uint256 internal price;
    HedgeFunToken internal token;
    Curve internal curve;
    HedgeFunV2Treasury internal treasury;
    PoolKey internal key;
    uint256 internal id;

    function setUp() public {
        vm.skip(vm.envOr("MAINNET_E2E", uint256(0)) == 0, "mainnet fork: set MAINNET_E2E=1 and RH_RPC (archive)");
        uint256 forkBlock = vm.envOr("MAINNET_E2E_BLOCK", PINNED_BLOCK);
        vm.createSelectFork(vm.envString("RH_RPC"), forkBlock);
        assertEq(block.chainid, 4663, "Robinhood Chain mainnet only");
        emit log_named_uint("fork block", forkBlock);
        emit log_named_uint("fork time", block.timestamp);
        _deployCore();
        _registerKindsAndPolicy();
        _listTheDayOneSet();
    }

    // ---------------------------------------------------------------------------------- production deployment
    function _deployCore() private {
        bytes32 defaultsHash = keccak256(abi.encode(V2MainnetDefaults.release()));
        V2MainnetCore.Deployed memory x = new DeployV2MainnetCore().deploy(
            DEPLOYER, V2MainnetCore.Roles(SAFE, SAFE, WETH), true, defaultsHash, 7931, 0
        );
        factory = x.factory;
        registry = x.treasury;
        curveDeployer = x.curve;
        router = x.router;
        assertEq(factory.owner(), DEPLOYER);
        assertEq(curveDeployer.DEFAULT_SALE_BPS(), 7931);
        assertEq(registry.DEFAULT_LP_BPS(), 7000);
        assertEq(registry.kindCount(), 1, "the core is born with kind 0 only");
    }

    /// @dev kinds 1 to 5 by the production scripts, in the runbook's order, then the spot engine's policy by its script
    function _registerKindsAndPolicy() private {
        RegisterV2UpgradeableKinds.Kinds memory k = new RegisterV2UpgradeableKinds().register(DEPLOYER, factory);
        engineKind = k.engine;
        RegisterV2TradablePercent.Registration memory rebalance =
            new RegisterV2TradablePercent().register(DEPLOYER, factory, DEPENDENCIES, AUDIT);
        uint8 percentKind = new RegisterV2PercentBuyback().register(DEPLOYER, factory);
        uint8 cycleKind = new RegisterV2UpgradeableCycle().register(DEPLOYER, factory);
        assertEq(k.buyback, 1);
        assertEq(engineKind, 2);
        assertEq(rebalance.kind, 3);
        assertEq(percentKind, 4);
        assertEq(cycleKind, 5);
        RegisterV2SpotPolicy spot = new RegisterV2SpotPolicy();
        RegisterV2SpotPolicy.Registration memory r = spot.register(DEPLOYER, factory, DEPENDENCIES, AUDIT);
        spot.check(factory, r, DEPENDENCIES, AUDIT);
        spotPolicyKey = r.policyKey;
        assertEq(registry.kindCount(), 6);
        assertTrue(registry.policy(spotPolicyKey).enabledForNewLaunches);
    }

    /// @dev `plan()` then `run()` from the committed plan file, as the operator will run them
    function _listTheDayOneSet() private {
        lister = new ListV2MainnetStocks();
        verifier = new VerifyV2MainnetListings();
        V2MainnetListingPlan.Entry[] memory e = lister.parsePlan(vm.readFile(lister.PLAN()));
        for (uint256 i; i < e.length; ++i) entries.push(e[i]);
        assertEq(entries.length, 18);

        vm.setEnv("V2_FACTORY", vm.toString(address(factory)));
        vm.setEnv("OPERATOR", vm.toString(DEPLOYER));
        vm.etch(DEPLOYER, type(ListingInvoker).runtimeCode);
        lister.plan();
        (ListV2MainnetStocks.Row[] memory p, string[] memory skipped) = lister.planFor(factory, e);
        for (uint256 i; i < skipped.length; ++i) emit log_named_string("excluded, oracle not healthy at this block", skipped[i]);
        assertEq(skipped.length, 0, "every day-one oracle is healthy at the pinned block");
        assertEq(p.length, entries.length);

        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(bytes32(uint256(1))));
        vm.expectRevert(abi.encodeWithSelector(ListV2MainnetStocks.PlanChanged.selector, lister.planHash(factory, p)));
        ListingInvoker(DEPLOYER).run(lister);
        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(keccak256(abi.encode(p))));
        vm.expectRevert(abi.encodeWithSelector(ListV2MainnetStocks.PlanChanged.selector, lister.planHash(factory, p)));
        ListingInvoker(DEPLOYER).run(lister); // the rows alone are not the hash: it names where they apply
        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(lister.planHash(factory, p)));
        ListingInvoker(DEPLOYER).run(lister);
        for (uint256 i; i < p.length; ++i) rows.push(p[i]);

        vm.prank(DEPLOYER);
        factory.setPublicLaunch(true);
    }

    // ================================================================================== the listings
    function test_runListedEveryStockOfThePlanAtTheReferenceOpening_andAgainSendsNothing() public {
        uint256 remaining = 10_000 - lister.REFERENCE_SALE_BPS();
        for (uint256 i; i < rows.length; ++i) {
            ListV2MainnetStocks.Row memory r = rows[i];
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(r.e.stock);
            assertTrue(enabled, r.e.symbol);
            assertEq(oracle, r.e.oracle, r.e.symbol);
            assertEq(pool, r.e.pool, r.e.symbol);
            assertEq(open, lister.referenceOpenPriceE18(r.priceE18), r.e.symbol);
            assertTrue(r.list, "nothing was listed before");
            assertEq(r.oldOpenPriceE18, 0);
            assertEq(r.setGates, r.e.fee == 10_000, "only the 1% pools' gates differ from the defaults");
            (bool ok, uint256 live) = PriceOracle(r.e.oracle).tryPrice();
            assertTrue(ok);
            assertEq(live, r.priceE18, "the price the opening came from is the block's");
            uint256 openingFdv = lister.impliedOpeningFdvUsdE18(open, live);
            assertApproxEqRel(openingFdv, 2_140.3805e18, 1e9, r.e.symbol);
            assertApproxEqRel(openingFdv * lister.REFERENCE_SALE_BPS() / remaining, 8_204.6e18, 0.001e18, "the raise");
            assertApproxEqRel(openingFdv * 10_000 * 10_000 / (remaining * remaining), 50_000e18, 0.001e18, "graduation FDV");
            assertEq(registry.lpBps(r.e.stock), 7000);
            emit log_named_string("listed", r.e.symbol);
            emit log_named_decimal_uint("  oracle price, USDG", live, 18);
            emit log_named_uint("  openPriceE18", open);
        }
        verifier.check(factory, entries, 0);

        (ListV2MainnetStocks.Row[] memory again, string[] memory skipped) = lister.planFor(factory, entries);
        assertEq(again.length, rows.length);
        assertEq(skipped.length, 0);
        for (uint256 i; i < again.length; ++i) {
            assertFalse(again[i].list, "already listed exactly so");
            assertFalse(again[i].setGates);
        }
        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(lister.planHash(factory, again)));
        vm.recordLogs();
        ListingInvoker(DEPLOYER).run(lister);
        assertEq(vm.getRecordedLogs().length, 0, "a listed factory is left alone");

        // the stale hash of the first run no longer matches: the rows changed (oldOpenPriceE18, list)
        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(lister.planHash(factory, rows)));
        vm.expectRevert(abi.encodeWithSelector(ListV2MainnetStocks.PlanChanged.selector, lister.planHash(factory, again)));
        ListingInvoker(DEPLOYER).run(lister);
    }

    // ================================================================================== two launches
    /// A spot engine (kind 2, the policy of RegisterV2SpotPolicy) on NVDA: launch at the listed opening, graduate
    /// through the real NVDA pool near the reference raise and FDV, and, where the live pool agrees with the
    /// oracle, the first engine action sells inventory to its 50% target.
    function test_kind2SpotEngineOnNVDA_launchesAtTheListing_graduates_andTheEngineActs() public {
        _select("NVDA");
        _launchEngine("LISTNVDA", engineKind, _spotConfig());
        (, uint256 treasuryStock) = _graduate();
        HedgeFunV2EngineTreasuryCore e = HedgeFunV2EngineTreasuryCore(address(treasury));
        assertEq(e.bookedStock(), treasuryStock, "the graduation stock is inventory");
        assertEq(e.avgCost(), price, "booked at the listing's live oracle price");
        assertEq(e.payoutBps(), 5000);

        (bool healthy, uint256 p) = treasury.health();
        emit log_named_uint("treasury health at the fork block", healthy ? 1 : 0);
        if (healthy) {
            assertEq(p, price);
            (bool due, StrategyAction proposed,) = e.preview();
            assertTrue(due, "all-stock is over the 50% target");
            assertEq(uint256(proposed), uint256(StrategyAction.SellStock));
            uint256 poolUsdg = IERC20(USDG).balanceOf(listing.pool);
            vm.prank(KEEPER);
            (HedgeFunV2Treasury.Action action,) = treasury.execute();
            assertEq(uint256(action), uint256(HedgeFunV2Treasury.Action.RebalanceSell));
            assertGt(e.reserveUsdg(), 0, "the sale's USDG is the reserve");
            assertGt(poolUsdg - IERC20(USDG).balanceOf(listing.pool), 0, "USDG really left the real NVDA pool");
            uint256 value = Math.mulDiv(e.bookedStock(), price, SCALE);
            assertApproxEqAbs(value * 10_000 / (value + e.reserveUsdg()), 5000, 20, "at target");
        } else {
            // the real pool and the oracle disagree by more than the gate at this block: the engine fails closed
            vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
            vm.prank(KEEPER);
            treasury.execute();
        }
    }

    /// The ordinary lot strategy (kind 0) on SPY, listed with one of the oracles deployed on 2026-10-05: launch at
    /// the listed opening and graduate through the real SPY pool; the graduation stock is the first lot at cost.
    function test_kind0OnSPY_launchesAtTheListing_graduates_andBooksTheLot() public {
        _select("SPY");
        _launch("LISTSPY", 0);
        (, uint256 treasuryStock) = _graduate();
        assertEq(treasury.lotCount(), 1, "the graduation stock is a lot");
        (uint256 qty, uint256 cost, bool half,) = treasury.lots(0);
        assertEq(qty, treasuryStock);
        assertEq(cost, price, "booked at the listing's live oracle price");
        assertFalse(half);
        assertEq(treasury.bookedStock(), treasuryStock);
        assertEq(treasury.lastSalePrice(), price);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        vm.prank(KEEPER);
        treasury.execute();
    }

    // ---------------------------------------------------------------------------------- launch and graduation
    function _select(string memory symbol) private {
        for (uint256 i; i < rows.length; ++i) {
            if (keccak256(bytes(rows[i].e.symbol)) == keccak256(bytes(symbol))) {
                listing = rows[i].e;
                openPriceE18 = rows[i].openPriceE18;
                price = rows[i].priceE18;
                break;
            }
        }
        require(listing.stock != address(0), "not in the plan");
        address[2] memory traders = [ALICE, BOB];
        for (uint256 i; i < traders.length; ++i) {
            vm.prank(USDG_SOURCE);
            IERC20(USDG).transfer(traders[i], 20_000e6);
            vm.prank(traders[i]);
            IERC20(USDG).approve(address(router), type(uint256).max);
        }
    }

    function _request(string memory symbol, uint8 kind) private view returns (HedgeFunFactory.Request memory q) {
        q.name = "Mainnet listing fork";
        q.symbol = symbol;
        q.stock = listing.stock;
        q.creator = CREATOR;
        q.taxBps = 100;
        q.creatorBps = 1000;
        q.tp1Bps = 500;
        q.tp2Bps = 1000;
        q.dipBps = 500;
        q.lotBps = 2000;
        q.nonce = uint96(kind) + 1;
        q.maxFee = factory.getDefaults().launchFeeAmount;
        q.expectedOpenPriceE18 = openPriceE18;
    }

    function _launch(string memory symbol, uint8 kind) private {
        HedgeFunFactory.Request memory q = _request(symbol, kind);
        if (kind != 0) {
            vm.prank(CREATOR);
            registry.setStrategyKind(symbol, q.nonce, kind);
        }
        _open(q, kind);
    }

    function _launchEngine(string memory symbol, uint8 kind, EngineConfig memory config) private {
        HedgeFunFactory.Request memory q = _request(symbol, kind);
        vm.prank(CREATOR);
        registry.setEngineConfig(symbol, q.nonce, kind, config);
        _open(q, kind);
    }

    function _open(HedgeFunFactory.Request memory q, uint8 kind) private {
        (address predictedToken, address predictedTreasury, bytes32 terms) = factory.predict(q);
        vm.deal(CREATOR, q.maxFee);
        vm.prank(CREATOR);
        id = factory.launch{value: q.maxFee}(q, terms);
        curve = Curve(factory.curves(id));
        token = HedgeFunToken(curve.token());
        treasury = HedgeFunV2Treasury(curve.treasury());
        (key,) = factory.graduationConfig(id);
        assertEq(address(token), predictedToken);
        assertEq(address(treasury), predictedTreasury);
        assertEq(registry.strategyKindOf(keccak256(abi.encode(q.symbol, CREATOR, q.nonce))), kind);
        assertEq(curve.minTokenReserve(), 206_900_000e18, "79.31% of one billion is sold on the curve");
        assertEq(registry.lpBpsOfTreasury(address(treasury)), 7000, "the launch froze seventy to thirty");
        uint256 raiseUsd = (curve.terminalStock() - curve.virtualStock()) * price / 1e18;
        assertApproxEqRel(raiseUsd, 8_204.6e18, 0.001e18, "net raise to graduate, at the listing's price");
        assertEq(address(treasury.pool()), listing.pool, "the treasury trades on the listed pool");
        assertEq(address(treasury.oracle()), listing.oracle, "and is priced by the listed oracle");
        HedgeFunTreasuryBase.Params memory p = treasury.params();
        assertEq(p.maxDeviationBps, listing.maxDeviationBps, "the listing's gates");
        assertEq(p.maxSlippageBps, listing.maxSlippageBps);
        assertEq(p.sellChunkUsdg, listing.sellChunkUsdg);
        address[2] memory traders = [ALICE, BOB];
        for (uint256 i; i < traders.length; ++i) {
            vm.prank(traders[i]);
            token.approve(address(router), type(uint256).max);
        }
        vm.warp(block.timestamp + 30); // past the opening window
    }

    function _path(bool buying) private view returns (Router.Hop[] memory path) {
        path = new Router.Hop[](1);
        path[0] = Router.Hop(listing.pool, buying ? listing.stock : USDG);
    }

    function _buy(address user, uint256 usdgIn) private returns (uint256 got, uint256 refund) {
        Router.TradeParams memory p = Router.TradeParams(id, USDG, usdgIn, 0, 1, block.timestamp, 0, true);
        uint256 userTokens = token.balanceOf(user);
        vm.prank(user);
        (got, refund) = router.buy(p, _path(true));
        assertEq(token.balanceOf(user) - userTokens, got);
    }

    /// @dev Two buyers on the curve through the real stock pool; the second crosses and graduates.
    function _graduate() private returns (uint256 lpStock, uint256 treasuryStock) {
        (uint256 aliceTokens,) = _buy(ALICE, 300e6);
        assertGt(aliceTokens, 0);
        assertEq(uint256(curve.status()), uint256(Curve.Status.Active));
        uint256 pmStock = IERC20(listing.stock).balanceOf(address(PM));
        uint256 held = IERC20(listing.stock).balanceOf(address(treasury));
        (, uint256 refund) = _buy(BOB, 9_500e6);
        assertEq(uint256(curve.status()), uint256(Curve.Status.Graduated), "the crossing buy graduates in the same transaction");
        assertGt(refund, 0, "the stock beyond the terminal reserve comes back");
        lpStock = IERC20(listing.stock).balanceOf(address(PM)) - pmStock;
        treasuryStock = IERC20(listing.stock).balanceOf(address(treasury)) - held;
        assertGt(PM.getLiquidity(key.toId()), 0, "the deployed V4 manager holds the graduated position");
        uint256 raise = curve.terminalStock() - curve.virtualStock();
        assertApproxEqRel(lpStock + treasuryStock, raise, 0.0001e18, "the raise is split between pool and treasury");
        assertLe(lpStock, Math.mulDiv(lpStock + treasuryStock, 7000, 10_000));
        assertLe(Math.mulDiv(lpStock + treasuryStock, 7000, 10_000) - lpStock, 1e12, "the pool gets its 70% within dust");
        assertApproxEqRel(_fdvUsd(), 50_000e18, 0.01e18, "FDV at the graduated pool's price");
        emit log_named_decimal_uint("graduation: stock to the V4 pool, USD", lpStock * price / 1e18, 18);
        emit log_named_decimal_uint("graduation: stock to the treasury, USD", treasuryStock * price / 1e18, 18);
        emit log_named_decimal_uint("graduation: FDV at the pool price, USD", _fdvUsd(), 18);
    }

    function _fdvUsd() private view returns (uint256) {
        (uint160 sqrtP,,,) = PM.getSlot0(key.toId());
        uint256 p = Math.mulDiv(Math.mulDiv(sqrtP, sqrtP, 1 << 96), 1e18, 1 << 96); // currency1 per currency0, e18
        uint256 stockPerToken = address(token) < listing.stock ? p : 1e36 / p;
        return stockPerToken * 1_000_000_000 * price / 1e18;
    }

    /// @dev schema 1: 50% stock, a 2.5% band, ten minutes between actions, half of a sale's gain to the buy-back;
    ///      one action at most the listing's chunk, a day at most five of them (the end-to-end suite's config).
    function _spotConfig() private view returns (EngineConfig memory c) {
        c.schema = 1;
        c.engineVersion = 1;
        c.policyKey = spotPolicyKey;
        c.words[0] = bytes32(uint256(5000) | uint256(250) << 16 | uint256(600) << 32 | uint256(5000) << 64);
        c.words[1] = bytes32(uint256(2_000e6));
        c.words[2] = bytes32(uint256(10_000e6));
    }
}
