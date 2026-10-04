// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {TestUsdg, TestStock} from "./testnet/TestnetAssets.sol";
import {TestnetMarket, IV3Pool} from "./testnet/TestnetMarket.sol";

/// @notice Funds team wallets on the Hedgefun V2 testnet deployment (chain 46630) with test assets, and makes each
///         stock's pool ready for treasuries. Reads the address book `DeployV2Testnet` wrote. Operator only: the
///         operator owns every test token and the market.
///
///   run()            TEAM=0xA,0xB,...  tops every TEAM address up to the targets below, and pokes any pool whose
///                                      observation ring is not live yet
///   topUp(address)   the same for one address
///   pokeAll()        only the pool step
///
/// Top-ups mint the shortfall only, so running it again is harmless. Targets: SEED_USDG whole tUSDG (default
/// 100,000) and SEED_STOCK_USD dollars of each test stock at its feed price (default 25,000). Test ETH for gas comes
/// from the public faucet, never from here.
///
///   OPERATOR=0x.. TEAM=0x..,0x.. forge script script/SeedTestnet.s.sol:SeedTestnet \
///     --rpc-url https://rpc.testnet.chain.robinhood.com --sender $OPERATOR [--account <keystore> --broadcast]
contract SeedTestnet is Script {
    uint256 internal constant CHAIN_ID = 46630;
    uint16 internal constant MIN_CARDINALITY = 660;     // PoolTrader: TWAP_WINDOW + RING_MARGIN

    error WrongChain(uint256 chainId);
    error NotOperator(address sender, address operator);
    error NoTeam();

    struct Book {
        TestUsdg usdg;
        TestnetMarket market;
        string[] symbols;
        TestStock[] stocks;
        PriceOracle[] oracles;
        address[] pools;
    }

    function run() external {
        address[] memory team = vm.envAddress("TEAM", ",");
        if (team.length == 0) revert NoTeam();
        Book memory b = _begin();
        vm.startBroadcast();
        for (uint256 i; i < team.length; i++) _topUp(b, team[i]);
        _pokeAll(b);
        vm.stopBroadcast();
    }

    function topUp(address who) external {
        Book memory b = _begin();
        vm.startBroadcast();
        _topUp(b, who);
        vm.stopBroadcast();
    }

    function pokeAll() external {
        Book memory b = _begin();
        vm.startBroadcast();
        _pokeAll(b);
        vm.stopBroadcast();
    }

    function _begin() internal view returns (Book memory b) {
        if (block.chainid != CHAIN_ID) revert WrongChain(block.chainid);
        string memory json = vm.readFile(vm.envOr("ADDRESS_BOOK", string("deploy/testnet-v2.json")));
        address operator = vm.parseJsonAddress(json, ".operator");
        if (msg.sender != operator) revert NotOperator(msg.sender, operator);
        b.usdg = TestUsdg(vm.parseJsonAddress(json, ".usdg"));
        b.market = TestnetMarket(vm.parseJsonAddress(json, ".market"));
        b.symbols = vm.parseJsonKeys(json, ".stocks");
        uint256 n = b.symbols.length;
        b.stocks = new TestStock[](n);
        b.oracles = new PriceOracle[](n);
        b.pools = new address[](n);
        for (uint256 i; i < n; i++) {
            string memory k = string.concat(".stocks.", b.symbols[i]);
            b.stocks[i] = TestStock(vm.parseJsonAddress(json, string.concat(k, ".token")));
            b.oracles[i] = PriceOracle(vm.parseJsonAddress(json, string.concat(k, ".oracle")));
            b.pools[i] = vm.parseJsonAddress(json, string.concat(k, ".pool"));
        }
    }

    function _topUp(Book memory b, address who) internal {
        uint256 usdgTarget = vm.envOr("SEED_USDG", uint256(100_000)) * 1e6;
        uint256 stockUsd = vm.envOr("SEED_STOCK_USD", uint256(25_000));
        _mintTo(address(b.usdg), who, usdgTarget, "tUSDG");
        for (uint256 i; i < b.stocks.length; i++) {
            (bool ok, uint256 price,) = b.oracles[i].lastPriceAt();
            if (!ok || price == 0) {
                console2.log("skipped: no feed price for", b.symbols[i]);
                continue;
            }
            _mintTo(address(b.stocks[i]), who, stockUsd * 1e36 / price, b.symbols[i]);
        }
    }

    function _mintTo(address token, address who, uint256 target, string memory symbol) internal {
        uint256 have = TestUsdg(token).balanceOf(who);
        if (have >= target) return;
        TestUsdg(token).mint(who, target - have);
        console2.log(string.concat("minted ", symbol, " to"), who, target - have);
    }

    /// a pool's grown observation ring goes live on its first write in a later second than the last one
    function _pokeAll(Book memory b) internal {
        for (uint256 i; i < b.pools.length; i++) {
            (,,, uint16 card,,,) = IV3Pool(b.pools[i]).slot0();
            if (card >= MIN_CARDINALITY) continue;
            b.market.poke(b.pools[i]);
            console2.log(string.concat("poked ", b.symbols[i], " pool"), b.pools[i]);
        }
    }
}
