#!/usr/bin/env python3
"""Sample each candidate pool's tick through the trading window to get realised
variance — the input to the gamma (LVR) side of the trade.

Why this matters more than it looks: for a delta-hedged concentrated LP the
whole decision reduces to one comparison that does not depend on how much
capital we deploy.

    fee income over the window   =  feesPerL * L
    adverse selection (LVR)      =  (1/4) * L * sqrt(P) * RV

L cancels. A pool is worth entering iff feesPerL > (1/4)*sqrt(P)*RV, where
RV is the realised variance over the same window (sum of squared log returns).
Capital size then only decides the liquidity share, the venue minimums and the
hedge granularity — not whether the pool makes money.

RV is measured off the pool's own tick because the pool price, not the oracle,
is what the position is actually exposed to.

Read-only, cached, resumable. Writes data/vol_samples.json.
"""
import json, os, sys, time, urllib.request, math

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CENSUS = os.path.join(HERE, "data", "v3_pool_census.json")
CACHE = os.path.join(HERE, "data", "vol_samples.json")
ARCHIVE = "https://rpc-robinhood.blockmachine.io"
SLOT0 = "0x3850c7bd"
N_SAMPLES = int(os.environ.get("N_SAMPLES", "60"))   # through the window
TOP_N = int(os.environ.get("TOP_N", "40"))


def rpc(calls, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                ARCHIVE, data=json.dumps(calls).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception as e:
            last = e
            time.sleep(4.0 * (i + 1))
    raise last


def main():
    census = json.load(open(CENSUS))
    win = census["window"]
    b0, b1 = win["start_block"], win["end_block"]
    blocks = [b0 + round((b1 - b0) * i / (N_SAMPLES - 1)) for i in range(N_SAMPLES)]

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    cache.setdefault("blocks", blocks)
    cache.setdefault("ticks", {})

    live = [r for r in census["pools"] if r.get("active_liquidity", 0) > 0 and "skip" not in r]
    live.sort(key=lambda r: -r["tvl_usdg"])
    targets = live[:TOP_N]

    want = [(f"{r['pool']}|{b}", r["pool"], b)
            for r in targets for b in blocks
            if f"{r['pool']}|{b}" not in cache["ticks"]]
    print(f"{len(targets)} pools x {len(blocks)} blocks: {len(want)} missing", file=sys.stderr)

    size, pause, fails = 12, 1.2, 0
    i = 0
    while i < len(want):
        chunk = want[i:i + size]
        calls = [{"jsonrpc": "2.0", "id": n, "method": "eth_call",
                  "params": [{"to": p, "data": SLOT0}, hex(b)]}
                 for n, (k, p, b) in enumerate(chunk)]
        try:
            res = rpc(calls)
        except Exception as e:
            fails += 1
            if fails > 6:
                print(f"giving up at {i}/{len(want)}: {e}", file=sys.stderr)
                break
            time.sleep(15)
            continue
        by_id = {r["id"]: r.get("result") for r in res}
        for n, (k, p, b) in enumerate(chunk):
            v = by_id.get(n)
            if v and len(v) > 130:
                sqrtP = int(v[2:66], 16)
                tick = int(v[66:130], 16)
                if tick >= 2 ** 255:
                    tick -= 2 ** 256
                cache["ticks"][k] = tick
        json.dump(cache, open(CACHE, "w"), indent=0)
        i += size
        if i % 240 == 0:
            print(f"  {i}/{len(want)}", file=sys.stderr)
        time.sleep(pause)

    done = sum(1 for r in targets if all(f"{r['pool']}|{b}" in cache["ticks"] for b in blocks))
    print(f"complete for {done}/{len(targets)} pools -> {CACHE}", file=sys.stderr)


if __name__ == "__main__":
    main()
