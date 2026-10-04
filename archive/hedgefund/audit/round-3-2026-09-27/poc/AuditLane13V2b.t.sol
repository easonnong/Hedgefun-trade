// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {console2} from "forge-std/console2.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {SwapParams} from "v4-core/src/types/PoolOperation.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";
import {CurveDeployer} from "../src/v2/CurveDeployer.sol";
import {HedgeFunToken} from "../src/HedgeFunToken.sol";
import {HedgeFunHook} from "../src/hooks/HedgeFunHook.sol";

contract AuditLane13V2b is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    PoolSwapTest internal swapRouter;

    function setUp() public {
        _setUpV2(18);
        swapRouter = new PoolSwapTest(pm);
        stock.mint(address(this), 1e30);
    }

    function _sellIntoPool(PoolKey memory key, address token, uint256 amount) internal returns (uint256 got) {
        IERC20(token).approve(address(swapRouter), type(uint256).max);
        bool tokenIs0 = Currency.unwrap(key.currency0) == token;
        uint256 before = stock.balanceOf(address(this));
        swapRouter.swap(key, SwapParams({zeroForOne: tokenIs0, amountSpecified: -int256(amount),
            sqrtPriceLimitX96: tokenIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        got = stock.balanceOf(address(this)) - before;
    }

    /// Is the graduation trigger a free option? The crossing buyer both chooses the moment and knows the
    /// pool's opening price and depth exactly. Measure whether it can be closed at a profit atomically.
    function test_L13_crossingBuyerCannotProfitByDumpingIntoTheFreshPool() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        vm.warp(block.timestamp + 10); // past the opening burn window; the sniper case is separate
        address token = curve.token();

        // someone else funds most of the curve first, so the crossing buyer is spending other people's depth
        uint256 cap = curve.terminalStock() - (curve.virtualStock() + curve.realStockReserve());
        curve.buy((cap * 90) / 100, 1, address(0xBEEF), block.timestamp);

        uint256 stockBefore = stock.balanceOf(address(this));
        uint256 tokBefore = IERC20(token).balanceOf(address(this));
        curve.buy(type(uint256).max, 1, address(this), block.timestamp);   // the crossing buy graduates
        uint256 spent = stockBefore - stock.balanceOf(address(this));
        uint256 gained = IERC20(token).balanceOf(address(this)) - tokBefore;
        uint256 back = _sellIntoPool(key, token, gained);
        console2.log("crossing buy: stock spent", spent);
        console2.log("crossing buy: tokens out ", gained);
        console2.log("immediate dump returns   ", back);
        assertLt(back, spent, "the crossing buy plus an atomic dump must not profit");
    }

    /// How much of the raise the graduated pool can actually return, and to whom.
    function test_L13_poolDepthAgainstTheRaise() public {
        (uint256 id, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        vm.warp(block.timestamp + 10);
        address token = curve.token();
        uint256 raise = curve.terminalStock() - curve.virtualStock();
        curve.buy(type(uint256).max, 1, address(this), block.timestamp);
        (,address treasury,,,) = factory.strategies(id);
        uint256 float_ = IERC20(token).balanceOf(address(this));
        uint256 poolStock = stock.balanceOf(address(pm));
        console2.log("raise                  ", raise);
        console2.log("stock in the V4 pool   ", poolStock);
        console2.log("stock in the treasury  ", stock.balanceOf(treasury));
        console2.log("float held by the buyer", float_);
        uint256 out1 = _sellIntoPool(key, token, float_ / 100);
        console2.log("selling 1% of float ->", out1);
        uint256 out10 = _sellIntoPool(key, token, float_ / 10);
        console2.log("selling 10% more    ->", out10);
        assertLt(poolStock, raise, "the pool never holds the whole raise");
    }

    /// Anyone can compute a vault address before graduation. Anything sent there is lost for good.
    function test_L13_vaultDonationsArePermanentlyLocked() public {
        (uint256 id, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        CurveDeployer cd = factory.curveDeployer();
        (,address treasury,,,) = factory.strategies(id);
        address predicted = cd.predictVault(bytes32(id),
            abi.encode(address(factory), address(pm), key, curve.token(), address(stock), treasury));
        stock.mint(address(0xD0), 5e18);
        vm.prank(address(0xD0));
        stock.transfer(predicted, 5e18);           // pre-donation, before the vault exists
        _graduateV2(curve);
        assertEq(hook.liquidityVaultOf(key.toId()), predicted, "predictVault matches what deploy produced");
        V2LiquidityVault vault = V2LiquidityVault(predicted);
        assertEq(stock.balanceOf(predicted), 5e18, "the donation neither seeds nor refunds");
        vault.collectFees();
        assertEq(stock.balanceOf(predicted), 5e18, "collectFees never touches it either");
        // there is no other function on the vault
        assertEq(vault.factory(), address(factory));
    }

    /// The whole fee path dies if the stock issuer refuses the VAULT as a recipient, too.
    function test_L13_blockedVaultAlsoStopsTheTokenBurn() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        V2LiquidityVault vault = V2LiquidityVault(hook.liquidityVaultOf(key.toId()));
        address token = curve.token();
        IERC20(token).approve(address(swapRouter), type(uint256).max);
        stock.approve(address(swapRouter), type(uint256).max);
        bool tokenIs0 = Currency.unwrap(key.currency0) == token;
        swapRouter.swap(key, SwapParams({zeroForOne: !tokenIs0, amountSpecified: -int256(1e18),
            sqrtPriceLimitX96: !tokenIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        swapRouter.swap(key, SwapParams({zeroForOne: tokenIs0, amountSpecified: -int256(1e16),
            sqrtPriceLimitX96: tokenIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        stock.blockRecipient(address(vault));
        vm.expectRevert();   // poolManager.take wraps it: SafeERC20FailedOperation over "blocked recipient"
        vault.collectFees();
        uint256 supplyBefore = HedgeFunToken(token).totalSupply();
        stock.blockRecipient(address(0xdead));
        vault.collectFees();
        assertLt(HedgeFunToken(token).totalSupply(), supplyBefore, "the token leg only ever moves with the stock leg");
    }

    /// The last seller: the real reserve always covers the whole remaining float.
    function test_L13_lastSellerIsAlwaysRedeemable() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        vm.warp(block.timestamp + 10);   // past the opening burn, so the float is large
        uint256 cap = curve.terminalStock() - (curve.virtualStock() + curve.realStockReserve());
        curve.buy(cap - 1, 1, address(this), block.timestamp);
        IERC20 tok = IERC20(curve.token());
        uint256 held = tok.balanceOf(address(this));
        (uint256 out, uint256 tax) = curve.quoteSell(held);
        assertLe(out + tax, curve.realStockReserve(), "the whole float is redeemable out of the real reserve");
        uint256 before = stock.balanceOf(address(this));
        curve.sell(held, 0, address(this), block.timestamp);
        assertEq(stock.balanceOf(address(this)) - before, out);
        console2.log("float               ", held);
        console2.log("reserve left after  ", curve.realStockReserve());
        console2.log("unclaimed fees      ", curve.totalFees());
        // what remains is the fee take plus the tokens the buy tax burned; never negative
        assertGe(stock.balanceOf(address(curve)), curve.realStockReserve() + curve.totalFees());
    }

    /// A graduated pool opens with BOTH the snipe window and the sell spike off. Measure it.
    function test_L13_graduatedPoolOpensWithNoSpikeAndNoSnipe() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        uint256 sellRate = hook.sellRateBps(key.toId());
        uint256 buyRate = hook.buyRateBps(key.toId());
        (,,,,,, uint16 snipeBps, uint8 snipeSeconds) = _rates(key);
        console2.log("graduated sellRateBps", sellRate);
        console2.log("graduated buyRateBps ", buyRate);
        console2.log("lastEventAt          ", hook.lastEventAt(key.toId()));
        assertEq(sellRate, 1000, "the flat creator tax, not the 9000 bps opening spike a V1 launch gets");
        assertEq(buyRate, 1000, "no snipe window");
        assertEq(snipeBps, 0);
        assertEq(snipeSeconds, 0);
        assertEq(hook.lastEventAt(key.toId()), 0, "the spike clock is explicitly zeroed at graduation");
        // and the spike still arms later, on a buyback
        assertEq(hook.liquidityVaultOf(key.toId()).code.length > 0, true);
    }

    function _rates(PoolKey memory key) internal view
        returns (uint16, uint16, uint32, uint16, uint16, uint16, uint16, uint8)
    {
        HedgeFunHook.Rates memory r = hook.rates(key.toId());
        return (r.taxBps, r.spikeBps, r.spikeSeconds, r.protocolBps, r.creatorBps, r.sweepTipBps, r.snipeBps, r.snipeSeconds);
    }

    /// The hook checks nothing about a registered vault beyond code.length != 0. Reach my own verdict on
    /// whether anything but CurveDeployer.deployVault can ever supply that address.
    function test_L13_onlyDeployVaultCanEverSupplyTheSeeder() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        HedgeFunHook.Rates memory r = hook.rates(key.toId());
        (,address treasury,,,) = factory.strategies(0);
        address token = curve.token();   // hoisted: an argument call would consume the expectRevert
        // nobody but the bound factory may register at all, with any vault argument
        vm.expectRevert(HedgeFunHook.NotFactory.selector);
        hook.registerGraduatedWithVault(key, token, address(stock), treasury, protocol, address(this), r, address(this));
        // and the registered seeder is exactly the CREATE2 address only deployVault can reach
        address predicted = factory.curveDeployer().predictVault(bytes32(uint256(0)),
            abi.encode(address(factory), address(pm), key, token, address(stock), treasury));
        assertEq(hook.liquidityVaultOf(key.toId()), predicted);
        assertGt(predicted.code.length, 0);
    }

    /// A curve buy pays the full price for tokens the tax burns: quantify the shipped opening default.
    function test_L13_openingWindowBurnRate() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        for (uint256 s; s < 5; ++s) {
            uint256 snap = vm.snapshotState();
            vm.warp(curve.launchedAt() + s);
            (uint256 spend, uint256 out, uint256 burn) = curve.quoteBuy(10e18);
            console2.log("second", s);
            console2.log("   rate bps", curve.buyRateBps());
            console2.log("   spend   ", spend);
            console2.log("   out     ", out);
            console2.log("   burned  ", burn);
            vm.revertToState(snap);
        }
        assertEq(curve.buyRateBps(), 9900, "the launch second burns 99% of the gross purchase");
    }
}
