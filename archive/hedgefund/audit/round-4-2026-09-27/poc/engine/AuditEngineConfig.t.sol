// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Round-4 external audit, engine lane: the CONFIG surface of HedgeFunV2EngineTreasury.
//   E-1  maxTradeUsdg below minLotUsdg is accepted and the treasury can never execute anything
//   E-2  deadbandBps has no floor against execution friction; a 1 bp band churns on every print and bleeds value
//   E-4  the daily cap is a UTC calendar epoch: 2x maxDaily inside cooldown+1 seconds; maxDaily has no ceiling
//   E-6  setEngineConfig validates no word; predict succeeds and launch fails as an opaque TreasuryDeployFailed
//   E-3  execute() pays no bounty to its caller
//   E-8  setEngineConfig / setStrategyKind still write a launched salt's record (view only, treasury unchanged)

import {HedgeFunFactory} from "../../../../src/HedgeFunFactory.sol";
import {HedgeFunTreasuryBase} from "../../../../src/HedgeFunTreasuryBase.sol";
import {HedgeFunV2EngineTreasury} from "../../../../src/v2/HedgeFunV2EngineTreasury.sol";
import {V2TreasuryDeployer} from "../../../../src/v2/V2TreasuryDeployer.sol";
import {
    EngineConfig, IStrategyPolicy, StrategyAction, StrategyCapabilities, StrategyContext, StrategyIntent
} from "../../../../src/v2/strategy/IStrategyPolicy.sol";
import {AuditEngineFixture} from "./AuditEngineFixture.sol";

/// @dev ignores the cooldown and always asks to sell everything; the core must bound it
contract AlwaysSellAll is IStrategyPolicy {
    function policyMetadata() external pure returns (uint32, uint32, uint256) {
        return (StrategyCapabilities.SPOT_ENGINE_V1, StrategyCapabilities.CONFIG_SCHEMA_V1, StrategyCapabilities.SPOT_SELL);
    }
    function decide(StrategyContext calldata c, EngineConfig calldata, bytes32 s) external pure returns (StrategyIntent memory) {
        return StrategyIntent(c.configHash, c.nonce, StrategyAction.SellStock, type(uint256).max, s);
    }
}

contract AuditEngineConfigTest is AuditEngineFixture {
    bytes32 internal rebalanceKey;

    function setUp() public {
        _setUpEngine(18, true);
        rebalanceKey = _registerPolicy(address(rebalance), 150_000, "rebalance");
    }

    // ------------------------------------------------------------------ E-1: a treasury that can never act
    /// The constructor checks fifteen things about the config and not that a single action can ever clear the
    /// core's own minimum lot. maxTrade = minLot - 1 launches, graduates, and then every path ends in NotDue: over-
    /// weight, under-weight, after a doubling, after a halving, after a week. V1 refuses the analogous
    /// `sellChunkUsdg < minLotUsdg` in `_setDefaults` and `_lotParams` for exactly this reason.
    function test_E1_maxTradeBelowMinLotLaunchesAndIsPermanentlyInert() public {
        HedgeFunV2EngineTreasury t = _launchGraduated(_config(rebalanceKey, 5000, 500, 60, MIN_LOT - 1, 10 * MIN_LOT), 1);
        assertGt(t.bookedStock(), 0, "graduation delivered strategy capital");
        assertEq(t.reserveUsdg(), 0);
        // 100% stock against a 50% target: the policy asks to sell, the core refuses the dust
        (bool due,,) = t.preview();
        assertFalse(due);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();

        // make it under-weight instead
        usdg.mint(address(t), 10 * _stockValue(t, PRICE));
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();

        // a doubling, a halving, a week, a fresh epoch: never
        _market(2 * PRICE);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();
        _market(PRICE / 2);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();
        vm.warp(block.timestamp + 7 days);
        _market(PRICE);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
        t.execute();
        assertEq(t.strategyNonce(), 0, "no action ever executed");
        assertEq(t.lastStrategyAt(), 0);

        // the same launch one unit higher works on the first call
        HedgeFunV2EngineTreasury ok = _launchGraduated(_config(rebalanceKey, 5000, 500, 60, MIN_LOT, 10 * MIN_LOT), 2);
        ok.execute();
        assertEq(ok.strategyNonce(), 1);
    }

    // ------------------------------------------------------------------ E-2: no friction floor on the deadband
    /// V1 refuses `tp1Bps < 2 * (maxSlippageBps + poolFeeBps)` and `dipBps < 2 * (...)` so that the rule clears its own
    /// execution cost. The engine accepts deadbandBps = 1 against a 130 bp friction allowance (100 bp slippage
    /// + 30 bp pool fee). Every alternating Chainlink print then produces a trade, and each round trip returns
    /// the treasury to the same price with less value. A 5% band trades zero times on the same prints.
    function test_E2_oneBpDeadbandTradesOnEveryPrintAndBleedsValue() public {
        HedgeFunV2EngineTreasury churn = _launchGraduated(_config(rebalanceKey, 5000, 1, 1, 1_000_000e6, type(uint256).max), 3);
        HedgeFunV2EngineTreasury sane = _launchGraduated(_config(rebalanceKey, 5000, 500, 1, 1_000_000e6, type(uint256).max), 4);
        // both start 100% stock: bring both to target at the same price, then compare
        usdg.mint(address(churn), _stockValue(churn, PRICE));
        usdg.mint(address(sane), _stockValue(sane, PRICE));
        (bool dueChurn,,) = churn.preview();
        (bool dueSane,,) = sane.preview();
        assertFalse(dueChurn, "at target: nothing due");
        assertFalse(dueSane);

        uint256 v0 = _totalValue(churn, PRICE);
        uint256 sane0 = _totalValue(sane, PRICE);
        uint256 trades;
        // twenty round trips of the feed's own 0.5% deviation trigger
        for (uint256 i; i < 20; ++i) {
            vm.warp(block.timestamp + 1);
            _market(PRICE * 1005 / 1000);
            if (_tryExecute(churn)) ++trades;
            vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
            sane.execute();
            vm.warp(block.timestamp + 1);
            _market(PRICE);
            if (_tryExecute(churn)) ++trades;
            vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);
            sane.execute();
        }
        uint256 v1 = _totalValue(churn, PRICE);
        emit log_named_uint("E-2 trades on 40 prints, deadband 1 bp", trades);
        emit log_named_uint("E-2 value before (USDG e6)", v0);
        emit log_named_uint("E-2 value after  (USDG e6)", v1);
        emit log_named_uint("E-2 value lost   (USDG e6)", v0 - v1);
        assertEq(trades, 40, "every print past a 1 bp band is a trade");
        assertLt(v1, v0, "each round trip at the same price costs friction");
        assertEq(_totalValue(sane, PRICE), sane0, "a 5% band traded nothing and lost nothing");
        assertEq(sane.strategyNonce(), 0);
    }

    function _tryExecute(HedgeFunV2EngineTreasury t) private returns (bool ok) {
        try t.execute() { ok = true; } catch {}
    }

    // ------------------------------------------------------------------ E-4: UTC epoch, not a rolling day
    /// Documented in STRATEGY_ENGINE.md as an open decision. Measured: with cooldown 1 s, two full daily caps
    /// clear one second apart across midnight UTC. And maxDailyTurnoverUsdg accepts type(uint256).max, so the
    /// "daily bound" is a creator's choice with no owner ceiling; only maxTrade is capped (by sellChunkUsdg).
    function test_E4_twoDailyCapsOneSecondApartAcrossMidnightUtc() public {
        bytes32 key = _registerPolicy(address(new AlwaysSellAll()), 100_000, "always-sell");
        HedgeFunV2EngineTreasury t = _launchGraduated(_config(key, 5000, 500, 1, 100e6, 100e6), 5);
        assertGt(_stockValue(t, PRICE), 400e6, "enough excess to fill two caps");
        uint256 midnight = (block.timestamp / 1 days + 1) * 1 days;
        vm.warp(midnight - 2);
        _market(PRICE);
        t.execute();
        assertEq(t.turnoverInEpoch(), 100e6);
        vm.warp(midnight - 1);                                   // past the 1 s cooldown, same UTC day
        _market(PRICE);
        vm.expectRevert(HedgeFunTreasuryBase.NotDue.selector);  // cap reached
        t.execute();
        vm.warp(midnight);                                       // one second later
        _market(PRICE);
        t.execute();
        assertEq(t.turnoverInEpoch(), 100e6, "a fresh epoch, a fresh cap");
        assertEq(t.strategyNonce(), 2, "200e6 of turnover against a 100e6 'daily' cap, two seconds apart");

        // no ceiling on the daily word
        HedgeFunV2EngineTreasury unbounded = _launchGraduated(_config(rebalanceKey, 5000, 500, 1, 100e6, type(uint256).max), 6);
        assertTrue(unbounded.configHash() != bytes32(0));
    }

    // ------------------------------------------------------------------ E-6: opaque failure at launch
    /// `setEngineConfig` checks the policy and the schema, and none of the three words. A zero target predicts an
    /// address and fails inside CREATE2, whose revert reason does not survive. V1 mirrors every constructor check in
    /// `_setDefaults` for this reason ("a default the treasury refuses bricks every launch as an opaque
    /// TreasuryDeployFailed"). The fee transfer is inside the same transaction, so nothing is lost.
    function test_E6_setEngineConfigAcceptsWhatTheConstructorRefuses() public {
        HedgeFunFactory.Request memory q = _request();
        q.nonce = 7;
        // target 0, deadband 0, cooldown 0, maxTrade 0, daily 0
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(rebalanceKey, 0, 0, 0, 0, 0));
        (, address predicted, bytes32 terms) = factory.predict(q);
        assertTrue(predicted != address(0), "predict has no opinion");
        vm.expectRevert(V2TreasuryDeployer.TreasuryDeployFailed.selector);
        factory.launch(q, terms);
        // maxTrade above the listing's sell chunk: same shape
        HedgeFunFactory.Request memory q2 = _request();
        q2.nonce = 8;
        deployer.setEngineConfig(q2.symbol, q2.nonce, engineKind, _config(rebalanceKey, 5000, 500, 60, uint256(type(uint128).max) + 1, type(uint256).max));
        (,, bytes32 terms2) = factory.predict(q2);
        vm.expectRevert(V2TreasuryDeployer.TreasuryDeployFailed.selector);
        factory.launch(q2, terms2);
    }

    // ------------------------------------------------------------------ E-3: nobody is paid to call execute()
    function test_E3_executePaysNoBounty() public {
        HedgeFunV2EngineTreasury t = _launchGraduated(_config(rebalanceKey, 5000, 500, 60, 100e6, 500e6), 9);
        address keeper = address(0xBEEF);
        vm.prank(keeper);
        t.execute();
        assertEq(stock.balanceOf(keeper), 0);
        assertEq(usdg.balanceOf(keeper), 0);
        // V1's rule pays bountyBps of what a call produced; the engine's Params still carry it, unused
        assertEq(t.params().bountyBps, 50);
    }

    // ------------------------------------------------------------------ E-8: launched salt still writable
    function test_E8_launchedSaltRecordIsStillWritableButInert() public {
        HedgeFunFactory.Request memory q = _request();
        q.nonce = 10;
        EngineConfig memory c = _config(rebalanceKey, 5000, 500, 60, 100e6, 500e6);
        HedgeFunV2EngineTreasury t = _launchGraduated(c, 10);
        bytes32 salt = keccak256(abi.encode(q.symbol, address(this), q.nonce));
        // rewrite the record after launch: the deployer emits EngineConfigSet again and the view changes
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, _config(rebalanceKey, 9000, 100, 1, 1e6, 1e6));
        assertEq(uint256(deployer.engineConfigOf(salt).words[0]) & 0xffff, 9000, "view now disagrees with the treasury");
        deployer.setStrategyKind(q.symbol, q.nonce, 0);
        assertEq(deployer.strategyKindOf(salt), 0);
        // the treasury is what it was
        assertEq(uint256(t.engineConfig().words[0]) & 0xffff, 5000);
        // and a relaunch on the same salt cannot happen: the token address is taken
        (,, bytes32 terms) = factory.predict(q);
        vm.expectRevert();
        factory.launch(q, terms);
    }
}
