// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2BuybackTreasury} from "../src/v2/HedgeFunV2BuybackTreasury.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// Round 4, delta lane: round 3's I-8 was Info because "kind 1 is marked DRAFT and registered by nobody".
/// d5218ee relabels kind 1 "Opt-in: production must register its exact code chunks", the rehearsal script
/// registers it and the CI fork gate exercises it. The condition that made I-8 Info is gone; the defect is not.
contract AuditDelta4Kind1 is V2FactoryFixture {
    HedgeFunV2BuybackTreasury internal treasury;
    HedgeFunBondingCurve internal curve;

    function setUp() public {
        _setUpV2(18);
        V2TreasuryDeployer deployer = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        (address a, address b) = deployer.makeChunks(type(HedgeFunV2BuybackTreasury).creationCode);
        vm.prank(owner);
        assertEq(deployer.registerKind(a, b), 1);
        HedgeFunFactory.Request memory q = _request();
        deployer.setStrategyKind(q.symbol, q.nonce, 1);
        (,, bytes32 terms) = factory.predict(q);
        uint256 id = factory.launch(q, terms);
        curve = HedgeFunBondingCurve(factory.curves(id));
        (, address t,,,) = factory.strategies(id);
        treasury = HedgeFunV2BuybackTreasury(t);
        stock.approve(address(curve), type(uint256).max);
        vm.warp(curve.launchedAt() + curve.snipeSeconds());
    }

    /// The published scorecard is `(stockEquivalentHeld + totalStockSpentOnBuybacks) / totalStockReceived`
    /// (README.md, docs/REFERENCE.md). Kind 1's `book()` never reaches `_book`, the only writer of the
    /// denominator, so for a kind-1 strategy it is 0 for life while both numerator terms grow.
    function test_kindOneScorecardDividesByZeroForLife() public {
        _graduateV2(curve);
        assertGt(treasury.buybackStock(), 0, "the graduation share was booked as budget");
        assertEq(treasury.totalStockReceived(), 0, "but the denominator never moved");
        (bool ok, uint256 held) = treasury.stockEquivalentHeld();
        assertTrue(ok); assertGt(held, 0, "numerator term 1 > 0");
        treasury.buyback();
        assertGt(treasury.totalStockSpentOnBuybacks(), 0, "numerator term 2 > 0");
        assertEq(treasury.totalStockReceived(), 0, "denominator still 0 after spending");
        // more stock arrives later (sell tax, LP fees): booked as budget, denominator untouched
        stock.mint(address(treasury), 7e18);
        assertTrue(treasury.book());
        assertEq(treasury.totalStockReceived(), 0);
        emit log_named_uint("scorecard numerator (stock units)", held + treasury.totalStockSpentOnBuybacks());
        emit log_named_uint("scorecard denominator", treasury.totalStockReceived());
    }
}
