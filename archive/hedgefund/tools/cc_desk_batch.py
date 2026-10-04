#!/usr/bin/env python3
"""Safe Transaction Builder batches for the CoveredCallDesk. Nothing else.

Same rule as emergency/build.py, whose encoder, checksum, RPC reader and refusal discipline this reuses: it never
signs, never broadcasts, never holds a key. It reads the chain with eth_call and writes one JSON file for the Safe UI.

    # once, after the deploy script: list the stocks, allow the writer (the Safe) and the market maker
    python3 tools/cc_desk_batch.py setup --desk 0xDESK --buyer 0xMARKETMAKER --stocks NVDA
    # the same without --buyer lists the stocks and allows the writer now; setBuyer comes in its own batch later
    # every week, after the RFQ: approve + offer with the agreed terms
    python3 tools/cc_desk_batch.py offer --desk 0xDESK --stock NVDA --size 280 --strike 240 --premium 1.80 \
        --expiry 2026-10-09 --buyer 0xMARKETMAKER
    # what every signer runs on the file they were sent
    python3 tools/cc_desk_batch.py decode deploy/safe/<file>.json

`--check` runs every check and the simulation but writes nothing. Both planners refuse, and write nothing, unless the
chain agrees with every input: the desk is owned by the Safe and not paused, each stock's feed is the one the
launchpad's PriceOracle already prices it with (resolved by address, never by name), the feed has 8 decimals and
describes `RH<SYM> / USD`, the token has 18 decimals and answers `uiMultiplier()` / `oraclePaused()`, and for an
offer: the stock is listed, the writer and buyer are allowed, the Safe holds the size, the expiry is a market day,
and the three live fields `offer` binds (feed, exerciseWindow, stockMultiplier) are read at build time. Every call is
then simulated from the Safe, except `offer` when the allowance it needs is granted by the `approve` in the same
batch, which eth_call cannot chain; its own revert conditions are checked statically above.

Strike and premium are typed per WHOLE token in USDG (`--strike 240`, `--premium 1.80`); size in whole tokens. The
file carries base units: size 1e18, strike and premium 1e6, premium for the whole size.
"""
import argparse, datetime, json, sys, time, zoneinfo
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emergency"))
import build  # noqa: E402

ET = zoneinfo.ZoneInfo("America/New_York")
CLOSE_ET = datetime.time(16, 0)
TERMS_T = "(address,address,uint128,uint128,uint128,uint64,uint64,uint8,address,uint32,uint256)"
TERMS_FIELDS = [("buyer", "address"), ("underlying", "address"), ("size", "uint128"), ("strike", "uint128"),
                ("premium", "uint128"), ("expiry", "uint64"), ("fillDeadline", "uint64"), ("mode", "uint8"),
                ("feed", "address"), ("exerciseWindow", "uint32"), ("stockMultiplier", "uint256")]
MODES = {"physical": 0, "netshare": 1}
# name -> (signature, [(argName, type)]); `offer` takes the Terms tuple, spelled out for the Safe UI
METHODS = {
    "list": ("list(address,address,bool)", [("underlying", "address"), ("feed", "address"), ("enabled", "bool")]),
    "setWriter": ("setWriter(address,bool)", [("writer", "address"), ("allowed", "bool")]),
    "setBuyer": ("setBuyer(address,bool)", [("buyer", "address"), ("allowed", "bool")]),
    "approve": ("approve(address,uint256)", [("spender", "address"), ("amount", "uint256")]),
    "offer": (f"offer({TERMS_T})", [("t", "tuple")]),
}
UNUSUAL = "re-run with --unusual if these terms are really what was agreed"


# ---------------------------------------------------------------------------------------------------- reads
def rd_addr(rpc, to, sig, *a): return build.w_addr(rpc.call(to, sig, *a)[0])
def rd_uint(rpc, to, sig, *a): return build.w_uint(rpc.call(to, sig, *a)[0])
def rd_bool(rpc, to, sig, *a): return build.w_bool(rpc.call(to, sig, *a)[0])


def rd_str(rpc, to, sig, *a):
    w = rpc.call(to, sig, *a)
    n = int(w[1], 16)
    return bytes.fromhex("".join(w[2:]))[:n].decode("utf-8", "replace")


def has_code(rpc, a): return rpc.code(a) not in ("0x", "")


def addresses():
    return json.loads((ROOT / "emergency" / "addresses.json").read_text())


def desk_state(rpc, desk, safe):
    if not has_code(rpc, desk): raise build.Refuse(f"no code at desk {desk}")
    st = {"desk": desk, "safe": safe, "owner": rd_addr(rpc, desk, "owner()"), "paused": rd_bool(rpc, desk, "paused()"),
          "usdg": rd_addr(rpc, desk, "usdg()"), "calendar": rd_addr(rpc, desk, "calendar()"),
          "exerciseWindow": rd_uint(rpc, desk, "exerciseWindow()"), "nextId": rd_uint(rpc, desk, "nextId()")}
    if st["owner"].lower() != safe.lower(): raise build.Refuse(f"desk owner is {st['owner']}, not the Safe {safe}")
    return st


def listing_of(rpc, desk, token):
    w = rpc.call(desk, "listings(address)", token)
    return {"feed": build.w_addr(w[0]), "feedDecimals": build.w_uint(w[1]), "enabled": build.w_bool(w[2])}


def stock_facts(rpc, addrs, sym):
    """The token by symbol from addresses.json; its feed from the launchpad's PriceOracle, by address."""
    if sym not in addrs["stocks"]: raise build.Refuse(f"{sym}: not in emergency/addresses.json stocks")
    token = build.checksum_addr(addrs["stocks"][sym])
    oracle = build.w_addr(rpc.call(addrs["factory"], "listings(address)", token)[0])
    if oracle.lower() == build.ZERO: raise build.Refuse(f"{sym}: the factory has no PriceOracle for it, so there is no feed to copy -- list it on the launchpad first")
    feed = rd_addr(rpc, oracle, "stockFeed()")
    if rd_uint(rpc, token, "decimals()") != 18: raise build.Refuse(f"{sym}: token decimals != 18")
    if rd_uint(rpc, feed, "decimals()") != 8: raise build.Refuse(f"{sym}: feed {feed} decimals != 8")
    desc = rd_str(rpc, feed, "description()")
    if desc != f"RH{sym} / USD": raise build.Refuse(f"{sym}: feed {feed} describes itself as {desc!r}, expected 'RH{sym} / USD'")
    try:
        mult = rd_uint(rpc, token, "uiMultiplier()"); paused = rd_bool(rpc, token, "oraclePaused()")
    except build.RpcError as e:
        raise build.Refuse(f"{sym}: token does not answer uiMultiplier()/oraclePaused(): {e}")
    w = rpc.call(feed, "latestRoundData()")
    return {"sym": sym, "token": token, "oracle": oracle, "feed": feed, "description": desc, "multiplier": mult, "oraclePaused": paused,
            "price": build.w_int(w[1]) / 1e8, "priceAt": build.w_uint(w[3]), "symbol": rd_str(rpc, token, "symbol()")}


# ---------------------------------------------------------------------------------------------------- calls and the file
def make_call(to, name, values, note=""):
    sig, inputs = METHODS[name]
    if len(values) != len(inputs): raise build.Refuse(f"{name}: wrong argument count")
    data = build.cast("calldata", sig, *[build._arg(v) for v in values]).lower()
    if not data.startswith(build.selector(sig)): raise build.Refuse(f"{name}: cast returned a foreign selector")
    return {"to": to, "name": name, "values": list(values), "data": data, "note": note}


def tx_json(c):
    _, inputs = METHODS[c["name"]]
    ins, vals = [], {}
    for (nm, ty), v in zip(inputs, c["values"]):
        if ty == "tuple":
            ins.append({"internalType": "struct CoveredCallDesk.Terms", "name": nm, "type": "tuple",
                        "components": [{"internalType": t, "name": n, "type": t} for n, t in TERMS_FIELDS]})
            vals[nm] = json.dumps([build._arg(x) for x in v])
        else:
            ins.append({"internalType": ty, "name": nm, "type": ty}); vals[nm] = build._arg(v)
    return {"to": c["to"], "value": "0", "data": c["data"],
            "contractMethod": {"inputs": ins, "name": c["name"], "payable": False}, "contractInputsValues": vals}


def bundle(calls, chain_id, safe, name, description):
    b = {"version": "1.0", "chainId": str(chain_id), "createdAt": int(time.time() * 1000),
         "meta": {"name": name, "description": description, "txBuilderVersion": "1.16.5",
                  "createdFromSafeAddress": safe, "createdFromOwnerAddress": ""},
         "transactions": [tx_json(c) for c in calls]}
    b["meta"]["checksum"] = build.safe_checksum(b)
    return b


def describe(calls, names):
    lines = []
    for i, c in enumerate(calls, 1):
        _, inputs = METHODS[c["name"]]
        lines.append(f"  [{i}/{len(calls)}] to {c['to']}  ({names.get(c['to'].lower(), 'UNKNOWN TARGET')})")
        if c["name"] == "offer":
            lines.append("        offer(" + ", ".join(f"{n}={build._arg(v)}" for (n, _), v in zip(TERMS_FIELDS, c["values"][0])) + ")")
        else:
            lines.append(f"        {c['name']}(" + ", ".join(f"{nm}={build._arg(v)}" for (nm, _), v in zip(inputs, c["values"])) + ")")
        if c["note"]: lines.append(f"        -> {c['note']}")
        lines.append(f"        data {c['data']}")
    return "\n".join(lines)


def simulate(calls, safe, rpc, skip=()):
    out = []
    for i, c in enumerate(calls, 1):
        if i in skip: out.append(f"  [{i}] {c['name']}: not simulated -- {skip[i]}"); continue
        try:
            rpc._req("eth_call", [{"from": safe, "to": c["to"], "data": c["data"]}, "latest"]); out.append(f"  [{i}] {c['name']}: eth_call from the Safe ok")
        except build.RpcError as e:
            raise build.Refuse(f"transaction {i} ({c['name']}) REVERTS when simulated from the Safe: {e}. The batch was not written.")
    return "\n".join(out)


def write(playbook, calls, chain_id, safe, description, lines, check):
    if not calls: print("\nNOTHING TO DO: the chain is already in the state this batch would produce. No file written."); return None
    print("\n".join(lines))
    if check: print("\n--check: nothing written."); return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    b = bundle(calls, chain_id, safe, f"CC-DESK {playbook} {stamp}", description)
    out = ROOT / "deploy" / "safe" / f"{stamp}-cc-desk-{playbook}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(b, indent=2) + "\n")
    out.with_suffix(".txt").write_text("\n".join(lines) + "\n")
    print(f"\ntransactions   {len(calls)}\nmeta.checksum  {b['meta']['checksum']}\nbatch digest   {build.batch_digest(b['transactions'])}\nwrote          {out.relative_to(ROOT)}")
    print("\nNEXT  Safe UI -> Apps -> Transaction Builder -> drag the JSON in -> Create Batch -> Simulate -> Send Batch.")
    print(f"      Every signer first runs:  python3 tools/cc_desk_batch.py decode {out.relative_to(ROOT)}")
    print("      and reads the batch digest back to you. NOTHING has been sent; this tool cannot send.")
    return out


# ---------------------------------------------------------------------------------------------------- planners
def plan_setup(a, rpc, addrs):
    safe, desk = addrs["safe"], build.checksum_addr(a.desk)
    st = desk_state(rpc, desk, safe)
    if st["usdg"].lower() != "0x5fc5360d0400a0fd4f2af552add042d716f1d168": raise build.Refuse(f"desk usdg is {st['usdg']}")
    if st["calendar"].lower() not in [c.lower() for c in addrs["calendars"]]: raise build.Refuse(f"desk calendar {st['calendar']} is not in addresses.json")
    buyer = build.checksum_addr(a.buyer) if a.buyer else None
    if buyer and buyer.lower() in (safe.lower(), desk.lower()): raise build.Refuse("the buyer cannot be the Safe or the desk")
    calls, lines = [], ["setup", f"  desk {desk}  owner {st['owner']}  paused {st['paused']}  exerciseWindow {st['exerciseWindow']} s  nextId {st['nextId']}"]
    names = {desk.lower(): "CoveredCallDesk"}
    for sym in [s.strip().upper() for s in a.stocks.split(",") if s.strip()]:
        f = stock_facts(rpc, addrs, sym)
        cur = listing_of(rpc, desk, f["token"])
        age = int(time.time()) - f["priceAt"]
        lines.append(f"  {sym:6} token {f['token']}  feed {f['feed']} ({f['description']}, via PriceOracle {f['oracle']})  "
                     f"last ${f['price']:,.2f} {age // 60} min ago  uiMultiplier {f['multiplier']}  oraclePaused {f['oraclePaused']}")
        if cur["feed"].lower() == f["feed"].lower() and cur["enabled"]: lines.append(f"         already listed with this feed; skipped"); continue
        if cur["feed"] != build.ZERO and cur["feed"].lower() != f["feed"].lower():
            raise build.Refuse(f"{sym}: the desk already lists it with feed {cur['feed']}; re-listing with {f['feed']} is a deliberate change, not setup")
        calls.append(make_call(desk, "list", [f["token"], f["feed"], True], f"list {sym} with the launchpad's feed"))
    if rd_bool(rpc, desk, "isWriter(address)", safe): lines.append(f"  writer {safe} already allowed; skipped")
    else: calls.append(make_call(desk, "setWriter", [build.checksum_addr(safe), True], "the Safe writes the options"))
    if buyer is None: lines.append("  no --buyer: nobody may fill until a later setup batch names the market maker")
    elif rd_bool(rpc, desk, "isBuyer(address)", buyer): lines.append(f"  buyer {buyer} already allowed; skipped")
    else:
        calls.append(make_call(desk, "setBuyer", [buyer, True], "the market maker may fill"))
        if not has_code(rpc, buyer): lines.append(f"  note: buyer {buyer} has no code (an EOA); if they fill from a contract wallet, that is the address to allow")
    lines += ["", describe(calls, names), "", "simulation", simulate(calls, safe, rpc)]
    return calls, lines, f"list {a.stocks}, setWriter(Safe){f', setBuyer({buyer})' if buyer else ' (no buyer yet)'}. Built against desk {desk}."


def parse_when(text, what):
    """`YYYY-MM-DD` means 16:00 ET that day; `YYYY-MM-DDTHH:MM` is ET; anything with an offset is taken as is."""
    try:
        if len(text) == 10: t = datetime.datetime.combine(datetime.date.fromisoformat(text), CLOSE_ET, tzinfo=ET)
        else:
            t = datetime.datetime.fromisoformat(text)
            if t.tzinfo is None: t = t.replace(tzinfo=ET)
    except ValueError:
        raise build.Refuse(f"{what}: cannot parse {text!r}; use YYYY-MM-DD (16:00 ET) or YYYY-MM-DDTHH:MM[+offset]")
    return int(t.timestamp())


def fmt_when(ts): return datetime.datetime.fromtimestamp(ts, ET).strftime("%a %Y-%m-%d %H:%M ET")


def to_units(text, decimals, what):
    try: d = Decimal(text)
    except Exception: raise build.Refuse(f"{what}: not a number: {text!r}")
    if d <= 0: raise build.Refuse(f"{what}: must be positive")
    q = (d * (10 ** decimals)).to_integral_value(rounding=ROUND_DOWN)
    if q != d * (10 ** decimals): raise build.Refuse(f"{what}: {text} has more than {decimals} decimals")
    return int(q)


def plan_offer(a, rpc, addrs):
    safe, desk = addrs["safe"], build.checksum_addr(a.desk)
    st = desk_state(rpc, desk, safe)
    if st["paused"]: raise build.Refuse("the desk is paused: no offers")
    if not rd_bool(rpc, desk, "isWriter(address)", safe): raise build.Refuse("the Safe is not an allowed writer -- run setup first")
    sym = a.stock.upper()
    f = stock_facts(rpc, addrs, sym)
    cur = listing_of(rpc, desk, f["token"])
    if not cur["enabled"]: raise build.Refuse(f"{sym} is not listed on the desk -- run setup first")
    if cur["feed"].lower() != f["feed"].lower(): raise build.Refuse(f"{sym}: desk lists feed {cur['feed']} but the launchpad prices with {f['feed']}; decide which before offering")
    if f["oraclePaused"]: raise build.Refuse(f"{sym}: oraclePaused() is true (corporate action in progress); offer would revert")
    buyer = build.checksum_addr(a.buyer) if a.buyer else build.ZERO
    if buyer != build.ZERO and not rd_bool(rpc, desk, "isBuyer(address)", buyer): raise build.Refuse(f"buyer {buyer} is not allowed on the desk -- run setup first")
    if buyer == build.ZERO: print("  note: no --buyer: ANY allowed buyer may fill this offer")

    now = int(time.time())
    size = to_units(a.size, 18, "--size"); strike = to_units(a.strike, 6, "--strike"); prem_per = to_units(a.premium, 6, "--premium")
    premium = prem_per * size // 10 ** 18
    expiry = parse_when(a.expiry, "--expiry")
    fill_by = parse_when(a.fill_by, "--fill-by") if a.fill_by else min(now + 2 * 86400, expiry)
    if expiry <= now: raise build.Refuse(f"--expiry {fmt_when(expiry)} is in the past")
    if expiry > now + 400 * 86400: raise build.Refuse("--expiry beyond the desk's MAX_TENOR")
    if not (now <= fill_by <= expiry): raise build.Refuse(f"--fill-by {fmt_when(fill_by)} must be between now and expiry")
    if rd_bool(rpc, st["calendar"], "isClosed(uint256)", expiry): raise build.Refuse(f"--expiry {fmt_when(expiry)}: the calendar says the market is closed then; offer would revert")
    if datetime.datetime.fromtimestamp(expiry, ET).time() != CLOSE_ET: print(f"  note: expiry {fmt_when(expiry)} is not the 16:00 ET close")
    bal = rd_uint(rpc, f["token"], "balanceOf(address)", safe)
    if bal < size: raise build.Refuse(f"the Safe holds {bal / 1e18:,.6f} {sym}, less than the size {size / 1e18:,.6f}")
    mode = MODES[a.mode]

    # sanity against the live print: a covered call is written out of the money, for a few percent, not a typo
    spot = f["price"]; strike_f = strike / 1e6; prem_f = prem_per / 1e6
    notional = size / 1e18 * spot; days = max((expiry - now) / 86400, 1e-9)
    unusual = []
    if strike_f < spot: unusual.append(f"strike ${strike_f:,.2f} is IN the money against the last print ${spot:,.2f}")
    if strike_f > 1.5 * spot: unusual.append(f"strike ${strike_f:,.2f} is more than 50% above the last print ${spot:,.2f}")
    if prem_f > 0.1 * spot: unusual.append(f"premium ${prem_f:,.2f}/token is more than 10% of the last print")
    if unusual and not a.unusual: raise build.Refuse("; ".join(unusual) + f". {UNUSUAL}")
    lines = ["offer", f"  desk {desk}  writer (Safe) {safe}  buyer {buyer if buyer != build.ZERO else 'any allowed buyer'}",
             f"  {sym} {f['token']}  size {size / 1e18:,.6f}  Safe balance {bal / 1e18:,.6f}",
             f"  strike ${strike_f:,.2f}/token  premium ${prem_f:,.4f}/token = ${premium / 1e6:,.2f} total  mode {a.mode}",
             f"  expiry {fmt_when(expiry)} ({expiry})  fill by {fmt_when(fill_by)} ({fill_by})",
             f"  bound live fields: feed {f['feed']} ({f['description']})  exerciseWindow {st['exerciseWindow']} s  stockMultiplier {f['multiplier']}",
             f"  last print ${spot:,.2f} {(now - f['priceAt']) // 60} min ago: strike {(strike_f / spot - 1) * 100:+.2f}% from spot, notional ${notional:,.0f}, "
             f"premium {premium / 1e6 / notional * 100:.3f}% of notional over {days:.1f} days ({premium / 1e6 / notional * 365 / days * 100:.1f}%/yr)"]
    if unusual: lines.append("  UNUSUAL (--unusual given): " + "; ".join(unusual))
    terms = [buyer, f["token"], size, strike, premium, expiry, fill_by, mode, cur["feed"], st["exerciseWindow"], f["multiplier"]]
    calls = [make_call(f["token"], "approve", [desk, size], f"let the desk pull {size / 1e18:,.6f} {sym}"),
             make_call(desk, "offer", [terms], f"option #{st['nextId']} if nothing else is offered first")]
    allowance = rd_uint(rpc, f["token"], "allowance(address,address)", safe, desk)
    skip = {} if allowance >= size else {2: f"the Safe's allowance to the desk is {allowance / 1e18:,.6f} < size; tx 1 grants it in the same batch, and eth_call cannot chain the two. offer's own checks (listing, writer, buyer, deadlines, calendar, stock controls, balance) were verified above."}
    names = {desk.lower(): "CoveredCallDesk", f["token"].lower(): f"{sym} token"}
    lines += ["", describe(calls, names), "", "simulation", simulate(calls, safe, rpc, skip)]
    return calls, lines, (f"approve + offer: {size / 1e18:,.6f} {sym}, strike {strike_f:,.2f}, premium {premium / 1e6:,.2f} USDG, "
                          f"expiry {fmt_when(expiry)}, {a.mode}, buyer {buyer}. Built against desk {desk}.")


# ---------------------------------------------------------------------------------------------------- decode (signers)
def decode_file(path):
    b = json.loads(Path(path).read_text())
    ok = True
    def flag(msg):
        nonlocal ok; ok = False; print(f"  !! {msg}")
    addrs = addresses()
    print(f"file       {path}\nname       {b['meta'].get('name')}\nchainId    {b.get('chainId')}\nsafe       {b['meta'].get('createdFromSafeAddress')}")
    if str(addrs["chainId"]) != str(b.get("chainId")): flag(f"chainId is {b.get('chainId')}, addresses.json says {addrs['chainId']}")
    if addrs["safe"].lower() != str(b["meta"].get("createdFromSafeAddress", "")).lower(): flag("createdFromSafeAddress is not the Safe in addresses.json")
    want = build.safe_checksum(b)
    if b["meta"].get("checksum") != want: flag(f"meta.checksum {b['meta'].get('checksum')} does not match the file's contents ({want}): EDITED after it was built")
    by_sel = {build.selector(sig): (name, sig, inputs) for name, (sig, inputs) in METHODS.items()}
    tokens = {v.lower(): k for k, v in addrs["stocks"].items()}
    desk = addrs.get("coveredCallDesk", "").lower()
    for i, t in enumerate(b["transactions"], 1):
        to = t["to"].lower()
        who = "CoveredCallDesk" if to == desk else f"{tokens[to]} token" if to in tokens else ("desk not yet in addresses.json" if not desk else "NOT IN addresses.json")
        print(f"  [{i}/{len(b['transactions'])}] to {t['to']}  ({who})")
        if str(t.get("value", "0")) != "0": flag(f"value is {t.get('value')}: no desk batch sends value")
        data = (t.get("data") or "").lower()
        hit = by_sel.get(data[:10])
        if not hit: flag(f"selector {data[:10]} is NOT a function this tool emits ({', '.join(METHODS)}). DO NOT SIGN."); continue
        name, sig, inputs = hit
        vals = json.loads(build.cast("calldata-decode", "--json", sig, data))
        if name == "offer":
            terms = [build._norm(v) for v in vals[0]]
            print("        offer(" + ", ".join(f"{n}={build._arg(v)}" for (n, _), v in zip(TERMS_FIELDS, terms)) + ")")
            print(f"        size {int(terms[2]) / 1e18:,.6f}  strike ${int(terms[3]) / 1e6:,.2f}  premium ${int(terms[4]) / 1e6:,.2f} total  "
                  f"expiry {fmt_when(int(terms[5]))}  fill by {fmt_when(int(terms[6]))}  mode {[k for k, v in MODES.items() if v == int(terms[7])][0]}")
            if to != desk and desk: flag("offer must target the desk")
            recoded = build.cast("calldata", sig, build._arg(terms)).lower()
        else:
            nv = [build._norm(v) for v in vals]
            print(f"        {name}(" + ", ".join(f"{nm}={build._arg(v)}" for (nm, _), v in zip(inputs, nv)) + ")")
            if name == "approve":
                print(f"        {int(nv[1]) / 1e18:,.6f} tokens to {nv[0]}")
                if to not in tokens: flag("approve must target a stock token from addresses.json")
                if desk and nv[0].lower() != desk: flag("approve spender is not the desk")
            elif to != desk and desk: flag(f"{name} must target the desk")
            recoded = build.cast("calldata", sig, *[build._arg(v) for v in nv]).lower()
        if recoded != data: flag("calldata does not round-trip through its own decoding (trailing or malformed bytes)")
        if (t.get("contractMethod") or {}).get("name") != name: flag("the decoded view in the file (contractMethod) does NOT match the raw data. The raw data is what executes.")
    print(f"\ntransactions   {len(b['transactions'])}\nmeta.checksum  {b['meta'].get('checksum')}\nbatch digest   {build.batch_digest(b['transactions'])}")
    print("\nVERDICT  " + ("consistent. Now compare the batch digest with the person who built it, by voice." if ok else "PROBLEMS ABOVE. DO NOT SIGN."))
    return ok


# ---------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup"); s.add_argument("--desk", required=True); s.add_argument("--buyer", help="the market maker; omit to list and allow the writer now and name the buyer later"); s.add_argument("--stocks", default="NVDA")
    o = sub.add_parser("offer"); o.add_argument("--desk", required=True); o.add_argument("--stock", required=True)
    o.add_argument("--size", required=True, help="whole tokens"); o.add_argument("--strike", required=True, help="USDG per whole token")
    o.add_argument("--premium", required=True, help="USDG per whole token, for the whole size it is premium x size")
    o.add_argument("--expiry", required=True, help="YYYY-MM-DD = 16:00 ET that day"); o.add_argument("--fill-by", help="default: 48 h from now, capped at expiry")
    o.add_argument("--buyer", help="the RFQ winner; omit to let any allowed buyer fill"); o.add_argument("--mode", choices=MODES, default="netshare")
    o.add_argument("--unusual", action="store_true", help="accept in-the-money, far, or very expensive terms")
    d = sub.add_parser("decode"); d.add_argument("file")
    for p in (s, o):
        p.add_argument("--check", action="store_true", help="check and simulate, write nothing")
        p.add_argument("--rpc", default="https://robinhood-rpc.publicnode.com")
    a = ap.parse_args(argv)
    if a.cmd == "decode": return 0 if decode_file(a.file) else 1
    addrs = addresses(); rpc = build.Rpc(a.rpc)
    if rpc.chain_id() != addrs["chainId"]: raise build.Refuse("wrong chain")
    calls, lines, description = (plan_setup if a.cmd == "setup" else plan_offer)(a, rpc, addrs)
    write(a.cmd, calls, addrs["chainId"], addrs["safe"], description, lines, a.check)
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except build.Refuse as e: sys.exit(f"REFUSED: {e}")
