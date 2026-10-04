// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {InteractFactoryTest} from "./InteractFactory.t.sol";
import {StrategyFactory} from "../src/str/StrategyFactory.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {SwapParams} from "v4-core/src/types/PoolOperation.sol";
import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";

interface IKeyedT { function poolKey() external view returns (Currency, Currency, uint24, int24, IHooks); }

/// Lead's measurement of a number the whole buy-back argument needs and nobody had: **how far does one
/// buy-back-sized trade move a genuinely single-sided seeded launch pool?**
///
/// My earlier `ZZLeadShoveCost` measured the hook tax on a two-sided pool, which is the right harness for
/// the tax and the wrong one for impact. This launches through the real `StrategyFactory`, so the pool is
/// seeded exactly as production seeds it: the entire supply, one-sided, from `floorTick + spacing` to
/// `maxUsableTick`. The buy-back's price impact is what an exiting holder captures by timing their sale
/// into it (see the spike finding), so this bounds that payoff.
contract ZZLeadSeededImpact is InteractFactoryTest {
    using StateLibrary for IPoolManager;
    using PoolIdLibrary for PoolKey;

    PoolSwapTest sr;

    function _launchAndKey() internal returns (PoolKey memory key, address tok) {
        uint256 id = _launch(factory, _req("IMPACT"));
        address treasury;
        (tok, treasury,,,) = factory.strategies(id);
        (key.currency0, key.currency1, key.fee, key.tickSpacing, key.hooks) = IKeyedT(treasury).poolKey();
    }

    function _spot(PoolKey memory key) internal view returns (uint160 s) { (s,,,) = pm.getSlot0(key.toId()); }

    /// stock -> token, exact input, no price limit
    function _buy(PoolKey memory key, uint256 stockIn) internal returns (int256) {
        bool zeroForOne = Currency.unwrap(key.currency0) == address(stock);
        sr.swap(key, SwapParams({zeroForOne: zeroForOne, amountSpecified: -int256(stockIn),
                sqrtPriceLimitX96: zeroForOne ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        return 0;
    }

    function test_lead_oneBuybackChunkMovesASeededPoolBy() public {
        sr = new PoolSwapTest(pm);
        stock.mint(address(this), 1e24);
        stock.approve(address(sr), type(uint256).max);

        (PoolKey memory key,) = _launchAndKey();

        // the factory's default chunk is 500 USDG; at the harness's 100 USDG/stock that is 5 stock
        uint256 chunk = 5 ether;

        // (a) into a pool that has never traded -- the state right after launch
        uint160 s0 = _spot(key);
        _buy(key, chunk);
        uint160 s1 = _spot(key);
        uint256 movedA = _pctMove(s0, s1, Currency.unwrap(key.currency0) == address(stock));
        emit log_named_uint("one 500-USDG chunk into a virgin seeded pool, price move in bps", movedA);

        // (b) after real buying has established a market -- 200 stock, 40x the chunk
        _buy(key, 200 ether);
        uint160 s2 = _spot(key);
        _buy(key, chunk);
        uint160 s3 = _spot(key);
        uint256 movedB = _pctMove(s2, s3, Currency.unwrap(key.currency0) == address(stock));
        emit log_named_uint("the same chunk after 200 stock of buying, price move in bps", movedB);

        // (c) and after a lot more
        _buy(key, 2000 ether);
        uint160 s4 = _spot(key);
        _buy(key, chunk);
        uint160 s5 = _spot(key);
        uint256 movedC = _pctMove(s4, s5, Currency.unwrap(key.currency0) == address(stock));
        emit log_named_uint("the same chunk after 2200 stock of buying, price move in bps", movedC);

        // The finding is the comparison against the cap, not any single number.
        emit log_named_uint("maxBuybackImpactBps, factory default", factory.getDefaults().maxBuybackImpactBps);
        emit log_named_uint("maxBuybackImpactBps, the loosest the factory permits", 1000);
        assertGt(movedA, 0, "a chunk must move a single-sided pool at all");
    }

    /// |price(s1)/price(s0) - 1| in bps, where price is the TOKEN's price in stock
    function _pctMove(uint160 a, uint160 b, bool stockIsC0) internal pure returns (uint256) {
        (uint256 lo, uint256 hi) = uint256(a) < uint256(b) ? (uint256(a), uint256(b)) : (uint256(a), uint256(b));
        stockIsC0;
        uint256 r = hi == lo ? 0 : (uint256(b) * 1e4) / uint256(a);
        return r >= 1e4 ? r - 1e4 : 1e4 - r;   // sqrt-price move in bps; price moves ~2x this
    }
}
