// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Round-4 external audit, engine lane. Shared setup for the AuditEngine*.t.sol proofs of concept.
// Inherits the repository's own V2FactoryFixture (real PoolManager, mined hook, real V2 factory and deployers)
// and swaps only the stock/USDG V3 venue for the flat-price MockPool from test/mocks/Mocks.sol, which -- unlike
// the engine suite's EngineVenue -- supports BOTH token orderings and any stock decimals.

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {HedgeFunFactory} from "../../../../src/HedgeFunFactory.sol";
import {HedgeFunBondingCurve} from "../../../../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2EngineTreasury} from "../../../../src/v2/HedgeFunV2EngineTreasury.sol";
import {V2TreasuryDeployer} from "../../../../src/v2/V2TreasuryDeployer.sol";
import {EngineConfig, StrategyCapabilities} from "../../../../src/v2/strategy/IStrategyPolicy.sol";
import {V2RebalancePolicy} from "../../../../src/v2/strategy/V2RebalancePolicy.sol";
import {MockPool} from "../../../../test/mocks/Mocks.sol";
import {V2FactoryFixture} from "../../../../test/utils/V2FactoryFixture.sol";

abstract contract AuditEngineFixture is V2FactoryFixture {
    uint256 internal constant PRICE = 100e18;   // USDG per whole stock token, 1e18-scaled
    uint256 internal constant MIN_LOT = 5e6;    // the fixture's Defaults.minLotUsdg

    V2TreasuryDeployer internal deployer;
    V2RebalancePolicy internal rebalance;
    MockPool internal venue;
    uint8 internal engineKind;
    uint256 internal scale;
    uint8 internal stockDecimals;

    /// @param decimals_ stock token decimals (18 on Robinhood Chain; 6 exercised as well)
    /// @param stockIsToken0 the V3 pool's token ordering. USDG is token0 in 16 of the 25 watched pools and token1
    ///        in 9, and the engine suite only ever exercises stock-as-token0.
    function _setUpEngine(uint8 decimals_, bool stockIsToken0) internal {
        _setUpV2(decimals_);
        stockDecimals = decimals_;
        scale = 1e18 * 10 ** uint256(decimals_) / 1e6;
        venue = new MockPool(address(stock), address(usdg), stockIsToken0, 3000, scale);
        venue.setPrice(PRICE);
        v3f.set(address(stock), address(usdg), 3000, address(venue));
        vm.prank(owner);
        factory.list(address(stock), address(oracle), address(venue), openPrice, true);
        usdg.mint(address(venue), 100_000_000e6);
        stock.mint(address(venue), 1_000_000 * 10 ** uint256(decimals_));

        deployer = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        rebalance = new V2RebalancePolicy();
        (address a, address b) = deployer.makeChunks(type(HedgeFunV2EngineTreasury).creationCode);
        vm.prank(owner);
        engineKind = deployer.registerEngineKind(
            a, b, StrategyCapabilities.SPOT_ENGINE_V1, StrategyCapabilities.CONFIG_SCHEMA_V1,
            StrategyCapabilities.SPOT_BUY | StrategyCapabilities.SPOT_SELL
        );
    }

    function _registerPolicy(address implementation, uint32 maxGas, bytes32 label) internal returns (bytes32 key) {
        vm.prank(owner);
        key = deployer.registerPolicy(
            implementation, maxGas, 160, keccak256(abi.encode("audit4-deps", label)), keccak256(abi.encode("audit4-audit", label))
        );
    }

    function _config(bytes32 policyKey, uint16 targetBps, uint16 deadbandBps, uint32 cooldown, uint256 maxTrade, uint256 maxDaily)
        internal pure returns (EngineConfig memory c)
    {
        c.schema = StrategyCapabilities.CONFIG_SCHEMA_V1;
        c.engineVersion = StrategyCapabilities.SPOT_ENGINE_V1;
        c.policyKey = policyKey;
        c.words[0] = bytes32(uint256(targetBps) | uint256(deadbandBps) << 16 | uint256(cooldown) << 32);
        c.words[1] = bytes32(maxTrade);
        c.words[2] = bytes32(maxDaily);
    }

    /// launch an engine treasury under `c` for salt (symbol, this, nonce) and graduate its curve in one buy
    function _launchGraduated(EngineConfig memory c, uint96 nonce) internal returns (HedgeFunV2EngineTreasury t) {
        HedgeFunFactory.Request memory q = _request();
        q.nonce = nonce;
        deployer.setEngineConfig(q.symbol, q.nonce, engineKind, c);
        (, address predicted, bytes32 terms) = factory.predict(q);
        uint256 id = factory.launch(q, terms);
        (, address deployed,,,) = factory.strategies(id);
        assertEq(deployed, predicted, "CREATE2 prediction must hold for an engine kind");
        t = HedgeFunV2EngineTreasury(deployed);
        HedgeFunBondingCurve curve = HedgeFunBondingCurve(factory.curves(id));
        stock.approve(address(curve), type(uint256).max);
        _graduateV2(curve);
    }

    /// move Chainlink and the venue together, the way a real print followed by arbitrage would
    function _market(uint256 price) internal {
        venue.setPrice(price);
        stockFeed.set(int256(price / 1e10));
        usdgFeed.set(1e8);
    }

    function _stockValue(HedgeFunV2EngineTreasury t, uint256 price) internal view returns (uint256) {
        return t.bookedStock() * price / scale;
    }

    function _totalValue(HedgeFunV2EngineTreasury t, uint256 price) internal view returns (uint256) {
        return _stockValue(t, price) + t.reserveUsdg();
    }
}
