#!/usr/bin/env python3
"""Manipulation cost of one V2RebalancePolicy action, on a constant-liquidity Uniswap V3 pool. No network.

The engine (`HedgeFunV2EngineTreasury.execute`) values the treasury at the CHAINLINK price `p`, decides at `p`, and then
trades through `PoolTrader._swapBounded`: an exact-input V3 swap whose price limit is `p * (1 -/+ maxSlippageBps)` and
whose realised average must be no worse than `p * (1 -/+ (maxSlippageBps + poolFeeBps))`. Before it trades, `health()`
requires the pool's spot within `maxDeviationBps` of `p` AND within `maxDeviationBps` ticks of the pool's own 600 s mean.

So the pool cannot move the decision (the trigger is Chainlink's), but whoever calls `execute()` chooses the moment, and
the room between the deviation gate (where spot may sit when the call begins) and the slippage limit (where the fill may
end) is what a sandwich can extract. This script measures it:

  push      the attacker moves spot to the edge of the deviation gate (selling stock for a treasury sell, buying for a
            treasury buy), inside the same block -- the TWAP gate does not move, the oracle does not move
  execute   the treasury's exact-input swap fills from the pushed spot down to the slippage limit, or until `maxTrade`
  unwind    the attacker buys back exactly what they sold

and reports the attacker's USDG P&L and the treasury's extra cost against an unmanipulated fill, for a grid of
`maxTradeUsdg` against pool depth (USDG that moves the pool 1%; round 3 measured ~$3.3k for AMD and ~$55k for AAPL on
2026-09-27). Amounts in human units; the pool is single-range constant `L` with the fee on the input, exactly V3's
in-range step. Rehearsal gates: maxDeviationBps 50, maxSlippageBps 100, fee 30 bps (`script/RehearseV2Launchpad.s.sol`).

    python3 sandwich_model.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Pool:
    """One in-range V3 step: constant liquidity L in sqrt-price units, fee on the input."""
    sqrt_p: float          # sqrt(USDG per stock)
    L: float
    fee: float

    @classmethod
    def with_depth(cls, price: float, usdg_per_1pct: float, fee: float) -> "Pool":
        # USDG needed to lift the price by 1%: L * (sqrt(1.01 p) - sqrt(p))
        L = usdg_per_1pct / (math.sqrt(price) * (math.sqrt(1.01) - 1))
        return cls(math.sqrt(price), L, fee)

    @property
    def price(self) -> float:
        return self.sqrt_p ** 2

    def sell_stock(self, stock_in: float, sqrt_limit: float) -> tuple[float, float]:
        """exact input of stock (token0 in), price falls, stops at sqrt_limit. returns (stock spent, usdg out)"""
        net = stock_in * (1 - self.fee)
        # stock needed to reach the limit
        to_limit = self.L * (1 / sqrt_limit - 1 / self.sqrt_p) if sqrt_limit < self.sqrt_p else 0.0
        if net >= to_limit:
            net = to_limit
        new_sqrt = 1 / (1 / self.sqrt_p + net / self.L) if net > 0 else self.sqrt_p
        usdg_out = self.L * (self.sqrt_p - new_sqrt)
        self.sqrt_p = new_sqrt
        return net / (1 - self.fee), usdg_out

    def buy_stock(self, usdg_in: float, sqrt_limit: float) -> tuple[float, float]:
        """exact input of USDG (token1 in), price rises, stops at sqrt_limit. returns (usdg spent, stock out)"""
        net = usdg_in * (1 - self.fee)
        to_limit = self.L * (sqrt_limit - self.sqrt_p) if sqrt_limit > self.sqrt_p else 0.0
        if net >= to_limit:
            net = to_limit
        new_sqrt = self.sqrt_p + net / self.L
        stock_out = self.L * (1 / self.sqrt_p - 1 / new_sqrt)
        self.sqrt_p = new_sqrt
        return net / (1 - self.fee), stock_out

    def buy_exact_stock(self, stock_out: float) -> float:
        """buy exactly `stock_out`; returns USDG paid (fee on the input)"""
        new_sqrt = 1 / (1 / self.sqrt_p - stock_out / self.L)
        usdg_net = self.L * (new_sqrt - self.sqrt_p)
        self.sqrt_p = new_sqrt
        return usdg_net / (1 - self.fee)

    def sell_exact_stock_for(self, usdg_out: float) -> float:
        """sell enough stock to receive exactly `usdg_out`; returns stock paid"""
        new_sqrt = self.sqrt_p - usdg_out / self.L
        net = self.L * (1 / new_sqrt - 1 / self.sqrt_p)
        self.sqrt_p = new_sqrt
        return net / (1 - self.fee)


@dataclass(frozen=True)
class Gates:
    max_deviation: float = 0.0050     # maxDeviationBps 50
    max_slippage: float = 0.0100      # maxSlippageBps 100
    fee: float = 0.0030               # the 0.30% V3 tier
    min_lot_usdg: float = 5.0


def treasury_sell(pool: Pool, p: float, offered_stock: float, g: Gates) -> tuple[float, float, bool]:
    """`_swapBounded(buy=false)`: limit p*(1-slip); average must clear p*(1-slip-fee). returns (spent, got, ok)"""
    spent, got = pool.sell_stock(offered_stock, math.sqrt(p * (1 - g.max_slippage)))
    ok = got >= spent * p * (1 - g.max_slippage - g.fee) and spent > 0 and got > 0
    return spent, got, ok


def treasury_buy(pool: Pool, p: float, offered_usdg: float, g: Gates) -> tuple[float, float, bool]:
    spent, got = pool.buy_stock(offered_usdg, math.sqrt(p * (1 + g.max_slippage)))
    ok = got * p >= spent * (1 - g.max_slippage - g.fee) and spent > 0 and got > 0
    return spent, got, ok


def sandwich_sell(p: float, depth: float, max_trade: float, g: Gates, push: float | None = None) -> dict:
    """the treasury is overweight and will sell `max_trade` USDG of stock at the oracle price p"""
    push = g.max_deviation if push is None else push
    offered = max_trade / p                                                   # `_ruleStockFor(capUsdg, p)`
    # -- control: nobody pushes
    ctl = Pool.with_depth(p, depth, g.fee)
    spent0, got0, ok0 = treasury_sell(ctl, p, offered, g)
    # -- attack: push to the gate's edge, execute, unwind
    pool = Pool.with_depth(p, depth, g.fee)
    pushed_usdg = 0.0; pushed_stock = 0.0
    if push > 0:
        pushed_stock = pool.sell_exact_stock_for(pool.L * (pool.sqrt_p - math.sqrt(p * (1 - push))))
        pushed_usdg = pool.L * (math.sqrt(p) - pool.sqrt_p)
    spent1, got1, ok1 = treasury_sell(pool, p, offered, g)
    unwind_usdg = pool.buy_exact_stock(pushed_stock) if pushed_stock else 0.0
    attacker = pushed_usdg - unwind_usdg
    return dict(
        control_spent=spent0, control_got=got0, control_ok=ok0, control_cost=spent0 * p - got0,
        spent=spent1, got=got1, ok=ok1, cost=spent1 * p - got1,
        fill_short=spent1 < offered - 1e-12, turnover=spent1 * p,
        attacker_pnl=attacker, push_stock=pushed_stock,
        extra_cost=(spent1 * p - got1) - (spent1 / max(spent0, 1e-18)) * (spent0 * p - got0),
        end_price=pool.price,
    )


def sandwich_buy(p: float, depth: float, max_trade: float, g: Gates, push: float | None = None) -> dict:
    push = g.max_deviation if push is None else push
    ctl = Pool.with_depth(p, depth, g.fee)
    spent0, got0, ok0 = treasury_buy(ctl, p, max_trade, g)
    pool = Pool.with_depth(p, depth, g.fee)
    pushed_usdg = 0.0; pushed_stock = 0.0
    if push > 0:
        target = math.sqrt(p * (1 + push))
        pushed_usdg, pushed_stock = pool.buy_stock(pool.L * (target - pool.sqrt_p) / (1 - g.fee) + 1e-15, target)
    spent1, got1, ok1 = treasury_buy(pool, p, max_trade, g)
    unwind_usdg = 0.0
    if pushed_stock:
        s, unwind_usdg = pool.sell_stock(pushed_stock, 1e-9)
    attacker = unwind_usdg - pushed_usdg
    return dict(control_spent=spent0, control_got=got0, control_ok=ok0, control_cost=spent0 - got0 * p,
                spent=spent1, got=got1, ok=ok1, cost=spent1 - got1 * p, fill_short=spent1 < max_trade - 1e-9,
                turnover=spent1, attacker_pnl=attacker, push_stock=pushed_stock,
                extra_cost=(spent1 - got1 * p) - (spent1 / max(spent0, 1e-18)) * (spent0 - got0 * p),
                end_price=pool.price)


def trigger_move(target: float, band: float) -> float:
    """the stock move from target that first puts the stock share outside the band: s(x) = t(1+x)/(1+tx)"""
    return band / (target * (1 - target - band))


def donation_to_cross(total: float, target: float, band: float) -> float:
    """USDG value of stock an attacker must GIVE the treasury, sitting exactly at target, to push it over the band"""
    return band * total / (1 - target - band)


def table(header, rows):
    w = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    line = lambda r: "| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"
    return "\n".join([line(header), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows])


def main():
    g = Gates()
    p = 100.0
    print("Gates: deviation 50 bps, slippage 100 bps, fee 30 bps. Oracle p = $100. Attacker pushes spot to the gate's edge,\n"
          "calls execute(), unwinds in the same block. 'extra cost' is the treasury's cost beyond an unmanipulated fill of the\n"
          "same size; 'bound' is the (slip+fee) floor the contract enforces on the realised average.\n")
    for label, gg in (("30 bps pool, gates 50/100 (rehearsal defaults)", Gates()),
                      ("5 bps pool, gates 50/100", Gates(fee=0.0005)),
                      ("5 bps pool, gates 20/50 (the V2_SANDWICH_FORK.md listing)", Gates(fee=0.0005, max_deviation=0.002, max_slippage=0.005))):
        for side, fn in (("treasury SELLS (overweight)", sandwich_sell), ("treasury BUYS (underweight)", sandwich_buy)):
            rows = []
            for depth in (3_300, 10_000, 55_000, 250_000):
                for max_trade in (100, 500, 2_000, 10_000):
                    r = fn(p, depth, max_trade, gg)
                    rows.append([f"${depth:,}", f"${max_trade:,}", f"${r['turnover']:,.0f}" + (" (short)" if r["fill_short"] else ""),
                                 f"{r['control_cost'] / r['turnover'] * 1e4:.0f} bps" if r["turnover"] else "-",
                                 f"{r['cost'] / r['turnover'] * 1e4:.0f} bps" if r["turnover"] else "-",
                                 f"{(gg.max_slippage + gg.fee) * 1e4:.0f} bps",
                                 f"${r['extra_cost']:,.2f}", f"${r['attacker_pnl']:,.2f}",
                                 "yes" if r["attacker_pnl"] > 0 else "no", "ok" if r["ok"] else "REVERT Slippage"])
            print(f"### {label} -- {side}: one action, atomic sandwich at the deviation gate\n")
            print(table(["depth ($/1%)", "maxTrade", "filled", "cost, no push", "cost, pushed", "bound", "extra cost", "attacker P&L",
                         "profitable?", "avg check"], rows))
            print()

    print("### The same sell, but the pool is ALREADY at the gate's edge when execute() is called (no push to pay for):\n"
          "the caller just waits for a moment when spot lags the feed by 50 bps, then executes and arbs the pool back.\n")
    rows = []
    for depth in (3_300, 10_000, 55_000):
        for max_trade in (100, 500, 2_000):
            # a pool sitting 50 bps low: start the pool there, no push cost; attacker's gain = the arb back to oracle
            pool = Pool.with_depth(p * (1 - g.max_deviation), depth, g.fee)
            spent, got, ok = treasury_sell(pool, p, max_trade / p, g)
            # arb: buy stock until the pool is back at p*(1-0.005)
            usdg_in, stock_out = pool.buy_stock(1e12, math.sqrt(p * (1 - g.max_deviation)))
            arb = stock_out * p * (1 - g.max_deviation) - usdg_in           # marked at the pre-call pool price
            rows.append([f"${depth:,}", f"${max_trade:,}", f"${spent * p:,.0f}", f"{(spent * p - got) / (spent * p) * 1e4:.0f} bps",
                         f"${arb:,.2f}"])
    print(table(["depth ($/1%)", "maxTrade", "filled", "treasury cost vs oracle", "arb gain (marked at pool)"], rows))
    print()

    print("### Deadband -> the stock move that first triggers an action, and what one action costs in bps of treasury value\n")
    rows = []
    for t in (0.5, 0.8):
        for b_bps in (1, 10, 100, 500):
            b = b_bps / 1e4
            x = trigger_move(t, b)
            action = b                                   # first action sells the excess: ~b of total value
            rows.append([f"{t:.0%}", f"{b_bps} bps", f"{x * 100:.2f}%", f"{action * 1e4:.0f} bps of value",
                         f"{action * (g.max_slippage + g.fee) * 1e4:.2f} bps of value", f"{action * 0.0035 * 1e4:.3f} bps of value"])
    print(table(["target", "deadband", "trigger move", "action size", "worst cost (130 bps of it)", "typical (35 bps)"], rows))
    print("\nA Chainlink equity feed prints on a 0.5% move. Any deadband whose trigger move is under 0.5% fires on EVERY print;\n"
          "at target 50% that is every deadband under ~12 bps. At 100 bps the feed must move 4.1% between actions.\n")

    print("### Donation as a trigger: treasury at target, attacker gives stock to cross the band, then sandwiches the sell\n")
    rows = []
    for total in (20_000, 100_000):
        for b_bps in (100, 500):
            b = b_bps / 1e4
            d = donation_to_cross(total, 0.5, b)
            excess = (0.5 * total + d) - 0.5 * (total + d)          # what the engine will sell, uncapped
            gain = sandwich_sell(p, 3_300, min(excess, 2_000), g)["attacker_pnl"]
            rows.append([f"${total:,}", f"{b_bps} bps", f"${d:,.0f}", f"${excess:,.0f}", f"${gain:,.2f}", f"${gain - d:,.0f}"])
    print(table(["treasury value", "deadband", "donation needed", "engine sells", "sandwich gain (thin pool, maxTrade 2000)", "net"], rows))
    print("\nA donation is irrevocable and the sandwich returns at most ~1% of one capped action; the attacker who wants the\n"
          "timing simply calls execute() when it is already due -- it is permissionless and pays no bounty.\n")

    print("### Per-day bound: 130 bps of the turnover the config allows in one UTC day, doubled across the epoch boundary\n")
    rows = []
    for max_trade, max_daily, cooldown in ((100, 500, 60), (2_000, 10_000, 60), (2_000, 2_000 * 24, 3_600), (2_000, 10**18, 1)):
        by_cd = max_trade * 86_400 / cooldown
        day = min(max_daily, by_cd)
        rows.append([f"${max_trade:,}", f"${max_daily:,.0f}" if max_daily < 1e12 else "unbounded", f"{cooldown}s",
                     f"${day:,.0f}" if day < 1e12 else "unbounded", "maxDaily" if max_daily <= by_cd else "cooldown",
                     f"${day * 0.013:,.0f}/day" if day < 1e12 else "unbounded",
                     f"${2 * day * 0.013:,.0f}" if day < 1e12 else "unbounded"])
    print(table(["maxTrade", "maxDaily", "cooldown", "turnover/day", "binding", "worst loss/day", "worst loss, 24h window straddling 00:00 UTC"], rows))
    print("\nWith cooldown 1 s and maxDaily unbounded nothing but the oracle's print count bounds the day: each print that\n"
          "crosses the band is one capped action, so 130 bps x maxTrade x prints/day.\n")


if __name__ == "__main__":
    main()
