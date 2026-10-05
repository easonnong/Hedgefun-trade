// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {HedgeFunV2Factory} from "../../src/v2/HedgeFunV2Factory.sol";
import {PriceOracle} from "../../src/PriceOracle.sol";
import {TestnetMarket} from "./TestnetMarket.sol";

/// @notice Re-list the test market's stocks on a reviewed V2 testnet factory at the opening price that graduates
///         the default 79.31% sale near a $50,000 FDV; no redeployment, and nothing but `openPriceE18` changes.
/// @dev A core that reuses the existing test market inherits the listings' earlier opening prices, which were
///      chosen for a 44% sale: at 79.31% they raise about $36,000-39,000 and graduate near $220,000-237,000.
///      This applies `DeployV2Testnet.referenceOpenPriceE18` to each enabled listing at its oracle's current
///      price: an opening FDV of about $2,140 and a raise of about $8,205.
///
///      `plan()` is read-only and prints the plan and its hash. `run()` broadcasts only the plan whose hash is
///      EXPECTED_PLAN_HASH, so a feed moved or a listing changed after the review fails closed. A launch quote
///      read before the re-listing reverts on `expectedOpenPriceE18`; existing launches keep their frozen curve.
///      Never run alongside another owner operation.
contract CalibrateV2OpenPrices is Script {
    /// The same reference as `DeployV2Testnet`; `test/TestnetV2OpenPricesFork.t.sol` holds the two equal.
    uint256 public constant TARGET_GRADUATION_FDV_USD_E18 = 50_000e18;
    uint16 public constant REFERENCE_SALE_BPS = 7931;
    uint256 private constant SUPPLY_TOKENS = 1_000_000_000;

    struct Relisting {
        address stock;
        address oracle;
        address pool;
        uint256 oldOpenPriceE18;
        uint256 newOpenPriceE18;
    }

    function run() external {
        (HedgeFunV2Factory factory, address operator, TestnetMarket market) = _inputs();
        require(msg.sender == operator && factory.owner() == operator, "factory owner only");
        Relisting[] memory p = planFor(factory, market);
        require(keccak256(abi.encode(p)) == vm.envBytes32("EXPECTED_PLAN_HASH"), "plan changed");
        vm.startBroadcast(operator);
        for (uint256 i; i < p.length; ++i) {
            if (p[i].newOpenPriceE18 != p[i].oldOpenPriceE18) {
                factory.list(p[i].stock, p[i].oracle, p[i].pool, p[i].newOpenPriceE18, true);
            }
        }
        vm.stopBroadcast();
        for (uint256 i; i < p.length; ++i) {
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(p[i].stock);
            require(
                oracle == p[i].oracle && pool == p[i].pool && open == p[i].newOpenPriceE18 && enabled,
                "readback failed"
            );
        }
    }

    /// @notice Read-only: the re-listings `run()` would send and the hash it must be given.
    function plan() external view returns (Relisting[] memory p) {
        (HedgeFunV2Factory factory,, TestnetMarket market) = _inputs();
        p = planFor(factory, market);
        for (uint256 i; i < p.length; ++i) {
            console2.log("stock", p[i].stock);
            console2.log("  openPriceE18 now", p[i].oldOpenPriceE18);
            console2.log("  openPriceE18 new", p[i].newOpenPriceE18);
        }
        console2.log("EXPECTED_PLAN_HASH");
        console2.logBytes32(keccak256(abi.encode(p)));
    }

    /// @dev Every stock of the test market that `factory` lists and has enabled, in the market's own order.
    function planFor(HedgeFunV2Factory factory, TestnetMarket market) public view returns (Relisting[] memory p) {
        uint256 count = market.poolCount();
        Relisting[] memory all = new Relisting[](count);
        uint256 n;
        for (uint256 i; i < count; ++i) {
            (address stock,,,,,) = market.lines(market.pools(i));
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(stock);
            if (!enabled) continue;
            (bool ok, uint256 priceE18,) = PriceOracle(oracle).lastPriceAt();
            require(ok, "no oracle price");
            all[n++] = Relisting(stock, oracle, pool, open, referenceOpenPriceE18(priceE18));
        }
        require(n != 0, "nothing listed");
        p = new Relisting[](n);
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
