// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {InteractFactoryTest} from "./InteractFactory.t.sol";
import {StrategyFactory} from "../src/str/StrategyFactory.sol";
import {StrategyHook} from "../src/str/StrategyHook.sol";

/// Lead's probe on `Defaults`: (a) is the mined hook salt an accidental restatement guard, and
/// (b) which Defaults fields does `_setDefaults` actually bound?
contract ZZLeadDefaults is InteractFactoryTest {
    // (a) THE FALSIFICATION. If the owner moves ANY default after a creator mined a salt, does the
    //     creator's launch execute with substituted parameters, or does it revert?
    function test_lead_movingADefaultUnderAPendingLaunchREVERTS_itDoesNotSubstitute() public {
        StrategyFactory.Request memory q = _req("PEND");
        (,,,, uint256 open,) = factory.listings(q.stock);
        q.expectedOpenPriceE18 = open;
        bytes32 salt = _mineSalt(factory, q);                    // creator mines against today's defaults

        // owner moves one unrestated default: the protocol's cut, 20% -> 100%
        StrategyFactory.Defaults memory d = _defaults();
        d.protocolBps = 10_000;
        d.maxCreatorBps = 0;
        vm.prank(owner); factory.setDefaults(d);

        // the creator's already-signed request, unchanged, with the salt they mined
        q.creatorBps = 0;                                        // else BadRequest on maxCreatorBps, a different error
        vm.prank(creator);
        vm.expectRevert(bytes("hook deploy"));   // CREATE2 swallows the constructor's BadConfig
        factory.launch(q, salt);
    }

    // (b) protocolBps = 100% IS a constructible configuration. Nothing stops the owner setting it,
    //     and a strategy launched under it funds its treasury with exactly nothing, forever.
    function test_lead_aTreasuryThatCanNeverBeFundedIsAValidConfiguration() public {
        StrategyFactory.Defaults memory d = _defaults();
        d.protocolBps = 10_000;
        d.maxCreatorBps = 0;
        vm.prank(owner); factory.setDefaults(d);                 // accepted: 10000 + 0 is not > 1e4

        StrategyFactory.Request memory q = _req("HONEY");
        q.creatorBps = 0;
        uint256 id = _launch(factory, q);
        (,, address hook,,) = factory.strategies(id);
        assertEq(StrategyHook(hook).protocolBps(), 10_000, "100% of the stock-denominated tax to the protocol");
        assertEq(StrategyHook(hook).creatorBps(), 0);
        // README: "protocolBps to the protocol, creatorBps to the creator, and the remainder to the treasury"
        assertEq(1e4 - StrategyHook(hook).protocolBps() - StrategyHook(hook).creatorBps(), 0,
                 "the remainder the README promises the treasury is exactly zero, immutably");
    }

    // (c) spikeSeconds is uint32 and completely unbounded. A ~90% sell tax that decays over 136 years
    //     is a valid launch.
    function test_lead_spikeSecondsIsUnbounded_soAPermanentNinetyPercentSellTaxIsAValidLaunch() public {
        StrategyFactory.Defaults memory d = _defaults();
        d.spikeBps = 9000;                       // the enforced maximum
        d.spikeSeconds = type(uint32).max;       // 4,294,967,295 s = 136 years. Not checked anywhere.
        vm.prank(owner); factory.setDefaults(d); // accepted

        uint256 id = _launch(factory, _req("TRAP"));
        (,, address hook,,) = factory.strategies(id);
        StrategyHook h = StrategyHook(hook);

        assertEq(h.sellRateBps(), 9000, "at launch: 90% sell tax");
        vm.warp(block.timestamp + 365 days);
        assertEq(h.sellRateBps(), 8933, "one year later, still 89.33%");
        vm.warp(block.timestamp + 10 * 365 days);
        assertEq(h.sellRateBps(), 8273, "eleven years later, still 82.73%");
    }

    // (d) buybackCooldown is uint32 and unbounded too: a strategy whose buy-back can never fire twice.
    function test_lead_buybackCooldownIsUnbounded() public {
        StrategyFactory.Defaults memory d = _defaults();
        d.buybackCooldown = type(uint32).max;
        vm.prank(owner); factory.setDefaults(d);      // accepted, no bound anywhere
        assertEq(factory.getDefaults().buybackCooldown, type(uint32).max, "136 years between buy-backs is a valid default");
        uint256 id = _launch(factory, _req("SLOW"));  // and it launches, freezing that into the treasury
        (, address treasury,,,) = factory.strategies(id);
        assertTrue(treasury != address(0));
    }
}
