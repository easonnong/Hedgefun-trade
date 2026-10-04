"""What a stock that trends does to a V2 launch: the raise, the strategy treasury, and the token's own price.

Three stages of one launch, driven over a synthetic stock price path -- constant drift per day, with or without
volatility -- instead of a history, so that the direction is the experiment rather than an accident of the window:

  1. pre-graduation: the graduation target is fixed in STOCK units (`Rg`), so its dollar cost and what early buyers
     hold both move with the stock while the raise fills;
  2. post-graduation: the treasury's share of the raise is booked as its first lot at the graduation price, sell tax
     and stock-side LP fees flow in, and `HedgeFunTreasuryBase`'s rule (stop, then take-profit, then dip, as
     `HedgeFunV2Treasury.execute()` orders them) runs bar by bar -- through the SAME `Ledger` that
     `tools/rule_backtest.py` replays histories with;
  3. the token's price in the stock, which is the only price the pool knows, and its dollar price, which is that
     times the stock.

Pure Python, deterministic (a seeded, normalised shock sequence), no network. Amounts are human units (FUN, stock,
USDG), not raw token units; the V4 pool is continuous `x * y = k` with the LP fee on the input and the hook tax on the
output, exactly as `lab/model.py` approximates it. Volume is an INPUT, swept explicitly. None of this is a forecast.

    python3 -m lab.trend            # the tables in docs/V2_TREND_SCENARIOS.md
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
from dataclasses import dataclass, replace
from pathlib import Path

from lab.model import simulate

ROOT = Path(__file__).resolve().parents[1]
STEPS_PER_DAY = 24
BUYBACK_TWAP_WINDOW = 600            # HedgeFunTreasuryBase.BUYBACK_TWAP_WINDOW, seconds
MAX_STRATEGY_LOTS = 128              # HedgeFunV2Treasury.MAX_STRATEGY_LOTS


def _rule_backtest():
    """`tools/` is not a package; load the replay tool by path so its `Ledger` is the one and only rule."""
    spec = importlib.util.spec_from_file_location("hedgefun_rule_backtest", ROOT / "tools" / "rule_backtest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Ledger = _rule_backtest().Ledger


# ------------------------------------------------------------------------------------------------ inputs
def stock_path(days: int, drift: float, vol: float = 0.0, *, start: float = 100.0, seed: int = 7,
               steps_per_day: int = STEPS_PER_DAY) -> list[float]:
    """Hourly stock prices over `days`, with a constant `drift` per day and a daily volatility `vol`.

    The shocks are normalised to mean zero and unit variance over the sample, so a path carries EXACTLY the drift
    asked for -- a flat path ends where it started, however much it wobbles -- and the seed decides only the shape.
    """
    if days < 0 or steps_per_day <= 0 or start <= 0 or drift <= -1 or vol < 0:
        raise ValueError("bad path parameters")
    n = days * steps_per_day
    mu = math.log1p(drift) / steps_per_day
    if n == 0:
        return [start]
    if vol == 0:
        return [start * math.exp(mu * i) for i in range(n + 1)]
    rng = random.Random(seed)
    z = [rng.gauss(0.0, 1.0) for _ in range(n)]
    if n > 1:
        mean = sum(z) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in z) / n)
        z = [(x - mean) / sd for x in z]
    else:
        z = [0.0]
    sigma = vol / math.sqrt(steps_per_day)
    out = [start]
    for x in z:
        out.append(out[-1] * math.exp(mu + sigma * x))
    return out


@dataclass(frozen=True)
class Curve:
    """A launch's frozen terms, in the units `docs/V2_BONDING_CURVE.md` uses. `opening_fdv_stock` is `V`, the virtual
    stock reserve (`openPrice x supply`): the opening FDV in stock units. Production listings open near $10k FDV."""
    supply: float = 1_000_000_000.0
    opening_fdv_stock: float = 100.0
    sale_bps: int = 8000
    lp_bps: int = 5000
    tax_bps: int = 1000
    lp_fee_bps: int = 30
    protocol_bps: int = 2000         # of the stock-denominated sell tax (factory default)
    creator_bps: int = 1000          # the creator's pick, at most maxCreatorBps = 3000

    @property
    def tax(self) -> float: return self.tax_bps / 10_000

    @property
    def lp_fee(self) -> float: return self.lp_fee_bps / 10_000

    @property
    def treasury_share(self) -> float: return 1 - (self.protocol_bps + self.creator_bps) / 10_000

    def graduation(self) -> dict:
        """the split at graduation, from `lab.model.simulate`, plus the curve constants it leaves implicit"""
        g = simulate({"supply": self.supply, "virtual_stock": self.opening_fdv_stock, "sale_bps": self.sale_bps,
                      "lp_bps": self.lp_bps, "lp_fee_bps": self.lp_fee_bps, "trade_tax_bps": self.tax_bps})["graduation"]
        v, s = self.opening_fdv_stock, self.supply
        tmin = s * (1 - self.sale_bps / 10_000)
        g.update(virtual_stock=v, invariant=s * v, tmin=tmin, yg=s * v / tmin, open_price=v / s,
                 open_to_terminal=g["terminal_price"] / (v / s),
                 supply_after=g["lp_token"] + g["sold_user_token_estimate"])
        return g

    def tokens_between(self, r0: float, r1: float) -> float:
        """gross tokens the curve hands out while its real reserve goes from `r0` to `r1` stock"""
        k, v = self.supply * self.opening_fdv_stock, self.opening_fdv_stock
        return k / (v + r0) - k / (v + r1)


@dataclass(frozen=True)
class Rule:
    """A creator's rule and the factory defaults around it. `tp2` is twice `tp1`, as every template and the replay
    tool assume. `cost` is the stock<->USDG swap's pool fee plus slippage; `bounty`, `min_lot_usdg`,
    `buyback_chunk_usdg`, `buyback_cooldown` and `max_buyback_impact` are `RehearseV2Launchpad.s.sol`'s defaults."""
    name: str = "trend_holder"
    tp1: float = 0.30
    dip: float = 0.03
    stop: float = 0.0
    lot: float = 0.50
    cost: float = 0.0035
    bounty: float = 0.005
    min_lot_usdg: float = 5.0
    buyback_chunk_usdg: float = 500.0
    buyback_cooldown: int = 60
    max_buyback_impact: float = 0.03


TEMPLATES = {
    "trend_holder": Rule("trend_holder", tp1=0.30, dip=0.03, stop=0.0, lot=0.50),       # LAUNCH_KIT's default
    "scalper": Rule("scalper", tp1=0.05, dip=0.05, stop=0.0, lot=0.20),                  # rule-backtest's "shipped 5/5"
    "range_grid": Rule("range_grid", tp1=0.20, dip=0.15, stop=0.0, lot=0.20),
    "tp_stop": Rule("tp_stop", tp1=0.15, dip=0.10, stop=0.12, lot=0.50),
}

# (from, to) as fractions of the raise, in fill order
COHORTS = (("first 1%", 0.0, 0.01), ("first 5%", 0.0, 0.05), ("first 25%", 0.0, 0.25),
           ("middle 25%", 0.375, 0.625), ("last 5%", 0.95, 1.0))


# ------------------------------------------------------------------------------------------------ stage 1
def pregraduation(curve: Curve, path: list[float], fill_days: int, cohorts=COHORTS) -> dict:
    """The raise fills at a constant rate in STOCK over `fill_days`, buying at each step's price on `path`.

    Returns the dollar cost of graduating against the same raise at the opening price, and for each buyer cohort what
    it paid, what its tokens are worth at graduation on the curve (stock and dollars) and what it would get dumping
    them alone into the fresh V4 pool. Paper value is the terminal curve price, which is also the V4 opening price.
    """
    n = fill_days * STEPS_PER_DAY
    if n <= 0 or len(path) < n + 1:
        raise ValueError("path must cover the fill")
    g = curve.graduation()
    rg, terminal, p_grad = g["real_stock"], g["terminal_price"], path[n]
    step_stock = rg / n
    usd_cost = sum(step_stock * path[i] for i in range(1, n + 1))
    out = dict(rg=rg, fill_days=fill_days, usd_cost=usd_cost, usd_cost_flat=rg * path[0], p_open=path[0], p_grad=p_grad,
               stock_multiple=p_grad / path[0], cohorts=[])
    for label, a, b in cohorts:
        stock_paid = rg * (b - a)
        usd_paid = 0.0
        for i in range(1, n + 1):
            lo, hi = max(a, (i - 1) / n), min(b, i / n)
            if hi > lo:
                usd_paid += (hi - lo) * rg * path[i]
        gross = curve.tokens_between(a * rg, b * rg)
        net = gross * (1 - curve.tax)
        paper_stock = net * terminal
        # dumping alone into the fresh pool: LP fee on the FUN input, hook tax on the stock output
        eff = net * (1 - curve.lp_fee)
        dump_stock = g["lp_stock"] * eff / (g["lp_token"] + eff) * (1 - curve.tax)
        out["cohorts"].append(dict(
            label=label, stock_paid=stock_paid, usd_paid=usd_paid, tokens=net,
            share_of_supply=net / g["supply_after"],
            paper_stock=paper_stock, paper_multiple_stock=paper_stock / stock_paid,
            paper_usd=paper_stock * p_grad, paper_multiple_usd=paper_stock * p_grad / usd_paid,
            dump_stock=dump_stock, dump_multiple_stock=dump_stock / stock_paid,
            dump_multiple_usd=dump_stock * p_grad / usd_paid,
            price_after_dump=(g["lp_stock"] - dump_stock / (1 - curve.tax)) / (g["lp_token"] + eff) / terminal))
    return out


def curve_round_trip(curve: Curve, *, at: float = 0.5, size: float = 0.01) -> dict:
    """buy `size` of the raise when the raise is `at` full, then sell it straight back: what the round trip costs"""
    g = curve.graduation()
    rg, v, k = g["real_stock"], curve.opening_fdv_stock, curve.supply * curve.opening_fdv_stock
    r0 = at * rg
    t0 = k / (v + r0)
    s = size * rg
    t1 = k / (v + r0 + s)
    net = (t0 - t1) * (1 - curve.tax)
    gross_out = (v + r0 + s) - k / (t1 + net)
    stock_back = gross_out * (1 - curve.tax)
    return dict(tax_bps=curve.tax_bps, stock_in=s, stock_back=stock_back, loss=1 - stock_back / s,
                loss_flat_tax=1 - (1 - curve.tax) ** 2)


# ------------------------------------------------------------------------------------------------ stage 2 and 3
def run_post_graduation(curve: Curve, rule: Rule, path: list[float], volume: float, *,
                        buybacks: bool = True, booking: str = "daily", burn_source: str = "pool") -> dict:
    """Graduate at `path[0]`, then run the pool, the fee flows and the rule over the rest of `path`.

    `volume` is the FUN pool's daily volume as a fraction of the raise `Rg`, in stock units, both legs together. It is
    taken as round trips -- a buy, then a sale of the same size -- so nobody accumulates and every move in the
    token's stock price is the mechanism's: the buy tax burn, the FUN-side LP fee burn and the treasury's buy-backs.
    `burn_source` says whose tokens the buy tax burned: "pool" -- the seller sells back only what the buy delivered,
    so the burned tokens are ones the pool paid out and never gets back (the pool's FUN falls, its price rises); or
    "float" -- the seller also sells the burned amount out of the float, so the pool ends each round trip where it
    began and only buy-backs move it. The truth is between the two. `booking` is the keeper's cadence for `book()`
    ("daily" or "hourly"); a successful `execute()` also books, as on chain. Buy-backs are paced by the chunk, the
    cooldown and the impact cap off a 10-minute mean, and refused below `minLotUsdg`, as in
    `HedgeFunTreasuryBase.buyback`.
    """
    if volume < 0 or len(path) < 2 or booking not in ("daily", "hourly") or burn_source not in ("pool", "float"):
        raise ValueError("bad run parameters")
    g = curve.graduation()
    f, t, share = curve.lp_fee, curve.tax, curve.treasury_share
    x, y = g["lp_token"], g["lp_stock"]                                    # FUN, stock in the pool
    supply = supply0 = g["supply_after"]
    price0 = y / x
    ledger = Ledger()
    p0 = path[0]
    ledger.book(g["treasury_stock"], p0)
    budget = 0.0                                                            # buybackStock, in stock
    unbooked = tax_received = lp_fee_stock = 0.0
    spent = spent_usd = pending_profit = 0.0
    burned_tax = burned_lp = burned_buyback = 0.0
    volume_usd = stock_in = stock_to_sellers = stock_to_others = bounty_fun = 0.0
    lots_full_steps = 0
    step_stock = volume * g["real_stock"] / 2 / STEPS_PER_DAY
    chunk_per_hour = 3600 / max(rule.buyback_cooldown, 1)
    pushes_per_hour = 3600 / BUYBACK_TWAP_WINDOW

    def book_now(p):
        nonlocal unbooked, tax_received
        if unbooked * p >= rule.min_lot_usdg and len(ledger.lots) < MAX_STRATEGY_LOTS:
            ledger.book(unbooked, p); tax_received += unbooked; unbooked = 0.0

    for i in range(1, len(path)):
        p = path[i]
        # -- the pool's hour: a buy of stock, then a sale of the FUN it delivered (or of that plus the burn, from the float)
        if step_stock > 0:
            fee = step_stock * f; lp_fee_stock += fee; budget += fee; stock_in += step_stock
            eff = step_stock - fee
            out = x * eff / (y + eff); y += eff; x -= out
            tax_fun = out * t; burned_tax += tax_fun; supply -= tax_fun
            q = out - tax_fun if burn_source == "pool" else out
            fee_fun = q * f; burned_lp += fee_fun; supply -= fee_fun
            eff = q - fee_fun
            h = y * eff / (x + eff); x += eff; y -= h
            unbooked += h * t * share; stock_to_others += h * t * (1 - share); stock_to_sellers += h * (1 - t)
            volume_usd += (step_stock + h) * p
        # -- the keeper: book, then execute (stop, take-profit, dip); a successful execute() books too
        if booking == "hourly" or i % STEPS_PER_DAY == 0:
            book_now(p)
        acted = (ledger.n_tp, ledger.n_stop, ledger.n_dip)
        ledger.step(p, rule.tp1, rule.dip, rule.stop, rule.lot, rule.cost, rule.bounty, rule.min_lot_usdg, MAX_STRATEGY_LOTS)
        if acted != (ledger.n_tp, ledger.n_stop, ledger.n_dip):
            book_now(p)
        if len(ledger.lots) >= MAX_STRATEGY_LOTS:
            lots_full_steps += 1
        new_profit = ledger.buyback - pending_profit; pending_profit = ledger.buyback
        budget += new_profit
        # -- the buy-back: chunked, cooled down, impact-capped off the pool's own mean, refused below a lot
        if buybacks and budget > 0:
            want = min(budget, chunk_per_hour * rule.buyback_chunk_usdg / p)
            cap = y * ((1 + rule.max_buyback_impact) ** (pushes_per_hour / 2) - 1)
            spend = min(want, cap)
            if spend >= min(want, rule.min_lot_usdg / p) and spend > 0:
                fee = spend * f
                eff = spend - fee
                out = x * eff / (y + eff); y += eff; x -= out
                bounty = out * rule.bounty; bounty_fun += bounty
                burned_buyback += out - bounty; supply -= out - bounty
                budget -= spend; budget += fee
                spent += spend; spent_usd += spend * p
    p_end = path[-1]
    received = ledger.received
    held = ledger.held()
    price_end = y / x
    treasury_stock_equivalent = held + unbooked + budget + ledger.reserve / p_end
    return dict(
        days=(len(path) - 1) / STEPS_PER_DAY, p_start=p0, p_end=p_end, stock_multiple=p_end / p0,
        graduation_lot=g["treasury_stock"], tax_received=tax_received, unbooked_end=unbooked,
        lots_end=len(ledger.lots), lots_full_steps=lots_full_steps,
        tp_fired=ledger.n_tp > 0, n_tp=ledger.n_tp, n_stop=ledger.n_stop, n_dip=ledger.n_dip,
        held_stock=held, reserve_usdg=ledger.reserve,
        profit_to_buyback=ledger.buyback, lp_fee_stock=lp_fee_stock,
        buyback_spent_stock=spent, buyback_spent_usd=spent_usd, buyback_pending_stock=budget,
        burned_buyback=burned_buyback, burned_tax=burned_tax, burned_lp=burned_lp,
        supply_start=supply0, supply_end=supply,
        burned_buyback_share=burned_buyback / supply0, burned_tax_share=burned_tax / supply0,
        burned_lp_share=burned_lp / supply0, burned_share=(supply0 - supply) / supply0,
        multiple=ledger.value(p_end) / received if received else 1.0,
        treasury_usd_start=g["treasury_stock"] * p0,
        treasury_usd_end=treasury_stock_equivalent * p_end,
        fun_price_stock_start=price0, fun_price_stock_end=price_end,
        fun_price_stock_change=price_end / price0 - 1,
        fun_price_usd_change=(price_end * p_end) / (price0 * p0) - 1,
        volume_stock_daily=volume * g["real_stock"], volume_usd=volume_usd,
        pool_stock_end=y, pool_fun_end=x, stock_in_volume=stock_in, stock_to_sellers=stock_to_sellers,
        stock_to_protocol_creator=stock_to_others, bounty_fun=bounty_fun, burn_source=burn_source,
    )


def fun_price_decomposition(curve: Curve, rule: Rule, path: list[float], volume: float) -> dict:
    """the token's price change in the stock, split into what the burns from trading did and what buy-backs added,
    under both readings of whose tokens the buy tax burned (see `run_post_graduation`)"""
    pool_off = run_post_graduation(curve, rule, path, volume, buybacks=False, burn_source="pool")
    pool_on = run_post_graduation(curve, rule, path, volume, buybacks=True, burn_source="pool")
    float_off = run_post_graduation(curve, rule, path, volume, buybacks=False, burn_source="float")
    float_on = run_post_graduation(curve, rule, path, volume, buybacks=True, burn_source="float")
    return dict(stock_change=pool_on["stock_multiple"] - 1,
                burns_only=pool_off["fun_price_stock_change"],
                buyback_added=pool_on["fun_price_stock_change"] - pool_off["fun_price_stock_change"],
                with_buybacks=pool_on["fun_price_stock_change"],
                usd_change=pool_on["fun_price_usd_change"],
                float_burns_only=float_off["fun_price_stock_change"],
                float_with_buybacks=float_on["fun_price_stock_change"],
                float_usd_change=float_on["fun_price_usd_change"],
                burned_share=pool_on["burned_share"], burned_tax_share=pool_on["burned_tax_share"],
                burned_buyback_share=pool_on["burned_buyback_share"],
                buyback_spent_stock=pool_on["buyback_spent_stock"], profit_to_buyback=pool_on["profit_to_buyback"],
                lp_fee_stock=pool_on["lp_fee_stock"])


# ------------------------------------------------------------------------------------------------ stage 4
def pathological(curve: Curve, rule: Rule, *, shock: float, fill_days: int = 8, shock_days: int = 4,
                 after_days: int = 30, volume: float = 0.2, start: float = 100.0) -> dict:
    """Half the raise fills flat, the stock moves to `shock` times its price over `shock_days`, and then two
    branches: the raise never completes (everyone sells back to the curve), or the other half fills at the new
    price, the launch graduates there, and the stock walks back to where it started over `after_days`."""
    if shock <= 0 or fill_days < 2 or fill_days % 2:
        raise ValueError("bad shock parameters")
    g = curve.graduation()
    rg, t = g["real_stock"], curve.tax
    half = fill_days // 2
    p_shock = start * shock
    tokens_half = curve.tokens_between(0, rg / 2) * (1 - t)
    out = dict(
        shock=shock, rg=rg, reserve_stock=rg / 2,
        reserve_usd_before=rg / 2 * start, reserve_usd_after=rg / 2 * p_shock,
        remaining_usd_before=rg / 2 * start, remaining_usd_after=rg / 2 * p_shock,
        holders_tokens=tokens_half, holders_paid_stock=rg / 2, holders_paid_usd=rg / 2 * start,
        # the curve does not know the stock moved: the same tokens quote the same stock
        holders_curve_stock=rg / 2 * (1 - t), holders_curve_usd=rg / 2 * (1 - t) * p_shock,
        group_exit_recovery_usd=(1 - t) * shock,
    )
    # branch: the raise completes at the shocked price, then the stock goes home
    path = [p_shock] * (half * STEPS_PER_DAY + 1)
    home = stock_path(after_days, (1 / shock) ** (1 / after_days) - 1, start=p_shock)
    run = run_post_graduation(curve, rule, home, volume)
    grad_cost_usd = rg / 2 * start + rg / 2 * p_shock
    top = pregraduation(curve, [start] * (half * STEPS_PER_DAY + 1) + path[1:], fill_days)
    out.update(graduation_usd=grad_cost_usd, graduation_usd_flat=rg * start, lot_cost=p_shock,
               first_cohort=top["cohorts"][0], last_cohort=top["cohorts"][-1], after=run,
               lot_vs_end=start / p_shock - 1, tp_needs=p_shock * (1 + rule.tp1) / start - 1)
    return out


# ------------------------------------------------------------------------------------------------ the report
PATHS = (("+3%/day", 0.03, 0.0), ("+1%/day", 0.01, 0.0), ("+1%/day, 2% vol", 0.01, 0.02),
         ("flat, 2% vol", 0.0, 0.02), ("flat, 4% vol", 0.0, 0.04),
         ("-1%/day, 2% vol", -0.01, 0.02), ("-1%/day", -0.01, 0.0), ("-3%/day", -0.03, 0.0))


def _cohort(result, label):
    return next(c for c in result["cohorts"] if c["label"] == label)


def _pct(x, digits=0):
    return f"{x * 100:+.{digits}f}%"


def _usd(x):
    return f"${x:,.0f}"


def _table(header, rows):
    line = "| " + " | ".join(header) + " |"
    sep = "|" + "|".join("---" for _ in header) + "|"
    return "\n".join([line, sep] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def report(curve: Curve = Curve(), rule: Rule = TEMPLATES["trend_holder"], volume: float = 0.2,
           horizons=(30, 90)) -> str:
    g = curve.graduation()
    out = []
    out.append(f"Base launch: supply {curve.supply:,.0f}, opening FDV {curve.opening_fdv_stock:g} stock "
               f"(${curve.opening_fdv_stock * 100:,.0f} at $100/stock), sale {curve.sale_bps / 100:g}%, LP {curve.lp_bps / 100:g}%, "
               f"tax {curve.tax_bps / 100:g}%, LP fee {curve.lp_fee_bps / 100:g}%. Raise Rg = {g['real_stock']:g} stock "
               f"(${g['real_stock'] * 100:,.0f}); pool {g['lp_stock']:g} stock / {g['lp_token']:,.0f} FUN; treasury "
               f"{g['treasury_stock']:g} stock; open-to-terminal {g['open_to_terminal']:.1f}x. Rule {rule.name}: "
               f"tp {rule.tp1:.0%}/{2 * rule.tp1:.0%}, dip {rule.dip:.0%}, stop {rule.stop:.0%}, lot {rule.lot:.0%}. "
               f"Volume {volume:.0%} of Rg per day.")

    # ---- stage 1
    rows = []
    for label, drift, vol in PATHS:
        for n in (1, 7, 30):
            path = stock_path(n, drift, vol)
            r = pregraduation(curve, path, n)
            first, last = _cohort(r, "first 5%"), _cohort(r, "last 5%")
            rows.append([label, n, f"{r['stock_multiple']:.2f}x", _usd(r["usd_cost"]), _pct(r["usd_cost"] / r["usd_cost_flat"] - 1),
                         f"{first['paper_multiple_stock']:.1f}x / {first['paper_multiple_usd']:.1f}x",
                         f"{first['dump_multiple_usd']:.1f}x",
                         f"{last['paper_multiple_stock']:.2f}x / {last['paper_multiple_usd']:.2f}x"])
    out.append("### Table 1a. The raise under a trend (sale 80%, tax 10%)\n\n" + _table(
        ["path", "fill days", "stock at graduation", "USD cost to graduate", "vs flat",
         "first 5%: paper multiple stock / USD", "first 5%: dump alone, USD", "last 5%: paper stock / USD"], rows))

    rows = []
    for sale in (4400, 6000, 8000):
        c = replace(curve, sale_bps=sale)
        gg = c.graduation()
        r = pregraduation(c, stock_path(7, 0.0), 7)
        one, five = _cohort(r, "first 1%"), _cohort(r, "first 5%")
        rows.append([f"{sale / 100:g}%", f"{gg['open_to_terminal']:.1f}x", f"{gg['real_stock']:.1f} ({_usd(gg['real_stock'] * 100)})",
                     f"{gg['lp_stock']:.1f} / {gg['treasury_stock']:.1f}", f"{gg['lp_token'] / gg['supply_after']:.0%}",
                     f"{one['paper_multiple_stock']:.1f}x / {one['dump_multiple_stock']:.1f}x / {one['price_after_dump']:.0%}",
                     f"{five['paper_multiple_stock']:.1f}x / {five['dump_multiple_stock']:.1f}x / {five['price_after_dump']:.0%}"])
    out.append("### Table 1b. Sale share: what the raise is and what the first buyers get (flat stock)\n\n" + _table(
        ["sale", "open to terminal", "Rg stock (USD at $100)", "pool / treasury stock", "pool FUN as % of supply",
         "first 1% of the raise: paper / dump alone / price after", "first 5%: paper / dump alone / price after"], rows))

    rows = []
    for tax in (100, 200, 1000):
        r = curve_round_trip(replace(curve, tax_bps=tax))
        rows.append([f"{tax / 100:g}%", f"{r['loss']:.2%}", f"{r['loss_flat_tax']:.2%}"])
    out.append("### Table 1c. Round trip on the curve: buy 1% of the raise halfway through, sell it back\n\n" + _table(
        ["tax", "round-trip loss", "(1-t)^2"], rows))

    # ---- stage 2
    for days in horizons:
        rows = []
        for label, drift, vol in PATHS:
            r = run_post_graduation(curve, rule, stock_path(days, drift, vol), volume)
            rows.append([label, f"{r['stock_multiple']:.2f}x", "yes" if r["tp_fired"] else "no", r["n_tp"], r["n_stop"], r["n_dip"],
                         r["lots_end"], _usd(r["reserve_usdg"]), f"{r['buyback_spent_stock']:.2f}",
                         _pct(r["burned_buyback_share"], 2), f"{r['multiple']:.2f}",
                         f"{_usd(r['treasury_usd_start'])} -> {_usd(r['treasury_usd_end'])}"])
        out.append(f"### Table 2a. The treasury over {days} days (base launch, {rule.name}, volume {volume:.0%}/day)\n\n" + _table(
            ["path", "stock", "TP fired", "TP sales", "stops", "dips", "lots", "USDG reserve", "buy-back stock spent",
             "FUN burned by buy-backs", "multiple vs hold", "treasury USD"], rows))

    rows = []
    for name, rl in TEMPLATES.items():
        cells = [f"{name} ({rl.tp1:.0%}/{2 * rl.tp1:.0%}, dip {rl.dip:.0%}, stop {rl.stop:.0%}, lot {rl.lot:.0%})"]
        for label, drift, vol in (PATHS[0], PATHS[1], PATHS[2], PATHS[5], PATHS[6], PATHS[7]):
            r = run_post_graduation(curve, rl, stock_path(90, drift, vol), volume)
            cells.append(f"{r['multiple']:.2f} ({r['n_tp']}/{r['n_stop']}/{r['n_dip']}, {_pct(r['burned_buyback_share'], 1)})")
        rows.append(cells)
    out.append("### Table 2b. Rule templates over 90 days: multiple vs hold (TP sales / stops / dips, FUN burned by buy-backs)\n\n" + _table(
        ["template", "+3%/day", "+1%/day", "+1%/day, 2% vol", "-1%/day, 2% vol", "-1%/day", "-3%/day"], rows))

    rows = []
    for drift_label, drift in (("+1%/day", 0.01), ("-1%/day", -0.01)):
        for tax in (100, 200, 1000):
            for vol in (0.05, 0.2, 0.5):
                c = replace(curve, tax_bps=tax)
                r = run_post_graduation(c, rule, stock_path(90, drift, 0.0), vol)
                rows.append([drift_label, f"{tax / 100:g}%", f"{vol:.0%}", _usd(r["volume_usd"]), f"{r['tax_received'] + r['unbooked_end']:.2f}",
                             f"{r['lp_fee_stock']:.2f}", _pct(r["burned_tax_share"], 2), _pct(r["burned_buyback_share"], 2),
                             f"{r['multiple']:.2f}"])
    out.append("### Table 2c. Tax and volume over 90 days: what flows in and what burns\n\n" + _table(
        ["path", "tax", "volume / day", "volume USD, 90d", "sell tax to treasury, stock", "stock LP fees", "FUN burned by buy tax",
         "FUN burned by buy-backs", "multiple vs hold"], rows))

    # ---- stage 3
    rows = []
    for label, drift, vol in PATHS:
        d = fun_price_decomposition(curve, rule, stock_path(90, drift, vol), volume)
        rows.append([label, _pct(d["stock_change"]), _pct(d["burned_tax_share"], 1), _pct(d["burned_buyback_share"], 1),
                     _pct(d["float_with_buybacks"], 1), _pct(d["float_usd_change"]),
                     _pct(d["burns_only"], 1), _pct(d["with_buybacks"], 1), _pct(d["usd_change"])])
    out.append(f"### Table 3a. The token's price over 90 days (base launch, volume {volume:.0%}/day)\n\n" + _table(
        ["path", "stock moved", "supply burned by buy tax", "by buy-backs",
         "FUN in stock, float sells the burn back: total", "in USD",
         "FUN in stock, float never sells: burns only", "with buy-backs", "in USD"], rows))

    rows = []
    for vol in (0.05, 0.2, 0.5):
        for sale in (4400, 6000, 8000):
            c = replace(curve, sale_bps=sale)
            d = fun_price_decomposition(c, rule, stock_path(90, 0.0, 0.02), vol)
            rows.append([f"{vol:.0%}", f"{sale / 100:g}%", _pct(d["burned_share"], 1), _pct(d["float_with_buybacks"], 1),
                         _pct(d["burns_only"], 1), _pct(d["with_buybacks"], 1)])
    out.append("### Table 3b. Flat stock, 2% vol, 90 days: the mechanism alone, by volume and sale share\n\n" + _table(
        ["volume / day", "sale", "supply burned", "FUN in stock, float sells the burn back",
         "float never sells: burns only", "with buy-backs"], rows))

    # ---- stage 4
    rows = []
    for shock in (0.5, 2.0):
        for rl in (TEMPLATES["trend_holder"], TEMPLATES["tp_stop"]):
            r = pathological(curve, rl, shock=shock)
            a = r["after"]
            rows.append([f"{shock:g}x", rl.name, _usd(r["reserve_usd_before"]), _usd(r["reserve_usd_after"]),
                         _usd(r["remaining_usd_after"]), _pct(r["group_exit_recovery_usd"] - 1),
                         _usd(r["graduation_usd"]), f"${r['lot_cost']:.0f}", "yes" if a["tp_fired"] else "no", a["n_stop"],
                         f"{a['multiple']:.2f}", f"{_usd(a['treasury_usd_start'])} -> {_usd(a['treasury_usd_end'])}"])
    out.append("### Table 4. Half the raise fills at $100, the stock moves, the rest fills there, then the stock walks back to $100 over 30 days\n\n" + _table(
        ["stock", "rule", "reserve USD before", "after", "USD still needed", "group exit vs USD paid", "USD cost to graduate",
         "treasury lot cost", "TP fired", "stops", "multiple vs hold", "treasury USD"], rows))
    return "\n\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sale-bps", type=int, default=8000)
    ap.add_argument("--tax-bps", type=int, default=1000)
    ap.add_argument("--lp-bps", type=int, default=5000)
    ap.add_argument("--fdv-stock", type=float, default=100.0, help="opening FDV in stock units (V)")
    ap.add_argument("--volume", type=float, default=0.2, help="daily pool volume as a fraction of the raise")
    ap.add_argument("--rule", choices=sorted(TEMPLATES), default="trend_holder")
    a = ap.parse_args(argv)
    curve = Curve(sale_bps=a.sale_bps, tax_bps=a.tax_bps, lp_bps=a.lp_bps, opening_fdv_stock=a.fdv_stock)
    print(report(curve, TEMPLATES[a.rule], a.volume))


if __name__ == "__main__":
    main()
