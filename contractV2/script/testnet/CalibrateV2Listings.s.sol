// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {HedgeFunV2Factory} from "../../src/v2/HedgeFunV2Factory.sol";
import {V2TreasuryDeployer} from "../../src/v2/V2TreasuryDeployer.sol";
import {PriceOracle} from "../../src/PriceOracle.sol";
import {TestnetMarket} from "./TestnetMarket.sol";

/// @notice Bring the test market's listings on a reviewed V2 testnet factory to the release settings: the opening
///         price that graduates the default 79.31% sale near a $50,000 FDV, and 70% of the raise to the locked
///         LP. No redeployment; nothing but `openPriceE18` and the stock's LP share changes.
/// @dev A core that reuses the existing test market inherits the listings' earlier opening prices, which were
///      chosen for a 44% sale: at 79.31% they raise about $36,000-39,000 and graduate near $220,000-237,000.
///      This applies `DeployV2Testnet.referenceOpenPriceE18` to each enabled listing at its oracle's current
///      price: an opening FDV of about $2,140 and a raise of about $8,205. The LP share splits that raise at
///      graduation, about $5,743 to the pool and $2,461 to the treasury; it moves neither the raise nor the FDV.
///
///      `plan()` is read-only and prints the plan and its hash. `run()` broadcasts only the plan whose hash is
///      EXPECTED_PLAN_HASH, so a feed moved or a listing changed after the review fails closed. A launch quote
///      read before either change reverts; existing launches keep their frozen curve and split.
///      Never run alongside another owner operation.
contract CalibrateV2Listings is Script {
    /// The same reference as `DeployV2Testnet`; `test/TestnetV2ListingCalibrationFork.t.sol` holds the two equal.
    uint256 public constant TARGET_GRADUATION_FDV_USD_E18 = 50_000e18;
    uint16 public constant REFERENCE_SALE_BPS = 7931;
    /// Share of a graduation's net raise seeded into the locked V4 position; the rest is the treasury's.
    uint16 public constant LP_BPS = 7000;
    uint256 private constant SUPPLY_TOKENS = 1_000_000_000;

    struct Calibration {
        address stock;
        address oracle;
        address pool;
        uint256 oldOpenPriceE18;
        uint256 newOpenPriceE18;
        uint16 oldLpBps;
        uint16 newLpBps;
    }

    function run() external {
        (HedgeFunV2Factory factory, address operator, TestnetMarket market) = _inputs();
        require(msg.sender == operator && factory.owner() == operator, "factory owner only");
        V2TreasuryDeployer registry = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        Calibration[] memory p = planFor(factory, market);
        require(keccak256(abi.encode(p)) == vm.envBytes32("EXPECTED_PLAN_HASH"), "plan changed");
        vm.startBroadcast(operator);
        for (uint256 i; i < p.length; ++i) {
            if (p[i].newOpenPriceE18 != p[i].oldOpenPriceE18) {
                factory.list(p[i].stock, p[i].oracle, p[i].pool, p[i].newOpenPriceE18, true);
            }
            if (p[i].newLpBps != p[i].oldLpBps) registry.setLpBps(p[i].stock, p[i].newLpBps);
        }
        vm.stopBroadcast();
        for (uint256 i; i < p.length; ++i) {
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(p[i].stock);
            require(
                oracle == p[i].oracle && pool == p[i].pool && open == p[i].newOpenPriceE18 && enabled
                    && registry.lpBps(p[i].stock) == p[i].newLpBps,
                "readback failed"
            );
        }
    }

    /// @notice Read-only: the changes `run()` would send and the hash it must be given.
    function plan() external view returns (Calibration[] memory p) {
        (HedgeFunV2Factory factory,, TestnetMarket market) = _inputs();
        p = planFor(factory, market);
        for (uint256 i; i < p.length; ++i) {
            console2.log("stock", p[i].stock);
            console2.log("  openPriceE18 now", p[i].oldOpenPriceE18);
            console2.log("  openPriceE18 new", p[i].newOpenPriceE18);
            console2.log("  lpBps now, new", p[i].oldLpBps, p[i].newLpBps);
        }
        console2.log("EXPECTED_PLAN_HASH");
        console2.logBytes32(keccak256(abi.encode(p)));
    }

    /// @dev Every stock of the test market that `factory` lists and has enabled, in the market's own order.
    function planFor(HedgeFunV2Factory factory, TestnetMarket market) public view returns (Calibration[] memory p) {
        V2TreasuryDeployer registry = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        uint256 count = market.poolCount();
        Calibration[] memory all = new Calibration[](count);
        uint256 n;
        for (uint256 i; i < count; ++i) {
            (address stock,,,,,) = market.lines(market.pools(i));
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(stock);
            if (!enabled) continue;
            (bool ok, uint256 priceE18,) = PriceOracle(oracle).lastPriceAt();
            require(ok, "no oracle price");
            all[n++] =
                Calibration(stock, oracle, pool, open, referenceOpenPriceE18(priceE18), registry.lpBps(stock), LP_BPS);
        }
        require(n != 0, "nothing listed");
        p = new Calibration[](n);
        for (uint256 i; i < n; ++i) p[i] = all[i];
    }

    /// @notice 18-decimal stock units per token, scaled by 1e18, as `DeployV2Testnet.referenceOpenPriceE18`.
    function referenceOpenPriceE18(uint256 stockUsdE18) public pure returns (uint256) {
        uint256 remaining = 10_000 - REFERENCE_SALE_BPS;
        uint256 openingFdv = Math.mulDiv(TARGET_GRADUATION_FDV_USD_E18, remaining * remaining, 10_000 * 10_000);
        return Math.mulDiv(openingFdv, 1e18, stockUsdE18 * SUPPLY_TOKENS);
    }

    function _inputs() private view returns (HedgeFunV2Factory factory, address operator, TestnetMarket market) {
        require(block.chainid == 46630, "testnet only");
        factory = HedgeFunV2Factory(vm.envAddress("V2_FACTORY"));
        operator = vm.envAddress("OPERATOR");
        market = TestnetMarket(vm.envAddress("TESTNET_MARKET"));
        require(address(factory.curveDeployer()).code.length != 0, "V2 factory required");
    }
}
