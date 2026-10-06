// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {HedgeFunV2Factory} from "../../src/v2/HedgeFunV2Factory.sol";
import {V2TreasuryDeployer} from "../../src/v2/V2TreasuryDeployer.sol";
import {V2TreasuryUpgradeController} from "../../src/v2/V2TreasuryUpgradeController.sol";
import {PolicyManifest, StrategyCapabilities} from "../../src/v2/strategy/IStrategyPolicy.sol";
import {V2RebalancePolicy} from "../../src/v2/strategy/V2RebalancePolicy.sol";
import {ReviewedTreasuryRegistry} from "../helpers/ReviewedTreasuryRegistry.sol";

/// @notice Register the schema-1 policy (`V2RebalancePolicy`) that the upgradeable spot engine, kind 2, needs on
///         the mainnet factory's registry. Without it no kind-2 launch can be configured: `setEngineConfig` wants
///         a registered, enabled policy key of the engine's schema.
/// @dev Two owner transactions, as the testnet deployments make them inline (`DeployV2FeeUpgradeTestnet._register`):
///      the policy is deployed from this source, then `registerPolicy(policy, 150_000, 160, dependencies, audit)`.
///      Chain 4663 only; the policy's runtime code is pinned here, so a build from other source is refused before
///      anything is sent; the registry and its upgrade controller must be the reviewed runtimes the other
///      `RegisterV2*` scripts accept. A policy registration is permanent (it can only be disabled for new launches),
///      so the dependency and audit manifest hashes must describe this actual candidate.
///
///      Requires OPERATOR (the factory owner, and the broadcaster), V2_FACTORY, DEPENDENCY_MANIFEST_HASH and
///      AUDIT_MANIFEST_HASH. Prints the policy address and key; `VerifyV2SpotPolicy` reads them back from the
///      confirmed chain.
contract RegisterV2SpotPolicy is ReviewedTreasuryRegistry {
    uint256 public constant CHAIN_ID = 4663;
    /// `registerPolicy` limits: the gas a `decide` call may use, as the testnet deployments register it, and the
    ///  registry's fixed return size.
    uint32 public constant POLICY_MAX_GAS = 150_000;
    uint16 public constant POLICY_RETURN_BYTES = 160;
    /// keccak256 of `V2RebalancePolicy`'s runtime code from this source with the repository's compiler settings
    /// (solc 0.8.26, Cancun, optimizer runs 1, no metadata hash). Both the deployment and the readback refuse any other.
    bytes32 public constant POLICY_RUNTIME_CODE_HASH = 0x703c92e4d169643e9b20eadf00cd53470b95699186a5ce9131feee42299c0b74;

    struct Registration {
        bytes32 policyKey;
        address policy;
    }

    error WrongChain(uint256 chainId);
    error PolicyCodeNotReviewed(bytes32 actual);
    error BadBinding();
    error BadReadback();

    function run() external returns (Registration memory r) {
        address operator = vm.envAddress("OPERATOR");
        if (operator == address(0) || msg.sender != operator) revert BadBinding();
        r = register(
            operator,
            HedgeFunV2Factory(vm.envAddress("V2_FACTORY")),
            vm.envBytes32("DEPENDENCY_MANIFEST_HASH"),
            vm.envBytes32("AUDIT_MANIFEST_HASH")
        );
        console2.log("policy: V2RebalancePolicy, engine version 1, config schema 1 (the spot engine's, kind 2)");
        console2.log("policy", r.policy);
        console2.log("policy key");
        console2.logBytes32(r.policyKey);
        console2.log("simulation only unless --broadcast; run VerifyV2SpotPolicy against the confirmed chain");
    }

    function register(address operator, HedgeFunV2Factory factory, bytes32 dependencies, bytes32 audit)
        public
        returns (Registration memory r)
    {
        if (block.chainid != CHAIN_ID) revert WrongChain(block.chainid);
        bytes32 runtime = keccak256(type(V2RebalancePolicy).runtimeCode);
        if (runtime != POLICY_RUNTIME_CODE_HASH) revert PolicyCodeNotReviewed(runtime);
        V2TreasuryDeployer registry = _reviewedRegistry(factory);
        V2TreasuryUpgradeController controller = registry.upgradeController();
        if (
            operator == address(0) || dependencies == bytes32(0) || audit == bytes32(0) || factory.owner() != operator
                || registry.factory() != address(factory) || address(controller).code.length == 0
                || controller.owner() != operator || controller.UPGRADE_DELAY() != 2 days
                || registry.POLICY_RETURN_BYTES() != POLICY_RETURN_BYTES
        ) revert BadBinding();
        vm.startBroadcast(operator);
        r.policy = address(new V2RebalancePolicy());
        r.policyKey = registry.registerPolicy(r.policy, POLICY_MAX_GAS, POLICY_RETURN_BYTES, dependencies, audit);
        vm.stopBroadcast();
        check(factory, r, dependencies, audit);
    }

    /// @notice The registration as the registry reports it: this source's policy, under the key the registry
    ///         derives, with the spot engine's manifest, enabled for new launches.
    function check(HedgeFunV2Factory factory, Registration memory r, bytes32 dependencies, bytes32 audit) public view {
        if (block.chainid != CHAIN_ID) revert WrongChain(block.chainid);
        V2TreasuryDeployer registry = _reviewedRegistry(factory);
        if (
            registry.factory() != address(factory) || r.policy == address(0) || dependencies == bytes32(0)
                || audit == bytes32(0)
        ) revert BadReadback();
        PolicyManifest memory m = registry.policy(r.policyKey);
        if (
            m.implementation != r.policy || r.policy.codehash != POLICY_RUNTIME_CODE_HASH
                || m.runtimeCodeHash != POLICY_RUNTIME_CODE_HASH
                || m.engineVersion != StrategyCapabilities.SPOT_ENGINE_V1
                || m.configSchema != StrategyCapabilities.CONFIG_SCHEMA_V1
                || m.capabilities != (StrategyCapabilities.SPOT_BUY | StrategyCapabilities.SPOT_SELL)
                || m.maxGas != POLICY_MAX_GAS || m.maxReturnBytes != POLICY_RETURN_BYTES || !m.enabledForNewLaunches
                || registry.policyDependencyManifestHash(r.policyKey) != dependencies
                || registry.policyAuditManifestHash(r.policyKey) != audit
                || r.policyKey
                    != keccak256(
                        abi.encode(
                            r.policy,
                            POLICY_RUNTIME_CODE_HASH,
                            StrategyCapabilities.SPOT_ENGINE_V1,
                            StrategyCapabilities.CONFIG_SCHEMA_V1,
                            StrategyCapabilities.SPOT_BUY | StrategyCapabilities.SPOT_SELL,
                            POLICY_MAX_GAS,
                            POLICY_RETURN_BYTES,
                            dependencies,
                            audit
                        )
                    )
        ) revert BadReadback();
        V2TreasuryUpgradeController controller = registry.upgradeController();
        if (
            address(controller).code.length == 0 || controller.owner() != factory.owner()
                || controller.UPGRADE_DELAY() != 2 days
        ) revert BadReadback();
    }
}

/// @notice Read-only confirmation against the confirmed chain. Requires V2_FACTORY, SPOT_POLICY and
///         SPOT_POLICY_KEY (from the receipts and the registration's log), DEPENDENCY_MANIFEST_HASH and
///         AUDIT_MANIFEST_HASH (the ones that were registered).
contract VerifyV2SpotPolicy is Script {
    function run() external {
        HedgeFunV2Factory factory = HedgeFunV2Factory(vm.envAddress("V2_FACTORY"));
        RegisterV2SpotPolicy.Registration memory r =
            RegisterV2SpotPolicy.Registration(vm.envBytes32("SPOT_POLICY_KEY"), vm.envAddress("SPOT_POLICY"));
        new RegisterV2SpotPolicy()
            .check(factory, r, vm.envBytes32("DEPENDENCY_MANIFEST_HASH"), vm.envBytes32("AUDIT_MANIFEST_HASH"));
        console2.log("live spot-engine policy verified", r.policy);
        console2.logBytes32(r.policyKey);
    }
}
