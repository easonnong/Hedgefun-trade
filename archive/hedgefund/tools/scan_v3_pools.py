#!/usr/bin/env python3
"""Read-only census of Uniswap V3 <stock>/USDG pools on Robinhood Chain.

Answers one question: if we deploy C dollars as a concentrated LP at +/-band,
what share of the pool's in-range liquidity do we buy, and what did that share
of the pool earn in fees over the last full trading week?

Everything is an eth_call. Nothing here signs, writes, or touches the live
keeper's state. Two RPCs are used: publicnode for head state, the blockmachine
archive for the historical feeGrowth sample.

Gotchas this encodes, each of which produced a wrong answer first:
  * USDG has 6 decimals, stock tokens have 18. Every price and balance needs
    the 10**(dec0-dec1) adjustment or the ranking is nonsense.
  * The factory has ~160 pools that were initialised at MAX_SQRT_RATIO and
    hold nothing. They are filtered on active liquidity, not on TVL.
  * A requested +/-1% band is snapped to the pool's tick spacing, so the band
    you get is wider than the band you asked for. Fee yield scales inversely
    with width, so the actual band is what gets used.
  * The sample window must be trading hours. A 24h window ending on a weekend
    measures a closed market and ranks every pool at zero.

Outputs data/v3_pool_census.json.
"""
import json, os, sys, time, urllib.request, math, calendar
from _registry import load_tokens

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PN = "https://robinhood-rpc.publicnode.com"
ARCHIVE = "https://rpc-robinhood.blockmachine.io"
FACTORY = "0x1f7d7550b1b028f7571e69a784071f0205fd2efa"
USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
FEES = [100, 500, 3000, 10000]
Q96 = 2 ** 96
Q128 = 2 ** 128

# last full US trading week before the run date (UTC)
WINDOW_START = "2026-09-14 13:30:00"   # Mon open
WINDOW_END   = "2026-09-18 20:00:00"   # Fri close
TRADING_DAYS = 5.0

SEL = {
    "getPool": "0x1698ee82", "slot0": "0x3850c7bd", "liquidity": "0x1a686502",
    "feeGrowthGlobal0X128": "0xf3058399", "feeGrowthGlobal1X128": "0x46141319",
    "token0": "0x0dfe1681", "token1": "0xd21220a7", "tickSpacing": "0xd0c93a7c",
    "balanceOf": "0x70a08231", "decimals": "0x313ce567",
}


def rpc(url, calls, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(calls).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2.0 * (i + 1))


def batched(url, calls, size=80, pause=0.15):
    out = {}
    for i in range(0, len(calls), size):
        for r in rpc(url, calls[i:i + size]):
            out[r["id"]] = r.get("result")
        time.sleep(pause)
    return out


def call(cid, to, data, block="latest"):
    return {"jsonrpc": "2.0", "id": cid, "method": "eth_call",
            "params": [{"to": to, "data": data}, block]}


def addr32(a):
    return a.lower().replace("0x", "").rjust(64, "0")


def dec(h, start=0, length=64, signed=False):
    if not h:
        return 0
    h = h[2:] if h.startswith("0x") else h
    v = int(h[start:start + length] or "0", 16)
    if signed and v >= 2 ** 255:
        v -= 2 ** 256
    return v


def block_at(ts, head, head_ts, spb):
    """Binary-search the archive for the block at a unix timestamp."""
    guess = head - int((head_ts - ts) / spb)
    lo, hi = max(1, guess - 2_000_000), min(head, guess + 2_000_000)
    while lo < hi:
        mid = (lo + hi) // 2
        r = rpc(PN, [{"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                      "params": [hex(mid), False]}])[0]["result"]
        if r is None:
            hi = mid - 1
            continue
        if int(r["timestamp"], 16) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def main():
    tokens = load_tokens()
    syms = [s for s in tokens if s != "USDG"]

    head_r = rpc(PN, [{"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}])[0]
    head = int(head_r["result"], 16)
    head_ts = int(rpc(PN, [{"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                            "params": [hex(head), False]}])[0]["result"]["timestamp"], 16)
    t0 = calendar.timegm(time.strptime(WINDOW_START, "%Y-%m-%d %H:%M:%S"))
    t1 = calendar.timegm(time.strptime(WINDOW_END, "%Y-%m-%d %H:%M:%S"))
    spb = 0.1005
    b_start = block_at(t0, head, head_ts, spb)
    b_end = block_at(t1, head, head_ts, spb)
    print(f"head={head} window blocks {b_start}..{b_end} "
          f"({WINDOW_START} -> {WINDOW_END} UTC)", file=sys.stderr)

    # 0. decimals for every token
    calls, meta, cid = [], {}, 0
    for s in syms + ["USDG"]:
        cid += 1
        calls.append(call(cid, tokens[s]["address"], SEL["decimals"]))
        meta[cid] = s
    decs = {}
    for cid, r in batched(PN, calls).items():
        decs[meta[cid]] = dec(r) if r else 18

    # 1. discover pools
    calls, meta, cid = [], {}, 0
    for s in syms:
        for fee in FEES:
            cid += 1
            calls.append(call(cid, FACTORY, SEL["getPool"] + addr32(tokens[s]["address"])
                              + addr32(USDG) + hex(fee)[2:].rjust(64, "0")))
            meta[cid] = (s, fee)
    pools = {}
    for cid, r in batched(PN, calls).items():
        if r and int(r, 16) != 0:
            pools[meta[cid]] = "0x" + r[-40:]
    print(f"{len(pools)} pools exist", file=sys.stderr)

    # 2. head state
    calls, meta, cid = [], {}, 0
    for (s, fee), p in pools.items():
        for fn in ("slot0", "liquidity", "token0", "tickSpacing"):
            cid += 1
            calls.append(call(cid, p, SEL[fn]))
            meta[cid] = (s, fee, fn)
        for tk, lbl in ((tokens[s]["address"], "balStock"), (USDG, "balUsdg")):
            cid += 1
            calls.append(call(cid, tk, SEL["balanceOf"] + addr32(p)))
            meta[cid] = (s, fee, lbl)
    st = {}
    for cid, r in batched(PN, calls).items():
        s, fee, fn = meta[cid]
        st.setdefault((s, fee), {})[fn] = r

    live = [(s, fee) for (s, fee) in pools if dec(st.get((s, fee), {}).get("liquidity")) > 0]
    print(f"{len(live)} pools carry active liquidity", file=sys.stderr)

    # 3. feeGrowth at both ends of the trading window, live pools only
    archive_ok = True
    for lbl, blk in (("_a", b_start), ("_b", b_end)):
        calls, meta, cid = [], {}, 0
        for key in live:
            for fn in ("feeGrowthGlobal0X128", "feeGrowthGlobal1X128", "liquidity"):
                cid += 1
                calls.append(call(cid, pools[key], SEL[fn], hex(blk)))
                meta[cid] = (key, fn)
        try:
            for cid, r in batched(ARCHIVE, calls, size=25, pause=0.8).items():
                key, fn = meta[cid]
                st[key][fn + lbl] = r
        except Exception as e:
            print(f"archive sample failed at {lbl}: {e}", file=sys.stderr)
            archive_ok = False
            break

    # 4. derive
    rows = []
    for (s, fee), p in pools.items():
        d = st.get((s, fee), {})
        sqrtP = dec(d.get("slot0"))
        L = dec(d.get("liquidity"))
        if not sqrtP:
            continue
        tick = dec(d.get("slot0"), 64, signed=True)
        usdg_is_token0 = ("0x" + (d.get("token0") or "")[-40:]).lower() == USDG.lower()
        spacing = dec(d.get("tickSpacing"), signed=True) or 1
        d0, d1 = (decs["USDG"], decs[s]) if usdg_is_token0 else (decs[s], decs["USDG"])
        Praw = (sqrtP / Q96) ** 2                       # token1_raw per token0_raw
        adj = 10 ** (d0 - d1)
        price1per0 = Praw * adj                         # human token1 per human token0
        stock_usdg = (1 / price1per0) if usdg_is_token0 else price1per0
        bal_stock = dec(d.get("balStock")) / 10 ** decs[s]
        bal_usdg = dec(d.get("balUsdg")) / 10 ** decs["USDG"]
        row = {"symbol": s, "fee_bps": fee / 100, "pool": p, "tick_spacing": spacing,
               "usdg_is_token0": usdg_is_token0, "tick": tick,
               "price_usdg_per_stock": stock_usdg, "bal_stock": bal_stock,
               "bal_usdg": bal_usdg, "tvl_usdg": bal_usdg + bal_stock * stock_usdg,
               "active_liquidity": L}
        if L == 0 or not (0.01 < stock_usdg < 1e6):
            row["skip"] = "empty_or_uninitialised"
            rows.append(row)
            continue

        want = 0.01
        dt = math.log(1 + want) / math.log(1.0001)
        lo = math.floor((tick - dt) / spacing) * spacing
        hi = math.ceil((tick + dt) / spacing) * spacing
        Pa, Pb = 1.0001 ** lo, 1.0001 ** hi              # raw-price bounds
        row["band_requested_pct"] = want * 100
        row["band_actual_pct"] = round(((1 - 1.0001 ** (lo - tick)) + (1.0001 ** (hi - tick) - 1)) / 2 * 100, 3)
        row["ticks_in_band"] = hi - lo

        k = 2 * math.sqrt(Praw) - Praw / math.sqrt(Pb) - math.sqrt(Pa)
        if k <= 0:
            row["skip"] = "degenerate_band"
            rows.append(row)
            continue
        for C in (100, 1000, 5000, 25000):
            v1_raw = (C * 10 ** d0) * Praw if usdg_is_token0 else C * 10 ** d1
            Lm = v1_raw / k
            row[f"L_at_{C}"] = Lm
            row[f"share_at_{C}"] = Lm / (L + Lm)

        if archive_ok and d.get("feeGrowthGlobal0X128_b") and d.get("feeGrowthGlobal0X128_a"):
            g0 = max(dec(d["feeGrowthGlobal0X128_b"]) - dec(d["feeGrowthGlobal0X128_a"]), 0)
            g1 = max(dec(d["feeGrowthGlobal1X128_b"]) - dec(d["feeGrowthGlobal1X128_a"]), 0)
            row["L_window_start"] = dec(d.get("liquidity_a"))
            row["L_window_end"] = dec(d.get("liquidity_b"))
            # USDG value of one unit of liquidity's fees over the window
            f0 = (g0 / Q128) / 10 ** d0
            f1 = (g1 / Q128) / 10 ** d1
            per_L = (f0 + f1 * stock_usdg) if usdg_is_token0 else (f0 * stock_usdg + f1)
            row["fees_per_L_week"] = per_L
            Lref = row["L_window_end"] or L
            row["pool_fees_week_usdg"] = per_L * Lref
            row["pool_volume_week_usdg"] = (per_L * Lref) / (fee / 1e6) if fee else 0
            for C in (100, 1000, 5000, 25000):
                fees = per_L * row[f"L_at_{C}"]
                row[f"fees_week_at_{C}"] = fees
                row[f"fee_apr_at_{C}"] = fees * 52 / C
        rows.append(row)

    rows.sort(key=lambda r: -(r.get("pool_volume_week_usdg") or 0))
    out = {"generated_at": int(time.time()), "head_block": head,
           "window": {"start_utc": WINDOW_START, "end_utc": WINDOW_END,
                      "start_block": b_start, "end_block": b_end,
                      "trading_days": TRADING_DAYS},
           "archive_ok": archive_ok, "factory": FACTORY, "usdg": USDG,
           "decimals": decs, "pools": rows}
    path = os.path.join(HERE, "data", "v3_pool_census.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"wrote {path}: {len(rows)} pools", file=sys.stderr)


if __name__ == "__main__":
    main()
