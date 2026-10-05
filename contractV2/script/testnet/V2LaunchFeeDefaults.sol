// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HedgeFunFactory} from "../../src/HedgeFunFactory.sol";

/// @dev Release fee choices only. Preserve every other trading, liquidity and strategy default.
library V2LaunchFeeDefaults {
    function applyTo(HedgeFunFactory.Defaults memory d) internal pure returns (HedgeFunFactory.Defaults memory) {
        d.lpFee = 2000; // 0.20% to the pool's locked position, which funds the buy-back; it was 0.30%.
        d.protocolBps = 3000; // 30% of the collected tax, from the treasury's share; it was 20%.
        d.maxCreatorBps = 1000; // Up to 10% of the collected tax, not 10% of trade volume.
        d.launchFeeCurrency = HedgeFunFactory.FeeCurrency.Native;
        d.launchFeeAmount = 0.0005 ether;
        return d;
    }
}
