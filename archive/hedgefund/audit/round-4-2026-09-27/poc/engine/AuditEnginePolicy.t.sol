// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Round-4 external audit, engine lane: the POLICY boundary of HedgeFunV2EngineTreasury, end to end through a
// launched, graduated treasury (the repository's StrategyPolicyAdversarialMocks.t.sol exercises the same mocks
// against a bare staticcall, and V2StrategyEngine.t.sol covers revert / huge return / SSTORE only).
//   safe  159-byte return, gas bomb, dirty uint64 nonce word, BuybackBurn from a spot policy, buy from a sell-only
//         policy, out-of-range action word: all fail closed, none advances nonce, cooldown, epoch or balances
//   E-5   the out-of-range word is refused by abi.decode's Panic(0x21), not by the engine's own check, which is dead
//   E-7   a mutable-storage policy and a proxy policy both pass registration and launch, then change behaviour
//         under the pinned codehash (documented in STRATEGY_ENGINE.md as a governance duty; measured here)

import {HedgeFunTreasuryBase} from "../../../../src/HedgeFunTreasuryBase.sol";
import {HedgeFunV2EngineTreasury} from "../../../../src/v2/HedgeFunV2EngineTreasury.sol";
import {
    EngineConfig, IStrategyPolicy, StrategyAction, StrategyCapabilities, StrategyContext, StrategyIntent
} from "../../../../src/v2/strategy/IStrategyPolicy.sol";
import {
    GasBombStrategyPolicy, HonestBuyPolicy, HonestHoldPolicy, MalformedReturnStrategyPolicy,
    MutableStrategyPolicyProxy, StrategyPolicyMockBase
} from "../../../../test/mocks/StrategyPolicyMocks.sol";
import {AuditEngineFixture} from "./AuditEngineFixture.sol";

/// @dev spot capabilities (so it passes setEngineConfig), but the action word it returns is 64
contract SpotPolicyReturningActionWord64 is StrategyPolicyMockBase {
    function decide(StrategyContext calldata context, EngineConfig calldata, bytes32) external pure override returns (StrategyIntent memory intent) {
        intent = _intent(context, StrategyAction.Hold, 1);
        assembly ("memory-safe") {
            mstore(add(intent, 0x40), 64)
            return(intent, 0xa0)
        }
    }
}

/// @dev a well-formed 160-byte intent whose nonce word carries dirt above bit 63
contract DirtyNoncePolicy is StrategyPolicyMockBase {
    function decide(StrategyContext calldata context, EngineConfig calldata, bytes32) external pure override returns (StrategyIntent memory intent) {
        intent = _intent(context, StrategyAction.SellStock, 1e18);
        uint256 dirty = uint256(context.nonce) | (uint256(1) << 64);
        assembly ("memory-safe") {
            mstore(add(intent, 0x20), dirty)
            return(intent, 0xa0)
        }
    }
}

/// @dev the repository's MutableDecisionStrategyPolicy proposes 1 wei, which the core refuses as dust; this one
///      proposes everything so the core's caps are what bound it
contract MutableSellOrHold is StrategyPolicyMockBase {
    StrategyAction public action;
    function setAction(StrategyAction next) external { action = next; }
    function decide(StrategyContext calldata context, EngineConfig calldata, bytes32) external view override returns (StrategyIntent memory) {
        return _intent(context, action, action == StrategyAction.Hold ? 0 : type(uint256).max);
    }
}

contract BuybackBurnPolicy is StrategyPolicyMockBase {
    function decide(StrategyContext calldata context, EngineConfig calldata, bytes32) external pure override returns (StrategyIntent memory) {
        return _intent(context, StrategyAction.BuybackBurn, 1e18);
    }
}

/// @dev declares SELL only, proposes BUY
contract SellOnlyPolicyProposingBuy is StrategyPolicyMockBase {
    function policyMetadata() external pure override returns (uint32, uint32, uint256) {
        return (StrategyCapabilities.SPOT_ENGINE_V1, StrategyCapabilities.CONFIG_SCHEMA_V1, StrategyCapabilities.SPOT_SELL);
    }
    function decide(StrategyContext calldata context, EngineConfig calldata, bytes32) external pure override returns (StrategyIntent memory) {
        return _intent(context, StrategyAction.BuyStock, 50e6);
    }
}

contract AuditEnginePolicyTest is AuditEngineFixture {
    uint96 internal nonce = 100;

    function setUp() public {
        _setUpEngine(18, true);
    }

    function _launchWith(address policy, bytes32 label) internal returns (HedgeFunV2EngineTreasury t) {
        bytes32 key = _registerPolicy(policy, 400_000, label);
        t = _launchGraduated(_config(key, 5000, 500, 60, 100e6, 500e6), nonce++);
    }

    struct Snap { uint256 stock; uint256 usdg; uint256 booked; uint64 nonce_; uint256 lastAt; uint64 epoch; uint256 used; bytes32 state; uint256 lastGood; }

    function _snap(HedgeFunV2EngineTreasury t) internal view returns (Snap memory s) {
        s = Snap(stock.balanceOf(address(t)), usdg.balanceOf(address(t)), t.bookedStock(), t.strategyNonce(), t.lastStrategyAt(),
            t.turnoverEpoch(), t.turnoverInEpoch(), t.policyState(), t.lastGoodPrice());
    }

    function _assertUnchanged(HedgeFunV2EngineTreasury t, Snap memory s) internal view {
        Snap memory n = _snap(t);
        assertEq(n.stock, s.stock); assertEq(n.usdg, s.usdg); assertEq(n.booked, s.booked);
        assertEq(n.nonce_, s.nonce_); assertEq(n.lastAt, s.lastAt); assertEq(n.epoch, s.epoch);
        assertEq(n.used, s.used); assertEq(n.state, s.state); assertEq(n.lastGood, s.lastGood);
    }

    function test_safe_malformed159ByteReturnFailsClosed() public {
        HedgeFunV2EngineTreasury t = _launchWith(address(new MalformedReturnStrategyPolicy()), "159");
        Snap memory s = _snap(t);
        vm.expectRevert(HedgeFunV2EngineTreasury.BadPolicyReturn.selector);
        t.execute();
        _assertUnchanged(t, s);
    }

    function test_safe_gasBombIsBoundedByTheManifestGasAndFailsClosed() public {
        HedgeFunV2EngineTreasury t = _launchWith(address(new GasBombStrategyPolicy()), "bomb");
        Snap memory s = _snap(t);
        uint256 g0 = gasleft();
        vm.expectRevert(HedgeFunV2EngineTreasury.PolicyFailure.selector);
        t.execute();
        assertLt(g0 - gasleft(), 1_000_000, "the bomb cost about the manifest's 400k, not the block");
        _assertUnchanged(t, s);
        // preview is a view over the same call and fails the same way
        vm.expectRevert(HedgeFunV2EngineTreasury.PolicyFailure.selector);
        t.preview();
    }

    /// E-5: the mock's own comment says "a spot engine must reject this raw action word before attempting an enum
    /// ABI decode". The engine decodes first, so the refusal is Solidity's decoder validation -- which reverts
    /// with NO data at all (not even a Panic) -- and `_basicIntentValid`'s `uint8(action) <= BuybackBurn` can
    /// never be false. Fails closed either way; a keeper just sees an empty revert.
    function test_E5_outOfRangeActionWordIsRefusedByAnEmptyDecodeRevertNotByTheEngine() public {
        HedgeFunV2EngineTreasury t = _launchWith(address(new SpotPolicyReturningActionWord64()), "word64");
        Snap memory s = _snap(t);
        vm.expectRevert(bytes(""));
        t.execute();
        _assertUnchanged(t, s);
    }

    function test_safe_dirtyNonceWordIsRefusedByDecode() public {
        HedgeFunV2EngineTreasury t = _launchWith(address(new DirtyNoncePolicy()), "dirty");
        Snap memory s = _snap(t);
        vm.expectRevert();
        t.execute();
        _assertUnchanged(t, s);
    }

    function test_safe_buybackBurnIntentFromASpotPolicyIsBadIntent() public {
        HedgeFunV2EngineTreasury t = _launchWith(address(new BuybackBurnPolicy()), "bb");
        Snap memory s = _snap(t);
        vm.expectRevert(HedgeFunV2EngineTreasury.BadIntent.selector);
        t.execute();
        _assertUnchanged(t, s);
    }

    function test_safe_sellOnlyPolicyCannotBuy() public {
        HedgeFunV2EngineTreasury t = _launchWith(address(new SellOnlyPolicyProposingBuy()), "sellonly");
        usdg.mint(address(t), 10 * _stockValue(t, PRICE));   // genuinely under-weight, so the direction check passes
        Snap memory s = _snap(t);
        vm.expectRevert(HedgeFunV2EngineTreasury.BadIntent.selector);
        t.execute();
        _assertUnchanged(t, s);
    }

    /// E-7a: runtime-codehash pinning does not pin semantics. Same address, same codehash, different decisions.
    function test_E7_mutableStoragePolicyChangesBehaviourUnderThePinnedCodehash() public {
        MutableSellOrHold policy = new MutableSellOrHold();
        policy.setAction(StrategyAction.SellStock);
        HedgeFunV2EngineTreasury t = _launchWith(address(policy), "mutable");
        bytes32 pinned = t.policyRuntimeCodeHash();
        t.execute();                                            // sells one bounded chunk
        assertEq(t.strategyNonce(), 1);
        vm.warp(block.timestamp + 60);
        _market(PRICE);
        policy.setAction(StrategyAction.Hold);                  // anyone; the policy has no owner
        assertEq(address(policy).codehash, pinned);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();                                            // the strategy is now switched off from outside
        // and the bound still holds when it is switched back on: at most one capped, in-band trade per cooldown
        policy.setAction(StrategyAction.SellStock);
        t.execute();
        assertLe(t.turnoverInEpoch(), 200e6);
    }

    /// E-7b: a delegating proxy passes registerPolicy (its fallback answers policyMetadata), setEngineConfig and the
    /// constructor, then is re-pointed after launch.
    function test_E7_proxyPolicyRegistersLaunchesAndIsRepointed() public {
        HonestHoldPolicy hold = new HonestHoldPolicy();
        HonestBuyPolicy buy = new HonestBuyPolicy();
        MutableStrategyPolicyProxy proxy = new MutableStrategyPolicyProxy(address(hold));
        HedgeFunV2EngineTreasury t = _launchWith(address(proxy), "proxy");
        assertEq(t.policyImplementation(), address(proxy));
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();                                            // hold
        proxy.setImplementation(address(buy));                  // anyone
        usdg.mint(address(t), 10 * _stockValue(t, PRICE));
        // HonestBuyPolicy asks for 1 wei of USDG; the core refuses dust below minLot, so still NotDue -- the point is
        // that the delegated code changed under a codehash the treasury still considers valid
        (bool due, StrategyAction action,) = t.preview();
        assertFalse(due);
        assertEq(uint256(action), uint256(StrategyAction.Hold));
        assertEq(address(proxy).codehash, t.policyRuntimeCodeHash());
    }
}
