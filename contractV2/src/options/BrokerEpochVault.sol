// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {PriceOracle} from "../PriceOracle.sol";

interface IBrokerStockControls {
    function uiMultiplier() external view returns (uint256);
}

/// @notice Experimental, broker-executed covered-call vault; NOT a broker connector or proof of broker solvency.
/// Shares claim the remaining stock. Positive, settled option PnL is separately claimable in USDG.
/// Negative option PnL reimburses the fixed settlement recipient IN STOCK at a fresh oracle price.
/// Operator and reviewer are trusted to attest complete broker fills, costs, assignments and zero residual exposure.
/// Evidence hashes commit to reports; they do not prove their truth. No automatic unlock at expiry or admin sweep.
/// A failed/ineligible broker account or unavailable attestors can delay withdrawals indefinitely.
contract BrokerEpochVault is ERC20, Ownable2Step, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 public constant INDEX_SCALE = 1e36;
    uint256 public constant VALUE_SCALE = 1e30; // 18d stock * 18d price => 6d USDG
    uint256 public constant MIN_AMOUNT = 1e12;
    uint256 public constant MAX_STOCK = 1e30;
    uint256 public constant MAX_SHARES = 1e36;
    uint256 public constant MAX_USDG = 1e24;
    uint256 public constant MAX_QUEUE = 64;
    uint256 public constant REVIEW_DELAY = 1 hours;
    uint256 public constant MIN_TENOR = 12 hours;
    uint256 public constant MAX_TENOR = 9 days;

    enum Phase {
        Collecting,
        Locked,
        Reviewing
    }

    struct Epoch {
        uint64 lockedAt;
        uint64 expiry;
        uint64 settledAt;
        uint256 stockAtLock;
        uint256 sharesAtLock;
        uint256 maxCoveredStock;
        uint256 strike; // 1e18 USDG per TOKEN, not necessarily per broker share
        uint256 minPremium; // 6d USDG for maxCoveredStock
        uint256 stockMultiplier;
        bytes32 instructionHash;
        bytes32 executionHash;
        uint256 filledStock;
        uint256 grossPremium;
        int256 netPnl;
        uint256 stockDebit;
        uint256 debitPrice;
        bytes32 settlementHash;
    }

    struct Report {
        int256 netPnl; // after broker close/assignment costs; excludes operator margin principal
        uint64 closedAt;
        uint64 proposedAt;
        bytes32 evidenceHash;
        bytes32 digest;
    }

    IERC20 public immutable stock;
    IERC20 public immutable usdg;
    PriceOracle public immutable oracle;
    address public immutable operator;
    address public immutable reviewer;
    address public immutable settlementRecipient;
    Phase public phase;
    bool public paused;
    uint256 public currentEpoch = 1;
    uint256 public reportNonce;
    uint256 public activeStock;
    uint256 public pendingStock;
    uint256 public reservedStock;
    uint256 public rewardReserve;
    uint256 public reportFunding;
    uint256 public rewardIndex;
    uint256 public totalRewardsFunded;
    uint256 public totalRewardsClaimed;
    int256 public cumulativeOptionPnl;
    mapping(uint256 => Epoch) private _epochs;
    Report public report;
    mapping(address => bool) public eligible;
    mapping(address => uint256) public pendingDeposit;
    mapping(address => uint256) public pendingRedeem;
    mapping(address => uint256) public claimableStock;
    mapping(address => uint256) public rewardCredits;
    mapping(address => uint256) public rewardCheckpoint;
    mapping(address => uint256) private _rewardRemainder;
    address[] private _depositors;
    address[] private _redeemers;
    mapping(address => bool) private _depositQueued;
    mapping(address => bool) private _redeemQueued;

    event EligibilitySet(address indexed account, bool allowed);
    event PauseSet(bool paused);
    event DepositRequested(uint256 indexed epoch, address indexed account, uint256 stockAmount);
    event DepositCancelled(address indexed account, uint256 stockAmount);
    event DepositActivated(uint256 indexed epoch, address indexed account, uint256 stockAmount, uint256 shares);
    event RedeemRequested(uint256 indexed epoch, address indexed account, uint256 shares);
    event RedeemCancelled(address indexed account, uint256 shares);
    event RedeemReserved(uint256 indexed epoch, address indexed account, uint256 shares, uint256 stockAmount);
    event StockClaimed(address indexed account, address indexed recipient, uint256 amount);
    event RewardsClaimed(address indexed account, address indexed recipient, uint256 amount);
    event EpochLocked(
        uint256 indexed epoch,
        uint256 stockAmount,
        uint256 coveredStock,
        uint256 strike,
        uint64 expiry,
        bytes32 instructionHash
    );
    event ExecutionRecorded(uint256 indexed epoch, bytes32 executionHash, uint256 filledStock, uint256 grossPremium);
    event SettlementProposed(
        uint256 indexed epoch, bytes32 indexed digest, int256 netPnl, bytes32 evidenceHash, uint256 reviewAfter
    );
    event SettlementRejected(uint256 indexed epoch, bytes32 digest);
    event EpochSettled(
        uint256 indexed epoch, bytes32 indexed digest, int256 netPnl, uint256 stockDebit, uint256 debitPrice
    );

    error Unauthorized();
    error WrongPhase();
    error BadConfiguration();
    error BadAmount();
    error BadTerms();
    error QueueFull();
    error NotEligible();
    error Paused();
    error TooEarly();
    error InvalidReport();
    error UnsafeAssets();
    error NonTransferable();

    constructor(
        address owner_,
        IERC20 stock_,
        IERC20 usdg_,
        PriceOracle oracle_,
        address operator_,
        address reviewer_,
        address recipient_
    ) ERC20("Hedgefun Broker NVDA", "bNVDA") Ownable(owner_) {
        if (
            address(stock_) == address(0) || address(usdg_) == address(0) || address(stock_) == address(usdg_)
                || address(oracle_) == address(0) || operator_ == address(0) || reviewer_ == address(0)
                || operator_ == reviewer_ || recipient_ == address(0) || recipient_ == address(this)
                || IERC20Metadata(address(stock_)).decimals() != 18 || IERC20Metadata(address(usdg_)).decimals() != 6
                || oracle_.stock() != address(stock_)
        ) revert BadConfiguration();
        stock = stock_;
        usdg = usdg_;
        oracle = oracle_;
        operator = operator_;
        reviewer = reviewer_;
        settlementRecipient = recipient_;
    }

    function setEligible(address account, bool allowed) external onlyOwner {
        if (account == address(0)) revert BadConfiguration();
        eligible[account] = allowed;
        emit EligibilitySet(account, allowed);
    }

    /// Pausing stops new risk, but not pending-deposit refunds, settlement or exits.
    function setPaused(bool value) external onlyOwner {
        paused = value;
        emit PauseSet(value);
    }

    function renounceOwnership() public pure override {
        revert Unauthorized();
    }

    function getEpoch(uint256 epoch) external view returns (Epoch memory) {
        return _epochs[epoch];
    }

    /// Candidate TVL inputs. Excludes unsolicited donations, unaccepted report funding and broker assets.
    /// This is gross on-chain custody, NOT live NAV while an option position is open.
    function managedBalances() external view returns (uint256 stockAmount, uint256 usdgAmount) {
        return (activeStock + pendingStock + reservedStock, rewardReserve);
    }

    function claimableRewards(address account) public view returns (uint256) {
        uint256 delta = rewardIndex - rewardCheckpoint[account];
        uint256 amount = Math.mulDiv(balanceOf(account), delta, INDEX_SCALE);
        uint256 rem = mulmod(balanceOf(account), delta, INDEX_SCALE) + _rewardRemainder[account];
        return rewardCredits[account] + amount + rem / INDEX_SCALE;
    }

    /// Pending deposits never collateralize this epoch, and can always be cancelled.
    function requestDeposit(uint256 amount) external nonReentrant {
        if (paused) revert Paused();
        if (!eligible[msg.sender]) revert NotEligible();
        if (amount < MIN_AMOUNT || activeStock + pendingStock + reservedStock + amount > MAX_STOCK) revert BadAmount();
        if (!_depositQueued[msg.sender]) {
            if (_depositors.length == MAX_QUEUE) revert QueueFull();
            _depositQueued[msg.sender] = true;
            _depositors.push(msg.sender);
        }
        _pullExact(stock, msg.sender, amount);
        pendingDeposit[msg.sender] += amount;
        pendingStock += amount;
        emit DepositRequested(currentEpoch, msg.sender, amount);
    }

    function cancelDeposit(uint256 amount) external nonReentrant {
        if (amount == 0 || amount > pendingDeposit[msg.sender]) revert BadAmount();
        pendingDeposit[msg.sender] -= amount;
        pendingStock -= amount;
        _pushExact(stock, msg.sender, amount);
        emit DepositCancelled(msg.sender, amount);
    }

    /// Shares remain exposed until settlement; a request never snapshots an earlier price or avoids a loss.
    function requestRedeem(uint256 shares) external nonReentrant {
        if (shares == 0 || pendingRedeem[msg.sender] + shares > balanceOf(msg.sender)) revert BadAmount();
        if (!_redeemQueued[msg.sender]) {
            if (_redeemers.length == MAX_QUEUE) revert QueueFull();
            _redeemQueued[msg.sender] = true;
            _redeemers.push(msg.sender);
        }
        pendingRedeem[msg.sender] += shares;
        emit RedeemRequested(currentEpoch, msg.sender, shares);
    }

    function cancelRedeem(uint256 shares) external nonReentrant {
        if (shares == 0 || shares > pendingRedeem[msg.sender]) revert BadAmount();
        pendingRedeem[msg.sender] -= shares;
        emit RedeemCancelled(msg.sender, shares);
    }

    /// Between epochs anybody can process queues. No caller can do so once capital has been locked.
    function processQueues() external nonReentrant {
        if (phase != Phase.Collecting) revert WrongPhase();
        _processQueues();
    }

    /// MUST be confirmed on-chain before any broker order is submitted. All existing exits are reserved first.
    function lockEpoch(uint256 coveredStock, uint256 strike, uint256 minPremium, uint64 expiry, bytes32 instructionHash)
        external
        nonReentrant
    {
        if (msg.sender != operator) revert Unauthorized();
        if (paused) revert Paused();
        if (phase != Phase.Collecting) revert WrongPhase();
        _processQueues();
        if (
            coveredStock == 0 || coveredStock > activeStock || totalSupply() == 0 || instructionHash == bytes32(0)
                || minPremium == 0 || minPremium > MAX_USDG || expiry < block.timestamp + MIN_TENOR
                || expiry > block.timestamp + MAX_TENOR || strike <= oracle.price()
        ) revert BadTerms();
        Epoch storage e = _epochs[currentEpoch];
        e.lockedAt = uint64(block.timestamp);
        e.expiry = expiry;
        e.stockAtLock = activeStock;
        e.sharesAtLock = totalSupply();
        e.maxCoveredStock = coveredStock;
        e.strike = strike;
        e.minPremium = minPremium;
        e.stockMultiplier = IBrokerStockControls(address(stock)).uiMultiplier();
        if (e.stockMultiplier == 0) revert BadTerms();
        e.instructionHash = instructionHash;
        phase = Phase.Locked;
        emit EpochLocked(currentEpoch, activeStock, coveredStock, strike, expiry, instructionHash);
    }

    /// One aggregate fill report per epoch; any partial fills must be consolidated by the broker executor.
    /// The report must refer to the committed single call, with no live remainder orders left behind.
    function recordExecution(bytes32 executionHash, uint256 filledStock, uint256 grossPremium) external {
        if (msg.sender != operator) revert Unauthorized();
        if (phase != Phase.Locked) revert WrongPhase();
        Epoch storage e = _epochs[currentEpoch];
        if (
            e.executionHash != bytes32(0) || executionHash == bytes32(0) || filledStock == 0
                || filledStock > e.maxCoveredStock || grossPremium > MAX_USDG
                || grossPremium < Math.mulDiv(e.minPremium, filledStock, e.maxCoveredStock, Math.Rounding.Ceil)
        ) revert BadTerms();
        e.executionHash = executionHash;
        e.filledStock = filledStock;
        e.grossPremium = grossPremium;
        emit ExecutionRecorded(currentEpoch, executionHash, filledStock, grossPremium);
    }

    /// netPnl=0 with no recorded execution is a dual-attested no-trade abort, not a timed escape hatch.
    /// Positive PnL MUST be prefunded here before review. An API balance or bank transfer promise is insufficient.
    function proposeSettlement(int256 netPnl, uint64 closedAt, bytes32 evidenceHash) external nonReentrant {
        if (msg.sender != operator) revert Unauthorized();
        if (phase != Phase.Locked) revert WrongPhase();
        Epoch storage e = _epochs[currentEpoch];
        if (
            netPnl > int256(MAX_USDG) || netPnl < -int256(MAX_USDG) || evidenceHash == bytes32(0)
                || closedAt < e.lockedAt || closedAt > block.timestamp
        ) revert InvalidReport();
        if (e.executionHash == bytes32(0)) {
            if (netPnl != 0) revert InvalidReport();
        } else {
            if (block.timestamp < e.expiry) revert TooEarly();
            if (netPnl > int256(e.grossPremium)) revert InvalidReport();
        }
        bytes32 digest = keccak256(
            abi.encode(
                block.chainid,
                address(this),
                currentEpoch,
                ++reportNonce,
                e.instructionHash,
                e.executionHash,
                netPnl,
                closedAt,
                evidenceHash
            )
        );
        report = Report(netPnl, closedAt, uint64(block.timestamp), evidenceHash, digest);
        phase = Phase.Reviewing;
        if (netPnl > 0) {
            reportFunding = uint256(netPnl);
            _pullExact(usdg, operator, reportFunding);
        }
        _checkBacking();
        emit SettlementProposed(currentEpoch, digest, netPnl, evidenceHash, block.timestamp + REVIEW_DELAY);
    }

    function rejectSettlement(bytes32 digest) external nonReentrant {
        if (msg.sender != operator && msg.sender != reviewer) revert Unauthorized();
        if (phase != Phase.Reviewing || report.digest != digest) revert InvalidReport();
        uint256 refund = reportFunding;
        delete report;
        reportFunding = 0;
        phase = Phase.Locked;
        if (refund != 0) _pushExact(usdg, operator, refund);
        emit SettlementRejected(currentEpoch, digest);
    }

    /// Reviewer must independently check fills, cancelled orders, zero option/assigned-stock exposure, costs,
    /// and settlement of cash. Solidity cannot establish any of those facts about IBKR/Alpaca.
    function confirmSettlement(bytes32 digest) external nonReentrant {
        if (msg.sender != reviewer) revert Unauthorized();
        if (phase != Phase.Reviewing || report.digest != digest) revert InvalidReport();
        if (block.timestamp < uint256(report.proposedAt) + REVIEW_DELAY) revert TooEarly();
        _checkBacking();
        Epoch storage e = _epochs[currentEpoch];
        int256 pnl = report.netPnl;
        uint256 debit;
        uint256 debitPrice;
        if (pnl > 0) {
            uint256 funded = uint256(pnl);
            if (reportFunding != funded) revert UnsafeAssets();
            reportFunding = 0;
            rewardReserve += funded;
            totalRewardsFunded += funded;
            rewardIndex += Math.mulDiv(funded, INDEX_SCALE, totalSupply());
        } else if (pnl < 0) {
            debitPrice = oracle.price(); // Never silently use a stale/weekend price to transfer user collateral.
            debit = Math.mulDiv(uint256(-pnl), VALUE_SCALE, debitPrice, Math.Rounding.Ceil);
            // No pending deposits/old claims may cover a loss. Excess broker losses belong to the operator.
            if (debit > e.filledStock || debit >= activeStock) revert UnsafeAssets();
            activeStock -= debit;
        }
        e.netPnl = pnl;
        e.stockDebit = debit;
        e.debitPrice = debitPrice;
        e.settlementHash = digest;
        e.settledAt = uint64(block.timestamp);
        cumulativeOptionPnl += pnl;
        uint256 settledEpoch = currentEpoch++;
        delete report;
        phase = Phase.Collecting;
        if (debit != 0) _pushExact(stock, settlementRecipient, debit);
        _processQueues(); // Exits first, then new deposits, after the old cohort's profit/loss is fixed.
        _checkBacking();
        emit EpochSettled(settledEpoch, digest, pnl, debit, debitPrice);
    }

    function claimStock(address to) external nonReentrant returns (uint256 amount) {
        if (to == address(0) || to == address(this)) revert BadConfiguration();
        amount = claimableStock[msg.sender];
        if (amount == 0) revert BadAmount();
        claimableStock[msg.sender] = 0;
        reservedStock -= amount;
        _pushExact(stock, to, amount); // A failed token transfer reverts, retaining the entire claim.
        emit StockClaimed(msg.sender, to, amount);
    }

    function claimRewards(address to) external nonReentrant returns (uint256 amount) {
        if (to == address(0) || to == address(this)) revert BadConfiguration();
        _accrue(msg.sender);
        amount = rewardCredits[msg.sender];
        if (amount == 0) revert BadAmount();
        rewardCredits[msg.sender] = 0;
        rewardReserve -= amount;
        totalRewardsClaimed += amount;
        _pushExact(usdg, to, amount);
        emit RewardsClaimed(msg.sender, to, amount);
    }

    function _processQueues() internal {
        _checkBacking();
        // Each redemption uses the same stock/share exchange rate (rounding dust remains with the pool).
        uint256 sharesBefore = totalSupply();
        uint256 stockBefore = activeStock;
        for (uint256 i; i < _redeemers.length; ++i) {
            address account = _redeemers[i];
            uint256 shares = pendingRedeem[account];
            delete pendingRedeem[account];
            delete _redeemQueued[account];
            if (shares == 0) continue;
            uint256 amount = shares == totalSupply() ? activeStock : Math.mulDiv(shares, stockBefore, sharesBefore);
            activeStock -= amount;
            reservedStock += amount;
            claimableStock[account] += amount;
            _burn(account, shares);
            emit RedeemReserved(currentEpoch, account, shares, amount);
        }
        delete _redeemers;
        sharesBefore = totalSupply();
        stockBefore = activeStock;
        for (uint256 i; i < _depositors.length; ++i) {
            address account = _depositors[i];
            uint256 amount = pendingDeposit[account];
            delete pendingDeposit[account];
            delete _depositQueued[account];
            if (amount == 0) continue;
            pendingStock -= amount;
            uint256 shares = sharesBefore == 0 ? amount : Math.mulDiv(amount, sharesBefore, stockBefore);
            if (!eligible[account] || shares == 0 || shares > MAX_SHARES - totalSupply() || paused) {
                reservedStock += amount;
                claimableStock[account] += amount;
            } else {
                activeStock += amount;
                _mint(account, shares);
                emit DepositActivated(currentEpoch, account, amount, shares);
            }
        }
        delete _depositors;
    }

    function _accrue(address account) internal {
        uint256 delta = rewardIndex - rewardCheckpoint[account];
        uint256 amount = Math.mulDiv(balanceOf(account), delta, INDEX_SCALE);
        uint256 rem = mulmod(balanceOf(account), delta, INDEX_SCALE) + _rewardRemainder[account];
        rewardCredits[account] += amount + rem / INDEX_SCALE;
        _rewardRemainder[account] = rem % INDEX_SCALE;
        rewardCheckpoint[account] = rewardIndex;
    }

    function _update(address from, address to, uint256 value) internal override {
        if (from != address(0) && to != address(0)) revert NonTransferable();
        if (from != address(0)) _accrue(from);
        if (to != address(0)) _accrue(to);
        super._update(from, to, value);
    }

    function _checkBacking() internal view {
        if (
            stock.balanceOf(address(this)) < activeStock + pendingStock + reservedStock
                || usdg.balanceOf(address(this)) < rewardReserve + reportFunding
        ) revert UnsafeAssets();
    }

    function _pullExact(IERC20 token, address from, uint256 amount) internal {
        uint256 beforeBalance = token.balanceOf(address(this));
        token.safeTransferFrom(from, address(this), amount);
        if (token.balanceOf(address(this)) != beforeBalance + amount) revert UnsafeAssets();
    }

    function _pushExact(IERC20 token, address to, uint256 amount) internal {
        uint256 beforeBalance = token.balanceOf(address(this));
        uint256 recipientBefore = token.balanceOf(to);
        token.safeTransfer(to, amount);
        if (token.balanceOf(address(this)) + amount != beforeBalance || token.balanceOf(to) != recipientBefore + amount)
        {
            revert UnsafeAssets();
        }
    }
}
