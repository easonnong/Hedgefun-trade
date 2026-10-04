// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {PriceOracle} from "../src/PriceOracle.sol";
import {TradingCalendar} from "../src/TradingCalendar.sol";
import {HedgeFunFactory} from "../src/HedgeFunFactory.sol";

interface IFeed { function decimals() external view returns (uint8); function description() external view returns (string memory); }

/// One `PriceOracle` per stock of the planned first batch, against the production calendar. An oracle has no owner
/// and no role: deploying one lists nothing. Listing is the Safe's `factory.list`, after its signers have read back
/// every immutable this script prints (docs/DEPLOYMENT.md, sections 7.1 and 9).
///
///   forge script script/DeployPriceOracles.s.sol --tc DeployPriceOracles --rpc-url publicnode                 # simulate
///   forge script script/DeployPriceOracles.s.sol --tc DeployPriceOracles --rpc-url publicnode --broadcast \
///     --account <deployer keystore> --sender <deployer>
///
/// Token and feed addresses are the ones resolved by address in docs/DEPLOYMENT.md 7.1, never by feed name.
/// Both ages are 26 hours: the USDG/USD feed heartbeats every 24 h, and weekday stock feeds went up to 13.4 h
/// without an update outside regular hours (measured 2026-09-22). Neither can be changed after deployment.
contract DeployPriceOracles is Script {
    HedgeFunFactory constant FACTORY = HedgeFunFactory(0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961);
    address constant CALENDAR = 0xFE9E85f0C258Fc2757eB6Acd1ca032Ec860487F5;
    address constant SAFE = 0x2910117dd2cB431173Ae9Fb6eAF30726321d1693;
    address constant USDG_FEED = 0x61B7e5650328764B076A108EFF5fa7282a1B9aD2;
    uint256 constant MAX_STOCK_AGE = 26 hours;
    uint256 constant MAX_USDG_AGE = 26 hours;

    struct Stock { string sym; address token; address feed; }

    function stocks() public pure returns (Stock[12] memory s) {
        s[0]  = Stock("NVDA",  0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC, 0x379EC4f7C378F34a1B47E4F3cbeBCbAC3E8E9F15);
        s[1]  = Stock("SPCX",  0x4a0E65A3EcceC6dBe60AE065F2e7bb85Fae35eEa, 0xB265810950ba6c5C0Ff821c9963014a56fD8Bffb);
        s[2]  = Stock("CRCL",  0xdF0992E440dD0be65BD8439b609d6D4366bf1CB5, 0x6652eDf64bA3731C4F2D3ce821A0Fb1f1f6b482a);
        s[3]  = Stock("GOOGL", 0x2e0847E8910a9732eB3fb1bb4b70a580ADAD4FE3, 0xF6f373a037c30F0e5010d854385cA89185AE638b);
        s[4]  = Stock("AMZN",  0x12f190a9F9d7D37a250758b26824B97CE941bF54, 0xD5a1508ceD74c084eBf3cBe853e2C968fB2a651C);
        s[5]  = Stock("GME",   0x1b0E319c6A659F002271B69dB8A7df2F911c153E, 0x27C71df6A64fB476468EdF256CF72c038baB5B67);
        s[6]  = Stock("META",  0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35, 0x7C38C00C30BEe9378381E7B6135d7283356D71b1);
        s[7]  = Stock("USAR",  0xd917B029C761D264c6A312BBbcDA868658eF86a6, 0xA994d3684e8400A6c8078226925779FdeE682DD9);
        s[8]  = Stock("MSTR",  0xec262a75e413fAfD0dF80480274532C79D42da09, 0x396118bdFB181e6240E74D243F266B061c0edc3D);
        s[9]  = Stock("AMD",   0x86923f96303D656E4aa86D9d42D1e57ad2023fdC, 0x943A29E7ae51A4798823ca9eEd2ed533B2A22C72);
        s[10] = Stock("MU",    0xfF080c8ce2E5feadaCa0Da81314Ae59D232d4afD, 0x425EEFdCf05ed6526C3cE61Af99429A228a6d596);
        s[11] = Stock("INTC",  0xc72b96e0E48ecd4DC75E1e45396e26300BC39681, 0x3f390C5C24628Ac7C489515402235FeAD71D1913);
    }

    function run() external {
        require(block.chainid == 4663, "not Robinhood Chain");
        require(address(FACTORY).code.length != 0 && TradingCalendar(CALENDAR).owner() == SAFE, "calendar");
        require(IFeed(USDG_FEED).decimals() == 8, "usdg feed decimals");
        Stock[12] memory s = stocks();

        // every input is checked before the first broadcast, so a wrong address stops the run with nothing spent
        for (uint256 i; i < s.length; i++) {
            require(IERC20Metadata(s[i].token).decimals() == 18, string.concat(s[i].sym, ": token decimals"));
            require(IFeed(s[i].feed).decimals() == 8, string.concat(s[i].sym, ": feed decimals"));
            (address listed,,,) = FACTORY.listings(s[i].token);
            require(listed == address(0), string.concat(s[i].sym, ": already listed"));
        }

        vm.startBroadcast();
        PriceOracle[12] memory o;
        for (uint256 i; i < s.length; i++) o[i] = new PriceOracle(s[i].token, s[i].feed, USDG_FEED, CALENDAR, MAX_STOCK_AGE, MAX_USDG_AGE);
        vm.stopBroadcast();

        console2.log("sym | oracle | feed description() | lastPriceAt (USDG per stock, 1e18) | feed age s | tryPrice ok");
        for (uint256 i; i < s.length; i++) {
            PriceOracle x = o[i];
            require(x.stock() == s[i].token && address(x.stockFeed()) == s[i].feed && address(x.usdgFeed()) == USDG_FEED
                && address(x.calendar()) == CALENDAR && x.maxStockAge() == MAX_STOCK_AGE && x.maxUsdgAge() == MAX_USDG_AGE, "read-back");
            (bool okAt, uint256 p, uint256 at) = x.lastPriceAt();
            (bool ok,) = x.tryPrice();
            console2.log(string.concat(s[i].sym, " | ", vm.toString(address(x)), " | ", IFeed(s[i].feed).description(), " | ",
                okAt ? vm.toString(p) : "none", " | ", okAt ? vm.toString(block.timestamp - at) : "-", " | ", ok ? "true" : "false"));
        }
    }
}
