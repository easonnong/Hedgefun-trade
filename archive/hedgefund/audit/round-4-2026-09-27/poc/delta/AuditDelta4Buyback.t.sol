// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";

/// Round 4, delta lane: `HedgeFunTreasuryBase.buyback` now calls `_notePrice(p)` when the oracle is live
/// (d5218ee). The base is shared with the V1 `HedgeFunTreasury`, so this is the one delta line that changes
/// V1 semantics for any future V1 re-deployment. Questions: can a buy-back advance `lastGoodPrice` in a way the
/// stock-trading paths trust wrongly; can it be refreshed with a stale value; does it extend the five-day window.
contract AuditDelta4Buyback is V2FactoryFixture {
    function setUp() public { _setUpV2(18); }

    function _creditPot(HedgeFunV2Treasury t, uint256 amount) internal {
        address vault = t.liquidityVault();
        stock.mint(vault, amount);
        vm.startPrank(vault);
        stock.approve(address(t), amount);
        t.creditLiquidityFee(amount);
        vm.stopPrank();
    }

    function _refreshFeeds() internal { stockFeed.set(100e8); usdgFeed.set(1e8); }

    /// The cache moves only on a SUCCESSFUL buy-back made while `tryPrice()` is live; a closed-market buy-back
    /// sized off the cache leaves it alone. The value written is a fresh Chainlink print, never a stale one.
    function test_cacheMovesOnlyOnALiveSuccessfulBuyback() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        uint256 t0 = block.timestamp;
        _graduateV2(curve);                                   // graduation's own book() noted the price at t0
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        assertEq(t.lastGoodPriceAt(), t0, "booked at graduation");
        _creditPot(t, 20e18);

        // four days later, feed fresh: a buy-back refreshes the cache (this is the new behaviour)
        vm.warp(t0 + 4 days); _refreshFeeds();
        (bool live,) = oracle.tryPrice(); assertTrue(live);
        t.buyback();
        assertEq(t.lastGoodPriceAt(), t0 + 4 days, "a live buy-back refreshed the cache");

        // 27 hours on, the feed is past its 26-hour age limit: tryPrice is false, the buy-back sizes off the cache
        vm.warp(t0 + 4 days + 27 hours);
        (live,) = oracle.tryPrice(); assertFalse(live, "feed aged out");
        (uint256 spent,) = t.buyback();
        assertGt(spent, 0, "sized off the 27-hour-old cache, well inside MAX_SIZING_AGE");
        assertEq(t.lastGoodPriceAt(), t0 + 4 days, "a closed-market buy-back CANNOT refresh the cache");
        // Under the pre-delta base the only writer was a rule action, so the cache would still read t0 here,
        // 5 days + 3 hours old, and this buy-back would have reverted Unhealthy.
        assertGt(block.timestamp - t0, t.MAX_SIZING_AGE(), "the old cache would have expired");

        // the window is not extendable from inside a closure: keep the feed stale and walk past five days
        vm.warp(t0 + 4 days + 5 days + 1);
        vm.expectRevert(HedgeFunTreasuryBase.Unhealthy.selector);
        t.buyback();
    }

    /// A buy-back that reverts after the note (here: Cooldown before it, dust NotDue after it) writes nothing.
    function test_aRevertedBuybackWritesNoCache() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        _graduateV2(curve);
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        _creditPot(t, 20e18);
        vm.warp(block.timestamp + 3 days); _refreshFeeds();
        t.buyback();
        uint256 at = t.lastGoodPriceAt();
        vm.warp(block.timestamp + 10); _refreshFeeds();
        vm.expectRevert(HedgeFunTreasuryBase.Cooldown.selector);
        t.buyback();
        assertEq(t.lastGoodPriceAt(), at, "Cooldown: not written");
    }

    /// The new writer is gated by `tryPrice()` alone -- feed age, calendar, oraclePaused -- and NOT by `health()`,
    /// which every previous writer of the cache went through. A pool sitting outside the deviation gate does not
    /// stop the buy-back from noting the feed's price. Consequence-free today: the only reader of `lastGoodPrice`
    /// in `src/` is the buy-back's own sizing fallback (grep: HedgeFunTreasuryBase.sol:465), and the value is a
    /// signed Chainlink print either way. Recorded because it is a widened writer on a base that V1 shares.
    function test_cacheIsWrittenEvenWhileHealthIsShut() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        _graduateV2(curve);
        HedgeFunV2Treasury t = HedgeFunV2Treasury(curve.treasury());
        _creditPot(t, 20e18);
        vm.warp(block.timestamp + 61); _refreshFeeds();
        // shove the mocked stock/USDG venue 20% off the oracle: health() shuts, tryPrice() does not care
        uint256 scale = 1e18 * 1e18 / 1e6;
        stockPool.setSqrt(uint160(Math.sqrt(Math.mulDiv(120e18, 1 << 192, scale))));
        (bool healthy,) = t.health(); assertFalse(healthy, "deviation gate shut");
        (bool live, uint256 p) = oracle.tryPrice(); assertTrue(live);
        t.buyback();
        assertEq(t.lastGoodPriceAt(), block.timestamp, "written past the shut gate");
        assertEq(t.lastGoodPrice(), p, "with the feed's own price, not the pool's");
    }
}
