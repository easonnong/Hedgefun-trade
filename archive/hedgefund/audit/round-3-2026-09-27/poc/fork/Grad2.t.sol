// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import "forge-std/Test.sol";
interface IV3Pool {
    function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool);
    function token0() external view returns (address);
    function token1() external view returns (address);
    function fee() external view returns (uint24);
    function swap(address,bool,int256,uint160,bytes calldata) external returns (int256,int256);
}
interface IERC20x { function transfer(address,uint256) external returns (bool); function symbol() external view returns (string memory);}
contract Grad2Test is Test {
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    uint160 constant MINS = 4295128739;
    uint160 constant MAXS = 1461446703485210103287273052203988822378723970342;
    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        IV3Pool p = IV3Pool(msg.sender);
        if (a0 > 0) IERC20x(p.token0()).transfer(msg.sender, uint256(a0));
        if (a1 > 0) IERC20x(p.token1()).transfer(msg.sender, uint256(a1));
    }
    function _bps(uint160 s0, uint160 s1, bool stockIsT1) internal pure returns (uint256) {
        uint256 r = stockIsT1 ? (uint256(s0) * 1e6 / uint256(s1)) : (uint256(s1) * 1e6 / uint256(s0));
        if (r < 1e6) return 0;
        return r * r / 1e8 - 1e4;
    }
    function _exactOut(address pool, bool t1, uint256 out) internal returns (uint256 usdgIn, uint256 bps, bool full) {
        (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
        deal(USDG, address(this), 500_000_000e6);
        (int256 a0, int256 a1) = IV3Pool(pool).swap(address(this), t1, -int256(out), t1 ? MINS+1 : MAXS-1, "");
        uint256 got = t1 ? uint256(-a1) : uint256(-a0);
        usdgIn = t1 ? uint256(a0) : uint256(a1);
        full = got >= out;
        (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
        bps = _bps(s0, s1, t1);
    }
    function _usdgFor(address pool, bool t1, uint256 target) internal returns (uint256) {
        uint256 lo = 100e6; uint256 hi = 3_000_000e6;
        for (uint256 i; i < 22; i++) {
            uint256 mid = (lo + hi) / 2;
            uint256 sn = vm.snapshotState();
            (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
            deal(USDG, address(this), mid);
            IV3Pool(pool).swap(address(this), t1, int256(mid), t1 ? MINS+1 : MAXS-1, "");
            (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
            uint256 b = _bps(s0, s1, t1);
            vm.revertToState(sn);
            if (b >= target) hi = mid; else lo = mid + 1;
        }
        return hi;
    }
    struct S { string n; address pool; address stock; uint256 rg; }
    function test_g2() public {
        S[4] memory L = [
          S("CRCL", 0x654E4143e82a5824445Ade0824351C2A9ACD95a8, 0xdF0992E440dD0be65BD8439b609d6D4366bf1CB5, 436e18),
          S("SPCX", 0xc61284332117c3FB23A2A56cceFFD07F7aF60029, 0x4a0E65A3EcceC6dBe60AE065F2e7bb85Fae35eEa, 262.4e18),
          S("META", 0x107a7Cb40d8665360ba10E59471Af06150A50922, 0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35, 53.6e18),
          S("MSTR", 0x17578C0e0D15da44f31677263114F71aE76653EA, 0xec262a75e413fAfD0dF80480274532C79D42da09, 244.4e18)
        ];
        for (uint256 i; i < 4; i++) {
            bool t1 = IV3Pool(L[i].pool).token1() == L[i].stock;
            emit log_named_string("=== stock", L[i].n);
            emit log_named_uint("v3 fee", IV3Pool(L[i].pool).fee());
            uint256 sn = vm.snapshotState();
            (uint256 u, uint256 b, bool full) = _exactOut(L[i].pool, t1, L[i].rg);
            emit log_named_uint("USDG to buy Rg (1e6)", u);
            emit log_named_uint("stock px up bps", b);
            emit log_named_string("full fill", full ? "yes" : "NO");
            vm.revertToState(sn);
            emit log_named_uint("USDG for +50bps", _usdgFor(L[i].pool, t1, 50));
        }
    }
}
