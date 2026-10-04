#!/usr/bin/env python3
"""Replay the kind-0 lot rule on a price series and count what the treasury would do.

A model of the rule in HedgeFunTreasuryBase / HedgeFunV2Treasury / HedgeFunV2AllInTreasury, not the contracts:
one keeper visit per price, repeating execute() until nothing is due, then buy-backs as the cooldown allows.
It was checked against the contracts on a fork for one nine-step path (tools/tests/test_strategy_backtest.py).

Not modelled: the token pool (so no burned amounts and no impact cap on a buy-back), trade tax and LP fees
arriving, user order flow, stock-pool depth (slippage is one assumed number), stops, closures and gaps between
observations. Read the counts as what the price path alone would trigger.
"""
import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "tsla-hourly-2023-11_2026-10.csv"
MAX_LOTS = 128


def load(path=DATA):
    with open(path) as f:
        return [(int(r["timestamp"]), float(r["close"])) for r in csv.DictReader(f)]


@dataclass
class Costs:
    pool_fee: float = 0.0030        # the stock/USDG pool's fee tier
    keeper: float = 0.0050          # bountyBps
    slippage: float = 0.0005        # assumed, on top of the fee
    sell_chunk: float = 2000.0      # the listing's sellChunkUsdg
    min_lot: float = 5.0            # minLotUsdg
    buyback_chunk: float = 500.0    # buybackChunkUsdg, kind 0
    buyback_bps: int = 0            # the percentage kind: share of the waiting budget per call; 0 = fixed chunk
    buyback_cooldown: int = 60
    observation_seconds: int = 3600


@dataclass
class Lot:
    qty: float
    cost: float
    half: bool = False
    tp1_left: float = 0.0


@dataclass
class Treasury:
    tp1: float
    tp2: float
    dip: float
    buy_share: float
    costs: Costs = field(default_factory=Costs)
    cycle: bool = False             # HedgeFunV2CycleTreasury's one recovery buy after a sale; not checked on chain
    lots: list = field(default_factory=list)
    usdg: float = 0.0
    buyback_stock: float = 0.0
    last_sale: float = 0.0
    armed: float = 0.0
    sells: int = 0
    dip_buys: int = 0
    recovery_buys: int = 0
    buybacks: int = 0
    buyback_usd: float = 0.0
    cost_usd: float = 0.0
    buyback_days: set = field(default_factory=set)

    def execute(self, p):
        """One action in the contract's order: a due take-profit, else a due buy."""
        c = self.costs
        due = None
        for lot in self.lots:
            second = self.tp2 == 0 or lot.half
            trigger = self.tp2 if (second and self.tp2) else self.tp1
            if p >= lot.cost * (1 + trigger):
                key = (not second, lot.cost, -lot.qty)       # a half-sold lot first, then the cheapest
                if due is None or key < due[0]:
                    due = (key, lot, second)
        if due:
            _, lot, second = due
            q = c.sell_chunk / p
            left = 0.0
            if not second:
                left = lot.tp1_left or lot.qty / 2
                q = min(q, left)
            else:
                q = min(q, lot.qty)
            principal = q * lot.cost / p                      # sold for USDG; the rest of q is profit, kept in stock
            got = principal * p * (1 - c.pool_fee - c.slippage)
            profit = q - principal
            reward = profit * c.keeper
            self.cost_usd += principal * p * (c.pool_fee + c.slippage) + reward * p
            self.buyback_stock += profit - reward
            self.usdg += got
            if not second:
                lot.tp1_left = left - q
                if lot.tp1_left <= 1e-12:
                    lot.half, lot.tp1_left = True, 0.0
            lot.qty -= q
            if lot.qty <= 1e-12:
                self.lots.remove(lot)
            self.last_sale = p
            self.sells += 1
            if self.cycle and got >= c.min_lot:
                self.armed = p
            return True
        dip_due = self.last_sale and p <= self.last_sale * (1 - self.dip)
        recovery_due = self.cycle and self.armed and p >= self.armed * (1 + self.dip)
        if (dip_due or recovery_due) and len(self.lots) < MAX_LOTS:
            spend = self.usdg * self.buy_share
            if not dip_due:
                spend = min(spend, c.sell_chunk)
            if spend < c.min_lot:
                return False
            swap_in = spend * (1 - c.keeper)
            got = swap_in / p * (1 - c.pool_fee - c.slippage)
            reward = swap_in * c.keeper
            self.cost_usd += swap_in * (c.pool_fee + c.slippage) + reward
            self.usdg -= swap_in + reward
            self.lots.append(Lot(got, swap_in / got))
            self.last_sale, self.armed = p, 0.0
            if dip_due:
                self.dip_buys += 1
            else:
                self.recovery_buys += 1
            return True
        return False

    def buy_back(self, p, day):
        c = self.costs
        for _ in range(max(1, c.observation_seconds // c.buyback_cooldown)):
            if self.buyback_stock * p < 0.01:
                break
            lot = c.min_lot / p
            offer = max(self.buyback_stock * c.buyback_bps / 10_000, lot) if c.buyback_bps else c.buyback_chunk / p
            amount = min(self.buyback_stock, offer)
            self.buyback_stock -= amount
            self.buyback_usd += amount * p
            self.buybacks += 1
            self.buyback_days.add(day)

    def nav(self, p):
        return (sum(lot.qty for lot in self.lots) + self.buyback_stock) * p + self.usdg


def run(series, capital, tp1, tp2, dip, buy_share, costs=None, cycle=False):
    t = Treasury(tp1, tp2, dip, buy_share, costs or Costs(), cycle)
    first = series[0][1]
    t.lots.append(Lot(capital / first, first))               # the graduation stock, booked at the first price
    t.last_sale = first
    for when, p in series[1:]:
        for _ in range(200):
            if not t.execute(p):
                break
        t.buy_back(p, when // 86400)
    last = series[-1][1]
    days = len({when // 86400 for when, _ in series})
    return {
        "sells": t.sells, "dip_buys": t.dip_buys, "recovery_buys": t.recovery_buys, "buybacks": t.buybacks,
        "buyback_days": len(t.buyback_days), "days": days, "buyback_usd": t.buyback_usd,
        "buyback_pct": t.buyback_usd / capital * 100, "cost_usd": t.cost_usd,
        "nav_pct": (t.nav(last) / capital - 1) * 100,
        "total_pct": ((t.nav(last) + t.buyback_usd) / capital - 1) * 100,
        "stock_pct": (last / first - 1) * 100, "treasury": t,
    }


RULES = [  # tp1, tp2, dip, share of cash per buy
    (0.05, 0.10, 0.05, 0.20), (0.03, 0.06, 0.03, 0.50), (0.02, 0.04, 0.02, 0.50),
    (0.01, 0.02, 0.01, 0.50), (0.005, 0.01, 0.005, 0.50),
]


def name(rule):
    tp1, tp2, dip, share = rule
    return f"{tp1 * 100:g}% / {tp2 * 100:g}% / {dip * 100:g}%, {share * 100:g}%"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(DATA))
    parser.add_argument("--capital", type=float, default=18_000)
    args = parser.parse_args()
    series = load(args.data)
    days = len({when // 86400 for when, _ in series})
    print(f"{len(series)} prices over {days} trading days, stock {(series[-1][1] / series[0][1] - 1) * 100:+.1f}%, "
          f"capital {args.capital:,.0f} USD\n")
    for fee, keeper in ((0.0030, 0.0050), (0.0030, 0.0010), (0.0005, 0.0010), (0.0005, 0.0005)):
        print(f"### pool fee {fee * 100:g}%, keeper {keeper * 100:g}%\n")
        print("| take-profit 1 / 2 / dip, buy share | sells | buys | buy-backs | days with a buy-back | bought back (USD) "
              "| of capital | costs (USD) | treasury NAV | NAV + buy-backs |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for rule in RULES:
            x = run(series, args.capital, *rule, costs=Costs(pool_fee=fee, keeper=keeper))
            print(f"| {name(rule)} | {x['sells']} | {x['dip_buys']} | {x['buybacks']} | {x['buyback_days']} "
                  f"| {x['buyback_usd']:,.0f} | {x['buyback_pct']:.0f}% | {x['cost_usd']:,.0f} "
                  f"| {x['nav_pct']:+.1f}% | {x['total_pct']:+.1f}% |")
        print()
    print("### buy-back sizing, 1% / 2% / 1%, 50%, pool fee 0.05%, keeper 0.1%\n")
    print("| capital | sizing | buy-backs | per trading day | days with a buy-back | bought back (USD) |")
    print("|---:|---|---:|---:|---:|---:|")
    for capital in (args.capital, args.capital * 10):
        for label, extra in (("fixed 500 USDG (kind 0)", {}), ("10% of the budget", {"buyback_bps": 1000})):
            x = run(series, capital, 0.01, 0.02, 0.01, 0.50, costs=Costs(pool_fee=0.0005, keeper=0.0010, **extra))
            print(f"| {capital:,.0f} | {label} | {x['buybacks']} | {x['buybacks'] / days:.1f} "
                  f"| {x['buyback_days']} of {days} | {x['buyback_usd']:,.0f} |")


if __name__ == "__main__":
    main()
