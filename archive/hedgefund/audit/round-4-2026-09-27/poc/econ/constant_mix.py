#!/usr/bin/env python3
"""Kind 2 (V2RebalancePolicy, constant-mix) against kind 0 (stop / take-profit / dip) on the project's own trend model.

`vendor/` holds `lab/trend.py`, `lab/model.py` and `tools/rule_backtest.py` verbatim from
origin/research/v2-trend-scenarios @ f1af82e. Kind 0 below IS that model's `run_post_graduation`; kind 2 is the same
function with the engine's decision in place of the `Ledger`: the pool, the tax and LP-fee flows, the buy-back loop and
the scorecard are shared line for line, so the two kinds differ only in what the treasury does with its stock.

The engine, as `HedgeFunV2EngineTreasury` does it:
  - inventory is every stock the treasury holds outside `buybackStock` (no lots, no booking gate), valued at the oracle;
  - stock share s = S / (S + U); if s > target + band sell min(maxTrade, S - target (S + U), remaining day) of stock;
    if s < target - band buy min(maxTrade, target (S + U) - S, U, remaining day) of USDG; else hold;
  - one action per cooldown; a keeper polls hourly (one execute() per bar) unless `polls_per_hour` says otherwise;
  - every swap loses `cost` (pool fee + slippage, 35 bps as kind 0 assumes); an action under `minLotUsdg` is not due;
  - a sale's proceeds are USDG inventory. NOTHING reaches `buybackStock` but the stock-side LP fee, so the only burns
    are LP-fee funded -- exactly as in the contract, where no engine path credits `buybackStock`.

    python3 constant_mix.py            # the tables in ../../lanes/econ.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
from lab.trend import BUYBACK_TWAP_WINDOW, PATHS, STEPS_PER_DAY, TEMPLATES, Curve, Rule, run_post_graduation, stock_path  # noqa: E402


@dataclass(frozen=True)
class Engine:
    name: str
    target: float = 0.50
    band: float = 0.05
    cooldown: int = 60                    # seconds; the engine's own limiter
    max_trade_usdg: float = 2_000.0       # sellChunkUsdg, the rehearsal default and the constructor's ceiling
    max_daily_usdg: float = float("inf")  # the UTC-day turnover cap
    polls_per_hour: int = 1               # how often a keeper calls execute(); at most 3600 / cooldown act
    cost: float = 0.0035                  # pool fee + slippage per swap, as Rule.cost
    min_lot_usdg: float = 5.0
    # the rest of the treasury is the inherited base: same buy-back pacing as kind 0
    bounty: float = 0.005
    buyback_chunk_usdg: float = 500.0
    buyback_cooldown: int = 60
    max_buyback_impact: float = 0.03


ENGINES = {
    "E-50/5": Engine("E-50/5", target=0.50, band=0.05),
    "E-50/1": Engine("E-50/1", target=0.50, band=0.01),
    "E-80/5": Engine("E-80/5", target=0.80, band=0.05),
    "E-test": Engine("E-test", target=0.50, band=0.05, max_trade_usdg=100.0, max_daily_usdg=500.0),   # the repo's test config
}


def run_engine(curve: Curve, cfg: Engine, path: list[float], volume: float, *, buybacks: bool = True,
               burn_source: str = "pool") -> dict:
    """`lab.trend.run_post_graduation`, with the engine's rule. Everything not about the rule is copied verbatim."""
    if volume < 0 or len(path) < 2 or burn_source not in ("pool", "float"):
        raise ValueError("bad run parameters")
    g = curve.graduation()
    f, t, share = curve.lp_fee, curve.tax, curve.treasury_share
    x, y = g["lp_token"], g["lp_stock"]
    supply = supply0 = g["supply_after"]
    price0 = y / x
    p0 = path[0]
    stock = g["treasury_stock"]                                             # inventory, in stock
    usdg = 0.0                                                              # inventory, in USDG
    received = stock
    budget = 0.0                                                            # buybackStock: LP fees only
    tax_received = lp_fee_stock = 0.0
    spent = spent_usd = 0.0
    burned_tax = burned_lp = burned_buyback = 0.0
    volume_usd = stock_in = stock_to_sellers = stock_to_others = bounty_fun = 0.0
    n_sell = n_buy = 0
    turnover = exec_cost = 0.0
    day = -1; day_turnover = 0.0
    step_stock = volume * g["real_stock"] / 2 / STEPS_PER_DAY
    chunk_per_hour = 3600 / max(cfg.buyback_cooldown, 1)
    pushes_per_hour = 3600 / BUYBACK_TWAP_WINDOW
    polls = min(cfg.polls_per_hour, 3600 // max(cfg.cooldown, 1)) or 1

    for i in range(1, len(path)):
        p = path[i]
        if i // STEPS_PER_DAY != day:
            day = i // STEPS_PER_DAY; day_turnover = 0.0
        # -- the pool's hour: identical to run_post_graduation
        if step_stock > 0:
            fee = step_stock * f; lp_fee_stock += fee; budget += fee; stock_in += step_stock
            eff = step_stock - fee
            out = x * eff / (y + eff); y += eff; x -= out
            tax_fun = out * t; burned_tax += tax_fun; supply -= tax_fun
            q = out - tax_fun if burn_source == "pool" else out
            fee_fun = q * f; burned_lp += fee_fun; supply -= fee_fun
            eff = q - fee_fun
            h = y * eff / (x + eff); x += eff; y -= h
            inflow = h * t * share
            stock += inflow; received += inflow; tax_received += inflow      # the engine books on the next execute()
            stock_to_others += h * t * (1 - share); stock_to_sellers += h * (1 - t)
            volume_usd += (step_stock + h) * p
        # -- the keeper: up to `polls` execute() calls this hour, each one bounded action
        for _ in range(polls):
            S = stock * p; T = S + usdg
            if T <= 0: break
            remaining = cfg.max_daily_usdg - day_turnover
            if remaining <= 0: break
            if S > (cfg.target + cfg.band) * T:
                amt = min(cfg.max_trade_usdg, S - cfg.target * T, remaining)
                if amt < cfg.min_lot_usdg: break
                stock -= amt / p; usdg += amt * (1 - cfg.cost); exec_cost += amt * cfg.cost
                n_sell += 1
            elif S < (cfg.target - cfg.band) * T:
                amt = min(cfg.max_trade_usdg, cfg.target * T - S, usdg, remaining)
                if amt < cfg.min_lot_usdg: break
                usdg -= amt; stock += amt * (1 - cfg.cost) / p; exec_cost += amt * cfg.cost
                n_buy += 1
            else:
                break
            turnover += amt; day_turnover += amt
        # -- the buy-back: identical to run_post_graduation, funded by LP fees alone
        if buybacks and budget > 0:
            want = min(budget, chunk_per_hour * cfg.buyback_chunk_usdg / p)
            cap = y * ((1 + cfg.max_buyback_impact) ** (pushes_per_hour / 2) - 1)
            spend = min(want, cap)
            if spend >= min(want, cfg.min_lot_usdg / p) and spend > 0:
                fee = spend * f
                eff = spend - fee
                out = x * eff / (y + eff); y += eff; x -= out
                bounty = out * cfg.bounty; bounty_fun += bounty
                burned_buyback += out - bounty; supply -= out - bounty
                budget -= spend; budget += fee
                spent += spend; spent_usd += spend * p
    p_end = path[-1]
    price_end = y / x
    equivalent = stock + budget + usdg / p_end
    return dict(
        days=(len(path) - 1) / STEPS_PER_DAY, p_start=p0, p_end=p_end, stock_multiple=p_end / p0,
        graduation_lot=g["treasury_stock"], tax_received=tax_received,
        n_sell=n_sell, n_buy=n_buy, turnover_usd=turnover, exec_cost_usd=exec_cost,
        held_stock=stock, reserve_usdg=usdg, share_end=stock * p_end / (stock * p_end + usdg),
        lp_fee_stock=lp_fee_stock, buyback_spent_stock=spent, buyback_spent_usd=spent_usd, buyback_pending_stock=budget,
        burned_buyback=burned_buyback, burned_tax=burned_tax, burned_lp=burned_lp,
        supply_start=supply0, supply_end=supply,
        burned_buyback_share=burned_buyback / supply0, burned_share=(supply0 - supply) / supply0,
        multiple=equivalent / received if received else 1.0,
        treasury_usd_start=g["treasury_stock"] * p0, treasury_usd_end=equivalent * p_end,
        fun_price_stock_change=price_end / price0 - 1,
        fun_price_usd_change=(price_end * p_end) / (price0 * p0) - 1,
    )


def _pct(x, d=0):
    return f"{x * 100:+.{d}f}%"


def _usd(x):
    return f"${x:,.0f}"


def _table(header, rows):
    w = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    line = lambda r: "| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"
    return "\n".join([line(header), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows])


def main(days: int = 90, volume: float = 0.2):
    curve = Curve()
    rule = TEMPLATES["trend_holder"]
    g = curve.graduation()
    print(f"Base launch as docs/V2_TREND_SCENARIOS.md: raise {g['real_stock']:g} stock, treasury {g['treasury_stock']:g} stock "
          f"(${g['treasury_stock'] * 100:,.0f} at $100), volume {volume:.0%} of the raise per day, {days} days, hourly bars.\n"
          f"Kind 0 = trend_holder (tp 30%/60%, dip 3%, no stop, lot 50%). Kind 2 engines: E-50/5 target 50% band 5%,\n"
          f"E-50/1 band 1%, E-80/5 target 80% band 5% (all maxTrade 2,000 USDG, no daily cap, cooldown 60 s, hourly keeper),\n"
          f"E-test = the repository's test config (maxTrade 100, 500/day). Every swap costs 35 bps. 'multiple' is the contract's\n"
          f"own scorecard: (stock held + buy-back stock + USDG at the end price) / stock received; 1.00 = sat on the stock.\n")

    names = list(ENGINES)
    # -- Table A: the gross multiple -- everything held plus everything spent on burns, in stock, over everything
    #    received. The contract's own scorecard leaves out what buy-backs spent and, for kind 0, counts only booked
    #    tax; this one treats a burn as value delivered and counts every stock that arrived, so the kinds compare.
    def gross_k0(r):
        got = r["held_stock"] + r["unbooked_end"] + r["buyback_pending_stock"] + r["reserve_usdg"] / r["p_end"] + r["buyback_spent_stock"]
        return got / (r["graduation_lot"] + r["tax_received"] + r["unbooked_end"])
    def gross_e(r):
        got = r["held_stock"] + r["buyback_pending_stock"] + r["reserve_usdg"] / r["p_end"] + r["buyback_spent_stock"]
        return got / (r["graduation_lot"] + r["tax_received"])
    rows = []
    for label, drift, vol in PATHS:
        path = stock_path(days, drift, vol)
        k0 = run_post_graduation(curve, rule, path, volume)
        cells = [label, f"{k0['stock_multiple']:.2f}x", f"{k0['multiple']:.2f} / {gross_k0(k0):.2f}",
                 _usd(k0["treasury_usd_end"]) + " + " + _usd(k0["buyback_spent_usd"])]
        for n in names:
            r = run_engine(curve, ENGINES[n], path, volume)
            cells += [f"{r['multiple']:.2f} / {gross_e(r):.2f}", _usd(r["treasury_usd_end"]) + " + " + _usd(r["buyback_spent_usd"])]
        rows.append(cells)
    hdr = ["path", "stock", "kind 0: scorecard / gross", "USD end + burned"]
    for n in names:
        hdr += [f"{n}: scorecard / gross", "USD end + burned"]
    print(f"### A. Multiple vs hold (the contract's scorecard / gross incl. burns), and what ${g['treasury_stock'] * 100:,.0f} of treasury became ({days} days)\n")
    print(_table(hdr, rows))
    print()

    # -- Table B: activity, cost, burns
    rows = []
    for label, drift, vol in PATHS:
        path = stock_path(days, drift, vol)
        k0 = run_post_graduation(curve, rule, path, volume)
        rows.append([label, "kind 0", f"{k0['n_tp']} tp / {k0['n_dip']} dip", "-", "-", _usd(k0["reserve_usdg"]),
                     f"{k0['buyback_spent_stock']:.1f}", _pct(k0["burned_buyback_share"], 2)])
        for n in names:
            r = run_engine(curve, ENGINES[n], path, volume)
            rows.append(["", n, f"{r['n_sell']} sell / {r['n_buy']} buy", _usd(r["turnover_usd"]), _usd(r["exec_cost_usd"]),
                         _usd(r["reserve_usdg"]), f"{r['buyback_spent_stock']:.1f}", _pct(r["burned_buyback_share"], 2)])
    print(f"### B. Actions, turnover, execution cost, buy-backs ({days} days)\n")
    print(_table(["path", "kind", "actions", "turnover", "execution cost", "USDG reserve end", "buy-back stock spent",
                  "FUN burned by buy-backs"], rows))
    print()

    # -- Table C: the first day: the graduation sell-down
    rows = []
    for n in ("E-50/5", "E-80/5", "E-test"):
        cfg = ENGINES[n]
        r = run_engine(curve, cfg, stock_path(1, 0.0), 0.0)
        r24 = run_engine(curve, cfg, stock_path(30, 0.0), 0.0)
        rows.append([n, f"{r['n_sell']}", _usd(r["turnover_usd"]), f"{r['share_end']:.1%}", f"{r24['n_sell']}", f"{r24['share_end']:.1%}"])
    print("### C. Flat stock, no volume: how fast the graduation lot is sold down to target (hourly keeper)\n")
    print(_table(["engine", "sells, day 1", "sold, day 1", "stock share after day 1", "sells, 30 days", "share after 30 days"], rows))
    print("\nWith a keeper that calls every cooldown instead of every hour, E-50/5 needs 3 actions (3 minutes) for the same sell-down.\n")

    # -- Table D: a faster keeper does not change the answer on the trend
    rows = []
    for label, drift, vol in (PATHS[0], PATHS[1], PATHS[4], PATHS[7]):
        path = stock_path(days, drift, vol)
        cells = [label]
        for polls in (1, 60):
            cfg = Engine("E-50/1", target=0.5, band=0.01, polls_per_hour=polls)
            r = run_engine(curve, cfg, path, volume)
            cells += [f"{r['multiple']:.3f}", f"{r['n_sell'] + r['n_buy']}", _usd(r["exec_cost_usd"])]
        rows.append(cells)
    print("### D. E-50/1 with an hourly keeper against one that calls every cooldown\n")
    print(_table(["path", "hourly: multiple", "actions", "cost", "per-minute: multiple", "actions", "cost"], rows))


if __name__ == "__main__":
    main()
