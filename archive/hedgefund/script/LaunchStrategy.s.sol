// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {TradingCalendar} from "../src/TradingCalendar.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";

/// Launches one strategy token against a stock the factory already lists. What a front end does, as a script.
///
/// REHEARSE IT ON A FORK FIRST and read what it prints back. Nothing in this repo broadcasts a mainnet launch for
/// you: on mainnet this is a command a human runs with their own key.
///
///   anvil --fork-url https://rpc.mainnet.chain.robinhood.com --chain-id 31337 -p 8545 &
///   FACTORY=0x.. STOCK=0x.. NAME="NVDA 5% Strategy" SYMBOL=NVDA5STR \
///     forge script script/LaunchStrategy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast \
///       --unlocked --sender 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
///
/// (anvil's first account, unlocked by the local node: no key on a command line, in a rehearsal or anywhere else.
/// The same convention, and the same `--chain-id 31337`, as script/DeployStrategyLaunchpad.s.sol.)
///
/// The rule is the creator's and is frozen at launch. Defaults below are the 5% grid; every one is an env var:
///   TAX_BPS 1000  CREATOR_BPS 1000  TP1_BPS 500  TP2_BPS 1000  DIP_BPS 500  STOP_BPS 0  LOT_BPS 2000
///   BAND_BPS_PER_HOUR 0   -- how far a scheduled closure lets the V3 pool pull the price off a silent feed, per
///                            hour of silence. Must be <= factory.bandCeiling(stock), which is 0 unless the owner
///                            raised it for this stock. Replay it first: tools/band_backtest.py. On CRCL's history
///                            10 bought the whole weekend and anything more bought nothing.
///   NONCE 0               -- bump it to retry a launch whose address is taken
///   MAX_FEE               -- defaults to the fee the factory quotes right now; the launch reverts `Restated` if
///                            the owner raised it in between. The open price is pinned the same way.
///
/// LISTING IS NOT THIS SCRIPT'S JOB. `factory.list` is the owner's -- a Safe on mainnet -- and what it fixes is
/// permanent for every treasury launched under it: which oracle, and through the oracle which CALENDAR, whose
/// owner can halt every strategy priced through it. For a fork rehearsal only, REHEARSAL_LIST=1 lists the stock
/// from the broadcasting key (which must own the factory), and then FEED, POOL and CALENDAR_OWNER are all required:
/// the calendar's owner is never defaulted. OPEN_PRICE_E18 (default 5e10) and BAND_CEILING (default 0) apply there.
/// It is refused on chain id 4663 -- mainnet, or a fork that still reports it: a listing made here skips every check
/// docs/DEPLOYMENT.md asks of a real one (the oracle's ages, the feed resolved by address, a calendar owned by a
/// verified Safe), and it is permanent. Rehearse under `--chain-id 31337`, as the deploy script does.
contract LaunchStrategy is Script {
    address constant USDG      = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address constant USDG_FEED = 0x61B7e5650328764B076A108EFF5fa7282a1B9aD2;

    /// @dev approves the launch fee where it is a token, and returns the msg.value where it is native
    function _payFee(HedgeFunFactory f, address stock) internal returns (uint256) {
        HedgeFunFactory.Defaults memory d = f.getDefaults();
        if (d.launchFeeCurrency == HedgeFunFactory.FeeCurrency.Native) return d.launchFeeAmount;
        if (d.launchFeeCurrency != HedgeFunFactory.FeeCurrency.None && d.launchFeeAmount != 0) {
            IERC20(d.launchFeeCurrency == HedgeFunFactory.FeeCurrency.Stock ? stock : USDG).approve(address(f), d.launchFeeAmount);
        }
        return 0;
    }

    function _request(HedgeFunFactory f, address stock) internal view returns (HedgeFunFactory.Request memory q) {
        q.name = vm.envString("NAME"); q.symbol = vm.envString("SYMBOL"); q.stock = stock;
        q.creator = vm.envOr("CREATOR", msg.sender);
        q.taxBps = _bps("TAX_BPS", 1000);
        q.creatorBps = _bps("CREATOR_BPS", 1000);
        q.tp1Bps = _bps32("TP1_BPS", 500);                          // uint32: 100x cost is 990,000
        q.tp2Bps = _bps32("TP2_BPS", 1000);
        q.dipBps = _bps("DIP_BPS", 500);
        q.stopBps = _bps("STOP_BPS", 0);
        q.lotBps = _bps("LOT_BPS", 2000);
        q.bandBpsPerHour = _bps("BAND_BPS_PER_HOUR", 0);
        q.nonce = uint96(vm.envOr("NONCE", uint256(0)));
        q.maxFee = vm.envOr("MAX_FEE", f.getDefaults().launchFeeAmount);
        (,, q.expectedOpenPriceE18,) = f.listings(stock);
    }

    /// @dev keccak of the five-word PoolKey, exactly as v4-core's `PoolIdLibrary.toId` computes it
    function _poolId(HedgeFunFactory f, address token, address stock, address hook) internal view returns (bytes32) {
        HedgeFunFactory.Defaults memory d = f.getDefaults();
        (address c0, address c1) = token < stock ? (token, stock) : (stock, token);
        return keccak256(abi.encode(c0, c1, d.lpFee, d.tickSpacing, hook));
    }

    error RehearsalOnly();
    error OutOfRange(string name, uint256 value);

    /// @dev a bps env var, refused rather than silently truncated: `uint16(70000)` is 4464, and a rule is forever
    function _bps32(string memory name, uint256 dflt) internal view returns (uint32) {
        uint256 v = vm.envOr(name, dflt);
        if (v > type(uint32).max) revert OutOfRange(name, v);
        return uint32(v);
    }

    function _bps(string memory name, uint256 dflt) internal view returns (uint16) {
        uint256 v = vm.envOr(name, dflt);
        if (v > type(uint16).max) revert OutOfRange(name, v);
        return uint16(v);
    }

    function _rehearsalList(HedgeFunFactory f, address stock) internal {
        if (block.chainid == 4663) revert RehearsalOnly();
        address calOwner = vm.envAddress("CALENDAR_OWNER");                     // required: it can halt everything priced here
        require(calOwner != address(0), "CALENDAR_OWNER");
        TradingCalendar cal = new TradingCalendar(calOwner);
        address oracle = address(new PriceOracle(stock, vm.envAddress("FEED"), USDG_FEED, address(cal), 26 hours, 26 hours));
        f.list(stock, oracle, vm.envAddress("POOL"), vm.envOr("OPEN_PRICE_E18", uint256(5e10)), true);
        uint256 ceiling = vm.envOr("BAND_CEILING", uint256(0));
        if (ceiling > type(uint16).max) revert OutOfRange("BAND_CEILING", ceiling);
        if (ceiling != 0) f.setBandCeiling(stock, uint16(ceiling));
        console2.log("REHEARSAL listing -- calendar", address(cal), "oracle", oracle);
    }

    function run() external {
        HedgeFunFactory f = HedgeFunFactory(vm.envAddress("FACTORY"));
        address stock = vm.envAddress("STOCK");

        vm.startBroadcast();
        (address oracle,,, bool enabled) = f.listings(stock);
        if (oracle == address(0) && vm.envOr("REHEARSAL_LIST", uint256(0)) == 1) { _rehearsalList(f, stock); (oracle,,, enabled) = f.listings(stock); }
        require(oracle != address(0) && enabled, "STOCK is not listed (and enabled) on this factory; listing is the owner's call");

        HedgeFunFactory.Request memory q = _request(f, stock);
        require(q.bandBpsPerHour <= f.bandCeiling(stock), "BAND_BPS_PER_HOUR is above factory.bandCeiling(stock)");

        console2.log("=== launching", q.symbol, "===");
        console2.log("chain id", block.chainid, block.chainid == 4663 ? "(Robinhood Chain -- mainnet OR a fork of it)" : "");
        console2.log("factory ", address(f)); console2.log("stock   ", stock); console2.log("creator ", q.creator);
        console2.log("agreeing to: fee <=", q.maxFee, " open price (stock per token, 1e18) ==", q.expectedOpenPriceE18);
        console2.log("band, bps per hour of closure:", q.bandBpsPerHour, " ceiling:", f.bandCeiling(stock));

        (,, bytes32 terms) = f.predict(q);                                       // the defaults and listing as they stand now
        uint256 id = f.launch{value: _payFee(f, stock)}(q, terms);
        vm.stopBroadcast();

        (address token, address treasury, address hook,,) = f.strategies(id);
        require(token == f.predictToken(q), "landed off predict()");
        console2.log("--- launched, id", id, "---");
        console2.log("token    ", token); console2.log("treasury ", treasury); console2.log("hook     ", hook, "(the one hook; the pool id below is what its calls take)");
        console2.logBytes32(_poolId(f, token, stock, hook));
        console2.log("supply seeded into the pool:", IERC20(token).totalSupply() / 1e18);
        console2.log("factory keeps (should be 0):", IERC20(token).balanceOf(address(f)));
        (bool ok, uint256 p) = PriceOracle(oracle).tryPrice();
        if (ok) console2.log("oracle price x1e4:", p / 1e14);
        else console2.log("oracle: shut (closure or after hours). Expected out of hours; a band-0 rule waits for the open.");
        console2.log("");
        console2.log("NEXT: the first buyer brings the first stock -- the pool opened single-sided. Then anyone may call");
        console2.log("hook.sweep(poolId) and treasury.book() / takeProfit() / buyDip() / buyback().");
    }
}
