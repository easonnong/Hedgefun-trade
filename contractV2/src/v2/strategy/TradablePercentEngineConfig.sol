// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Schema 3: input-asset percentages and daily turnover of tradable stock plus available USDG.
/// @dev words[0]: target[0..15], band[16..31], cooldown[32..63], payout[64..79].
/// words[1]: buyBps[0..15], sellBps[16..31]. words[2]: daily turnover bps. All unused bits must be zero.
/// Distinct denominators mean dailyBps need not be greater than buyBps or sellBps. The execution core floors
/// each percentage and rejects sub-minimum trades rather than increasing a cap. Schemas 1 and 2 are unchanged.
///
/// The percentages are the creator's, under two protocol limits. Schema 3 has no listing chunk, so nothing else
/// bounds one action: `MAX_ACTION_BPS` does, and it scales with the treasury where a fixed amount could not.
/// And the allocation band has the floor schema 1 has, `SpotEngineConfig.minDeadbandBps` of the listing: a
/// band inside execution friction rebalances on moves smaller than the cost of rebalancing. The treasury's
/// constructor knows the listing and passes that floor; a caller without it (the policy, tooling) passes zero.
library TradablePercentEngineConfig {
    uint32 internal constant CONFIG_SCHEMA = 3;
    uint256 internal constant BPS = 10_000;
    uint256 internal constant MIN_TARGET_BPS = 2_000;
    uint256 internal constant MAX_TARGET_BPS = 9_000;
    uint256 internal constant MIN_COOLDOWN = 600;
    /// @notice the most one action may take: a quarter of the available cash (a buy) or of the tradable stock (a sale)
    uint256 internal constant MAX_ACTION_BPS = 2_500;

    function payoutBps(bytes32 word0) internal pure returns (uint256) {
        return uint16(uint256(word0) >> 64);
    }

    function buyBps(bytes32 word1) internal pure returns (uint256) {
        return uint16(uint256(word1));
    }

    function sellBps(bytes32 word1) internal pure returns (uint256) {
        return uint16(uint256(word1) >> 16);
    }

    function valid(bytes32[3] memory words, uint256 minDeadband) internal pure returns (bool) {
        uint256 packed = uint256(words[0]);
        uint256 target = uint16(packed);
        uint256 band = uint16(packed >> 16);
        uint256 buy = buyBps(words[1]);
        uint256 sell = sellBps(words[1]);
        uint256 daily = uint256(words[2]);
        return packed >> 80 == 0 && payoutBps(words[0]) <= BPS && target >= MIN_TARGET_BPS && target <= MAX_TARGET_BPS
            && band >= minDeadband && band < target && target + band < BPS && uint32(packed >> 32) >= MIN_COOLDOWN
            && uint256(words[1]) >> 32 == 0 && buy >= 1 && buy <= MAX_ACTION_BPS && sell >= 1
            && sell <= MAX_ACTION_BPS && daily >= 1 && daily <= BPS;
    }
}
