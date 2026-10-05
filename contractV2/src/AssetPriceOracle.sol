// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IAggregatorV3} from "./interfaces/IAggregatorV3.sol";
import {ITradingCalendar} from "./interfaces/ITradingCalendar.sol";

/// Price of one token of a listed asset that is NOT a Robinhood stock token, in USDG, 1e18-scaled, in human units
/// (USDG per whole token): asset feed / USDG feed. Written for wrapped ETH.
///
/// `PriceOracle` asks the listed token whether its oracle is paused, a question only the stock tokens answer, and
/// fails closed on silence: it can never price a token like WETH. This is the same reader without that question and
/// with the same read ABI, so a factory listing and every treasury use it exactly as they use `PriceOracle`. The
/// names `stock`, `stockFeed` and `maxStockAge` are that ABI's; here they mean the listed asset.
///
/// A price is only served when ALL of these hold; anything else fails closed:
///   - the calendar says trading is not halted (for an asset that trades around the clock that is an owner's
///     switch, not a schedule),
///   - both rounds are positive, not from the future, and no older than their max age.
/// There is no L2 sequencer uptime feed on this chain, so updatedAt is the only liveness signal there is. A feed
/// that prints on a deviation threshold lags the market by up to that threshold; the treasuries' own gate, spot
/// and the pool's mean against this price, is what stops a trade when the two have drifted apart.
contract AssetPriceOracle {
    /// the oldest asset print a listing may accept, as for a stock
    uint256 internal constant MAX_ASSET_AGE = 48 hours;

    IAggregatorV3 public immutable stockFeed;
    IAggregatorV3 public immutable usdgFeed;
    ITradingCalendar public immutable calendar;
    address public immutable stock;
    uint256 public immutable maxStockAge;
    uint256 public immutable maxUsdgAge;
    uint256 internal immutable _num;   // 1e18 * 10^usdgFeedDecimals
    uint256 internal immutable _den;   // 10^assetFeedDecimals

    error Unhealthy();

    constructor(address asset_, address assetFeed_, address usdgFeed_, address calendar_, uint256 maxAssetAge_, uint256 maxUsdgAge_) {
        require(asset_ != address(0) && assetFeed_ != address(0) && usdgFeed_ != address(0) && calendar_ != address(0), "zero");
        require(maxAssetAge_ != 0 && maxAssetAge_ <= MAX_ASSET_AGE && maxUsdgAge_ != 0, "age");
        stock = asset_; stockFeed = IAggregatorV3(assetFeed_); usdgFeed = IAggregatorV3(usdgFeed_); calendar = ITradingCalendar(calendar_);
        maxStockAge = maxAssetAge_; maxUsdgAge = maxUsdgAge_;
        _num = 1e18 * 10 ** uint256(IAggregatorV3(usdgFeed_).decimals());
        _den = 10 ** uint256(IAggregatorV3(assetFeed_).decimals());
    }

    /// @return ok false whenever the price must not be used; p is 0 then
    function tryPrice() public view returns (bool ok, uint256 p) {
        try calendar.isClosed(block.timestamp) returns (bool closed) { if (closed) return (false, 0); } catch { return (false, 0); }
        (bool okS, uint256 s) = _read(stockFeed, maxStockAge);
        (bool okU, uint256 u) = _read(usdgFeed, maxUsdgAge);
        if (!okS || !okU) return (false, 0);
        p = Math.mulDiv(s, _num, u * _den);
        return (p != 0, p);
    }

    /// @notice the same price, WITHOUT the calendar and the asset's age gate: what the feeds are saying right now.
    /// @dev Never a price to TRADE at on its own: `tryPrice` is what answers that question, and it fails closed.
    ///      The round sanity checks still apply, and the dollar leg never gets to be stale.
    function lastPriceAt() external view returns (bool ok, uint256 p, uint256 stockUpdatedAt) {
        (bool okU, uint256 u) = _read(usdgFeed, maxUsdgAge);
        if (!okU) return (false, 0, 0);
        try stockFeed.latestRoundData() returns (uint80, int256 s, uint256, uint256 su, uint80) {
            if (s <= 0 || su == 0 || su > block.timestamp) return (false, 0, 0);
            p = Math.mulDiv(uint256(s), _num, u * _den);
            return (p != 0, p, su);
        } catch { return (false, 0, 0); }
    }

    function price() external view returns (uint256 p) {
        bool ok; (ok, p) = tryPrice();
        if (!ok) revert Unhealthy();
    }

    function _read(IAggregatorV3 feed, uint256 maxAge) internal view returns (bool, uint256) {
        try feed.latestRoundData() returns (uint80, int256 answer, uint256, uint256 updatedAt, uint80) {
            if (answer <= 0 || updatedAt == 0 || updatedAt > block.timestamp || block.timestamp - updatedAt > maxAge) return (false, 0);
            return (true, uint256(answer));
        } catch { return (false, 0); }
    }
}
