#!/usr/bin/env python3
"""Turn a reviewed token-metadata plan (deploy/metadata-*.json) into a Safe Transaction Builder file. Nothing else.

Same rule as emergency/build.py, whose encoder, checksum and bundle format this reuses: it never signs, never
broadcasts, never holds a key. It reads the chain with eth_call, makes ONE other network request -- an HTTPS GET of
the logo URL, to prove the bytes are really served -- and writes one JSON file for the Safe UI.

    python3 tools/metadata_batch.py deploy/metadata-crclgrid-2026-09-22.json            # checks, simulates, writes
    python3 tools/metadata_batch.py deploy/metadata-crclgrid-2026-09-22.json --check    # checks only
    python3 tools/metadata_batch.py --decode deploy/safe/<file>.json                    # what signers run

`HedgeFunToken.setMetadata` REPLACES the whole entry -- logo, description, socials and extraURI are all written from
the four arguments (`HedgeFunToken.sol:_write`). A plan that omits a field wipes it. So for every token this refuses,
and writes nothing, unless:

  - the token has code, `deployer()` is the plan's Safe, and `locked()` is false;
  - the plan's description is byte-identical to the one on chain, or the entry says `"replacesDescription": true`
    with the current value quoted in `"replaces"` -- so wiping 304 bytes of text is something a reviewer typed,
    never something a missing key did;
  - every string is inside the token's OWN caps, read from the token (`MAX_LINK_BYTES`, `MAX_DESCRIPTION_BYTES`),
    measured in BYTES, not characters;
  - every non-empty link is `https://` (the contract takes any string; a `http:`, `javascript:` or `data:` link in a
    field a wallet renders is not something this tool will encode);
  - the logo is a content-addressed icon on the site's own R2 bucket -- `https://<host>/media/icons/<sha256>.png`,
    the shape `server/icons.ts` writes -- and a GET of it returns `image/png` whose sha256 IS the hash in the path.
    `--icon-pending` downgrades an unpublished icon to a warning for a rehearsal; it never writes a batch.

Then every transaction is simulated from the Safe, and the encoded calldata is decoded back and compared field by
field against the plan before anything is written.

`setMetadata` takes a struct, so the transactions are emitted as custom data (`contractMethod: null`): the Safe UI
renders a struct's fields inconsistently across Transaction Builder versions, and a field a signer cannot read is
worse than hex they verify with `--decode`. The calldata is what cast encoded; `--decode` prints the entry in full.
"""
import argparse, datetime, hashlib, json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emergency"))
import build  # noqa: E402

SET_METADATA = "setMetadata(string,string,(string,string,string,string,string),string)"
SET_EDITOR = "setEditor(address)"
SOCIALS = ("twitter", "telegram", "discord", "website", "farcaster")
ICON_URL = re.compile(r"^https://([a-z0-9][a-z0-9.-]*[a-z0-9])/media/icons/([0-9a-f]{64})\.png$")
ICON_MAX_BYTES = 512 * 1024          # server/icons.ts MAX_ICON_BYTES
FETCH_TIMEOUT = 20


# ---------------------------------------------------------------------------------------------------- reads
def _call(rpc, to, sig):
    return bytes.fromhex(rpc._req("eth_call", [{"to": to, "data": build.selector(sig)}, "latest"])[2:])


def _strings(raw, count):
    """Decode `count` dynamic strings returned by an eth_call, as bytes -> str, without going through cast."""
    out = []
    for i in range(count):
        off = int.from_bytes(raw[i * 32:i * 32 + 32], "big")
        n = int.from_bytes(raw[off:off + 32], "big")
        out.append(raw[off + 32:off + 32 + n].decode("utf-8"))
    return out


def read_entry(rpc, token):
    """The token's metadata half, exactly as it stands. Strings come back as bytes so a comparison is a byte comparison."""
    word = lambda sig: int.from_bytes(_call(rpc, token, sig), "big")
    return {
        "deployer": build.checksum_addr("0x%040x" % word("deployer()")),
        "editor": build.checksum_addr("0x%040x" % word("editor()")),
        "locked": bool(word("locked()")),
        "updatedAt": word("updatedAt()"),
        "maxLink": word("MAX_LINK_BYTES()"),
        "maxDescription": word("MAX_DESCRIPTION_BYTES()"),
        "logo": _strings(_call(rpc, token, "logo()"), 1)[0],
        "description": _strings(_call(rpc, token, "description()"), 1)[0],
        "extraURI": _strings(_call(rpc, token, "extraURI()"), 1)[0],
        "socials": dict(zip(SOCIALS, _strings(_call(rpc, token, "socials()"), 5))),
    }


def fetch_icon(url, sha):
    """The only non-RPC request this tool makes. Proves the URL serves the exact bytes its path claims."""
    req = urllib.request.Request(url, headers={"user-agent": "hedgefund-metadata-batch"}, method="GET")
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
        kind = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
        body = r.read(ICON_MAX_BYTES + 1)
    if kind != "image/png": raise build.Refuse(f"logo {url} is served as {kind!r}, not image/png")
    if len(body) > ICON_MAX_BYTES: raise build.Refuse(f"logo {url} is larger than {ICON_MAX_BYTES} bytes")
    got = hashlib.sha256(body).hexdigest()
    if got != sha: raise build.Refuse(f"logo {url} serves sha256 {got}, but its own path says {sha}")
    return len(body)


# ---------------------------------------------------------------------------------------------------- encode
def _quoted(s):
    """One tuple element for `cast calldata`. Its parser splits on commas and has no escape, so an unquoted empty
    element is a parse error and a quote or backslash inside one is unencodable. Refuse rather than guess."""
    if '"' in s or "\\" in s: raise build.Refuse(f"a metadata string contains a quote or backslash, which cannot be encoded through cast: {s!r}")
    return '"' + s + '"'


def encode_metadata(token, entry, note):
    socials = "(" + ",".join(_quoted(entry["socials"][k]) for k in SOCIALS) + ")"
    data = build.cast("calldata", SET_METADATA, entry["logo"], entry["description"], socials, entry["extraURI"]).lower()
    if not data.startswith(build.selector(SET_METADATA)): raise build.Refuse("cast returned a foreign selector for setMetadata")
    back = json.loads(build.cast("calldata-decode", "--json", SET_METADATA, data))
    if back != [entry["logo"], entry["description"], [entry["socials"][k] for k in SOCIALS], entry["extraURI"]]:
        raise build.Refuse("setMetadata calldata does not decode back to the plan's own strings; not writing a batch on encoding this tool cannot verify")
    return {"to": token, "name": "setMetadata", "sig": SET_METADATA, "entry": entry, "data": data, "note": note}


def encode_editor(token, editor, note):
    data = build.cast("calldata", SET_EDITOR, editor).lower()
    if not data.startswith(build.selector(SET_EDITOR)): raise build.Refuse("cast returned a foreign selector for setEditor")
    return {"to": token, "name": "setEditor", "sig": SET_EDITOR, "entry": None, "data": data, "note": note}


def bundle(calls, chain_id, safe, name, description):
    """The Transaction Builder file, custom-data form. Same checksum the UI recomputes on import."""
    b = {"version": "1.0", "chainId": str(chain_id), "createdAt": int(time.time() * 1000),
         "meta": {"name": name, "description": description, "txBuilderVersion": "1.16.5",
                  "createdFromSafeAddress": safe, "createdFromOwnerAddress": ""},
         "transactions": [{"to": c["to"], "value": "0", "data": c["data"], "contractMethod": None, "contractInputsValues": None} for c in calls]}
    b["meta"]["checksum"] = build.safe_checksum(b)
    return b


# ---------------------------------------------------------------------------------------------------- describe
def describe(calls, names):
    lines = []
    for i, c in enumerate(calls, 1):
        lines.append(f"  [{i}/{len(calls)}] to {c['to']}  ({names.get(c['to'].lower(), 'UNKNOWN TARGET')})")
        lines.append(f"        {c['sig']}")
        if c["entry"]:
            e = c["entry"]
            lines.append(f"        logo         {e['logo'] or '(empty)'}")
            lines.append(f"        description  {len(e['description'].encode()):>4} bytes  {e['description'][:72]}{'...' if len(e['description']) > 72 else ''}")
            for k in SOCIALS: lines.append(f"        {k:<12} {e['socials'][k] or '(empty)'}")
            lines.append(f"        extraURI     {e['extraURI'] or '(empty)'}")
        if c["note"]: lines.append(f"        -> {c['note']}")
        lines.append(f"        data {c['data']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------- checks
def check_token(rpc, plan, sym, s, icon_pending):
    token = build.checksum_addr(s["token"])
    if rpc._req("eth_getCode", [token, "latest"]) in ("0x", ""): raise build.Refuse(f"{sym}: no contract at {token}")
    on = read_entry(rpc, token)
    if on["deployer"].lower() != plan["safe"].lower():
        raise build.Refuse(f"{sym}: deployer is {on['deployer']}, not the plan's Safe {plan['safe']} -- this Safe cannot write this token's metadata")
    if on["locked"]: raise build.Refuse(f"{sym}: metadata is locked; there is no way back and nothing to build")

    want = {"logo": s["logo"], "description": s["description"], "extraURI": s.get("extraURI", ""),
            "socials": {k: s.get("socials", {}).get(k, "") for k in SOCIALS}}
    if want["description"] != on["description"]:
        if not s.get("replacesDescription"):
            raise build.Refuse(f"{sym}: the plan's description is not the one on chain, and the entry does not say "
                               f'"replacesDescription": true. setMetadata REPLACES the whole entry: on chain is '
                               f"{len(on['description'].encode())} bytes, the plan is {len(want['description'].encode())}.")
        if s.get("replaces") != on["description"]:
            raise build.Refuse(f"{sym}: \"replacesDescription\" is set but \"replaces\" is not the description now on chain, "
                               f"so the reviewer approved replacing something else. Quote the current text exactly.")

    for field, value in [("logo", want["logo"]), ("extraURI", want["extraURI"])] + [(k, want["socials"][k]) for k in SOCIALS]:
        n = len(value.encode())
        if n > on["maxLink"]: raise build.Refuse(f"{sym}: {field} is {n} bytes, over the token's MAX_LINK_BYTES {on['maxLink']}")
        if value and not value.startswith("https://"): raise build.Refuse(f"{sym}: {field} is not an https:// link: {value!r}")
    n = len(want["description"].encode())
    if n > on["maxDescription"]: raise build.Refuse(f"{sym}: description is {n} bytes, over the token's MAX_DESCRIPTION_BYTES {on['maxDescription']}")

    icon = ""
    if want["logo"]:
        m = ICON_URL.match(want["logo"])
        if not m: raise build.Refuse(f"{sym}: logo is not a content-addressed icon (https://<host>/media/icons/<sha256>.png): {want['logo']}")
        host, sha = m.group(1), m.group(2)
        if host != plan["iconHost"]: raise build.Refuse(f"{sym}: logo host {host} is not the plan's iconHost {plan['iconHost']}")
        try:
            size = fetch_icon(want["logo"], sha)
            icon = f"{size:,} bytes, sha256 verified"
        except build.Refuse:
            raise
        except Exception as e:
            if not icon_pending: raise build.Refuse(f"{sym}: logo {want['logo']} could not be fetched ({e}). Upload the icon first -- a batch is not signed against a dead URL. --icon-pending rehearses without writing.")
            icon = f"NOT PUBLISHED YET ({e})"

    unchanged = (want["logo"] == on["logo"] and want["description"] == on["description"]
                 and want["extraURI"] == on["extraURI"] and want["socials"] == on["socials"])
    return token, on, want, icon, unchanged


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", nargs="?"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--decode", metavar="FILE"); ap.add_argument("--icon-pending", action="store_true")
    ap.add_argument("--rpc", default="https://rpc.mainnet.chain.robinhood.com")
    a = ap.parse_args(argv)
    if a.decode: return decode_file(a.decode)
    if not a.plan: raise build.Refuse("give a plan file, or --decode a built batch")

    plan = json.loads(Path(a.plan).read_text())
    rpc = build.Rpc(a.rpc)
    if int(rpc._req("eth_chainId", []), 16) != plan["chainId"]: raise build.Refuse("wrong chain")
    plan["safe"] = build.checksum_addr(plan["safe"])

    lines, calls, names, pending = [], [], {}, False
    for sym, s in plan["tokens"].items():
        token, on, want, icon, unchanged = check_token(rpc, plan, sym, s, a.icon_pending)
        names[token.lower()] = f"HedgeFunToken {sym}"
        pending = pending or icon.startswith("NOT PUBLISHED")
        lines.append(f"  {sym:10} {token}  entry written {'never' if not on['updatedAt'] else datetime.datetime.fromtimestamp(on['updatedAt'], datetime.timezone.utc):%Y-%m-%d %H:%M UTC}"
                     f"  editor {on['editor']}  logo {icon or '(none)'}")
        if unchanged:
            lines.append(f"  {'':10} entry already matches the plan; no setMetadata")
        else:
            calls.append(encode_metadata(token, want, f"{sym}: replace the whole entry"))
        # Omitted means "leave the current editor alone". Explicit null is intentionally different: it revokes
        # the editor by sending setEditor(address(0)), matching the declarative plan format.
        if "editor" in s:
            editor = build.ZERO if s["editor"] is None else build.checksum_addr(s["editor"])
            if editor.lower() == on["editor"].lower(): lines.append(f"  {'':10} editor already {editor}; no setEditor")
            elif editor == build.ZERO:
                calls.append(encode_editor(token, editor, f"{sym}: revoke the current metadata editor."))
            else:
                calls.append(encode_editor(token, editor, f"{sym}: let {editor} maintain the links without the Safe. It can neither appoint nor lock."))

    if not calls:
        print("tokens\n" + "\n".join(lines) + "\n\nNOTHING TO DO: every token already reads as the plan. No file written.")
        return 0
    print("tokens\n" + "\n".join(lines) + "\n\n" + describe(calls, names) + "\n\nsimulation\n"
          + build.simulate(calls, {"safe": plan["safe"]}, rpc))
    if a.check or pending:
        if pending: print("\nNOT WRITTEN: an icon is not published yet (--icon-pending). Upload it, then run this again.")
        return 0
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    b = bundle(calls, plan["chainId"], plan["safe"], f"METADATA {Path(a.plan).stem} {stamp}",
               f"Token metadata for {', '.join(plan['tokens'])}. Built from {Path(a.plan).name} by tools/metadata_batch.py.")
    out = ROOT / "deploy" / "safe" / f"{stamp}-{Path(a.plan).stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(b, indent=2) + "\n")
    print(f"\ntransactions   {len(calls)}\nmeta.checksum  {b['meta']['checksum']}\nbatch digest   {build.batch_digest(b['transactions'])}\nwrote          {out.relative_to(ROOT)}")
    print(f"\nNEXT  every signer runs:  python3 tools/metadata_batch.py --decode {out.relative_to(ROOT)}")
    print("      and reads the batch digest back to whoever built it. NOTHING has been sent; this tool cannot send.")
    return 0


def decode_file(path):
    """What a signer runs on the file they were sent. Decodes from `data`, never from anything the file claims."""
    b = json.loads(Path(path).read_text())
    ok = True
    def flag(msg):
        nonlocal ok; ok = False; print(f"  !! {msg}")
    print(f"file       {path}\nname       {b['meta'].get('name')}\nchainId    {b.get('chainId')}\nsafe       {b['meta'].get('createdFromSafeAddress')}")
    want = build.safe_checksum(b)
    if b["meta"].get("checksum") != want: flag(f"meta.checksum does not match the file's contents ({want}): EDITED after it was built")
    known = {build.selector(SET_METADATA): SET_METADATA, build.selector(SET_EDITOR): SET_EDITOR}
    for i, t in enumerate(b["transactions"], 1):
        data = (t.get("data") or "").lower()
        print(f"  [{i}/{len(b['transactions'])}] to {t['to']}")
        if str(t.get("value", "0")) != "0": flag(f"value is {t.get('value')}: a metadata batch never sends value")
        sig = known.get(data[:10])
        if not sig:
            flag(f"selector {data[:10]} is not setMetadata or setEditor. DO NOT SIGN it in a metadata batch."); continue
        vals = json.loads(build.cast("calldata-decode", "--json", sig, data))
        if build.cast("calldata", sig, *([vals[0], vals[1], "(" + ",".join(_quoted(x) for x in vals[2]) + ")", vals[3]] if sig == SET_METADATA else vals)).lower() != data:
            flag("calldata does not round-trip through its own decoding (trailing or malformed bytes)")
        if sig == SET_EDITOR:
            print(f"        setEditor({vals[0]})   <- may rewrite this token's metadata from now on; cannot appoint or lock")
            continue
        logo, desc, soc, extra = vals
        print(f"        setMetadata -- REPLACES the whole entry")
        print(f"        logo         {logo or '(empty)'}")
        print(f"        description  {len(desc.encode()):>4} bytes  {desc}")
        for k, v in zip(SOCIALS, soc): print(f"        {k:<12} {v or '(empty)'}")
        print(f"        extraURI     {extra or '(empty)'}")
        for field, v in [("logo", logo), ("extraURI", extra)] + list(zip(SOCIALS, soc)):
            if v and not v.startswith("https://"): flag(f"{field} is not an https:// link: {v!r}")
        if logo and not ICON_URL.match(logo): flag(f"logo is not a content-addressed /media/icons/<sha256>.png URL: {logo}")
    print(f"\nbatch digest   {build.batch_digest(b['transactions'])}")
    print("\nRead the digest back to whoever built this file before you sign." if ok else "\nDO NOT SIGN: see the !! lines above.")
    return 0 if ok else 1


if __name__ == "__main__":
    try: sys.exit(main())
    except build.Refuse as e: sys.exit(f"REFUSED: {e}")
