// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {TestnetV2EthBridge} from "../script/testnet/TestnetV2EthBridge.s.sol";
import {TestnetV2EthMarket} from "../script/testnet/TestnetV2EthMarket.s.sol";

contract EthBridgeFeatureHarness is TestnetV2EthBridge {
    function featureKind(string calldata feature) external pure returns (uint8) {
        return _featureKind(feature);
    }
}

contract EthMarketFeatureHarness is TestnetV2EthMarket {
    function featureKind(string calldata feature) external pure returns (uint8) {
        return _featureKind(feature);
    }
}

contract TestnetV2ConsumerFeatureGateTest is Test {
    EthBridgeFeatureHarness private bridge;
    EthMarketFeatureHarness private market;

    function setUp() public {
        bridge = new EthBridgeFeatureHarness();
        market = new EthMarketFeatureHarness();
    }

    function test_consumersAcceptLegacyAndV2CoreBooks() public view {
        _assertKind("v2-creator-selected-stock-fees-v1", 1);
        _assertKind("v2-two-sided-stock-fees-v1", 2);
        _assertKind("v2-creator-selected-stock-fees-v2", 3);
        _assertKind("v2-two-sided-stock-fees-v2", 4);
    }

    function test_consumersRejectFreshWalletAndUnknownBooks() public view {
        _assertKind("v2-creator-selected-fresh-wallet-v2", 0);
        _assertKind("v2-two-sided-stock-fees-v3", 0);
        _assertKind("", 0);
    }

    function _assertKind(string memory feature, uint8 expected) private view {
        assertEq(bridge.featureKind(feature), expected);
        assertEq(market.featureKind(feature), expected);
    }
}
