// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HedgeFunFactory} from "../../src/HedgeFunFactory.sol";

/// @notice The factory defaults a Robinhood Chain (4663) V2 core is constructed with.
/// @dev One explicit copy, so the fork rehearsal and the deployment cannot disagree, and nothing here is read from
///      a testnet script. These are release CANDIDATES: `DeployV2MainnetCore` refuses to run unless the caller
///      supplies their hash, which is how a reviewer confirms the exact values and how an edit here is noticed.
///      A treasury and a curve freeze what they read at launch; the owner can change these for later launches.
library V2MainnetDefaults {
    /// The share of supply every launch sells on its curve: `CurveDeployer` is constructed with it and accepts
    /// no other. 79.31%, the ordinary-curve allocation of the launchpads this one is compared with.
    uint16 internal constant SALE_BPS = 7931;

    function release() internal pure returns (HedgeFunFactory.Defaults memory d) {
        d.supply = 1_000_000_000e18;
        d.lpFee = 3000; // V2's locked liquidity vault collects fees; V1's zero-fee default cannot be reused.
        d.tickSpacing = 60;
        d.minTaxBps = 100; // the 1% base tax; a creator chooses 1% to 15%
        d.maxTaxBps = 1500;
        d.protocolBps = 2000;
        d.maxCreatorBps = 1000; // up to 10% of the collected tax, not 10% of trade volume
        d.spikeBps = 0; // V2 LP fees can fund buybacks without strategy profit; no buyback-triggered sell spike.
        d.spikeSeconds = 0;
        d.sweepTipBps = 0;
        d.snipeBps = 9900;
        d.snipeSeconds = 3;
        d.bountyBps = 10; // 0.1%: too little to pay an outside keeper for a take-profit, so the keeper is run in-house
        d.maxSlippageBps = 100;
        d.maxDeviationBps = 50;
        d.maxBuybackImpactBps = 300;
        d.buybackCooldown = 60;
        d.minLotUsdg = 5e6;
        d.buybackChunkUsdg = 500e6;
        d.sellChunkUsdg = 2_000e6;
        d.launchFeeCurrency = HedgeFunFactory.FeeCurrency.Native;
        d.launchFeeAmount = 0.0005 ether;
    }
}
