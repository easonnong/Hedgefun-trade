// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HedgeFunHook} from "./HedgeFunHook.sol";
import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency, CurrencyLibrary} from "v4-core/src/types/Currency.sol";
import {SwapParams} from "v4-core/src/types/PoolOperation.sol";
import {BalanceDelta} from "v4-core/src/types/BalanceDelta.sol";
import {BeforeSwapDelta, BeforeSwapDeltaLibrary, toBeforeSwapDelta} from "v4-core/src/types/BeforeSwapDelta.sol";
import {Hooks} from "v4-core/src/libraries/Hooks.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {LPFeeLibrary} from "v4-core/src/libraries/LPFeeLibrary.sol";
import {FullMath} from "v4-core/src/libraries/FullMath.sol";
import {HedgeFunMath} from "../libraries/HedgeFunMath.sol";

/// @notice V2 fees are stock on every side. A sell is taxed on the stock it receives and an exact-output buy on the
///         stock it pays, both in `afterSwap` as before. An exact-input buy is taxed on the stock it pays too, in
///         `beforeSwap`: the fee never exists in the strategy token, so nothing is held for anyone to convert and
///         the permissionless `sweep` settles every fee the pool has taken.
/// @dev `afterSwap` can only take from the unspecified currency, which for an exact-input buy is the token. Taking
///      the stock instead means taking it from the SPECIFIED amount, which only `beforeSwap` can do, and it does so
///      before the pool has moved: a swap that then stops at its price limit would have paid the rate on stock it
///      never traded. Such a buy is refused (`PartialFillRefused`) rather than overcharged; a buyer bounds the
///      price with a minimum output, as `HedgeFunV2TradeRouter` does. The treasury's own swaps are untaxed and may
///      stop early as before.
///
///      A graduated pool has no launch window (`registerGraduatedWithVault` refuses one), so its buy rate is the
///      flat tax. The fee is `floor(paid * rate)`: a payment under `10000 / rate` raw stock units pays none and is
///      not held to a fill.
///
///      The pool's LP fee funds the treasury's buy-back, and it is charged on what the swap moves. A buy's tax
///      never meets the pool, so left alone a buy would pay the LP fee on `1 - rate` of its payment and the
///      buy-back budget would shrink as the tax grows. Both buy paths therefore take `fee / (1 - fee)` of the tax
///      as well and donate it to the pool as LP fee: the swap's own LP fee and the donation together are the
///      pool's fee rate of everything the buyer pays, at any tax. The position's only owner is the vault, so the
///      donation reaches the buy-back budget by the path every LP fee takes. A sell needs nothing: its LP fee is
///      charged on the tokens it puts in.
///
///      A pool registered without a vault keeps the base hook's rules, token-denominated burn included. The
///      address carries the base flags and BEFORE_SWAP | BEFORE_SWAP_RETURNS_DELTA: 0x28CC.
contract HedgeFunV2Hook is HedgeFunHook {
    using PoolIdLibrary for PoolKey;
    using CurrencyLibrary for Currency;
    using StateLibrary for IPoolManager;

    /// @dev Transient: what `beforeSwap` took from an exact-input buy, for `afterSwap` to hold the fill to. The
    ///      pool makes no call between the two, so one slot serves every pool. Slots 0 and 1 are the base's.
    uint256 private constant TAKEN_SLOT = 2;

    error PartialFillRefused();

    constructor(IPoolManager manager) HedgeFunHook(manager) {}

    function version() external pure returns (uint256) { return 3; }

    function _flags() internal pure override returns (uint160) {
        return FLAGS | Hooks.BEFORE_SWAP_FLAG | Hooks.BEFORE_SWAP_RETURNS_DELTA_FLAG;
    }

    function beforeSwap(address sender, PoolKey calldata key, SwapParams calldata params, bytes calldata)
        external override returns (bytes4, BeforeSwapDelta, uint24)
    {
        if (msg.sender != address(poolManager)) revert NotPoolManager();
        PoolId id = key.toId();
        Pool storage p = _pool(id);
        if (sender == p.treasury || !_taxedOnInput(id, p, params)) {
            return (IHooks.beforeSwap.selector, BeforeSwapDeltaLibrary.ZERO_DELTA, 0);
        }
        uint256 paid = uint256(-params.amountSpecified);
        uint256 tax = HedgeFunMath.bps(paid, p.taxBps);
        if (tax == 0) return (IHooks.beforeSwap.selector, BeforeSwapDeltaLibrary.ZERO_DELTA, 0);
        if (tax > uint128(type(int128).max)) revert BadConfig();
        // The claim joins every other pool's claims on this stock; `accruedStock` is what keeps it this pool's.
        poolManager.mint(address(this), Currency.wrap(p.stock).toId(), tax);
        p.accruedStock += uint128(tax);
        uint256 taken = tax + _topUpLpFee(key, id, p, tax);
        // As on an exact-output buy: `moved` is the stock the swap moves; the buyer pays it, the tax and the top-up.
        emit Taxed(id, false, false, paid - taken, tax, p.taxBps);
        assembly ("memory-safe") { tstore(TAKEN_SLOT, taken) }
        return (IHooks.beforeSwap.selector, toBeforeSwapDelta(int128(int256(taken)), 0), 0);
    }

    /// @dev An exact-input buy on a vault pool was taxed before the swap; here it only has to have filled. An
    ///      exact-output buy is taxed by the base, in stock, and tops the LP fee up on that tax here.
    function _tax(PoolId id, Pool storage p, address sender, PoolKey calldata key, SwapParams calldata params, BalanceDelta swapDelta)
        internal override returns (int128)
    {
        if (!_taxedOnInput(id, p, params)) {
            int128 tax = super._tax(id, p, sender, key, params, swapDelta);
            bool buying = p.tokenIsCurrency0 != params.zeroForOne;
            if (tax == 0 || !buying || liquidityVaultOf[id] == address(0)) return tax;
            return tax + int128(int256(_topUpLpFee(key, id, p, uint256(uint128(tax)))));
        }
        uint256 taken;
        assembly ("memory-safe") { taken := tload(TAKEN_SLOT) tstore(TAKEN_SLOT, 0) }
        int128 swapped = params.zeroForOne ? swapDelta.amount0() : swapDelta.amount1();
        if (taken != 0 && uint256(uint128(-swapped)) != uint256(-params.amountSpecified) - taken) revert PartialFillRefused();
        return 0;
    }

    /// @dev Donates `fee / (1 - fee)` of a buy's tax to the pool as LP fee, in stock, and returns it: the caller
    ///      takes it from the buyer in the same delta as the tax. Nothing for a pool with no liquidity in range
    ///      to receive it, or one whose LP fee is not a static rate.
    function _topUpLpFee(PoolKey calldata key, PoolId id, Pool storage p, uint256 tax) private returns (uint256 topUp) {
        uint24 fee = key.fee;
        if (LPFeeLibrary.isDynamicFee(fee) || fee == 0 || fee >= LPFeeLibrary.MAX_LP_FEE || poolManager.getLiquidity(id) == 0) return 0;
        topUp = FullMath.mulDiv(tax, fee, LPFeeLibrary.MAX_LP_FEE - fee);
        if (topUp == 0) return 0;
        (uint256 amount0, uint256 amount1) = p.tokenIsCurrency0 ? (uint256(0), topUp) : (topUp, uint256(0));
        poolManager.donate(key, amount0, amount1, "");
    }

    function _taxedOnInput(PoolId id, Pool storage p, SwapParams calldata params) private view returns (bool) {
        return liquidityVaultOf[id] != address(0) && params.amountSpecified < 0 && p.tokenIsCurrency0 != params.zeroForOne;
    }
}
