// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {VmSafe} from "forge-std/Vm.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {HedgeFunFactory} from "../../src/HedgeFunFactory.sol";
import {HedgeFunV2Factory} from "../../src/v2/HedgeFunV2Factory.sol";
import {V2TreasuryDeployer} from "../../src/v2/V2TreasuryDeployer.sol";
import {PriceOracle} from "../../src/PriceOracle.sol";
import {IUniswapV3Pool} from "../../src/interfaces/IUniswapV3.sol";
import {MAX_SLIPPAGE_BPS} from "../../src/libraries/HedgeFunLimits.sol";
import {V2MainnetDefaults} from "./V2MainnetDefaults.sol";

/// @notice What the mainnet listing scripts share: the plan file, the opening-price rule and the checks a row
///         must pass before it is sent or believed. Chain 4663 only.
/// @dev The plan file (`deploy/mainnet-v2-listings.json`) names, per stock, the token, the `PriceOracle`, the
///      stock/USDG V3 pool with its fee tier and the three listing gates. It never holds an opening price: that is
///      computed from the oracle's live `tryPrice()` when the plan is made (docs/V2_RELEASE_RUNBOOK.md, section C).
///      Its `candidates` list is read by nobody here.
abstract contract V2MainnetListingPlan is Script {
    uint256 public constant CHAIN_ID = 4663;
    address public constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    /// Every listed oracle must price against this dollar feed and follow this calendar: the eighteen V1 oracles
    /// and the five of 2026-10-05 all do (deploy/mainnet-v2-oracles.json). A mis-pasted oracle fails here.
    address public constant USDG_FEED = 0x61B7e5650328764B076A108EFF5fa7282a1B9aD2;
    address public constant CALENDAR = 0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5;
    string public constant PLAN = "deploy/mainnet-v2-listings.json";

    /// The release's opening rule, as `DeployV2Testnet.referenceOpenPriceE18` and `CalibrateV2Listings`: a
    /// graduation near a $50,000 FDV when the curve deployer's fixed 79.31% has been sold.
    uint256 public constant TARGET_GRADUATION_FDV_USD_E18 = 50_000e18;
    uint16 public constant REFERENCE_SALE_BPS = V2MainnetDefaults.SALE_BPS;
    uint16 public constant LP_BPS = V2MainnetDefaults.LP_BPS;
    uint256 internal constant SUPPLY_TOKENS = 1_000_000_000;

    /// one stock of the plan file, as written there
    struct Entry {
        string symbol;
        address stock;
        address oracle;
        address pool;
        uint24 fee;
        uint16 maxDeviationBps;
        uint16 maxSlippageBps;
        uint64 sellChunkUsdg;
    }

    error WrongChain(uint256 chainId);
    error WrongPlan(string what);
    error BadEntry(string symbol, string what);
    error SaleShareNotTheReference(uint16 actual);
    error LpDefaultNotTheReference(uint16 actual);
    error FactoryMismatch(string what);

    /// @notice 18-decimal stock units per token, scaled by 1e18, from the stock's price in USDG per share (1e18):
    ///         `DeployV2Testnet.referenceOpenPriceE18`, which `test/ListV2MainnetStocks.t.sol` holds equal.
    function referenceOpenPriceE18(uint256 stockUsdE18) public pure returns (uint256) {
        return Math.mulDiv(openingFdvUsdE18(), 1e18, stockUsdE18 * SUPPLY_TOKENS);
    }

    /// @notice The opening FDV the rule aims at, USD (1e18): $2,140.3805, the graduation FDV scaled by the square
    ///         of the unsold share, since graduation preserves the supply and the price grows as the sale proceeds.
    function openingFdvUsdE18() public pure returns (uint256) {
        uint256 remaining = 10_000 - REFERENCE_SALE_BPS;
        return Math.mulDiv(TARGET_GRADUATION_FDV_USD_E18, remaining * remaining, 10_000 * 10_000);
    }

    /// @notice The opening FDV in USD (1e18) a listing's `openPriceE18` implies at `stockUsdE18`: the rule above,
    ///         inverted, for the plan's printout.
    function impliedOpeningFdvUsdE18(uint256 openPriceE18, uint256 stockUsdE18) public pure returns (uint256) {
        return Math.mulDiv(openPriceE18 * SUPPLY_TOKENS, stockUsdE18, 1e18);
    }

    /// @notice The plan file's `stocks`, in the file's order, with every value range-checked. `candidates` are not read.
    function parsePlan(string memory json) public view returns (Entry[] memory entries) {
        if (vm.parseJsonUint(json, ".chainId") != CHAIN_ID) revert WrongPlan("chainId");
        if (vm.parseJsonAddress(json, ".usdg") != USDG) revert WrongPlan("usdg");
        if (vm.parseJsonAddress(json, ".oracleBindings.usdgFeed") != USDG_FEED) revert WrongPlan("usdgFeed");
        if (vm.parseJsonAddress(json, ".oracleBindings.calendar") != CALENDAR) revert WrongPlan("calendar");
        uint256 n;
        while (vm.keyExistsJson(json, _at(n))) ++n;
        if (n == 0) revert WrongPlan("no stocks");
        entries = new Entry[](n);
        for (uint256 i; i < n; ++i) {
            string memory p = _at(i);
            Entry memory e;
            e.symbol = vm.parseJsonString(json, string.concat(p, ".symbol"));
            e.stock = vm.parseJsonAddress(json, string.concat(p, ".token"));
            e.oracle = vm.parseJsonAddress(json, string.concat(p, ".oracle"));
            e.pool = vm.parseJsonAddress(json, string.concat(p, ".pool"));
            uint256 fee = vm.parseJsonUint(json, string.concat(p, ".fee"));
            uint256 dev = vm.parseJsonUint(json, string.concat(p, ".maxDeviationBps"));
            uint256 slip = vm.parseJsonUint(json, string.concat(p, ".maxSlippageBps"));
            uint256 chunk = vm.parseJsonUint(json, string.concat(p, ".sellChunkUsdg"));
            if (bytes(e.symbol).length == 0) revert BadEntry(e.symbol, "symbol");
            if (fee == 0 || fee > type(uint24).max) revert BadEntry(e.symbol, "fee");
            if (dev > type(uint16).max || slip > type(uint16).max) revert BadEntry(e.symbol, "gates");
            if (chunk > type(uint64).max) revert BadEntry(e.symbol, "sellChunkUsdg");
            (e.fee, e.maxDeviationBps, e.maxSlippageBps, e.sellChunkUsdg) =
                (uint24(fee), uint16(dev), uint16(slip), uint64(chunk));
            entries[i] = e;
        }
    }

    function _at(uint256 i) private pure returns (string memory) {
        return string.concat(".stocks[", vm.toString(i), "]");
    }

    /// @dev The factory the plan is for: a V2 core on this chain whose curve deployer sells the reference share
    ///      and whose registry splits a raise seventy to thirty by default. The opening rule holds for no other.
    function _checkFactory(HedgeFunV2Factory factory) internal view returns (HedgeFunFactory.Defaults memory d) {
        if (block.chainid != CHAIN_ID) revert WrongChain(block.chainid);
        if (address(factory).code.length == 0 || address(factory.curveDeployer()).code.length == 0) {
            revert FactoryMismatch("V2 factory required");
        }
        uint16 sale = factory.curveDeployer().DEFAULT_SALE_BPS();
        if (sale != REFERENCE_SALE_BPS) revert SaleShareNotTheReference(sale);
        V2TreasuryDeployer registry = V2TreasuryDeployer(address(factory.treasuryDeployer()));
        uint16 lp = registry.DEFAULT_LP_BPS();
        if (lp != LP_BPS) revert LpDefaultNotTheReference(lp);
        if (registry.factory() != address(factory)) revert FactoryMismatch("registry");
        if (factory.usdg() != USDG) revert FactoryMismatch("usdg");
        d = factory.getDefaults();
        if (d.supply != SUPPLY_TOKENS * 1e18) revert FactoryMismatch("supply");
    }

    /// @dev What the factory's own `list` and `setListingGates` would refuse, and what they would accept but the
    ///      plan must not: a pool that is not the V3 factory's for (USDG, stock, fee), an oracle for another stock
    ///      or against another dollar feed or calendar, gates the treasury could not use, a stock named twice.
    function _checkEntry(HedgeFunV2Factory factory, HedgeFunFactory.Defaults memory d, Entry[] memory all, uint256 i)
        internal
        view
    {
        Entry memory e = all[i];
        for (uint256 j; j < i; ++j) {
            if (
                all[j].stock == e.stock || all[j].pool == e.pool || all[j].oracle == e.oracle
                    || keccak256(bytes(all[j].symbol)) == keccak256(bytes(e.symbol))
            ) revert BadEntry(e.symbol, "duplicate");
        }
        if (e.stock.code.length == 0 || IERC20Metadata(e.stock).decimals() != 18) revert BadEntry(e.symbol, "18-decimal stock");
        if (e.oracle.code.length == 0 || PriceOracle(e.oracle).stock() != e.stock) revert BadEntry(e.symbol, "oracle.stock");
        if (address(PriceOracle(e.oracle).usdgFeed()) != USDG_FEED) revert BadEntry(e.symbol, "oracle.usdgFeed");
        if (address(PriceOracle(e.oracle).calendar()) != CALENDAR) revert BadEntry(e.symbol, "oracle.calendar");
        if (e.pool.code.length == 0 || IUniswapV3Pool(e.pool).fee() != e.fee) revert BadEntry(e.symbol, "pool.fee");
        if (factory.v3Factory().getPool(USDG, e.stock, e.fee) != e.pool) revert BadEntry(e.symbol, "not the V3 factory's pool");
        if (e.maxDeviationBps == 0 || e.maxDeviationBps >= e.maxSlippageBps || e.maxSlippageBps > MAX_SLIPPAGE_BPS) {
            revert BadEntry(e.symbol, "gates");
        }
        if (e.sellChunkUsdg == 0 || e.sellChunkUsdg < d.minLotUsdg) revert BadEntry(e.symbol, "sellChunkUsdg");
    }

    /// @dev The gates a treasury launched on `stock` would get: `HedgeFunFactory._gates`, the pair falling back as
    ///      a pair on a zero slippage, the chunk on its own.
    function _effectiveGates(HedgeFunV2Factory factory, HedgeFunFactory.Defaults memory d, address stock)
        internal
        view
        returns (uint16 dev, uint16 slip, uint256 chunk)
    {
        uint64 stored;
        (dev, slip, stored) = factory.listingGates(stock);
        if (slip == 0) (dev, slip) = (d.maxDeviationBps, d.maxSlippageBps);
        chunk = stored == 0 ? d.sellChunkUsdg : stored;
    }

    function _symbolsOf(Entry[] memory entries) internal pure returns (string[] memory s) {
        s = new string[](entries.length);
        for (uint256 i; i < entries.length; ++i) s[i] = entries[i].symbol;
    }
}

/// @notice List the stocks of `deploy/mainnet-v2-listings.json` on the V2 mainnet factory, as its owner, each at
///         the opening price the release rule gives for the oracle's price at that moment, and set the gates
///         where the plan's differ from what the factory would apply.
/// @dev `plan()` is read-only: it prices every stock off its oracle's live `tryPrice()`, prints the rows and the
///      `EXPECTED_PLAN_HASH` that `run()` must be given. The hash covers the chain, the factory and every row,
///      the price each opening price was computed from included: a feed that printed again, a listing changed or
///      a plan file edited after the review stops `run()` with `PlanChanged`. A stock whose oracle is not healthy
///      (market closed, feed stale, stock paused) is reported and left out of the plan, never listed on an old
///      print; when nothing is healthy there is nothing to list and `run()` refuses.
///
///      `run()` recomputes the plan, refuses any other hash, then sends as the owner `factory.list(stock, oracle,
///      pool, openPriceE18, true)` for every row whose listing is not already exactly that, and
///      `setListingGates(stock, maxDeviationBps, maxSlippageBps, sellChunkUsdg)` for every row whose effective
///      gates (the listing's, or the factory defaults it falls back to) differ from the plan's. It reads everything
///      back and writes `deploy/mainnet-v2-listings.candidate.json`: the rows, the block and the price each opening
///      price came from. That file is unverified by construction; `VerifyV2MainnetListings` reads the confirmed
///      chain. The broadcast is up to two owner transactions per stock with fixed arguments, so never run this
///      alongside another owner operation, and run `plan()` again afterwards: every row must show nothing to send.
///
///      It refuses a factory whose `curveDeployer().DEFAULT_SALE_BPS()` is not 7931 or whose
///      `treasuryDeployer().DEFAULT_LP_BPS()` is not 7000, since the opening rule assumes both, and any chain but
///      4663. Requires V2_FACTORY; `run()` also OPERATOR (the owner, and the broadcaster) and EXPECTED_PLAN_HASH.
///      The LP share is not touched: the registry's 70% default applies, `setLpBps` only to deviate. The listing
///      check (`tools/v2_launch_check.py --factory`) is a separate step, before `plan()` and again before a
///      first launch.
contract ListV2MainnetStocks is V2MainnetListingPlan {
    string internal constant OUT = "deploy/mainnet-v2-listings.candidate.json";
    string internal constant OUT_DRY = "deploy/mainnet-v2-listings.dryrun.json";

    /// one stock as `run()` will send it
    struct Row {
        Entry e;
        uint256 priceE18;         // the oracle's live price the opening price was computed from
        uint256 openPriceE18;     // referenceOpenPriceE18(priceE18)
        uint256 oldOpenPriceE18;  // the factory's today, 0 when unlisted
        bool list;                // the listing is not already (oracle, pool, openPriceE18, enabled)
        bool setGates;            // the effective gates are not the plan's
    }

    error NotFactoryOwner(address sender);
    error PlanChanged(bytes32 actual);
    error NothingToList();
    error ReadbackFailed(string symbol, string what);

    function run() external returns (Row[] memory rows) {
        HedgeFunV2Factory factory = HedgeFunV2Factory(vm.envAddress("V2_FACTORY"));
        address operator = vm.envAddress("OPERATOR");
        if (operator == address(0) || msg.sender != operator || factory.owner() != operator) revert NotFactoryOwner(msg.sender);
        Entry[] memory entries = parsePlan(vm.readFile(PLAN));
        string[] memory skipped;
        (rows, skipped) = planFor(factory, entries);
        bytes32 h = planHash(factory, rows);
        if (h != vm.envBytes32("EXPECTED_PLAN_HASH")) revert PlanChanged(h);
        if (rows.length == 0) revert NothingToList();
        uint256 startBlock = block.number;
        execute(factory, operator, rows);
        bool requested =
            vm.isContext(VmSafe.ForgeContext.ScriptBroadcast) || vm.isContext(VmSafe.ForgeContext.ScriptResume);
        _writeCandidate(factory, operator, rows, skipped, h, startBlock, requested);
        console2.log("listed", rows.length, "stocks on", address(factory));
        console2.log("simulation readback passed; after the broadcast run plan() again and VerifyV2MainnetListings");
    }

    /// @notice Read-only: the rows `run()` would send and the hash it must be given.
    function plan() external view returns (Row[] memory rows) {
        HedgeFunV2Factory factory = HedgeFunV2Factory(vm.envAddress("V2_FACTORY"));
        Entry[] memory entries = parsePlan(vm.readFile(PLAN));
        string[] memory skipped;
        (rows, skipped) = planFor(factory, entries);
        HedgeFunFactory.Defaults memory d = factory.getDefaults();
        uint256 remaining = 10_000 - REFERENCE_SALE_BPS;
        for (uint256 i; i < rows.length; ++i) {
            Row memory r = rows[i];
            uint256 openingFdv = impliedOpeningFdvUsdE18(r.openPriceE18, r.priceE18);
            console2.log("stock", r.e.symbol, r.e.stock);
            console2.log("  oracle", r.e.oracle);
            console2.log("  pool, fee", r.e.pool, r.e.fee);
            console2.log("  oracle price, USDG e18", r.priceE18);
            console2.log("  openPriceE18 now, new", r.oldOpenPriceE18, r.openPriceE18);
            console2.log(
                "  implied opening FDV, raise and graduation FDV, USD",
                openingFdv / 1e18,
                openingFdv * REFERENCE_SALE_BPS / remaining / 1e18,
                openingFdv * 10_000 * 10_000 / (remaining * remaining) / 1e18
            );
            (uint16 dev, uint16 slip, uint256 chunk) = _effectiveGates(factory, d, r.e.stock);
            console2.log("  gates now: deviation, slippage, chunk", dev, slip, chunk);
            console2.log("  gates plan: deviation, slippage, chunk", r.e.maxDeviationBps, r.e.maxSlippageBps, r.e.sellChunkUsdg);
            console2.log("  send list(), setListingGates()", r.list, r.setGates);
        }
        for (uint256 i; i < skipped.length; ++i) {
            console2.log("EXCLUDED, oracle not healthy (market closed, feed stale or stock paused):", skipped[i]);
        }
        console2.log("planned", rows.length, "of", entries.length);
        console2.log("EXPECTED_PLAN_HASH");
        console2.logBytes32(planHash(factory, rows));
    }

    /// @notice What `run()` must be given: the rows, and where they apply.
    function planHash(HedgeFunV2Factory factory, Row[] memory rows) public view returns (bytes32) {
        return keccak256(abi.encode(block.chainid, factory, rows));
    }

    /// @notice Every entry priced at its oracle's live price, in the plan's order; the entries whose oracle is not
    ///         healthy are returned by symbol instead. Reverts on a factory the rule does not hold for and on an
    ///         entry the factory would refuse or the plan must not carry.
    function planFor(HedgeFunV2Factory factory, Entry[] memory entries)
        public
        view
        returns (Row[] memory rows, string[] memory skipped)
    {
        HedgeFunFactory.Defaults memory d = _checkFactory(factory);
        Row[] memory all = new Row[](entries.length);
        string[] memory out = new string[](entries.length);
        uint256 n;
        uint256 s;
        for (uint256 i; i < entries.length; ++i) {
            _checkEntry(factory, d, entries, i);
            (bool ok, Row memory r) = _row(factory, d, entries[i]);
            if (ok) all[n++] = r;
            else out[s++] = entries[i].symbol;
        }
        rows = new Row[](n);
        for (uint256 i; i < n; ++i) rows[i] = all[i];
        skipped = new string[](s);
        for (uint256 i; i < s; ++i) skipped[i] = out[i];
    }

    /// @dev One entry priced at its oracle's live price, or `ok` false when the oracle is not healthy.
    function _row(HedgeFunV2Factory factory, HedgeFunFactory.Defaults memory d, Entry memory e)
        private
        view
        returns (bool ok, Row memory r)
    {
        (ok, r.priceE18) = PriceOracle(e.oracle).tryPrice();
        if (!ok) return (false, r);
        r.e = e;
        r.openPriceE18 = referenceOpenPriceE18(r.priceE18);
        if (r.openPriceE18 == 0) revert BadEntry(e.symbol, "opening price rounds to zero");
        (address oracle, address pool, uint256 open, bool enabled) = factory.listings(e.stock);
        r.oldOpenPriceE18 = open;
        r.list = !(enabled && oracle == e.oracle && pool == e.pool && open == r.openPriceE18);
        (uint16 dev, uint16 slip, uint256 chunk) = _effectiveGates(factory, d, e.stock);
        r.setGates = dev != e.maxDeviationBps || slip != e.maxSlippageBps || chunk != e.sellChunkUsdg;
    }

    /// @notice The owner transactions for `rows`, then the readback. `run()` calls this after the hash check;
    ///         the tests call it with rows they have reviewed themselves.
    function execute(HedgeFunV2Factory factory, address operator, Row[] memory rows) public {
        if (block.chainid != CHAIN_ID) revert WrongChain(block.chainid);
        if (factory.owner() != operator) revert NotFactoryOwner(operator);
        vm.startBroadcast(operator);
        for (uint256 i; i < rows.length; ++i) {
            Row memory r = rows[i];
            if (r.list) factory.list(r.e.stock, r.e.oracle, r.e.pool, r.openPriceE18, true);
            if (r.setGates) factory.setListingGates(r.e.stock, r.e.maxDeviationBps, r.e.maxSlippageBps, r.e.sellChunkUsdg);
        }
        vm.stopBroadcast();
        HedgeFunFactory.Defaults memory d = factory.getDefaults();
        for (uint256 i; i < rows.length; ++i) {
            Row memory r = rows[i];
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(r.e.stock);
            if (!enabled || oracle != r.e.oracle || pool != r.e.pool || open != r.openPriceE18) {
                revert ReadbackFailed(r.e.symbol, "listing");
            }
            (uint16 dev, uint16 slip, uint256 chunk) = _effectiveGates(factory, d, r.e.stock);
            if (dev != r.e.maxDeviationBps || slip != r.e.maxSlippageBps || chunk != r.e.sellChunkUsdg) {
                revert ReadbackFailed(r.e.symbol, "gates");
            }
        }
    }

    function _writeCandidate(
        HedgeFunV2Factory factory,
        address operator,
        Row[] memory rows,
        string[] memory skipped,
        bytes32 h,
        uint256 startBlock,
        bool requested
    ) internal {
        string memory k = "mainnetListings";
        vm.serializeString(k, "schema", "v2-mainnet-listings-v1");
        vm.serializeUint(k, "chainId", CHAIN_ID);
        // Always false: this file is written by the simulation. Receipts and VerifyV2MainnetListings make it true.
        vm.serializeBool(k, "verified", false);
        vm.serializeBool(k, "broadcastRequested", requested);
        vm.serializeUint(k, "block", startBlock);
        vm.serializeUint(k, "timestamp", block.timestamp);
        vm.serializeString(k, "plan", PLAN);
        vm.serializeBytes32(k, "planHash", h);
        vm.serializeAddress(k, "factory", address(factory));
        vm.serializeAddress(k, "operator", operator);
        vm.serializeAddress(k, "usdg", USDG);
        vm.serializeUint(k, "saleBps", REFERENCE_SALE_BPS);
        vm.serializeUint(k, "defaultLpBps", LP_BPS);
        vm.serializeString(k, "openingFdvUsdE18", vm.toString(openingFdvUsdE18()));
        vm.serializeString(k, "excludedUnhealthyOracle", skipped);
        string memory stocks;
        for (uint256 i; i < rows.length; ++i) {
            stocks = vm.serializeString("listedStocks", rows[i].e.symbol, _rowJson(rows[i]));
        }
        string memory json = vm.serializeString(k, "stocks", stocks);
        string memory path = requested ? OUT : OUT_DRY;
        vm.writeJson(json, path);
        console2.log("unverified candidate", path);
    }

    function _rowJson(Row memory r) internal returns (string memory) {
        string memory k = string.concat("listedStock.", r.e.symbol);
        vm.serializeAddress(k, "token", r.e.stock);
        vm.serializeAddress(k, "oracle", r.e.oracle);
        vm.serializeAddress(k, "pool", r.e.pool);
        vm.serializeUint(k, "fee", r.e.fee);
        // the oracle's live price at the simulation block, which the opening price was computed from
        vm.serializeString(k, "priceE18", vm.toString(r.priceE18));
        vm.serializeString(k, "openPriceE18", vm.toString(r.openPriceE18));
        vm.serializeString(k, "previousOpenPriceE18", vm.toString(r.oldOpenPriceE18));
        vm.serializeUint(k, "maxDeviationBps", r.e.maxDeviationBps);
        vm.serializeUint(k, "maxSlippageBps", r.e.maxSlippageBps);
        vm.serializeString(k, "sellChunkUsdg", vm.toString(r.e.sellChunkUsdg));
        vm.serializeBool(k, "listSent", r.list);
        return vm.serializeBool(k, "setListingGatesSent", r.setGates);
    }
}

/// @notice Read-only: every stock of the plan file is listed on the factory with the plan's oracle, pool and
///         gates, keeps the registry's 70% LP share, and opens at the release rule's price for this block's
///         oracle price. Run it on the block the listings landed in (`--fork-block-number`), or on a later block
///         with `PRICE_TOLERANCE_BPS` for the drift the feed has printed since; with the default 0 only the
///         rounding of the rule itself is allowed. Requires V2_FACTORY.
/// @dev The price is the oracle's `tryPrice()`; when the market is closed at the block, the feed's last answer
///      (`lastPriceAt`) is used and said so. A listing is never judged on `lastPriceAt` elsewhere; here it is
///      only compared with.
contract VerifyV2MainnetListings is V2MainnetListingPlan {
    error ListingMismatch(string symbol, string what);

    function run() external view {
        HedgeFunV2Factory factory = HedgeFunV2Factory(vm.envAddress("V2_FACTORY"));
        Entry[] memory entries = parsePlan(vm.readFile(PLAN));
        check(factory, entries, vm.envOr("PRICE_TOLERANCE_BPS", uint256(0)));
        console2.log("live V2 mainnet listings verified", entries.length, address(factory));
    }

    function check(HedgeFunV2Factory factory, Entry[] memory entries, uint256 toleranceBps) public view {
        HedgeFunFactory.Defaults memory d = _checkFactory(factory);
        for (uint256 i; i < entries.length; ++i) {
            _checkEntry(factory, d, entries, i);
            uint256 open = _checkListed(factory, d, entries[i]);
            _checkOpening(entries[i], open, toleranceBps);
        }
    }

    /// @dev the listing, its effective gates and its LP share are the plan's; returns the listed opening price
    function _checkListed(HedgeFunV2Factory factory, HedgeFunFactory.Defaults memory d, Entry memory e)
        private
        view
        returns (uint256 open)
    {
        (address oracle, address pool, uint256 listed, bool enabled) = factory.listings(e.stock);
        if (!enabled || oracle != e.oracle || pool != e.pool || listed == 0) revert ListingMismatch(e.symbol, "listing");
        (uint16 dev, uint16 slip, uint256 chunk) = _effectiveGates(factory, d, e.stock);
        if (dev != e.maxDeviationBps || slip != e.maxSlippageBps || chunk != e.sellChunkUsdg) {
            revert ListingMismatch(e.symbol, "gates");
        }
        if (V2TreasuryDeployer(address(factory.treasuryDeployer())).lpBps(e.stock) != LP_BPS) {
            revert ListingMismatch(e.symbol, "lpBps");
        }
        open = listed;
    }

    /// @dev `open` is the rule applied to this block's oracle price, exactly (the rule floors, and a listing made
    ///      from this very price reproduces it) or within `toleranceBps` of it in price terms, which is the feed
    ///      having moved between the plan's block and this one.
    function _checkOpening(Entry memory e, uint256 open, uint256 toleranceBps) private view {
        (bool live, uint256 price) = PriceOracle(e.oracle).tryPrice();
        if (!live) {
            (live, price,) = PriceOracle(e.oracle).lastPriceAt();
            if (!live) revert ListingMismatch(e.symbol, "no oracle price at this block");
            console2.log("  (market closed at this block: compared with the feed's last print)", e.symbol);
        }
        uint256 expected = referenceOpenPriceE18(price);
        uint256 drift;
        if (open != expected) {
            uint256 implied = Math.mulDiv(openingFdvUsdE18(), 1e18, open * SUPPLY_TOKENS);
            drift = (implied > price ? implied - price : price - implied) * 10_000 / price;
            if (drift > toleranceBps) revert ListingMismatch(e.symbol, "opening price");
        }
        console2.log("listed", e.symbol, e.stock);
        console2.log("  openPriceE18, at this block's price, drift bps", open, expected, drift);
    }
}
