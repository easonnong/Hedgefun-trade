#!/usr/bin/env python3
"""Does the trade tax predict volume and graduation on pons.family (Robinhood Chain)?

Pons V2 is a bonding-curve launchpad on our chain. Every launch pays a 1% base
trade fee (`curveFeeBps = 100` in launch config 0) and the creator may add
`creatorTaxBps` in [0, 1000] on top, fixed for the life of the curve. That is
a natural experiment for Hedgefun's own 1-15% creator tax: same chain, same
quote assets, only the tax varies.

Read-only. Nothing here signs or broadcasts. Two RPCs, both public and keyless:

  * https://rpc.mainnet.chain.robinhood.com  -- eth_getLogs, <= 15,000 blocks per
    window, ~1 request/s (it answers 429 above that), and a 10,000-log result
    cap ("logs matched by query exceeds limit of 10000") that the scanner
    handles by halving the window.
  * https://robinhood-rpc.publicnode.com    -- eth_call at `latest` (no archive
    access without a token) and block headers.

Phases (each is resumable and cached under data/pons/):

  scan     pull every TokenLaunched / PoolGraduated / LaunchSwept (factory) and
           CurveBuy / CurveSell / CurveCompleted (any address; attributed to a
           launch later) log into data/pons/logs/<from>-<to>.jsonl.gz
  enrich   creatorTaxBps + feeBps per curve via Multicall3, block timestamps
           (every 5,000 blocks, exact for launch/graduation blocks of graduated
           launches), quote-token symbol/decimals, Chainlink USD prices
  analyze  per-launch rows -> data/pons/launches.csv (git-ignored, ~75 MB) and
           data/pons/launches_extract.csv.gz (committed), bucket tables ->
           data/pons/summary.json and stdout (markdown)

  python3 tools/pons_elasticity.py all            # scan + enrich + analyze
  python3 tools/pons_elasticity.py scan --to-block N

Facts this encodes, each verified against the chain before being relied on:
  * Blocks are ~0.10 s apart, so 15,000 blocks is ~25 minutes and the factory's
    life (first activity block ~27.81M, 2026-08-04) is ~3,100 windows.
  * `CurveBuy.quoteIn` is GROSS (fee and tax come out of it); `CurveSell.quoteOut`
    is NET (fee and tax already deducted). Gross sell = quoteOut + fee + tax.
  * `TokenLaunched` carries the pair token (address(0) = native ETH) but not
    the creator tax; that is `creatorTaxBps()` on the curve. Trades also carry
    `tax`, so the eth_call value is cross-checked against tax/quoteIn.
  * The curve auto-graduates inside the crossing buy (`_tryAutoGraduate`), so
    CurveCompleted, LaunchSwept and PoolGraduated normally share a block.
  * `feeBps()` reads 100 on every curve, but the DEPLOYED curve also charges a
    decaying anti-snipe fee in the first seconds after launch (factory and
    curve both answer snipeTaxStartBps() = 9900, snipeTaxSeconds() = 3 on
    2026-09-28). Observed effective fees step 9900 -> 718 -> 119 -> 100 bps.
    It is reported in CurveBuy/CurveSell `fee`, never in `tax`. The vendored
    PonsV2BondingCurve.sol has no snipe code at all, although the vendored
    factory calls curve.exemptFromSnipeTax(); the deployed bytecode is newer.
    So a trade-implied fee is only a lower bound check, never a substitute
    for the feeBps() read.
  * Cache files are named <first block>-<last block>; the log iterator refuses
    holes, overlapping files and any repeated (block, logIndex).
"""
import argparse
import calendar
import csv
import glob
import gzip
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "pons")
LOGDIR = os.path.join(DATA, "logs")

LOG_RPC = "https://rpc.mainnet.chain.robinhood.com"
READ_RPC = "https://robinhood-rpc.publicnode.com"

FACTORY = "0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e"
MULTICALL3 = "0xca11bde05977b3631167028862be2a173976ca11"
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
NATIVE = "0x" + "00" * 20

# first factory activity is between blocks 27,802,614 and 27,810,426 (bisected
# on eth_getLogs; the chain keeps no archive state so eth_getCode cannot be
# used). Start a little earlier so nothing is missed.
DEFAULT_FROM_BLOCK = 27_790_000
WINDOW = 15_000
CHUNK = 150_000          # blocks per cache file (10 windows)
MIN_WINDOW = 250
LOG_PAUSE = 1.05         # seconds between eth_getLogs calls
TS_STEP = 5_000          # block-timestamp sample spacing for interpolation

# keccak256 of the event signatures, computed with `cast keccak`
T_LAUNCHED = "0x8d4aad4953d0ca700d468f3753aa14432d1b35b43ec6409f051fb6aa43a89607"
T_POOL_GRAD = "0x0a44ef75df69c534f43cd6c1aa3ef8983065fe5fe79ef9e79f6494e6f258c259"
T_SWEPT = "0xcdb72f157fd3666758a6ce201387ffb52038c7562e4fff352828da1096c4b6b4"
T_BUY = "0xec36bf571f136799e8dc0b0b8bea4b04d8bd3d43de838aab0d5fc21d4cbfc455"
T_SELL = "0x8113d738abdcb6b38357e9d53a54a7157861a09031b453651f0fe7fe151f59df"
T_COMPLETED = "0xf8d37a90738ae063b8b8058b66f5880cf3cf7ab0c5d4fa78219696591dfbfb67"
TOPICS = [T_LAUNCHED, T_POOL_GRAD, T_SWEPT, T_BUY, T_SELL, T_COMPLETED]

SEL = {
    "creatorTaxBps": "0xc1bb8901", "feeBps": "0x24a9d853", "pairToken": "0x3de35b79",
    "graduated": "0xe7c2b772", "symbol": "0x95d89b41", "decimals": "0x313ce567",
    "latestRoundData": "0xfeaf968c", "aggregate3": "0x82ad56cb",
}

TAX_BUCKETS = [("1% (base only)", 100, 100), ("1-2%", 101, 200), ("2-5%", 201, 500), ("5-11%", 501, 1100)]


# ---------------------------------------------------------------------------
# JSON-RPC
# ---------------------------------------------------------------------------

class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _post(url, payload, timeout=120):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def rpc(url, method, params, tries=6):
    """Single call. Retries on 429/5xx/timeouts with backoff; raises RpcError on
    a JSON-RPC error so callers can react to the message (window too big)."""
    delay = 2.0
    for i in range(tries):
        try:
            r = _post(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and i < tries - 1:
                time.sleep(delay)
                delay *= 1.7
                continue
            body = e.read()[:200].decode(errors="replace")
            raise RpcError(e.code, body)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if i < tries - 1:
                time.sleep(delay)
                delay *= 1.7
                continue
            raise
        if "error" in r:
            err = r["error"]
            raise RpcError(err.get("code"), err.get("message", str(err)))
        return r["result"]
    raise RuntimeError("unreachable")


def rpc_batch(url, calls, size=50, pause=0.2, tries=6):
    """calls: list of (id, method, params). Returns {id: result_or_None}."""
    out = {}
    for i in range(0, len(calls), size):
        chunk = [{"jsonrpc": "2.0", "id": cid, "method": m, "params": p} for cid, m, p in calls[i:i + size]]
        delay = 2.0
        for t in range(tries):
            try:
                res = _post(url, chunk)
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
                if t == tries - 1:
                    raise
                time.sleep(delay)
                delay *= 1.7
        for r in res:
            out[r["id"]] = r.get("result")
        time.sleep(pause)
    return out


def head_block():
    return int(rpc(READ_RPC, "eth_blockNumber", []), 16)


def block_ts(n):
    return int(rpc(READ_RPC, "eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def block_at(ts):
    """First block whose timestamp is >= ts (bisection on headers, ~26 calls)."""
    lo, hi = 1, head_block()
    while lo < hi:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def parse_time(s):
    # timegm, not mktime - time.timezone: the latter ignores DST, and put the
    # first scan's "2026-09-17T00:00:00Z" at 2026-09-16T23:00:00Z (block 64,884,917).
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


# ---------------------------------------------------------------------------
# ABI helpers (no web3: the repo's tools all speak raw JSON-RPC)
# ---------------------------------------------------------------------------

def addr_of(word):
    return "0x" + word[-40:].lower()


def words(data):
    h = data[2:] if data.startswith("0x") else data
    return [int(h[i:i + 64], 16) for i in range(0, len(h) - len(h) % 64, 64)]


def decode_string(hexdata):
    try:
        b = bytes.fromhex(hexdata[2:])
        if len(b) >= 64:
            off = int.from_bytes(b[:32], "big")
            ln = int.from_bytes(b[off:off + 32], "big")
            return b[off + 32:off + 32 + ln].decode("utf-8", errors="replace")
        return b.rstrip(b"\0").decode("utf-8", errors="replace")  # bytes32 symbol
    except Exception:
        return "?"


def encode_aggregate3(targets_and_data):
    """Multicall3.aggregate3((address target, bool allowFailure, bytes callData)[])."""
    n = len(targets_and_data)
    body = []
    tuples = []
    for target, data in targets_and_data:
        d = data[2:] if data.startswith("0x") else data
        dlen = len(d) // 2
        padded = d + "0" * ((64 - len(d) % 64) % 64)
        t = (target[2:].lower().rjust(64, "0") + "1".rjust(64, "0") + hex(0x60)[2:].rjust(64, "0")
             + hex(dlen)[2:].rjust(64, "0") + padded)
        tuples.append(t)
    offsets = []
    pos = 32 * n
    for t in tuples:
        offsets.append(pos)
        pos += len(t) // 2
    body.append(hex(n)[2:].rjust(64, "0"))
    body += [hex(o)[2:].rjust(64, "0") for o in offsets]
    body += tuples
    return SEL["aggregate3"] + hex(0x20)[2:].rjust(64, "0") + "".join(body)


def decode_aggregate3(hexdata):
    """Returns list of (success, returndata_hex)."""
    b = bytes.fromhex(hexdata[2:])
    arr = int.from_bytes(b[0:32], "big")
    n = int.from_bytes(b[arr:arr + 32], "big")
    base = arr + 32
    out = []
    for i in range(n):
        toff = int.from_bytes(b[base + 32 * i:base + 32 * i + 32], "big")
        t = base + toff
        success = int.from_bytes(b[t:t + 32], "big") == 1
        boff = int.from_bytes(b[t + 32:t + 64], "big")
        blen = int.from_bytes(b[t + boff:t + boff + 32], "big")
        out.append((success, "0x" + b[t + boff + 32:t + boff + 32 + blen].hex()))
    return out


def multicall(calls, batch=150):
    """calls: list of (target, calldata). Returns list of (success, hex) in order."""
    results = []
    for i in range(0, len(calls), batch):
        part = calls[i:i + batch]
        data = encode_aggregate3(part)
        for attempt in range(5):
            try:
                res = rpc(READ_RPC, "eth_call", [{"to": MULTICALL3, "data": data}, "latest"])
                results += decode_aggregate3(res)
                break
            except RpcError as e:
                if attempt == 4:
                    raise
                time.sleep(3 * (attempt + 1))
        time.sleep(0.15)
    return results


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

def chunk_path(a, b, partial=False):
    return os.path.join(LOGDIR, f"{a:09d}-{b:09d}{'.partial' if partial else ''}.jsonl.gz")


class Windower:
    """Adaptive eth_getLogs window. The official RPC has three ceilings that all
    surface as JSON-RPC errors rather than HTTP ones: a 10,000-log result cap,
    a ~2-5 s server-side query timeout ("log query timed out", common on
    busy stretches and on old blocks), and a ~1 request/s rate limit (HTTP
    429, handled with backoff in rpc()). Halve on the first two, grow back
    after a run of cheap successes, never exceed WINDOW."""

    def __init__(self, stats):
        self.win = WINDOW
        self.good = 0
        self.stats = stats

    def fetch(self, a, b):
        """Logs for [a, b] inclusive; b is advisory, returns (logs, last_block)."""
        while True:
            end = min(b, a + self.win - 1)
            t0 = time.time()
            try:
                res = rpc(LOG_RPC, "eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(end), "topics": [TOPICS]}])
            except RpcError as e:
                msg = (e.message or "").lower()
                self.stats["calls"] += 1
                if "exceeds limit" in msg or "timed out" in msg or "too many" in msg or "range" in msg or "limit" in msg:
                    if self.win <= MIN_WINDOW:
                        raise
                    self.win = max(MIN_WINDOW, self.win // 2)
                    self.good = 0
                    self.stats["splits"] += 1
                    time.sleep(LOG_PAUSE)
                    continue
                raise
            self.stats["calls"] += 1
            dt = time.time() - t0
            time.sleep(max(0.0, LOG_PAUSE - dt))
            if len(res) < 3500 and dt < 1.0:
                self.good += 1
                if self.good >= 3 and self.win < WINDOW:
                    self.win = min(WINDOW, self.win * 2)
                    self.good = 0
            else:
                self.good = 0
            return res, end


def slim(log):
    return {"b": int(log["blockNumber"], 16), "i": int(log["logIndex"], 16),
            "a": log["address"].lower(), "t": log["topics"], "d": log["data"], "tx": log["transactionHash"]}


def scan(from_block, to_block):
    os.makedirs(LOGDIR, exist_ok=True)
    for p in glob.glob(os.path.join(LOGDIR, "*.partial.jsonl.gz")):
        os.remove(p)
    start = (from_block // CHUNK) * CHUNK
    stats = {"calls": 0, "splits": 0, "logs": 0, "t0": time.time()}
    chunks = list(range(start, to_block + 1, CHUNK))
    windower = Windower(stats)
    for ci, a in enumerate(chunks):
        b = min(a + CHUNK - 1, to_block)
        partial = b < a + CHUNK - 1
        # the first file is named for the block the scan really starts at, so
        # scanned_range() reports the true window rather than the chunk grid
        w = max(a, from_block)
        path = chunk_path(w, b, partial)
        if os.path.exists(path):
            continue
        rows = []
        while w <= b:
            logs, wb = windower.fetch(w, b)
            rows += [slim(l) for l in logs]
            w = wb + 1
        rows.sort(key=lambda r: (r["b"], r["i"]))
        tmp = path + ".tmp"
        with gzip.open(tmp, "wt") as f:
            for r in rows:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        os.replace(tmp, path)
        stats["logs"] += len(rows)
        el = time.time() - stats["t0"]
        print(f"[scan] chunk {ci + 1}/{len(chunks)} {a}-{b}: {len(rows)} logs "
              f"(calls {stats['calls']}, splits {stats['splits']}, window {windower.win}, {el / 60:.1f} min)", flush=True)
    return stats


def iter_logs(needles=None):
    """Every cached log, in (block, logIndex) order. Refuses a cache in which
    that order is not strictly increasing: a repeated key is a log counted
    twice (e.g. two overlapping .partial files left by concurrent scans).
    `needles`: only parse lines containing one of these substrings (a cheap
    topic pre-filter; the order check then covers only the matching lines)."""
    scanned_range()   # refuses holes and overlapping files before anything is counted
    files = sorted(glob.glob(os.path.join(LOGDIR, "*.jsonl.gz")))
    prev = (-1, -1)
    for p in files:
        with gzip.open(p, "rt") as f:
            for line in f:
                if needles is not None and not any(n in line for n in needles):
                    continue
                r = json.loads(line)
                key = (r["b"], r["i"])
                if key <= prev:
                    raise SystemExit(f"log cache repeats or reorders log {key} (after {prev}) in {p}")
                prev = key
                yield r


def scanned_range():
    """(first, last) block covered by the cache; refuses a cache with a hole."""
    files = sorted(glob.glob(os.path.join(LOGDIR, "*.jsonl.gz")))
    if not files:
        return None, None
    spans = [(int(os.path.basename(f).split("-")[0]), int(os.path.basename(f).split("-")[1].split(".")[0]))
             for f in files]
    for (a0, b0), (a1, b1) in zip(spans, spans[1:]):
        if a1 <= b0:
            raise SystemExit(f"log cache files overlap: {a0}-{b0} and {a1}-{b1}; delete the stale one "
                             f"(scan deletes every .partial file before it runs)")
        if a1 != b0 + 1:
            if os.environ.get("PONS_ALLOW_HOLES"):
                print(f"[warn] log cache has a hole between {b0} and {a1}", file=sys.stderr)
                continue
            raise SystemExit(f"log cache has a hole between {b0} and {a1}; rerun scan")
    return spans[0][0], spans[-1][1]


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------

def load_json(name, default):
    p = os.path.join(DATA, name)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return default


def save_json(name, obj):
    p = os.path.join(DATA, name)
    with open(p + ".tmp", "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(p + ".tmp", p)


def first_pass():
    """Launch table + the block set needed for timestamps. Cheap, no RPC."""
    launches = {}
    graduated_blocks = {}
    for l in iter_logs(needles=(T_LAUNCHED, T_COMPLETED)):
        t0 = l["t"][0]
        if t0 == T_LAUNCHED and l["a"] == FACTORY:
            token = addr_of(l["t"][1]); curve = addr_of(l["t"][2]); deployer = addr_of(l["t"][3])
            w = words(l["d"])
            launches[curve] = {"token": token, "curve": curve, "deployer": deployer,
                               "pair": "0x" + hex(w[0])[2:].rjust(40, "0") if w[0] else NATIVE,
                               "config": w[1], "threshold": w[2], "block": l["b"], "tx": l["tx"]}
        elif t0 == T_COMPLETED:
            graduated_blocks[l["a"]] = l["b"]
    return launches, graduated_blocks


def enrich():
    launches, grad_blocks = first_pass()
    curves = sorted(launches)
    print(f"[enrich] {len(curves)} launches, {sum(1 for c in curves if c in grad_blocks)} completed curves")

    # 1. creatorTaxBps / feeBps per curve, Multicall3, cached
    meta = load_json("curve_meta.json", {})
    todo = [c for c in curves if c not in meta]
    print(f"[enrich] curve fee params: {len(todo)} to fetch")
    for i in range(0, len(todo), 600):
        part = todo[i:i + 600]
        calls = []
        for c in part:
            calls += [(c, SEL["creatorTaxBps"]), (c, SEL["feeBps"])]
        res = multicall(calls)
        for j, c in enumerate(part):
            ok1, r1 = res[2 * j]
            ok2, r2 = res[2 * j + 1]
            meta[c] = {"creatorTaxBps": int(r1, 16) if ok1 and len(r1) >= 66 else None,
                       "feeBps": int(r2, 16) if ok2 and len(r2) >= 66 else None}
        save_json("curve_meta.json", meta)
        print(f"[enrich]   {min(i + 600, len(todo))}/{len(todo)}", flush=True)

    # 2. quote tokens: symbol + decimals
    quotes = load_json("quote_tokens.json", {})
    pairs = sorted({l["pair"] for l in launches.values()})
    for p in pairs:
        if p in quotes:
            continue
        if p == NATIVE:
            quotes[p] = {"symbol": "ETH", "decimals": 18}
            continue
        res = multicall([(p, SEL["symbol"]), (p, SEL["decimals"])])
        quotes[p] = {"symbol": decode_string(res[0][1]) if res[0][0] else "?",
                     "decimals": int(res[1][1], 16) if res[1][0] and len(res[1][1]) >= 66 else None}
    save_json("quote_tokens.json", quotes)
    print(f"[enrich] quote tokens: {[(q['symbol'], p[:8]) for p, q in quotes.items()]}")

    # 3. Chainlink USD prices at latest, if the repo's feed registry knows the symbol
    feeds = {}
    fp = os.path.join(HERE, "data", "chainlink_feeds.json")
    if os.path.exists(fp):
        with open(fp) as f:
            feeds = json.load(f)
    prices = {}
    calls = []
    keys = []
    for p, q in quotes.items():
        sym = q["symbol"]
        if p == USDG:
            prices[p] = {"usd": 1.0, "source": "USDG assumed 1.00"}
            continue
        cands = [f"{sym} / USD", f"Robinhood {sym} / USD", f"RH{sym} / USD", f"{sym.upper()} / USD"]
        if sym == "ETH":
            cands = ["ETH / USD"]
        feed = next((feeds[k] for k in cands if k in feeds), None)
        if feed:
            calls.append((feed["addr"], SEL["latestRoundData"]))
            keys.append((p, feed))
    if calls:
        res = multicall(calls)
        for (p, feed), (ok, r) in zip(keys, res):
            if ok and len(r) >= 2 + 64 * 5:
                w = words(r)
                prices[p] = {"usd": w[1] / 10 ** feed.get("decimals", 8), "updatedAt": w[3],
                             "source": feed["addr"]}
    # fallback: the deepest <stock>/USDG V3 pool's slot0 at latest, for stocks with no push feed here
    census_path = os.path.join(HERE, "data", "v3_pool_census.json")
    tokens_path = os.path.join(HERE, "data", "rh_stock_tokens.json")
    if os.path.exists(census_path) and os.path.exists(tokens_path):
        with open(census_path) as f:
            census = json.load(f)
        with open(tokens_path) as f:
            sym_of = {a.lower(): sym for sym, a in json.load(f)["stock_tokens"].items()}
        best = {}
        for pool in census.get("pools", []):
            if pool.get("skip") or not pool.get("active_liquidity"):
                continue
            sym = pool["symbol"]
            if sym not in best or pool["tvl_usdg"] > best[sym]["tvl_usdg"]:
                best[sym] = pool
        calls, keys = [], []
        for p in quotes:
            if p in prices or p == NATIVE:
                continue
            sym = sym_of.get(p) or quotes[p]["symbol"]
            pool = best.get(sym)
            if pool and (quotes[p]["decimals"] or 18) == 18:
                calls.append((pool["pool"], "0x3850c7bd"))   # slot0()
                keys.append((p, pool))
        if calls:
            res = multicall(calls)
            for (p, pool), (ok, r) in zip(keys, res):
                if ok and len(r) >= 66:
                    sqrt_p = words(r)[0]
                    ratio = (sqrt_p / 2 ** 96) ** 2          # token1 per token0, raw units
                    usd = (1e12 / ratio) if pool["usdg_is_token0"] else (ratio * 1e12)
                    prices[p] = {"usd": usd, "source": f"V3 pool slot0 {pool['pool']} (USDG at 1.00)"}
    for p in quotes:
        prices.setdefault(p, {"usd": None, "source": "no Chainlink feed in data/chainlink_feeds.json and no V3/USDG pool"})
    save_json("quote_prices.json", prices)
    print(f"[enrich] prices: {[(quotes[p]['symbol'], v['usd']) for p, v in prices.items()]}")

    # 4. block timestamps: a grid every TS_STEP blocks (interpolated) plus exact
    # values for launch and completion blocks of every completed curve
    a, b = scanned_range()
    bt = {int(k): v for k, v in load_json("block_times.json", {}).items()}
    want = set(range((a // TS_STEP) * TS_STEP, b + TS_STEP, TS_STEP))
    want.add(a)
    want.add(b)
    for c, gb in grad_blocks.items():
        if c in launches:
            want.add(gb)
            want.add(launches[c]["block"])
    todo = sorted(x for x in want if x not in bt)
    print(f"[enrich] block timestamps: {len(todo)} to fetch")
    for i in range(0, len(todo), 2000):
        part = todo[i:i + 2000]
        res = rpc_batch(READ_RPC, [(n, "eth_getBlockByNumber", [hex(n), False]) for n in part])
        for n in part:
            r = res.get(n)
            if r:
                bt[n] = int(r["timestamp"], 16)
        save_json("block_times.json", {str(k): v for k, v in bt.items()})
        print(f"[enrich]   {min(i + 2000, len(todo))}/{len(todo)}", flush=True)


class BlockClock:
    def __init__(self):
        bt = {int(k): v for k, v in load_json("block_times.json", {}).items()}
        self.keys = sorted(bt)
        self.vals = [bt[k] for k in self.keys]

    def ts(self, block):
        import bisect
        if not self.keys:
            return None
        i = bisect.bisect_left(self.keys, block)
        if i < len(self.keys) and self.keys[i] == block:
            return self.vals[i]
        if i == 0:
            return self.vals[0] - (self.keys[0] - block) * 0.1
        if i >= len(self.keys):
            return self.vals[-1] + (block - self.keys[-1]) * 0.1
        k0, k1 = self.keys[i - 1], self.keys[i]
        v0, v1 = self.vals[i - 1], self.vals[i]
        return v0 + (v1 - v0) * (block - k0) / (k1 - k0)


def iso(ts):
    if ts is None:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def tax_bucket(bps):
    for name, lo, hi in TAX_BUCKETS:
        if lo <= bps <= hi:
            return name
    return "other"


def quantile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def median(xs):
    return quantile(xs, 0.5)


def spearman(xs, ys):
    """Spearman rank correlation, ties averaged. None if degenerate."""
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


EXTRACT_COLS = [
    "curve", "deployer_id", "deployer_launches_in_scan", "launch_block", "launch_time", "in_cohort",
    "quote_symbol", "quote_kind", "fee_bps", "creator_tax_bps", "total_tax_bps", "tax_bucket",
    "n_trades", "unique_traders", "unique_traders_ex_deployer", "only_deployer_traded",
    "quote_volume_gross", "volume_usd_now", "one_way_volume_usd_now", "round_trip_volume_share",
    "deployer_buy_share", "top_buyer_share", "creator_tax_usd_now", "snipe_fee_usd_now",
    "graduated", "hours_to_graduation",
]


def write_extract(rows):
    """The committed per-launch file. launches.csv is ~75 MB (27 MB gzipped),
    almost all of it incompressible addresses and hashes, so the repo carries
    this instead: every launch, the columns the tables are computed from,
    floats rounded, and the deployer as an integer id in first-launch order
    (the address is one eth_getLogs away from the curve address)."""
    ids = {}
    for r in rows:
        ids.setdefault(r["deployer"], len(ids))
    path = os.path.join(DATA, "launches_extract.csv.gz")
    with gzip.open(path + ".tmp", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(EXTRACT_COLS)
        for r in rows:
            out = []
            for k in EXTRACT_COLS:
                v = ids[r["deployer"]] if k == "deployer_id" else r[k]
                if isinstance(v, float):
                    v = round(v, 4) if abs(v) < 10 else round(v, 2)
                out.append("" if v is None else v)
            w.writerow(out)
    os.replace(path + ".tmp", path)


def analyze(cohort_start=None, cohort_end=None, followup_hours=24.0):
    launches, _ = first_pass()
    meta = load_json("curve_meta.json", {})
    quotes = load_json("quote_tokens.json", {})
    prices = load_json("quote_prices.json", {})
    clock = BlockClock()
    a, b = scanned_range()
    stock_addrs = set()
    tp = os.path.join(HERE, "data", "rh_stock_tokens.json")
    if os.path.exists(tp):
        with open(tp) as f:
            stock_addrs = {v.lower() for v in json.load(f)["stock_tokens"].values()}

    agg = {c: {"buys": 0, "sells": 0, "quote_in": 0, "quote_out_net": 0, "quote_out_gross": 0,
               "fee": 0, "tax": 0, "traders": set(), "senders": set(), "first": None, "last": None,
               "same_sender_recipient": 0,
               "completed_block": None, "swept_block": None, "pool_block": None,
               "deployer_buy_in": 0, "deployer_sell_out": 0, "deployer_trades": 0,
               "top": defaultdict(int), "sell_by": defaultdict(int), "tax_seen": None, "fee_seen": None,
               "snipe_fee": 0, "snipe_trades": 0}
           for c in launches}
    token_to_curve = {l["token"]: c for c, l in launches.items()}
    stray = 0
    # The deployed curve charges a decaying anti-snipe fee on top of feeBps in
    # the first seconds after launch (the vendored curve source has no such
    # code; the chain does). It lands in the `fee` field, never in `tax`.
    # Offsets are in blocks after the launch block (~0.1 s each).
    SNIPE_OFFSETS = [(0, 10), (11, 30), (31, 60), (61, 150), (151, 300), (301, 10 ** 12)]
    snipe_prof = {k: {"trades": 0, "snipe_trades": 0, "eff_bps": []} for k in SNIPE_OFFSETS}
    for l in iter_logs():
        t0 = l["t"][0]
        if t0 == T_BUY or t0 == T_SELL:
            g = agg.get(l["a"])
            if g is None:
                stray += 1
                continue
            sender, recipient = addr_of(l["t"][1]), addr_of(l["t"][2])
            dep = launches[l["a"]]["deployer"]
            is_dep = recipient == dep or sender == dep
            if is_dep:
                g["deployer_trades"] += 1
            w = words(l["d"])
            base = (meta.get(l["a"]) or {}).get("feeBps") or 100
            gross = w[0] if t0 == T_BUY else w[1] + w[2] + w[3]
            excess = w[2] - gross * base // 10000
            off = l["b"] - launches[l["a"]]["block"]
            for k in SNIPE_OFFSETS:
                if k[0] <= off <= k[1]:
                    sp = snipe_prof[k]
                    sp["trades"] += 1
                    if excess > 1:
                        sp["snipe_trades"] += 1
                        if gross:
                            sp["eff_bps"].append(w[2] * 10000 / gross)
                    break
            if excess > 1:
                g["snipe_fee"] += excess
                g["snipe_trades"] += 1
            if t0 == T_BUY:
                spent, fee, tax = w[0], w[2], w[3]
                g["buys"] += 1
                g["quote_in"] += spent
                if is_dep:
                    g["deployer_buy_in"] += spent
                g["top"][recipient] += spent
                # 1e6 raw units keeps the rounding error of tax/spent under
                # 0.01 bps for every quote asset (10**12 excluded USDG, 6 dp)
                if spent >= 10 ** 6:
                    if g["tax_seen"] is None:
                        g["tax_seen"] = round(tax * 10000 / spent)
                    # min, not first: the snipe fee only ever raises the ratio
                    fs = round(fee * 10000 / spent)
                    g["fee_seen"] = fs if g["fee_seen"] is None else min(g["fee_seen"], fs)
            else:
                net, fee, tax = w[1], w[2], w[3]
                g["sells"] += 1
                g["quote_out_net"] += net
                g["quote_out_gross"] += net + fee + tax
                # the seller is msg.sender (it hands over the tokens); a buy's
                # holder is its recipient. Same address on both = a round trip.
                g["sell_by"][sender] += net + fee + tax
                if is_dep:
                    g["deployer_sell_out"] += net + fee + tax
            g["fee"] += fee
            g["tax"] += tax
            g["traders"].add(recipient)
            g["senders"].add(sender)
            if sender == recipient:
                g["same_sender_recipient"] += 1
            g["first"] = l["b"] if g["first"] is None else min(g["first"], l["b"])
            g["last"] = l["b"] if g["last"] is None else max(g["last"], l["b"])
        elif t0 == T_COMPLETED:
            g = agg.get(l["a"])
            if g is not None:
                g["completed_block"] = l["b"]
        elif l["a"] == FACTORY and t0 in (T_SWEPT, T_POOL_GRAD):
            c = token_to_curve.get(addr_of(l["t"][1]))
            if c is not None:
                agg[c]["swept_block" if t0 == T_SWEPT else "pool_block"] = l["b"]

    # per-launch rows
    rows = []
    mismatch = 0
    no_tax = 0
    for c, L in launches.items():
        g = agg[c]
        m = meta.get(c, {})
        ctax = m.get("creatorTaxBps")
        fee_bps = m.get("feeBps")
        if ctax is None:
            ctax = g["tax_seen"]
        if fee_bps is None:
            fee_bps = g["fee_seen"] if g["fee_seen"] is not None else 100
        if g["tax_seen"] is not None and m.get("creatorTaxBps") is not None and g["tax_seen"] != m["creatorTaxBps"]:
            mismatch += 1
        if ctax is None:
            no_tax += 1
            continue
        q = quotes.get(L["pair"], {"symbol": "?", "decimals": 18})
        dec = q["decimals"] or 18
        px = (prices.get(L["pair"]) or {}).get("usd")
        scale = 10 ** dec
        lt = clock.ts(L["block"])
        gt = clock.ts(g["completed_block"]) if g["completed_block"] else None
        top_share = (max(g["top"].values()) / g["quote_in"]) if g["quote_in"] else None
        vol = g["quote_in"] + g["quote_out_gross"]
        rt = sum(g["top"][x] + g["sell_by"][x] for x in g["top"] if x in g["sell_by"])
        n_tr = g["buys"] + g["sells"]
        rows.append({
            "token": L["token"], "curve": c, "deployer": L["deployer"], "tx": L["tx"],
            "quote_token": L["pair"], "quote_symbol": q["symbol"], "quote_decimals": dec,
            "quote_kind": ("native" if L["pair"] == NATIVE else "usdg" if L["pair"] == USDG
                           else "stock" if L["pair"] in stock_addrs else "other"),
            "launch_config_id": L["config"],
            "graduation_threshold": L["threshold"] / scale,
            "fee_bps": fee_bps, "creator_tax_bps": ctax, "total_tax_bps": fee_bps + ctax,
            "tax_bucket": tax_bucket(fee_bps + ctax),
            "launch_block": L["block"], "launch_time": iso(lt),
            "n_buys": g["buys"], "n_sells": g["sells"], "n_trades": g["buys"] + g["sells"],
            "unique_traders": len(g["traders"]), "unique_senders": len(g["senders"]),
            "unique_traders_ex_deployer": len(g["traders"] - {L["deployer"]}),
            "same_sender_recipient_trades": g["same_sender_recipient"],
            "quote_in_gross": g["quote_in"] / scale,
            "quote_out_net": g["quote_out_net"] / scale,
            "quote_out_gross": g["quote_out_gross"] / scale,
            "quote_volume_gross": (g["quote_in"] + g["quote_out_gross"]) / scale,
            "fees_collected": g["fee"] / scale, "creator_tax_collected": g["tax"] / scale,
            "snipe_fee_collected": g["snipe_fee"] / scale, "snipe_trades": g["snipe_trades"],
            "fee_bps_source": "creatorTaxBps()/feeBps() eth_call" if c in meta and m.get("feeBps") is not None
                              else "min trade-implied",
            "usd_price_now": px,
            "volume_usd_now": ((g["quote_in"] + g["quote_out_gross"]) / scale * px) if px else None,
            "creator_tax_usd_now": (g["tax"] / scale * px) if px else None,
            "fees_usd_now": (g["fee"] / scale * px) if px else None,
            "snipe_fee_usd_now": (g["snipe_fee"] / scale * px) if px else None,
            # curve-phase creator take: 35% of the base fee (30% protocol / 35% buyback-lock / 35% creator,
            # ref/CLAUDE.md) plus the whole creator tax. An estimate: the split is read from constructor defaults.
            "creator_revenue_est": (0.35 * g["fee"] + g["tax"]) / scale,
            "creator_revenue_usd_now": ((0.35 * g["fee"] + g["tax"]) / scale * px) if px else None,
            "deployer_buy_share": (g["deployer_buy_in"] / g["quote_in"]) if g["quote_in"] else None,
            "deployer_sell_out_gross": g["deployer_sell_out"] / scale,
            "deployer_volume_gross": (g["deployer_buy_in"] + g["deployer_sell_out"]) / scale,
            "deployer_volume_usd_now": ((g["deployer_buy_in"] + g["deployer_sell_out"]) / scale * px) if px else None,
            # creator tax the deployer address paid on its own trades, which pons
            # pays straight back to the creator (other wallets it controls are invisible)
            "creator_tax_paid_by_deployer": (g["deployer_buy_in"] + g["deployer_sell_out"]) * ctax / 10000 / scale,
            "creator_tax_paid_by_deployer_usd_now": ((g["deployer_buy_in"] + g["deployer_sell_out"]) * ctax / 10000 / scale * px)
                                                    if px else None,
            "deployer_trades": g["deployer_trades"],
            "only_deployer_traded": int(n_tr > 0 and g["deployer_trades"] == n_tr),
            # volume from addresses that both bought and sold this token: the
            # closest on-chain proxy for churn/wash this data offers
            "round_trip_volume_share": (rt / vol) if vol else None,
            "one_way_volume": (vol - rt) / scale,
            "one_way_volume_usd_now": ((vol - rt) / scale * px) if px else None,
            "top_buyer_share": top_share,
            "first_trade_block": g["first"] or "", "first_trade_time": iso(clock.ts(g["first"])) if g["first"] else "",
            "last_trade_block": g["last"] or "", "last_trade_time": iso(clock.ts(g["last"])) if g["last"] else "",
            "graduated": int(g["completed_block"] is not None),
            "graduated_block": g["completed_block"] or "", "graduated_time": iso(gt),
            "hours_to_graduation": round((gt - lt) / 3600, 3) if (gt and lt) else "",
            "pool_created": int(g["pool_block"] is not None),
        })
    per_dep = defaultdict(int)
    for r in rows:
        per_dep[r["deployer"]] += 1
    for r in rows:
        r["deployer_launches_in_scan"] = per_dep[r["deployer"]]
    scan_start_ts, scan_end_ts = clock.ts(a), clock.ts(b)
    if cohort_start is None:
        cohort_start = scan_start_ts
    if cohort_end is None:
        cohort_end = scan_end_ts - followup_hours * 3600
    for r in rows:
        t = clock.ts(r["launch_block"])
        r["in_cohort"] = int(cohort_start <= t <= cohort_end)
    rows.sort(key=lambda r: r["launch_block"])
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "launches.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    write_extract(rows)
    print(f"[analyze] {len(rows)} launches written; {stray} curve logs from non-pons addresses ignored; "
          f"{mismatch} launches where trade-implied tax != creatorTaxBps()")

    all_rows = rows
    rows = [r for r in rows if r["in_cohort"]]
    summary = {"window": {"from_block": a, "to_block": b, "from_time": iso(scan_start_ts), "to_time": iso(scan_end_ts),
                          "cohort_start": iso(cohort_start), "cohort_end": iso(cohort_end),
                          "followup_hours": followup_hours},
               "n_launches_scanned": len(all_rows), "n_launches": len(rows), "tables": {}, "spearman": {}, "quotes": {}}
    n_trades_all = sum(g["buys"] + g["sells"] for g in agg.values())
    summary["checks"] = {
        "launch_events": len(launches),
        "launches_dropped_no_tax_known": no_tax,
        "duplicate_curves_in_csv": len(all_rows) - len({r["curve"] for r in all_rows}),
        "duplicate_tokens_in_csv": len(all_rows) - len({r["token"] for r in all_rows}),
        "curve_logs_from_non_pons_addresses": stray,
        "tax_mismatch_trade_vs_creatorTaxBps": mismatch,
        "fee_bps_values": dict(Counter(r["fee_bps"] for r in all_rows)),
        "trades_total": n_trades_all,
        "trades_sender_eq_recipient": sum(g["same_sender_recipient"] for g in agg.values()),
        "scan_launches_traded": sum(1 for r in all_rows if r["n_trades"] > 0),
        "scan_launches_graduated": sum(r["graduated"] for r in all_rows),
        "scan_graduated_without_pool_event": sum(1 for r in all_rows if r["graduated"] and not r["pool_created"]),
        "cohort_launches_traded": sum(1 for r in rows if r["n_trades"] > 0),
        "cohort_launches_graduated": sum(r["graduated"] for r in rows),
        "cohort_quote_kinds": dict(Counter(r["quote_kind"] for r in rows)),
        "cohort_total_tax_bps": dict(sorted(Counter(r["total_tax_bps"] for r in rows).items())),
        "cohort_traded_without_usd_price": sum(1 for r in rows if r["n_trades"] > 0 and r["volume_usd_now"] is None),
        "deployers_in_cohort": len({r["deployer"] for r in rows}),
        "top10_deployer_launch_share": sum(c for _, c in Counter(r["deployer"] for r in rows).most_common(10)) / len(rows),
    }
    summary["snipe"] = {
        "launches_with_snipe_taxed_trade": sum(1 for r in all_rows if r["snipe_trades"] > 0),
        "snipe_taxed_trades": sum(r["snipe_trades"] for r in all_rows),
        "snipe_fee_usd_now": sum(r["snipe_fee_usd_now"] or 0 for r in all_rows),
        "all_fees_usd_now": sum(r["fees_usd_now"] or 0 for r in all_rows),
        "creator_tax_usd_now": sum(r["creator_tax_usd_now"] or 0 for r in all_rows),
        "by_blocks_after_launch": [
            {"blocks": f"{k[0]}-{k[1]}" if k[1] < 10 ** 12 else f">{k[0] - 1}", "trades": v["trades"],
             "snipe_taxed": v["snipe_trades"], "median_effective_fee_bps_when_taxed": median(v["eff_bps"]),
             "max_effective_fee_bps": max(v["eff_bps"]) if v["eff_bps"] else None}
            for k, v in snipe_prof.items()],
    }

    ORGANIC_MIN_TRADERS = 3
    FEW_LAUNCHES = 3

    def _share(rs, num, den):
        # in the same units row by row; rows without a USD price drop out of both sums
        pairs = [(r[num], r[den]) for r in rs if r[num] is not None and r[den] is not None]
        d = sum(b for _, b in pairs)
        return (sum(a for a, _ in pairs) / d) if d else None

    def table(subset, vol_key, organic=False):
        rev_key = "creator_revenue_usd_now" if vol_key == "volume_usd_now" else "creator_revenue_est"
        out = []
        for name, lo, hi in TAX_BUCKETS:
            rs = [r for r in subset if lo <= r["total_tax_bps"] <= hi]
            if organic:
                traded = [r for r in rs if r["unique_traders_ex_deployer"] >= ORGANIC_MIN_TRADERS]
            else:
                traded = [r for r in rs if r["n_trades"] > 0]
            vols = [r[vol_key] for r in traded if r[vol_key] is not None]
            ow_key = "one_way_volume_usd_now" if vol_key == "volume_usd_now" else "one_way_volume"
            ows = [r[ow_key] for r in traded if r[ow_key] is not None]
            grads = [r for r in rs if r["graduated"]]
            grads_t = [r for r in traded if r["graduated"]]
            out.append({
                "bucket": name, "n": len(rs), "n_traded": len(traded),
                "traded_share": len(traded) / len(rs) if rs else None,
                "median_volume_traded": median(vols), "p90_volume_traded": quantile(vols, 0.9),
                "total_volume": sum(vols),
                "median_one_way_volume_traded": median(ows), "total_one_way_volume": sum(ows),
                "deployer_share_of_volume": _share(traded, "deployer_volume_usd_now" if vol_key == "volume_usd_now"
                                                   else "deployer_volume_gross", vol_key),
                "deployer_share_of_creator_tax": (
                    _share(traded, "creator_tax_paid_by_deployer_usd_now", "creator_tax_usd_now") if vol_key == "volume_usd_now"
                    else _share(traded, "creator_tax_paid_by_deployer", "creator_tax_collected")),
                "median_trades_traded": median([r["n_trades"] for r in traded]),
                "median_traders_all_traded": median([r["unique_traders"] for r in traded]),
                "median_traders_traded": median([r["unique_traders_ex_deployer"] for r in traded]),
                "share_traded_only_by_deployer": (sum(r["only_deployer_traded"] for r in traded) / len(traded)) if traded else None,
                "median_round_trip_share": median([r["round_trip_volume_share"] for r in traded if r["round_trip_volume_share"] is not None]),
                "median_top_buyer_share_graduated": median([r["top_buyer_share"] for r in grads if r["top_buyer_share"] is not None]),
                "n_deployers": len({r["deployer"] for r in rs}),
                "top10_deployer_launch_share": (sum(c for _, c in Counter(x["deployer"] for x in rs).most_common(10)) / len(rs)) if rs else None,
                "graduated": len(grads),
                "grad_rate": len(grads) / len(rs) if rs else None,
                "grad_rate_traded": len(grads_t) / len(traded) if traded else None,
                "median_hours_to_grad": median([r["hours_to_graduation"] for r in grads if r["hours_to_graduation"] != ""]),
                "median_deployer_buy_share": median([r["deployer_buy_share"] for r in traded if r["deployer_buy_share"] is not None]),
                "median_creator_tax_traded": median([r[rev_key] for r in traded if r[rev_key] is not None]),
                "total_creator_tax": sum(r[rev_key] for r in traded if r[rev_key] is not None),
            })
        return out

    subsets = {
        "all (USD, converted at today's Chainlink price)": ([r for r in rows if r["volume_usd_now"] is not None or r["n_trades"] == 0], "volume_usd_now"),
        "stock-quoted (USD at today's price)": ([r for r in rows if r["quote_kind"] == "stock"], "volume_usd_now"),
        "USDG-quoted (USDG)": ([r for r in rows if r["quote_kind"] == "usdg"], "quote_volume_gross"),
        "native ETH-quoted (ETH)": ([r for r in rows if r["quote_kind"] == "native"], "quote_volume_gross"),
        # serial launchers (bots) dominate raw launch counts; a creator with a
        # handful of launches is closer to the person Hedgefun's form serves
        f"all, deployers with <= {FEW_LAUNCHES} launches in the scan (USD)": (
            [r for r in rows if r["deployer_launches_in_scan"] <= FEW_LAUNCHES
             and (r["volume_usd_now"] is not None or r["n_trades"] == 0)], "volume_usd_now"),
    }
    summary["organic_min_traders"] = ORGANIC_MIN_TRADERS
    summary["few_launches"] = FEW_LAUNCHES
    summary["tables_organic"] = {}
    for name, (sub, key) in subsets.items():
        summary["tables"][name] = table(sub, key)
        summary["tables_organic"][name] = table(sub, key, organic=True)
        traded = [r for r in sub if r["n_trades"] > 0 and r[key] is not None]
        summary["spearman"][name] = {
            "n_traded": len(traded),
            "tax_vs_log_volume": spearman([r["total_tax_bps"] for r in traded], [math.log(r[key] + 1e-9) for r in traded]),
            "tax_vs_trades": spearman([r["total_tax_bps"] for r in traded], [r["n_trades"] for r in traded]),
            "tax_vs_traders": spearman([r["total_tax_bps"] for r in traded], [r["unique_traders"] for r in traded]),
            "tax_vs_graduated_all": spearman([r["total_tax_bps"] for r in sub], [r["graduated"] for r in sub]),
        }
        organic = [r for r in sub if r["unique_traders_ex_deployer"] >= ORGANIC_MIN_TRADERS and r[key] is not None]
        summary["spearman"][name]["n_organic"] = len(organic)
        summary["spearman"][name]["organic_tax_vs_log_volume"] = spearman(
            [r["total_tax_bps"] for r in organic], [math.log(r[key] + 1e-9) for r in organic])
        summary["spearman"][name]["organic_tax_vs_traders"] = spearman(
            [r["total_tax_bps"] for r in organic], [r["unique_traders_ex_deployer"] for r in organic])
        summary["spearman"][name]["organic_tax_vs_graduated"] = spearman(
            [r["total_tax_bps"] for r in organic], [r["graduated"] for r in organic])
    # within-deployer: the same creator at 1% and at a higher tax. Holds the
    # launcher fixed, which the bucket tables cannot. Per deployer, compare the
    # share of their launches that traded / graduated / drew >= 3 outside
    # traders at 1% against the same shares at the higher tax, then average.
    summary["within_deployer"] = {}
    base_name = TAX_BUCKETS[0][0]
    for name, lo, hi in TAX_BUCKETS[1:]:
        by_dep = defaultdict(lambda: {"base": [], "hi": []})
        for r in rows:
            if r["total_tax_bps"] == 100:
                by_dep[r["deployer"]]["base"].append(r)
            elif lo <= r["total_tax_bps"] <= hi:
                by_dep[r["deployer"]]["hi"].append(r)
        both = {d: v for d, v in by_dep.items() if v["base"] and v["hi"]}
        res = {"n_deployers": len(both), "n_launches_base": sum(len(v["base"]) for v in both.values()),
               "n_launches_higher": sum(len(v["hi"]) for v in both.values())}
        for metric, f in (("traded", lambda r: r["n_trades"] > 0),
                          ("graduated", lambda r: r["graduated"] == 1),
                          ("organic", lambda r: r["unique_traders_ex_deployer"] >= ORGANIC_MIN_TRADERS)):
            diffs = []
            for v in both.values():
                pb = sum(1 for r in v["base"] if f(r)) / len(v["base"])
                ph = sum(1 for r in v["hi"] if f(r)) / len(v["hi"])
                diffs.append(ph - pb)
            res[metric] = {"mean_rate_base": (sum(sum(1 for r in v["base"] if f(r)) / len(v["base"]) for v in both.values()) / len(both)) if both else None,
                           "mean_rate_higher": (sum(sum(1 for r in v["hi"] if f(r)) / len(v["hi"]) for v in both.values()) / len(both)) if both else None,
                           "mean_diff_higher_minus_base": (sum(diffs) / len(diffs)) if diffs else None,
                           "deployers_higher_better": sum(1 for d in diffs if d > 0),
                           "deployers_higher_worse": sum(1 for d in diffs if d < 0),
                           "deployers_tie": sum(1 for d in diffs if d == 0)}
        # volume and outside traders, same creator: per creator, the median over
        # their traded launches at each tax (USD at today's price), then the
        # median across creators of higher / base and higher - base
        ratios, tdiffs = [], []
        for v in both.values():
            vb = [r["volume_usd_now"] for r in v["base"] if r["n_trades"] > 0 and r["volume_usd_now"]]
            vh = [r["volume_usd_now"] for r in v["hi"] if r["n_trades"] > 0 and r["volume_usd_now"]]
            if vb and vh:
                ratios.append(median(vh) / median(vb))
            tb = [r["unique_traders_ex_deployer"] for r in v["base"] if r["n_trades"] > 0]
            th = [r["unique_traders_ex_deployer"] for r in v["hi"] if r["n_trades"] > 0]
            if tb and th:
                tdiffs.append(median(th) - median(tb))
        res["volume"] = {"n_deployers": len(ratios), "median_ratio_higher_over_base": median(ratios),
                         "deployers_higher_more": sum(1 for x in ratios if x > 1),
                         "deployers_higher_less": sum(1 for x in ratios if x < 1)}
        res["outside_traders"] = {"n_deployers": len(tdiffs), "median_diff_higher_minus_base": median(tdiffs),
                                  "mean_diff_higher_minus_base": (sum(tdiffs) / len(tdiffs)) if tdiffs else None,
                                  "deployers_higher_more": sum(1 for x in tdiffs if x > 0),
                                  "deployers_higher_less": sum(1 for x in tdiffs if x < 0)}
        summary["within_deployer"][f"{base_name} vs {name}"] = res
    # per stock symbol, in stock units
    by_sym = defaultdict(list)
    for r in rows:
        if r["quote_kind"] == "stock":
            by_sym[r["quote_symbol"]].append(r)
    for sym, rs in sorted(by_sym.items(), key=lambda kv: -len(kv[1])):
        summary["quotes"][sym] = {"n": len(rs), "n_traded": sum(1 for r in rs if r["n_trades"] > 0),
                                  "graduated": sum(r["graduated"] for r in rs),
                                  "volume_units": sum(r["quote_volume_gross"] for r in rs),
                                  "usd_price_now": rs[0]["usd_price_now"],
                                  "by_bucket": table(rs, "quote_volume_gross")}
    # distribution of creator tax choices
    dist = defaultdict(int)
    for r in rows:
        dist[r["creator_tax_bps"]] += 1
    summary["creator_tax_distribution"] = dict(sorted(dist.items()))
    save_json("summary.json", summary)
    print(render(summary))
    return summary


def fmt(x, nd=1):
    if x is None or x == "":
        return "-"
    if isinstance(x, float):
        if abs(x) >= 1000:
            return f"{x:,.0f}"
        return f"{x:.{nd}f}" if abs(x) >= 1 else f"{x:.3f}"
    return str(x)


def pct(x):
    return "-" if x is None else f"{100 * x:.1f}%"


def render(summary):
    out = []
    w = summary["window"]
    out.append(f"scan: blocks {w['from_block']}-{w['to_block']} ({w['from_time']} to {w['to_time']}); "
               f"cohort: launches {w['cohort_start']} to {w['cohort_end']} "
               f"({summary['n_launches']} of {summary['n_launches_scanned']} scanned)\n")
    def emit(title, rows, traded_label):
        out.append(f"### {title}\n")
        out.append(f"| tax | launches | {traded_label} | median vol | p90 vol | total vol | median trades | median traders | median traders (ex-creator) | graduated | grad rate (all) | grad rate ({traded_label}) | median h to grad | median creator buy share | only creator traded | median round-trip vol share | median top-buyer share (graduated) | deployers | top-10 deployer share | median creator revenue (est.) | total creator revenue (est.) |")
        out.append("|" + "---|" * 21)
        for r in rows:
            out.append(f"| {r['bucket']} | {r['n']} | {pct(r['traded_share'])} | {fmt(r['median_volume_traded'])} | "
                       f"{fmt(r['p90_volume_traded'])} | {fmt(r['total_volume'])} | {fmt(r['median_trades_traded'])} | "
                       f"{fmt(r['median_traders_all_traded'])} | "
                       f"{fmt(r['median_traders_traded'])} | {r['graduated']} | {pct(r['grad_rate'])} | "
                       f"{pct(r['grad_rate_traded'])} | {fmt(r['median_hours_to_grad'])} | {pct(r['median_deployer_buy_share'])} | "
                       f"{pct(r['share_traded_only_by_deployer'])} | {pct(r['median_round_trip_share'])} | "
                       f"{pct(r['median_top_buyer_share_graduated'])} | {r['n_deployers']} | {pct(r['top10_deployer_launch_share'])} | "
                       f"{fmt(r['median_creator_tax_traded'], 2)} | {fmt(r['total_creator_tax'])} |")
        out.append("")

    for name in summary["tables"]:
        emit(f"{name}: launches with at least one trade", summary["tables"][name], "traded")
        emit(f"{name}: launches with >= {summary['organic_min_traders']} traders other than the creator",
             summary["tables_organic"][name], "organic")
        s = summary["spearman"][name]
        out.append(f"Spearman, traded (n={s['n_traded']}): tax vs log volume {fmt(s['tax_vs_log_volume'], 3)}, "
                   f"tax vs trades {fmt(s['tax_vs_trades'], 3)}, tax vs traders {fmt(s['tax_vs_traders'], 3)}; "
                   f"tax vs graduated over all launches {fmt(s['tax_vs_graduated_all'], 3)}. "
                   f"Organic (n={s['n_organic']}): tax vs log volume {fmt(s['organic_tax_vs_log_volume'], 3)}, "
                   f"tax vs traders {fmt(s['organic_tax_vs_traders'], 3)}, tax vs graduated {fmt(s['organic_tax_vs_graduated'], 3)}\n")
    out.append("### within-deployer: the same creator at 1% and at a higher tax\n")
    out.append("| comparison | deployers | launches at 1% | launches higher | traded: 1% / higher / diff | graduated: 1% / higher / diff | organic: 1% / higher / diff | graduated: higher better / worse / tie | median volume ratio higher / 1% (deployers more / less) | median outside traders, higher - 1% (more / less) |")
    out.append("|" + "---|" * 10)
    for k, v in summary.get("within_deployer", {}).items():
        cells = []
        for m in ("traded", "graduated", "organic"):
            x = v[m]
            d = x["mean_diff_higher_minus_base"]
            dtxt = "-" if d is None else f"{100 * d:+.1f} pp"
            cells.append(f"{pct(x['mean_rate_base'])} / {pct(x['mean_rate_higher'])} / {dtxt}")
        g = v["graduated"]
        vv, tt = v["volume"], v["outside_traders"]
        out.append(f"| {k} | {v['n_deployers']} | {v['n_launches_base']} | {v['n_launches_higher']} | {cells[0]} | {cells[1]} | {cells[2]} | "
                   f"{g['deployers_higher_better']} / {g['deployers_higher_worse']} / {g['deployers_tie']} | "
                   f"{fmt(vv['median_ratio_higher_over_base'], 2)} ({vv['deployers_higher_more']} / {vv['deployers_higher_less']}) | "
                   f"{fmt(tt['median_diff_higher_minus_base'], 1)} ({tt['deployers_higher_more']} / {tt['deployers_higher_less']}) |")
    out.append("")
    out.append("### checks\n")
    out.append(json.dumps(summary.get("checks", {}), indent=1))
    out.append("")
    out.append("### creator tax choices (bps -> launches)\n")
    out.append(", ".join(f"{k}: {v}" for k, v in summary["creator_tax_distribution"].items()))
    return "\n".join(out)


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["scan", "enrich", "analyze", "all"])
    ap.add_argument("--from-block", type=int, default=None,
                    help=f"default: --from-time, else {DEFAULT_FROM_BLOCK} (factory start)")
    ap.add_argument("--from-time", default=None, help="ISO UTC, e.g. 2026-09-17T00:00:00Z; resolved to a block")
    ap.add_argument("--to-block", type=int, default=None, help="default: head - 100")
    ap.add_argument("--cohort-start", default=None, help="ISO UTC; launches before this are excluded from tables")
    ap.add_argument("--cohort-end", default=None,
                    help="ISO UTC; launches after this are excluded from tables (default: scan end - 24h)")
    ap.add_argument("--followup-hours", type=float, default=24.0)
    args = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    if args.phase in ("scan", "all"):
        from_block = args.from_block
        if from_block is None and args.from_time:
            from_block = block_at(parse_time(args.from_time))
            print(f"[scan] {args.from_time} -> block {from_block}")
        if from_block is None:
            from_block = DEFAULT_FROM_BLOCK
        to_block = args.to_block or (head_block() - 100)
        print(f"[scan] blocks {from_block}-{to_block}")
        scan(from_block, to_block)
    if args.phase in ("enrich", "all"):
        enrich()
    if args.phase in ("analyze", "all"):
        analyze(cohort_start=parse_time(args.cohort_start) if args.cohort_start else None,
                cohort_end=parse_time(args.cohort_end) if args.cohort_end else None,
                followup_hours=args.followup_hours)


if __name__ == "__main__":
    main()
