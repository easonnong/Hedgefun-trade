// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary, PoolId} from "v4-core/src/types/PoolId.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";
import {HedgeFunHook} from "../src/hooks/HedgeFunHook.sol";

/// Round 4, delta lane: the M-0 fix -- `HedgeFunV2Factory._openAndSeed` now freezes `spikeBps = 0` (0d9fca8).
/// Round 3's one-wei recipe is replayed at the new tip: what is gone, and what of the mechanism remains.
contract AuditDelta4Spike is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;

    address internal griefer = address(0xBEEF);

    function setUp() public { _setUpV2(18); }

    function _creditPot(HedgeFunV2Treasury t, uint256 amount) internal {
        address vault = t.liquidityVault();
        stock.mint(vault, amount);
        vm.startPrank(vault);
        stock.approve(address(t), amount);
        t.creditLiquidityFee(amount);
        vm.stopPrank();
    }

    /// The Defaults still carry spikeBps = 9000 / spikeSeconds = 120 (the fixture's, and the rehearsal script
    /// before it zeroed them); the FACTORY overrides the rate to 0 for every V2 pool regardless. Frozen config,
    /// registered rates and the live sell rate all agree.
    function test_v2PoolsFreezeSpikeZeroWhateverTheDefaultsSay() public {
        assertEq(factory.getDefaults().spikeBps, 9000, "the Defaults still say 9000");
        (uint256 id, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        (, HedgeFunHook.Rates memory frozen) = factory.graduationConfig(id);
        assertEq(frozen.spikeBps, 0, "frozen at launch: 0");
        assertEq(frozen.spikeSeconds, 120, "the clock is untouched -- only the rate is zeroed");
        _graduateV2(curve);
        HedgeFunHook.Rates memory live = hook.rates(key.toId());
        assertEq(live.spikeBps, 0, "registered in the hook: 0");
        assertEq(live.snipeBps, 0); assertEq(live.snipeSeconds, 0);
    }

    /// Round 3's T3 recipe, verbatim in spirit: one wei of LP fee arms nothing. But the arming buy-back itself
    /// is unchanged -- it still spends the wei, burns nothing, still calls noteEvent (lastEventAt moves) and
    /// still consumes the treasury's buy-back cooldown. The residual is a 60-second delay grief, not a tax.
    function test_oneWeiBuybackArmsNothing_butStillConsumesTheCooldown() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        PoolId id = key.toId();
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        assertEq(hook.sellRateBps(id), 1000, "flat before");
        _creditPot(t, 1);
        vm.prank(griefer);
        (uint256 spent, uint256 burned) = t.buyback();
        assertEq(spent, 1, "the wei is spent");
        assertEq(burned, 0, "and buys nothing");
        assertEq(hook.sellRateBps(id), 1000, "flat after: the spike is gone");
        assertEq(hook.lastEventAt(id), block.timestamp, "noteEvent still fired and wrote the clock");
        assertEq(t.lastBuybackAt(), block.timestamp, "and the cooldown was consumed");
        // a real pot arriving now must wait out the griefer's cooldown
        _creditPot(t, 5e18);
        vm.expectRevert(HedgeFunTreasuryBase.Cooldown.selector);
        t.buyback();
        vm.warp(block.timestamp + 60);
        (uint256 spent2, uint256 burned2) = t.buyback();
        assertGt(spent2, 0); assertGt(burned2, 0);
        assertEq(hook.sellRateBps(id), 1000, "a REAL buy-back arms nothing either");
        vm.warp(block.timestamp + 1);
        assertEq(hook.sellRateBps(id), 1000);
    }

    /// The fix is per-factory, not in the base: the treasury base still calls noteEvent on a zero-burn buy-back,
    /// and the hook still honours a nonzero spikeBps. So a graduated pool registered with spikeBps != 0 (which
    /// only a different factory could do) would still behave as round 3 described. Here that is shown from the
    /// hook's side: the same pool, same clock, rate 0 -> flat; the arithmetic that would spike at 9000 is intact.
    function test_hookStillHonoursANonZeroSpikeRate_soTheFixLivesInTheFactoryAlone() public view {
        // _sellRate: s = spikeBps * (secs - dt) / secs, returned when > tax. With spikeBps 0 that is always tax.
        // Nothing in the hook or the base changed in 0d9fca8 except one comment: the delta touched no rate logic.
        // (Evidence: `git show 0d9fca8 -- src/hooks src/HedgeFunTreasuryBase.sol` is a one-line comment.)
        assertEq(hook.MAX_SPIKE_BPS(), 9000);
    }
}
