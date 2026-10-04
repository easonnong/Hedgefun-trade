// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {CoveredCallDesk} from "../src/options/CoveredCallDesk.sol";
import {ITradingCalendar} from "../src/interfaces/ITradingCalendar.sol";
import {IOwned} from "../src/interfaces/IOwned.sol";

interface ISafeLike {
    function getThreshold() external view returns (uint256);
    function getOwners() external view returns (address[] memory);
}

/// One `CoveredCallDesk` for the protocol Safe, against USDG and the production calendar. Deploying it lists
/// nothing and allows nobody: the desk is inert until the Safe signs the setup batch that `tools/cc_desk_batch.py
/// setup` builds (list, setWriter, setBuyer). The broadcaster holds no role afterwards; `owner` is the Safe from the
/// constructor, so there is no ownership transfer to forget.
///
///   forge script script/DeployCoveredCallDesk.s.sol --tc DeployCoveredCallDesk --rpc-url publicnode                 # simulate
///   forge script script/DeployCoveredCallDesk.s.sol --tc DeployCoveredCallDesk --rpc-url publicnode --broadcast \
///     --account <deployer keystore> --sender <deployer>
///
/// Every input is checked before the first broadcast, and every immutable is read back after it. The three addresses
/// are the ones in docs/ADDRESSES.md; the script refuses any other chain.
contract DeployCoveredCallDesk is Script {
    address constant SAFE = 0x2910117dd2cB431173Ae9Fb6eAF30726321d1693;
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address constant CALENDAR = 0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5;
    uint256 constant RH = 4663;
    // a Saturday 16:00 ET: 2026-10-03 20:00 UTC. The calendar must call it closed, or it is not the production one.
    uint256 constant A_SATURDAY = 1791057600;
    // a Friday 16:00 ET: 2026-10-09 20:00 UTC. The calendar must call it open.
    uint256 constant A_FRIDAY = 1791576000;

    function check() public view {
        require(block.chainid == RH, "not Robinhood Chain");
        require(SAFE.code.length != 0 && ISafeLike(SAFE).getThreshold() >= 2 && ISafeLike(SAFE).getOwners().length >= 3, "SAFE is not a multisig");
        require(USDG.code.length != 0 && IERC20Metadata(USDG).decimals() == 6, "USDG decimals");
        require(CALENDAR.code.length != 0 && IOwned(CALENDAR).owner() == SAFE, "calendar owner is not the Safe");
        require(ITradingCalendar(CALENDAR).isClosed(A_SATURDAY) && !ITradingCalendar(CALENDAR).isClosed(A_FRIDAY), "calendar does not behave like the production one");
    }

    function readBack(CoveredCallDesk desk) public view {
        require(desk.owner() == SAFE, "read-back: owner");
        require(address(desk.usdg()) == USDG && desk.usdgDecimals() == 6, "read-back: usdg");
        require(address(desk.calendar()) == CALENDAR, "read-back: calendar");
        require(desk.exerciseWindow() == 2 hours && desk.nextId() == 1 && !desk.paused(), "read-back: initial state");
        (address feed,,) = desk.listings(USDG);
        require(!desk.isWriter(SAFE) && feed == address(0), "read-back: must start empty");
    }

    function run() external returns (CoveredCallDesk desk) {
        check();
        vm.startBroadcast();
        desk = new CoveredCallDesk(SAFE, IERC20(USDG), ITradingCalendar(CALENDAR));
        vm.stopBroadcast();
        readBack(desk);

        console2.log("CoveredCallDesk      ", address(desk));
        console2.log("owner (Safe)         ", desk.owner());
        console2.log("usdg                 ", address(desk.usdg()));
        console2.log("calendar             ", address(desk.calendar()));
        console2.log("runtime bytes        ", address(desk).code.length);
        console2.log("exerciseWindow (s)   ", desk.exerciseWindow());
        console2.log("");
        console2.log("NEXT  1. verify: forge verify-contract --verifier sourcify --chain-id 4663 <desk> src/options/CoveredCallDesk.sol:CoveredCallDesk");
        console2.log("      2. record the address in emergency/addresses.json and docs/ADDRESSES.md");
        console2.log("      3. python3 tools/cc_desk_batch.py setup --desk <desk> --buyer <market maker> --stocks NVDA  -> Safe signs");
    }
}
