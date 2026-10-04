#!/usr/bin/env python3
"""Emergency kit for the strategy-token launchpad: builds Safe Transaction Builder batches. Nothing else.

HARD RULE. This file never signs, never broadcasts, never holds a key. It makes two kinds of network request,
`eth_call`-class reads (eth_chainId, eth_getBlockByNumber, eth_getCode, eth_call) and nothing else, and its only
output is a JSON file a human drags into the Safe UI. There is no code path here that can move the chain.

Standard library only. ABI encoding and keccak are delegated to Foundry's `cast` (offline subcommands only:
`calldata`, `calldata-decode`, `abi-encode`, `keccak`, `sig`, `to-check-sum-address`).

    python3 emergency/build.py status
    python3 emergency/build.py stop-launches            | resume-launches
    python3 emergency/build.py delist NVDA 0xabc...     | relist NVDA
    python3 emergency/build.py halt --days 5            | extend --days 3 | resume-halt
    python3 emergency/build.py everything --days 5      | resume-everything --from emergency/out/<file>.json
    python3 emergency/build.py decode emergency/out/<file>.json      (what signers run on the file they were sent)

The shape: `read_state()` turns the chain into a plain dict, the `plan_*` functions turn that dict into a list of
calls, `bundle()` turns the calls into the Safe file. `encode` (used by test/Emergency.t.sol through vm.ffi) feeds
the SAME planners a state dict from the command line, so the calldata the Forge test executes against the real
contracts is produced by the code that produces the 3am batch.
"""
import argparse, datetime, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ZERO = "0x" + "00" * 20
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
MODES = {0: "none", 1: "FORCED SHUT", 2: "forced open"}
SCAN_DAYS = 45            # how far ahead overrides are looked for; a halt longer than this needs --window

# the owner surface. name -> (signature, [(argName, type)])
METHODS = {
    "setOverride": ("setOverride(uint256,uint8)", [("day", "uint256"), ("mode", "uint8")]),
    "setPublicLaunch": ("setPublicLaunch(bool)", [("open", "bool")]),
    "list": ("list(address,address,address,uint256,bool)",
             [("stock", "address"), ("oracle", "address"), ("v3Pool", "address"), ("openPriceE18", "uint256"), ("enabled", "bool")]),
}
# Owner functions `decode` can NAME but this kit never emits: configuration for FUTURE launches. Neither stops, slows or
# reverses anything that exists, so neither is an emergency lever. Kept out of METHODS on purpose -- METHODS is what the
# planner may build and what `parse_batch` may undo.
CONFIG_METHODS = {
    "setBandCeiling": ("setBandCeiling(address,uint16)", [("stock", "address"), ("bps", "uint16")]),
    "setListingGates": ("setListingGates(address,uint16,uint16,uint64)",
                        [("stock", "address"), ("maxDeviationBps", "uint16"), ("maxSlippageBps", "uint16"), ("sellChunkUsdg", "uint64")]),
    "setLauncher": ("setLauncher(address,bool)", [("launcher", "address"), ("ok", "bool")]),
}
# The one owner call that lands on a TREASURY: where the stock it holds points its votes. It moves no asset and cannot
# reach the rule, so it can neither cause nor stop an emergency. `decode` names it so a signer sees what it is, and
# refuses it like the configuration calls.
GOVERNANCE_METHODS = {
    "setVoteDelegate": ("setVoteDelegate(address)", [("delegatee", "address")]),
}


class Refuse(Exception):
    """A reason not to produce a batch. Always printed in full; never swallowed."""


# ---------------------------------------------------------------------------------------------------- cast
def cast(*args, stdin=None):
    try:
        r = subprocess.run(["cast", *args], capture_output=True, text=True, input=stdin)
    except FileNotFoundError:
        raise Refuse("Foundry's `cast` is not on PATH. Install Foundry (https://getfoundry.sh) -- this kit will not hand-roll ABI encoding.")
    if r.returncode != 0:
        raise Refuse(f"cast {' '.join(args[:2])} failed: {r.stderr.strip()}")
    return r.stdout.strip()


_SEL = {}
def selector(sig):
    if sig not in _SEL: _SEL[sig] = cast("sig", sig).lower()
    return _SEL[sig]


def keccak_text(s):
    # as explicit hex bytes: `cast keccak` treats any input that starts with 0x as hex, and a text that happens to
    # start with an address would be hashed as something else, or refused
    h = cast("keccak", stdin="0x" + s.encode("utf-8").hex()).lower()
    if s == "abc" and h != "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45": raise Refuse("cast keccak is not keccak256")
    return h


def checksum_addr(a):
    if not isinstance(a, str) or not ADDR_RE.match(a): raise Refuse(f"not an address: {a!r}")
    return cast("to-check-sum-address", a)


def _arg(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (list, tuple)): return "(" + ",".join(_arg(x) for x in v) + ")"
    return str(v)


def make_call(to, name, values, note=""):
    """One owner call: raw calldata from cast (authoritative) plus the decoded form the Safe UI and signers read."""
    sig, inputs = METHODS[name]
    if len(values) != len(inputs): raise Refuse(f"{name}: wrong argument count")
    data = cast("calldata", sig, *[_arg(v) for v in values]).lower()
    if not data.startswith(selector(sig)): raise Refuse(f"{name}: cast returned a foreign selector")
    return {"to": to, "name": name, "values": list(values), "data": data, "note": note}


# ---------------------------------------------------------------------------------------------------- rpc (reads only)
class Rpc:
    ALLOWED = {"eth_chainId", "eth_getBlockByNumber", "eth_getCode", "eth_call"}

    def __init__(self, url): self.url = url; self.n = 0

    def _req(self, method, params):
        if method not in self.ALLOWED: raise Refuse(f"{method} is not a read; this kit does not send it")
        self.n += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json", "User-Agent": "emergency-kit/1"})
        last = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=20) as r: out = json.loads(r.read())
                if "error" in out: raise RpcError(out["error"])
                return out["result"]
            except RpcError: raise
            except Exception as e:                                   # transport: retry, then say so
                last = e; time.sleep(0.5 * (attempt + 1))
        raise Refuse(f"RPC {self.url} unreachable: {last}")

    def chain_id(self): return int(self._req("eth_chainId", []), 16)
    def block(self):
        b = self._req("eth_getBlockByNumber", ["latest", False])
        return int(b["number"], 16), int(b["timestamp"], 16)
    def code(self, a): return self._req("eth_getCode", [a, "latest"])

    def call(self, to, sig, *args, frm=None):
        """sig is 'name(inTypes)'; returns the raw 32-byte words. Every return this kit reads is static."""
        tx = {"to": to, "data": cast("calldata", sig, *[_arg(a) for a in args])}
        if frm: tx["from"] = frm
        h = self._req("eth_call", [tx, "latest"])[2:]
        return [h[i:i + 64] for i in range(0, len(h), 64)]


class RpcError(Exception):
    pass


def w_addr(w): return checksum_addr("0x" + w[24:])
def w_uint(w): return int(w, 16)
def w_bool(w): return int(w, 16) != 0
def w_int(w):
    v = int(w, 16)
    return v - (1 << 256) if v >> 255 else v


# ---------------------------------------------------------------------------------------------------- addresses.json
def load_addresses(path):
    p = Path(path)
    if not p.exists():
        raise Refuse(f"{p} does not exist. Copy emergency/addresses.example.json to emergency/addresses.json and fill it in "
                     f"(README, 'Filling in addresses.json').")
    try: a = json.loads(p.read_text())
    except json.JSONDecodeError as e: raise Refuse(f"{p} is not valid JSON: {e}")
    bad = []
    def need(label, v):
        if not isinstance(v, str) or not ADDR_RE.match(v) or int(v, 16) == 0: bad.append(f"{label} = {v!r}")
    need("safe", a.get("safe")); need("factory", a.get("factory"))
    cals = a.get("calendars")
    if not isinstance(cals, list) or not cals: bad.append("calendars = (empty: list every TradingCalendar any listed oracle was ever built on)")
    else:
        for i, c in enumerate(cals): need(f"calendars[{i}]", c)
    stocks = a.get("stocks")
    if not isinstance(stocks, dict) or not stocks: bad.append("stocks = (empty: SYMBOL -> stock token address, one per stock ever listed)")
    else:
        for s, v in stocks.items(): need(f"stocks.{s}", v)
    if not isinstance(a.get("chainId"), int): bad.append(f"chainId = {a.get('chainId')!r}")
    if not isinstance(a.get("rpc"), str) or not a["rpc"].startswith("http"): bad.append(f"rpc = {a.get('rpc')!r}")
    if bad:
        raise Refuse(f"{p} still holds placeholders or malformed values. REFUSING to build anything from it:\n    " + "\n    ".join(bad))
    return {"chainId": a["chainId"], "rpc": a["rpc"], "safe": checksum_addr(a["safe"]), "factory": checksum_addr(a["factory"]),
            "calendars": [checksum_addr(c) for c in cals], "stocks": {s.upper(): checksum_addr(v) for s, v in stocks.items()}}


# ---------------------------------------------------------------------------------------------------- reading the chain
def read_state(addrs, rpc, window=SCAN_DAYS, with_strategies=False):
    got = rpc.chain_id()
    if got != addrs["chainId"]:
        raise Refuse(f"chainId mismatch: addresses.json says {addrs['chainId']}, the RPC at {rpc.url} answers {got}. Wrong RPC or wrong file.")
    number, ts = rpc.block()
    safe, factory = addrs["safe"], addrs["factory"]
    for label, a in [("safe", safe), ("factory", factory)] + [(f"calendar {c}", c) for c in addrs["calendars"]]:
        if rpc.code(a) in ("0x", "0x0", None): raise Refuse(f"{label} {a} has no code on chain {got}. Wrong address or wrong chain.")

    st = {"chainId": got, "block": number, "timestamp": ts, "safe": safe, "factory": factory, "warnings": [], "unowned": []}

    def owner_of(label, a):
        o = w_addr(rpc.call(a, "owner()")[0])
        try: pend = w_addr(rpc.call(a, "pendingOwner()")[0])
        except RpcError: pend = ZERO
        if pend != ZERO:
            st["warnings"].append(f"{label} {a} has a PENDING owner {pend}: an ownership transfer is half done. Whoever that is can "
                                  f"take the contract with acceptOwnership(). Find out why before anything else.")
        return o

    fo = owner_of("factory", factory)
    if fo != safe:
        raise Refuse(f"factory.owner() is {fo}, not the Safe in addresses.json ({safe}). A batch from that Safe would revert. REFUSING.")
    st["publicLaunch"] = w_bool(rpc.call(factory, "publicLaunch()")[0])

    # listings: the mapping cannot be enumerated on chain, so addresses.json names the stocks
    st["listings"] = []
    cal_src = {}                                                   # calendar -> who pointed at it
    for sym, stock in addrs["stocks"].items():
        w = rpc.call(factory, "listings(address)", stock)
        L = {"symbol": sym, "stock": stock, "oracle": w_addr(w[0]), "v3Pool": w_addr(w[1]),
             "openPriceE18": str(w_uint(w[2])), "enabled": w_bool(w[3])}
        L["bandCeiling"] = w_uint(rpc.call(factory, "bandCeiling(address)", stock)[0])   # most bps/h a NEW launch may ask for; 0 = Chainlink-only
        try:                                                                             # (maxDeviationBps, maxSlippageBps, sellChunkUsdg) a NEW launch is born with; (0, 0) pair / 0 chunk = the factory's defaults
            g = rpc.call(factory, "listingGates(address)", stock); L["gates"] = [w_uint(g[0]), w_uint(g[1]), w_uint(g[2])]
        except (RpcError, IndexError):                                                   # informational only: never let it stop `status` in an emergency
            L["gates"] = None
        L["listed"] = L["oracle"] != ZERO
        if L["listed"]:
            c = w_addr(rpc.call(L["oracle"], "calendar()")[0]); L["calendar"] = c
            cal_src.setdefault(c, []).append(f"{sym} listing oracle")
        st["listings"].append(L)

    # strategies: every treasury exposes oracle(). addresses.json carries the calendar list as well because a
    # re-listing with a new oracle leaves old launches on the old calendar
    st["strategies"] = []
    count = w_uint(rpc.call(factory, "strategyCount()")[0]); st["strategyCount"] = count
    known = {L["stock"] for L in st["listings"]}
    for i in range(count):
        w = rpc.call(factory, "strategies(uint256)", i)
        S = {"id": i, "token": w_addr(w[0]), "treasury": w_addr(w[1]), "hook": w_addr(w[2]), "stock": w_addr(w[3]), "creator": w_addr(w[4])}
        if S["stock"] not in known:
            st["warnings"].append(f"strategy #{i} trades stock {S['stock']}, which is NOT in addresses.json. Add it, or delist/everything will miss it.")
        try:
            c = w_addr(rpc.call(w_addr(rpc.call(S["treasury"], "oracle()")[0]), "calendar()")[0]); S["calendar"] = c
            cal_src.setdefault(c, []).append(f"strategy #{i}")
        except RpcError: S["calendar"] = None                      # not readable: the calendar list in addresses.json is the net
        if with_strategies:
            h = rpc.call(S["treasury"], "health()"); S["healthy"], S["price"] = w_bool(h[0]), w_uint(h[1])
            S["buybackStock"] = w_uint(rpc.call(S["treasury"], "buybackStock()")[0])
            S["lastGoodPriceAt"] = w_uint(rpc.call(S["treasury"], "lastGoodPriceAt()")[0])
            S["pricedOffPoolOnly"] = w_bool(rpc.call(S["treasury"], "pricedOffPoolOnly()")[0])
            S["bandBpsPerHour"] = w_uint(rpc.call(S["treasury"], "params()")[-1])    # Params' last field, fixed at launch; > 0 trades closures
            try: S["symbol"] = bytes.fromhex("".join(rpc.call(S["token"], "symbol()"))[128:]).rstrip(b"\0").decode(errors="replace")
            except Exception: S["symbol"] = "?"
        st["strategies"].append(S)

    for c in cal_src:
        if c not in addrs["calendars"]:
            st["warnings"].append(f"calendar {c} ({', '.join(cal_src[c])}) is on chain but NOT in addresses.json. It is included below; add it to the file.")
    st["calendars"] = []
    for c in list(dict.fromkeys(addrs["calendars"] + list(cal_src))):
        o = owner_of("calendar", c)
        today = w_uint(rpc.call(c, "tradingDate(uint256)", ts)[0])
        C = {"address": c, "owner": o, "today": today, "usedBy": cal_src.get(c, []),
             "utcOffset": w_int(rpc.call(c, "utcOffset(uint256)", ts)[0]),
             "closedNow": w_bool(rpc.call(c, "isClosed(uint256)", ts)[0]),
             "overrides": {}}
        for d in range(today, today + window):
            m = w_uint(rpc.call(c, "override_(uint256)", d)[0])
            if m: C["overrides"][str(d)] = m
        if o != safe: st["unowned"].append(c)
        st["calendars"].append(C)
    return st


# ---------------------------------------------------------------------------------------------------- planners (pure)
def day_str(d): return (datetime.date(1970, 1, 1) + datetime.timedelta(days=int(d))).strftime("%a %Y-%m-%d")


def _owned_calendars(st, skip_unowned):
    cals = [c for c in st["calendars"] if c.get("owner", st["safe"]) == st["safe"]]
    missing = [c["address"] for c in st["calendars"] if c.get("owner", st["safe"]) != st["safe"]]
    if missing and not skip_unowned:
        raise Refuse("these calendars are NOT owned by the Safe, so the Safe cannot halt what is priced through them:\n    "
                     + "\n    ".join(missing) + "\n  Re-run with --skip-unowned to halt the rest, and say out loud that the halt is PARTIAL.")
    if not cals: raise Refuse("the Safe owns no calendar: lever L3 does not exist. (AUDIT FA-1 suggested renouncing it; if that happened, this is the cost.)")
    return cals


def plan_stop_launches(st, force=False):
    if not st["publicLaunch"] and not force: return []
    return [make_call(st["factory"], "setPublicLaunch", [False], "strangers can no longer launch; the owner still can")]


def plan_resume_launches(st, force=False):
    if st["publicLaunch"] and not force: return []
    return [make_call(st["factory"], "setPublicLaunch", [True], "ANYONE can launch again, against every enabled listing")]


def _find(st, ref):
    for L in st["listings"]:
        if ref.upper() == L["symbol"].upper() or ref.lower() == L["stock"].lower(): return L
    raise Refuse(f"{ref}: not a symbol or stock address in addresses.json")


def _relist(st, refs, enabled):
    """Re-call `list` with everything read back from the listing, and only `enabled` changed."""
    out = []
    for ref in refs:
        L = _find(st, ref)
        if not L.get("listed", L["oracle"] != ZERO): raise Refuse(f"{L['symbol']} ({L['stock']}) has never been listed on this factory: nothing to {'enable' if enabled else 'disable'}")
        if L["enabled"] == enabled: continue
        word = "re-enabled: new launches allowed" if enabled else "disabled: new launches revert NotListed; launched strategies untouched"
        out.append(make_call(st["factory"], "list", [L["stock"], L["oracle"], L["v3Pool"], int(L["openPriceE18"]), enabled], f"{L['symbol']} {word}"))
    return out


def plan_delist(st, refs): return _relist(st, refs, False)
def plan_relist(st, refs): return _relist(st, refs, True)


def plan_halt(st, days, skip_unowned=False):
    if days < 1: raise Refuse("--days must be at least 1")
    out = []
    for c in _owned_calendars(st, skip_unowned):
        for d in range(c["today"], c["today"] + days):
            was = c["overrides"].get(str(d), 0)
            if was == 1: continue
            note = f"{day_str(d)} forced shut" + (" (WAS forced open: resume will set it to none, not back to open)" if was == 2 else "")
            out.append(make_call(c["address"], "setOverride", [d, 1], note))
    return out


def halted_through(c):
    """Last day of the unbroken run of forced-shut days starting today, or None if today is not forced shut."""
    d = c["today"]
    if c["overrides"].get(str(d), 0) != 1: return None
    while c["overrides"].get(str(d + 1), 0) == 1: d += 1
    return d


def plan_extend(st, days, skip_unowned=False):
    if days < 1: raise Refuse("--days must be at least 1")
    out = []
    for c in _owned_calendars(st, skip_unowned):
        last = halted_through(c)
        if last is None:
            raise Refuse(f"calendar {c['address']} is not forced shut today ({day_str(c['today'])}): there is no halt to extend. "
                         f"If the halt already lapsed, the rule is LIVE right now -- use `halt`.")
        for d in range(last + 1, last + 1 + days):
            if c["overrides"].get(str(d), 0) != 1: out.append(make_call(c["address"], "setOverride", [d, 1], f"{day_str(d)} forced shut (extension)"))
    return out


def plan_resume_halt(st, keep=(), only=None, skip_unowned=True):
    out = []
    for c in _owned_calendars(st, skip_unowned):
        for d, m in sorted((int(k), v) for k, v in c["overrides"].items()):
            if m != 1 or d < c["today"] or d in keep: continue
            if only is not None and (c["address"].lower(), d) not in only: continue
            out.append(make_call(c["address"], "setOverride", [d, 0], f"{day_str(d)} back to the schedule"))
    return out


def plan_everything(st, days, skip_unowned=False):
    enabled = [L["stock"] for L in st["listings"] if L.get("listed", L["oracle"] != ZERO) and L["enabled"]]
    # the halt first: it is the only part that touches money already in treasuries
    return plan_halt(st, days, skip_unowned) + plan_stop_launches(st) + plan_delist(st, enabled)


def plan_resume_everything(st, refs, reopen_launch, keep=(), only=None):
    # mirror image, reverse order: the rule last, because it is the part that starts trading
    return plan_relist(st, refs) + (plan_resume_launches(st) if reopen_launch else []) + plan_resume_halt(st, keep, only)


# ---------------------------------------------------------------------------------------------------- the Safe file
def _tx_json(c):
    _, inputs = METHODS[c["name"]]
    ins, vals = [], {}
    for (nm, ty), v in zip(inputs, c["values"]):
        ins.append({"internalType": ty, "name": nm, "type": ty})
        vals[nm] = _arg(v)
    return {"to": c["to"], "value": "0", "data": c["data"],
            "contractMethod": {"inputs": ins, "name": c["name"], "payable": False}, "contractInputsValues": vals}


def _serialize(j):
    """safe-react-apps/apps/tx-builder/src/lib/checksum.ts, serializeJSONObject, reproduced exactly."""
    if isinstance(j, list): return "[" + ",".join(_serialize(e) for e in j) + "]"
    if isinstance(j, dict):
        keys = sorted(j.keys())
        return "{" + json.dumps(keys, separators=(",", ":"), ensure_ascii=False) + "".join(_serialize(j[k]) + "," for k in keys) + "}"
    return json.dumps(j, separators=(",", ":"), ensure_ascii=False)


def safe_checksum(batch):
    """keccak of the canonical serialisation with meta.name nulled and meta.checksum absent -- what the Transaction
    Builder recomputes on import. A mismatch makes the UI warn that the file was changed after it was exported."""
    meta = {k: v for k, v in batch["meta"].items() if k != "checksum"}; meta["name"] = None
    return keccak_text(_serialize({**batch, "meta": meta}))


def batch_digest(txs):
    """keccak over every (to, data) in order: one short string to read aloud between whoever built the file and whoever signs it."""
    return keccak_text("|".join(f"{t['to'].lower()}:{t['data'].lower()}" for t in txs))


def bundle(calls, chain_id, safe, name, description):
    b = {"version": "1.0", "chainId": str(chain_id), "createdAt": int(time.time() * 1000),
         "meta": {"name": name, "description": description, "txBuilderVersion": "1.16.5",
                  "createdFromSafeAddress": safe, "createdFromOwnerAddress": ""},
         "transactions": [_tx_json(c) for c in calls]}
    b["meta"]["checksum"] = safe_checksum(b)
    return b


def describe(calls, st):
    names = {st["factory"]: "HedgeFunFactory"}
    for c in st.get("calendars", []): names[c["address"]] = "TradingCalendar"
    lines = []
    for i, c in enumerate(calls, 1):
        _, inputs = METHODS[c["name"]]
        lines.append(f"  [{i}/{len(calls)}] to {c['to']}  ({names.get(c['to'], 'UNKNOWN TARGET')})")
        lines.append(f"        {c['name']}(" + ", ".join(f"{nm}={_arg(v)}" for (nm, _), v in zip(inputs, c["values"])) + ")")
        if c["name"] == "setOverride": lines.append(f"        day {c['values'][0]} = {day_str(c['values'][0])}, mode {c['values'][1]} = {MODES[c['values'][1]]}")
        if c["note"]: lines.append(f"        -> {c['note']}")
        lines.append(f"        data {c['data']}")
    return "\n".join(lines)


def simulate(calls, st, rpc):
    """eth_call each transaction FROM the Safe against the latest block. Every call this kit emits stands on its own --
    none depends on an earlier one in the same batch -- so each is checked alone and a revert refuses the batch."""
    out = []
    for i, c in enumerate(calls, 1):
        try:
            rpc._req("eth_call", [{"from": st["safe"], "to": c["to"], "data": c["data"]}, "latest"]); out.append(f"  [{i}] eth_call from the Safe: ok")
        except RpcError as e:
            raise Refuse(f"transaction {i} ({c['name']}) REVERTS when simulated from the Safe: {e}. The batch was not written.")
    return "\n".join(out)


def write_batch(playbook, calls, st, rpc, description, out_dir):
    if not calls:
        print(f"\nNOTHING TO DO: the chain is already in the state `{playbook}` would produce. No file written.\n"); return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    b = bundle(calls, st["chainId"], st["safe"], f"EMERGENCY {playbook} {stamp}", description)
    text = [f"playbook   {playbook}", f"chain      {st['chainId']}   block {st['block']}   "
            f"{datetime.datetime.fromtimestamp(st['timestamp'], datetime.timezone.utc):%Y-%m-%d %H:%M:%S} UTC", f"safe       {st['safe']}",
            f"what       {description}", "", describe(calls, st), "", "simulation", simulate(calls, st, rpc), "",
            f"transactions   {len(calls)}", f"meta.checksum  {b['meta']['checksum']}", f"batch digest   {batch_digest(b['transactions'])}"]
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stamp}-{playbook}.json"
    try: shown = path.resolve().relative_to(Path.cwd())
    except ValueError: shown = path
    path.write_text(json.dumps(b, indent=2) + "\n")
    (out_dir / f"{stamp}-{playbook}.txt").write_text("\n".join(text) + "\n")
    print("\n".join(text))
    print(f"\nwrote {shown}\n      {shown.with_suffix('.txt')}  (this summary; send both to the signers)")
    print("\nNEXT  Safe UI -> Apps -> Transaction Builder -> drag the JSON in -> Create Batch -> Simulate -> Send Batch.")
    print(f"      Every signer first runs:  python3 emergency/build.py decode {shown}")
    print("      and reads the batch digest back to you. NOTHING has been sent; this tool cannot send.")
    return path


# ---------------------------------------------------------------------------------------------------- decode (signers)
def decode_file(path, addrs=None):
    b = json.loads(Path(path).read_text())
    ok = True
    def flag(msg):
        nonlocal ok; ok = False; print(f"  !! {msg}")
    print(f"file       {path}\nname       {b['meta'].get('name')}\nchainId    {b.get('chainId')}\nsafe       {b['meta'].get('createdFromSafeAddress')}")
    if addrs:
        if str(addrs["chainId"]) != str(b.get("chainId")): flag(f"chainId is {b.get('chainId')}, addresses.json says {addrs['chainId']}")
        if addrs["safe"].lower() != str(b["meta"].get("createdFromSafeAddress", "")).lower(): flag("createdFromSafeAddress is not the Safe in addresses.json")
    want = safe_checksum(b)
    if b["meta"].get("checksum") != want: flag(f"meta.checksum {b['meta'].get('checksum')} does not match the file's contents ({want}): EDITED after it was built")
    by_sel = {selector(sig): (name, sig, inputs) for name, (sig, inputs) in METHODS.items()}
    cfg_sel = {selector(sig): (name, sig, inputs) for name, (sig, inputs) in {**CONFIG_METHODS, **GOVERNANCE_METHODS}.items()}
    known = {}
    if addrs: known = {addrs["factory"].lower(): "HedgeFunFactory", **{c.lower(): "TradingCalendar" for c in addrs["calendars"]}}
    for i, t in enumerate(b["transactions"], 1):
        print(f"  [{i}/{len(b['transactions'])}] to {t['to']}  ({known.get(t['to'].lower(), 'NOT IN addresses.json' if addrs else 'unchecked')})")
        if addrs and t["to"].lower() not in known: flag("target is not the factory or a calendar from addresses.json")
        if str(t.get("value", "0")) != "0": flag(f"value is {t.get('value')}: no playbook sends value")
        data = (t.get("data") or "").lower()
        hit = by_sel.get(data[:10])
        if not hit:
            cfg = cfg_sel.get(data[:10])
            if cfg:
                cname, csig, cinputs = cfg
                try:
                    cvals = json.loads(cast("calldata-decode", "--json", csig, data))
                    print(f"        {cname}(" + ", ".join(f"{nm}={_arg(_norm(v))}" for (nm, _), v in zip(cinputs, cvals)) + ")")
                except Refuse:
                    print(f"        {cname}(<arguments do not decode>)")
                if cname in GOVERNANCE_METHODS:
                    flag(f"{cname} is a governance action, not an emergency lever -- it does not belong in an emergency batch. It is the one owner call on a launched TREASURY: it points the votes of the stock held there, moves no asset, cannot reach the rule and stops nothing. DO NOT SIGN it here; it is its own decision and its own transaction (docs/OPERATIONS.md)."); continue
                flag(f"{cname} is a configuration change, not an emergency lever -- it does not belong in an emergency batch. It reaches FUTURE launches only and stops nothing that exists. DO NOT SIGN it here; it is prepared and reviewed as its own transaction (docs/OPERATIONS.md)."); continue
            flag(f"selector {data[:10]} is NOT a function this kit emits ({', '.join(METHODS)}). transferOwnership / renounceOwnership / setDefaults / anything on the hook / anything else does not belong in an emergency batch. DO NOT SIGN."); continue
        name, sig, inputs = hit
        want_to = "TradingCalendar" if name == "setOverride" else "HedgeFunFactory"
        if addrs and known.get(t["to"].lower()) not in (None, want_to): flag(f"{name} is a {want_to} function but the target is a {known[t['to'].lower()]}")
        vals = json.loads(cast("calldata-decode", "--json", sig, data))
        recoded = cast("calldata", sig, *[_arg(_norm(v)) for v in vals]).lower()
        if recoded != data: flag("calldata does not round-trip through its own decoding (trailing or malformed bytes)")
        print(f"        {name}(" + ", ".join(f"{nm}={_arg(_norm(v))}" for (nm, _), v in zip(inputs, vals)) + ")")
        if name == "setOverride":
            print(f"        day {vals[0]} = {day_str(vals[0])}, mode {vals[1]} = {MODES.get(int(vals[1]), '??')}")
            if int(vals[1]) == 2: flag("mode 2 FORCES A DAY OPEN. No playbook in this kit does that. DO NOT SIGN without knowing exactly why.")
        shown = t.get("contractInputsValues") or {}
        mine = _tx_json({"to": t["to"], "name": name, "values": [_norm(v) for v in vals], "data": data})["contractInputsValues"]
        if (t.get("contractMethod") or {}).get("name") != name or {k: str(v).lower() for k, v in shown.items()} != {k: v.lower() for k, v in mine.items()}:
            flag("the decoded view in the file (contractMethod / contractInputsValues) does NOT match the raw data. The raw data is what executes.")
    print(f"\ntransactions   {len(b['transactions'])}\nmeta.checksum  {b['meta'].get('checksum')}\nbatch digest   {batch_digest(b['transactions'])}")
    print("\nVERDICT  " + ("consistent. Now compare the batch digest with the person who built it, by voice." if ok else "PROBLEMS ABOVE. DO NOT SIGN."))
    return ok


def _norm(v):
    if isinstance(v, list): return [_norm(x) for x in v]
    if isinstance(v, bool): return v
    if isinstance(v, str) and ADDR_RE.match(v): return checksum_addr(v)
    if isinstance(v, str) and re.match(r"^-?\d+$", v): return int(v)
    return v


def parse_batch(path):
    """What a batch built by this kit did, so a resume can undo exactly that and nothing it did not do."""
    b = json.loads(Path(path).read_text())
    if b["meta"].get("checksum") != safe_checksum(b): raise Refuse(f"{path}: checksum does not match its contents; not using an edited file as the source of a resume")
    by_sel = {selector(sig): (name, sig) for name, (sig, _) in METHODS.items()}
    stocks, days, closed_launch = [], set(), False
    for t in b["transactions"]:
        name, sig = by_sel[t["data"][:10].lower()]
        vals = [_norm(v) for v in json.loads(cast("calldata-decode", "--json", sig, t["data"]))]
        if name == "list" and vals[-1] is False: stocks.append(vals[0])
        if name == "setOverride" and vals[1] == 1: days.add((t["to"].lower(), vals[0]))
        if name == "setPublicLaunch" and vals[0] is False: closed_launch = True
    return stocks, days, closed_launch


# ---------------------------------------------------------------------------------------------------- status
def _gates_str(g):
    if g is None: return "not readable on this factory"
    chunk = f"sell chunk {g[2] / 1e6:,.2f} USDG" if g[2] else "sell chunk default"
    if not (g[0] or g[1]): return f"deviation/slippage defaults / {chunk}" + ("  <- this stock's own chunk; new launches only" if g[2] else " (none set for this stock)")
    return f"deviation {g[0]} bps / slippage {g[1]} bps / {chunk}  <- this stock's own; new launches only. Slippage is the most a sandwich takes per treasury trade"


def print_status(st, days):
    now = datetime.datetime.fromtimestamp(st["timestamp"], datetime.timezone.utc)
    print(f"chain {st['chainId']}   block {st['block']}   {now:%a %Y-%m-%d %H:%M:%S} UTC   (READ-ONLY: eth_call only)")
    print(f"safe     {st['safe']}\nfactory  {st['factory']}   owner == safe: yes")
    print(f"  publicLaunch      {st['publicLaunch']}   {'<- anyone can launch' if st['publicLaunch'] else '<- only the Safe can launch'}")
    print("\nlistings")
    for L in st["listings"]:
        if not L["listed"]: print(f"  {L['symbol']:<8} {L['stock']}  never listed"); continue
        print(f"  {L['symbol']:<8} {L['stock']}  {'ENABLED ' if L['enabled'] else 'disabled'}  V3 pool {L['v3Pool']}\n           oracle {L['oracle']}  calendar {L['calendar']}  openPriceE18 {L['openPriceE18']}  bandCeiling {L['bandCeiling']} bps/h{'  <- new launches may TRADE closures' if L['bandCeiling'] else ''}\n           listingGates {_gates_str(L.get('gates'))}")
    print("\ncalendars")
    for c in st["calendars"]:
        own = "owner == safe" if c["owner"] == st["safe"] else f"OWNER IS {c['owner']} -- THE SAFE CANNOT HALT THIS ONE"
        print(f"  {c['address']}  {own}\n    used by: {', '.join(c['usedBy']) or 'nothing read from the chain (listed in addresses.json only)'}")
        et = now + datetime.timedelta(seconds=c["utcOffset"])
        print(f"    Eastern time now {et:%a %H:%M} -> trading date {c['today']} ({day_str(c['today'])});  isClosed(now) = {c['closedNow']}")
        for d in range(c["today"], c["today"] + days):
            m = c["overrides"].get(str(d), 0)
            print(f"      {d}  {day_str(d)}  override {m} {MODES[m]}")
        last = halted_through(c)
        if last is not None:
            # trading date `last` ends at 20:00 ET on that civil date
            end = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=last, hours=20, seconds=-c["utcOffset"])
            print(f"    HALT IN FORCE through {day_str(last)}. It lapses BY ITSELF at {end:%a %Y-%m-%d %H:%M} UTC (20:00 ET) unless extended.")
        else: print("    no halt in force today")
    print(f"\nstrategies ({st['strategyCount']})")
    for S in st["strategies"]:
        left = ""
        if S["buybackStock"]:
            until = S["lastGoodPriceAt"] + 5 * 86400
            left = (f"  buyback funded ({S['buybackStock']} wei of stock); while unhealthy it can still size until "
                    f"{datetime.datetime.fromtimestamp(until, datetime.timezone.utc):%a %m-%d %H:%M} UTC")
        print(f"  #{S['id']:<3} {S['symbol']:<10} treasury {S['treasury']}  health = {str(S['healthy']).lower():<5} price {S['price']}"
              f"{'  [pool-only price: scheduled closure]' if S['pricedOffPoolOnly'] else ''}"
              f"{'  band=' + str(S['bandBpsPerHour']) + 'bps/h (trades closures)' if S['bandBpsPerHour'] else ''}{left}")
    healthy = [S for S in st["strategies"] if S["healthy"]]
    print(f"\n  {len(healthy)} of {st['strategyCount']} strategies have health() == true" + (": the rule can trade in them right now." if healthy else ": the rule is stopped everywhere."))
    for w in st["warnings"]: print(f"\nWARNING  {w}")


# ---------------------------------------------------------------------------------------------------- cli
def main(argv=None):
    ap = argparse.ArgumentParser(description="Build Safe Transaction Builder batches for the launchpad's emergency levers. Never signs, never sends.")
    ap.add_argument("--addresses", default=str(HERE / "addresses.json"))
    ap.add_argument("--rpc", help="override the RPC in addresses.json (a local anvil fork during a drill)")
    ap.add_argument("--out", default=str(HERE / "out"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--days", type=int, default=7)
    sub.add_parser("stop-launches"); sub.add_parser("resume-launches")
    for n in ("delist", "relist"): sub.add_parser(n).add_argument("stocks", nargs="+", metavar="SYM|addr")
    for n in ("halt", "extend", "everything"):
        p = sub.add_parser(n); p.add_argument("--days", type=int, required=True); p.add_argument("--skip-unowned", action="store_true")
    p = sub.add_parser("resume-halt"); p.add_argument("--keep", default="", help="comma-separated day indices to leave forced shut (a real day of mourning)")
    p.add_argument("--window", type=int, default=SCAN_DAYS)
    p = sub.add_parser("resume-everything"); p.add_argument("--from", dest="src", help="the `everything` batch to undo: re-enables exactly what it disabled")
    p.add_argument("stocks", nargs="*", metavar="SYM|addr"); p.add_argument("--reopen-launches", action="store_true"); p.add_argument("--keep", default="")
    p.add_argument("--window", type=int, default=SCAN_DAYS)
    sub.add_parser("decode").add_argument("file")
    e = sub.add_parser("encode", help="offline: planner + encoder on a state given as JSON; prints abi.encode(address[],bytes[]). For test/Emergency.t.sol.")
    e.add_argument("playbook"); e.add_argument("--state", required=True); e.add_argument("--days", type=int, default=0)
    e.add_argument("--stocks", default=""); e.add_argument("--reopen-launches", action="store_true")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "encode":
            st = json.loads(a.state); refs = [s for s in a.stocks.split(",") if s]
            calls = {"stop-launches": lambda: plan_stop_launches(st), "resume-launches": lambda: plan_resume_launches(st),
                     "delist": lambda: plan_delist(st, refs), "relist": lambda: plan_relist(st, refs),
                     "halt": lambda: plan_halt(st, a.days), "extend": lambda: plan_extend(st, a.days), "resume-halt": lambda: plan_resume_halt(st),
                     "everything": lambda: plan_everything(st, a.days),
                     "resume-everything": lambda: plan_resume_everything(st, refs, a.reopen_launches)}[a.playbook]()
            print(cast("abi-encode", "f(address[],bytes[])", "[" + ",".join(c["to"] for c in calls) + "]", "[" + ",".join(c["data"] for c in calls) + "]"))
            return 0
        if a.cmd == "decode":
            addrs = load_addresses(a.addresses) if Path(a.addresses).exists() else None
            if addrs is None: print("(no addresses.json here: targets are NOT being checked against it)\n")
            return 0 if decode_file(a.file, addrs) else 1

        addrs = load_addresses(a.addresses)
        rpc = Rpc(a.rpc or addrs["rpc"])
        window = max(getattr(a, "window", SCAN_DAYS), getattr(a, "days", 0) + SCAN_DAYS)
        st = read_state(addrs, rpc, window=window, with_strategies=a.cmd == "status")
        if a.cmd == "status": print_status(st, a.days); return 0
        for w in st["warnings"]: print(f"WARNING  {w}\n")

        keep = tuple(int(x) for x in getattr(a, "keep", "").split(",") if x)
        if a.cmd == "stop-launches": calls, what = plan_stop_launches(st), "L1: setPublicLaunch(false). Strangers cannot launch; the Safe still can."
        elif a.cmd == "resume-launches": calls, what = plan_resume_launches(st), "RESUME L1: setPublicLaunch(true). Anyone can launch against every enabled listing."
        elif a.cmd == "delist": calls, what = plan_delist(st, a.stocks), f"L2: disable the listing of {', '.join(a.stocks)}. New launches revert NotListed; launched strategies are untouched."
        elif a.cmd == "relist": calls, what = plan_relist(st, a.stocks), f"RESUME L2: re-enable the listing of {', '.join(a.stocks)} on the terms currently stored."
        elif a.cmd == "halt": calls, what = plan_halt(st, a.days, a.skip_unowned), f"L3: force {a.days} trading date(s) shut from today on every calendar. The rule stops; token pools, tax, sweep and buy-backs do NOT."
        elif a.cmd == "extend": calls, what = plan_extend(st, a.days, a.skip_unowned), f"L3 EXTEND: {a.days} more forced-shut trading date(s) after the last one already set."
        elif a.cmd == "resume-halt": calls, what = plan_resume_halt(st, keep), "RESUME L3: every forced-shut day from today on goes back to the schedule. The rule starts trading again."
        elif a.cmd == "everything": calls, what = plan_everything(st, a.days, a.skip_unowned), f"L4: halt {a.days} day(s) + stop public launches + disable every enabled listing."
        else:
            refs, only, reopen = list(a.stocks), None, a.reopen_launches
            if a.src:
                stocks, only, closed = parse_batch(a.src); refs += [s for s in stocks if s.lower() not in {r.lower() for r in refs}]; reopen = reopen or closed
            calls, what = plan_resume_everything(st, refs, reopen, keep, only), "RESUME L4: re-enable listings, reopen launches, clear the forced-shut days. Mirror of `everything`."
        write_batch(a.cmd, calls, st, rpc, what, a.out)
        return 0
    except Refuse as r:
        print(f"\nREFUSED: {r}\n", file=sys.stderr); return 2
    except RpcError as r:
        print(f"\nREFUSED: the RPC answered with an error and this kit does not guess: {r}\n", file=sys.stderr); return 2


if __name__ == "__main__":
    sys.exit(main())
