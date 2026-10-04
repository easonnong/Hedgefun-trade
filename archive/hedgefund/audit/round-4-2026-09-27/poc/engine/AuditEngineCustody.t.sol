// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Round-4 external audit, engine lane: CUSTODY and the two things the engine suite never exercises.
//   safe  the only outward stock/USDG movement is the V3 swap callback paying the listed pool; no allowance is
//         ever left to anyone; re-entry from inside the swap into execute/book/buyback is refused; a sell can
//         never reach the buyback bucket; a policy has nothing to pull
//   safe  USDG as token0 (9 of the 25 watched pools; "this bug has been shipped twice") -- sell and buy both move
//         the right asset the right way
//   safe  a 6-decimal stock
//   safe  the commitment: a stranger's setEngineConfig cannot touch the creator's salt

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {HedgeFunFactory} from "../../../../src/HedgeFunFactory.sol";
import {HedgeFunTreasuryBase} from "../../../../src/HedgeFunTreasuryBase.sol";
import {HedgeFunV2EngineTreasury} from "../../../../src/v2/HedgeFunV2EngineTreasury.sol";
import {HedgeFunV2Treasury} from "../../../../src/v2/HedgeFunV2Treasury.sol";
import {StrategyAction} from "../../../../src/v2/strategy/IStrategyPolicy.sol";
import {ISwapCallback, MockPool} from "../../../../test/mocks/Mocks.sol";
import {AuditEngineFixture} from "./AuditEngineFixture.sol";

/// @dev a venue that, from inside swap(), tries every state-changing entry point of the treasury before paying.
///      MockPool.swap is not virtual, so this is a standalone copy of its flat-price surface (stock as token0).
contract ReentrantVenue {
    address public immutable token0; address public immutable token1; uint24 public immutable fee;
    uint256 internal immutable SCALE;
    uint256 public price; int24 public tick; uint16 public constant cardinality = 1000;
    HedgeFunV2EngineTreasury public target;
    uint256 public executeOk; uint256 public bookOk; uint256 public buybackOk; uint256 public attempts;

    constructor(address stock, address usdg, uint24 fee_, uint256 scale) { (token0, token1, fee, SCALE) = (stock, usdg, fee_, scale); }
    function setTarget(HedgeFunV2EngineTreasury t) external { target = t; }
    function setPrice(uint256 p) public { price = p; tick = TickMath.getTickAtSqrtPrice(sqrtOf(p)); }
    function sqrtOf(uint256 p) public view returns (uint160) { return uint160(Math.sqrt(Math.mulDiv(p, 1 << 192, SCALE))); }
    function slot0() external view returns (uint160, int24, uint16, uint16, uint16, uint8, bool) { return (sqrtOf(price), tick, 0, cardinality, cardinality, 0, true); }
    function observe(uint32[] calldata ago) external view returns (int56[] memory tc, uint160[] memory l) {
        tc = new int56[](2); l = new uint160[](2); tc[1] = int56(tick) * int56(uint56(ago[0]));
    }
    function swap(address recipient, bool zeroForOne, int256 amountSpecified, uint160 limit, bytes calldata data) external returns (int256 a0, int256 a1) {
        require(amountSpecified > 0, "exact in only");
        require(zeroForOne ? limit < sqrtOf(price) : limit > sqrtOf(price), "SPL");
        if (address(target) != address(0)) {
            ++attempts;
            try target.execute() { ++executeOk; } catch {}
            try target.book() returns (bool) { ++bookOk; } catch {}
            try target.buyback() { ++buybackOk; } catch {}
        }
        uint256 inAmt = uint256(amountSpecified);
        uint256 net = inAmt * (1e6 - fee) / 1e6;
        uint256 outAmt = zeroForOne ? Math.mulDiv(net, price, SCALE) : Math.mulDiv(net, SCALE, price);
        IERC20(zeroForOne ? token1 : token0).transfer(recipient, outAmt);
        (a0, a1) = zeroForOne ? (int256(inAmt), -int256(outAmt)) : (-int256(outAmt), int256(inAmt));
        IERC20 tin = IERC20(zeroForOne ? token0 : token1);
        uint256 before = tin.balanceOf(address(this));
        ISwapCallback(msg.sender).uniswapV3SwapCallback(a0, a1, data);
        require(tin.balanceOf(address(this)) >= before + inAmt, "IIA");
    }
}

abstract contract AuditEngineCustodyBase is AuditEngineFixture {
    bytes32 internal key;

    function _sellThenBuy(HedgeFunV2EngineTreasury t) internal {
        // 100% stock -> one bounded sell
        uint256 stockBefore = stock.balanceOf(address(t));
        uint256 usdgBefore = usdg.balanceOf(address(t));
        uint256 venueStock = stock.balanceOf(address(venue));
        uint256 venueUsdg = usdg.balanceOf(address(venue));
        (bool due, StrategyAction a,) = t.preview();
        assertTrue(due); assertEq(uint256(a), uint256(StrategyAction.SellStock));
        (HedgeFunV2Treasury.Action act,) = t.execute();
        assertEq(uint256(act), uint256(HedgeFunV2Treasury.Action.RebalanceSell));
        uint256 sold = stockBefore - stock.balanceOf(address(t));
        uint256 got = usdg.balanceOf(address(t)) - usdgBefore;
        assertGt(sold, 0); assertGt(got, 0);
        assertEq(stock.balanceOf(address(venue)) - venueStock, sold, "stock went to the listed pool and nowhere else");
        assertEq(venueUsdg - usdg.balanceOf(address(venue)), got, "USDG came from the listed pool");
        assertEq(t.turnoverInEpoch(), sold * PRICE / scale);
        assertLe(t.turnoverInEpoch(), 100e6);
        // value conservation up to the venue's 0.30% fee: USDG got >= sold * p * (1 - fee - slip)
        assertGe(got, sold * PRICE / scale * 9870 / 10000);

        // flood USDG -> one bounded buy
        vm.warp(block.timestamp + 60);
        _market(PRICE);
        usdg.mint(address(t), 10 * _stockValue(t, PRICE));
        stockBefore = stock.balanceOf(address(t)); usdgBefore = usdg.balanceOf(address(t));
        venueStock = stock.balanceOf(address(venue)); venueUsdg = usdg.balanceOf(address(venue));
        (due, a,) = t.preview();
        assertTrue(due); assertEq(uint256(a), uint256(StrategyAction.BuyStock));
        (act,) = t.execute();
        assertEq(uint256(act), uint256(HedgeFunV2Treasury.Action.RebalanceBuy));
        uint256 spent = usdgBefore - usdg.balanceOf(address(t));
        uint256 bought = stock.balanceOf(address(t)) - stockBefore;
        assertEq(spent, 100e6, "the per-call cap binds");
        assertGt(bought, 0);
        assertEq(usdg.balanceOf(address(venue)) - venueUsdg, spent);
        assertEq(venueStock - stock.balanceOf(address(venue)), bought);
        assertGe(bought, spent * scale / PRICE * 9870 / 10000);

        // ledger
        assertEq(t.bookedStock() + t.buybackStock(), stock.balanceOf(address(t)), "buckets cover the balance exactly");
        assertEq(t.lotCount(), 0, "the engine never opens a lot");
        // no allowance survives to anyone
        assertEq(stock.allowance(address(t), address(venue)), 0);
        assertEq(usdg.allowance(address(t), address(venue)), 0);
        assertEq(stock.allowance(address(t), t.policyImplementation()), 0);
        assertEq(usdg.allowance(address(t), t.policyImplementation()), 0);
        assertEq(stock.allowance(address(t), address(this)), 0);
    }
}

contract AuditEngineCustodyStockIsToken0 is AuditEngineCustodyBase {
    function setUp() public {
        _setUpEngine(18, true);
        key = _registerPolicy(address(rebalance), 150_000, "rebalance");
    }

    function test_safe_sellThenBuy_stockIsToken0_18dec() public {
        _sellThenBuy(_launchGraduated(_config(key, 5000, 500, 60, 100e6, 500e6), 1));
    }

    function test_safe_reentryFromInsideTheSwapIsRefused() public {
        ReentrantVenue rv = new ReentrantVenue(address(stock), address(usdg), 3000, scale);
        rv.setPrice(PRICE);
        v3f.set(address(stock), address(usdg), 3000, address(rv));
        vm.prank(owner);
        factory.list(address(stock), address(oracle), address(rv), openPrice, true);
        usdg.mint(address(rv), 100_000_000e6); stock.mint(address(rv), 1_000_000e18);
        HedgeFunV2EngineTreasury t = _launchGraduated(_config(key, 5000, 500, 60, 100e6, 500e6), 2);
        rv.setTarget(t);
        t.execute();
        assertEq(rv.attempts(), 1, "the venue was inside the treasury's swap");
        assertEq(rv.executeOk() + rv.bookOk() + rv.buybackOk(), 0, "every re-entry refused by the shared guard");
        assertEq(t.strategyNonce(), 1);
    }

    /// LP stock fees live in buybackStock; a sell is bounded by bookedStock and cannot reach them
    function test_safe_sellCannotReachTheBuybackBucket() public {
        HedgeFunV2EngineTreasury t = _launchGraduated(_config(key, 5000, 500, 1, type(uint128).max, type(uint256).max), 3);
        address vault = t.liquidityVault();
        uint256 fee = 7e18;
        stock.mint(vault, fee);
        vm.startPrank(vault); stock.approve(address(t), fee); t.creditLiquidityFee(fee); vm.stopPrank();
        assertEq(t.buybackStock(), fee);
        // sell as much as the engine ever will: to target, in as many calls as it takes
        for (uint256 i; i < 5; ++i) { vm.warp(block.timestamp + 1); _market(PRICE); try t.execute() {} catch { break; } }
        assertEq(t.buybackStock(), fee, "untouched");
        assertGe(stock.balanceOf(address(t)), fee + t.bookedStock());
        assertApproxEqRel(_stockValue(t, PRICE), t.reserveUsdg(), 0.02e18, "at target: 50/50 within friction");
    }

    /// a stranger cannot select or configure the creator's salt; only the creator's own second call restates
    function test_safe_strangerCannotTouchTheCreatorsSalt() public {
        HedgeFunFactory.Request memory q = _request();
        q.nonce = 4;
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(key, 5000, 500, 60, 100e6, 500e6));
        (, address mine, bytes32 terms) = factory.predict(q);
        vm.prank(address(0xBAD));
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(key, 9000, 100, 1, 1, 1));
        (, address still,) = factory.predict(q);
        assertEq(still, mine, "a stranger's record lives under a different salt");
        uint256 id = factory.launch(q, terms);
        (, address deployed,,,) = factory.strategies(id);
        assertEq(deployed, mine);
        assertEq(uint256(HedgeFunV2EngineTreasury(deployed).engineConfig().words[0]) & 0xffff, 5000);
    }
}

contract AuditEngineCustodyUsdgIsToken0 is AuditEngineCustodyBase {
    function setUp() public {
        _setUpEngine(18, false);
        key = _registerPolicy(address(rebalance), 150_000, "rebalance");
    }
    function test_safe_sellThenBuy_usdgIsToken0_18dec() public {
        assertEq(venue.token0(), address(usdg));
        _sellThenBuy(_launchGraduated(_config(key, 5000, 500, 60, 100e6, 500e6), 1));
    }
}

contract AuditEngineCustodySixDecimals is AuditEngineCustodyBase {
    function setUp() public {
        _setUpEngine(6, true);
        key = _registerPolicy(address(rebalance), 150_000, "rebalance");
    }
    function test_safe_sellThenBuy_6decStock() public {
        assertEq(scale, 1e18);
        _sellThenBuy(_launchGraduated(_config(key, 5000, 500, 60, 100e6, 500e6), 1));
    }
}

contract AuditEngineCustodySixDecimalsUsdgIsToken0 is AuditEngineCustodyBase {
    function setUp() public {
        _setUpEngine(6, false);
        key = _registerPolicy(address(rebalance), 150_000, "rebalance");
    }
    function test_safe_sellThenBuy_6decStock_usdgIsToken0() public {
        _sellThenBuy(_launchGraduated(_config(key, 5000, 500, 60, 100e6, 500e6), 1));
    }
}
