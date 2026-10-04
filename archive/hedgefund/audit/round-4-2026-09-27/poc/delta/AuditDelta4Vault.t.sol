// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Vm} from "forge-std/Vm.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {SwapParams} from "v4-core/src/types/PoolOperation.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";
import {V2FactoryFixture} from "./utils/V2FactoryFixture.sol";
import {HedgeFunBondingCurve} from "../src/v2/HedgeFunBondingCurve.sol";
import {HedgeFunV2Treasury} from "../src/v2/HedgeFunV2Treasury.sol";
import {V2LiquidityVault} from "../src/v2/V2LiquidityVault.sol";

/// Round 4, delta lane: the M-1 fix in `V2LiquidityVault.collectFees` (0d9fca8) -- a stock leg the issuer
/// refuses is parked in `pendingStockFee` and retried through a `try this.creditPendingStock()` self-call.
/// Questions owned here: can the parked fee be lost, double-counted, griefed or used to block the token burn;
/// does the self-call guard hold; does the event stream still add up.
contract AuditDelta4Vault is V2FactoryFixture {
    using PoolIdLibrary for PoolKey;

    PoolSwapTest internal router;
    address internal trader = address(0x7A0);
    address internal outsider = address(0xBEEF);

    // the graduated set, kept in storage so the tests stay under the stack limit
    HedgeFunBondingCurve internal curve;
    PoolKey internal key;
    HedgeFunV2Treasury internal t;
    V2LiquidityVault internal vault;
    address internal token;

    function setUp() public {
        _setUpV2(18);
        router = new PoolSwapTest(pm);
    }

    // ------------------------------------------------------------------------------------------------ helpers

    function _buyFun(address who, uint256 stockIn, PoolKey memory key, address token) internal {
        bool stockIs0 = address(stock) < token;
        vm.startPrank(who);
        stock.approve(address(router), type(uint256).max);
        router.swap(key, SwapParams({zeroForOne: stockIs0, amountSpecified: -int256(stockIn),
            sqrtPriceLimitX96: stockIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        vm.stopPrank();
    }

    function _sellFun(address who, uint256 funIn, PoolKey memory key, address token) internal {
        bool stockIs0 = address(stock) < token;
        vm.startPrank(who);
        IERC20(token).approve(address(router), type(uint256).max);
        router.swap(key, SwapParams({zeroForOne: !stockIs0, amountSpecified: -int256(funIn),
            sqrtPriceLimitX96: !stockIs0 ? TickMath.MIN_SQRT_PRICE + 1 : TickMath.MAX_SQRT_PRICE - 1}),
            PoolSwapTest.TestSettings({takeClaims: false, settleUsingBurn: false}), "");
        vm.stopPrank();
    }

    /// One round trip so the position earns LP fees in BOTH currencies.
    function _accrue(PoolKey memory key, address token) internal {
        stock.mint(trader, 100e18);
        _buyFun(trader, 100e18, key, token);
        _sellFun(trader, IERC20(token).balanceOf(trader) / 2, key, token);
    }

    function _graduated() internal {
        (, curve, key) = _launchV2(true);
        _graduateV2(curve);
        t = HedgeFunV2Treasury(curve.treasury());
        vault = V2LiquidityVault(t.liquidityVault());
        token = curve.token();
        assertTrue(address(vault) != address(0), "vault wired at graduation");
    }

    function _sumStockCredited(Vm.Log[] memory logs, address emitter) internal pure returns (uint256 sum, uint256 n) {
        bytes32 sig = keccak256("FeesCollected(uint256,uint256)");
        for (uint256 i; i < logs.length; i++) {
            if (logs[i].emitter == emitter && logs[i].topics[0] == sig) {
                (uint256 s,) = abi.decode(logs[i].data, (uint256, uint256));
                sum += s; n++;
            }
        }
    }

    // ------------------------------------------------------------------------------------------------ tests

    /// A refused stock leg is parked, the token burn proceeds anyway (the M-1 coupling is gone), the parked
    /// amount accumulates across refused calls, and when the refusal lifts it is delivered EXACTLY once: the
    /// treasury's budget grows by precisely the sum the events report, and the vault is left empty.
    function test_parkedFeeIsDeliveredExactlyOnce_andTheEventStreamAddsUp() public {
        _graduated();
        uint256 budget0 = t.buybackStock();
        uint256 parked1;
        uint256 parked2;
        vm.recordLogs();

        // 1. the issuer refuses delivery to the treasury: stock parked, token burned
        {
            uint256 supply0 = IERC20(token).totalSupply();
            _accrue(key, token);
            stock.blockRecipient(address(t));
            (uint256 s1, uint256 b1) = vault.collectFees();
            assertEq(s1, 0, "stock leg parked, reported as 0");
            assertGt(b1, 0, "token leg burned regardless");
            parked1 = stock.balanceOf(address(vault));
            assertGt(parked1, 0, "the parked stock sits in the vault");
            assertEq(t.buybackStock(), budget0, "treasury not credited while blocked");
            assertEq(IERC20(token).totalSupply(), supply0 - b1, "burn is real");
        }
        // 2. more fees while still refused: the parked amount accumulates, the burn keeps going
        {
            _accrue(key, token);
            (uint256 s2, uint256 b2) = vault.collectFees();
            assertEq(s2, 0); assertGt(b2, 0);
            parked2 = stock.balanceOf(address(vault));
            assertGt(parked2, parked1, "accumulates");
            assertEq(t.buybackStock(), budget0, "still nothing credited");
        }
        // 3. the refusal lifts: one call delivers everything parked plus this call's own fee
        uint256 s3;
        {
            stock.blockRecipient(address(0));
            _accrue(key, token);
            uint256 b3;
            (s3, b3) = vault.collectFees();
            assertGt(s3, parked2, "delivered = parked remainder + the new fee");
            assertGt(b3, 0);
            assertEq(t.buybackStock(), budget0 + s3, "budget grew by exactly what was reported delivered");
            assertEq(stock.balanceOf(address(vault)), 0, "nothing left behind: no loss");
        }
        // 4. a further call finds no phantom remainder: no double count
        {
            (uint256 s4, uint256 b4) = vault.collectFees();
            assertEq(s4, 0); assertEq(b4, 0);
            assertEq(t.buybackStock(), budget0 + s3, "budget unchanged by an empty retry");
        }
        // 5. the FeesCollected stream sums to the budget delta: a consumer summing events is not misled
        (uint256 reported, uint256 n) = _sumStockCredited(vm.getRecordedLogs(), address(vault));
        assertEq(n, 4, "four collections");
        assertEq(reported, t.buybackStock() - budget0, "sum of stockToTreasury over events == stock actually credited");
        emit log_named_uint("parked after call 1", parked1);
        emit log_named_uint("parked after call 2", parked2);
        emit log_named_uint("delivered by call 3", s3);
    }

    /// A fee-on-transfer stock (the vault is the SENDER) trips InexactTransfer inside the self-call: also
    /// parked, also retried once the surcharge is gone, and the token burn is never held hostage.
    function test_feeOnTransferStockParksTooAndRecovers() public {
        _graduated();
        uint256 budget0 = t.buybackStock();
        _accrue(key, token);
        stock.taxSender(address(vault));
        (uint256 s1, uint256 b1) = vault.collectFees();
        assertEq(s1, 0, "surcharged transfer parked");
        assertGt(b1, 0, "burn proceeded");
        assertEq(t.buybackStock(), budget0, "the exactness check refused the short delivery: nothing credited");
        uint256 parked = stock.balanceOf(address(vault));
        assertGt(parked, 0);
        stock.taxSender(address(0));
        (uint256 s2,) = vault.collectFees();
        assertEq(s2, parked, "the whole parked amount, once");
        assertEq(t.buybackStock(), budget0 + parked);
        assertEq(stock.balanceOf(address(vault)), 0);
    }

    /// The 63/64 gas rule cannot be used to park the stock leg on purpose: at every gas budget the call either
    /// reverts whole or delivers the stock. (The inner leg needs ~1e5 gas; the tail after the try needs ~2e4;
    /// a partial outcome requires inner > 63 x tail, which is false here by a factor of ~10.)
    function test_gasStarvationCannotParkTheFee() public {
        _graduated();
        _accrue(key, token);
        bool sawPartial;
        uint256 minOk;
        uint256 maxFail;
        for (uint256 g = 40_000; g <= 600_000; g += 1_000) {
            uint256 snap = vm.snapshotState();
            try vault.collectFees{gas: g}() returns (uint256 s, uint256 b) {
                if (s == 0 && b > 0) sawPartial = true;
                if (minOk == 0) minOk = g;
            } catch {
                maxFail = g;
            }
            vm.revertToState(snap);
        }
        assertFalse(sawPartial, "no gas budget yields (stock parked, token burned)");
        assertGt(minOk, 0, "some budget succeeds");
        assertLt(maxFail, minOk, "success is monotone in gas: no partial window");
        emit log_named_uint("smallest succeeding gas budget", minOk);
        emit log_named_uint("largest failing gas budget", maxFail);
    }

    /// The self-call guard: nobody but the vault itself can drive `creditPendingStock`, parked fee or not --
    /// not an outsider, not the treasury, not the pool manager.
    function test_onlyTheVaultItselfCanRetry() public {
        _graduated();
        _accrue(key, token);
        stock.blockRecipient(address(t));
        vault.collectFees();
        assertGt(stock.balanceOf(address(vault)), 0, "a fee is parked");
        stock.blockRecipient(address(0));
        vm.prank(outsider); vm.expectRevert(V2LiquidityVault.Busy.selector); vault.creditPendingStock();
        vm.prank(address(t)); vm.expectRevert(V2LiquidityVault.Busy.selector); vault.creditPendingStock();
        vm.prank(address(pm)); vm.expectRevert(V2LiquidityVault.Busy.selector); vault.creditPendingStock();
        vm.prank(address(factory)); vm.expectRevert(V2LiquidityVault.Busy.selector); vault.creditPendingStock();
        assertGt(stock.balanceOf(address(vault)), 0, "still parked: nobody else could move it");
    }

    /// What is NOT fixed and cannot be by this design (round 3 said so): a vault the issuer blocklists fails
    /// inside V4's `take`, before either delivery leg exists, so BOTH legs revert together.
    function test_blocklistedVaultStillRevertsBothLegs() public {
        _graduated();
        _accrue(key, token);
        stock.blockRecipient(address(vault));
        vm.expectRevert();
        vault.collectFees();
    }

    /// There is no getter for the parked amount and no event names it: the only on-chain view of a parked fee
    /// is the vault's raw stock balance, which also counts donations (round 3's L-5).
    function test_parkedAmountIsOnlyObservableAsARawBalance() public {
        _graduated();
        _accrue(key, token);
        stock.blockRecipient(address(t));
        (uint256 reported,) = vault.collectFees();
        assertEq(reported, 0, "the event and return value say 0 while stock is parked");
        stock.mint(address(vault), 3e18);                 // a donation, indistinguishable from the parked fee
        uint256 raw = stock.balanceOf(address(vault));
        assertGt(raw, 3e18, "raw balance = parked fee + donation, with no way to split them on chain");
        // `pendingStockFee` is private: no selector exists for it
        (bool ok,) = address(vault).staticcall(abi.encodeWithSignature("pendingStockFee()"));
        assertFalse(ok, "no getter");
    }
}
