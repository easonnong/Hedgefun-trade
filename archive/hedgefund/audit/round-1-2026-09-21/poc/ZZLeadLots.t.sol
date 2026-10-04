// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TreasuryV4Base} from "./StrategyTreasuryV4Unit.t.sol";
import {stdError} from "forge-std/StdError.sol";
import {StrategyTreasuryBase} from "../src/str/StrategyTreasuryBase.sol";

/// Lead's probe on the lot array: `_shrink` is swap-and-pop and `takeProfit`/`stopLoss` take the index from the
/// caller, so what does a caller actually get when the array moves under them?
contract ZZLeadLots is TreasuryV4Base {
    function stockIsCurrency0() internal pure override returns (bool) { return true; }

    address constant VICTIM = address(0x1C7114);

    /// Three lots at three different costs. The caller names index 2; another call closes index 0 first;
    /// index 2 no longer exists and the caller eats a panic, not a named error.
    function test_lead_aClosedLotTurnsSomeoneElsesIndexIntoAnOutOfBoundsPanic() public {
        _fundAndBook(10 ether);                       // lot 0, cost 100
        _fundAndBook(10 ether);                       // lot 1, cost 100
        _fundAndBook(10 ether);                       // lot 2, cost 100
        assertEq(treasury.lotCount(), 3);

        _px(111e18);                                  // past tp2 for all three
        vm.startPrank(bot);
        treasury.takeProfit(0);                       // sells half of lot 0
        treasury.takeProfit(0);                       // sells the rest: lot 2 is swapped into slot 0, array is now 2 long
        vm.stopPrank();
        assertEq(treasury.lotCount(), 2);

        // VICTIM's transaction was built when there were three lots and named the last one.
        vm.prank(VICTIM);
        vm.expectRevert(stdError.indexOOBError);      // panic 0x32, not a named error
        treasury.takeProfit(2);
    }

    /// The sharper version: the index still exists, but it is now a DIFFERENT lot with a different cost basis,
    /// and the call goes through.
    function test_lead_anIndexCanSilentlyBecomeADifferentLot() public {
        _fundAndBook(10 ether);                       // lot 0, cost 100
        _px(90e18); _fundAndBook(10 ether);           // lot 1, cost 90  -- cheaper basis
        _px(111e18);                                  // 111: +11% on lot 0, +23% on lot 1

        (, uint256 cost0Before,) = treasury.lots(0);
        assertEq(cost0Before, 100e18, "slot 0 starts as the 100-cost lot");

        // someone closes lot 0 out from under a pending takeProfit(0)
        vm.startPrank(bot);
        treasury.takeProfit(0);
        treasury.takeProfit(0);
        vm.stopPrank();

        (, uint256 cost0After,) = treasury.lots(0);
        assertEq(cost0After, 90e18, "slot 0 is now the 90-cost lot: swap-and-pop moved it here");

        // VICTIM still thinks slot 0 is the 100-cost lot. The call succeeds, on the other lot.
        uint256 before = stock.balanceOf(VICTIM);
        vm.prank(VICTIM); treasury.takeProfit(0);
        assertGt(stock.balanceOf(VICTIM), before, "paid a bounty on a lot the caller never chose");
    }

    /// Negative result, recorded so the next round does not re-derive it: a lot can never reach 1 wei, so the
    /// `q = L.qty / 2 == 0` path in `takeProfit` is not reachable.
    function test_lead_aOneWeiLotCannotBeBooked_soTheHalfEqualsZeroPathIsUnreachable() public {
        stock.mint(address(treasury), 1);                       // one wei of stock
        assertFalse(treasury.book(), "book must refuse: _ruleValue(1, p) rounds to 0, under minLotUsdg");
        assertEq(treasury.lotCount(), 0);
        // and the smallest lot book() WILL take is already far above 1 wei
        stock.mint(address(treasury), 0.05 ether - 2);          // total is now 5e16 - 1: one wei under the floor
        assertFalse(treasury.book(), "still under the floor");
        stock.mint(address(treasury), 1);                       // total 5e16 exactly
        assertTrue(treasury.book(), "exactly at the floor it books");
        (uint256 qty,,) = treasury.lots(0);
        assertEq(qty, 0.05 ether, "the smallest bookable lot is 5e16 wei, not 1");
    }
}
