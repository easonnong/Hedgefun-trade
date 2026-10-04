// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {TradingCalendar} from "../src/TradingCalendar.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {HedgeFunFactory, TreasuryDeployer, TokenDeployer} from "../src/HedgeFunFactory.sol";
import {HedgeFunToken} from "../src/HedgeFunToken.sol";
import {HedgeFunTreasury} from "../src/HedgeFunTreasury.sol";
import {HedgeFunHook} from "../src/hooks/HedgeFunHook.sol";
import {HedgeFunTradeRouter} from "../src/HedgeFunTradeRouter.sol";
import {SandboxStock, SandboxQuote, SandboxFeed} from "./sandbox/SandboxAssets.sol";
import {SandboxLp, IV3Factory, IV3Pool} from "./sandbox/SandboxLp.sol";
import {SandboxLaunchBundle} from "./sandbox/SandboxLaunchBundle.sol";

/// Versioned wiring. Old real-USDG sandboxes cannot be operated through this script.
contract SandboxBook is Ownable2Step {
    address public stock; address public quote; address public feed; address public quoteFeed;
    address public pool; address public lp; address public oracle; address public calendar;
    address public factory; address public router; address public token; address public treasury;
    address public hook; uint256 public id; uint256 public stagedAt;
    bool public stockIsToken0;

    constructor(address initialOwner) Ownable(initialOwner) {}
    function version() external pure returns (uint256) { return 2; }
    function write(address stock_, address quote_, address pool_, address lp_, address oracle_, address calendar_) external onlyOwner {
        require(stock == address(0) && stock_ != address(0) && quote_ != address(0), "once");
        stock = stock_; quote = quote_; pool = pool_; lp = lp_; oracle = oracle_; calendar = calendar_;
        feed = address(SandboxLp(lp_).feed()); quoteFeed = address(SandboxLp(lp_).quoteFeed());
        stockIsToken0 = stock_ < quote_; stagedAt = block.timestamp;
    }
    function writeLaunch(address factory_, address router_, uint256 id_, address token_, address treasury_, address hook_) external onlyOwner {
        require(factory == address(0) && factory_ != address(0), "once");
        factory = factory_; router = router_; id = id_; token = token_; treasury = treasury_; hook = hook_;
    }
}

/// Rehearse the real V3/V4 protocol using TWO owner-minted, worthless assets. Only native gas costs money.
/// No real USDG transfer, approval, feed or pool is used. Never deposit real funds in these contracts.
/// Treasury deposits and the strategy token's V4 liquidity retain the production protocol's irreversibility.
///
/// Run with --tc Sandbox (the file also declares SandboxBook). Commands without --broadcast only simulate.
/// stage(10000000): 10 TEST dollars, 80% in the pool and 20% idle. Wait 601 seconds before launch().
/// price(priceE18,maxInput): maxInput uses the input token's decimals (quote=6, stock=18).
/// trade(quoteIn,minTokensOut,minQuoteOut): explicit independently chosen bounds for the buy and half-sale.
/// exit(min0,min1): burn the V3 position, collect principal/fees, sweep idle test assets to the operator.
contract Sandbox is Script {
    address constant PM = 0x8366a39CC670B4001A1121B8F6A443A643e40951;
    address constant V3_FACTORY = 0x1f7d7550B1b028f7571E69A784071F0205FD2EfA;
    address constant REAL_USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    uint24 constant FEE = 3000;
    int24 constant SPACING = 60;
    uint256 constant SCALE = 1e30;
    uint256 constant P0 = 100e18;
    uint256 constant Q96 = 1 << 96;
    string constant STOCK_NAME = "Sandbox Stock - NO VALUE";
    string constant STOCK_SYMBOL = "SBXSTK";

    function _sqrtFor(uint256 p) internal pure returns (uint160) {
        require(p >= 25e18 && p <= 400e18, "sandbox price range");
        return uint160(Math.sqrt(Math.mulDiv(SCALE, 1 << 192, p)));
    }
    function _align(int24 tick) internal pure returns (int24) {
        int24 aligned = tick / SPACING * SPACING;
        return tick < 0 && tick % SPACING != 0 ? aligned - SPACING : aligned;
    }
    function _bookLabel() internal pure virtual returns (string memory) { return "SANDBOX="; }
    function _bookAddress() internal view virtual returns (address) { return vm.envAddress("SANDBOX"); }
    function _book() internal view returns (SandboxBook bk) {
        bk = SandboxBook(_bookAddress());
        require(address(bk).codehash == keccak256(type(SandboxBook).runtimeCode), "unsupported sandbox; redeploy v2");
        require(bk.version() == 2 && bk.quote() != address(0) && bk.quote() != REAL_USDG, "test quote only");
        require(bk.quote().codehash == keccak256(type(SandboxQuote).runtimeCode), "test quote bytecode");
        require(bk.stock().codehash == keccak256(type(SandboxStock).runtimeCode), "test stock bytecode");
        SandboxLp lp = SandboxLp(bk.lp());
        require(lp.quote() == bk.quote() && lp.stock() == bk.stock() && address(lp.pool()) == bk.pool(), "wiring");
        require(lp.owner() == bk.owner() && SandboxQuote(bk.quote()).owner() == bk.owner()
            && SandboxStock(bk.stock()).owner() == bk.owner(), "owners");
        require(address(lp.feed()) == bk.feed() && address(lp.quoteFeed()) == bk.quoteFeed()
            && lp.feed().owner() == address(lp) && lp.quoteFeed().owner() == address(lp), "feeds");
    }
    function _begin() internal returns (SandboxBook bk) {
        bk = _book();
        vm.startBroadcast();
        (, address me,) = vm.readCallers();
        require(bk.owner() == me, "sandbox owner");
    }
    function _mineHook(address deployer) internal view returns (bytes32 salt, address at) {
        bytes32 h = keccak256(abi.encodePacked(type(HedgeFunHook).creationCode, abi.encode(PM)));
        for (uint256 i; i < 5_000_000; i++) {
            at = vm.computeCreate2Address(bytes32(i), h, deployer);
            if (uint160(at) & 0x3FFF == 0x2844 && at.code.length == 0) return (bytes32(i), at);
        }
        revert("no hook salt");
    }
    function _mineStock(address initialOwner, address quote) internal view returns (bytes32 salt, address at) {
        bytes32 h = keccak256(abi.encodePacked(type(SandboxStock).creationCode, abi.encode(STOCK_NAME, STOCK_SYMBOL, initialOwner)));
        for (uint256 i; i < 100_000; i++) {
            at = vm.computeCreate2Address(bytes32(i), h, CREATE2_FACTORY);
            if (at > quote && at.code.length == 0) return (bytes32(i), at);
        }
        revert("no stock salt");
    }

    function _defaults() internal pure returns (HedgeFunFactory.Defaults memory d) {
        d.supply = 1_000_000_000e18; d.tickSpacing = 60; d.minTaxBps = 100; d.maxTaxBps = 1500; d.protocolBps = 2000; d.maxCreatorBps = 3000;
        d.spikeBps = 9000; d.spikeSeconds = 120; d.sweepTipBps = 50; d.bountyBps = 50; d.maxSlippageBps = 100; d.maxDeviationBps = 50;
        d.maxBuybackImpactBps = 300; d.buybackCooldown = 60; d.snipeBps = 9900; d.snipeSeconds = 3;
        d.sellChunkUsdg = 2_000e6;
        d.minLotUsdg = 2e5;                                                      // 0.20 USDG: pocket money makes lots
        d.buybackChunkUsdg = 50e6;
        d.launchFeeCurrency = HedgeFunFactory.FeeCurrency.None;
    }

    function stage(uint256 poolQuote) external returns (SandboxBook bk) {
        require(poolQuote >= 1e6 && poolQuote <= 1_000_000e6, "test budget 1..1000000");
        vm.startBroadcast();
        (, address me,) = vm.readCallers();
        bk = new SandboxBook(me);
        SandboxQuote quote = new SandboxQuote(me);
        (bytes32 salt, address stockAt) = _mineStock(me, address(quote));
        SandboxStock stock = new SandboxStock{salt: salt}(STOCK_NAME, STOCK_SYMBOL, me);
        require(address(stock) == stockAt && stock.owner() == me, "stock ownership/address");
        SandboxLp lp = _stagePool(address(stock), address(quote), poolQuote, me);
        TradingCalendar cal = new TradingCalendar(me);
        PriceOracle oracle = new PriceOracle(address(stock), address(lp.feed()), address(lp.quoteFeed()), address(cal), 26 hours, 26 hours);
        bk.write(address(stock), address(quote), address(lp.pool()), address(lp), address(oracle), address(cal));
        vm.stopBroadcast();
        console2.log(_bookLabel(), address(bk));
        console2.log("stock (NO VALUE):", address(stock));
        console2.log("test dollar (NOT USDG):", address(quote));
        console2.log("pool:", address(lp.pool()));
        console2.log("Wait 601 seconds, then launch(). Only test assets are used; native gas is real.");
    }

    function _stagePool(address stock, address quote, uint256 budget, address me) internal returns (SandboxLp lp) {
        address pool = IV3Factory(V3_FACTORY).createPool(quote, stock, FEE);
        uint160 sqrtP = _sqrtFor(P0);
        IV3Pool(pool).initialize(sqrtP);
        IV3Pool(pool).increaseObservationCardinalityNext(700);
        int24 lo = _align(TickMath.getTickAtSqrtPrice(_sqrtFor(P0 * 4)));
        int24 hi = _align(TickMath.getTickAtSqrtPrice(_sqrtFor(P0 / 4)));
        uint160 sqrtA = TickMath.getSqrtPriceAtTick(lo);
        uint160 sqrtB = TickMath.getSqrtPriceAtTick(hi);
        uint128 liquidity = SafeCast.toUint128(Math.mulDiv(Math.mulDiv(budget * 4 / 5, sqrtP, Q96), sqrtB, sqrtB - sqrtP));
        uint256 stockNeeded = Math.mulDiv(liquidity, sqrtP - sqrtA, Q96);
        lp = new SandboxLp(me, V3_FACTORY, quote, stock, lo, hi);
        SandboxQuote(quote).mint(address(lp), budget);
        SandboxStock(stock).mint(address(lp), stockNeeded * 4 + 1e18);
        // If someone initialized/moved the public pool between setup transactions, stop before depositing.
        (uint160 actual,,,,,,) = IV3Pool(pool).slot0();
        require(actual == sqrtP, "pool moved during setup");
        lp.addLiquidity(liquidity, budget * 4 / 5 + 1, stockNeeded + 1, block.timestamp + 600);
    }

    function launch() external {
        SandboxBook bk = _begin();
        require(bk.factory() == address(0), "already launched");
        require(block.timestamp >= bk.stagedAt() + 601, "wait 601 seconds");
        (, address me,) = vm.readCallers();
        SandboxLp lp = SandboxLp(bk.lp());
        lp.setPrice(P0 * 1002 / 1000, IERC20(bk.quote()).balanceOf(address(lp)), block.timestamp + 600);
        (,,, uint16 card,,,) = IV3Pool(bk.pool()).slot0();
        require(card >= 660, "observation ring");
        HedgeFunFactory f = _launchFactory(me, bk.quote());
        f.list(bk.stock(), bk.oracle(), bk.pool(), 5e10, true);
        f.setBandCeiling(bk.stock(), 10);
        uint256 id = _launchOne(f, bk.stock(), me);
        (address token, address treasury, address hook,,) = f.strategies(id);
        bk.writeLaunch(address(f), address(new HedgeFunTradeRouter(f)), id, token, treasury, hook);
        vm.stopBroadcast();
        console2.log("factory:", address(f)); console2.log("token:", token); console2.log("treasury:", treasury);
    }

    function _launchFactory(address me, address quote) internal returns (HedgeFunFactory f) {
        SandboxLaunchBundle bundle = new SandboxLaunchBundle(me);
        (bytes32 salt, address hookAt) = _mineHook(address(bundle));
        bytes memory factoryCode = abi.encodePacked(type(HedgeFunFactory).creationCode, abi.encode(
            me, PM, V3_FACTORY, quote, me, vm.computeCreateAddress(address(bundle), 2),
            vm.computeCreateAddress(address(bundle), 3), hookAt, _defaults()
        ));
        (address hook, address deployed) = bundle.deploy(salt,
            abi.encodePacked(type(HedgeFunHook).creationCode, abi.encode(PM)),
            type(TreasuryDeployer).creationCode, type(TokenDeployer).creationCode, factoryCode);
        require(hook == hookAt, "hook address");
        f = HedgeFunFactory(deployed);
    }

    function _launchOne(HedgeFunFactory f, address stock, address me) internal returns (uint256) {
        HedgeFunFactory.Request memory q;
        q.name = "SANDBOX Strategy - NO VALUE"; q.symbol = "SBXSTR"; q.stock = stock; q.creator = me;
        q.taxBps = 1000; q.creatorBps = 1000; q.tp1Bps = 1000; q.tp2Bps = 2000; q.dipBps = 500; q.stopBps = 0; q.lotBps = 5000;
        q.bandBpsPerHour = 10; q.expectedOpenPriceE18 = 5e10;
        (,, bytes32 terms) = f.predict(q);
        HedgeFunToken.Info memory page;
        page.description = "TEST ONLY. Both stock and settlement dollar are owner-minted and have NO VALUE. Do not buy or deposit real assets.";
        return f.launchWithMetadata(q, terms, page);
    }

    function price(uint256 newP, uint256 maxInput) external {
        SandboxBook bk = _begin();
        SandboxLp(bk.lp()).setPrice(newP, maxInput, block.timestamp + 600);
        vm.stopBroadcast();
        console2.log("test stock price x1e4:", newP / 1e14);
    }
    function repeg() external {
        SandboxBook bk = _begin();
        SandboxLp(bk.lp()).repeg();
        vm.stopBroadcast();
    }
    function pause(bool on) external {
        SandboxBook bk = _begin();
        SandboxStock(bk.stock()).setOraclePaused(on);
        vm.stopBroadcast();
    }
    function multiplier(uint256 value) external {
        SandboxBook bk = _begin();
        SandboxStock(bk.stock()).setUiMultiplier(value);
        vm.stopBroadcast();
    }

    /// Two separately bounded trades; a failed half-sale can leave the bought strategy tokens with the operator.
    function trade(uint256 quoteIn, uint256 minTokensOut, uint256 minQuoteOut) external {
        require(quoteIn != 0 && minTokensOut != 0 && minQuoteOut != 0, "explicit trade bounds");
        SandboxBook bk = _begin();
        require(bk.factory() != address(0), "launch first");
        (, address me,) = vm.readCallers();
        HedgeFunTradeRouter router = HedgeFunTradeRouter(bk.router());
        SandboxQuote(bk.quote()).mint(me, quoteIn);
        require(IERC20(bk.quote()).approve(address(router), quoteIn), "approve quote");
        uint256 got = router.buy(bk.id(), bk.pool(), quoteIn, minTokensOut, block.timestamp + 600);
        require(IERC20(bk.token()).approve(address(router), got / 2), "approve token");
        uint256 back = router.sell(bk.id(), bk.pool(), got / 2, minQuoteOut, block.timestamp + 600);
        vm.stopBroadcast();
        console2.log("test tokens bought / test dollars returned:", got, back);
    }

    /// Test assets gifted to the immutable treasury are intentionally not withdrawable.
    function seed(uint256 stockQuote, uint256 reserveQuote) external {
        SandboxBook bk = _begin();
        require(bk.treasury() != address(0), "launch first");
        (bool ok, uint256 p) = HedgeFunTreasury(bk.treasury()).health();
        require(ok, "unhealthy: settle pool/feed before seed");
        if (stockQuote != 0) SandboxStock(bk.stock()).mint(bk.treasury(), Math.mulDiv(stockQuote, SCALE, p));
        if (reserveQuote != 0) SandboxQuote(bk.quote()).mint(bk.treasury(), reserveQuote);
        bool booked = HedgeFunTreasury(bk.treasury()).book();
        vm.stopBroadcast();
        console2.log("test seed booked:", booked);
    }

    function exit(uint256 min0, uint256 min1) external {
        SandboxBook bk = _begin();
        (, address me,) = vm.readCallers();
        SandboxLp lp = SandboxLp(bk.lp());
        uint128 amount = lp.positionLiquidity();
        if (amount != 0) lp.removeLiquidity(amount, min0, min1, me, block.timestamp + 600);
        else lp.collectFees(me);
        lp.sweep(bk.quote(), me);
        lp.sweep(bk.stock(), me);
        vm.stopBroadcast();
    }

    function status() external view {
        SandboxBook bk = _book();
        SandboxLp lp = SandboxLp(bk.lp());
        (uint160 sqrtP,,,,,,) = IV3Pool(bk.pool()).slot0();
        console2.log("TEST DOLLAR (NOT USDG):", bk.quote());
        console2.log("pool spot x1e4:", lp.priceAt(sqrtP) / 1e14);
        console2.log("active / owned liquidity:", IV3Pool(bk.pool()).liquidity(), lp.positionLiquidity());
        console2.log("idle test dollars (1e6):", IERC20(bk.quote()).balanceOf(address(lp)));
        if (bk.treasury() == address(0)) return;
        HedgeFunTreasury t = HedgeFunTreasury(bk.treasury());
        (bool ok, uint256 p) = t.health();
        console2.log("rule can price / price x1e4:", ok, p / 1e14);
        console2.log("lots / booked stock:", t.lotCount(), t.bookedStock());
        console2.log("test dollar reserve (1e6):", t.reserveUsdg());
        console2.log("dip reference x1e4:", t.lastSalePrice() / 1e14);
    }
}
