// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import "forge-std/Test.sol";

interface IV3Pool {
    function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool);
    function token0() external view returns (address);
    function token1() external view returns (address);
    function swap(address recipient, bool zeroForOne, int256 amountSpecified, uint160 sqrtPriceLimitX96, bytes calldata data)
        external returns (int256 amount0, int256 amount1);
}
interface IERC20x { function balanceOf(address) external view returns (uint256); function transfer(address,uint256) external returns (bool); function symbol() external view returns (string memory);}

contract GradTest is Test {
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    uint160 constant MIN_SQRT = 4295128739;
    uint160 constant MAX_SQRT = 1461446703485210103287273052203988822378723970342;

    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        IV3Pool p = IV3Pool(msg.sender);
        if (a0 > 0) IERC20x(p.token0()).transfer(msg.sender, uint256(a0));
        if (a1 > 0) IERC20x(p.token1()).transfer(msg.sender, uint256(a1));
    }

    // buy exactly `stockOut` of stock with USDG; return usdg spent and bps the stock price rose
    function _buyExactOut(address pool, bool stockIsT1, uint256 stockOut) internal returns (uint256 usdgIn, uint256 bps, bool full) {
        (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
        deal(USDG, address(this), 500_000_000e6);
        bool zeroForOne = stockIsT1;             // usdg is token0 iff stock is token1
        uint160 lim = zeroForOne ? MIN_SQRT + 1 : MAX_SQRT - 1;
        (int256 a0, int256 a1) = IV3Pool(pool).swap(address(this), zeroForOne, -int256(stockOut), lim, "");
        uint256 got = stockIsT1 ? uint256(-a1) : uint256(-a0);
        usdgIn = stockIsT1 ? uint256(a0) : uint256(a1);
        full = got >= stockOut;
        (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
        uint256 r = stockIsT1 ? (uint256(s0) * 1e6 / uint256(s1)) : (uint256(s1) * 1e6 / uint256(s0));
        bps = r * r / 1e8 - 1e4;
    }

    // smallest USDG that moves the stock price by >= targetBps
    function _usdgFor(address pool, bool stockIsT1, uint256 targetBps) internal returns (uint256) {
        uint256 lo = 1e6; uint256 hi = 5_000_000e6;
        for (uint256 i; i < 40; i++) {
            uint256 mid = (lo + hi) / 2;
            uint256 snap = vm.snapshotState();
            (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
            deal(USDG, address(this), mid);
            bool zeroForOne = stockIsT1;
            uint160 lim = zeroForOne ? MIN_SQRT + 1 : MAX_SQRT - 1;
            IV3Pool(pool).swap(address(this), zeroForOne, int256(mid), lim, "");
            (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
            uint256 r = stockIsT1 ? (uint256(s0) * 1e6 / uint256(s1)) : (uint256(s1) * 1e6 / uint256(s0));
            uint256 bps = r * r / 1e8 - 1e4;
            vm.revertToState(snap);
            if (bps >= targetBps) hi = mid; else lo = mid + 1;
        }
        return hi;
    }

    struct S { string name; address pool; bool stockIsT1; uint256 rg; }

    function test_graduation_cost() public {
        S[3] memory list = [
            S("NVDA", 0xd4EB21209C4D6093f80B5b84f5C45cc093EA14a3, true,  176_800_000_000_000_000_000),
            S("GME",  0xE2b46c905E12Ab8E2f864e4821a4325884C1B126, false, 1692_000_000_000_000_000_000),
            S("AMD",  0x48D284A2A4d3DC1b3Da08231Fe44317e7e7Aa51f, true,  65_200_000_000_000_000_000)
        ];
        for (uint256 i; i < 3; i++) {
            emit log_named_string("=== stock", list[i].name);
            uint256 snap = vm.snapshotState();
            (uint256 usdgIn, uint256 bps, bool full) = _buyExactOut(list[i].pool, list[i].stockIsT1, list[i].rg);
            emit log_named_uint("Rg (1e18)", list[i].rg);
            emit log_named_uint("USDG to buy Rg (1e6)", usdgIn);
            emit log_named_uint("stock price up, bps", bps);
            emit log_named_string("filled full Rg", full ? "yes" : "NO - pool exhausted");
            vm.revertToState(snap);
            emit log_named_uint("USDG to breach 50bps health gate (1e6)", _usdgFor(list[i].pool, list[i].stockIsT1, 50));
            emit log_named_uint("USDG to move +300bps (1e6)", _usdgFor(list[i].pool, list[i].stockIsT1, 300));
        }
    }
}
