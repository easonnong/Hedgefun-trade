#!/usr/bin/env python3
"""Which stocks can the strategy-token launchpad actually list?

`HedgeFunFactory.list` (a V3 pool; the V4 stock venue was removed before the first release) and `PriceOracle`'s constructor between them
impose gates that most of the 196-token registry does not pass. This checks each
gate against live chain state and says why a ticker fails.

  1. ORACLE   - PriceOracle needs a Chainlink stock feed and the USDG feed. No
                push feed, no oracle, no listing. This is the binding gate.
  2. PAUSABLE - PriceOracle calls `oraclePaused()` on the stock token and fails
                closed if the call reverts, so the token must implement it.
  3. V3 POOL  - list() requires v3Factory.getPool(usdg, stock, fee) == pool, so
                a real <stock>/USDG pool at some fee tier.
  4. OBS RING - the V3 treasury corroborates spot with a TWAP and refuses a pool
                whose observation ring cannot serve the window
                (ShortObservationRing). A 600s window needs ~660 slots.
  5. DEPTH    - a listed pool the treasury cannot trade a lot through is a
                listing that bricks on first use.

V4 listability (a hookless <stock>/USDG pool) is NOT checked here - that needs a
V4 scan, which PR #2's own survey covers.

Read-only. Writes data/listability.json.
"""
import json, os, sys, time, urllib.request, math
from _registry import load_tokens

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PN = "https://robinhood-rpc.publicnode.com"
SLOT0, ORACLE_PAUSED = "0x3850c7bd", "0x7706ba52"   # slot0(), oraclePaused() -- verified with `cast sig`
TWAP_WINDOW = 600            # seconds, per the treasury's default
MIN_SLOTS = TWAP_WINDOW + 60  # ring must outlive the window with headroom


def rpc(calls, size=80):
    out = {}
    for i in range(0, len(calls), size):
        req = urllib.request.Request(
            PN, data=json.dumps(calls[i:i + size]).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        for r in json.load(urllib.request.urlopen(req, timeout=60)):
            out[r["id"]] = r.get("result")
        time.sleep(0.15)
    return out


def dec(h, start=0, length=64):
    if not h:
        return 0
    h = h[2:] if h.startswith("0x") else h
    return int(h[start:start + length] or "0", 16)


def main():
    census = json.load(open(os.path.join(HERE, "data", "v3_pool_census.json")))
    tokens = load_tokens()
    feeds = json.load(open(os.path.join(HERE, "data", "chainlink_feeds.json")))

    # feed lookup tolerating all three naming conventions on this chain
    feed_for = {}
    for name, v in feeds.items():
        for sym in tokens:
            if name in (f"Robinhood {sym} / USD", f"RH{sym} / USD", f"Robinhood {sym}-USD"):
                feed_for[sym] = (name, v["addr"])

    live = [r for r in census["pools"] if r.get("active_liquidity", 0) > 0 and "skip" not in r]
    best = {}
    for r in live:
        s = r["symbol"]
        if s not in best or r["tvl_usdg"] > best[s]["tvl_usdg"]:
            best[s] = r

    # observation ring on the best pool per ticker + oraclePaused() on the token
    calls, meta, cid = [], {}, 0
    for s, r in best.items():
        cid += 1
        calls.append({"jsonrpc": "2.0", "id": cid, "method": "eth_call",
                      "params": [{"to": r["pool"], "data": SLOT0}, "latest"]})
        meta[cid] = (s, "slot0")
    for s in tokens:
        if s in ("USDG", "WETH"):
            continue
        cid += 1
        calls.append({"jsonrpc": "2.0", "id": cid, "method": "eth_call",
                      "params": [{"to": tokens[s]["address"], "data": ORACLE_PAUSED}, "latest"]})
        meta[cid] = (s, "paused")
    res = rpc(calls)
    obs, pausable = {}, {}
    for cid, r in res.items():
        s, kind = meta[cid]
        if kind == "slot0" and r:
            # slot0: sqrtPriceX96, tick, observationIndex, cardinality, cardinalityNext, ...
            obs[s] = (dec(r, 64 * 3), dec(r, 64 * 4))
        elif kind == "paused":
            pausable[s] = (r is not None and len(r) >= 66)

    rows = []
    for s in sorted(tokens):
        if s in ("USDG", "WETH"):
            continue
        r = best.get(s)
        card, card_next = obs.get(s, (0, 0))
        blockers = []
        if s not in feed_for:
            blockers.append("no_chainlink_feed")
        if not pausable.get(s):
            blockers.append("no_oraclePaused")
        if not r:
            blockers.append("no_live_v3_usdg_pool")
        else:
            if card < MIN_SLOTS:
                blockers.append(f"short_obs_ring({card})")
            if r["tvl_usdg"] < 50_000:
                blockers.append(f"thin_pool(${r['tvl_usdg']:,.0f})")
        rows.append({
            "symbol": s,
            "feed_name": feed_for.get(s, (None, None))[0],
            "feed": feed_for.get(s, (None, None))[1],
            "oracle_paused_implemented": pausable.get(s, False),
            "best_v3_pool": r["pool"] if r else None,
            "fee_bps": r["fee_bps"] if r else None,
            "tvl_usdg": r["tvl_usdg"] if r else 0,
            "obs_cardinality": card, "obs_cardinality_next": card_next,
            "listable_v3": not blockers,
            "blockers": blockers,
        })

    ok = [r for r in rows if r["listable_v3"]]
    ok.sort(key=lambda r: -r["tvl_usdg"])
    json.dump({"generated_at": int(time.time()), "twap_window_s": TWAP_WINDOW,
               "min_obs_slots": MIN_SLOTS, "rows": rows},
              open(os.path.join(HERE, "data", "listability.json"), "w"), indent=1)

    print(f"registry: {len(rows)} stock tokens")
    print(f"  with a Chainlink push feed : {sum(1 for r in rows if r['feed'])}")
    print(f"  implementing oraclePaused(): {sum(1 for r in rows if r['oracle_paused_implemented'])}")
    print(f"  with a live V3/USDG pool   : {sum(1 for r in rows if r['best_v3_pool'])}")
    print(f"  LISTABLE on V3 today       : {len(ok)}\n")
    hdr = f"{'sym':7}{'TVL$':>12}{'fee%':>6}{'obs':>7}{'next':>7}  feed description"
    print(hdr); print("-" * 74)
    for r in ok:
        print(f"{r['symbol']:7}{r['tvl_usdg']:12,.0f}{r['fee_bps']:6.2f}"
              f"{r['obs_cardinality']:7}{r['obs_cardinality_next']:7}  {r['feed_name']}")

    print("\nhas a feed but not listable on V3:")
    for r in sorted(rows, key=lambda r: -r["tvl_usdg"]):
        if r["feed"] and not r["listable_v3"]:
            print(f"  {r['symbol']:7}{r['tvl_usdg']:12,.0f}  {', '.join(r['blockers'])}")


if __name__ == "__main__":
    main()
