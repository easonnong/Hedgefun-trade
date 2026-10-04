// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";

interface IV3Factory { function getPool(address, address, uint24) external view returns (address); }
interface IPool { function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool); }
interface IERC20Min { function balanceOf(address) external view returns (uint256); }

/// Which stocks can the V3 treasury actually be listed against? Two hard gates, both structural:
///   - the pool must exist and hold real USDG;
///   - its observation ring must serve the 600s TWAP window (PoolTrader refuses shorter at construction), and
///     that same ring is what makes weekend trading possible at all, since the equity feed is frozen then.
contract V3Survey is Script {
    address constant F    = 0x1f7d7550B1b028f7571E69A784071F0205FD2EfA;
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    uint16  constant NEED = 660;                                    // TWAP_WINDOW + 60

    function run() external view {
        string memory raw = vm.readFile("data/rh_stock_tokens.json");
        string[] memory syms = vm.parseJsonKeys(raw, ".stock_tokens");
        uint24[4] memory fees = [uint24(100), 500, 3000, 10000];

        console2.log("sym | fee | ring | USDG in pool | pool");
        uint256 usable;
        for (uint256 i; i < syms.length; i++) {
            address t = vm.parseJsonAddress(raw, string.concat(".stock_tokens.", syms[i]));
            for (uint256 j; j < 4; j++) {
                address p = IV3Factory(F).getPool(USDG, t, fees[j]);
                if (p == address(0)) continue;
                uint256 usdg = IERC20Min(USDG).balanceOf(p);
                if (usdg < 50_000e6) continue;                       // not a real book
                (,,, uint16 card,,,) = IPool(p).slot0();
                console2.log(string.concat(syms[i], " | ", vm.toString(fees[j]), " | ", vm.toString(card),
                    card >= NEED ? " | OK   | " : " | SHORT| ", vm.toString(usdg / 1e6)));
                if (card >= NEED) usable++;
            }
        }
        console2.log("usable pools:", usable);
    }
}
