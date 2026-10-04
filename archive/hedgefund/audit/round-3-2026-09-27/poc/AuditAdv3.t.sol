// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary, PoolId} from "v4-core/src/types/PoolId.sol";
import {SwapParams} from "v4-core/src/types/PoolOperation.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// @dev Adversarial round 3: attack H-1's unnamed evaporation conditions.
contract AuditAdv3 is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;
    PoolSwapTest internal router;
    address internal griefer = address(0xBEEF);

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

    /// ADV-1: with spikeBps = 0 the whole H-1 chain still runs and arms nothing.
    function test_ADV_spikeBpsZeroKillsH1() public {
        HedgeFunFactory.Defaults memory d = _defaults();
        d.spikeBps = 0;
        vm.prank(owner); factory.setDefaults(d);
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        address vault = t.liquidityVault();
        stock.mint(vault, 1);
        vm.startPrank(vault); stock.approve(address(t), 1); t.creditLiquidityFee(1); vm.stopPrank();
        vm.prank(griefer);
        (uint256 spent,) = t.buyback();
        assertEq(spent, 1, "still spends the wei");
        emit log_named_uint("sellRateBps after buyback at spikeBps=0", hook.sellRateBps(id));
        assertEq(hook.sellRateBps(id), 1000, "no spike arms at spikeBps=0");
    }

    /// ADV-2: at the enforced FLOOR lpFee = 1 the fee inlet yields nothing on a very large buy.
    function test_ADV_lpFeeFloorStarvesTheFuelLine() public {
        HedgeFunFactory.Defaults memory d = _defaults();
        d.lpFee = 1;                                   // _minLpFee(), the v2 floor
        vm.prank(owner); factory.setDefaults(d);
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        address token = curve.token();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        V2LiquidityVault vault = V2LiquidityVault(hook.liquidityVaultOf(key.toId()));
        stock.mint(griefer, 10_000e18);
        _buyFun(griefer, 100e18, key, token);          // a 100-stock buy, huge against the pool
        (uint256 stockFee, uint256 tokenBurned) = vault.collectFees();
        emit log_named_uint("lpFee=1: stock fee from a 100-stock buy", stockFee);
        emit log_named_uint("lpFee=1: token burn", tokenBurned);
        emit log_named_uint("lpFee=1: buybackStock", t.buybackStock());
        emit log_named_uint("lpFee=1: sellRateBps (pre-buyback)", hook.sellRateBps(key.toId()));
    }

    /// ADV-3: at lpFee = 3000, what does the SAME 100-stock buy yield? (control for ADV-2)
    function test_ADV_lpFeeControl3000() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        address token = curve.token();
        V2LiquidityVault vault = V2LiquidityVault(hook.liquidityVaultOf(key.toId()));
        stock.mint(griefer, 10_000e18);
        _buyFun(griefer, 100e18, key, token);
        (uint256 stockFee, uint256 tokenBurned) = vault.collectFees();
        emit log_named_uint("lpFee=3000: stock fee from a 100-stock buy", stockFee);
        emit log_named_uint("lpFee=3000: token burn", tokenBurned);
    }

    /// ADV-4: H-1 does not need lastEventAt == 0. Arm once, let the window lapse, re-arm --
    ///        which is the same guard a non-zeroed lastEventAt would present at graduation+240s.
    function test_ADV_h1DoesNotNeedLastEventAtZero() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        address vault = t.liquidityVault();
        stock.mint(vault, 100);
        vm.startPrank(vault); stock.approve(address(t), 100); t.creditLiquidityFee(1); vm.stopPrank();
        vm.prank(griefer); t.buyback();
        assertEq(hook.sellRateBps(id), 9000, "armed, lastEventAt now = now");
        // From here on lastEventAt is a real timestamp, exactly the counterfactual state that
        // NOT zeroing it at registration would produce. The spike still re-arms every 240s.
        vm.warp(block.timestamp + 241);
        vm.startPrank(vault); t.creditLiquidityFee(1); vm.stopPrank();
        vm.prank(griefer); t.buyback();
        assertEq(hook.sellRateBps(id), 9000, "re-armed from a NONZERO lastEventAt");
    }
}
