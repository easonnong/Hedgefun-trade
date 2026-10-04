// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// External audit round 4, economics lane. Evidence for lanes/econ.md. Offline: no RPC, no environment variables.
// Runs against a checkout of codex/v2-strategy-engine (5aedceb) via ./run.sh, which stages this file into test/.

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {SwapMath} from "v4-core/src/libraries/SwapMath.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2EngineTreasury} from "../src/v2/HedgeFunV2EngineTreasury.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {EngineConfig, StrategyAction, StrategyCapabilities} from "../src/v2/strategy/IStrategyPolicy.sol";
import {V2RebalancePolicy} from "../src/v2/strategy/V2RebalancePolicy.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {ISwapCallback, SwitchableCalendar} from "./mocks/Mocks.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// @dev A V3 pool reduced to one in-range step: constant liquidity, the fee on the input, a price limit the swap
///      stops at, exact input AND exact output, computed by Uniswap's own `SwapMath`. Token0 is the stock, token1
///      USDG. The 10-minute mean is a separate stored tick so a test can move spot without moving the mean, which
///      is what an atomic push does to a real pool.
contract ConstantLiquidityVenue {
    address public immutable token0;
    address public immutable token1;
    uint24 public immutable fee;
    uint256 internal immutable scale;
    uint160 public sqrtPriceX96;
    uint128 public liquidity;
    int24 public twapTick;
    uint256 public volumeIn0;
    uint256 public volumeIn1;

    constructor(address stock, address usdg, uint24 fee_, uint256 scale_) {
        token0 = stock;
        token1 = usdg;
        fee = fee_;
        scale = scale_;
    }

    function sqrtOf(uint256 priceE18) public view returns (uint160) {
        return uint160(Math.sqrt(Math.mulDiv(priceE18, 1 << 192, scale)));
    }

    function priceOf(uint160 s) public view returns (uint256) {
        return Math.mulDiv(Math.mulDiv(s, s, 1 << 96), scale, 1 << 96);
    }

    function price() external view returns (uint256) {
        return priceOf(sqrtPriceX96);
    }

    /// @dev "arbs brought the pool back and the mean has caught up"
    function setPrice(uint256 priceE18) external {
        sqrtPriceX96 = sqrtOf(priceE18);
        twapTick = TickMath.getTickAtSqrtPrice(sqrtPriceX96);
    }

    function settleTwap() external {
        twapTick = TickMath.getTickAtSqrtPrice(sqrtPriceX96);
    }

    /// @notice size the book by the USDG that lifts the price 1% from where it stands (round 3 measured this on
    ///         the live pools: about $3.3k for AMD/USDG, about $55k for AAPL/USDG, 2026-09-27)
    function setDepth(uint256 usdgPer1pct) external {
        uint160 up = sqrtOf(Math.mulDiv(priceOf(sqrtPriceX96), 101, 100));
        liquidity = uint128(Math.mulDiv(usdgPer1pct, 1 << 96, up - sqrtPriceX96));
    }

    function slot0() external view returns (uint160, int24, uint16, uint16, uint16, uint8, bool) {
        return (sqrtPriceX96, TickMath.getTickAtSqrtPrice(sqrtPriceX96), 0, 1000, 1000, 0, true);
    }

    function observe(uint32[] calldata ago) external view returns (int56[] memory tc, uint160[] memory l) {
        tc = new int56[](2);
        l = new uint160[](2);
        tc[1] = int56(twapTick) * int56(uint56(ago[0]));
    }

    /// @dev V3's sign convention: `amountSpecified > 0` is exact input, `< 0` exact output.
    function swap(address recipient, bool zeroForOne, int256 amountSpecified, uint160 limit, bytes calldata data)
        external
        returns (int256 a0, int256 a1)
    {
        require(amountSpecified != 0, "AS");
        require(
            zeroForOne
                ? limit < sqrtPriceX96 && limit > TickMath.MIN_SQRT_PRICE
                : limit > sqrtPriceX96 && limit < TickMath.MAX_SQRT_PRICE,
            "SPL"
        );
        (uint160 next, uint256 amountIn, uint256 amountOut, uint256 feeAmount) =
            SwapMath.computeSwapStep(sqrtPriceX96, limit, liquidity, -amountSpecified, fee);
        sqrtPriceX96 = next;
        uint256 spent = amountIn + feeAmount;
        (a0, a1) = zeroForOne ? (int256(spent), -int256(amountOut)) : (-int256(amountOut), int256(spent));
        if (zeroForOne) volumeIn0 += spent;
        else volumeIn1 += spent;
        IERC20 input = IERC20(zeroForOne ? token0 : token1);
        if (amountOut != 0) IERC20(zeroForOne ? token1 : token0).transfer(recipient, amountOut);
        uint256 before = input.balanceOf(address(this));
        ISwapCallback(msg.sender).uniswapV3SwapCallback(a0, a1, data);
        require(input.balanceOf(address(this)) >= before + spent, "IIA");
    }
}

/// @dev The attacker: pushes the venue to a chosen sqrt price, lets the treasury trade, unwinds exactly.
contract Sandwicher is ISwapCallback {
    ConstantLiquidityVenue public immutable venue;
    IERC20 public immutable stock;
    IERC20 public immutable usdg;

    constructor(ConstantLiquidityVenue venue_, IERC20 stock_, IERC20 usdg_) {
        venue = venue_;
        stock = stock_;
        usdg = usdg_;
    }

    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        require(msg.sender == address(venue), "venue");
        if (a0 > 0) stock.transfer(msg.sender, uint256(a0));
        if (a1 > 0) usdg.transfer(msg.sender, uint256(a1));
    }

    /// sell stock until spot sits at `sqrtLimit`; returns the stock sold
    function pushDownTo(uint160 sqrtLimit) external returns (uint256 sold) {
        (int256 a0,) = venue.swap(address(this), true, int256(uint256(type(uint128).max)), sqrtLimit, "");
        sold = uint256(a0);
    }

    /// buy stock until spot sits at `sqrtLimit`; returns the stock bought
    function pushUpTo(uint160 sqrtLimit) external returns (uint256 bought) {
        (int256 a0,) = venue.swap(address(this), false, int256(uint256(type(uint128).max)), sqrtLimit, "");
        bought = uint256(-a0);
    }

    function buyExactStock(uint256 amount) external {
        venue.swap(address(this), false, -int256(amount), TickMath.MAX_SQRT_PRICE - 1, "");
    }

    function sellExactStock(uint256 amount) external {
        venue.swap(address(this), true, int256(amount), TickMath.MIN_SQRT_PRICE + 1, "");
    }
}

contract AuditEcon4Test is V2FactoryFixture {
    uint256 internal constant P = 100e18;           // $100 per stock, 1e18
    uint256 internal constant SCALE = 1e30;         // 18-decimal stock, 6-decimal USDG
    uint256 internal constant BPS = 10_000;

    V2TreasuryDeployer internal deployer;
    V2RebalancePolicy internal policyImplementation;
    ConstantLiquidityVenue internal venue;
    bytes32 internal policyKey;
    uint8 internal engineKind;
    uint96 internal nextNonce = 400;

    function setUp() public {
        _setUpV2(18);
        deployer = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        policyImplementation = new V2RebalancePolicy();
        vm.startPrank(owner);
        policyKey = deployer.registerPolicy(
            address(policyImplementation), 150_000, deployer.POLICY_RETURN_BYTES(), keccak256("econ-deps"), keccak256("econ-audit")
        );
        (address a, address b) = deployer.makeChunks(type(HedgeFunV2EngineTreasury).creationCode);
        engineKind = deployer.registerEngineKind(
            a, b, StrategyCapabilities.SPOT_ENGINE_V1, StrategyCapabilities.CONFIG_SCHEMA_V1,
            StrategyCapabilities.SPOT_BUY | StrategyCapabilities.SPOT_SELL
        );
        vm.stopPrank();
        _venue(3000, 10_000e6, address(oracle));
    }

    // ------------------------------------------------------------------------------------------------ fixture
    /// a fresh venue at the given fee tier and depth, listed as the stock's pool under `oracle_`
    function _venue(uint24 fee, uint256 depthUsdg, address oracle_) internal {
        venue = new ConstantLiquidityVenue(address(stock), address(usdg), fee, SCALE);
        venue.setPrice(P);
        venue.setDepth(depthUsdg);
        usdg.mint(address(venue), 100_000_000e6);
        stock.mint(address(venue), 10_000_000e18);
        v3f.set(address(stock), address(usdg), fee, address(venue));
        vm.prank(owner);
        factory.list(address(stock), oracle_, address(venue), openPrice, true);
    }

    function _config(uint256 target, uint256 band, uint256 cooldown, uint256 maxTrade, uint256 maxDaily)
        internal view returns (EngineConfig memory c)
    {
        c.schema = StrategyCapabilities.CONFIG_SCHEMA_V1;
        c.engineVersion = StrategyCapabilities.SPOT_ENGINE_V1;
        c.policyKey = policyKey;
        c.words[0] = bytes32(target | band << 16 | cooldown << 32);
        c.words[1] = bytes32(maxTrade);
        c.words[2] = bytes32(maxDaily);
    }

    function _launch(EngineConfig memory c) internal returns (HedgeFunV2EngineTreasury t) {
        HedgeFunFactory.Request memory q = _request();
        q.nonce = nextNonce++;
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, c);
        (,, bytes32 terms) = factory.predict(q);
        uint256 id = factory.launch(q, terms);
        (, address at,,,) = factory.strategies(id);
        t = HedgeFunV2EngineTreasury(at);
        HedgeFunBondingCurve curve = HedgeFunBondingCurve(factory.curves(id));
        stock.approve(address(curve), type(uint256).max);
        _graduateV2(curve);
    }

    function _refresh(int256 feedPrice) internal {
        stockFeed.set(feedPrice);
        usdgFeed.set(1e8);
    }

    /// value at the oracle, in USDG: how the engine itself measures the treasury
    function _value(HedgeFunV2EngineTreasury t, uint256 p) internal view returns (uint256) {
        return Math.mulDiv(t.bookedStock() + t.unbookedStock(), p, SCALE) + t.reserveUsdg();
    }

    function _shareBps(HedgeFunV2EngineTreasury t, uint256 p) internal view returns (uint256) {
        uint256 s = Math.mulDiv(t.bookedStock() + t.unbookedStock(), p, SCALE);
        return s * BPS / (s + t.reserveUsdg());
    }

    function _bps(uint256 part, uint256 whole) internal pure returns (uint256) {
        return whole == 0 ? 0 : part * BPS / whole;
    }

    // ------------------------------------------------------------------------------------------------ X-1
    /// The sandwich, measured. One action of the graduation sell-down, on a 30 bps pool with the rehearsal gates
    /// (deviation 50, slippage 100): the attacker pushes spot 49 bps under the oracle, calls execute(), buys back
    /// what it sold. The treasury's fill is ~50 bps worse than an unmanipulated one; the attacker LOSES money,
    /// because the round-trip fee (60 bps of the push) exceeds the room the deviation gate leaves (50 bps).
    function test_X1_sandwichOn30bpsPool_treasuryPays50bpsMore_attackerLoses() public {
        (uint256 turnover, uint256 costControl, uint256 costPushed, int256 attacker) = _sandwich(3000, 10_000e6, 2_000e6);
        emit log_named_decimal_uint("turnover (USDG)", turnover, 6);
        emit log_named_uint("treasury cost vs oracle, no push (bps of turnover)", _bps(costControl, turnover));
        emit log_named_uint("treasury cost vs oracle, pushed (bps of turnover)", _bps(costPushed, turnover));
        emit log_named_decimal_int("attacker P&L (USDG)", attacker, 6);
        assertGt(costPushed, costControl, "the push worsens the fill");
        uint256 extra = _bps(costPushed - costControl, turnover);
        assertGe(extra, 44, "extra cost is the deviation gate's room");
        assertLe(extra, 55, "extra cost is bounded by the deviation gate");
        assertLe(_bps(costPushed, turnover), 130, "the (slip + fee) floor holds");
        assertLt(attacker, 0, "on a 30 bps tier the sandwich is a loss for the attacker");
    }

    /// Same action on a 5 bps pool, same gates: the room (50 bps) now exceeds the round-trip fee (10 bps) and
    /// the attacker is paid. The gate that decides profitability is `maxDeviationBps` against `2 x poolFeeBps`.
    function test_X1_sandwichOn5bpsPool_attackerProfits() public {
        (uint256 turnover, uint256 costControl, uint256 costPushed, int256 attacker) = _sandwich(500, 10_000e6, 2_000e6);
        emit log_named_decimal_uint("turnover (USDG)", turnover, 6);
        emit log_named_uint("treasury cost vs oracle, no push (bps of turnover)", _bps(costControl, turnover));
        emit log_named_uint("treasury cost vs oracle, pushed (bps of turnover)", _bps(costPushed, turnover));
        emit log_named_decimal_int("attacker P&L (USDG)", attacker, 6);
        assertGt(attacker, 0, "on a 5 bps tier the sandwich pays");
        assertLe(_bps(costPushed, turnover), 105, "the (slip + fee) floor holds");
    }

    /// The deviation gate is the binding one: a push of 51 bps shuts `health()`, 49 bps does not. Both leave
    /// the 10-minute mean where it was, so the TWAP gate alone would have passed 49 either way.
    function test_X1_deviationGateBindsAt50bps() public {
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, 2_000e6, 10_000e6));
        Sandwicher bot = new Sandwicher(venue, stock, usdg);
        stock.mint(address(bot), 1_000e18);
        uint256 snap = vm.snapshotState();
        bot.pushDownTo(venue.sqrtOf(P * 9949 / 10_000));
        (bool ok,) = t.health();
        assertFalse(ok, "51 bps under the oracle: shut");
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        t.execute();
        vm.revertToState(snap);
        bot.pushDownTo(venue.sqrtOf(P * 9951 / 10_000));
        (ok,) = t.health();
        assertTrue(ok, "49 bps under the oracle: open");
        t.execute();
    }

    function _sandwich(uint24 fee, uint256 depth, uint256 maxTrade)
        internal returns (uint256 turnover, uint256 costControl, uint256 costPushed, int256 attacker)
    {
        _venue(fee, depth, address(oracle));
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, maxTrade, 10_000e6));
        uint256 stock0 = t.bookedStock();
        assertEq(t.reserveUsdg(), 0, "graduation hands the engine stock only");
        (bool due, StrategyAction a,) = t.preview();
        assertTrue(due && a == StrategyAction.SellStock, "100% stock against a 50% target: it sells");

        uint256 snap = vm.snapshotState();
        t.execute();
        uint256 sold0 = stock0 - t.bookedStock();
        costControl = Math.mulDiv(sold0, P, SCALE) - t.reserveUsdg();
        vm.revertToState(snap);

        Sandwicher bot = new Sandwicher(venue, stock, usdg);
        stock.mint(address(bot), 1_000e18);
        usdg.mint(address(bot), 1_000_000e6);
        uint256 usdgBefore = usdg.balanceOf(address(bot));
        uint256 stockBefore = stock.balanceOf(address(bot));
        uint256 pushed = bot.pushDownTo(venue.sqrtOf(P * 9951 / 10_000));      // 49 bps: inside the gate
        t.execute();
        uint256 sold1 = stock0 - t.bookedStock();
        costPushed = Math.mulDiv(sold1, P, SCALE) - t.reserveUsdg();
        turnover = Math.mulDiv(sold1, P, SCALE);
        bot.buyExactStock(pushed);
        assertEq(stock.balanceOf(address(bot)), stockBefore, "flat in stock after the unwind");
        attacker = int256(usdg.balanceOf(address(bot))) - int256(usdgBefore);
        // the control sold at most as much; compare per unit sold
        if (sold1 != sold0) costControl = Math.mulDiv(costControl, sold1, sold0);
    }

    // ------------------------------------------------------------------------------------------------ X-2
    /// The daily turnover cap is a UTC calendar day, not a rolling window: 500 USDG in the five minutes before
    /// midnight and another 500 in the five after. The cooldown (60 s) is the only thing between them.
    function test_X2_utcDayBoundaryDoublesTheDailyBudgetInTenMinutes() public {
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, 100e6, 500e6));
        uint256 midnight = (block.timestamp / 1 days + 1) * 1 days;
        vm.warp(midnight - 360);                                                  // five actions at -360 .. -120
        uint256 turnover;
        for (uint256 i; i < 5; ++i) {
            _refresh(100e8);
            venue.setPrice(P);
            t.execute();
            turnover += 100e6;
            vm.warp(block.timestamp + 60);
        }
        assertEq(t.turnoverInEpoch(), 500e6);
        // 60 s before midnight, cooldown satisfied: same epoch, budget spent
        assertEq(block.timestamp, midnight - 60);
        _refresh(100e8);
        venue.setPrice(P);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();
        vm.warp(midnight);
        for (uint256 i; i < 5; ++i) {
            _refresh(100e8);
            venue.setPrice(P);
            t.execute();
            turnover += 100e6;
            vm.warp(block.timestamp + 60);
        }
        assertEq(t.turnoverInEpoch(), 500e6, "a fresh 500 after the boundary");
        assertEq(turnover, 1_000e6, "1,000 USDG of a 500 USDG/day cap inside ten minutes");
        emit log_named_decimal_uint("turnover in the 10 minutes around 00:00 UTC (USDG)", turnover, 6);
    }

    // ------------------------------------------------------------------------------------------------ X-3
    /// Across a scheduled closure the engine cannot act at all -- not even on kind 0's band path, which
    /// `health()` still serves -- because `execute()` separately demands a live `tryPrice()`. `oraclePaused()`
    /// fails closed the same way. What is NOT closed: a feed that is stale but inside `maxStockAge` on an open
    /// day, when the pool sits within the deviation gate of the stale print.
    function test_X3_closureAndPauseFailClosed_staleWithinAgeTrades() public {
        SwitchableCalendar cal = new SwitchableCalendar();
        PriceOracle o2 = new PriceOracle(address(stock), address(stockFeed), address(usdgFeed), address(cal), 26 hours, 26 hours);
        _venue(3000, 10_000e6, address(o2));
        vm.prank(owner);
        factory.setBandCeiling(address(stock), 200);
        // a band-enabled request: kind 0 would trade the closure off the pool's mean, inside the band
        HedgeFunFactory.Request memory q = _request();
        q.nonce = nextNonce++;
        q.bandBpsPerHour = 200;
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(5000, 500, 60, 2_000e6, 10_000e6));
        (,, bytes32 terms) = factory.predict(q);
        uint256 id = factory.launch(q, terms);
        (, address at,,,) = factory.strategies(id);
        HedgeFunV2EngineTreasury t = HedgeFunV2EngineTreasury(at);
        HedgeFunBondingCurve curve = HedgeFunBondingCurve(factory.curves(id));
        stock.approve(address(curve), type(uint256).max);
        _graduateV2(curve);

        // (a) the weekend: calendar closed, feed frozen 30 h, pool where the feed left it
        cal.setClosed(true);
        vm.warp(block.timestamp + 30 hours);
        stockFeed.setAt(100e8, block.timestamp - 30 hours);
        usdgFeed.set(1e8);
        venue.setPrice(P);
        (bool ok, uint256 p) = t.health();
        assertTrue(ok, "kind 0's band path: health() serves the frozen print during a scheduled closure");
        assertEq(p, P);
        (bool due,,) = t.preview();
        assertFalse(due, "the engine's preview: not due");
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        t.execute();
        // ... and with the pool pinned 2% away inside the band, still nothing
        venue.setPrice(P * 98 / 100);
        (ok, p) = t.health();
        assertTrue(ok, "band path still open at -2%");
        assertLt(p, P, "and it would have served a pulled price");
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        t.execute();

        // (b) the market reopens, the feed prints, a corporate action pauses the oracle
        cal.setClosed(false);
        venue.setPrice(P);
        _refresh(100e8);
        stock.setOraclePaused(true);
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        t.execute();
        stock.setOraclePaused(false);

        // (c) an open day, the feed 25 h old but inside maxStockAge, the pool within the gate: it trades
        stockFeed.setAt(100e8, block.timestamp - 25 hours);
        (HedgeFunV2Treasury.Action action,) = t.execute();
        assertEq(uint256(action), uint256(HedgeFunV2Treasury.Action.RebalanceSell), "a 25 h old print is traded on");
        // (d) the same stale print, but the pool has moved 2% (the market did): shut
        vm.warp(block.timestamp + 60);
        usdgFeed.set(1e8);
        venue.setPrice(P * 98 / 100);
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        t.execute();
        // (e) pool held 49 bps under the stale print: it trades, and the fill may end 100 bps under it
        venue.setPrice(P * 9951 / 10_000);
        uint256 usdgBefore = t.reserveUsdg();
        uint256 stockBefore = t.bookedStock();
        t.execute();
        uint256 sold = stockBefore - t.bookedStock();
        uint256 got = t.reserveUsdg() - usdgBefore;
        emit log_named_uint("fill vs the stale print, pool 49 bps under it (bps below)", _bps(Math.mulDiv(sold, P, SCALE) - got, Math.mulDiv(sold, P, SCALE)));
    }

    // ------------------------------------------------------------------------------------------------ X-4
    /// Graduation hands the engine 100% stock and 0 USDG against a 50% target, so its first act is to sell
    /// half the graduation lot into the same V3 pool the raise just bought through, one capped action per
    /// cooldown, until the share is back inside the band. With maxTrade at the 2,000 USDG chunk default and
    /// no daily cap this is minutes; the per-action slippage floor is the only bound on price.
    function test_X4_graduationLotIsSoldDownToTargetImmediately() public {
        _venue(3000, 3_300e6, address(oracle));                                   // AMD-like depth
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, 2_000e6, type(uint256).max));
        uint256 v0 = _value(t, P);
        assertEq(_shareBps(t, P), 10_000, "100% stock at graduation");
        uint256 actions;
        uint256 sold;
        uint256 got;
        while (true) {
            venue.setPrice(P);                                                     // arbs refill between cooldowns
            _refresh(100e8);
            (bool due,,) = t.preview();
            if (!due) break;
            uint256 s0 = t.bookedStock();
            uint256 u0 = t.reserveUsdg();
            t.execute();
            ++actions;
            sold += s0 - t.bookedStock();
            got += t.reserveUsdg() - u0;
            vm.warp(block.timestamp + 60);
        }
        uint256 share = _shareBps(t, P);
        emit log_named_decimal_uint("treasury value at graduation (USDG)", v0, 6);
        emit log_named_uint("actions to reach the band", actions);
        emit log_named_uint("minutes at cooldown 60 s", actions);
        emit log_named_decimal_uint("stock sold, valued at the oracle (USDG)", Math.mulDiv(sold, P, SCALE), 6);
        emit log_named_decimal_uint("USDG received", got, 6);
        emit log_named_uint("execution cost of the sell-down (bps of what was sold)", _bps(Math.mulDiv(sold, P, SCALE) - got, Math.mulDiv(sold, P, SCALE)));
        emit log_named_uint("stock share after (bps)", share);
        assertLe(share, 5_500, "inside the band");
        assertGe(share, 4_950, "and not below target");
        assertGe(Math.mulDiv(sold, P, SCALE), v0 * 45 / 100, "about half the graduation lot left in minutes");
        assertEq(t.buybackStock(), 0, "none of it reaches the buy-back bucket");
    }

    // ------------------------------------------------------------------------------------------------ X-5
    /// The floors the engine constructor enforces admit a 1 bp deadband, a 1 s cooldown and an unbounded day.
    /// At 1 bp every Chainlink print (0.5% deviation trigger) is an action: a +0.5% / -0.5% pair of prints is
    /// a sell and a buy of ~0.125% of treasury value each, each paying the full execution cost.
    function test_X5_floorsAdmitOnePipBandOneSecondCooldownUnboundedDay_everyPrintIsAnAction() public {
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 1, 1, 2_000e6, type(uint256).max));
        // sell down to target first (three capped actions at 1 s spacing)
        while (true) {
            venue.setPrice(P);
            _refresh(100e8);
            (bool due,,) = t.preview();
            if (!due) break;
            t.execute();
            vm.warp(block.timestamp + 1);
        }
        uint256 v = _value(t, P);
        // +0.5%: one print, one sell
        venue.setPrice(P * 1005 / 1000);
        _refresh(1005e7);
        (bool due1, StrategyAction a1, uint256 in1) = t.preview();
        assertTrue(due1 && a1 == StrategyAction.SellStock, "a single 0.5% print triggers a sell at a 1 bp band");
        uint256 s0 = t.bookedStock();
        t.execute();
        uint256 sellUsdg = Math.mulDiv(s0 - t.bookedStock(), P * 1005 / 1000, SCALE);
        vm.warp(block.timestamp + 1);
        // -0.5%: back where it was, one buy
        venue.setPrice(P);
        _refresh(100e8);
        (bool due2, StrategyAction a2, uint256 in2) = t.preview();
        assertTrue(due2 && a2 == StrategyAction.BuyStock, "the print that reverts it triggers a buy");
        t.execute();
        emit log_named_decimal_uint("treasury value (USDG)", v, 6);
        emit log_named_decimal_uint("sell on the +0.5% print (USDG)", sellUsdg, 6);
        emit log_named_decimal_uint("buy on the -0.5% print (USDG)", in2, 6);
        emit log_named_uint("each action, bps of treasury value", _bps(sellUsdg, v));
        in1;
    }

    // ------------------------------------------------------------------------------------------------ X-6
    /// `execute()` pays no bounty: the caller's stock, USDG and launch-token balances are untouched. Kind 0's
    /// `bountyBps` (50 here) is carried in `Params` but never read by the engine's actions.
    function test_X6_executePaysNoBounty() public {
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, 2_000e6, 10_000e6));
        IERC20 fun = t.token();
        address keeper = address(0xBEEF);
        uint256 s = stock.balanceOf(keeper);
        uint256 u = usdg.balanceOf(keeper);
        uint256 f = fun.balanceOf(keeper);
        vm.prank(keeper);
        t.execute();
        assertEq(stock.balanceOf(keeper), s);
        assertEq(usdg.balanceOf(keeper), u);
        assertEq(fun.balanceOf(keeper), f);
        assertEq(t.params().bountyBps, 50, "a bounty is configured, and unused");
    }

    // ------------------------------------------------------------------------------------------------ X-7
    /// The engine has no profit path to the burn: a sell at 100, a buy at 80 and a sell at 100 leave
    /// `buybackStock` at zero and `buyback()` refusing. Only LP fees (`creditLiquidityFee`) ever fund a burn
    /// under kind 2. Kind 0 would have sent the profit share of every take-profit there.
    function test_X7_rebalanceGainsNeverReachTheBurn() public {
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, 2_000e6, type(uint256).max));
        _runToBand(t, 100e8, P);
        uint256 usdgAfterSellDown = t.reserveUsdg();
        _runToBand(t, 80e8, P * 80 / 100);                                        // underweight: buys at 80
        _runToBand(t, 100e8, P);                                                    // overweight again: sells at 100
        assertEq(t.buybackStock(), 0, "no profit share, ever");
        assertEq(t.totalBurned(), 0);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.buyback();
        emit log_named_decimal_uint("USDG reserve after the first sell-down", usdgAfterSellDown, 6);
        emit log_named_decimal_uint("USDG reserve after the 80 -> 100 round trip", t.reserveUsdg(), 6);
        emit log_named_decimal_uint("stock held after (1e18)", t.bookedStock(), 18);
    }

    function _runToBand(HedgeFunV2EngineTreasury t, int256 feed, uint256 poolPrice) internal {
        for (uint256 i; i < 64; ++i) {
            venue.setPrice(poolPrice);
            _refresh(feed);
            (bool due,,) = t.preview();
            if (!due) return;
            t.execute();
            vm.warp(block.timestamp + 60);
        }
    }

    // ------------------------------------------------------------------------------------------------ X-8
    /// A donation is an observation: stock sent to the treasury crosses the band and forces a sell. The donor
    /// pays the donation and gets, at best, the sandwich on one capped action. Here the donation needed at a
    /// 5% band is 2,222 USDG of stock against a bounded gain of under 1.3% of one action.
    function test_X8_donationTriggersASellButCostsTheDonorTheDonation() public {
        HedgeFunV2EngineTreasury t = _launch(_config(5000, 500, 60, 2_000e6, type(uint256).max));
        _runToBand(t, 100e8, P);
        venue.setPrice(P);
        _refresh(100e8);
        uint256 total = _value(t, P);
        (bool due,,) = t.preview();
        assertFalse(due, "at rest inside the band");
        // d such that (S + d) / (T + d) > 0.55, with S = 0.5 T: d > 0.05 T / 0.45
        uint256 dUsdg = total * 500 / 4_500 + 1e6;
        uint256 dStock = Math.mulDiv(dUsdg, SCALE, P);
        stock.mint(address(this), dStock);
        stock.transfer(address(t), dStock);
        (due,,) = t.preview();
        assertTrue(due, "the donation crossed the band");
        (, uint256 usdgOut) = _executeMeasured(t);
        emit log_named_decimal_uint("treasury value before (USDG)", total, 6);
        emit log_named_decimal_uint("donation needed (USDG of stock)", dUsdg, 6);
        emit log_named_decimal_uint("engine sold (USDG)", usdgOut, 6);
        emit log_named_decimal_uint("upper bound on any sandwich of that sale (1.3%)", usdgOut * 130 / 10_000, 6);
        assertGt(dUsdg, usdgOut * 130 / 10_000 * 10, "the donation is more than ten times the most a sandwich could return");
    }

    function _executeMeasured(HedgeFunV2EngineTreasury t) internal returns (uint256 stockSold, uint256 usdgOut) {
        uint256 s0 = t.bookedStock() + t.unbookedStock();
        uint256 u0 = t.reserveUsdg();
        t.execute();
        stockSold = s0 - t.bookedStock();
        usdgOut = t.reserveUsdg() - u0;
    }

    // ------------------------------------------------------------------------------------------------ X-9
    /// The creator-side setter validates nothing about the numbers; the engine constructor is the only floor.
    /// A treasury with maxTrade above `sellChunkUsdg` is refused at launch (TreasuryDeployFailed) -- the one
    /// value-relative bound there is -- while deadband 1 / cooldown 1 / maxDaily 2^256-1 all deploy.
    function test_X9_deployerAcceptsAnyWordsTheConstructorDoesNotRefuse() public {
        HedgeFunFactory.Request memory q = _request();
        q.nonce = nextNonce++;
        // maxTrade 1 wei above the chunk: accepted by setEngineConfig and quoted by predict, refused only when
        // the constructor runs at launch (CREATE2 swallows the reason: TreasuryDeployFailed)
        vm.prank(owner);
        factory.setListingGates(address(stock), 50, 100, 2_000e6);
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(5000, 500, 60, 2_000e6 + 1, type(uint256).max));
        (,, bytes32 badTerms) = factory.predict(q);
        vm.expectRevert(V2TreasuryDeployer.TreasuryDeployFailed.selector);
        factory.launch(q, badTerms);
        // deadband 1 bp, cooldown 1 s, unbounded day: accepted end to end
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(5000, 1, 1, 2_000e6, type(uint256).max));
        (,, bytes32 terms) = factory.predict(q);
        factory.launch(q, terms);
    }
}
