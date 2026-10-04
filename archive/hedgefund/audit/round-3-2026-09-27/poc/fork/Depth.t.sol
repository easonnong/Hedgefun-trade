// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import "forge-std/Test.sol";

interface IV3Pool {
    function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool);
    function liquidity() external view returns (uint128);
    function token0() external view returns (address);
    function token1() external view returns (address);
    function fee() external view returns (uint24);
    function swap(address recipient, bool zeroForOne, int256 amountSpecified, uint160 sqrtPriceLimitX96, bytes calldata data)
        external returns (int256 amount0, int256 amount1);
}
interface IERC20x { function balanceOf(address) external view returns (uint256); function transfer(address,uint256) external returns (bool); function decimals() external view returns (uint8); function symbol() external view returns (string memory);}

contract DepthTest is Test {
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address constant NVDA = 0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC;
    address constant GME  = 0x1b0E319c6A659F002271B69dB8A7df2F911c153E;
    address constant AMD  = 0x86923f96303D656E4aa86D9d42D1e57ad2023fdC;
    address constant P_NVDA = 0xd4EB21209C4D6093f80B5b84f5C45cc093EA14a3;
    address constant P_GME  = 0xE2b46c905E12Ab8E2f864e4821a4325884C1B126;
    address constant P_AMD  = 0x48D284A2A4d3DC1b3Da08231Fe44317e7e7Aa51f;

    uint160 constant MIN_SQRT = 4295128739;
    uint160 constant MAX_SQRT = 1461446703485210103287273052203988822378723970342;

    address payer;
    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        IV3Pool p = IV3Pool(msg.sender);
        if (a0 > 0) IERC20x(p.token0()).transfer(msg.sender, uint256(a0));
        if (a1 > 0) IERC20x(p.token1()).transfer(msg.sender, uint256(a1));
    }


    function _run(address pool, address stock, bool stockIsT1, uint256[] memory usdgAmts) internal {
        (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
        uint128 L = IV3Pool(pool).liquidity();
        emit log_named_string("pool stock", IERC20x(stock).symbol());
        emit log_named_uint("sqrtPriceX96 start", s0);
        emit log_named_uint("active liquidity", L);
        for (uint256 i; i < usdgAmts.length; i++) {
            uint256 snap = vm.snapshotState();
            deal(USDG, address(this), usdgAmts[i]);
            // buying stock with usdg
            bool zeroForOne = !stockIsT1 ? false : true; // usdg is token0 when stockIsT1
            uint160 lim = zeroForOne ? MIN_SQRT + 1 : MAX_SQRT - 1;
            (int256 a0, int256 a1) = IV3Pool(pool).swap(address(this), zeroForOne, int256(usdgAmts[i]), lim, "");
            (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
            uint256 stockOut = stockIsT1 ? uint256(-a1) : uint256(-a0);
            uint256 usdgIn = stockIsT1 ? uint256(a0) : uint256(a1);
            // price move in bps of the STOCK price: stock price up when sqrt moves the right way
            uint256 moveBps;
            if (stockIsT1) {
                // stock price up == P(t1/t0) down == s1 < s0 ; price ratio = (s0/s1)^2
                moveBps = (uint256(s0) * 1e4 / uint256(s1));
                moveBps = moveBps * moveBps / 1e4 - 1e4;
            } else {
                moveBps = (uint256(s1) * 1e4 / uint256(s0));
                moveBps = moveBps * moveBps / 1e4 - 1e4;
            }
            emit log_named_uint("usdg in (1e6)", usdgIn);
            emit log_named_uint("stock out (1e18)", stockOut);
            emit log_named_uint("stock price up, bps", moveBps);
            vm.revertToState(snap);
        }
    }

    function test_depth() public {
        uint256[] memory a = new uint256[](7);
        a[0] = 10_000e6; a[1] = 50_000e6; a[2] = 100_000e6; a[3] = 250_000e6; a[4] = 500_000e6; a[5] = 1_000_000e6; a[6] = 2_000_000e6;
        emit log("=== NVDA/USDG 0.05%");
        _run(P_NVDA, NVDA, true, a);
        emit log("=== GME/USDG 0.05%");
        _run(P_GME, GME, false, a);
        emit log("=== AMD/USDG 0.30%");
        _run(P_AMD, AMD, true, a);
    }
}
