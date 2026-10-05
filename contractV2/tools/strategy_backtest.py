#!/usr/bin/env python3
"""Replay the treasury rules on a price series and count what each would do.

Three rules: the ordinary lot rule (kind 0), the cycle rule (the lot rule plus a recovery buy after a sale) and
the percentage rebalance (schema 3, with realised-net-income accounting). Models of the rules, not the contracts:
one keeper visit per price, repeating execute() until nothing is due, then buy-backs as the cooldown allows.
It was checked against the contracts for three price paths, two on a fork and one for the cycle treasury in
the repository's own fixture (tools/tests/test_strategy_backtest.py).

Not modelled: the token pool (so no burned amounts and no impact cap on a buy-back), trade tax and LP fees
arriving, user order flow, stock-pool depth (slippage is one assumed number), stops, closures and gaps between
observations. Read the counts as what the price path alone would trigger.
"""
import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "backtest"
DATA = DATA_DIR / "hourly" / "TSLA.csv"
MAX_LOTS = 128
TICKERS = ("TSLA", "ORCL", "COIN", "CRWV", "MSTR", "NVDA", "AMD", "PLTR", "MU", "SNDK")


def load(path=DATA):
    with open(path) as f:
        return [(int(r["timestamp"]), float(r["close"])) for r in csv.DictReader(f)]


def series_of(ticker, source="hourly"):
    """`hourly`: closes including extended hours. `feed`: every print of the stock's mainnet Chainlink feed."""
    return load(DATA_DIR / source / f"{ticker}.csv")


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
    cycle: bool = False             # HedgeFunV2CycleTreasury's one recovery buy after a sale
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
            if self.cycle and principal * p >= c.min_lot:     # a real sale of at least a lot re-arms the recovery
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


@dataclass
class Rebalance:
    """The percentage rebalance treasury: hold `target` of the tradable value in stock, trade back to it outside
    the band, at most a quarter of the cash or stock per action, and reserve `payout` of a sale's realised net
    gain for the buy-back after earlier realised losses are recovered."""
    target: float
    band: float
    payout: float
    costs: Costs = field(default_factory=Costs)
    buy_bps: float = 0.25
    sell_bps: float = 0.25
    daily_buy: float = 1.0
    daily_sell: float = 1.0
    stock: float = 0.0
    cash: float = 0.0
    avg_cost: float = 0.0
    buyback_stock: float = 0.0
    loss: float = 0.0
    day: int = -1
    basis: float = 0.0
    bought: float = 0.0
    sold: float = 0.0
    sells: int = 0
    buys: int = 0
    cost_usd: float = 0.0

    def execute(self, p, day):
        c = self.costs
        value = self.stock * p
        total = value + self.cash
        if total <= 0:
            return False
        if day != self.day:                               # the day's first action pins the basis of its budgets
            basis, bought, sold = total, 0.0, 0.0
        else:
            basis, bought, sold = self.basis, self.bought, self.sold
        if value > total * (self.target + self.band):
            remaining = basis * self.daily_sell - sold
            if remaining <= 0:
                return False
            offered = min((value - total * self.target) / p, self.stock * self.sell_bps, remaining / p)
            if offered * p < c.min_lot:
                return False
            cost = self.avg_cost
            withheld = (offered * (1 - cost / p) if p > cost else 0.0) * self.payout
            sale = offered - withheld
            out = sale * p * (1 - c.pool_fee - c.slippage)
            net = out * (1 - c.keeper)
            principal = sale * cost
            reserve = 0.0
            if net < principal:
                self.loss += principal - net
            elif net - principal <= self.loss:
                self.loss -= net - principal
            else:
                eligible, self.loss = net - principal - self.loss, 0.0
                if withheld and p > cost and self.payout:
                    reserve = min(withheld, eligible / (p - (p - cost) * self.payout) * self.payout)
            moved = sale + reserve
            if moved * p < c.min_lot:
                return False
            self.cost_usd += sale * p - net
            self.stock -= moved
            self.buyback_stock += reserve
            self.cash += net
            sold += moved * p
            self.sells += 1
        elif value < total * (self.target - self.band):
            remaining = basis * self.daily_buy - bought
            if remaining <= 0:
                return False
            offered = min(total * self.target - value, self.cash * self.buy_bps, remaining, self.cash)
            if offered < c.min_lot:
                return False
            retained = offered / p * (1 - c.pool_fee - c.slippage) * (1 - c.keeper)
            self.cost_usd += offered - retained * p
            self.avg_cost = (self.stock * self.avg_cost + offered) / (self.stock + retained)
            self.stock += retained
            self.cash -= offered
            bought += offered
            self.buys += 1
        else:
            return False
        self.day, self.basis, self.bought, self.sold = day, basis, bought, sold
        return True

    def nav(self, p):
        return (self.stock + self.buyback_stock) * p + self.cash


def run_rebalance(series, capital, target, band, payout, costs=None):
    first, last = series[0][1], series[-1][1]
    r = Rebalance(target, band, payout, costs or Costs(), stock=capital / first, avg_cost=first)
    bought_back, days = 0.0, set()
    for when, p in series[1:]:
        for _ in range(6):                                # the cooldown is ten minutes
            if not r.execute(p, when // 86400):
                break
        if r.buyback_stock > 0:
            bought_back += r.buyback_stock * p
            days.add(when // 86400)
            r.buyback_stock = 0.0
    nav = r.nav(last)
    return {"actions": r.sells + r.buys, "buyback_days": len(days), "buyback_pct": bought_back / capital * 100,
            "total_pct": ((nav + bought_back) / capital - 1) * 100, "nav_pct": (nav / capital - 1) * 100,
            "cost_usd": r.cost_usd, "treasury": r}


LOW = dict(pool_fee=0.0005, keeper=0.0010)
MATRIX = [  # label, runner -> (actions, bought back % of capital, NAV + buy-backs %)
    ("ordinary 3/6/3", lambda s, c: _lot(s, c, (0.03, 0.06, 0.03, 0.50), False)),
    ("ordinary 1/2/1", lambda s, c: _lot(s, c, (0.01, 0.02, 0.01, 0.50), False)),
    ("cycle 3/6/3", lambda s, c: _lot(s, c, (0.03, 0.06, 0.03, 0.50), True)),
    ("cycle 5/10/5", lambda s, c: _lot(s, c, (0.05, 0.10, 0.05, 0.20), True)),
    ("rebalance 70%", lambda s, c: _reb(s, c, 0.70)),
    ("rebalance 90%", lambda s, c: _reb(s, c, 0.90)),
]


def _lot(series, capital, rule, cycle):
    x = run(series, capital, *rule, costs=Costs(**LOW), cycle=cycle)
    return x["sells"] + x["dip_buys"] + x["recovery_buys"], x["buyback_pct"], x["total_pct"]


def _reb(series, capital, target):
    x = run_rebalance(series, capital, target, 0.01, 1.0, costs=Costs(**LOW))
    return x["actions"], x["buyback_pct"], x["total_pct"]


def matrix(source, capital):
    print(f"### every rule on every stock, {source} series, pool fee 0.05%, keeper 0.1%\n")
    print("Each cell: bought back as a share of capital / NAV + buy-backs / actions.\n")
    print("| stock | days | stock change | " + " | ".join(label for label, _ in MATRIX) + " |")
    print("|---|---:|---:|" + "---:|" * len(MATRIX))
    for ticker in TICKERS:
        s = series_of(ticker, source)
        days = len({when // 86400 for when, _ in s})
        cells = []
        for _, runner in MATRIX:
            actions, bought_back, total = runner(s, capital)
            cells.append(f"{bought_back:.0f}% / {total:+.0f}% / {actions}")
        print(f"| {ticker} | {days} | {(s[-1][1] / s[0][1] - 1) * 100:+.0f}% | " + " | ".join(cells) + " |")
    print()


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
    parser.add_argument("--matrix", action="store_true", help="every rule on every stock, both series")
    args = parser.parse_args()
    if args.matrix:
        matrix("hourly", args.capital)
        matrix("feed", args.capital)
        return
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
