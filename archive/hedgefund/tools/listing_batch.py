#!/usr/bin/env python3
"""Turn a reviewed listing plan (deploy/*.json) into a Safe Transaction Builder file. Nothing else.

Same rule as emergency/build.py, whose encoder, checksum and simulation this reuses: it never signs, never
broadcasts, never holds a key. It reads the chain with eth_call and writes one JSON file for the Safe UI.

    python3 tools/listing_batch.py deploy/first-batch-2026-09-22.json            # checks, simulates, writes
    python3 tools/listing_batch.py deploy/first-batch-2026-09-22.json --check    # checks only

It refuses, and writes nothing, unless for every stock: the oracle has code and its six immutables are the plan's
(stock, feed resolved by the plan's token, USDG feed, production calendar, both ages); the pool is the V3 factory's
canonical pool for (USDG, stock, fee) with an observation ring of at least 660 that serves observe([600, 0]); the
oracle's price and the pool's spot agree within 1%; and the stock is not already listed. Every transaction is
then simulated from the Safe. Order: list x N, setBandCeiling, setListingGates, setLauncher (left out once the router is vouched). setPublicLaunch is
never in it: that is its own decision (docs/DEPLOYMENT.md 7.7).
"""
import argparse, datetime, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emergency"))
import build  # noqa: E402

build.METHODS.update(build.CONFIG_METHODS)   # this file emits configuration; the emergency kit itself never does
V3_FACTORY = "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA"
USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
MIN_RING = 660


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--rpc", default="https://robinhood-rpc.publicnode.com")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    rpc = build.Rpc(a.rpc)
    call = lambda to, sig, *args, out: build.cast("abi-decode", f"f()({out})", rpc._req("eth_call", [{"to": to, "data": build.cast("calldata", sig, *args)}, "latest"]))
    same = lambda x, y: x.lower() == y.lower()
    if int(rpc._req("eth_chainId", []), 16) != plan["chainId"]: raise build.Refuse("wrong chain")
    F = plan["factory"]
    if not same(call(F, "owner()", out="address"), plan["safe"]): raise build.Refuse("factory owner is not the plan's Safe")

    lines, calls = [], []
    for sym, s in plan["stocks"].items():
        o, tok = s["oracle"], s["token"]
        if rpc._req("eth_getCode", [o, "latest"]) in ("0x", ""): raise build.Refuse(f"{sym}: no oracle at {o} -- deploy it first")
        got = {k: call(o, f"{k}()", out=t) for k, t in (("stock", "address"), ("usdgFeed", "address"), ("calendar", "address"), ("maxStockAge", "uint256"), ("maxUsdgAge", "uint256"))}
        if not (same(got["stock"], tok) and same(got["usdgFeed"], plan["usdgFeed"]) and same(got["calendar"], plan["calendar"])
                and int(got["maxStockAge"].split()[0]) == plan["maxAge"] and int(got["maxUsdgAge"].split()[0]) == plan["maxAge"]):
            raise build.Refuse(f"{sym}: oracle immutables differ from the plan: {got}")
        if not same(call(V3_FACTORY, "getPool(address,address,uint24)", USDG, tok, str(s["fee"]), out="address"), s["v3Pool"]):
            raise build.Refuse(f"{sym}: {s['v3Pool']} is not the canonical {s['fee']} pool")
        slot0 = call(s["v3Pool"], "slot0()", out="uint160,int24,uint16,uint16,uint16,uint8,bool").split("\n")
        ring = int(slot0[3].split()[0])
        if ring < MIN_RING: raise build.Refuse(f"{sym}: observation ring {ring} < {MIN_RING}")
        call(s["v3Pool"], "observe(uint32[])", "[600,0]", out="int56[],uint160[]")    # raises on OLD
        listed = call(F, "listings(address)", tok, out="address,address,uint256,bool").split("\n")[0]
        if not same(listed, build.ZERO): raise build.Refuse(f"{sym}: already listed with oracle {listed}")
        feed_px = int(call(o, "lastPriceAt()", out="bool,uint256,uint256").split("\n")[1].split()[0])
        sq = int(slot0[0].split()[0]); r = (sq / 2**96) ** 2
        usdg0 = int(USDG, 16) < int(tok, 16)
        spot = (1e12 / r) if usdg0 else (r * 1e12)
        gap = abs(spot / (feed_px / 1e18) - 1)
        if gap > 0.01: raise build.Refuse(f"{sym}: pool spot {spot:.4f} and oracle {feed_px/1e18:.4f} disagree by {gap:.2%}")
        fdv = int(s["openPriceE18"]) * feed_px / 1e27
        lines.append(f"  {sym:6} oracle {o}  pool {s['v3Pool']} ({s['fee']/1e4:.2f}%, ring {ring})  spot-vs-oracle {gap*1e4:4.0f} bp  "
                     f"openPriceE18 {s['openPriceE18']} = ${fdv:,.0f} FDV now")
        calls.append(build.make_call(F, "list", [build.checksum_addr(tok), build.checksum_addr(o), build.checksum_addr(s["v3Pool"]), int(s["openPriceE18"]), True], f"list {sym}"))
    for sym, s in plan["stocks"].items():
        if s["bandCeiling"]: calls.append(build.make_call(F, "setBandCeiling", [build.checksum_addr(s["token"]), s["bandCeiling"]], f"{sym} band ceiling {s['bandCeiling']} bps/h"))
    for sym, s in plan["stocks"].items():
        if s["gates"]: calls.append(build.make_call(F, "setListingGates", [build.checksum_addr(s["token"]), *s["gates"]], f"{sym} gates dev/slip/chunk {s['gates']}"))
    if call(F, "launchers(address)", plan["launchRouter"], out="bool") != "true":   # a later batch finds it already vouched
        calls.append(build.make_call(F, "setLauncher", [build.checksum_addr(plan["launchRouter"]), True], "vouch for the production HedgeFunLaunchRouter"))

    st = {"safe": plan["safe"], "factory": F, "calendars": [{"address": plan["calendar"]}]}
    print("stocks\n" + "\n".join(lines) + "\n\n" + build.describe(calls, st) + "\n\nsimulation\n" + build.simulate(calls, st, rpc))
    if a.check: return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    b = build.bundle(calls, plan["chainId"], plan["safe"], f"LISTING {Path(a.plan).stem} {stamp}",
                     f"list x{len(plan['stocks'])}, band ceilings, listing gates, setLauncher if not yet vouched. Built from {Path(a.plan).name}.")
    out = ROOT / "deploy" / "safe" / f"{stamp}-{Path(a.plan).stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(b, indent=2) + "\n")
    print(f"\ntransactions   {len(calls)}\nmeta.checksum  {b['meta']['checksum']}\nbatch digest   {build.batch_digest(b['transactions'])}\nwrote          {out.relative_to(ROOT)}")


if __name__ == "__main__":
    try: main()
    except build.Refuse as e: sys.exit(f"REFUSED: {e}")
