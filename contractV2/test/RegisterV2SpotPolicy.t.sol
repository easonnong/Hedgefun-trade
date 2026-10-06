// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {PoolManager} from "v4-core/src/PoolManager.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {EngineConfig, PolicyManifest} from "../src/v2/strategy/IStrategyPolicy.sol";
import {V2RebalancePolicy} from "../src/v2/strategy/V2RebalancePolicy.sol";
import {MockToken, MockV3Factory} from "./mocks/Mocks.sol";
import {V2MainnetCore} from "../script/mainnet/V2MainnetCore.sol";
import {DeployV2MainnetCore} from "../script/mainnet/DeployV2MainnetCore.s.sol";
import {RegisterV2SpotPolicy} from "../script/mainnet/RegisterV2SpotPolicy.s.sol";
import {RegisterV2UpgradeableKinds} from "../script/RegisterV2UpgradeableKinds.s.sol";
import {SafeLike, WrappedNative, MainnetCoreProbe} from "./DeployV2MainnetCore.t.sol";

/// Offline: the mainnet core at the chain's pinned addresses, then the spot engine's policy registered by its script.
contract RegisterV2SpotPolicyTest is Test {
    bytes32 internal constant DEPENDENCIES = keccak256("spot policy test: dependency manifest");
    bytes32 internal constant AUDIT = keccak256("spot policy test: audit manifest");

    address deployer = makeAddr("mainnet deployer");
    address creator = makeAddr("a creator");
    SafeLike owner;
    SafeLike protocol;
    WrappedNative weth;
    HedgeFunV2Factory factory;
    V2TreasuryDeployer registry;
    RegisterV2SpotPolicy script;
    uint8 engineKind;

    function setUp() public {
        vm.chainId(4663);
        MainnetCoreProbe probe = new MainnetCoreProbe();
        _deployAt(bytes.concat(type(PoolManager).creationCode, abi.encode(address(this))), probe.PM());
        vm.etch(probe.V3_FACTORY(), address(new MockV3Factory()).code);
        _deployAt(bytes.concat(type(MockToken).creationCode, abi.encode("USDG", uint8(6))), probe.USDG());
        owner = new SafeLike(2, 3);
        protocol = new SafeLike(3, 5);
        weth = new WrappedNative();
        V2MainnetCore.Deployed memory x = new DeployV2MainnetCore().deploy(
            deployer, V2MainnetCore.Roles(address(owner), address(protocol), address(weth)), true, probe.defaultsHash(), 7931, 0
        );
        factory = x.factory;
        registry = x.treasury;
        // the runbook's order: kinds 1 and 2 first, then kind 2's policy
        RegisterV2UpgradeableKinds.Kinds memory k = new RegisterV2UpgradeableKinds().register(deployer, factory);
        engineKind = k.engine;
        assertEq(engineKind, 2);
        script = new RegisterV2SpotPolicy();
    }

    function _deployAt(bytes memory creation, address where) internal {
        vm.etch(where, creation);
        (bool ok, bytes memory runtime) = where.call("");
        require(ok, "constructor");
        vm.etch(where, runtime);
    }

    /// schema 1, as the end-to-end suite configures the spot engine
    function _spotConfig(bytes32 policyKey) internal pure returns (EngineConfig memory c) {
        c.schema = 1;
        c.engineVersion = 1;
        c.policyKey = policyKey;
        c.words[0] = bytes32(uint256(5000) | uint256(250) << 16 | uint256(600) << 32 | uint256(5000) << 64);
        c.words[1] = bytes32(uint256(2_000e6));
        c.words[2] = bytes32(uint256(10_000e6));
    }

    function test_pinnedRuntimeHashIsThisSourcesPolicy() public {
        assertEq(keccak256(type(V2RebalancePolicy).runtimeCode), script.POLICY_RUNTIME_CODE_HASH());
        assertEq(address(new V2RebalancePolicy()).codehash, script.POLICY_RUNTIME_CODE_HASH());
    }

    function test_registersTheSpotEnginePolicy_asTheTestnetDeploymentsDo_andKind2CanBeConfiguredWithIt() public {
        // Before: kind 2 exists but no schema-1 policy is registered, so no spot engine can be configured.
        vm.prank(creator);
        vm.expectRevert();
        registry.setEngineConfig("SPOT", 1, engineKind, _spotConfig(keccak256("not a registered policy")));

        RegisterV2SpotPolicy.Registration memory r = script.register(deployer, factory, DEPENDENCIES, AUDIT);
        PolicyManifest memory m = registry.policy(r.policyKey);
        assertEq(m.implementation, r.policy);
        assertEq(m.runtimeCodeHash, script.POLICY_RUNTIME_CODE_HASH());
        assertEq(m.engineVersion, 1);
        assertEq(m.configSchema, 1, "the spot engine's schema");
        assertEq(m.capabilities, 3, "spot buy and sell");
        assertEq(m.maxGas, 150_000, "as DeployV2FeeUpgradeTestnet registers it");
        assertEq(m.maxReturnBytes, 160);
        assertTrue(m.enabledForNewLaunches);
        assertEq(registry.policyDependencyManifestHash(r.policyKey), DEPENDENCIES);
        assertEq(registry.policyAuditManifestHash(r.policyKey), AUDIT);
        (, uint32 schema,,) = registry.kindManifest(engineKind);
        assertEq(schema, m.configSchema, "the policy is the one kind 2 asks for");

        // The readback the verifier runs.
        script.check(factory, r, DEPENDENCIES, AUDIT);

        // After: a creator can bind a kind-2 launch to it.
        vm.prank(creator);
        registry.setEngineConfig("SPOT", 1, engineKind, _spotConfig(r.policyKey));
        assertEq(registry.strategyKindOf(keccak256(abi.encode("SPOT", creator, uint96(1)))), engineKind);
        assertEq(registry.kindCount(), 3, "a policy is not a kind");
    }

    function test_refusesEveryOtherChain() public {
        uint256[3] memory chains = [uint256(46630), 31337, 1];
        for (uint256 i; i < chains.length; ++i) {
            vm.chainId(chains[i]);
            vm.expectRevert(abi.encodeWithSelector(RegisterV2SpotPolicy.WrongChain.selector, chains[i]));
            script.register(deployer, factory, DEPENDENCIES, AUDIT);
        }
    }

    function test_refusesAnOperatorWhoIsNotTheOwner_andEmptyManifests() public {
        vm.expectRevert(RegisterV2SpotPolicy.BadBinding.selector);
        script.register(address(owner), factory, DEPENDENCIES, AUDIT);
        vm.expectRevert(RegisterV2SpotPolicy.BadBinding.selector);
        script.register(deployer, factory, bytes32(0), AUDIT);
        vm.expectRevert(RegisterV2SpotPolicy.BadBinding.selector);
        script.register(deployer, factory, DEPENDENCIES, bytes32(0));
        assertEq(registry.kindCount(), 3);
    }

    /// The readback is of this registration: another key, another policy, other manifests or a policy the owner
    /// registered by hand with other limits are all refused.
    function test_readbackRefusesAnythingButThisRegistration() public {
        RegisterV2SpotPolicy.Registration memory r = script.register(deployer, factory, DEPENDENCIES, AUDIT);

        vm.expectRevert(RegisterV2SpotPolicy.BadReadback.selector);
        script.check(factory, RegisterV2SpotPolicy.Registration(keccak256("another key"), r.policy), DEPENDENCIES, AUDIT);
        vm.expectRevert(RegisterV2SpotPolicy.BadReadback.selector);
        script.check(factory, RegisterV2SpotPolicy.Registration(r.policyKey, address(new V2RebalancePolicy())), DEPENDENCIES, AUDIT);
        vm.expectRevert(RegisterV2SpotPolicy.BadReadback.selector);
        script.check(factory, r, keccak256("other dependencies"), AUDIT);
        vm.expectRevert(RegisterV2SpotPolicy.BadReadback.selector);
        script.check(factory, r, DEPENDENCIES, keccak256("other audit"));

        // The owner's direct call with the tradable-percent limit: a valid registration, not this script's.
        V2RebalancePolicy other = new V2RebalancePolicy();
        vm.prank(deployer);
        bytes32 otherKey = registry.registerPolicy(address(other), 400_000, 160, DEPENDENCIES, AUDIT);
        assertTrue(registry.policy(otherKey).enabledForNewLaunches);
        vm.expectRevert(RegisterV2SpotPolicy.BadReadback.selector);
        script.check(factory, RegisterV2SpotPolicy.Registration(otherKey, address(other)), DEPENDENCIES, AUDIT);

        script.check(factory, r, DEPENDENCIES, AUDIT);
    }
}
