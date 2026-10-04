// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {BrokerEpochVault} from "../src/options/BrokerEpochVault.sol";
import {PriceOracle} from "../src/PriceOracle.sol";

contract BrokerTestToken is ERC20 {
    uint8 private _decimals;
    mapping(address => bool) public frozen;
    uint256 public uiMultiplier = 1e18;

    constructor(string memory symbol_, uint8 decimals_) ERC20(symbol_, symbol_) {
        _decimals = decimals_;
    }

    function decimals() public view override returns (uint8) {
        return _decimals;
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }

    function freeze(address to, bool value) external {
        frozen[to] = value;
    }

    function setMultiplier(uint256 value) external {
        uiMultiplier = value;
    }

    function _update(address from, address to, uint256 amount) internal override {
        require(!frozen[from] && !frozen[to], "frozen");
        super._update(from, to, amount);
    }
}

contract BrokerTestOracle {
    address public stock;
    uint256 public value = 200e18;
    bool public healthy = true;

    constructor(address stock_) {
        stock = stock_;
    }

    function set(uint256 value_, bool healthy_) external {
        value = value_;
        healthy = healthy_;
    }

    function price() external view returns (uint256) {
        require(healthy, "stale");
        return value;
    }
}

contract BrokerEpochVaultTest is Test {
    BrokerEpochVault internal vault;
    BrokerTestToken internal stock;
    BrokerTestToken internal usdg;
    BrokerTestOracle internal oracle;
    address internal alice = makeAddr("alice");
    address internal bob = makeAddr("bob");
    address internal operator = makeAddr("broker-operator");
    address internal reviewer = makeAddr("independent-reviewer");
    address internal recipient = makeAddr("fixed-settlement-recipient");
    bytes32 internal constant EVIDENCE = keccak256("test-only-closed-broker-report");

    function setUp() public {
        vm.warp(1_790_000_000);
        stock = new BrokerTestToken("NVDA", 18);
        usdg = new BrokerTestToken("USDG", 6);
        oracle = new BrokerTestOracle(address(stock));
        vault = new BrokerEpochVault(
            address(this),
            IERC20(address(stock)),
            IERC20(address(usdg)),
            PriceOracle(address(oracle)),
            operator,
            reviewer,
            recipient
        );
        vault.setEligible(alice, true);
        vault.setEligible(bob, true);
        stock.mint(alice, 10_000 ether);
        stock.mint(bob, 10_000 ether);
        usdg.mint(operator, 1_000_000e6);
        vm.prank(alice);
        stock.approve(address(vault), type(uint256).max);
        vm.prank(bob);
        stock.approve(address(vault), type(uint256).max);
        vm.prank(operator);
        usdg.approve(address(vault), type(uint256).max);
    }

    function _deposit(address user, uint256 amount) internal {
        vm.prank(user);
        vault.requestDeposit(amount);
    }

    function _seed() internal {
        _deposit(alice, 100 ether);
        vault.processQueues();
    }

    function _lock() internal {
        uint256 amount = vault.activeStock();
        vm.prank(operator);
        vault.lockEpoch(amount, 220e18, 200e6, uint64(block.timestamp + 7 days), keccak256("NVDA-CALL-220"));
    }

    function _fill() internal {
        uint256 amount = vault.activeStock();
        vm.prank(operator);
        vault.recordExecution(keccak256("actual-fill"), amount, 200e6);
    }

    function _proposal(int256 pnl) internal returns (bytes32 digest) {
        BrokerEpochVault.Epoch memory e = vault.getEpoch(vault.currentEpoch());
        vm.warp(e.expiry + 1);
        vm.prank(operator);
        vault.proposeSettlement(pnl, uint64(block.timestamp), EVIDENCE);
        (,,,, digest) = vault.report();
    }

    function _confirm(bytes32 digest) internal {
        vm.warp(block.timestamp + vault.REVIEW_DELAY());
        vm.prank(reviewer);
        vault.confirmSettlement(digest);
    }

    function _backed() internal view {
        assertEq(stock.balanceOf(address(vault)), vault.activeStock() + vault.pendingStock() + vault.reservedStock());
        assertEq(usdg.balanceOf(address(vault)), vault.rewardReserve() + vault.reportFunding());
        assertLe(vault.totalRewardsClaimed(), vault.totalRewardsFunded());
    }

    function test_midweekExitIsOnlyARequestAndExpiryAloneDoesNotUnlock() public {
        _seed();
        _lock();
        _fill();
        vm.prank(alice);
        vault.requestRedeem(100 ether);
        vm.expectRevert(BrokerEpochVault.WrongPhase.selector);
        vault.processQueues();
        vm.expectRevert(BrokerEpochVault.BadAmount.selector);
        vm.prank(alice);
        vault.claimStock(alice);
        vm.warp(block.timestamp + 30 days);
        vm.expectRevert(BrokerEpochVault.WrongPhase.selector);
        vault.processQueues();
        assertEq(vault.activeStock(), 100 ether);
    }

    function test_withdrawalsReservedBeforeNextBrokerLock() public {
        _seed();
        vm.prank(alice);
        vault.requestRedeem(40 ether);
        vm.prank(operator);
        vault.lockEpoch(60 ether, 220e18, 200e6, uint64(block.timestamp + 7 days), EVIDENCE);
        assertEq(vault.claimableStock(alice), 40 ether);
        assertEq(vault.getEpoch(1).maxCoveredStock, 60 ether);
        vm.prank(alice);
        vault.claimStock(alice);
        assertEq(vault.activeStock(), 60 ether);
        _backed();
    }

    function test_lateDepositDoesNotReceiveOldProfitAndExiterStillDoes() public {
        _seed();
        _lock();
        _fill();
        _deposit(bob, 100 ether);
        vm.prank(alice);
        vault.requestRedeem(100 ether);
        bytes32 digest = _proposal(200e6);
        assertEq(vault.claimableRewards(alice), 0); // report funding is not yet earnings
        _confirm(digest);
        assertEq(vault.balanceOf(bob), 100 ether);
        assertEq(vault.claimableRewards(bob), 0);
        assertEq(vault.claimableRewards(alice), 200e6);
        assertEq(vault.claimableStock(alice), 100 ether);
        vm.prank(alice);
        vault.claimRewards(alice);
        vm.prank(alice);
        vault.claimStock(alice);
        assertEq(usdg.balanceOf(alice), 200e6);
        _backed();
    }

    function test_lossChargesOldCohortAndNewSharesUsePostLossRatio() public {
        _seed();
        _lock();
        _fill();
        _deposit(bob, 100 ether);
        vm.prank(alice);
        vault.requestRedeem(50 ether);
        bytes32 digest = _proposal(-3_000e6);
        oracle.set(300e18, true);
        _confirm(digest);
        assertEq(stock.balanceOf(recipient), 10 ether);
        assertEq(vault.claimableStock(alice), 45 ether);
        assertEq(vault.activeStock(), 145 ether);
        assertEq(vault.balanceOf(bob), uint256(100 ether) * 50 / 45);
        assertEq(vault.cumulativeOptionPnl(), -3_000e6);
        _backed();
    }

    function test_positiveReportMustActuallyTransferUSDG() public {
        _seed();
        _lock();
        _fill();
        vm.prank(operator);
        usdg.approve(address(vault), 0);
        BrokerEpochVault.Epoch memory e = vault.getEpoch(vault.currentEpoch());
        vm.warp(e.expiry + 1);
        vm.expectRevert();
        vm.prank(operator);
        vault.proposeSettlement(200e6, uint64(block.timestamp), EVIDENCE);
        assertEq(uint256(vault.phase()), uint256(BrokerEpochVault.Phase.Locked));
        assertEq(vault.reportFunding(), 0);
    }

    function test_operatorCannotSelfApproveAndReviewerMustWait() public {
        _seed();
        _lock();
        _fill();
        bytes32 digest = _proposal(200e6);
        vm.expectRevert(BrokerEpochVault.Unauthorized.selector);
        vm.prank(operator);
        vault.confirmSettlement(digest);
        vm.expectRevert(BrokerEpochVault.TooEarly.selector);
        vm.prank(reviewer);
        vault.confirmSettlement(digest);
        _confirm(digest);
        vm.expectRevert(BrokerEpochVault.InvalidReport.selector);
        vm.prank(reviewer);
        vault.confirmSettlement(digest);
    }

    function test_rejectionRefundsOnlyReportFundingAndInvalidatesOldDigest() public {
        _seed();
        _lock();
        _fill();
        bytes32 oldDigest = _proposal(100e6);
        vm.prank(reviewer);
        vault.rejectSettlement(oldDigest);
        assertEq(usdg.balanceOf(operator), 1_000_000e6);
        vm.prank(operator);
        vault.proposeSettlement(200e6, uint64(block.timestamp), EVIDENCE);
        (,,,, bytes32 digest) = vault.report();
        assertTrue(digest != oldDigest);
        vm.warp(block.timestamp + vault.REVIEW_DELAY());
        vm.expectRevert(BrokerEpochVault.InvalidReport.selector);
        vm.prank(reviewer);
        vault.confirmSettlement(oldDigest);
        vm.prank(reviewer);
        vault.confirmSettlement(digest);
        _backed();
    }

    function test_failedOrderRequiresTwoAttestorsToRelease() public {
        _seed();
        _lock();
        vm.prank(alice);
        vault.requestRedeem(100 ether);
        vm.prank(operator);
        vault.proposeSettlement(0, uint64(block.timestamp), EVIDENCE);
        (,,,, bytes32 digest) = vault.report();
        _confirm(digest);
        assertEq(vault.claimableStock(alice), 100 ether);
        assertEq(vault.totalSupply(), 0);
        _backed();
    }

    function test_recordedTradeCannotUseEarlyNoTradeAbort() public {
        _seed();
        _lock();
        _fill();
        vm.expectRevert(BrokerEpochVault.TooEarly.selector);
        vm.prank(operator);
        vault.proposeSettlement(0, uint64(block.timestamp), EVIDENCE);
    }

    function test_pendingCapitalCannotSupportAnOversizedTrade() public {
        _seed();
        _lock();
        _deposit(bob, 100 ether);
        vm.expectRevert(BrokerEpochVault.BadTerms.selector);
        vm.prank(operator);
        vault.recordExecution(EVIDENCE, 101 ether, 200e6);
    }

    function test_lossCannotConsumePendingCapitalOrEntireStockBacking() public {
        _seed();
        _lock();
        _fill();
        _deposit(bob, 100 ether);
        bytes32 digest = _proposal(-20_000e6);
        vm.warp(block.timestamp + vault.REVIEW_DELAY());
        vm.expectRevert(BrokerEpochVault.UnsafeAssets.selector);
        vm.prank(reviewer);
        vault.confirmSettlement(digest);
        assertEq(vault.pendingStock(), 100 ether);
        assertEq(vault.activeStock(), 100 ether);
    }

    function test_staleOracleCannotPriceStockReimbursement() public {
        _seed();
        _lock();
        _fill();
        bytes32 digest = _proposal(-1_000e6);
        oracle.set(200e18, false);
        vm.warp(block.timestamp + vault.REVIEW_DELAY());
        vm.expectRevert("stale");
        vm.prank(reviewer);
        vault.confirmSettlement(digest);
        assertEq(vault.activeStock(), 100 ether);
    }

    function test_onlyOTMCallsWithinTenorAllowed() public {
        _seed();
        vm.expectRevert(BrokerEpochVault.BadTerms.selector);
        vm.prank(operator);
        vault.lockEpoch(100 ether, 200e18, 200e6, uint64(block.timestamp + 7 days), EVIDENCE);
        vm.expectRevert(BrokerEpochVault.BadTerms.selector);
        vm.prank(operator);
        vault.lockEpoch(100 ether, 220e18, 200e6, uint64(block.timestamp + 10 days), EVIDENCE);
    }

    function test_pausedOrIneligibleUsersCanStillExitAndCancelPending() public {
        _seed();
        _lock();
        _fill();
        _deposit(bob, 100 ether);
        vault.setPaused(true);
        vault.setEligible(alice, false);
        vm.prank(bob);
        vault.cancelDeposit(100 ether);
        vm.prank(alice);
        vault.requestRedeem(100 ether);
        _confirm(_proposal(200e6));
        vm.prank(alice);
        vault.claimStock(alice);
        vm.prank(alice);
        vault.claimRewards(alice);
        _backed();
    }

    function test_nonTransferableSharesCannotBypassQueue() public {
        _seed();
        _lock();
        vm.expectRevert(BrokerEpochVault.NonTransferable.selector);
        vm.prank(alice);
        vault.transfer(bob, 1 ether);
    }

    function test_failedClaimPreservesClaimAndCanUseAnotherRecipient() public {
        _seed();
        vm.prank(alice);
        vault.requestRedeem(100 ether);
        vault.processQueues();
        stock.freeze(alice, true);
        vm.expectRevert("frozen");
        vm.prank(alice);
        vault.claimStock(alice);
        assertEq(vault.claimableStock(alice), 100 ether);
        vm.prank(alice);
        vault.claimStock(bob);
        _backed();
    }

    function test_donationsCannotInflateSharePriceOrCandidateTVL() public {
        stock.mint(address(vault), 999 ether);
        usdg.mint(address(vault), 999e6);
        _seed();
        assertEq(vault.balanceOf(alice), 100 ether);
        (uint256 s, uint256 u) = vault.managedBalances();
        assertEq(s, 100 ether);
        assertEq(u, 0);
    }

    function test_twoEpochsDoNotRepayOldRewardsOrDiluteNewDeposits() public {
        _seed();
        _lock();
        _fill();
        _deposit(bob, 100 ether);
        _confirm(_proposal(200e6));
        vm.prank(alice);
        vault.claimRewards(alice);
        _lock();
        _fill();
        _confirm(_proposal(200e6));
        assertEq(vault.claimableRewards(alice), 100e6);
        assertEq(vault.claimableRewards(bob), 100e6);
        vm.prank(alice);
        vault.claimRewards(alice);
        vm.prank(bob);
        vault.claimRewards(bob);
        assertEq(vault.totalRewardsClaimed(), 400e6);
        _backed();
    }

    function testFuzz_cohortConservation(uint96 a, uint96 b, uint64 profit, uint96 exitShares) public {
        uint256 amountA = bound(uint256(a), 1 ether, 1_000 ether);
        uint256 amountB = bound(uint256(b), 1 ether, 1_000 ether);
        uint256 pnl = bound(uint256(profit), 1, 200e6);
        _deposit(alice, amountA);
        vault.processQueues();
        _lock();
        _fill();
        _deposit(bob, amountB);
        uint256 exiting = bound(uint256(exitShares), 1, amountA);
        vm.prank(alice);
        vault.requestRedeem(exiting);
        _confirm(_proposal(int256(pnl)));
        assertEq(vault.claimableRewards(bob), 0);
        assertLe(vault.claimableRewards(alice), pnl);
        assertEq(vault.claimableStock(alice), exiting);
        assertEq(vault.activeStock(), amountA - exiting + amountB);
        _backed();
    }

    function test_zeroTokenMultiplierCannotLock() public {
        _seed();
        stock.setMultiplier(0);
        vm.expectRevert(BrokerEpochVault.BadTerms.selector);
        vm.prank(operator);
        vault.lockEpoch(100 ether, 220e18, 200e6, uint64(block.timestamp + 7 days), EVIDENCE);
    }

    function test_oldReservedStockAndRewardsRemainClaimableDuringNewLoss() public {
        _seed();
        _lock();
        _fill();
        vm.prank(alice);
        vault.requestRedeem(40 ether);
        _confirm(_proposal(200e6));
        _lock();
        _fill();
        _confirm(_proposal(-1_000e6));
        assertEq(vault.activeStock(), 55 ether);
        assertEq(vault.claimableStock(alice), 40 ether);
        assertEq(vault.claimableRewards(alice), 200e6);
        vm.prank(alice);
        vault.claimStock(alice);
        vm.prank(alice);
        vault.claimRewards(alice);
        _backed();
    }

    function test_fullQueuesSettleWithinBoundedGasWithoutExternalUserTransfers() public {
        for (uint160 i = 1; i <= 64; ++i) {
            address user = address(1000 + i);
            vault.setEligible(user, true);
            stock.mint(user, 2 ether);
            vm.prank(user);
            stock.approve(address(vault), 2 ether);
            _deposit(user, 1 ether);
        }
        vm.expectRevert(BrokerEpochVault.QueueFull.selector);
        vm.prank(alice);
        vault.requestDeposit(1 ether);
        vault.processQueues();
        _lock();
        _fill();
        for (uint160 i = 1; i <= 64; ++i) {
            address user = address(1000 + i);
            vm.prank(user);
            vault.requestRedeem(1 ether);
            _deposit(user, 1 ether);
            stock.freeze(user, true); // Processing reserves claims; it does not push to frozen users.
        }
        bytes32 digest = _proposal(200e6);
        uint256 beforeGas = gasleft();
        _confirm(digest);
        uint256 used = beforeGas - gasleft();
        emit log_named_uint("full queue settlement gas", used);
        assertLt(used, 15_000_000);
        assertEq(vault.totalSupply(), 64 ether);
        assertEq(vault.activeStock(), 64 ether);
        assertEq(vault.reservedStock(), 64 ether);
        _backed();
    }
}
