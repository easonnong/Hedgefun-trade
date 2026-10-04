// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @notice Deploys a sandbox hook, its two bound deployers, and the factory in one transaction.
/// @dev The factory constructor must bind all three components before this call returns.
///      Initcode is supplied as calldata so it does not count against this contract's initcode limit.
contract SandboxLaunchBundle is Ownable {
    address public deployedHook;
    address public deployedTreasuryDeployer;
    address public deployedTokenDeployer;
    address public deployedFactory;
    bool private _deploying;

    error AlreadyDeployed();
    error EmptyInitCode();
    error DeploymentFailed(uint8 step);
    error NotBound(uint8 step);

    event Launched(address indexed hook, address treasuryDeployer, address tokenDeployer, address indexed factory);

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @param hookSalt CREATE2 salt mined against this bundle's address.
    /// @param hookInitCode Creation bytecode including constructor arguments.
    /// @param treasuryInitCode Creation bytecode for the treasury deployer.
    /// @param tokenInitCode Creation bytecode for the token deployer.
    /// @param factoryInitCode Creation bytecode including constructor arguments.
    ///        The three component addresses must match the hook CREATE2 address and
    ///        this bundle's CREATE nonces 2 and 3, respectively.
    function deploy(
        bytes32 hookSalt,
        bytes calldata hookInitCode,
        bytes calldata treasuryInitCode,
        bytes calldata tokenInitCode,
        bytes calldata factoryInitCode
    ) external onlyOwner returns (address hook, address factory) {
        if (_deploying || deployedFactory != address(0)) revert AlreadyDeployed();
        if (hookInitCode.length == 0 || treasuryInitCode.length == 0 || tokenInitCode.length == 0 || factoryInitCode.length == 0) {
            revert EmptyInitCode();
        }
        _deploying = true;

        hook = _create2(hookSalt, hookInitCode);
        if (hook == address(0)) revert DeploymentFailed(1);
        address treasuryDeployer = _create(treasuryInitCode);
        if (treasuryDeployer == address(0)) revert DeploymentFailed(2);
        address tokenDeployer = _create(tokenInitCode);
        if (tokenDeployer == address(0)) revert DeploymentFailed(3);
        factory = _create(factoryInitCode);
        if (factory == address(0)) revert DeploymentFailed(4);

        if (IBoundSandboxComponent(hook).factory() != factory) revert NotBound(1);
        if (IBoundSandboxComponent(treasuryDeployer).factory() != factory) revert NotBound(2);
        if (IBoundSandboxComponent(tokenDeployer).factory() != factory) revert NotBound(3);

        deployedHook = hook;
        deployedTreasuryDeployer = treasuryDeployer;
        deployedTokenDeployer = tokenDeployer;
        deployedFactory = factory;
        _deploying = false;
        emit Launched(hook, treasuryDeployer, tokenDeployer, factory);
    }

    function _create2(bytes32 salt, bytes calldata initCode) private returns (address at) {
        bytes memory code = initCode;
        assembly { at := create2(0, add(code, 0x20), mload(code), salt) }
    }

    function _create(bytes calldata initCode) private returns (address at) {
        bytes memory code = initCode;
        assembly { at := create(0, add(code, 0x20), mload(code)) }
    }
}

interface IBoundSandboxComponent {
    function factory() external view returns (address);
}
