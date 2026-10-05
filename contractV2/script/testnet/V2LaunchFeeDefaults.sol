// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HedgeFunFactory} from "../../src/HedgeFunFactory.sol";

/// @dev Release fee choices only. Preserve all trading, liquidity and strategy defaults.
library V2LaunchFeeDefaults {
    function applyTo(HedgeFunFactory.Defaults memory d) internal pure returns (HedgeFunFactory.Defaults memory) {
        d.maxCreatorBps = 1000; // Up to 10% of the collected tax, not 10% of trade volume.
        d.launchFeeCurrency = HedgeFunFactory.FeeCurrency.Native;
        d.launchFeeAmount = 0.0005 ether;
        return d;
    }
}
