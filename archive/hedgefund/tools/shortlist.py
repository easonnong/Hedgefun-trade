#!/usr/bin/env python3
"""Join the pool ranking with the Lighter venue data and apply the gates.

A pool is a candidate only if the whole trade can be assembled, not just the
LP leg. The gates, in the order they eliminate things:

  1. HEDGEABLE  - there must be a Lighter perp for the ticker. No perp, no
                  delta-neutral position, however good the pool looks.
  2. SIZEABLE   - the hedge has a $10 minimum notional and a minimum base
                  size. Below roughly $2k of LP the hedge cannot track the
                  inventory, because one minimum order is a large fraction of
                  the position's whole delta range.
  3. NOT-THE-POOL - above ~15% of in-range liquidity we are quoting to
                  ourselves: our own fee estimate stops being a measurement of
                  someone else's flow, and the exit moves the price we exit at.
  4. EDGE       - in-range-adjusted fees must beat LVR with margin, because
                  realised gamma is worse than the continuously-hedged limit.

Prints the shortlist and writes data/shortlist.json.
"""
import json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANCHE = int(os.environ.get("TRANCHE", "5000"))
SHARE_CAP = 0.15


def main():
    rank = json.load(open(os.path.join(HERE, "data", "pool_ranking.json")))
    det = json.load(open(os.path.join(HERE, "data", "lighter_details.json")))
    books = json.load(open(os.path.join(HERE, "data", "lighter_orderbooks.json")))["order_books"]
    spot = {o["symbol"].replace("/USDG", "") for o in books if o["market_type"] == "spot"}

    rows = []
    for r in rank["pools"]:
        s = r["symbol"]
        d = det.get(s)
        share = r.get(f"share_at_{TRANCHE}")
        if share is None:
            continue
        mark = float(d["mark_price"]) if d else None
        basis = ((r["price_usdg_per_stock"] - mark) / mark) if mark else None
        # capital at which we would hit the share cap: L scales linearly in C
        L_ref = r[f"L_at_{TRANCHE}"]
        cap_L = SHARE_CAP / (1 - SHARE_CAP) * r["active_liquidity"]
        capacity = TRANCHE * cap_L / L_ref
        row = {
            "symbol": s, "fee_bps": r["fee_bps"], "pool": r["pool"],
            "tvl_usdg": r["tvl_usdg"], "band_actual_pct": r["band_actual_pct"],
            "pool_volume_week_usdg": r["pool_volume_week_usdg"],
            "share": share, "vol_annualised": r.get("vol_annualised"),
            "in_range_fraction": r.get("in_range_fraction"),
            "recenters_per_week": r.get("recenters_per_week"),
            "fee_apr": r.get(f"fee_apr_at_{TRANCHE}"),
            "fee_apr_adj": r.get(f"fee_apr_adj_at_{TRANCHE}"),
            "edge_apr": r.get(f"edge_apr_at_{TRANCHE}"),
            "fee_over_lvr": r.get("fee_over_lvr"),
            "perp": bool(d), "spot_book": s in spot,
            "perp_market_id": d["market_id"] if d else None,
            "perp_max_leverage": (10000 / d["min_initial_margin_fraction"]) if d else None,
            "perp_default_leverage": (10000 / d["default_initial_margin_fraction"]) if d else None,
            "perp_daily_volume_usdg": float(d["daily_quote_token_volume"]) if d else None,
            "perp_open_interest_base": float(d["open_interest"]) if d else None,
            "perp_min_quote": float(d["min_quote_amount"]) if d else None,
            "perp_min_base": float(d["min_base_amount"]) if d else None,
            "perp_min_base_usdg": (float(d["min_base_amount"]) * mark) if d else None,
            "perp_taker_fee": d["taker_fee"] if d else None,
            "mark_price": mark, "pool_price": r["price_usdg_per_stock"],
            "basis_pool_vs_mark": basis,
            "capacity_usdg": capacity,
        }
        gates = []
        if not row["perp"]:
            gates.append("no_perp")
        if r["pool_volume_week_usdg"] < 250_000:
            # below this there is no flow to earn from; the fee/LVR ratio also
            # stops meaning anything because the RV sample sees no moves
            gates.append("dead_pool")
        if (r.get("vol_annualised") or 0) < 0.05 and s != "SGOV":
            gates.append("vol_sample_degenerate")
        if share > SHARE_CAP:
            gates.append("we_are_the_pool")
        if row["perp"] and row["perp_min_base_usdg"] and row["perp_min_base_usdg"] > TRANCHE * 0.02:
            gates.append("hedge_granularity")
        if row["fee_over_lvr"] is not None and row["fee_over_lvr"] < 1.5:
            gates.append("thin_edge")
        if row["fee_over_lvr"] is None:
            gates.append("no_vol_sample")
        row["blockers"] = gates
        rows.append(row)

    ok = [r for r in rows if not r["blockers"]]
    ok.sort(key=lambda r: -(r["edge_apr"] or 0))
    json.dump({"tranche_usdg": TRANCHE, "share_cap": SHARE_CAP,
               "window": rank["window"], "shortlist": ok, "all": rows},
              open(os.path.join(HERE, "data", "shortlist.json"), "w"), indent=1)

    print(f"tranche = ${TRANCHE:,}    window {rank['window']['start_utc']} -> {rank['window']['end_utc']}\n")
    hdr = (f"{'sym':7}{'fee%':>5}{'band%':>6}{'share':>7}{'poolVol/wk':>12}{'σann':>6}"
           f"{'inRng':>6}{'f/LVR':>7}{'edgeAPR':>8}{'capacity':>10}{'perpVol/d':>11}{'lev':>5}{'minHdg':>7}{'basis':>8}")
    print(hdr)
    print("-" * len(hdr))
    for r in ok:
        print(f"{r['symbol']:7}{r['fee_bps']:5.2f}{r['band_actual_pct']:6.2f}{r['share']*100:6.2f}%"
              f"{r['pool_volume_week_usdg']:12,.0f}{(r['vol_annualised'] or 0)*100:5.0f}%"
              f"{(r['in_range_fraction'] or 0)*100:5.0f}%{r['fee_over_lvr']:7.2f}"
              f"{(r['edge_apr'] or 0)*100:7.0f}%{r['capacity_usdg']:10,.0f}{r['perp_daily_volume_usdg']:11,.0f}"
              f"{r['perp_max_leverage']:5.0f}{r['perp_min_base_usdg']:7,.0f}"
              f"{(r['basis_pool_vs_mark'] or 0)*100:+7.2f}%")

    print("\nrejected:")
    for r in sorted(rows, key=lambda r: -(r["fee_apr"] or 0)):
        if r["blockers"] and (r["fee_apr"] or 0) > 1.0:
            print(f"  {r['symbol']:7}{r['fee_bps']:5.2f}bps  feeAPR {(r['fee_apr'] or 0)*100:6.0f}%  "
                  f"share {r['share']*100:5.2f}%  -> {', '.join(r['blockers'])}")


if __name__ == "__main__":
    main()
