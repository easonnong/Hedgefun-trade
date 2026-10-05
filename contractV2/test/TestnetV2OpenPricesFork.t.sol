// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {CalibrateV2OpenPrices} from "../script/testnet/CalibrateV2OpenPrices.s.sol";
import {DeployV2Testnet} from "../script/testnet/DeployV2Testnet.s.sol";
import {TestnetMarket} from "../script/testnet/TestnetMarket.sol";

contract OpenPriceOperatorInvoker {
    function run(CalibrateV2OpenPrices script) external { script.run(); }
}

/// The re-listing that brings a core on the existing test market to the fresh deployment's reference: the default
/// 79.31% sale raising about $8,205 and graduating near a $50,000 FDV.
///
/// OPEN_PRICES_FORK=true OPEN_PRICES_FORK_BLOCK=<fresh block> [V2_FACTORY=0x...]
///   forge test --match-contract TestnetV2OpenPricesForkTest -vv
contract TestnetV2OpenPricesForkTest is Test {
    uint256 constant REFERENCE_RAISE_USD_E18 = 8_204.6e18;
    uint256 constant REFERENCE_FDV_USD_E18 = 50_000e18;

    HedgeFunV2Factory internal factory;
    TestnetMarket internal market;
    V2TreasuryDeployer internal registry;
    CalibrateV2OpenPrices internal script;

    function test_referenceIsTheFreshDeployments() public {
        script = new CalibrateV2OpenPrices();
        DeployV2Testnet fresh = new DeployV2Testnet();
        assertEq(script.TARGET_GRADUATION_FDV_USD_E18(), fresh.TARGET_GRADUATION_FDV_USD_E18());
        assertEq(script.REFERENCE_SALE_BPS(), fresh.REFERENCE_SALE_BPS());
        uint256[7] memory prices = [uint256(24e18), 200e18, 228e18, 339e18, 358e18, 500e18, 600e18];
        for (uint256 i; i < prices.length; ++i) {
            assertEq(script.referenceOpenPriceE18(prices[i]), fresh.referenceOpenPriceE18(prices[i]));
        }
    }

    /// Opt-in, pinned public-testnet fork. No signing or broadcast to the public chain.
    function test_forkRelistsEveryStockAndTheDefaultSaleGraduatesNear50k() public {
        vm.skip(!vm.envOr("OPEN_PRICES_FORK", false), "set OPEN_PRICES_FORK=true");
        uint256 forkBlock = vm.envUint("OPEN_PRICES_FORK_BLOCK");
        vm.createSelectFork(
            vm.envOr("OPEN_PRICES_FORK_RPC", string("https://rpc.testnet.chain.robinhood.com")), forkBlock
        );
        assertEq(block.chainid, 46630);
        emit log_named_uint("requested fork block", forkBlock);
        factory = HedgeFunV2Factory(vm.envOr("V2_FACTORY", address(0x7BbaAb5d1426650FaaAEB0214D5a045A80FD2621)));
        market = TestnetMarket(vm.envOr("TESTNET_MARKET", address(0xc1AF2f52980F8A7AA4E90A8E30D5c3FaF0375f21)));
        registry = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        script = new CalibrateV2OpenPrices();
        address operator = factory.owner();

        CalibrateV2OpenPrices.Relisting[] memory p = script.planFor(factory, market);
        bytes32 defaultsBefore = keccak256(abi.encode(factory.getDefaults()));
        bytes32[] memory untouchedBefore = new bytes32[](p.length);
        HedgeFunFactory.Request memory stale = _request(p[0].stock, 0);
        for (uint256 i; i < p.length; ++i) {
            untouchedBefore[i] = _untouched(p[i].stock);
            assertGt(p[i].oldOpenPriceE18, p[i].newOpenPriceE18, "this core already opens at the reference");
        }

        vm.setEnv("V2_FACTORY", vm.toString(address(factory)));
        vm.setEnv("OPERATOR", vm.toString(operator));
        vm.setEnv("TESTNET_MARKET", vm.toString(address(market)));
        vm.etch(operator, type(OpenPriceOperatorInvoker).runtimeCode);
        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(bytes32(uint256(1))));
        vm.expectRevert(bytes("plan changed"));
        OpenPriceOperatorInvoker(operator).run(script);
        vm.setEnv("EXPECTED_PLAN_HASH", vm.toString(keccak256(abi.encode(p))));
        OpenPriceOperatorInvoker(operator).run(script);

        assertEq(keccak256(abi.encode(factory.getDefaults())), defaultsBefore, "defaults changed");
        CalibrateV2OpenPrices.Relisting[] memory again = script.planFor(factory, market);
        assertEq(again.length, p.length);
        for (uint256 i; i < p.length; ++i) {
            _assertRelisted(p[i]);
            assertEq(again[i].oldOpenPriceE18, again[i].newOpenPriceE18, "a second run has nothing to send");
            assertEq(_untouched(p[i].stock), untouchedBefore[i], "gates or LP share changed");
            _assertDefaultLaunchGraduatesAtTheReference(p[i].stock, i + 1);
        }

        // A quote read before the re-listing no longer launches.
        (,, bytes32 staleTerms) = factory.predict(stale);
        vm.deal(stale.creator, stale.maxFee);
        vm.prank(stale.creator);
        vm.expectRevert();
        factory.launch{value: stale.maxFee}(stale, staleTerms);
    }

    function _assertRelisted(CalibrateV2OpenPrices.Relisting memory r) private view {
        (address oracle, address pool, uint256 open, bool enabled) = factory.listings(r.stock);
        assertEq(oracle, r.oracle);
        assertEq(pool, r.pool);
        assertEq(open, r.newOpenPriceE18);
        assertTrue(enabled);
    }

    function _untouched(address stock) private view returns (bytes32) {
        (uint16 deviation, uint16 slippage, uint64 chunk) = factory.listingGates(stock);
        return keccak256(abi.encode(deviation, slippage, chunk, registry.lpBps(stock), factory.bandCeiling(stock)));
    }

    function _request(address stock, uint256 n) private returns (HedgeFunFactory.Request memory q) {
        q.name = "Open Price Fork Test";
        q.symbol = "OPENPRICE";
        q.stock = stock;
        q.creator = makeAddr("open price fork creator");
        q.taxBps = 100;
        q.tp1Bps = 500;
        q.tp2Bps = 1000;
        q.dipBps = 500;
        q.lotBps = 2000;
        q.nonce = uint96(factory.strategyCount() + 2000000 + n);
        q.maxFee = factory.getDefaults().launchFeeAmount;
        (,, q.expectedOpenPriceE18,) = factory.listings(stock);
    }

    function _assertDefaultLaunchGraduatesAtTheReference(address stock, uint256 n) private {
        HedgeFunFactory.Request memory q = _request(stock, n);
        (,, bytes32 terms) = factory.predict(q);
        vm.deal(q.creator, q.maxFee);
        vm.prank(q.creator);
        uint256 id = factory.launch{value: q.maxFee}(q, terms);
        HedgeFunBondingCurve curve = HedgeFunBondingCurve(factory.curves(id));
        (address oracle,,,) = factory.listings(stock);
        (bool ok, uint256 priceE18,) = PriceOracle(oracle).lastPriceAt();
        assertTrue(ok);

        uint256 remainingBps = 10_000 - script.REFERENCE_SALE_BPS();
        uint256 raiseUsd = (curve.terminalStock() - curve.virtualStock()) * priceE18 / 1e18;
        uint256 graduationFdvUsd = curve.terminalStock() * 10_000 / remainingBps * priceE18 / 1e18;
        emit log_named_address("stock", stock);
        emit log_named_decimal_uint("  net raise, USD", raiseUsd, 18);
        emit log_named_decimal_uint("  graduation FDV, USD", graduationFdvUsd, 18);
        assertApproxEqRel(raiseUsd, REFERENCE_RAISE_USD_E18, 0.001e18);
        assertApproxEqRel(graduationFdvUsd, REFERENCE_FDV_USD_E18, 0.001e18);
    }
}
