// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";

/// Test assets only. The explicit owner also works when deployed through the CREATE2 singleton.
contract SandboxStock is ERC20, Ownable2Step {
    bool public oraclePaused;
    uint256 public uiMultiplier = 1e18;
    error InvalidMultiplier();

    constructor(string memory n, string memory s, address initialOwner) ERC20(n, s) Ownable(initialOwner) {}
    function mint(address to, uint256 amount) external onlyOwner { _mint(to, amount); }
    function setOraclePaused(bool paused) external onlyOwner { oraclePaused = paused; }
    function setUiMultiplier(uint256 multiplier) external onlyOwner {
        if (multiplier == 0) revert InvalidMultiplier();
        uiMultiplier = multiplier;
    }
}

/// No backing, redemption or peg. Never confuse this six-decimal rehearsal token with real USDG.
contract SandboxQuote is ERC20, Ownable2Step {
    constructor(address initialOwner) ERC20("Sandbox Test Dollar - NO VALUE", "SBXUSD") Ownable(initialOwner) {}
    function decimals() public pure override returns (uint8) { return 6; }
    function mint(address to, uint256 amount) external onlyOwner { _mint(to, amount); }
}

/// Both feeds are owned by SandboxLp; a successful price move refreshes them in the same transaction.
contract SandboxFeed is Ownable {
    int256 public answer;
    uint256 public updatedAt;
    uint80 public round;
    error InvalidAnswer();

    constructor(int256 initialAnswer, address initialOwner) Ownable(initialOwner) { _set(initialAnswer); }
    function decimals() external pure returns (uint8) { return 8; }
    function description() external pure returns (string memory) { return "SANDBOX TEST FEED - NO VALUE"; }
    function set(int256 nextAnswer) external onlyOwner { _set(nextAnswer); }
    function _set(int256 nextAnswer) private {
        if (nextAnswer <= 0) revert InvalidAnswer();
        answer = nextAnswer;
        updatedAt = block.timestamp;
        round++;
    }
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80) {
        return (round, answer, updatedAt, updatedAt, round);
    }
}
