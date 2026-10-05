// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {AssetPriceOracle} from "../src/AssetPriceOracle.sol";
import {AlwaysOpenCalendar} from "../src/AlwaysOpenCalendar.sol";
import {MockToken, MockFeed, MockLpPool} from "./mocks/Mocks.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// Wrapped ETH as the venue sees it: an ERC-20 that knows nothing about `oraclePaused()`.
contract PlainAsset is ERC20 {
    uint8 private immutable _decimals;

    constructor(string memory symbol_, uint8 decimals_) ERC20(symbol_, symbol_) { _decimals = decimals_; }

    function decimals() public view override returns (uint8) { return _decimals; }
    function mint(address to, uint256 amount) external { _mint(to, amount); }
}

contract AssetPriceOracleTest is V2FactoryFixture {
    PlainAsset weth;
    MockFeed ethFeed;
    AlwaysOpenCalendar calendar;
    AssetPriceOracle assetOracle;
    address safe = makeAddr("owner safe");

    function setUp() public {
        _setUpV2(18);
        weth = new PlainAsset("WETH", 18);
        ethFeed = new MockFeed(8);
        ethFeed.set(2700e8);
        calendar = new AlwaysOpenCalendar(safe);
        assetOracle = new AssetPriceOracle(address(weth), address(ethFeed), address(usdgFeed), address(calendar), 26 hours, 26 hours);
    }

    /// The reason this contract exists: the stock oracle fails closed on a token that cannot say whether its
    /// oracle is paused, so it can never price wrapped ETH.
    function test_theStockOracleNeverPricesATokenWithoutOraclePaused_thisOneDoes() public {
        PriceOracle stockStyle =
            new PriceOracle(address(weth), address(ethFeed), address(usdgFeed), address(calendar), 26 hours, 26 hours);
        (bool ok, uint256 p) = stockStyle.tryPrice();
        assertFalse(ok);
        assertEq(p, 0);

        (ok, p) = assetOracle.tryPrice();
        assertTrue(ok);
        assertEq(p, 2700e18, "USDG per whole token, 1e18-scaled");
        assertEq(assetOracle.price(), 2700e18);
        assertEq(assetOracle.stock(), address(weth));
        assertEq(address(assetOracle.calendar()), address(calendar));
    }

    /// Same arithmetic as the stock oracle, feed for feed: on a token both can price, they agree to the wei.
    function testFuzz_agreesWithTheStockOracleOnATokenBothCanPrice(uint64 rawAsset, uint32 rawUsdg, uint8 feedDecimals)
        public
    {
        feedDecimals = uint8(bound(feedDecimals, 6, 18));
        MockFeed a = new MockFeed(feedDecimals);
        a.set(int256(bound(uint256(rawAsset), 1, type(uint64).max)));
        usdgFeed.set(int256(bound(uint256(rawUsdg), 0.9e8, 1.1e8)));
        PriceOracle baseline =
            new PriceOracle(address(stock), address(a), address(usdgFeed), address(calendar), 26 hours, 26 hours);
        AssetPriceOracle candidate =
            new AssetPriceOracle(address(stock), address(a), address(usdgFeed), address(calendar), 26 hours, 26 hours);
        (bool okR, uint256 pR) = baseline.tryPrice();
        (bool okC, uint256 pC) = candidate.tryPrice();
        assertEq(okC, okR);
        assertEq(pC, pR);
        (bool lastR, uint256 lpR, uint256 atR) = baseline.lastPriceAt();
        (bool lastC, uint256 lpC, uint256 atC) = candidate.lastPriceAt();
        assertEq(lastC, lastR);
        assertEq(lpC, lpR);
        assertEq(atC, atR);
    }

    function test_usdgOffItsPegMovesThePrice() public {
        usdgFeed.set(0.99e8);
        (, uint256 p) = assetOracle.tryPrice();
        assertEq(p, Math.mulDiv(2700e18, 1e8, 0.99e8), "more USDG for the same ETH when USDG is worth less");
    }

    function test_failsClosedOnAStaleOrBrokenFeed() public {
        vm.warp(block.timestamp + 26 hours);
        usdgFeed.set(1e8);
        (bool ok,) = assetOracle.tryPrice();
        assertTrue(ok, "exactly at the age limit");

        vm.warp(block.timestamp + 1);
        usdgFeed.set(1e8);
        (ok,) = assetOracle.tryPrice();
        assertFalse(ok, "the asset print is a second too old");
        (bool last, uint256 p, uint256 at) = assetOracle.lastPriceAt();
        assertTrue(last, "the last print is still reported, with its age, for whoever needs to know how old it is");
        assertEq(p, 2700e18);
        assertEq(at, block.timestamp - 26 hours - 1);
        vm.expectRevert(AssetPriceOracle.Unhealthy.selector);
        assetOracle.price();

        ethFeed.set(2700e8);
        usdgFeed.setAt(1e8, block.timestamp - 26 hours - 1);
        (ok,) = assetOracle.tryPrice();
        assertFalse(ok, "the dollar leg is stale");
        (last,,) = assetOracle.lastPriceAt();
        assertFalse(last, "and it never gets to be");

        usdgFeed.set(1e8);
        ethFeed.set(0);
        (ok,) = assetOracle.tryPrice();
        assertFalse(ok, "a zero answer");
        ethFeed.set(-1);
        (ok,) = assetOracle.tryPrice();
        assertFalse(ok, "a negative answer");
        ethFeed.setAt(2700e8, block.timestamp + 1);
        (ok,) = assetOracle.tryPrice();
        assertFalse(ok, "a print from the future");
        (last,,) = assetOracle.lastPriceAt();
        assertFalse(last);
    }

    function test_constructorRefusesZeroAddressesAndAnAgeBeyondTheCap() public {
        vm.expectRevert(bytes("zero"));
        new AssetPriceOracle(address(0), address(ethFeed), address(usdgFeed), address(calendar), 1 hours, 1 hours);
        vm.expectRevert(bytes("zero"));
        new AssetPriceOracle(address(weth), address(ethFeed), address(usdgFeed), address(0), 1 hours, 1 hours);
        vm.expectRevert(bytes("age"));
        new AssetPriceOracle(address(weth), address(ethFeed), address(usdgFeed), address(calendar), 48 hours + 1, 1 hours);
        vm.expectRevert(bytes("age"));
        new AssetPriceOracle(address(weth), address(ethFeed), address(usdgFeed), address(calendar), 0, 1 hours);
        new AssetPriceOracle(address(weth), address(ethFeed), address(usdgFeed), address(calendar), 48 hours, 1 hours);
    }

    // ------------------------------------------------------------------------------------------------ the calendar
    function test_calendarIsOpenAroundTheClockUntilItsOwnerHalts() public {
        // a Saturday and a Sunday: the equity calendar is shut, this one is not
        for (uint256 day; day < 14; ++day) {
            uint256 ts = 1_790_000_000 + day * 1 days;
            assertFalse(calendar.isClosed(ts));
            assertFalse(calendar.isScheduledClosure(ts));
            assertEq(calendar.tradingDate(ts), ts / 1 days, "a trading date is a UTC day");
        }
        vm.expectRevert(abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", address(this)));
        calendar.setHalted(true);

        vm.prank(safe);
        calendar.setHalted(true);
        assertTrue(calendar.isClosed(block.timestamp));
        assertFalse(calendar.isScheduledClosure(block.timestamp), "a halt is never a scheduled closure");
        (bool ok,) = assetOracle.tryPrice();
        assertFalse(ok, "no price while halted");
        (bool last, uint256 p,) = assetOracle.lastPriceAt();
        assertTrue(last);
        assertEq(p, 2700e18);

        vm.prank(safe);
        calendar.setHalted(false);
        (ok,) = assetOracle.tryPrice();
        assertTrue(ok);
    }

    function test_calendarOwnershipIsTwoStep() public {
        address next = makeAddr("next safe");
        vm.prank(safe);
        calendar.transferOwnership(next);
        assertEq(calendar.owner(), safe);
        vm.prank(next);
        calendar.acceptOwnership();
        assertEq(calendar.owner(), next);
    }

    // ------------------------------------------------------------------------------------------------ as a listing
    /// The factory lists it and a treasury is born, graduated and priced on it exactly as on a stock: the oracle's
    /// read ABI is the stock oracle's. Halting the calendar stops the treasury; resuming restarts it.
    function test_listedLaunchedGraduatedAndPricedLikeAStock_andTheHaltStopsTheTreasury() public {
        MockLpPool pool = new MockLpPool(address(weth), address(usdg), 500);
        pool.setSqrt(uint160(Math.sqrt(Math.mulDiv(2700e18, 1 << 192, 1e30))));
        v3f.set(address(weth), address(usdg), 500, address(pool));
        uint256 open = 3_700_000_000; // 3.7e-9 WETH per token: about 10,000 USDG for the whole supply at 2,700
        vm.prank(owner);
        factory.list(address(weth), address(assetOracle), address(pool), open, true);

        HedgeFunFactory.Request memory q = _request();
        q.symbol = "ETHPAIR";
        q.stock = address(weth);
        q.expectedOpenPriceE18 = open;
        (, address predicted, bytes32 terms) = factory.predict(q);
        uint256 id = factory.launch(q, terms);
        HedgeFunBondingCurve curve = HedgeFunBondingCurve(factory.curves(id));
        assertEq(curve.treasury(), predicted);
        HedgeFunV2Treasury treasury = HedgeFunV2Treasury(predicted);
        assertEq(address(treasury.oracle()), address(assetOracle));

        weth.mint(address(this), 1_000e18);
        weth.approve(address(curve), type(uint256).max);
        vm.warp(curve.launchedAt() + curve.snipeSeconds());
        ethFeed.set(2700e8);
        usdgFeed.set(1e8);
        curve.buy(type(uint256).max, 1, address(this), block.timestamp);
        assertEq(uint256(curve.status()), uint256(HedgeFunBondingCurve.Status.Graduated));
        assertGt(treasury.bookedStock(), 0, "the graduation ETH is booked at the oracle's price");
        assertEq(IERC20(address(weth)).balanceOf(address(treasury)), treasury.bookedStock() + treasury.buybackStock() + treasury.unbookedStock());

        (bool healthy, uint256 p) = treasury.health();
        assertTrue(healthy, "a token with no oraclePaused() is priced and tradable");
        assertEq(p, 2700e18);

        vm.prank(safe);
        calendar.setHalted(true);
        (healthy,) = treasury.health();
        assertFalse(healthy, "halted: the treasury does not trade");
        vm.expectRevert();
        treasury.execute();

        vm.prank(safe);
        calendar.setHalted(false);
        (healthy,) = treasury.health();
        assertTrue(healthy);
    }
}
