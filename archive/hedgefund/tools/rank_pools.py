#!/usr/bin/env python3
"""Join the census, the fee sample and the vol sample into one ranking.

The ranking rests on a single scale-free comparison, per pool, over the same
trading window:

    feesPerL          USDG of fees one unit of liquidity earned
    lvrPerL           (1/4) * sqrt(P) * RV, the adverse selection one unit of
                      liquidity paid, in the same USDG units

edge = feesPerL - lvrPerL. Both sides are proportional to L, so the sign of
the edge does not depend on how much capital we deploy. That is the whole
point: capital size decides the liquidity share and whether the hedge can be
sized at all, not whether the pool is worth entering.

Caveats that are deliberately not hidden:
  * feesPerL assumes the position was in range for the whole window. A +/-1%
    band on a stock that moved 4% was not. Treat it as the in-range fee rate,
    an upper bound on what a static position collects.
  * LVR is the continuously-hedged limit. The keeper hedges on a 60s poll with
    a venue minimum, so realised gamma is worse than LVR, not better.
  * RV is measured on 60 samples across 5 sessions, so it sees session-level
    moves and misses intraday noise; it understates RV.
  * Both are one window. See CLAUDE.md on sweeping a single directional window.

Writes data/pool_ranking.json and prints a table.
"""
import json, os, sys, math

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q128 = 2 ** 128


def dec(h):
    return int(h, 16) if h else 0


def main():
    census = json.load(open(os.path.join(HERE, "data", "v3_pool_census.json")))
    fees = json.load(open(os.path.join(HERE, "data", "fee_samples.json")))["samples"]
    vpath = os.path.join(HERE, "data", "vol_samples.json")
    vol = json.load(open(vpath)) if os.path.exists(vpath) else {"blocks": [], "ticks": {}}
    decs = census["decimals"]
    win = census["window"]

    out = []
    for r in census["pools"]:
        if r.get("active_liquidity", 0) <= 0 or "skip" in r:
            continue
        p = r["pool"]
        if f"{p}|a|feeGrowthGlobal0X128" not in fees:
            continue
        s = r["symbol"]
        d0, d1 = ((decs["USDG"], decs[s]) if r["usdg_is_token0"] else (decs[s], decs["USDG"]))
        g0 = max(dec(fees[f"{p}|b|feeGrowthGlobal0X128"]) - dec(fees[f"{p}|a|feeGrowthGlobal0X128"]), 0)
        g1 = max(dec(fees[f"{p}|b|feeGrowthGlobal1X128"]) - dec(fees[f"{p}|a|feeGrowthGlobal1X128"]), 0)
        px = r["price_usdg_per_stock"]
        # USDG value of the fees accrued by one unit of liquidity
        f0 = (g0 / Q128) / 10 ** d0
        f1 = (g1 / Q128) / 10 ** d1
        fees_per_L = (f0 + f1 * px) if r["usdg_is_token0"] else (f0 * px + f1)

        # realised variance from the pool's own tick path
        ticks = [vol["ticks"].get(f"{p}|{b}") for b in vol.get("blocks", [])]
        ticks = [t for t in ticks if t is not None]
        rv = in_range = None
        recenters = None
        if len(ticks) >= 10:
            lr = [(ticks[i + 1] - ticks[i]) * math.log(1.0001) for i in range(len(ticks) - 1)]
            rv = sum(x * x for x in lr)
            # how much of the window a +/-band position actually spent in range,
            # recentering each time it fell out. This is the correction the raw
            # fee number most needs: out of range earns nothing.
            half = r["ticks_in_band"] / 2
            anchor, inside, moves = ticks[0], 0, 0
            for t in ticks:
                if abs(t - anchor) <= half:
                    inside += 1
                else:
                    moves += 1
                    anchor = t
            in_range = inside / len(ticks)
            recenters = moves

        # LVR per unit L over the window, in USDG
        sqrtPraw = math.sqrt((r["tick"] and 1.0001 ** r["tick"]) or 1.0)
        to_usdg_t1 = (px if r["usdg_is_token0"] else 1.0) / 10 ** d1
        lvr_per_L = (0.25 * sqrtPraw * rv * to_usdg_t1) if rv is not None else None

        row = dict(r)
        row.update({
            "fees_per_L_week": fees_per_L,
            "pool_fees_week_usdg": fees_per_L * r["active_liquidity"],
            "pool_volume_week_usdg": fees_per_L * r["active_liquidity"] / (r["fee_bps"] / 1e4),
            "rv_week": rv,
            "vol_annualised": (math.sqrt(rv * 52) if rv else None),
            "in_range_fraction": in_range,
            "recenters_per_week": recenters,
            "lvr_per_L_week": lvr_per_L,
            # the decisive ratio: in-range-adjusted fees against adverse selection
            "edge_per_L_week": (fees_per_L * (in_range or 1) - lvr_per_L) if lvr_per_L is not None else None,
            "fee_over_lvr": (fees_per_L * (in_range or 1) / lvr_per_L) if lvr_per_L else None,
        })
        for C in (100, 1000, 5000, 25000):
            L = r.get(f"L_at_{C}")
            if not L:
                continue
            row[f"fees_week_at_{C}"] = fees_per_L * L
            row[f"fee_apr_at_{C}"] = fees_per_L * L * 52 / C
            if in_range is not None:
                row[f"fees_week_adj_at_{C}"] = fees_per_L * L * in_range
                row[f"fee_apr_adj_at_{C}"] = fees_per_L * L * in_range * 52 / C
            if lvr_per_L is not None:
                row[f"edge_week_at_{C}"] = (fees_per_L * (in_range or 1) - lvr_per_L) * L
                row[f"edge_apr_at_{C}"] = (fees_per_L * (in_range or 1) - lvr_per_L) * L * 52 / C
        out.append(row)

    out.sort(key=lambda r: -(r.get("edge_apr_at_5000") if r.get("edge_apr_at_5000") is not None
                             else r.get("fee_apr_at_5000") or -9e9))
    json.dump({"window": win, "generated_from": "v3_pool_census + fee_samples + vol_samples",
               "pools": out}, open(os.path.join(HERE, "data", "pool_ranking.json"), "w"), indent=1)

    hdr = (f"{'sym':7}{'fee%':>5}{'TVL$':>11}{'vol/wk$':>12}{'σann':>6}{'band%':>6}"
           f"{'inRng':>6}{'rcntr':>6}{'sh@5k':>7}{'feeAPR':>8}{'adjAPR':>8}{'edgeAPR':>9}{'f/LVR':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in out:
        if (r.get("pool_volume_week_usdg") or 0) < 1000:
            continue
        nan = float("nan")
        print(f"{r['symbol']:7}{r['fee_bps']:5.2f}{r['tvl_usdg']:11,.0f}"
              f"{r['pool_volume_week_usdg']:12,.0f}"
              f"{(r['vol_annualised'] or nan)*100:5.0f}%{r['band_actual_pct']:6.2f}"
              f"{(r['in_range_fraction'] if r['in_range_fraction'] is not None else nan)*100:5.0f}%"
              f"{(r['recenters_per_week'] if r['recenters_per_week'] is not None else nan):6.0f}"
              f"{r['share_at_5000']*100:6.2f}%{(r.get('fee_apr_at_5000') or nan)*100:7.0f}%"
              f"{(r.get('fee_apr_adj_at_5000') or nan)*100:7.0f}%"
              f"{(r.get('edge_apr_at_5000') if r.get('edge_apr_at_5000') is not None else nan)*100:8.0f}%"
              f"{(r.get('fee_over_lvr') or nan):7.2f}")


if __name__ == "__main__":
    main()
