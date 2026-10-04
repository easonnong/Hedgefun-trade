// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import "forge-std/Test.sol";
interface IV3Pool {
    function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool);
    function token0() external view returns (address); function token1() external view returns (address);
    function fee() external view returns (uint24); function liquidity() external view returns (uint128);
    function swap(address,bool,int256,uint160,bytes calldata) external returns (int256,int256);
}
interface IERC20x { function transfer(address,uint256) external returns (bool); function symbol() external view returns (string memory); function balanceOf(address) external view returns (uint256);}
interface IFactory { function listings(address) external view returns (address,address,uint256,bool); }
contract Rest7Test is Test {
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address constant FAC  = 0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961;
    uint160 constant MINS = 4295128739;
    uint160 constant MAXS = 1461446703485210103287273052203988822378723970342;
    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        IV3Pool p = IV3Pool(msg.sender);
        if (a0 > 0) IERC20x(p.token0()).transfer(msg.sender, uint256(a0));
        if (a1 > 0) IERC20x(p.token1()).transfer(msg.sender, uint256(a1));
    }
    function doSwap(address pool, bool zf, int256 amt) external returns (int256,int256) {
        return IV3Pool(pool).swap(address(this), zf, amt, zf ? MINS+1 : MAXS-1, "");
    }
    function _bps(uint160 s0, uint160 s1, bool t1) internal pure returns (uint256) {
        uint256 r = t1 ? (uint256(s0) * 1e6 / uint256(s1)) : (uint256(s1) * 1e6 / uint256(s0));
        if (r < 1e6) return 0;
        uint256 v = r * r / 1e8;
        return v < 1e4 ? 0 : v - 1e4;
    }
    function _usdgFor(address pool, bool t1, uint256 target) internal returns (uint256) {
        uint256 lo = 50e6; uint256 hi = 3_000_000e6;
        for (uint256 i; i < 16; i++) {
            uint256 mid = (lo + hi) / 2;
            uint256 sn = vm.snapshotState();
            (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
            deal(USDG, address(this), mid);
            uint256 b;
            try this.doSwap(pool, t1, int256(mid)) { (uint160 s1,,,,,,) = IV3Pool(pool).slot0(); b = _bps(s0,s1,t1); } catch { b = type(uint256).max; }
            vm.revertToState(sn);
            if (b >= target) hi = mid; else lo = mid + 1;
        }
        return hi;
    }
    function test_rest7() public {
        address[7] memory stocks = [
          0xc72b96e0E48ecd4DC75E1e45396e26300BC39681, // INTC
          0xaF3D76f1834A1d425780943C99Ea8A608f8a93f9, // AAPL
          0xD5f3879160bc7c32ebb4dC785F8a4F505888de68, // QQQ
          0xe93237C50D904957Cf27E7B1133b510C669c2e74, // MSFT
          0x322F0929c4625eD5bAd873c95208D54E1c003b2d, // TSLA
          0xa30FA36Db767ad9eD3f7a60fC79526fB4d56D344, // USO
          0xC9a981FEE1F9DEc688bb123ccDeCc63D0deBFC4e  // GLD
        ];
        for (uint256 i; i < 7; i++) {
            (, address pool, uint256 openP,) = IFactory(FAC).listings(stocks[i]);
            bool t1 = IV3Pool(pool).token1() == stocks[i];
            uint256 rg = 4 * openP * 1e27 / 1e18;
            emit log_named_string("stock", IERC20x(stocks[i]).symbol());
            emit log_named_uint("fee", IV3Pool(pool).fee());
            emit log_named_uint("Rg 1e18", rg);
            emit log_named_uint("pool stock inventory 1e18", IERC20x(stocks[i]).balanceOf(pool));
            uint256 sn = vm.snapshotState();
            (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
            deal(USDG, address(this), 500_000_000e6);
            try this.doSwap(pool, t1, -int256(rg)) returns (int256 a0, int256 a1) {
                uint256 got = t1 ? uint256(-a1) : uint256(-a0);
                emit log_named_uint("USDG for Rg 1e6", t1 ? uint256(a0) : uint256(a1));
                emit log_named_string("full fill", got >= rg ? "yes" : "NO");
                (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
                emit log_named_uint("one-shot move bps", _bps(s0, s1, t1));
            } catch {
                emit log_named_string("full fill", "REVERT - pool cannot supply Rg");
                emit log_named_uint("one-shot move bps", 0);
            }
            vm.revertToState(sn);
            emit log_named_uint("USDG for 50bps", _usdgFor(pool, t1, 50));
        }
    }
}
