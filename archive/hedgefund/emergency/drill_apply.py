#!/usr/bin/env python3
"""DRILL ONLY: replay a batch built by build.py on a LOCAL anvil fork, as the Safe, by impersonation.

This is the one file in the kit that changes state anywhere, and the only state it can change is a throwaway anvil on
this machine:
  - it refuses any RPC that is not http://127.0.0.1 / localhost / [::1];
  - it refuses any node whose web3_clientVersion does not start with "anvil";
  - it holds no key and signs nothing. It sends UNSIGNED eth_sendTransaction after anvil_impersonateAccount, which a
    real node rejects outright -- there is no account behind it to sign with.
It exists so the quarterly drill exercises the exact JSON a signer would load, not a re-typed copy of it.

    anvil --fork-url https://rpc.mainnet.chain.robinhood.com --port 8545
    python3 emergency/build.py --rpc http://127.0.0.1:8545 halt --days 3
    python3 emergency/drill_apply.py emergency/out/<file>.json
    python3 emergency/build.py --rpc http://127.0.0.1:8545 status
"""
import json, sys, time, urllib.parse, urllib.request

LOCAL = {"127.0.0.1", "localhost", "::1"}


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=20) as r:
        out = json.loads(r.read())
    if "error" in out: raise SystemExit(f"REFUSED by node: {method}: {out['error']}")
    return out["result"]


def main():
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    path = sys.argv[1]; url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8545"
    host = urllib.parse.urlparse(url).hostname
    if host not in LOCAL: raise SystemExit(f"REFUSED: {url} is not this machine. The drill runs on a local anvil fork and nowhere else.")
    client = rpc(url, "web3_clientVersion", [])
    if not client.lower().startswith("anvil"): raise SystemExit(f"REFUSED: the node at {url} says it is {client!r}, not anvil.")

    batch = json.loads(open(path).read())
    safe = batch["meta"]["createdFromSafeAddress"]
    if int(rpc(url, "eth_chainId", []), 16) != int(batch["chainId"]): raise SystemExit("REFUSED: the fork's chainId is not the batch's chainId")
    print(f"DRILL on {client} at {url}: impersonating the Safe {safe}. This is not a broadcast; nothing leaves this machine.")
    rpc(url, "anvil_impersonateAccount", [safe]); rpc(url, "anvil_setBalance", [safe, hex(10 ** 18)])
    for i, t in enumerate(batch["transactions"], 1):
        h = rpc(url, "eth_sendTransaction", [{"from": safe, "to": t["to"], "data": t["data"], "value": hex(int(t["value"]))}])
        for _ in range(50):
            rc = rpc(url, "eth_getTransactionReceipt", [h])
            if rc: break
            time.sleep(0.1)
        ok = rc and int(rc["status"], 16) == 1
        print(f"  [{i}/{len(batch['transactions'])}] {(t.get('contractMethod') or {}).get('name', '?'):<20} -> {'ok' if ok else 'REVERTED'}")
        if not ok: raise SystemExit("a transaction in the batch reverted on the fork: the batch would fail in the Safe too. Find out why BEFORE the real thing.")
    rpc(url, "anvil_stopImpersonatingAccount", [safe])
    print("applied. Now:  python3 emergency/build.py --rpc " + url + " status")


if __name__ == "__main__":
    main()
