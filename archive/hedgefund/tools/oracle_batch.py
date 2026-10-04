#!/usr/bin/env python3
"""Deploy a listing plan's PriceOracles from the Safe, as a Safe Transaction Builder file. Nothing else.

    forge build --contracts src/PriceOracle.sol                                   # the artifact this reads
    python3 tools/oracle_batch.py deploy/second-batch-2026-09-24.json --check      # checks only
    python3 tools/oracle_batch.py deploy/second-batch-2026-09-24.json              # checks, simulates, writes, fills `oracle`
    python3 tools/oracle_batch.py deploy/second-batch-2026-09-24.json --verify deploy/safe/<file>.json   # what a SIGNER runs

`emergency/build.py decode` refuses this file on purpose -- the emergency kit never deploys anything -- so a signer
verifies it with --verify instead: every transaction must be value 0 to the plan's CreateCall, call performCreate2,
carry exactly the artifact's creation code plus the constructor arguments the plan implies, and create the address the
plan names. It prints each oracle's decoded constructor arguments and the batch digest to read aloud.

An oracle has no owner and no role, so who deploys it does not matter; what matters is its six immutables, which the
signers read back before `list` (docs/DEPLOYMENT.md 7.1 and 9). Each is created by Safe's CreateCall with CREATE2, so
its address is `keccak(0xff, createCall, salt, keccak(initcode))` and known before it exists: this tool writes it into
the plan's `oracle` field, and `tools/listing_batch.py` refuses to list it until that address has code with the
plan's immutables. salt = keccak("hedgefun.PriceOracle.v1:" + SYMBOL).

It refuses, and writes nothing, unless: the local artifact's runtime equals the production MU oracle the first batch
listed (immutables masked), so the new oracles are the audited, Sourcify-verified code; every token has 18 decimals and implements oraclePaused(); every feed has 8 decimals and a round
younger than maxAge; the stock is not listed yet; and nothing is deployed at the predicted address. Every
performCreate2 is simulated from the Safe, and its returned address must equal the prediction.
"""
import argparse, datetime, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emergency"))
import build  # noqa: E402

build.METHODS["performCreate2"] = ("performCreate2(uint256,bytes,bytes32)",
                                   [("value", "uint256"), ("deploymentData", "bytes"), ("salt", "bytes32")])
ARTIFACT = ROOT / "out" / "PriceOracle.sol" / "PriceOracle.json"
REFERENCE = ("MU", "0x4D15A4A1028f001800774A3d2DC31d77945399a4")   # listed 2026-09-22, Sourcify `match`


def masked_equal(local_rt, onchain_rt, refs):
    got = list(onchain_rt)
    for rs in refs.values():
        for r in rs:
            s, n = r["start"] * 2, r["length"] * 2
            got[s:s + n] = local_rt[s:s + n]
    return "".join(got) == local_rt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("--check", action="store_true"); ap.add_argument("--verify", metavar="BATCH")
    ap.add_argument("--rpc", default="https://robinhood-rpc.publicnode.com")
    a = ap.parse_args()
    plan_path = Path(a.plan); plan = json.loads(plan_path.read_text())
    rpc = build.Rpc(a.rpc)
    call = lambda to, sig, *args, out: build.cast("abi-decode", f"f()({out})", rpc._req("eth_call", [{"to": to, "data": build.cast("calldata", sig, *args)}, "latest"]))
    num = lambda s: int(s.split()[0])
    same = lambda x, y: x.lower() == y.lower()
    if int(rpc._req("eth_chainId", []), 16) != plan["chainId"]: raise build.Refuse("wrong chain")
    F, CC = plan["factory"], plan["createCall"]
    if not same(call(F, "owner()", out="address"), plan["safe"]): raise build.Refuse("factory owner is not the plan's Safe")
    if rpc._req("eth_getCode", [CC, "latest"]) in ("0x", ""): raise build.Refuse(f"no CreateCall at {CC}")

    art = json.loads(ARTIFACT.read_text())
    creation, runtime = art["bytecode"]["object"], art["deployedBytecode"]["object"][2:]
    ref_rt = rpc._req("eth_getCode", [REFERENCE[1], "latest"])[2:]
    if not masked_equal(runtime, ref_rt, art["deployedBytecode"]["immutableReferences"]):
        raise build.Refuse(f"{ARTIFACT.relative_to(ROOT)} is not the code of the production {REFERENCE[0]} oracle {REFERENCE[1]}: rebuild at the deployed commit")

    if a.verify: return verify(plan, Path(a.verify), creation)
    ufeed = plan["usdgFeed"]; now = int(time.time())
    if num(call(ufeed, "decimals()", out="uint8")) != 8: raise build.Refuse("USDG feed decimals")
    lines, calls, predicted = [], [], {}
    for sym, s in plan["stocks"].items():
        tok, feed = s["token"], s["feed"]
        if num(call(tok, "decimals()", out="uint8")) != 18: raise build.Refuse(f"{sym}: token decimals")
        if call(tok, "oraclePaused()", out="bool") != "false": raise build.Refuse(f"{sym}: oraclePaused() is true or missing")
        if num(call(feed, "decimals()", out="uint8")) != 8: raise build.Refuse(f"{sym}: feed decimals")
        rd = call(feed, "latestRoundData()", out="uint80,int256,uint256,uint256,uint80").split("\n")
        age = now - num(rd[3])
        if num(rd[1]) <= 0 or age > plan["maxAge"]: raise build.Refuse(f"{sym}: feed answer {rd[1]} is {age}s old")
        if not same(call(F, "listings(address)", tok, out="address,address,uint256,bool").split("\n")[0], build.ZERO):
            raise build.Refuse(f"{sym}: already listed")
        args = build.cast("abi-encode", "f(address,address,address,address,uint256,uint256)", tok, feed, ufeed, plan["calendar"], str(plan["maxAge"]), str(plan["maxAge"]))
        init = creation + args[2:]
        salt = build.cast("keccak", f"hedgefun.PriceOracle.v1:{sym}")
        addr = build.cast("create2", "--deployer", CC, "--salt", salt, "--init-code", init).split()[-1]
        if rpc._req("eth_getCode", [addr, "latest"]) not in ("0x", ""): raise build.Refuse(f"{sym}: {addr} already has code")
        c = build.make_call(CC, "performCreate2", [0, init, salt], f"PriceOracle for {sym} -> {addr}")
        sim = rpc._req("eth_call", [{"from": plan["safe"], "to": CC, "data": c["data"]}, "latest"])
        if not same("0x" + sim[-40:], addr): raise build.Refuse(f"{sym}: simulated create returned {sim}, predicted {addr}")
        predicted[sym] = build.checksum_addr(addr); calls.append(c)
        lines.append(f"  {sym:5} oracle {predicted[sym]}  stock {tok}  feed {feed} ({call(feed, 'description()', out='string')}, {age/3600:.1f} h old)  salt {salt}")

    print(f"PriceOracle code == production {REFERENCE[0]} oracle {REFERENCE[1]} (immutables masked)\n"
          f"every oracle: usdgFeed {ufeed}, calendar {plan['calendar']}, maxStockAge = maxUsdgAge = {plan['maxAge']} s\n\n"
          + "oracles\n" + "\n".join(lines) + "\n\nsimulation\n  every performCreate2 eth_call from the Safe returned its predicted address")
    if a.check: return
    for sym, o in predicted.items(): plan["stocks"][sym]["oracle"] = o
    plan_path.write_text(json.dumps(plan, indent=1) + "\n")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    b = build.bundle(calls, plan["chainId"], plan["safe"], f"ORACLES {plan_path.stem} {stamp}",
                     f"PriceOracle x{len(calls)} via CreateCall.performCreate2 ({', '.join(predicted)}). Built from {plan_path.name}.")
    out = ROOT / "deploy" / "safe" / f"{stamp}-oracles-{plan_path.stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(b, indent=2) + "\n")
    print(f"\ntransactions   {len(calls)}\nmeta.checksum  {b['meta']['checksum']}\nbatch digest   {build.batch_digest(b['transactions'])}\n"
          f"wrote          {out.relative_to(ROOT)}\nfilled         `oracle` in {plan_path.name}")


def verify(plan, path, creation):
    b = json.loads(path.read_text()); txs = b["transactions"]; CC = plan["createCall"]
    sel = build.selector(build.METHODS["performCreate2"][0])
    problems, lines = [], []
    if str(b["chainId"]) != str(plan["chainId"]): problems.append(f"chainId {b['chainId']}")
    if b["meta"].get("checksum") != build.safe_checksum(b): problems.append("meta.checksum does not match the file: it was edited after it was built")
    if len(txs) != len(plan["stocks"]): problems.append(f"{len(txs)} transactions for {len(plan['stocks'])} stocks")
    for i, (t, (sym, s)) in enumerate(zip(txs, plan["stocks"].items()), 1):
        d = t["data"].lower()
        if t["to"].lower() != CC.lower(): problems.append(f"[{i}] target {t['to']} is not CreateCall {CC}")
        if str(t.get("value", "0")) != "0": problems.append(f"[{i}] sends value {t['value']}")
        if not d.startswith(sel): problems.append(f"[{i}] selector {d[:10]} is not performCreate2"); continue
        value, init, salt = build.cast("abi-decode", "--input", "f(uint256,bytes,bytes32)", "0x" + d[10:]).split("\n")
        args = build.cast("abi-encode", "f(address,address,address,address,uint256,uint256)", s["token"], s["feed"], plan["usdgFeed"], plan["calendar"], str(plan["maxAge"]), str(plan["maxAge"]))
        if init.lower() != (creation + args[2:]).lower():
            problems.append(f"[{i}] {sym}: deployment data is not PriceOracle's creation code + the plan's constructor arguments"); continue
        if salt.lower() != build.cast("keccak", f"hedgefun.PriceOracle.v1:{sym}").lower(): problems.append(f"[{i}] {sym}: salt {salt}")
        addr = build.cast("create2", "--deployer", CC, "--salt", salt, "--init-code", init).split()[-1]
        if addr.lower() != (s["oracle"] or "").lower(): problems.append(f"[{i}] {sym}: creates {addr}, plan names {s['oracle']}")
        if value.split()[0] != "0": problems.append(f"[{i}] performCreate2 value {value}")
        lines.append(f"  [{i}/{len(txs)}] CreateCall.performCreate2 -> PriceOracle {addr}\n"
                     f"        stock {s['token']} ({sym})  stockFeed {s['feed']}\n"
                     f"        usdgFeed {plan['usdgFeed']}  calendar {plan['calendar']}  maxStockAge = maxUsdgAge = {plan['maxAge']} s")
    print(f"file       {path}\nchainId    {b['chainId']}\nsafe       {b['meta'].get('createdFromSafeAddress')}\n\n" + "\n".join(lines)
          + f"\n\ntransactions   {len(txs)}\nmeta.checksum  {b['meta'].get('checksum')}\nbatch digest   {build.batch_digest(txs)}\n")
    for p_ in problems: print(f"  !! {p_}")
    print("VERDICT  " + ("PROBLEMS ABOVE. DO NOT SIGN." if problems else
          "consistent: every transaction deploys the production PriceOracle code with the plan's arguments. Compare the batch digest by voice."))
    if problems: sys.exit(1)


if __name__ == "__main__":
    try: main()
    except build.Refuse as e: sys.exit(f"REFUSED: {e}")
