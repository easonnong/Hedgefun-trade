#!/usr/bin/env python3
"""Sample feeGrowthGlobal at both ends of a trading window, for the pools that
matter, and cache it.

Split out of scan_v3_pools.py because the archive RPC rate-limits hard: this
runs small batches, sleeps, caches every partial result to
data/fee_samples.json, and is safe to re-run until the cache is full.

Read-only. eth_call at historical blocks, nothing else.
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CENSUS = os.path.join(HERE, "data", "v3_pool_census.json")
CACHE = os.path.join(HERE, "data", "fee_samples.json")
# blockmachine is the only endpoint that serves historical state; the official
# node answers "historical state ... is not available" and publicnode is not an
# archive either. One source, so pace against it rather than rotating.
RPCS = ["https://rpc-robinhood.blockmachine.io"]
SEL = {"feeGrowthGlobal0X128": "0xf3058399",
       "feeGrowthGlobal1X128": "0x46141319",
       "liquidity": "0x1a686502"}
TOP_N = int(os.environ.get("TOP_N", "60"))


def rpc(url, calls, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(calls).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception as e:
            last = e
            time.sleep(3.0 * (i + 1))
    raise last


def main():
    census = json.load(open(CENSUS))
    win = census["window"]
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    cache.setdefault("window", win)
    cache.setdefault("samples", {})

    live = [r for r in census["pools"] if r.get("active_liquidity", 0) > 0 and "skip" not in r]
    live.sort(key=lambda r: -r["tvl_usdg"])
    targets = live[:TOP_N]

    want = []
    for r in targets:
        for blk_lbl, blk in (("a", win["start_block"]), ("b", win["end_block"])):
            for fn in SEL:
                key = f"{r['pool']}|{blk_lbl}|{fn}"
                if key not in cache["samples"]:
                    want.append((key, r["pool"], blk, fn))
    print(f"{len(targets)} pools, {len(want)} samples missing", file=sys.stderr)

    rpc_i = 0
    size, pause = 12, 1.2
    i = 0
    while i < len(want):
        chunk = want[i:i + size]
        calls = [{"jsonrpc": "2.0", "id": n, "method": "eth_call",
                  "params": [{"to": p, "data": SEL[fn]}, hex(b)]}
                 for n, (k, p, b, fn) in enumerate(chunk)]
        try:
            res = rpc(RPCS[rpc_i % len(RPCS)], calls)
        except Exception as e:
            rpc_i += 1
            if rpc_i >= len(RPCS) * 3:
                print(f"giving up at {i}/{len(want)}: {e}", file=sys.stderr)
                break
            print(f"rpc rotate after {e}", file=sys.stderr)
            time.sleep(10)
            continue
        by_id = {r["id"]: r.get("result") for r in res}
        got = 0
        for n, (k, p, b, fn) in enumerate(chunk):
            v = by_id.get(n)
            if v:
                cache["samples"][k] = v
                got += 1
        json.dump(cache, open(CACHE, "w"), indent=0)
        i += size
        if i % 120 == 0:
            print(f"  {i}/{len(want)}", file=sys.stderr)
        time.sleep(pause)

    have = sum(1 for r in targets
               if all(f"{r['pool']}|{l}|{fn}" in cache["samples"] for l in "ab" for fn in SEL))
    print(f"complete for {have}/{len(targets)} pools -> {CACHE}", file=sys.stderr)


if __name__ == "__main__":
    main()
