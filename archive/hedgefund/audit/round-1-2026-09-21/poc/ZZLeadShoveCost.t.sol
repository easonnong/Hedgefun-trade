// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HookTaxBase} from "./InteractHookTax.t.sol";
import {BalanceDelta} from "v4-core/src/types/BalanceDelta.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolIdLibrary, PoolKey} from "v4-core/src/types/PoolId.sol";

/// Lead's measurement of the ONE number the buy-back's whole defence rests on.
///
/// `lpFee` is forced to 0 on every launch pool (StrategyFactory._setDefaults), so the AMM charges nothing for
/// a round trip and the pool's own impact round-trips to roughly nothing too. What is left as the cost of
/// shoving the launch pool is the hook tax, and nothing else. Measure it, both halves of the spike cycle.
contract ZZLeadShoveCost is HookTaxBase {
    using StateLibrary for IPoolManager;
    using PoolIdLibrary for PoolKey;

    function tokenIsCurrency0() internal pure override returns (bool) { return true; }

    /// A shove and its unwind, at the flat 10% rate. This is the FLOOR on what it costs to move this pool.
    function test_lead_roundTripCostAtTheFlatRate() public {
        _pastSpike();                                   // the launch spike has decayed; flat 10% both ways
        uint256 stockIn = 1e21;

        uint256 s0 = stock.balanceOf(address(this));
        uint256 t0 = token.balanceOf(address(this));
        _swap(!sellDir(), -int256(stockIn));            // buy: stock in, token out, taxed in the TOKEN
        uint256 gotTokens = token.balanceOf(address(this)) - t0;
        assertGt(gotTokens, 0);

        _swap(sellDir(), -int256(gotTokens));           // sell it all straight back: taxed in the STOCK
        uint256 s1 = stock.balanceOf(address(this));

        uint256 spent = s0 - s1;                        // net stock burned on the round trip
        // 1 - (1 - 0.10)*(1 - 0.10) = 19% of the notional, before AMM impact
        assertApproxEqRel(spent * 1e18 / stockIn, 0.19e18, 0.02e18,
            "a flat-rate round trip through a zero-LP-fee launch pool costs ~19% of the shove");
        emit log_named_decimal_uint("round-trip cost, flat rate, as a fraction of the shove", spent * 1e18 / stockIn, 18);
    }

    /// The same shove with the sell spike live. This is what an attacker pays if they land in the protected
    /// half of the cycle -- and it is the number the documents claim always applies.
    function test_lead_roundTripCostWithTheSpikeLive() public {
        uint256 stockIn = 1e21;
        assertEq(hook.sellRateBps(), 9000, "the launch itself arms the spike");

        uint256 s0 = stock.balanceOf(address(this));
        uint256 t0 = token.balanceOf(address(this));
        _swap(!sellDir(), -int256(stockIn));
        uint256 gotTokens = token.balanceOf(address(this)) - t0;
        _swap(sellDir(), -int256(gotTokens));
        uint256 spent = s0 - stock.balanceOf(address(this));

        // 1 - (1 - 0.10)*(1 - 0.90) = 91%
        assertApproxEqRel(spent * 1e18 / stockIn, 0.91e18, 0.02e18,
            "with the spike live the same round trip costs ~91% of the shove");
        emit log_named_decimal_uint("round-trip cost, spike live, as a fraction of the shove", spent * 1e18 / stockIn, 18);
    }

    /// And the ratio that decides whether any of this is safe: cost to shove vs the most a buy-back can be
    /// made to give up, which is `maxBuybackImpactBps` (<= 1000 = 10%, default 300 = 3%) of one chunk.
    function test_lead_theShoveCostDominatesTheBuybackPayoffAtEveryAllowedImpactCap() public {
        _pastSpike();
        uint256 stockIn = 1e21;
        uint256 s0 = stock.balanceOf(address(this));
        uint256 t0 = token.balanceOf(address(this));
        _swap(!sellDir(), -int256(stockIn));
        uint256 gotTokens = token.balanceOf(address(this)) - t0;
        _swap(sellDir(), -int256(gotTokens));
        uint256 costBps = (s0 - stock.balanceOf(address(this))) * 1e4 / stockIn;

        assertGt(costBps, 1000, "cost exceeds the LOOSEST impact cap the factory permits (maxBuybackImpactBps = 1000)");
        assertGt(costBps, 300,  "and far exceeds the default of 300");
        emit log_named_uint("round-trip shove cost, bps of notional", costBps);
        emit log_named_uint("maximum buy-back payoff, bps of one chunk", 1000);
    }
}
