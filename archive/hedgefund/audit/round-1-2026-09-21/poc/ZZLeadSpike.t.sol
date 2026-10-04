// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {StrategyHook} from "../src/str/StrategyHook.sol";

/// Lead's probe on the sell spike's re-arm bound.
///
/// `StrategyHook.noteEvent()` re-arms the spike only if `block.timestamp >= lastEventAt + 2 * spikeSeconds`.
/// The spike itself lasts `spikeSeconds`. So the timeline after one buy-back is:
///     [t0, t0+spikeSeconds)        spike live, decaying   -- a buy-back here IS protected
///     [t0+spikeSeconds, t0+2*S)    flat rate, and noteEvent REFUSES to re-arm
///                                  -- a buy-back here gets NO spike at all
/// README.md and the hook's own header say the spike "exists so that a buy-back cannot simply be dumped
/// into". This measures how much of the time that is actually true.
///
/// No pool, no treasury: `noteEvent` is treasury-only and `sellRateBps` is pure state, so a minimal harness
/// that impersonates the treasury isolates exactly the property under test.
contract ZZLeadSpike is Test {
    function test_lead_halfOfEveryBuybackCycleGetsNoSpikeProtection() public {
        // spikeSeconds = 120, spikeBps = 9000, taxBps = 1000 -- the repo's own defaults
        uint32 S = 120;
        StrategyHook h = _hookWith(1000, 9000, S);
        address treasury = h.treasury();

        uint256 t0 = block.timestamp;                 // the constructor arms the spike at deployment
        assertEq(h.sellRateBps(), 9000, "armed at birth");

        // --- the protected half ---
        vm.warp(t0 + 60);
        assertEq(h.sellRateBps(), 4500, "halfway through the spike: 9000 * (120-60) / 120");
        vm.prank(treasury); h.noteEvent();            // a buy-back here: refused re-arm, but the spike is live
        assertEq(h.lastEventAt(), t0, "not re-armed");
        assertEq(h.sellRateBps(), 4500, "still protected, by the spike that was already running");

        // --- the unprotected half ---
        vm.warp(t0 + 120);
        assertEq(h.sellRateBps(), 1000, "spike over: the flat rate");
        vm.prank(treasury); h.noteEvent();            // a buy-back here gets NOTHING
        assertEq(h.lastEventAt(), t0, "noteEvent refuses: t0+120 < t0+240");
        assertEq(h.sellRateBps(), 1000, "a buy-back at t0+120 is dumped into at the FLAT rate, not the spike");

        vm.warp(t0 + 239);
        vm.prank(treasury); h.noteEvent();
        assertEq(h.sellRateBps(), 1000, "still flat at t0+239 -- 120 of every 240 seconds are unprotected");

        // --- and the re-arm finally lands ---
        vm.warp(t0 + 240);
        vm.prank(treasury); h.noteEvent();
        assertEq(h.lastEventAt(), t0 + 240, "re-armed");
        assertEq(h.sellRateBps(), 9000);
    }

    /// The share of time that is unprotected is exactly spikeSeconds/(2*spikeSeconds) = 50%, whatever the
    /// parameters, and the buy-back cooldown does not change it: the cooldown only decides how MANY buy-backs
    /// land in each half, not which half they land in.
    function test_lead_theUnprotectedShareIsFiftyPercentAtEveryParameterChoice() public {
        uint32[3] memory spikes = [uint32(60), uint32(600), uint32(86400)];
        for (uint256 i; i < spikes.length; i++) {
            uint32 S = spikes[i];
            StrategyHook h = _hookWith(1000, 9000, S);
            address treasury = h.treasury();
            uint256 t0 = block.timestamp;
            uint256 unprotected;
            // sample each cycle at its two midpoints
            vm.warp(t0 + uint256(S) / 2);
            vm.prank(treasury); h.noteEvent();
            if (h.sellRateBps() == 1000) unprotected++;
            vm.warp(t0 + uint256(S) + uint256(S) / 2);
            vm.prank(treasury); h.noteEvent();
            if (h.sellRateBps() == 1000) unprotected++;
            assertEq(unprotected, 1, "exactly one of the two halves of every cycle is at the flat rate");
            vm.warp(t0);                              // reset for the next parameter
        }
    }

    // ------------------------------------------------------------------------------------------------ harness
    /// mine a salt so the hook lands on an address carrying 0x2844 in its low 14 bits, like the real deployer
    function _hookWith(uint16 taxBps, uint16 spikeBps, uint32 spikeSeconds) internal returns (StrategyHook) {
        StrategyHook.Rates memory r = StrategyHook.Rates({
            taxBps: taxBps, spikeBps: spikeBps, spikeSeconds: spikeSeconds,
            protocolBps: 2000, creatorBps: 1000, sweepTipBps: 50});
        MiniDeployer dep = new MiniDeployer();
        bytes memory args = abi.encode(
            IPoolManager(address(0x1111)), Currency.wrap(address(0xAAA1)), Currency.wrap(address(0xBBB2)),
            uint24(0), int24(60), address(0xAAA1), address(0xBBB2), address(0x7EA), address(0x9E0), address(0xC4E), r);
        bytes32 h = keccak256(abi.encodePacked(type(StrategyHook).creationCode, args));
        for (uint256 i; i < 2_000_000; i++) {
            if (uint160(vm.computeCreate2Address(bytes32(i), h, address(dep))) & 0x3FFF == 0x2844) {
                return StrategyHook(dep.deploy(bytes32(i), args));
            }
        }
        revert("no salt");
    }
}

/// stands in for HookDeployer: the hook reads `IBoundDeployer(msg.sender).factory()` as its seeder
contract MiniDeployer {
    function factory() external view returns (address) { return address(this); }
    function owner() external view returns (address) { return address(this); }
    function deploy(bytes32 salt, bytes memory args) external returns (address a) {
        bytes memory code = abi.encodePacked(type(StrategyHook).creationCode, args);
        assembly { a := create2(0, add(code, 0x20), mload(code), salt) }
        require(a != address(0), "hook deploy");
    }
}
