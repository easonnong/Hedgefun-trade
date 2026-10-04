// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {InteractFactoryTest} from "./InteractFactory.t.sol";
import {StrategyFactory} from "../src/str/StrategyFactory.sol";
import {StrategyHook} from "../src/str/StrategyHook.sol";

/// Lead's independent check of the clean lane's headline: can a CREATOR -- who `docs/SECURITY.md` calls
/// untrusted -- leave the treasury with nothing, without the owner doing anything unusual?
contract ZZLeadSplit is InteractFactoryTest {
    /// The check is a strict `>`, in all three places, so a sum of exactly 1e4 is legal everywhere.
    function test_lead_theSplitMayLegallySumToOneHundredPercent() public {
        // The natural owner configuration: "the protocol takes 20%, a creator may take up to the rest."
        StrategyFactory.Defaults memory d = _defaults();
        d.protocolBps = 2000;
        d.maxCreatorBps = 8000;                 // 2000 + 8000 == 1e4 exactly
        vm.prank(owner); factory.setDefaults(d);            // StrategyFactory.sol:253  `> 1e4` -- passes
        assertEq(factory.getDefaults().maxCreatorBps, 8000, "the owner's configuration is accepted");

        // A creator takes the maximum the owner allowed. Nothing unusual, nothing hidden.
        StrategyFactory.Request memory q = _req("MAXCUT");
        q.creatorBps = 8000;                                // StrategyFactory.sol:363  `> d.maxCreatorBps` -- passes
        uint256 id = _launch(factory, q);

        (,, address hook,,) = factory.strategies(id);
        StrategyHook h = StrategyHook(hook);                // StrategyHook.sol:116  `> 1e4` -- passes
        assertEq(h.protocolBps(), 2000);
        assertEq(h.creatorBps(), 8000);

        // StrategyHook.distributeStock: toTreasury = rest - rest*2000/1e4 - rest*8000/1e4
        // Both divisions floor, and the exact shares sum to `rest`, so the remainder is 0 or 1 wei.
        for (uint256 rest = 1; rest < 1e24; rest = rest * 7 + 3) {
            uint256 cut = rest * 2000 / 1e4;
            uint256 mine = rest * 8000 / 1e4;
            uint256 toTreasury = rest - cut - mine;
            assertLe(toTreasury, 1, "the treasury's share of ANY sell tax is at most one wei");
        }
        // and it is immutable: the hook has no setter for either rate
        assertEq(uint256(h.protocolBps()) + h.creatorBps(), 1e4,
            "100% of every sell tax is spoken for, forever, on a strategy the launchpad lists as having a treasury");
    }

    /// The same configuration one basis point away is safe, which is what makes this a bound bug rather than
    /// a design choice: nothing warns, and the difference between the two is one `>=`.
    function test_lead_oneBasisPointLessAndTheTreasuryIsFundedNormally() public {
        StrategyFactory.Defaults memory d = _defaults();
        d.protocolBps = 2000;
        d.maxCreatorBps = 7999;
        vm.prank(owner); factory.setDefaults(d);

        StrategyFactory.Request memory q = _req("OKCUT");
        q.creatorBps = 7999;
        uint256 id = _launch(factory, q);
        (,, address hook,,) = factory.strategies(id);
        StrategyHook h = StrategyHook(hook);

        uint256 rest = 1e21;
        uint256 toTreasury = rest - rest * h.protocolBps() / 1e4 - rest * h.creatorBps() / 1e4;
        assertEq(toTreasury, 1e17, "one bp of headroom funds the treasury with 0.01% of every sell tax");
    }
}
