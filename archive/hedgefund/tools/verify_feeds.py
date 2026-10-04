#!/usr/bin/env python3
"""Three-way price check: Chainlink feed vs pool spot vs Lighter mark.

Run this before funding anything. It answers the questions that actually block a
deployment, none of which the docs can answer because their feed tables render
client-side:

  * does a push feed exist for this ticker at all, or is it TWAP-fallback?
  * is it fresh, or are we inside the 24/5 weekend hole?
  * do the three prices agree, or is one of the three legs of the strategy
    looking at a different market from the other two?

The feed's `description()` string is NOT a reliable identifier: on this chain it
comes back as `RHMSFT / USD` for some tickers, `Robinhood META / USD` for
others, and `Robinhood SGOV-USD` for others again. Resolve feeds by address.

Read-only. Writes nothing.
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PN = "https://robinhood-rpc.publicnode.com"
LATEST, DECIMALS, DESCRIPTION = "0xfeaf968c", "0x313ce567", "0x7284e416"
USDG_FEED_NAME = "USDG / USD"
STALE_AFTER = 24 * 3600


def rpc(calls):
    req = urllib.request.Request(
        PN, data=json.dumps(calls).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def s_str(h):
    try:
        h = h[2:]
        off = int(h[0:64], 16) * 2
        ln = int(h[off:off + 64], 16) * 2
        return bytes.fromhex(h[off + 64:off + 64 + ln]).decode()
    except Exception:
        return "?"


def main():
    feeds = json.load(open(os.path.join(HERE, "data", "chainlink_feeds.json")))
    short = json.load(open(os.path.join(HERE, "data", "shortlist.json")))["all"]
    pools = {r["symbol"]: r for r in short}
    syms = sys.argv[1:] or [r["symbol"] for r in
                            json.load(open(os.path.join(HERE, "data", "shortlist.json")))["shortlist"]]

    # feed address by ticker, tolerating all three naming conventions
    addr = {}
    for name, v in feeds.items():
        for sym in set(syms) | {"USDG"}:
            if name in (f"Robinhood {sym} / USD", f"RH{sym} / USD",
                        f"Robinhood {sym}-USD", f"{sym} / USD"):
                addr[sym] = v["addr"]
    missing = [s for s in syms if s not in addr]

    calls, meta, i = [], {}, 0
    for sym, a in addr.items():
        for sel, lbl in ((LATEST, "latest"), (DECIMALS, "dec"), (DESCRIPTION, "desc")):
            i += 1
            calls.append({"jsonrpc": "2.0", "id": i, "method": "eth_call",
                          "params": [{"to": a, "data": sel}, "latest"]})
            meta[i] = (sym, lbl)
    res = {r["id"]: r.get("result") for r in rpc(calls)}
    fd = {}
    for i, (sym, lbl) in meta.items():
        fd.setdefault(sym, {})[lbl] = res.get(i)

    u = fd["USDG"]
    usdg = int(u["latest"][2:][64:128], 16) / 10 ** int(u["dec"], 16)
    now = int(time.time())
    print(f"USDG / USD = {usdg:.6f}\n")
    print(f"{'sym':6}{'description()':26}{'feed/USDG':>10}{'age':>7}{'pool':>10}{'mark':>10}"
          f"{'pool-feed':>10}{'mark-feed':>10}")
    bad = 0
    for sym in syms:
        if sym not in fd:
            continue
        d = fd[sym]
        h = d["latest"][2:]
        px = int(h[64:128], 16) / 10 ** int(d["dec"], 16)
        age = now - int(h[192:256], 16)
        fu = px / usdg
        p = pools.get(sym, {})
        pool, mark = p.get("pool_price"), p.get("mark_price")
        dp = (pool / fu - 1) * 100 if pool else 0
        dm = (mark / fu - 1) * 100 if mark else 0
        flag = ""
        if age > STALE_AFTER:
            flag += " STALE"
        if abs(dp) > 1 or abs(dm) > 1:
            flag += " DIVERGENT"
            bad += 1
        print(f"{sym:6}{s_str(d['desc']):26}{fu:10.2f}{age//3600:6}h"
              f"{(pool or 0):10.2f}{(mark or 0):10.2f}{dp:+9.2f}%{dm:+9.2f}%{flag}")
    if missing:
        print(f"\nNO PUSH FEED (TWAP fallback territory): {', '.join(missing)}")
    print(f"\n{bad} ticker(s) with >1% disagreement between the three prices")


if __name__ == "__main__":
    main()
