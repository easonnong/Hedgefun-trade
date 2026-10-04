// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {SandboxFeed} from "./SandboxAssets.sol";

interface IV3Factory {
    function createPool(address tokenA, address tokenB, uint24 fee) external returns (address);
    function getPool(address tokenA, address tokenB, uint24 fee) external view returns (address);
}

interface IV3Pool {
    function initialize(uint160 sqrtPriceX96) external;
    function increaseObservationCardinalityNext(uint16 next) external;
    function mint(address recipient, int24 tickLower, int24 tickUpper, uint128 amount, bytes calldata data) external returns (uint256, uint256);
    function swap(address recipient, bool zeroForOne, int256 amountSpecified, uint160 sqrtPriceLimitX96, bytes calldata data) external returns (int256, int256);
    function burn(int24 tickLower, int24 tickUpper, uint128 amount) external returns (uint256, uint256);
    function collect(address recipient, int24 tickLower, int24 tickUpper, uint128 amount0Requested, uint128 amount1Requested) external returns (uint128, uint128);
    function positions(bytes32 key) external view returns (uint128, uint256, uint256, uint128, uint128);
    function slot0() external view returns (uint160, int24, uint16, uint16, uint16, uint8, bool);
    function liquidity() external view returns (uint128);
    function token0() external view returns (address);
    function token1() external view returns (address);
    function tickSpacing() external view returns (int24);
}

/// A single canonical V3 pool and a single recoverable position, holding only rehearsal assets.
contract SandboxLp is Ownable2Step, ReentrancyGuard {
    using SafeERC20 for IERC20;
    uint256 private constant Q96 = 1 << 96;
    uint256 private constant SCALE = 1e30;
    address public immutable quote;
    address public immutable stock;
    IV3Pool public immutable pool;
    bool public immutable stockIsToken0;
    int24 public immutable tickLower;
    int24 public immutable tickUpper;
    SandboxFeed public immutable feed;
    SandboxFeed public immutable quoteFeed;
    uint8 private _callback; // 1: mint, 2: swap. No callback is accepted outside an active operation.
    uint256 private _remaining0;
    uint256 private _remaining1;

    error BadConfig();
    error BadCallback();
    error InputLimit();
    error Expired();
    error BadPrice();
    error PriceNotReached();
    error Slippage();

    constructor(address initialOwner, address factory, address quote_, address stock_, int24 lo, int24 hi)
        Ownable(initialOwner)
    {
        address p = IV3Factory(factory).getPool(quote_, stock_, 3000);
        if (p == address(0) || quote_ == stock_ || quote_ == address(0) || stock_ == address(0)) revert BadConfig();
        IV3Pool v3 = IV3Pool(p);
        bool stock0 = stock_ < quote_;
        if (v3.token0() != (stock0 ? stock_ : quote_) || v3.token1() != (stock0 ? quote_ : stock_)) revert BadConfig();
        int24 spacing = v3.tickSpacing();
        if (spacing <= 0 || lo >= hi || lo % spacing != 0 || hi % spacing != 0) revert BadConfig();
        quote = quote_; stock = stock_; pool = v3; stockIsToken0 = stock0;
        tickLower = lo; tickUpper = hi;
        feed = new SandboxFeed(100e8, address(this));
        quoteFeed = new SandboxFeed(1e8, address(this));
    }

    function addLiquidity(uint128 amount, uint256 max0, uint256 max1, uint256 deadline)
        external onlyOwner nonReentrant returns (uint256 a0, uint256 a1)
    {
        _deadline(deadline);
        if (amount == 0) revert BadConfig();
        _callback = 1; _remaining0 = max0; _remaining1 = max1;
        (a0, a1) = pool.mint(address(this), tickLower, tickUpper, amount, "");
        _clear();
    }

    /// Caps the actual input and requires the target to be reached inside active liquidity.
    /// The swap, stock feed and test-dollar feed either all succeed or all revert.
    function setPrice(uint256 priceE18, uint256 maxInput, uint256 deadline)
        external onlyOwner nonReentrant returns (int256 a0, int256 a1)
    {
        _deadline(deadline);
        uint160 target = sqrtFor(priceE18);
        if (pool.liquidity() == 0 || maxInput == 0 || maxInput > uint256(type(int256).max)) revert BadPrice();
        (uint160 current,,,,,,) = pool.slot0();
        if (current != target) {
            bool zeroForOne = target < current;
            _callback = 2;
            _remaining0 = zeroForOne ? maxInput : 0;
            _remaining1 = zeroForOne ? 0 : maxInput;
            (a0, a1) = pool.swap(address(this), zeroForOne, int256(maxInput), target, "");
            _clear();
        }
        (uint160 actual,,,,,,) = pool.slot0();
        if (actual != target || pool.liquidity() == 0) revert PriceNotReached();
        _setFeeds(priceE18);
    }

    /// Explicit operator action: adopts the current in-range pool price, including any public trades.
    function repeg() external onlyOwner nonReentrant {
        if (pool.liquidity() == 0) revert BadPrice();
        (uint160 sqrtP,,,,,,) = pool.slot0();
        _setFeeds(priceAt(sqrtP));
    }

    function removeLiquidity(uint128 amount, uint256 min0, uint256 min1, address recipient, uint256 deadline)
        external onlyOwner nonReentrant returns (uint128 a0, uint128 a1)
    {
        _deadline(deadline);
        if (amount == 0 || recipient == address(0)) revert BadConfig();
        (uint256 principal0, uint256 principal1) = pool.burn(tickLower, tickUpper, amount);
        if (principal0 < min0 || principal1 < min1) revert Slippage();
        return pool.collect(recipient, tickLower, tickUpper, type(uint128).max, type(uint128).max);
    }

    function collectFees(address recipient) external onlyOwner nonReentrant returns (uint128 a0, uint128 a1) {
        if (recipient == address(0)) revert BadConfig();
        if (positionLiquidity() != 0) pool.burn(tickLower, tickUpper, 0);
        return pool.collect(recipient, tickLower, tickUpper, type(uint128).max, type(uint128).max);
    }

    function positionLiquidity() public view returns (uint128 amount) {
        (amount,,,,) = pool.positions(keccak256(abi.encodePacked(address(this), tickLower, tickUpper)));
    }

    function sweep(address token, address recipient) external onlyOwner nonReentrant {
        if (recipient == address(0)) revert BadConfig();
        IERC20(token).safeTransfer(recipient, IERC20(token).balanceOf(address(this)));
    }

    function uniswapV3MintCallback(uint256 owed0, uint256 owed1, bytes calldata) external {
        if (_callback != 1) revert BadCallback();
        _pay(owed0, owed1);
    }

    function uniswapV3SwapCallback(int256 d0, int256 d1, bytes calldata) external {
        if (_callback != 2) revert BadCallback();
        _pay(d0 > 0 ? uint256(d0) : 0, d1 > 0 ? uint256(d1) : 0);
    }

    function _pay(uint256 owed0, uint256 owed1) private {
        if (msg.sender != address(pool)) revert BadCallback();
        if (owed0 > _remaining0 || owed1 > _remaining1) revert InputLimit();
        _remaining0 -= owed0; _remaining1 -= owed1;
        if (owed0 != 0) IERC20(stockIsToken0 ? stock : quote).safeTransfer(msg.sender, owed0);
        if (owed1 != 0) IERC20(stockIsToken0 ? quote : stock).safeTransfer(msg.sender, owed1);
    }

    function _clear() private { _callback = 0; _remaining0 = 0; _remaining1 = 0; }
    function _deadline(uint256 deadline) private view { if (block.timestamp > deadline) revert Expired(); }
    function _setFeeds(uint256 priceE18) private {
        _checkPrice(priceE18);
        feed.set(int256(priceE18 / 1e10));
        quoteFeed.set(1e8);
    }
    function _checkPrice(uint256 p) private pure { if (p < 25e18 || p > 400e18) revert BadPrice(); }
    function sqrtFor(uint256 p) public view returns (uint160) {
        _checkPrice(p);
        return uint160(Math.sqrt(stockIsToken0 ? Math.mulDiv(p, 1 << 192, SCALE) : Math.mulDiv(SCALE, 1 << 192, p)));
    }
    function priceAt(uint160 sqrtP) public view returns (uint256) {
        uint256 rawX96 = Math.mulDiv(sqrtP, sqrtP, Q96);
        if (rawX96 == 0) revert BadPrice();
        return stockIsToken0 ? Math.mulDiv(rawX96, SCALE, Q96) : Math.mulDiv(SCALE, Q96, rawX96);
    }
}
