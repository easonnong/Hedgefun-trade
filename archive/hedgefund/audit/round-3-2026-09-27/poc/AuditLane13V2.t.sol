// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {console2} from "forge-std/console2.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {SwapParams, ModifyLiquidityParams} from "v4-core/src/types/PoolOperation.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";
import {PoolModifyLiquidityTest} from "v4-core/src/test/PoolModifyLiquidityTest.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunToken} from "../src/HedgeFunToken.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";

/// Lane 13 (src/v2 surface) proof-of-concepts. Nothing here is a fix; every test is evidence.
contract AuditLane13V2 is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    PoolSwapTest internal swapRouter;

    function setUp() public {
        _setUpV2(18);
        swapRouter = new PoolSwapTest(pm);
    }

    function _vaultOf(PoolKey memory key) internal view returns (V2LiquidityVault) {
        return V2LiquidityVault(hook.liquidityVaultOf(key.toId()));
    }

    function _swapBothWays(PoolKey memory key) internal {
        address t0 = Currency.unwrap(key.currency0);
        address t1 = Currency.unwrap(key.currency1);
        IERC20(t0).approve(address(swapRouter), type(uint256).max);
        IERC20(t1).approve(address(swapRouter), type(uint256).max);
        // stock -> token, then token -> stock: both legs accrue a static-fee share to the locked position
        bool stockIs0 = t0 == address(stock);
        swapRouter.swap(key, SwapParams({zeroForOne: stockIs0, amountSpecified: -int256(1e18),
            sqrtPriceLimitX96: stockIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        swapRouter.swap(key, SwapParams({zeroForOne: !stockIs0, amountSpecified: -int256(1e18),
            sqrtPriceLimitX96: !stockIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
    }

    // ---------------------------------------------------------------- 1. collectFees has no per-leg isolation
    function test_L13_blockedStockLegAlsoStrandsTheTokenBurn() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        V2LiquidityVault vault = _vaultOf(key);
        address treasury = curve.treasury();
        HedgeFunToken token = HedgeFunToken(curve.token());
        _swapBothWays(key);

        // control: both legs deliver
        uint256 snap = vm.snapshotState();
        (uint256 stockFee, uint256 burned) = vault.collectFees();
        assertGt(stockFee, 0, "control stock leg");
        assertGt(burned, 0, "control token leg");
        vm.revertToState(snap);

        // the issuer of a tokenised equity blocklists the treasury (a switch someone else holds)
        stock.blockRecipient(treasury);
        vm.expectRevert(bytes("blocked recipient"));
        vault.collectFees();

        // the TOKEN side had nothing to do with the stock issuer, and is stranded with it:
        // no path in V2LiquidityVault burns token fees on their own.
        assertEq(token.balanceOf(address(vault)), 0, "no token fee reached the vault");

        // by contrast the hook, on the same codebase, splits its two legs with try/catch.
        stock.blockRecipient(address(0xdead));
        (stockFee, burned) = vault.collectFees();
        assertGt(stockFee, 0);
        assertGt(burned, 0);
    }

    // ---------------------------------------------------------------- 2. the permissionless fallback can never fire
    function test_L13_graduateFallbackIsUnreachable() public {
        (uint256 id, HedgeFunBondingCurve curve,) = _launchV2(true);
        // before the cap
        vm.expectRevert(HedgeFunV2Factory.NotReady.selector);
        factory.graduate(id);
        // one wei short of the cap: still Active
        uint256 cap = curve.terminalStock() - (curve.virtualStock() + curve.realStockReserve());
        curve.buy(cap - 1, 1, address(this), block.timestamp);
        assertEq(uint256(curve.status()), uint256(HedgeFunBondingCurve.Status.Active));
        vm.expectRevert(HedgeFunV2Factory.NotReady.selector);
        factory.graduate(id);

        // now make graduation revert: the treasury cannot receive its share of the raise
        stock.blockRecipient(curve.treasury());
        vm.expectRevert(bytes("blocked recipient"));
        curve.buy(type(uint256).max, 1, address(this), block.timestamp);
        // Ready never persisted, so the fallback is still NotReady - the curve is capped, not retryable
        assertEq(uint256(curve.status()), uint256(HedgeFunBondingCurve.Status.Active));
        vm.expectRevert(HedgeFunV2Factory.NotReady.selector);
        factory.graduate(id);
    }

    // ---------------------------------------------------------------- 3. the curve's reserve invariant
    function test_L13_fuzzCurveInvariantAndSolvency(uint256 seed) public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        IERC20 tok = IERC20(curve.token());
        stock.mint(address(this), 1e30);
        uint256 paidIn;
        uint256 paidOut;
        for (uint256 i; i < 24; ++i) {
            seed = uint256(keccak256(abi.encode(seed, i)));
            if (curve.status() != HedgeFunBondingCurve.Status.Active) break;
            if (seed % 3 != 0) {
                uint256 cap = curve.terminalStock() - (curve.virtualStock() + curve.realStockReserve());
                if (cap <= 1) break;
                uint256 want = 1 + (seed >> 8) % (cap - 1); // never cross the cap: graduation is tested elsewhere
                (uint256 spend, uint256 out,) = curve.quoteBuy(want);
                if (spend == 0 || out == 0) continue;
                uint256 before = stock.balanceOf(address(this));
                curve.buy(want, 0, address(this), block.timestamp);
                paidIn += before - stock.balanceOf(address(this));
            } else {
                uint256 have = tok.balanceOf(address(this));
                if (have == 0) continue;
                uint256 amount = 1 + (seed >> 8) % have;
                (uint256 out,) = curve.quoteSell(amount);
                if (out == 0) continue;
                uint256 before = stock.balanceOf(address(this));
                curve.sell(amount, 0, address(this), block.timestamp);
                paidOut += stock.balanceOf(address(this)) - before;
            }
            _assertCurveInvariant(curve, tok);
        }
        // the virtual leg is never paid: a round trip can only lose
        assertLe(paidOut, paidIn, "a trader can never take more stock out than went in");
    }

    function _assertCurveInvariant(HedgeFunBondingCurve curve, IERC20 tok) internal view {
        uint256 y = curve.virtualStock() + curve.realStockReserve();
        assertEq(y, Math.ceilDiv(curve.invariant(), curve.tokenReserve()), "y == ceil(k/x)");
        assertEq(tok.balanceOf(address(curve)), curve.tokenReserve(), "token balance == tokenReserve");
        assertGe(stock.balanceOf(address(curve)), curve.realStockReserve() + curve.totalFees(), "stock solvency");
        assertGe(curve.tokenReserve(), curve.minTokenReserve(), "reserve never below the terminal floor");
    }

    // every remaining token, sold back at once, must be payable out of the real reserve
    function test_L13_lastSellerCanAlwaysBeRedeemed() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        stock.mint(address(this), 1e30);
        uint256 cap = curve.terminalStock() - (curve.virtualStock() + curve.realStockReserve());
        curve.buy(cap - 1, 1, address(this), block.timestamp);
        IERC20 tok = IERC20(curve.token());
        uint256 held = tok.balanceOf(address(this));
        (uint256 out, uint256 tax) = curve.quoteSell(held);
        assertLe(out + tax, curve.realStockReserve(), "the whole float is redeemable from the real reserve");
        uint256 before = stock.balanceOf(address(this));
        curve.sell(held, 0, address(this), block.timestamp);
        assertEq(stock.balanceOf(address(this)) - before, out);
        _assertCurveInvariant(curve, tok);
        // what is left of the reserve is exactly the invariant's answer for the tokens the buy tax burned
        assertEq(curve.virtualStock() + curve.realStockReserve(),
            Math.ceilDiv(curve.invariant(), curve.tokenReserve()));
    }

    // ---------------------------------------------------------------- 4. the locked position
    function test_L13_vaultPrincipalCannotLeaveByAnyRoute() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        V2LiquidityVault vault = _vaultOf(key);
        uint128 lp = pm.getLiquidity(key.toId());
        assertGt(lp, 0);

        // the callback refuses any data the vault did not build itself
        vm.expectRevert(V2LiquidityVault.NotPoolManager.selector);
        vault.unlockCallback(abi.encode(uint8(1), uint128(lp), uint256(0), uint256(0)));
        vm.expectRevert(V2LiquidityVault.NotPoolManager.selector);
        vault.unlockCallback(abi.encode(uint8(2), uint128(0), uint256(0), uint256(0)));
        // re-seeding is refused
        vm.prank(address(factory));
        vm.expectRevert(V2LiquidityVault.AlreadySeeded.selector);
        vault.seed(uint160(1 << 96), 1, 1, 1);
        // a stranger cannot add liquidity to the graduated pool at all
        PoolModifyLiquidityTest lpRouter = new PoolModifyLiquidityTest(pm);
        IERC20(Currency.unwrap(key.currency0)).approve(address(lpRouter), type(uint256).max);
        IERC20(Currency.unwrap(key.currency1)).approve(address(lpRouter), type(uint256).max);
        vm.expectRevert();
        lpRouter.modifyLiquidity(key, ModifyLiquidityParams({tickLower: TickMath.minUsableTick(key.tickSpacing),
            tickUpper: TickMath.maxUsableTick(key.tickSpacing), liquidityDelta: 1e12, salt: 0}), "");
        // ... and a stranger's own (empty) position cannot be burned to reach the vault's
        vm.expectRevert();
        lpRouter.modifyLiquidity(key, ModifyLiquidityParams({tickLower: TickMath.minUsableTick(key.tickSpacing),
            tickUpper: TickMath.maxUsableTick(key.tickSpacing), liquidityDelta: -int256(uint256(lp)), salt: 0}), "");
        assertEq(pm.getLiquidity(key.toId()), lp, "principal unchanged");
    }

    // ---------------------------------------------------------------- 5. delegatecall storage safety
    function test_L13_graduationDelegatecallDoesNotTouchFactoryStorage() public {
        (uint256 id, HedgeFunBondingCurve curve,) = _launchV2(true);
        address ownerBefore = factory.owner();
        bool publicBefore = factory.publicLaunch();
        uint256 countBefore = factory.strategyCount();
        bytes32 rowBefore = _strategyRow(id);
        _graduateV2(curve);
        assertEq(factory.owner(), ownerBefore, "slot 0 (owner) survives the CurveDeployer delegatecall");
        assertEq(factory.publicLaunch(), publicBefore);
        assertEq(factory.strategyCount(), countBefore);
        assertEq(_strategyRow(id), rowBefore, "the strategy row is untouched");
        assertEq(factory.curves(id), address(curve));
    }

    function _strategyRow(uint256 id) internal view returns (bytes32) {
        (address t, address tr, address h, address s, address c) = factory.strategies(id);
        return keccak256(abi.encode(t, tr, h, s, c));
    }

    // ---------------------------------------------------------------- 6. what graduation actually moves
    function test_L13_graduationValueSplit() public {
        (uint256 id, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        stock.mint(address(this), 1e30);
        HedgeFunToken token = HedgeFunToken(curve.token());
        uint256 raise = curve.terminalStock() - curve.virtualStock();
        uint256 supply0 = token.totalSupply();
        _graduateV2(curve);
        V2LiquidityVault vault = _vaultOf(key);
        (,address treasury,,,) = factory.strategies(id);
        uint256 poolStock = stock.balanceOf(address(pm));
        uint256 poolToken = token.balanceOf(address(pm));
        console2.log("raise (stock)            ", raise);
        console2.log("stock left in the V4 pool", poolStock);
        console2.log("stock sent to treasury   ", stock.balanceOf(treasury));
        console2.log("supply at launch         ", supply0);
        console2.log("supply after graduation  ", token.totalSupply());
        console2.log("token left in the V4 pool", poolToken);
        console2.log("vault                    ", address(vault));
        assertEq(stock.balanceOf(address(curve)), curve.totalFees(), "the curve keeps only unclaimed fees");
        assertEq(stock.balanceOf(address(factory)), 0, "the factory keeps nothing");
        assertEq(token.balanceOf(address(factory)), 0);
        assertEq(token.balanceOf(address(vault)), 0);
        assertEq(stock.balanceOf(address(vault)), 0);
    }
}
