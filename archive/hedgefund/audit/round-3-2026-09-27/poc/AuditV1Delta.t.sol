// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {IUnlockCallback} from "v4-core/src/interfaces/callback/IUnlockCallback.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {ModifyLiquidityParams} from "v4-core/src/types/PoolOperation.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {HedgeFunFactory, TreasuryDeployer, TokenDeployer} from "../src/HedgeFunFactory.sol";
import {HedgeFunV2Factory} from "../src/v2/HedgeFunV2Factory.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";
import {HedgeFunHook} from "../src/hooks/HedgeFunHook.sol";
import {HedgeFunTreasuryBase} from "../src/HedgeFunTreasuryBase.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";

/// A contract with code that is NOT a V2LiquidityVault, used to prove the hook does not check what it is told.
contract NotAVault {
    uint256 public x;
    function poke() external { x++; }
}

contract AuditV1DeltaTest is V2FactoryFixture, IUnlockCallback {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    PoolKey internal _k;
    int256 internal _delta;

    function setUp() public { _setUpV2(18); }

    // ------------------------------------------------------------------ 1. lpFee on the V1 factory

    /// V1's `_minLpFee()/_maxLpFee()` both return 0, so the relaxed comparison is still `lpFee == 0`.
    function test_v1FactoryStillRefusesEveryNonZeroLpFee() public {
        HedgeFunFactory.Defaults memory d = _defaults();
        // the fixture's defaults carry lpFee = 3000, which only the V2 override accepts
        HedgeFunFactory v1 = new HedgeFunFactory(owner, address(pm), address(v3f), address(usdg), protocol,
            address(new TreasuryDeployer()), address(new TokenDeployer()), address(_deployHook(pm)), _zeroFeeDefaults());
        vm.startPrank(owner);
        for (uint24 f = 1; f <= 10; f++) {
            d = _zeroFeeDefaults(); d.lpFee = f;
            vm.expectRevert(HedgeFunFactory.BadRequest.selector);
            v1.setDefaults(d);
        }
        d = _zeroFeeDefaults(); d.lpFee = 100;   vm.expectRevert(HedgeFunFactory.BadRequest.selector); v1.setDefaults(d);
        d = _zeroFeeDefaults(); d.lpFee = 500;   vm.expectRevert(HedgeFunFactory.BadRequest.selector); v1.setDefaults(d);
        d = _zeroFeeDefaults(); d.lpFee = 3000;  vm.expectRevert(HedgeFunFactory.BadRequest.selector); v1.setDefaults(d);
        d = _zeroFeeDefaults(); d.lpFee = 8388608; vm.expectRevert(HedgeFunFactory.BadRequest.selector); v1.setDefaults(d);  // the dynamic-fee flag
        d = _zeroFeeDefaults(); d.lpFee = type(uint24).max; vm.expectRevert(HedgeFunFactory.BadRequest.selector); v1.setDefaults(d);
        d = _zeroFeeDefaults(); d.lpFee = 0; v1.setDefaults(d);                  // and zero still goes through
        vm.stopPrank();
        assertEq(v1.getDefaults().lpFee, 0, "V1 lpFee is still pinned at zero");
    }

    /// The V2 subclass is the thing that moved, and it moved to a bounded window.
    function test_v2FactoryAcceptsOnlyOneToThreeThousand() public {
        HedgeFunFactory.Defaults memory d = _defaults();
        vm.startPrank(owner);
        d.lpFee = 0;    vm.expectRevert(HedgeFunFactory.BadRequest.selector); factory.setDefaults(d);
        d.lpFee = 3001; vm.expectRevert(HedgeFunFactory.BadRequest.selector); factory.setDefaults(d);
        d.lpFee = 1;    factory.setDefaults(d);
        d.lpFee = 3000; factory.setDefaults(d);
        vm.stopPrank();
    }

    // ------------------------------------------------------------------ 2. the second seeder

    /// After graduation, the vault is the ONLY address the hook will let add liquidity -- the factory is out too.
    function test_afterGraduationNeitherFactoryNorStrangerMayAddLiquidity() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        address vault = hook.liquidityVaultOf(key.toId());
        assertTrue(vault != address(0) && vault != address(factory), "a second seeder exists");
        _k = key;
        _delta = 1e18;
        // a stranger
        vm.expectRevert();
        pm.unlock("");
        // the factory itself, which is the V1 seeder for every pool that has no vault
        vm.prank(address(factory));
        vm.expectRevert();
        pm.unlock("");
        assertEq(hook.liquidityVaultOf(key.toId()), vault, "the seeder cannot be moved");
    }

    /// `_onlySeed` is an exclusive-or: exactly one address per pool, and registration happens once.
    function test_aPoolCannotBeRegisteredTwiceNorThroughBothPaths() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        _graduateV2(curve);
        (, HedgeFunHook.Rates memory r) = factory.graduationConfig(0);
        address token = curve.token();
        address treasury = curve.treasury();
        address notAVault = address(new NotAVault());
        vm.startPrank(address(factory));
        vm.expectRevert(HedgeFunHook.AlreadyRegistered.selector);
        hook.register(key, token, address(stock), treasury, protocol, address(this), address(this), r);
        vm.expectRevert(HedgeFunHook.AlreadyRegistered.selector);
        hook.registerGraduated(key, token, address(stock), treasury, protocol, address(this), r);
        vm.expectRevert(HedgeFunHook.AlreadyRegistered.selector);
        hook.registerGraduatedWithVault(key, token, address(stock), treasury, protocol, address(this), r, notAVault);
        vm.stopPrank();
    }

    /// The hook validates NOTHING about the vault beyond `code.length != 0`.
    function test_theHookAcceptsAnyContractAsTheVault() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        (PoolKey memory key, HedgeFunHook.Rates memory r) = factory.graduationConfig(0);
        // a fresh, unrelated pool key on the same hook so registration is not already taken
        key.tickSpacing = 120;
        address stranger = address(new NotAVault());
        address freshTreasury = address(0xBEEF);
        address tok = curve.token();
        vm.prank(address(factory));
        hook.registerGraduatedWithVault(key, tok, address(stock), freshTreasury, protocol, address(this), r, stranger);
        assertEq(hook.liquidityVaultOf(key.toId()), stranger,
            "an EOA-owned contract with no locking property is now the pool's sole seeder");
        // and an address with no code is refused, which is the only test there is
        key.tickSpacing = 180;
        vm.prank(address(factory));
        vm.expectRevert(HedgeFunHook.BadConfig.selector);
        hook.registerGraduatedWithVault(key, tok, address(stock), address(0xCAFE), protocol, address(this), r, address(0xdead1234));
    }

    /// The launch-window exemption cannot be reached on a graduated pool.
    function test_graduatedPoolsCannotCarryASnipeWindow() public {
        (, HedgeFunBondingCurve curve, PoolKey memory key) = _launchV2(true);
        (, HedgeFunHook.Rates memory r) = factory.graduationConfig(0);
        assertEq(r.snipeBps, 0); assertEq(r.snipeSeconds, 0);
        _graduateV2(curve);
        assertEq(hook.buyRateBps(key.toId()), curve.taxBps(), "flat from the first block");
        // and the hook refuses to register one
        PoolKey memory k2 = key; k2.tickSpacing = 120;
        r.snipeBps = 100; r.snipeSeconds = 10;
        address tok2 = curve.token();
        vm.prank(address(factory));
        vm.expectRevert(HedgeFunHook.BadConfig.selector);
        hook.registerGraduated(k2, tok2, address(stock), address(0xF00D), protocol, address(this), r);
    }

    // ------------------------------------------------------------------ 4. the scorecard

    /// A bare stock transfer now moves the published numerator with the denominator standing still.
    function test_aStockDonationNowInflatesTheScorecardWithoutBeingBooked() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        _graduateV2(curve);
        HedgeFunTreasuryBase tr = HedgeFunTreasuryBase(curve.treasury());
        tr.book();
        (bool ok0, uint256 held0) = tr.stockEquivalentHeld();
        assertTrue(ok0);
        uint256 received0 = tr.totalStockReceived();
        uint256 unbooked0 = tr.unbookedStock();

        // a donation far below `minLotUsdg`, which `_book` will refuse for good
        uint256 dust = 1;   // one wei of stock
        stock.transfer(address(tr), dust);
        assertFalse(tr.book(), "a sub-lot donation can never be booked");
        (bool ok1, uint256 held1) = tr.stockEquivalentHeld();
        assertTrue(ok1);
        assertEq(tr.totalStockReceived(), received0, "the denominator did not move");
        assertEq(held1, held0 + dust, "but the numerator did, by the whole donation");
        assertEq(tr.unbookedStock(), unbooked0 + dust);

        // and a full lot-sized donation moves it too, until somebody calls the unpaid `book()`
        uint256 lot = 1e18;
        stock.transfer(address(tr), lot);
        (, uint256 held2) = tr.stockEquivalentHeld();
        assertEq(held2, held1 + lot, "counted before booking");
        assertTrue(tr.book());
        (, uint256 held3) = tr.stockEquivalentHeld();
        assertEq(held3, held2, "booking is numerator-neutral");
        assertEq(tr.totalStockReceived(), received0 + lot + dust, "and only booking moves the denominator");
    }

    /// The identity the new line establishes: the number is now exactly the stock balance plus USDG at the oracle.
    function test_scorecardIsNowTheWholeStockBalance() public {
        (, HedgeFunBondingCurve curve,) = _launchV2(true);
        _graduateV2(curve);
        HedgeFunTreasuryBase tr = HedgeFunTreasuryBase(curve.treasury());
        stock.transfer(address(tr), 3e18);
        tr.book();
        stock.transfer(address(tr), 7);
        (bool ok, uint256 p) = tr.health();
        assertTrue(ok);
        (, uint256 held) = tr.stockEquivalentHeld();
        assertEq(held, stock.balanceOf(address(tr)) + usdg.balanceOf(address(tr)) * 1e18 / p,
            "held == the entire stock balance + USDG marked at the oracle");
    }

    // ------------------------------------------------------------------ helpers

    function unlockCallback(bytes calldata) external returns (bytes memory) {
        pm.modifyLiquidity(_k, ModifyLiquidityParams({
            tickLower: TickMath.minUsableTick(_k.tickSpacing),
            tickUpper: TickMath.maxUsableTick(_k.tickSpacing),
            liquidityDelta: _delta, salt: bytes32(0)
        }), "");
        return "";
    }

    function _zeroFeeDefaults() internal pure returns (HedgeFunFactory.Defaults memory d) {
        d = _defaults();
        d.lpFee = 0;
    }

}
