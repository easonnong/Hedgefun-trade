// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {HedgeFunV2TradeRouter} from "../src/v2/HedgeFunV2TradeRouter.sol";
import {HedgeFunV2TradablePercentEngineTreasuryCore} from "../src/v2/HedgeFunV2TradablePercentEngineTreasury.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {EngineConfig} from "../src/v2/strategy/IStrategyPolicy.sol";
import {IUniswapV3Pool} from "../src/interfaces/IUniswapV3.sol";
import {IAggregatorV3} from "../src/interfaces/IAggregatorV3.sol";
import {AssetPriceOracle} from "../src/AssetPriceOracle.sol";
import {AlwaysOpenCalendar} from "../src/AlwaysOpenCalendar.sol";
import {IWrappedNative} from "../src/v2/HedgeFunV2NativeRouter.sol";
import {V2MainnetCore} from "../script/mainnet/V2MainnetCore.sol";
import {DeployV2MainnetCore, HandOverV2Mainnet, VerifyV2MainnetHandOver} from "../script/mainnet/DeployV2MainnetCore.s.sol";
import {V2MainnetDefaults} from "../script/mainnet/V2MainnetDefaults.sol";
import {RegisterV2TradablePercent} from "../script/RegisterV2TradablePercent.s.sol";

/// A launch paired with ETH itself, on a fork of Robinhood Chain (4663): the real wrapped ETH, the real Chainlink
/// ETH/USD and USDG/USD feeds, the real WETH/USDG pool and the real pool manager. The V2 core is deployed inside
/// the fork by the mainnet deployment script, handed to the real owner Safe, and wrapped ETH is listed on it with
/// `AssetPriceOracle` and `AlwaysOpenCalendar`. No key and no transaction: `vm.deal` funds the actors with ETH.
///
/// The Chainlink ETH feed prints on a 0.5% move, so at any block it may sit up to that far from the pool. The test
/// prints the pool's own price to the feed where it needs the two to agree, as a fresh report would.
///
/// MAINNET_ETH_PAIR_FORK=true MAINNET_ETH_PAIR_FORK_BLOCK=<fresh block> [MAINNET_ETH_PAIR_FORK_RPC=...]
///   forge test --match-contract MainnetV2EthPairForkTest -vv
contract MainnetV2EthPairForkTest is Test {
    address internal constant WETH = 0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73;
    address internal constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address internal constant ETH_FEED = 0x78F3556b67E17Df817D51Ef5a990cDaF09E8d3A9;
    address internal constant USDG_FEED = 0x61B7e5650328764B076A108EFF5fa7282a1B9aD2;
    /// the deepest WETH/USDG pool, 0.01%: wrapped ETH is token0
    address internal constant POOL = 0x52e65B17fB6E5BA00Ed806f37Afcd2DaA50271Ca;
    address internal constant SAFE = 0x2910117dd2cB431173Ae9Fb6eAF30726321d1693;

    HedgeFunV2Factory internal factory;
    V2TreasuryDeployer internal registry;
    V2MainnetCore.Deployed internal core;
    AssetPriceOracle internal oracle;
    AlwaysOpenCalendar internal calendar;
    address internal deployer = makeAddr("eth pair fork deployer");
    address internal creator = makeAddr("eth pair fork creator");
    address internal keeper = makeAddr("eth pair fork keeper");
    uint256 internal openPrice;
    uint8 internal rebalanceKind;
    bytes32 internal rebalancePolicyKey;

    function setUp() public {
        vm.skip(!vm.envOr("MAINNET_ETH_PAIR_FORK", false), "set MAINNET_ETH_PAIR_FORK=true");
        uint256 forkBlock = vm.envUint("MAINNET_ETH_PAIR_FORK_BLOCK");
        vm.createSelectFork(
            vm.envOr("MAINNET_ETH_PAIR_FORK_RPC", string("https://rpc.mainnet.chain.robinhood.com")), forkBlock
        );
        assertEq(block.chainid, 4663, "Robinhood Chain only");
        emit log_named_uint("eth pair fork block", forkBlock);
        assertEq(IUniswapV3Pool(POOL).token0(), WETH);
        assertEq(IUniswapV3Pool(POOL).token1(), USDG);
        assertEq(IUniswapV3Pool(POOL).fee(), 100);

        // The mainnet script, with the deploying key as first owner, exactly as it would be run.
        V2MainnetCore.Roles memory roles = V2MainnetCore.Roles(SAFE, SAFE, WETH);
        bytes32 reviewed = keccak256(abi.encode(V2MainnetDefaults.release()));
        V2MainnetCore.Deployed memory x = new DeployV2MainnetCore().deploy(deployer, roles, true, reviewed, 0);
        core = x;
        factory = x.factory;
        registry = x.treasury;

        // The owner's setup: the rebalance kind, and wrapped ETH listed like a stock.
        RegisterV2TradablePercent.Registration memory r = new RegisterV2TradablePercent().register(
            deployer, factory, keccak256("eth pair fork dependencies"), keccak256("eth pair fork audit")
        );
        rebalanceKind = r.kind;
        rebalancePolicyKey = r.policyKey;
        vm.startPrank(deployer);
        calendar = new AlwaysOpenCalendar(SAFE);
        oracle = new AssetPriceOracle(WETH, ETH_FEED, USDG_FEED, address(calendar), 26 hours, 26 hours);
        _syncFeeds();
        // about 10,000 USDG for the whole supply at the oracle's price, in ETH per token
        openPrice = Math.mulDiv(10_000e18, 1e18, oracle.price()) / 1_000_000_000;
        factory.list(WETH, address(oracle), POOL, openPrice, true);
        vm.stopPrank();

        // Hand over before launch opens; the Safe accepts and opens it.
        new HandOverV2Mainnet().handOver(deployer, factory, SAFE);
        vm.startPrank(SAFE);
        factory.acceptOwnership();
        factory.setPublicLaunch(true);
        vm.stopPrank();
        new VerifyV2MainnetHandOver().check(factory, SAFE);
        assertEq(calendar.owner(), SAFE);
    }

    /// The ordinary strategy on an ETH pair: the launch fee and every buy are plain ETH, the treasury sells ETH for
    /// USDG above its cost, burns the token with the profit, buys ETH back under its last sale, and stops the
    /// moment the Safe halts the calendar.
    function test_ethPairedLaunch_boughtWithEth_graduates_takesProfit_burns_buysTheDip_andHalts() public {
        uint256 fee = factory.getDefaults().launchFeeAmount;
        assertEq(fee, 0.0005 ether);
        uint256 protocolBefore = SAFE.balance;
        // 0.2% rungs: the ordinary strategy lets a creator choose them freely, and a move that small is one
        // this test can make in a pool this deep.
        (uint256 id, HedgeFunBondingCurve curve, HedgeFunV2Treasury t) = _launch("ETHPAIR", 0, 20, 0, 20);
        assertEq(SAFE.balance - protocolBefore, fee, "the native launch fee reached the protocol Safe");
        IERC20 token = IERC20(curve.token());

        // A first buy with plain ETH through the native router: no WETH, no approval, no route. What the curve
        // does not take comes back as ETH.
        vm.deal(creator, 1 ether);
        HedgeFunV2TradeRouter.TradeParams memory p = HedgeFunV2TradeRouter.TradeParams(
            id, WETH, 0.2 ether, 0.2 ether, 1, block.timestamp, uint8(curve.status()), true
        );
        vm.prank(creator);
        (uint256 bought, uint256 refund) = core.nativeRouter.buy{value: 0.2 ether}(p, new HedgeFunV2TradeRouter.Hop[](0));
        assertGt(bought, 0);
        assertEq(token.balanceOf(creator), bought);
        assertEq(creator.balance, 0.8 ether + refund, "the unused part is returned unwrapped");
        assertLt(refund, 1e9, "rounding dust only");
        assertEq(IERC20(WETH).balanceOf(creator), 0, "the buyer never holds wrapped ETH");

        _graduate(curve);
        assertGt(t.bookedStock(), 0, "the graduation ETH is a lot, booked at the Chainlink price");
        assertGt(t.lotCount(), 0);
        (bool healthy, uint256 open) = t.health();
        assertTrue(healthy);

        // +0.3%: over the 0.2% rung.
        _movePool(open * 1003 / 1000);
        uint256 cash = t.reserveUsdg();
        assertEq(uint256(_execute(t)), uint256(HedgeFunV2Treasury.Action.TakeProfit));
        assertGt(t.reserveUsdg(), cash, "ETH sold for USDG on the real pool");
        assertGt(t.buybackStock(), 0, "the profit stays in ETH for the buy-back");

        uint256 supply = token.totalSupply();
        vm.prank(keeper);
        (uint256 spent, uint256 burned) = t.buyback();
        assertGt(spent, 0);
        assertEq(token.totalSupply(), supply - burned, "the token is burned through its own ETH pool");

        // Back to the open: 0.3% under the last sale.
        while (_due(t) == HedgeFunV2Treasury.Action.TakeProfit) _execute(t);
        _movePool(open);
        uint256 lots = t.lotCount();
        assertEq(uint256(_execute(t)), uint256(HedgeFunV2Treasury.Action.BuyDip));
        assertEq(t.lotCount(), lots + 1);
        assertEq(
            IERC20(WETH).balanceOf(address(t)), t.bookedStock() + t.buybackStock() + t.unbookedStock(), "ETH ledger"
        );

        // The Safe's switch: no price, so no trade and no buy-back, until it is released.
        vm.prank(SAFE);
        calendar.setHalted(true);
        (healthy,) = t.health();
        assertFalse(healthy);
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        _execute(t);
        vm.prank(SAFE);
        calendar.setHalted(false);
        (healthy,) = t.health();
        assertTrue(healthy);
    }

    /// The rebalance kind on an ETH pair. Its daily budgets are counted per trading date, which here is the
    /// always-open calendar's UTC day.
    function test_ethPairedRebalance_sellsDownToItsTargetWithinTheDailyBudget() public {
        EngineConfig memory c;
        c.schema = 3;
        c.engineVersion = 1;
        c.policyKey = rebalancePolicyKey;
        // target 70% ETH, 5% band, 600 s between actions, all net gain to the buy-back; 25% per action, 50% a day
        c.words[0] = bytes32(uint256(7000) | uint256(500) << 16 | uint256(600) << 32 | uint256(10_000) << 64);
        c.words[1] = bytes32(uint256(2500) | uint256(2500) << 16);
        c.words[2] = bytes32(uint256(5000) | uint256(5000) << 16);
        vm.prank(creator);
        registry.setEngineConfig("ETHREBAL", 7, rebalanceKind, c);
        // This kind does not use the rungs, but its constructor keeps the legacy floor on them.
        (, HedgeFunBondingCurve curve, HedgeFunV2Treasury treasury) = _launch("ETHREBAL", 7, 500, 0, 500);
        _graduate(curve);
        HedgeFunV2TradablePercentEngineTreasuryCore t = HedgeFunV2TradablePercentEngineTreasuryCore(address(treasury));
        assertEq(address(t.tradingCalendar()), address(calendar));

        uint256 held = t.bookedStock() + t.unbookedStock();
        assertGt(held, 0);
        (uint64 epoch,, uint256 buyCap, uint256 sellCap,,) = t.dailyRiskLimits();
        assertEq(epoch, block.timestamp / 1 days, "a trading date is a UTC day");
        assertEq(buyCap, sellCap);
        assertEq(uint256(_execute(treasury)), uint256(HedgeFunV2Treasury.Action.RebalanceSell));
        assertLt(t.bookedStock(), held, "all ETH at graduation: the first action sells towards 70%");
        assertGt(t.reserveUsdg(), 0);
        assertLe(t.turnoverInEpoch(), sellCap);
        // One sale of a quarter of the ETH: 75%, the top of the band. Nothing more is due.
        vm.expectRevert();
        _execute(treasury);
        assertEq(IERC20(WETH).balanceOf(address(t)), t.bookedStock() + t.buybackStock() + t.unbookedStock());
    }

    // ------------------------------------------------------------------------------------------------ the venue
    function _launch(string memory symbol, uint96 nonce, uint32 tp1Bps, uint32 tp2Bps, uint16 dipBps)
        private
        returns (uint256 id, HedgeFunBondingCurve curve, HedgeFunV2Treasury treasury)
    {
        HedgeFunFactory.Defaults memory d = factory.getDefaults();
        HedgeFunFactory.Request memory q;
        q.name = "ETH pair fork rehearsal";
        q.symbol = symbol;
        q.nonce = nonce;
        q.stock = WETH;
        q.creator = creator;
        q.taxBps = d.minTaxBps;
        q.creatorBps = d.maxCreatorBps;
        q.tp1Bps = tp1Bps;
        q.tp2Bps = tp2Bps;
        q.dipBps = dipBps;
        q.lotBps = 5000;
        q.maxFee = d.launchFeeAmount;
        q.expectedOpenPriceE18 = openPrice;
        vm.deal(creator, d.launchFeeAmount);
        vm.startPrank(creator);
        (, address predicted, bytes32 terms) = factory.predict(q);
        id = factory.launch{value: d.launchFeeAmount}(q, terms);
        vm.stopPrank();
        curve = HedgeFunBondingCurve(factory.curves(id));
        treasury = HedgeFunV2Treasury(predicted);
        assertEq(curve.treasury(), predicted);
        assertEq(address(treasury.oracle()), address(oracle));
        vm.warp(curve.launchedAt() + curve.snipeSeconds());
        _syncFeeds();
    }

    /// @dev a buyer wraps ETH and takes the rest of the curve
    function _graduate(HedgeFunBondingCurve curve) private {
        address buyer = makeAddr("eth pair fork buyer");
        vm.deal(buyer, 200 ether);
        vm.startPrank(buyer);
        IWrappedNative(WETH).deposit{value: 200 ether}();
        IERC20(WETH).approve(address(curve), type(uint256).max);
        curve.buy(type(uint256).max, 1, buyer, block.timestamp);
        vm.stopPrank();
        assertEq(uint256(curve.status()), uint256(HedgeFunBondingCurve.Status.Graduated));
    }

    function _execute(HedgeFunV2Treasury t) private returns (HedgeFunV2Treasury.Action action) {
        vm.prank(keeper);
        (action,) = t.execute();
    }

    function _due(HedgeFunV2Treasury t) private returns (HedgeFunV2Treasury.Action action) {
        uint256 snapshot = vm.snapshotState();
        vm.prank(keeper);
        try t.execute() returns (HedgeFunV2Treasury.Action a, uint256) { action = a; }
        catch { action = HedgeFunV2Treasury.Action.Stop; }
        vm.revertToState(snapshot);
    }

    /// @dev USDG per whole ETH, 1e18-scaled, at the listing pool's spot: wrapped ETH is token0 with 18 decimals,
    ///      USDG is token1 with 6
    function _poolPrice() private view returns (uint256) {
        (uint160 sqrtP,,,,,,) = IUniswapV3Pool(POOL).slot0();
        return Math.mulDiv(Math.mulDiv(uint256(sqrtP), uint256(sqrtP), 1 << 96), 1e30, 1 << 96);
    }

    /// @dev A fresh report from both feeds, the ETH feed at the listing pool's own price.
    function _syncFeeds() private {
        (uint80 round, int256 usdgUsd,,,) = IAggregatorV3(USDG_FEED).latestRoundData();
        vm.mockCall(
            USDG_FEED,
            abi.encodeWithSelector(IAggregatorV3.latestRoundData.selector),
            abi.encode(round, usdgUsd, block.timestamp, block.timestamp, round)
        );
        int256 ethUsd = int256(Math.mulDiv(_poolPrice(), uint256(usdgUsd), 1e18));
        vm.mockCall(
            ETH_FEED,
            abi.encodeWithSelector(IAggregatorV3.latestRoundData.selector),
            abi.encode(round, ethUsd, block.timestamp, block.timestamp, round)
        );
    }

    /// @dev Trade the real listing pool to `priceE18`, let its 600-second mean catch up, and report the new price.
    function _movePool(uint256 priceE18) private {
        uint160 target = uint160(Math.sqrt(Math.mulDiv(priceE18, 1 << 192, 1e30)));
        (uint160 current,,,,,,) = IUniswapV3Pool(POOL).slot0();
        // A trader with both sides in hand. Wrapped ETH is real ETH deposited; the USDG is written into the fork.
        MarketMover m = new MarketMover();
        vm.deal(address(this), 20_000 ether);
        IWrappedNative(WETH).deposit{value: 20_000 ether}();
        IERC20(WETH).transfer(address(m), 20_000 ether);
        deal(USDG, address(m), 50_000_000e6);
        m.swapToLimit(POOL, target < current, type(int128).max, target);
        (current,,,,,,) = IUniswapV3Pool(POOL).slot0();
        assertEq(current, target, "the pool reached the price");
        vm.warp(block.timestamp + 660);
        _syncFeeds();
    }
}

/// Pays a V3 pool what a swap asks for, out of its own balance.
contract MarketMover {
    function swapToLimit(address pool, bool zeroForOne, int256 amount, uint160 limit) external {
        IUniswapV3Pool(pool).swap(address(this), zeroForOne, amount, limit, "");
    }

    function uniswapV3SwapCallback(int256 amount0, int256 amount1, bytes calldata) external {
        if (amount0 > 0) IERC20(IUniswapV3Pool(msg.sender).token0()).transfer(msg.sender, uint256(amount0));
        if (amount1 > 0) IERC20(IUniswapV3Pool(msg.sender).token1()).transfer(msg.sender, uint256(amount1));
    }
}
