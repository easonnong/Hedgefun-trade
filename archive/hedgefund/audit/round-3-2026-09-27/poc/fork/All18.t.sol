// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import "forge-std/Test.sol";
interface IV3Pool {
    function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool);
    function token0() external view returns (address); function token1() external view returns (address);
    function fee() external view returns (uint24);
    function swap(address,bool,int256,uint160,bytes calldata) external returns (int256,int256);
}
interface IERC20x { function transfer(address,uint256) external returns (bool); function symbol() external view returns (string memory);}
interface IFactory { function listings(address) external view returns (address,address,uint256,bool); }
/// @dev MEASUREMENT PROBE for round-3 findings M-2 (raise size vs venue depth) and M-3 (a curve whose
///      graduation requirement exceeds its pool's entire stock side can never graduate).
///
///      Its OUTPUT is the evidence, not its exit status. Every per-listing number below is read from LIVE
///      pool state and moves between runs -- INTC's shortfall read 115.9% of the requirement on 2026-09-27
///      and 119.7% a few thousand blocks later -- so the report dates each figure where it quotes it and
///      this probe asserts only on what is deterministic: that each listing resolves, that its pool is the
///      stock/USDG pair, and that the graduation requirement is non-zero. Re-run it to re-measure.
///
///      Robinhood Chain's public RPC is not an archive node (state ~24k blocks back is already gone), so
///      the fork cannot be pinned to the block the report quotes.
contract All18Test is Test {
    address constant USDG = 0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168;
    address constant FAC  = 0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961;
    uint160 constant MINS = 4295128739;
    uint160 constant MAXS = 1461446703485210103287273052203988822378723970342;
    function uniswapV3SwapCallback(int256 a0, int256 a1, bytes calldata) external {
        IV3Pool p = IV3Pool(msg.sender);
        if (a0 > 0) IERC20x(p.token0()).transfer(msg.sender, uint256(a0));
        if (a1 > 0) IERC20x(p.token1()).transfer(msg.sender, uint256(a1));
    }
    function _bps(uint160 s0, uint160 s1, bool t1) internal pure returns (uint256) {
        uint256 r = t1 ? (uint256(s0) * 1e6 / uint256(s1)) : (uint256(s1) * 1e6 / uint256(s0));
        if (r < 1e6) return 0;
        uint256 v = r * r / 1e8;
        return v < 1e4 ? 0 : v - 1e4;
    }
    function _usdgFor(address pool, bool t1, uint256 target) internal returns (uint256) {
        uint256 lo = 100e6; uint256 hi = 3_000_000e6;
        for (uint256 i; i < 16; i++) {
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
    function test_all18() public {
        // Locals, not storage: vm.revertToState() below rolls back this contract's storage as well.
        uint256 cannotFill;
        address[18] memory stocks = [
          0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC,0x4a0E65A3EcceC6dBe60AE065F2e7bb85Fae35eEa,
          0xdF0992E440dD0be65BD8439b609d6D4366bf1CB5,0x2e0847E8910a9732eB3fb1bb4b70a580ADAD4FE3,
          0x12f190a9F9d7D37a250758b26824B97CE941bF54,0x1b0E319c6A659F002271B69dB8A7df2F911c153E,
          0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35,0xd917B029C761D264c6A312BBbcDA868658eF86a6,
          0xec262a75e413fAfD0dF80480274532C79D42da09,0x86923f96303D656E4aa86D9d42D1e57ad2023fdC,
          0xfF080c8ce2E5feadaCa0Da81314Ae59D232d4afD,0xc72b96e0E48ecd4DC75E1e45396e26300BC39681,
          0xaF3D76f1834A1d425780943C99Ea8A608f8a93f9,0xD5f3879160bc7c32ebb4dC785F8a4F505888de68,
          0xe93237C50D904957Cf27E7B1133b510C669c2e74,0x322F0929c4625eD5bAd873c95208D54E1c003b2d,
          0xa30FA36Db767ad9eD3f7a60fC79526fB4d56D344,0xC9a981FEE1F9DEc688bb123ccDeCc63D0deBFC4e
        ];
        for (uint256 i; i < 18; i++) {
            (, address pool, uint256 openP,) = IFactory(FAC).listings(stocks[i]);
            assertTrue(pool != address(0), "listing resolves to a pool");
            bool t1 = IV3Pool(pool).token1() == stocks[i];
            assertEq(t1 ? IV3Pool(pool).token0() : IV3Pool(pool).token1(), USDG, "pool is stock/USDG");
            assertEq(t1 ? IV3Pool(pool).token1() : IV3Pool(pool).token0(), stocks[i], "pool is stock/USDG");
            uint256 rg = 4 * openP * 1e27 / 1e18;
            assertTrue(rg != 0, "graduation requirement is non-zero");
            emit log_named_string("stock", IERC20x(stocks[i]).symbol());
            emit log_named_uint("fee", IV3Pool(pool).fee());
            emit log_named_uint("Rg 1e18", rg);
            uint256 sn = vm.snapshotState();
            (uint160 s0,,,,,,) = IV3Pool(pool).slot0();
            deal(USDG, address(this), 500_000_000e6);
            // An exact-OUTPUT swap for Rg reverts outright when the pool cannot deliver Rg at any price.
            // That revert IS the finding (M-3): the graduation requirement exceeds the pool's entire stock
            // side, so the curve can never graduate and the buyers' stock is stranded on it. Catch it,
            // report how much the pool can actually deliver, and keep going through the remaining listings.
            try IV3Pool(pool).swap(address(this), t1, -int256(rg), t1 ? MINS+1 : MAXS-1, "") returns (int256 a0, int256 a1) {
                uint256 got = t1 ? uint256(-a1) : uint256(-a0);
                emit log_named_uint("USDG for Rg 1e6", t1 ? uint256(a0) : uint256(a1));
                emit log_named_string("full fill", got >= rg ? "yes" : "NO");
                (uint160 s1,,,,,,) = IV3Pool(pool).slot0();
                emit log_named_uint("one-shot move bps", _bps(s0, s1, t1));
            } catch {
                vm.revertToState(sn);
                sn = vm.snapshotState();
                deal(USDG, address(this), 500_000_000e6);
                // Drain the whole stock side to see what the pool holds, priced in the stock token.
                (int256 b0, int256 b1) = IV3Pool(pool).swap(address(this), t1, int256(500_000_000e6), t1 ? MINS+1 : MAXS-1, "");
                uint256 h = t1 ? uint256(-b1) : uint256(-b0);
                cannotFill++;
                emit log_named_string("full fill", "NO - pool cannot deliver Rg at any price");
                emit log_named_uint("stock the pool holds 1e18", h);
                emit log_named_uint("shortfall bps of Rg", (rg - h) * 10000 / rg);
            }
            vm.revertToState(sn);
            emit log_named_uint("USDG for 50bps", _usdgFor(pool, t1, 50));
        }

        // Reported, not asserted -- this count is live chain state. It read 1 (INTC) on 2026-09-27.
        emit log_named_uint("listings whose pool cannot deliver Rg (M-3)", cannotFill);
    }
}
