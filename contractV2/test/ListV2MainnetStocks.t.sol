// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {PoolManager} from "v4-core/src/PoolManager.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {V2TreasuryDeployer} from "../src/v2/V2TreasuryDeployer.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {MockToken, MockFeed, MockPool, MockV3Factory, SwitchableCalendar} from "./mocks/Mocks.sol";
import {V2MainnetCore} from "../script/mainnet/V2MainnetCore.sol";
import {DeployV2MainnetCore} from "../script/mainnet/DeployV2MainnetCore.s.sol";
import {V2MainnetListingPlan, ListV2MainnetStocks, VerifyV2MainnetListings} from "../script/mainnet/ListV2MainnetStocks.s.sol";
import {DeployV2Testnet} from "../script/testnet/DeployV2Testnet.s.sol";
import {CalibrateV2Listings} from "../script/testnet/CalibrateV2Listings.s.sol";
import {SafeLike, WrappedNative, MainnetCoreProbe, OtherSaleShareCore} from "./DeployV2MainnetCore.t.sol";

/// Offline: the mainnet core at the chain's pinned addresses, a mocked stock venue bound to the pinned USDG feed
/// and calendar, and the listing script's pure and view parts plus the transactions it sends. The committed plan
/// file is parsed here; what it lists is the fork suite's (`test/MainnetV2ListingsFork.t.sol`).
contract ListV2MainnetStocksTest is Test {
    address deployer = makeAddr("mainnet deployer");
    SafeLike owner;
    SafeLike protocol;
    WrappedNative weth;
    HedgeFunV2Factory factory;
    V2TreasuryDeployer registry;
    ListV2MainnetStocks script;
    VerifyV2MainnetListings verifier;
    MainnetCoreProbe probe;
    bytes32 reviewed;

    /// three mocked stocks: a 0.05% pool at the default gates, a 1% pool at the wide gates, another 0.05% pool
    V2MainnetListingPlan.Entry[] entries;
    MockToken[] stocks;
    MockFeed[] feeds;
    uint256[] pricesE18;

    function setUp() public {
        vm.chainId(4663);
        vm.warp(1_700_000_000);
        probe = new MainnetCoreProbe();
        _deployAt(bytes.concat(type(PoolManager).creationCode, abi.encode(address(this))), probe.PM());
        vm.etch(probe.V3_FACTORY(), address(new MockV3Factory()).code);
        _deployAt(bytes.concat(type(MockToken).creationCode, abi.encode("USDG", uint8(6))), probe.USDG());
        owner = new SafeLike(2, 3);
        protocol = new SafeLike(3, 5);
        weth = new WrappedNative();
        reviewed = probe.defaultsHash();
        V2MainnetCore.Deployed memory x = new DeployV2MainnetCore().deploy(deployer, _roles(), true, reviewed, 7931, 0);
        factory = x.factory;
        registry = x.treasury;
        script = new ListV2MainnetStocks();
        verifier = new VerifyV2MainnetListings();

        // the venue every mainnet oracle is bound to, at its pinned addresses
        _deployAt(bytes.concat(type(MockFeed).creationCode, abi.encode(uint8(8))), script.USDG_FEED());
        MockFeed(script.USDG_FEED()).set(1e8);
        vm.etch(script.CALENDAR(), type(SwitchableCalendar).runtimeCode);

        _stock("NVDA", 239.02e18, 500, 50, 100, 2_000e6);
        _stock("MSTR", 300e18, 10_000, 125, 175, 2_000e6);
        _stock("GLD", 254.4e18, 500, 50, 100, 2_000e6);
    }

    function _deployAt(bytes memory creation, address where) internal {
        vm.etch(where, creation);
        (bool ok, bytes memory runtime) = where.call("");
        require(ok, "constructor");
        vm.etch(where, runtime);
    }

    function _roles() internal view returns (V2MainnetCore.Roles memory) {
        return V2MainnetCore.Roles(address(owner), address(protocol), address(weth));
    }

    function _stock(string memory symbol, uint256 priceE18, uint24 fee, uint16 dev, uint16 slip, uint64 chunk) internal {
        MockToken stock = new MockToken(symbol, 18);
        MockFeed feed = new MockFeed(8);
        feed.set(int256(priceE18 / 1e10));
        PriceOracle oracle = new PriceOracle(address(stock), address(feed), script.USDG_FEED(), script.CALENDAR(), 26 hours, 26 hours);
        MockPool pool = new MockPool(address(stock), probe.USDG(), true, fee, 1e30);
        MockV3Factory(probe.V3_FACTORY()).set(address(stock), probe.USDG(), fee, address(pool));
        entries.push(V2MainnetListingPlan.Entry(symbol, address(stock), address(oracle), address(pool), fee, dev, slip, chunk));
        stocks.push(stock);
        feeds.push(feed);
        pricesE18.push(priceE18);
    }

    function _plan() internal view returns (ListV2MainnetStocks.Row[] memory rows, string[] memory skipped) {
        return script.planFor(factory, entries);
    }

    function _hash(ListV2MainnetStocks.Row[] memory rows) internal view returns (bytes32) {
        return script.planHash(factory, rows);
    }

    // ------------------------------------------------------------------------------------------ the rule
    /// One formula on both chains: `DeployV2Testnet.referenceOpenPriceE18`, `CalibrateV2Listings`' copy and this.
    function test_openingRuleIsTheTestnetDeploymentsAndTheCalibrations() public {
        DeployV2Testnet fresh = new DeployV2Testnet();
        CalibrateV2Listings calibration = new CalibrateV2Listings();
        assertEq(script.TARGET_GRADUATION_FDV_USD_E18(), fresh.TARGET_GRADUATION_FDV_USD_E18());
        assertEq(script.REFERENCE_SALE_BPS(), fresh.REFERENCE_SALE_BPS());
        assertEq(script.REFERENCE_SALE_BPS(), 7931);
        assertEq(script.LP_BPS(), 7000);
        assertEq(script.openingFdvUsdE18(), 2_140.3805e18, "the opening FDV of the runbook");
        uint256[9] memory prices = [uint256(24e18), 55.08e18, 101.16e18, 200e18, 239.02e18, 339e18, 550.29e18, 776.13e18, 5_000e18];
        for (uint256 i; i < prices.length; ++i) {
            uint256 open = script.referenceOpenPriceE18(prices[i]);
            assertEq(open, fresh.referenceOpenPriceE18(prices[i]));
            assertEq(open, calibration.referenceOpenPriceE18(prices[i]));
            // floor(openingFdv * 1e18 / (price * 1e9)), the runbook's formula written out
            assertEq(open, 2_140.3805e18 * 1e18 / (prices[i] * 1e9));
            assertLe(script.impliedOpeningFdvUsdE18(open, prices[i]), 2_140.3805e18);
            assertApproxEqRel(script.impliedOpeningFdvUsdE18(open, prices[i]), 2_140.3805e18, 1e9);
        }
    }

    // ------------------------------------------------------------------------------------------ the plan file
    function test_parsesTheCommittedPlanFile_eighteenStocksAndNoCandidate() public view {
        V2MainnetListingPlan.Entry[] memory e = script.parsePlan(vm.readFile(script.PLAN()));
        assertEq(e.length, 18, "the day-one set of docs/V2_RELEASE_RUNBOOK.md section C");
        assertEq(e[0].symbol, "NVDA");
        assertEq(e[0].stock, 0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC);
        assertEq(e[0].oracle, 0x03c77f527Aa1B0B304602e3fB9Ac994dd1c157f8);
        assertEq(e[0].pool, 0xd4EB21209C4D6093f80B5b84f5C45cc093EA14a3);
        assertEq(e[5].symbol, "GME");
        assertEq(e[5].fee, 500, "GME on its 0.05% pool");
        assertEq(e[15].symbol, "SGOV");
        assertEq(e[15].oracle, 0x093CD301Ce1AdEEdd9bC3814f9c00E42Ba603BeD, "deploy/mainnet-v2-oracles.json");
        assertEq(e[16].symbol, "SPY");
        assertEq(e[16].pool, 0xa7Bb1AC63BBaB0C44316E6c8C455213441689167);
        assertEq(e[16].fee, 500);
        assertEq(e[17].symbol, "DELL");
        assertEq(e[17].fee, 10_000);
        for (uint256 i; i < e.length; ++i) {
            bool onePercentPool = e[i].fee == 10_000;
            assertEq(e[i].maxDeviationBps, onePercentPool ? 125 : 50, e[i].symbol);
            assertEq(e[i].maxSlippageBps, onePercentPool ? 175 : 100, e[i].symbol);
            assertEq(e[i].sellChunkUsdg, 2_000e6, e[i].symbol);
            assertTrue(e[i].fee == 500 || e[i].fee == 3000 || e[i].fee == 10_000);
            bytes32 sym = keccak256(bytes(e[i].symbol));
            assertTrue(sym != keccak256("PLTR") && sym != keccak256("SLV"), "candidates are not planned");
            for (uint256 j; j < i; ++j) {
                assertTrue(e[j].stock != e[i].stock && e[j].oracle != e[i].oracle && e[j].pool != e[i].pool);
                assertTrue(keccak256(bytes(e[j].symbol)) != sym);
            }
        }
        assertEq(e[7].symbol, "MSTR");
        assertEq(e[7].maxDeviationBps, 125);
    }

    function test_refusesAPlanForAnotherChainOrVenue() public {
        string memory head = '"usdg":"0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168","oracleBindings":{"usdgFeed":"0x61B7e5650328764B076A108EFF5fa7282a1B9aD2","calendar":"0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5"}';
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.WrongPlan.selector, "chainId"));
        script.parsePlan(string.concat('{"chainId":46630,', head, ',"stocks":[]}'));
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.WrongPlan.selector, "no stocks"));
        script.parsePlan(string.concat('{"chainId":4663,', head, ',"stocks":[],"candidates":[{"symbol":"PLTR"}]}'));
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.WrongPlan.selector, "usdg"));
        script.parsePlan('{"chainId":4663,"usdg":"0x539574139BB4Ac74Fd2183ba0E38ed777E30B58d","oracleBindings":{"usdgFeed":"0x61B7e5650328764B076A108EFF5fa7282a1B9aD2","calendar":"0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5"},"stocks":[]}');
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.BadEntry.selector, "X", "fee"));
        script.parsePlan(string.concat('{"chainId":4663,', head, ',"stocks":[{"symbol":"X","token":"0x0000000000000000000000000000000000000001","oracle":"0x0000000000000000000000000000000000000002","pool":"0x0000000000000000000000000000000000000003","fee":0,"maxDeviationBps":50,"maxSlippageBps":100,"sellChunkUsdg":2000000000}]}'));
    }

    // ------------------------------------------------------------------------------------------ the plan
    function test_planPricesEveryHealthyStockAtItsLiveOraclePrice_andLeavesTheOthersOut() public {
        (ListV2MainnetStocks.Row[] memory rows, string[] memory skipped) = _plan();
        assertEq(rows.length, 3);
        assertEq(skipped.length, 0);
        for (uint256 i; i < rows.length; ++i) {
            assertEq(rows[i].e.stock, entries[i].stock);
            assertEq(rows[i].priceE18, pricesE18[i], "the oracle's price");
            assertEq(rows[i].openPriceE18, script.referenceOpenPriceE18(pricesE18[i]));
            assertEq(rows[i].oldOpenPriceE18, 0, "not listed yet");
            assertTrue(rows[i].list);
        }
        assertFalse(rows[0].setGates, "50 / 100 / 2,000 are the factory's defaults: nothing to set");
        assertTrue(rows[1].setGates, "125 / 175 on the 1% pool are not");
        assertFalse(rows[2].setGates);

        // a paused stock is left out, the rest still priced
        stocks[1].setOraclePaused(true);
        (rows, skipped) = _plan();
        assertEq(rows.length, 2);
        assertEq(skipped.length, 1);
        assertEq(skipped[0], "MSTR");
        assertEq(rows[1].e.stock, entries[2].stock);
        stocks[1].setOraclePaused(false);

        // a stale feed likewise
        feeds[2].setAt(int256(pricesE18[2] / 1e10), block.timestamp - 27 hours);
        (rows, skipped) = _plan();
        assertEq(rows.length, 2);
        assertEq(skipped[0], "GLD");
        feeds[2].set(int256(pricesE18[2] / 1e10));

        // a closed market excludes everything: there is nothing to list, and nothing is listed on the last print
        SwitchableCalendar(script.CALENDAR()).setClosed(true);
        (rows, skipped) = _plan();
        assertEq(rows.length, 0);
        assertEq(skipped.length, 3);
        SwitchableCalendar(script.CALENDAR()).setClosed(false);
        (rows,) = _plan();
        assertEq(rows.length, 3);
    }

    function test_hashNamesTheChainTheFactoryAndEveryRow() public {
        (ListV2MainnetStocks.Row[] memory rows,) = _plan();
        bytes32 h = _hash(rows);
        assertTrue(h != keccak256(abi.encode(rows)), "the rows alone are not the hash");
        assertTrue(h != script.planHash(HedgeFunV2Factory(address(0xdead)), rows), "it names the factory");
        // a feed that printed again moves the row and the hash
        feeds[0].set(int256(pricesE18[0] / 1e10) + 1e8);
        (ListV2MainnetStocks.Row[] memory again,) = _plan();
        assertTrue(again[0].openPriceE18 != rows[0].openPriceE18);
        assertTrue(_hash(again) != h);
        feeds[0].set(int256(pricesE18[0] / 1e10));
        (again,) = _plan();
        assertEq(_hash(again), h, "the same plan hashes the same");
        // a listing changed under the review moves it too
        vm.prank(deployer);
        factory.setListingGates(entries[0].stock, 60, 120, 2_000e6);
        (again,) = _plan();
        assertTrue(again[0].setGates);
        assertTrue(_hash(again) != h);
        vm.chainId(46630);
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.WrongChain.selector, 46630));
        script.planFor(factory, entries);
    }

    // ------------------------------------------------------------------------------------------ the transactions
    function test_executeListsAndSetsGatesWhereTheyDiffer_thenNothingIsLeftToSend_andTheVerifierAgrees() public {
        (ListV2MainnetStocks.Row[] memory rows,) = _plan();
        vm.recordLogs();
        script.execute(factory, deployer, rows);
        assertEq(vm.getRecordedLogs().length, 4, "three list() and one setListingGates()");
        HedgeFunFactory.Defaults memory d = factory.getDefaults();
        for (uint256 i; i < rows.length; ++i) {
            (address oracle, address pool, uint256 open, bool enabled) = factory.listings(entries[i].stock);
            assertTrue(enabled);
            assertEq(oracle, entries[i].oracle);
            assertEq(pool, entries[i].pool);
            assertEq(open, script.referenceOpenPriceE18(pricesE18[i]));
            (uint16 dev, uint16 slip, uint64 chunk) = factory.listingGates(entries[i].stock);
            if (i == 1) {
                assertEq(dev, 125);
                assertEq(slip, 175);
                assertEq(chunk, 2_000e6);
            } else {
                assertEq(dev, 0, "the defaults apply, nothing was stored");
                assertEq(slip, 0);
                assertEq(chunk, 0);
                assertEq(d.maxDeviationBps, 50);
                assertEq(d.maxSlippageBps, 100);
                assertEq(d.sellChunkUsdg, 2_000e6);
            }
            assertEq(registry.lpBps(entries[i].stock), 7000, "the registry's default LP share, untouched");
        }

        (ListV2MainnetStocks.Row[] memory again, string[] memory skipped) = _plan();
        assertEq(again.length, 3);
        assertEq(skipped.length, 0);
        for (uint256 i; i < again.length; ++i) {
            assertFalse(again[i].list, "already listed exactly so");
            assertFalse(again[i].setGates);
            assertEq(again[i].oldOpenPriceE18, again[i].openPriceE18);
        }
        vm.recordLogs();
        script.execute(factory, deployer, again);
        assertEq(vm.getRecordedLogs().length, 0, "a second run sends nothing");

        verifier.check(factory, entries, 0);

        // the opening price drifts with the stock: a re-plan after a 1% move re-lists at the new price
        feeds[0].set(int256(pricesE18[0] / 1e10) * 101 / 100);
        (again,) = _plan();
        assertTrue(again[0].list);
        assertFalse(again[1].list);
        assertFalse(again[0].setGates);
        vm.expectRevert(abi.encodeWithSelector(VerifyV2MainnetListings.ListingMismatch.selector, "NVDA", "opening price"));
        verifier.check(factory, entries, 0);
        verifier.check(factory, entries, 99); // a 1% rise is 99 bps of the new price
        vm.expectRevert(abi.encodeWithSelector(VerifyV2MainnetListings.ListingMismatch.selector, "NVDA", "opening price"));
        verifier.check(factory, entries, 98);
        script.execute(factory, deployer, again);
        verifier.check(factory, entries, 0);
    }

    function test_executeIsTheOwnersAndReadsBack() public {
        (ListV2MainnetStocks.Row[] memory rows,) = _plan();
        vm.expectRevert(abi.encodeWithSelector(ListV2MainnetStocks.NotFactoryOwner.selector, address(owner)));
        script.execute(factory, address(owner), rows);
        // the readback compares the chain with the rows, not the rows with themselves
        rows[0].list = false;
        vm.expectRevert(abi.encodeWithSelector(ListV2MainnetStocks.ReadbackFailed.selector, "NVDA", "listing"));
        script.execute(factory, deployer, rows);
        rows[0].list = true;
        rows[1].setGates = false;
        vm.expectRevert(abi.encodeWithSelector(ListV2MainnetStocks.ReadbackFailed.selector, "MSTR", "gates"));
        script.execute(factory, deployer, rows);
    }

    function test_verifierRefusesWhatIsNotListedAsPlanned() public {
        (ListV2MainnetStocks.Row[] memory rows,) = _plan();
        vm.expectRevert(abi.encodeWithSelector(VerifyV2MainnetListings.ListingMismatch.selector, "NVDA", "listing"));
        verifier.check(factory, entries, 0);
        script.execute(factory, deployer, rows);
        verifier.check(factory, entries, 0);

        vm.startPrank(deployer);
        factory.setListingGates(entries[2].stock, 60, 120, 2_000e6);
        vm.expectRevert(abi.encodeWithSelector(VerifyV2MainnetListings.ListingMismatch.selector, "GLD", "gates"));
        verifier.check(factory, entries, 0);
        factory.setListingGates(entries[2].stock, 0, 0, 0);
        verifier.check(factory, entries, 0);

        factory.list(entries[0].stock, entries[0].oracle, entries[0].pool, rows[0].openPriceE18, false);
        vm.expectRevert(abi.encodeWithSelector(VerifyV2MainnetListings.ListingMismatch.selector, "NVDA", "listing"));
        verifier.check(factory, entries, 0);
        factory.list(entries[0].stock, entries[0].oracle, entries[0].pool, rows[0].openPriceE18, true);

        registry.setLpBps(entries[1].stock, 5000);
        vm.expectRevert(abi.encodeWithSelector(VerifyV2MainnetListings.ListingMismatch.selector, "MSTR", "lpBps"));
        verifier.check(factory, entries, 0);
        registry.setLpBps(entries[1].stock, 7000);
        vm.stopPrank();

        // a closed market: compared with the last print, and said so
        SwitchableCalendar(script.CALENDAR()).setClosed(true);
        verifier.check(factory, entries, 0);
    }

    // ------------------------------------------------------------------------------------------ refusals
    /// The opening rule assumes the fixed 79.31% sale and the 70% LP default; a core with either different is refused
    /// before anything is priced.
    function test_refusesAFactoryWithAnotherSaleShareOrLpDefault() public {
        V2MainnetCore.Deployed memory other = new OtherSaleShareCore().deployWith(4400, deployer, _roles());
        assertEq(other.curve.DEFAULT_SALE_BPS(), 4400);
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.SaleShareNotTheReference.selector, uint16(4400)));
        script.planFor(other.factory, entries);
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.SaleShareNotTheReference.selector, uint16(4400)));
        verifier.check(other.factory, entries, 0);

        vm.mockCall(address(registry), abi.encodeWithSignature("DEFAULT_LP_BPS()"), abi.encode(uint16(5000)));
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.LpDefaultNotTheReference.selector, uint16(5000)));
        script.planFor(factory, entries);
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.LpDefaultNotTheReference.selector, uint16(5000)));
        verifier.check(factory, entries, 0);
        vm.clearMockedCalls();
        (ListV2MainnetStocks.Row[] memory rows,) = _plan();
        assertEq(rows.length, 3);
    }

    function test_refusesEntriesTheFactoryWouldRefuseOrThePlanMustNotCarry() public {
        V2MainnetListingPlan.Entry[] memory e = entries;

        e[0].pool = address(new MockPool(entries[0].stock, probe.USDG(), true, 3000, 1e30)); // a 0.30% pool under a 0.05% entry
        _expectBadEntry(e, "NVDA", "pool.fee");
        e[0].fee = 3000; // consistent, but not the V3 factory's pool for the pair at that tier
        _expectBadEntry(e, "NVDA", "not the V3 factory's pool");
        e = entries;
        e[0].pool = entries[2].pool; // GLD's pool, same tier, under NVDA
        _expectBadEntry(e, "NVDA", "not the V3 factory's pool");
        e = entries;

        e[1].oracle = address(new PriceOracle(entries[2].stock, address(feeds[2]), script.USDG_FEED(), script.CALENDAR(), 26 hours, 26 hours)); // prices GLD, under MSTR
        _expectBadEntry(e, "MSTR", "oracle.stock");
        e[1].oracle = entries[0].oracle; // NVDA's own oracle under MSTR: named twice
        _expectBadEntry(e, "MSTR", "duplicate");
        e = entries;

        e[1].maxSlippageBps = 125; // deviation must be under slippage
        _expectBadEntry(e, "MSTR", "gates");
        e[1].maxSlippageBps = 301; // over the treasury's cap
        _expectBadEntry(e, "MSTR", "gates");
        e[1].maxSlippageBps = 175;
        e[1].maxDeviationBps = 0;
        _expectBadEntry(e, "MSTR", "gates");
        e = entries;

        e[2].sellChunkUsdg = 4e6; // under the minimum lot
        _expectBadEntry(e, "GLD", "sellChunkUsdg");
        e = entries;

        e[2].stock = entries[0].stock;
        _expectBadEntry(e, "GLD", "duplicate");
        e = entries;
        e[2].symbol = "NVDA";
        _expectBadEntry(e, "NVDA", "duplicate");
        e = entries;

        // an oracle against another dollar feed, however healthy
        PriceOracle elsewhere = new PriceOracle(entries[0].stock, address(feeds[0]), address(new MockFeed(8)), script.CALENDAR(), 26 hours, 26 hours);
        e[0].oracle = address(elsewhere);
        _expectBadEntry(e, "NVDA", "oracle.usdgFeed");
        e = entries;

        MockToken six = new MockToken("SIX", 6);
        e[0].stock = address(six);
        _expectBadEntry(e, "NVDA", "18-decimal stock");
    }

    function _expectBadEntry(V2MainnetListingPlan.Entry[] memory e, string memory symbol, string memory what) internal {
        vm.expectRevert(abi.encodeWithSelector(V2MainnetListingPlan.BadEntry.selector, symbol, what));
        script.planFor(factory, e);
    }
}
