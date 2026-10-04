// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {TradingCalendar} from "../src/TradingCalendar.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolId} from "v4-core/src/types/PoolId.sol";
import {HedgeFunFactory, TreasuryDeployer, TokenDeployer} from "../src/HedgeFunFactory.sol";
import {HedgeFunToken} from "../src/HedgeFunToken.sol";
import {HedgeFunTreasury} from "../src/HedgeFunTreasury.sol";
import {HedgeFunHook} from "../src/hooks/HedgeFunHook.sol";
import {HedgeFunLaunchRouter} from "../src/HedgeFunLaunchRouter.sol";
import {HedgeFunTradeRouter} from "../src/HedgeFunTradeRouter.sol";

interface IV3Pool {
    function token0() external view returns (address);
    function swap(address recipient, bool zeroForOne, int256 amountSpecified, uint160 sqrtPriceLimitX96, bytes calldata data) external returns (int256, int256);
}

/// TEST ONLY. Buys a stock with USDG in a V3 pool and sends it where it is told -- an EOA cannot answer a V3 swap
/// callback, and the chain has no swap router wired to this factory. Holds nothing between calls; `minOut` is the only
/// protection, which is enough for the pocket-money sizes of a test run.
contract TestStockBuyer {
    address immutable usdg; address private _pool;
    constructor(address usdg_) { usdg = usdg_; }
    function buy(address pool, uint256 usdgIn, uint256 minOut, address to) external returns (uint256 out) {
        IERC20(usdg).transferFrom(msg.sender, address(this), usdgIn);
        bool zeroForOne = IV3Pool(pool).token0() == usdg;
        _pool = pool;
        (int256 a0, int256 a1) = IV3Pool(pool).swap(to, zeroForOne, int256(usdgIn), zeroForOne ? 4295128740 : 1461446703485210103287273052203988822378723970341, "");
        _pool = address(0);
        out = uint256(-(zeroForOne ? a1 : a0));
        require(out >= minOut, "TestStockBuyer: too little");
    }
    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        require(msg.sender == _pool, "not the pool");
        IERC20(usdg).transfer(msg.sender, uint256(a0 > 0 ? a0 : a1));
    }
}

/// A THROWAWAY run on the real chain: one key deploys everything, owns everything, lists five stocks and launches a
/// TEST token against each -- so the rule can be watched against real prints, real pools and real traders, which no
/// fork can show. It is NOT the production deployment and must never be mistaken for it:
///
///   - the broadcaster is the factory's owner, the calendar's owner and the protocol payout. `DeployStrategyLaunchpad`
///     refuses exactly that on this chain, on purpose; this script exists because a test wants the opposite.
///   - public launch stays CLOSED, so nobody else can launch through this factory.
///   - every token is named "TEST ..." / "t<SYM>STR" and its page says so, the launch fee is off, and the minimum lot is 0.20 USDG so that a few
///     dollars of trading is enough to see `book`, `takeProfit` and the buy-back happen.
///   - these are the release contracts (one singleton hook, tokens that carry their own page), deployed a SECOND time
///     under a throwaway owner. Nothing here is, or migrates to, the production deployment.
///
/// Three entry points, each its own command (add `--broadcast --account <keystore name>` to send; without it forge only
/// simulates against the live chain and prints what it would do):
///
///   forge script script/TestRun.s.sol --sig "deploy()"                 --rpc-url robinhood
///   FACTORY=0x.. ROUTER=0x.. forge script script/TestRun.s.sol --sig "trade(uint256)" 5000000 --rpc-url robinhood
///   FACTORY=0x..             forge script script/TestRun.s.sol --sig "seed(uint256,uint256)" 20000000 20000000 --rpc-url robinhood
///   FACTORY=0x..             forge script script/TestRun.s.sol --sig "keep()"          --rpc-url robinhood
///
/// `seed(stockUsdgEach, reserveUsdgEach)` gives every treasury a first lot and a dip reserve, from USDG alone: it buys
/// `stockUsdgEach` of the stock in the listing's V3 pool straight into the treasury, sends `reserveUsdgEach` of USDG
/// after it, and books. **It is ONE WAY -- nothing sent to a treasury can ever be taken out, by anyone -- so seed what you
/// are content to leave there.** It is what makes a short test worth watching: the first lot sets the dip reference,
/// so a 3% fall on AMZN or META buys a rung from the reserve within days, where a 30% take-profit may take a year.
/// `trade(usdgEach)` buys each token with that much USDG through `HedgeFunTradeRouter` and sells half straight back, so both
/// taxes exist. `keep()` is the keeper: it tries every permissionless action on every strategy and sends only the ones
/// that would succeed. Run it in a loop (`while true; do ...; sleep 60; done`) and the rule runs itself.
contract TestRun is Script {
    address constant PM         = 0x8366a39CC670B4001A1121B8F6A443A643e40951;
    address constant V3_FACTORY = 0x1f7d7550B1b028f7571E69A784071F0205FD2EfA;
    address constant USDG       = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address constant USDG_FEED  = 0x61B7e5650328764B076A108EFF5fa7282a1B9aD2;

    struct Pick { string sym; address stock; address feed; address pool; uint16 tp1; uint16 tp2; uint16 dip; uint16 lot; uint16 band; }

    /// the first batch and the rule `docs/rule-backtest` picked for each; pools and feeds as `test/FirstBatchFork.t.sol`
    function _picks() internal pure returns (Pick[5] memory p) {
        p[0] = Pick("CRCL", 0xdF0992E440dD0be65BD8439b609d6D4366bf1CB5, 0x6652eDf64bA3731C4F2D3ce821A0Fb1f1f6b482a, 0x654E4143e82a5824445Ade0824351C2A9ACD95a8, 2000, 4000, 2000, 2000, 10);   // band 10: its closures needed 5.9 bps/h
        p[1] = Pick("USAR", 0xd917B029C761D264c6A312BBbcDA868658eF86a6, 0xA994d3684e8400A6c8078226925779FdeE682DD9, 0x04391780F519B7d3ba59c9590459D76e23d225C4, 3000, 6000, 1500, 2000, 0);    // band 0: an $80k pool
        p[2] = Pick("GME",  0x1b0E319c6A659F002271B69dB8A7df2F911c153E, 0x27C71df6A64fB476468EdF256CF72c038baB5B67, 0xE2b46c905E12Ab8E2f864e4821a4325884C1B126, 3000, 6000, 800, 5000, 5);
        p[3] = Pick("AMZN", 0x12f190a9F9d7D37a250758b26824B97CE941bF54, 0xD5a1508ceD74c084eBf3cBe853e2C968fB2a651C, 0x8AC92DA74AB5F3b1d024Dc1943Ad7e15Dc4179Ef, 3000, 6000, 300, 5000, 5);
        p[4] = Pick("META", 0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35, 0x7C38C00C30BEe9378381E7B6135d7283356D71b1, 0x107a7Cb40d8665360ba10E59471Af06150A50922, 3000, 6000, 300, 5000, 5);
    }

    function _defaults() internal pure returns (HedgeFunFactory.Defaults memory d) {
        d.supply = 1_000_000_000e18; d.tickSpacing = 60; d.minTaxBps = 100; d.maxTaxBps = 1500; d.protocolBps = 2000; d.maxCreatorBps = 3000;
        d.spikeBps = 9000; d.spikeSeconds = 120; d.sweepTipBps = 50; d.bountyBps = 50; d.maxSlippageBps = 100; d.maxDeviationBps = 50;
        d.maxBuybackImpactBps = 300; d.buybackCooldown = 60; d.snipeBps = 9900; d.snipeSeconds = 3;
        d.sellChunkUsdg = 2_000e6;
        d.minLotUsdg = 2e5;            // TEST: 0.20 USDG, so pocket-money trading produces lots (production: 5 USDG)
        d.buybackChunkUsdg = 50e6;     // TEST: 50 USDG a call (production: 500)
        d.launchFeeCurrency = HedgeFunFactory.FeeCurrency.None;
    }

    /// @dev the hook's permissions are the low 14 bits of its address, so its salt is mined -- ONCE, for the one hook
    function _mineHook() internal view returns (bytes32 salt, address at) {
        bytes32 h = keccak256(abi.encodePacked(type(HedgeFunHook).creationCode, abi.encode(PM)));
        for (uint256 i; i < 5_000_000; i++) {
            at = vm.computeCreate2Address(bytes32(i), h, CREATE2_FACTORY);
            if (uint160(at) & 0x3FFF == 0x2844 && at.code.length == 0) return (bytes32(i), at);   // skip a hook already deployed from this code
        }
        revert("no hook salt");
    }

    // ------------------------------------------------------------------------------------------------ 1. deploy
    function deploy() external {
        (bytes32 hookSalt, address hookAt) = _mineHook();
        vm.startBroadcast();
        (, address me,) = vm.readCallers();                                     // whoever is actually broadcasting
        TradingCalendar cal = new TradingCalendar(me);
        HedgeFunHook hook = new HedgeFunHook{salt: hookSalt}(IPoolManager(PM));
        require(address(hook) == hookAt, "hook not where mined");
        HedgeFunFactory f = new HedgeFunFactory(me, PM, V3_FACTORY, USDG, me, address(new TreasuryDeployer()), address(new TokenDeployer()),
            address(hook), _defaults());
        HedgeFunLaunchRouter lr = new HedgeFunLaunchRouter(f);
        HedgeFunTradeRouter tr = new HedgeFunTradeRouter(f);
        console2.log("TEST RUN -- owner / protocol / calendar owner / creator are all", me);
        console2.log("FACTORY=", address(f)); console2.log("ROUTER=", address(tr));
        console2.log("hook (one for every strategy)", address(hook));
        console2.log("launch router", address(lr)); console2.log("calendar", address(cal));

        Pick[5] memory picks = _picks();
        for (uint256 i; i < picks.length; i++) _listAndLaunch(f, address(cal), picks[i], me);
        vm.stopBroadcast();
    }

    function _listAndLaunch(HedgeFunFactory f, address cal, Pick memory k, address me) internal {
        address oracle = address(new PriceOracle(k.stock, k.feed, USDG_FEED, cal, 26 hours, 26 hours));
        f.list(k.stock, oracle, k.pool, 5e10, true);
        if (k.band != 0) f.setBandCeiling(k.stock, k.band);
        HedgeFunFactory.Request memory q;
        q.name = string.concat("TEST ", k.sym, " Strategy"); q.symbol = string.concat("t", k.sym, "STR"); q.stock = k.stock; q.creator = me;
        q.taxBps = 1000; q.creatorBps = 1000; q.tp1Bps = k.tp1; q.tp2Bps = k.tp2; q.dipBps = k.dip; q.stopBps = 0; q.lotBps = k.lot;
        q.bandBpsPerHour = k.band; q.expectedOpenPriceE18 = 5e10;
        (,, bytes32 terms) = f.predict(q);                                       // the terms this launch agrees to
        HedgeFunToken.Info memory page;
        page.description = string.concat("THROWAWAY TEST of the strategy launchpad against ", k.sym, ". Not the production token. Do not buy.");
        uint256 id = f.launchWithMetadata(q, terms, page);
        (address token, address treasury, address hook,,) = f.strategies(id);
        console2.log(string.concat("--- ", q.symbol, " id"), id);
        console2.log("    token", token); console2.log("    treasury", treasury); console2.log("    hook", hook);
    }

    // ------------------------------------------------------------------------------------------------ 1b. seed
    /// @notice ONE WAY. Per strategy: `stockUsdgEach` of USDG (1e6 = 1 USDG) buys the stock into the treasury as its first
    ///         lot, and `reserveUsdgEach` of USDG follows as the dip reserve. Needs 5 x (stockUsdgEach + reserveUsdgEach).
    function seed(uint256 stockUsdgEach, uint256 reserveUsdgEach) external {
        HedgeFunFactory f = HedgeFunFactory(vm.envAddress("FACTORY")); Pick[5] memory picks = _picks(); uint256 n = f.strategyCount();
        vm.startBroadcast();
        TestStockBuyer buyer = new TestStockBuyer(USDG);
        IERC20(USDG).approve(address(buyer), stockUsdgEach * n);
        for (uint256 id; id < n; id++) _seedOne(f, buyer, picks, id, stockUsdgEach, reserveUsdgEach);
        vm.stopBroadcast();
    }

    function _seedOne(HedgeFunFactory f, TestStockBuyer buyer, Pick[5] memory picks, uint256 id, uint256 stockUsdg, uint256 reserveUsdg) internal {
        (, address tr,, address stock,) = f.strategies(id);
        address pool; for (uint256 j; j < picks.length; j++) if (picks[j].stock == stock) pool = picks[j].pool;
        uint256 got;
        if (stockUsdg != 0) {
            uint256 spot = HedgeFunTreasury(tr).spotPrice();                      // USDG per whole stock, 1e18
            got = buyer.buy(pool, stockUsdg, stockUsdg * 1e30 / spot * 97 / 100, tr);                  // at worst 3% under the pool's own spot
        }
        if (reserveUsdg != 0) IERC20(USDG).transfer(tr, reserveUsdg);
        bool booked = HedgeFunTreasury(tr).book();                                // false over a closure: it waits for the open
        console2.log("id / stock into the treasury (1e18) / booked now:", id, got, booked);
    }

    // ------------------------------------------------------------------------------------------------ 2. trade
    /// @notice buy each token with `usdgEach` (1e6 = 1 USDG) and sell half of what arrives. Needs 5 x usdgEach USDG.
    function trade(uint256 usdgEach) external {
        HedgeFunFactory f = HedgeFunFactory(vm.envAddress("FACTORY")); HedgeFunTradeRouter r = HedgeFunTradeRouter(vm.envAddress("ROUTER"));
        Pick[5] memory picks = _picks(); uint256 n = f.strategyCount();
        vm.startBroadcast();
        IERC20(USDG).approve(address(r), usdgEach * n);
        for (uint256 id; id < n; id++) {
            (address token,,, address stock,) = f.strategies(id);
            address pool; for (uint256 j; j < picks.length; j++) if (picks[j].stock == stock) pool = picks[j].pool;
            uint256 got = r.buy(id, pool, usdgEach, 1, block.timestamp + 600);
            IERC20(token).approve(address(r), got / 2);
            uint256 back = r.sell(id, pool, got / 2, 1, block.timestamp + 600);
            console2.log("id / tokens bought (1e18) / USDG back for half (1e6):", id, got / 1e18, back);
        }
        vm.stopBroadcast();
    }

    // ------------------------------------------------------------------------------------------------ 3. keep
    /// @notice the keeper. Each action is tried in simulation first (a snapshot, reverted) and broadcast only if it
    ///         would go through, so a run with nothing due sends nothing and costs nothing.
    function keep() external {
        HedgeFunFactory f = HedgeFunFactory(vm.envAddress("FACTORY")); uint256 n = f.strategyCount(); uint256 sent;
        for (uint256 id; id < n; id++) {
            (, address tr, address hk,,) = f.strategies(id);
            sent += _try(hk, abi.encodeWithSignature("sweep(bytes32)", PoolId.unwrap(HedgeFunHook(hk).poolOfTreasury(tr))), "sweep", id);
            sent += _tryBook(tr, id);
            uint256 lots = HedgeFunTreasury(tr).lotCount();
            for (uint256 i = lots; i > 0; i--) {                                   // high to low: a sold-out lot is swapped out
                sent += _try(tr, abi.encodeWithSignature("takeProfit(uint256)", i - 1), "takeProfit", id);
                sent += _try(tr, abi.encodeWithSignature("stopLoss(uint256)", i - 1), "stopLoss", id);
            }
            sent += _try(tr, abi.encodeWithSignature("buyDip()"), "buyDip", id);
            sent += _try(tr, abi.encodeWithSignature("buyback()"), "buyback", id);
        }
        console2.log("actions sent this run:", sent);
    }

    function _would(address to, bytes memory data) internal returns (bool ok, bytes memory ret) {
        uint256 snap = vm.snapshotState();
        (ok, ret) = to.call(data);
        vm.revertToState(snap);
    }

    function _try(address to, bytes memory data, string memory what, uint256 id) internal returns (uint256) {
        (bool ok,) = _would(to, data);
        if (!ok) return 0;
        vm.broadcast(); (bool sentOk,) = to.call(data); sentOk;
        console2.log(what, "-> strategy", id);
        return 1;
    }

    /// @dev `book()` does not revert when there is nothing to book, it returns false: only send a true one
    function _tryBook(address tr, uint256 id) internal returns (uint256) {
        (bool ok, bytes memory ret) = _would(tr, abi.encodeWithSignature("book()"));
        if (!ok || ret.length < 32 || !abi.decode(ret, (bool))) return 0;
        vm.broadcast(); HedgeFunTreasury(tr).book();
        console2.log("book -> strategy", id);
        return 1;
    }
}
