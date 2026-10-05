// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {ITradingCalendar} from "./interfaces/ITradingCalendar.sol";

/// @notice The calendar of an asset that trades around the clock: never closed by a schedule.
/// @dev `TradingCalendar` is the US equity session, shut every weekend. A listing of wrapped ETH needs the other
///      kind. The one thing an owner can do here is halt: while halted the asset's oracle serves no price, so every
///      treasury on that listing stops trading and stops buying back, exactly as on a day the owner of the equity
///      calendar forces shut. It is never a scheduled closure, so the closure-only pool band never applies.
///      A trading date is a UTC day.
contract AlwaysOpenCalendar is Ownable2Step, ITradingCalendar {
    bool public halted;

    event HaltedSet(bool halted);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function setHalted(bool value) external onlyOwner {
        halted = value;
        emit HaltedSet(value);
    }

    function isClosed(uint256) external view returns (bool) { return halted; }

    function isScheduledClosure(uint256) external pure returns (bool) { return false; }

    function tradingDate(uint256 ts) external pure returns (uint256) { return ts / 1 days; }
}
