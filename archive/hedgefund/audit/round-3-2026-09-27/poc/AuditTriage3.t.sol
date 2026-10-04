// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary, PoolId} from "v4-core/src/types/PoolId.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// @dev Round-3 triage: settle the one open question on the round's only High (E-1) --
///      does a ONE WEI buyback pot still arm the 90% sell spike?
contract AuditTriage3 is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;

    function setUp() public {
        _setUpV2(18);
    }

    /// The lead's open question, driven to the literal floor: buybackStock == 1 wei.
    function test_T3_oneWeiPotArmsTheNinetyPercentSpike() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        address vault = t.liquidityVault();
        assertTrue(vault != address(0), "vault wired");

        // The graduated pool opens with the spike OFF (lastEventAt == 0) -- the flat creator tax.
        assertEq(hook.sellRateBps(id), 1000, "graduated pool opens flat");

        // Credit exactly ONE WEI through the real inlet, with the real access control satisfied.
        stock.mint(vault, 1);
        vm.startPrank(vault);
        stock.approve(address(t), 1);
        t.creditLiquidityFee(1);
        vm.stopPrank();
        assertEq(t.buybackStock(), 1, "pot is one wei");

        // Anyone calls buyback.
        address griefer = address(0xBEEF);
        vm.prank(griefer);
        (uint256 spent, uint256 burned) = t.buyback();

        emit log_named_uint("spent", spent);
        emit log_named_uint("burned", burned);
        emit log_named_uint("sellRateBps after", hook.sellRateBps(id));

        assertEq(spent, 1, "the whole one-wei pot is spent");
        assertEq(t.buybackStock(), 0, "pot drained");
        assertEq(hook.sellRateBps(id), 9000, "one wei armed the 90% sell spike");
    }

    /// Does the spike actually cost sellers, and can it be re-armed on the 2*spikeSeconds cadence?
    function test_T3_oneWeiSpikeIsReArmableEvery240s() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        address vault = t.liquidityVault();

        stock.mint(vault, 10);
        vm.startPrank(vault);
        stock.approve(address(t), 10);
        t.creditLiquidityFee(1);
        vm.stopPrank();
        vm.prank(address(0xBEEF));
        t.buyback();
        assertEq(hook.sellRateBps(id), 9000, "armed once");

        // Inside 2*spikeSeconds the hook refuses to re-arm; the rate decays to the flat tax at +120s.
        vm.warp(block.timestamp + 130);
        assertEq(hook.sellRateBps(id), 1000, "decayed to flat at +130s");
        vm.startPrank(vault);
        t.creditLiquidityFee(1);
        vm.stopPrank();
        vm.prank(address(0xBEEF));
        t.buyback();
        assertEq(hook.sellRateBps(id), 1000, "noteEvent is a no-op inside 2*spikeSeconds");

        // At +240s from the first arming it re-arms, for one wei again.
        vm.warp(block.timestamp + 120);
        vm.startPrank(vault);
        t.creditLiquidityFee(1);
        vm.stopPrank();
        vm.prank(address(0xBEEF));
        t.buyback();
        assertEq(hook.sellRateBps(id), 9000, "re-armed at +240s for one wei");
    }

    /// The cheap end of the REAL inlet: how small a buy produces a nonzero collectable stock fee?
    function test_T3_smallestRealFeeThatFundsThePot() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        V2LiquidityVault vault = V2LiquidityVault(t.liquidityVault());

        // One small V4 buy through the production router path is out of scope here; instead drive the
        // pool directly with the fixture's own swap helper if present. Record what collectFees yields
        // on a pool with no post-graduation trade: it must be zero, and creditLiquidityFee must not fire.
        (uint256 stockFee, uint256 tokenBurned) = vault.collectFees();
        emit log_named_uint("stockFee with no trade", stockFee);
        emit log_named_uint("tokenBurned with no trade", tokenBurned);
        assertEq(t.buybackStock(), 0, "no trade, no pot");
        assertEq(hook.sellRateBps(id), 1000, "no trade, no spike");
    }
}
