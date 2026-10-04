// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";

/// @notice Change the keeper reward (`bountyBps`) in a factory's defaults, for FUTURE launches.
/// @dev One owner transaction. Every other default is read back and sent unchanged, and the readback requires
///      that nothing else moved. A treasury freezes its reward at launch, so live treasuries keep theirs, and a
///      launch quoted before this transaction must be quoted again (the defaults are part of its terms).
///      Requires OPERATOR (the factory owner), V2_FACTORY and KEEPER_REWARD_BPS.
contract SetV2KeeperReward is Script {
    error BadBinding();
    error BadReadback();

    function run() external {
        address operator = vm.envAddress("OPERATOR");
        if (operator == address(0) || msg.sender != operator) revert BadBinding();
        uint256 bps = vm.envUint("KEEPER_REWARD_BPS");
        if (bps > type(uint16).max) revert BadBinding();
        (uint16 before, uint16 afterwards) = set(operator, HedgeFunV2Factory(vm.envAddress("V2_FACTORY")), uint16(bps));
        console2.log("keeper reward bps, before", before);
        console2.log("keeper reward bps, now", afterwards);
        console2.log("simulation only unless --broadcast; live treasuries keep the reward they launched with");
    }

    function set(address operator, HedgeFunV2Factory factory, uint16 bps) public returns (uint16 before, uint16 afterwards) {
        if (address(factory).code.length == 0 || factory.owner() != operator) revert BadBinding();
        HedgeFunFactory.Defaults memory d = factory.getDefaults();
        before = d.bountyBps;
        d.bountyBps = bps;
        vm.startBroadcast(operator);
        factory.setDefaults(d);
        vm.stopBroadcast();
        if (keccak256(abi.encode(factory.getDefaults())) != keccak256(abi.encode(d))) revert BadReadback();
        afterwards = bps;
    }
}
