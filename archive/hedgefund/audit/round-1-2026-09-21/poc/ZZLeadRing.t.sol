// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {TwapRing} from "../src/str/TwapRing.sol";

/// Lead's own probe: can a griefer writing one observation per second push a 600 s window out of a
/// 1024-slot ring? Both StrategyTreasuryBase and TwapRing's own comments say a griefer can. Measure it.
contract ZZLeadRing is Test {
    using TwapRing for TwapRing.Ring;
    TwapRing.Ring private r;

    function _write(int24 t) internal { r.write(t); }

    function test_lead_griefer_one_write_per_second_cannot_starve_a_600s_window() public {
        vm.warp(1_000_000);
        _write(0);
        // a griefer flips the tick every second for well past a full ring
        for (uint256 i = 0; i < 3000; i++) {
            vm.warp(block.timestamp + 1);
            _write(int24(int256(i % 2 == 0 ? int256(100) : int256(-100))));
        }
        assertEq(r.filled, 1024, "ring is full");
        (bool ok, int24 mean) = r.meanTick(600, 0);
        assertTrue(ok, "600s window is STILL servable after 3000 seconds of one-per-second writes");
        // 600 seconds of alternating +100/-100 held one second each, mean is 0 with the negative-rounding fix
        assertEq(mean, 0, "mean of a symmetric flip is exactly zero");
    }

    function test_lead_the_widest_window_this_ring_can_ever_serve_is_1023_seconds() public {
        vm.warp(1_000_000);
        _write(0);
        for (uint256 i = 0; i < 3000; i++) { vm.warp(block.timestamp + 1); _write(int24(int256(i % 2 == 0 ? int256(100) : int256(-100)))); }
        (bool ok1023,) = r.meanTick(1023, 0);
        (bool ok1024,) = r.meanTick(1024, 0);
        assertTrue(ok1023, "1023 s servable");
        assertFalse(ok1024, "1024 s is not: the ring holds 1024 samples, so 1023 intervals");
    }

    function test_lead_a_quiet_pool_serves_the_window_from_one_old_observation() public {
        vm.warp(1_000_000);
        _write(500);                       // one swap, then nothing for an hour
        vm.warp(block.timestamp + 3600);
        (bool ok, int24 mean) = r.meanTick(600, 500);
        assertTrue(ok, "one observation older than the window is enough");
        assertEq(mean, 500, "and the mean is exactly that tick");
    }
}
