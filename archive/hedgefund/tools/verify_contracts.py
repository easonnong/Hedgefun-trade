#!/usr/bin/env python3
"""Read-only factory discovery; opt-in source publication to Sourcify. Never signs."""
import argparse
import contextlib
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

CHAIN = 4663
FACTORY = "0x58f6ced8d02cd2567f1458801440bc4eb67fa961"
REVISION = "3dc07eb83212d5fac4abeb9b5606c8accb9f254c"
FACTORY_START = 69454565            # the factory's deployment block
# Launched(uint256 indexed id, string symbol, address token, address treasury, address hook, address stock, address creator)
LAUNCHED_TOPIC = "0x797d1021a44c2a68e4c02160ae40b17e66b2feded79284a0cfe931e9e4c2a61e"
# The chain's own public RPC: no key, and it serves recent historical state and wide keyed log queries.
# PublicNode refuses both from a cloud host ("archive requests require a personal token").
DEFAULT_RPC = "https://rpc.mainnet.chain.robinhood.com"
API = "https://sourcify.dev/server/v2/contract"
TEMPLATES = {"token": "src/HedgeFunToken.sol:HedgeFunToken",
             "treasury": "src/HedgeFunTreasury.sol:HedgeFunTreasury"}
MATCHES = {"exact_match", "match"}
MAX_BODY = 8_000_000                # bytes read from any RPC or Sourcify response; more is refused, not truncated
MAX_STRATEGIES = 100_000            # strategyCount bound with no previous snapshot
MAX_NEW_STRATEGIES = 1_000          # ... and its growth bound over the previous snapshot's count
CREATION_LOOKUP_RETRY = 3600        # seconds between creation-tx lookups for a strategy after one failed


class ResponseTooLarge(RuntimeError):
    pass


class UnexpectedMatch(RuntimeError):
    """Sourcify returned a match value outside the known set: stored as None, and the record is an error."""


def read_json(response, limit=None):
    limit = MAX_BODY if limit is None else limit
    data = response.read(limit + 1)
    if len(data) > limit:
        raise ResponseTooLarge(f"Response larger than {limit} bytes")
    return json.loads(data)


def address(value):
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", value) or int(value, 16) == 0:
        raise ValueError("Invalid or zero address")
    return value.lower()


def command(args, cwd=None, timeout=300, strip=True):
    # Do not inherit private-key, RPC or FOUNDRY_* overrides from an operator shell.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR") if k in os.environ}
    env["FOUNDRY_PROFILE"] = "default"
    proc = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError(f"{args[0]} failed: {(proc.stderr or proc.stdout)[-2000:]}")
    return proc.stdout.strip() if strip else proc.stdout


RPC_RETRY_CODES = {403, 429, 500, 502, 503, 504}
RPC_BACKOFF = (1, 2, 4)
RPC_TRANSIENT = (urllib.error.URLError, TimeoutError, ConnectionResetError, http.client.IncompleteRead,
                 json.JSONDecodeError)


def rate_limited(error):
    """A JSON-RPC rate-limit refusal, which some providers return with HTTP 200."""
    if not isinstance(error, dict):
        return False
    message = str(error.get("message", "")).lower()
    return error.get("code") == -32005 or "rate" in message or "limit" in message


def rpc(url, method, params, sleep=time.sleep):
    if method not in {"eth_chainId", "eth_getBlockByNumber", "eth_call", "eth_getCode", "eth_getLogs"}:
        raise ValueError("Only read-only RPC methods are allowed")
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    # Public endpoints turn away an occasional request from a cloud IP (403), throttle (429, or a JSON-RPC
    # rate-limit error with HTTP 200), or drop a connection; one refusal must not abort a whole pass, so a
    # transient failure is retried with a short backoff.
    for delay in (*RPC_BACKOFF, None):
        req = urllib.request.Request(url, payload, {"Content-Type": "application/json", "User-Agent": "HedgeFun-verifier/1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                body = read_json(response)
        except urllib.error.HTTPError as error:
            if error.code not in RPC_RETRY_CODES or delay is None:
                raise RuntimeError(f"RPC {method} failed: HTTP {error.code}") from error
        except ResponseTooLarge as error:
            raise RuntimeError(f"RPC {method} failed: {error}") from error
        except RPC_TRANSIENT as error:
            if delay is None:
                raise RuntimeError(f"RPC {method} failed: {error}") from error
        else:
            if not isinstance(body, dict):
                raise RuntimeError(f"RPC {method} failed: malformed response")
            if delay is None or not rate_limited(body.get("error")):
                break
        sleep(delay)
    if "error" in body or "result" not in body:
        raise RuntimeError(f"RPC {method} failed: {body.get('error', 'missing result')}")
    return body["result"]


def calldata(signature, *args):
    return command(["cast", "calldata", signature, *map(str, args)])


def discover(url, factory, confirmations=12, previous_count=None):
    if int(rpc(url, "eth_chainId", []), 16) != CHAIN:
        raise ValueError("RPC chain does not match Robinhood mainnet 4663")
    latest = rpc(url, "eth_getBlockByNumber", ["latest", False])
    number = max(0, int(latest["number"], 16) - confirmations)
    block = rpc(url, "eth_getBlockByNumber", [hex(number), False])
    # Every call uses the same height; a final hash check rejects a reorg during discovery.
    tag = block["number"]
    if rpc(url, "eth_getCode", [factory, tag]) == "0x":
        raise ValueError("Factory has no code at snapshot")
    count = int(rpc(url, "eth_call", [{"to": factory,
        "data": calldata("strategyCount()")}, tag]), 16)
    # A lying or broken RPC must not make the loop below read (and the service submit) without end.
    limit = MAX_STRATEGIES if previous_count is None else previous_count + MAX_NEW_STRATEGIES
    if count > limit:
        raise ValueError(f"strategyCount {count} exceeds the bound {limit}; refusing the snapshot")
    found = []
    for index in range(count):
        encoded = rpc(url, "eth_call", [{"to": factory,
            "data": calldata("strategies(uint256)", index)}, tag])
        if not re.fullmatch(r"0x[0-9a-fA-F]{320}", encoded):
            raise ValueError("Unexpected strategies ABI response")
        words = [encoded[2+i*64:2+(i+1)*64] for i in range(5)]
        if any(int(word[:24], 16) for word in words):
            raise ValueError("Invalid ABI address padding")
        for kind, word in zip(("token", "treasury"), words):
            found.append({"address": address("0x" + word[-40:]), "contract": TEMPLATES[kind],
                          "kind": kind, "strategyId": index})
    if rpc(url, "eth_getBlockByNumber", [tag, False])["hash"] != block["hash"]:
        raise RuntimeError("Snapshot reorganized; retry discovery")
    return {"number": tag, "hash": block["hash"], "strategyCount": count}, found


def validate_source(source, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected revision must be a full 40-character commit")
    if command(["git", "rev-parse", "HEAD"], source) != revision:
        raise ValueError("Source checkout does not match pinned deployment revision")
    if command(["git", "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"], source):
        raise ValueError("Source checkout or dependencies are dirty")
    submodules = command(["git", "submodule", "status", "--recursive"], source, strip=False)
    if any(line and line[0] != " " for line in submodules.splitlines()):
        raise ValueError("Submodule revisions do not match deployment checkout")
    if (source / ".env").exists():
        raise ValueError("Isolated verification source checkout must not contain .env")
    tracked = set(command(["git", "ls-files", "--recurse-submodules"], source).splitlines())
    return tracked


def validate_input(source, target, tracked):
    if not re.fullmatch(r"src/[A-Za-z0-9_/]+\.sol:[A-Za-z0-9_]+", target):
        raise ValueError("Only explicit local src contracts can be published")
    raw = command(["forge", "verify-contract", "--root", str(source), "--chain", str(CHAIN),
                   "--show-standard-json-input", "0x0000000000000000000000000000000000000001", target], source)
    data = json.loads(raw)
    sources = data.get("sources", {})
    if not sources or target.split(":")[0] not in sources:
        raise ValueError("Compiler input is missing selected contract")
    for path, value in sources.items():
        if path not in tracked or not path.endswith(".sol") or not path.startswith(("src/", "lib/")):
            raise ValueError(f"Refusing non-contract or untracked source: {path}")
        file = (source / path).resolve()
        if not file.is_relative_to(source.resolve()) or value.get("content") != file.read_text():
            raise ValueError(f"Source content/path mismatch: {path}")
    return len(sources)


def sourcify_status(addr):
    req = urllib.request.Request(f"{API}/{CHAIN}/{addr}", headers={"User-Agent": "HedgeFun-verifier/1"})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = read_json(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {"status": "unverified", "runtimeMatch": None, "creationMatch": None}
        raise RuntimeError(f"Sourcify HTTP {error.code}") from error
    if not isinstance(body, dict) or "runtimeMatch" not in body or "creationMatch" not in body:
        raise RuntimeError("Unexpected Sourcify response; not verification evidence")
    if address(body.get("address", addr)) != addr or str(body.get("chainId", CHAIN)) != str(CHAIN):
        raise RuntimeError("Sourcify returned another contract/chain")
    runtime, creation = body["runtimeMatch"], body["creationMatch"]
    for value in (runtime, creation):
        if not known_match(value):
            raise UnexpectedMatch(f"Unexpected Sourcify match value {clean_text(str(value))[:80]!r}")
    if runtime in MATCHES and creation in MATCHES:
        status = "verified"
    elif runtime in MATCHES:
        status = "runtime_only"
    else:
        status = "unverified"
    return {"status": status, "runtimeMatch": runtime, "creationMatch": creation}


def known_match(value):
    return value is None or (isinstance(value, str) and value in MATCHES)


def load_manifest(path, factory, revision):
    if not path:
        return []
    data = json.loads(path.read_text())
    if data.get("chainId") != CHAIN or address(data.get("factory", "")) != factory or data.get("sourceRevision") != revision:
        raise ValueError("Manifest chain/factory/source revision mismatch")
    rows = data.get("contracts", [])
    for row in rows:
        row["address"] = address(row["address"])
        if row.get("creationTxHash") and not re.fullmatch(r"0x[0-9a-fA-F]{64}", row["creationTxHash"]):
            raise ValueError("Invalid creation transaction hash")
        if not re.fullmatch(r"src/[A-Za-z0-9_/]+\.sol:[A-Za-z0-9_]+", row["contract"]):
            raise ValueError("Invalid local contract identifier")
    return rows


def creation_tx(url, factory, strategy_id, token, treasury, to_block):
    """The launch transaction that created a strategy's token and treasury, from the factory's own Launched log.

    Sourcify cannot always find a factory child's creation on its own, and without it only the runtime code
    matches. The log is keyed on the indexed id, and its token and treasury must be the ones discovered.
    """
    logs = rpc(url, "eth_getLogs", [{"address": factory, "fromBlock": hex(FACTORY_START), "toBlock": to_block,
                                     "topics": [LAUNCHED_TOPIC, "0x%064x" % strategy_id]}])
    if not isinstance(logs, list) or len(logs) != 1:
        raise ValueError(f"Expected one Launched log for strategy {strategy_id}")
    log = logs[0]
    topics = log.get("topics") or []
    if (str(log.get("address", "")).lower() != factory.lower() or log.get("removed") is True
            or [str(t).lower() for t in topics[:2]] != [LAUNCHED_TOPIC, "0x%064x" % strategy_id]):
        raise ValueError(f"Launched log for strategy {strategy_id} is not the factory's live log")
    words = [log["data"][2 + i * 64:2 + (i + 1) * 64] for i in range(3)]
    if address("0x" + words[1][-40:]) != token or address("0x" + words[2][-40:]) != treasury:
        raise ValueError(f"Launched log for strategy {strategy_id} names other contracts")
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", log.get("transactionHash", "")):
        raise ValueError("Launched log has no transaction hash")
    return log["transactionHash"].lower()


def attach_creation_txs(url, factory, found, previous, to_block, now=None):
    """Give every discovered child its creation transaction: remembered from state, else looked up.

    A failed lookup scans the factory's logs from its deployment block, so it is not repeated on every pass:
    it is retried at most every CREATION_LOOKUP_RETRY seconds per strategy.
    """
    now = int(time.time()) if now is None else now
    by_strategy = {}
    for row in found:
        if "strategyId" in row:             # only factory children have a Launched log
            by_strategy.setdefault(row["strategyId"], {})[row["kind"]] = row
    for strategy_id, pair in by_strategy.items():
        known = [previous.get(row["address"], {}).get("creationTxHash") for row in pair.values()]
        tx = next((value for value in known if value), None)
        if not tx and "token" in pair and "treasury" in pair:
            failed = max(previous.get(row["address"], {}).get("creationTxLookupFailedAt") or 0 for row in pair.values())
            if now - failed < CREATION_LOOKUP_RETRY:
                continue
            try:
                tx = creation_tx(url, factory, strategy_id, pair["token"]["address"], pair["treasury"]["address"], to_block)
            except Exception as error:  # without it the submission still runs, as before, and may match runtime only
                print(f"No creation transaction for strategy {strategy_id}: {str(error).replace(url, '[RPC]')}",
                      file=sys.stderr, flush=True)
                for row in pair.values():
                    row["creationTxLookupFailedAt"] = now
        if tx:
            for row in pair.values():
                row["creationTxHash"] = tx
    return found


def merge_targets(found, manifest):
    result = {row["address"]: dict(row) for row in found}
    for row in manifest:
        previous = result.get(row["address"])
        if previous and previous["contract"] != row["contract"]:
            raise ValueError("Manifest conflicts with factory-discovered contract")
        result[row["address"]] = {**(previous or {"kind": "manifest"}), **row}
    return list(result.values())


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
        json.dump(state, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
        temporary = output.name
    os.replace(temporary, path)


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another verifier owns this state lock") from error
        yield


def clean_text(text, head=300, tail=1500):
    """HTML stripped and bounded. Forge prints its error last, so the tail is kept rather than the head."""
    text = re.sub(r"<[^>]+>", " ", text).strip()
    return text if len(text) <= head + tail else text[:head] + " [...] " + text[-tail:]


def clean_external(value, depth=0):
    """External (Sourcify/forge) data made safe to store: bounded strings, keys, items and depth."""
    if depth > 8:
        return None
    if isinstance(value, dict):
        return {re.sub(r"<[^>]+>", " ", str(k)).strip()[:100]: clean_external(v, depth + 1)
                for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [clean_external(v, depth + 1) for v in value[:50]]
    if isinstance(value, str):
        return clean_text(value)
    return value


def job_status(job_id):
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
        raise ValueError("Invalid Sourcify job ID")
    url = f"https://sourcify.dev/server/v2/verify/{job_id}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HedgeFun-verifier/1"}), timeout=45) as response:
        body = read_json(response)
    if not isinstance(body, dict) or not isinstance(body.get("isJobCompleted"), bool):
        raise RuntimeError("Unexpected verification job response")
    return {"jobId": job_id, "jobUrl": url, "jobCompleted": body["isJobCompleted"],
            "externalVerifications": clean_external(body.get("externalVerifications", {})),
            "jobError": clean_external(body.get("error"))}


def submit(source, url, target):
    args = ["forge", "verify-contract", "--root", str(source), "--chain", str(CHAIN),
            "--verifier", "sourcify", "--watch", "--retries", "2", "--delay", "5", "--rpc-url", url]
    if target.get("creationTxHash"):
        args += ["--creation-transaction-hash", target["creationTxHash"]]
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR") if k in os.environ}
    env["FOUNDRY_PROFILE"] = "default"
    try:
        proc = subprocess.run(args + [target["address"], target["contract"]], cwd=source,
                              env=env, capture_output=True, text=True, timeout=300)
        output = proc.stdout + proc.stderr
        failed = proc.returncode != 0
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"")
        output = output.decode(errors="replace") if isinstance(output, bytes) else output
        failed = True
    ids = re.findall(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", output)
    result = {"jobId": ids[-1], "jobCompleted": False} if ids else {}
    if failed:
        result["submissionError"] = clean_external(output.replace(url, "[RPC]"))
    return result


JOB_FIELDS = ("jobId", "jobUrl", "jobCompleted", "jobError", "externalVerifications",
              "jobLookupError", "jobMissingSince", "jobMissingCount")


def refresh_job(record, now):
    """Job diagnostics cannot override the authoritative contract match result."""
    if not record.get("jobId") or record.get("jobCompleted"):
        return
    try:
        record.update(job_status(record["jobId"]))
        for field in ("jobLookupError", "jobMissingSince", "jobMissingCount"):
            record.pop(field, None)
    except Exception as error:
        record["jobLookupError"] = clean_external(str(error))
        if isinstance(error, urllib.error.HTTPError) and error.code == 404:
            record.setdefault("jobMissingSince", now)
            record["jobMissingCount"] = record.get("jobMissingCount", 0) + 1
            # Only repeated authoritative absence permits replacing an expired job.
            # 429/5xx/network outages never authorize a duplicate submission.
            if (record["status"] != "verified" and record["jobMissingCount"] >= 3
                    and now - record["jobMissingSince"] >= 600):
                record["expiredJobId"] = record["jobId"]
                for field in JOB_FIELDS:
                    record.pop(field, None)
        else:
            record.pop("jobMissingSince", None)
            record.pop("jobMissingCount", None)


def backoff(count):
    """Seconds before the next try after `count` attempts or failures: 60, 120, 240, ... at most a day."""
    return min(86400, 60 * 2 ** min(max(1, count) - 1, 11))


def forget_unmatched_creation_tx(record, now):
    """A creation transaction that was submitted and still gave no creation match is dropped, so that it is read
    from the chain again: no sooner than CREATION_LOOKUP_RETRY later, and once per submission."""
    if (record.get("status") == "runtime_only" and record.get("jobCompleted")
            and record.get("submittedCreationTxHash")):
        record.pop("creationTxHash", None)
        record.pop("submittedCreationTxHash")
        record["creationTxLookupFailedAt"] = now


def process_target(target, previous, *, now, publish, source, url, tracked, checked):
    record = {**previous, **target, "checkedAt": now}
    if record.get("creationTxHash"):
        record.pop("creationTxLookupFailedAt", None)
    # The contract API is authoritative; job lifecycle and forwarding are separate.
    try:
        status = sourcify_status(target["address"])
        record.update(status)
        record.pop("error", None)
        refresh_job(record, now)
        forget_unmatched_creation_tx(record, now)
        if status["status"] == "verified":
            record.update(attempts=0, nextAttemptAt=0)
            record.pop("failures", None)
            return record
        if record.get("jobId") and not record.get("jobCompleted"):
            record["status"] = "pending"
            # Poll the running job on the backoff, not on every pass.
            record["nextAttemptAt"] = now + backoff(record.get("attempts", 0))
            return record
        if not publish or now < previous.get("nextAttemptAt", 0):
            return record
        if target["contract"] not in checked:
            validate_input(source, target["contract"], tracked)
            checked.add(target["contract"])
        record["attempts"] = previous.get("attempts", 0) + 1
        record["submittedAt"] = now
        # A new attempt must never inherit a completed/expired previous job's ID.
        for field in (*JOB_FIELDS, "submissionError", "submittedCreationTxHash"):
            record.pop(field, None)
        record.update(submit(source, url, target))
        if target.get("creationTxHash"):
            record["submittedCreationTxHash"] = target["creationTxHash"]
        # Exit code 0 is NOT enough. A queued/partial submission stays pending.
        record.update(sourcify_status(target["address"]))
        refresh_job(record, now)
        forget_unmatched_creation_tx(record, now)
        record.pop("failures", None)
        if record["status"] == "unverified":
            record["status"] = "pending"
        if record["status"] == "verified":
            record.update(attempts=0, nextAttemptAt=0)
            return record
    except Exception as error:
        record["status"] = "error"
        record["error"] = str(error).replace(url, "[RPC]")[-2000:]
        if isinstance(error, UnexpectedMatch):
            record.update(runtimeMatch=None, creationMatch=None)
        # Counted here, since an error before the submission never reaches `attempts += 1`.
        record["failures"] = previous.get("failures", 0) + 1
        record["nextAttemptAt"] = now + backoff(max(record.get("attempts", 0), record["failures"]))
        return record
    record["nextAttemptAt"] = now + backoff(record.get("attempts", 0))
    return record


def once(args, report=True, tick=lambda: None):
    source = args.source.resolve() if args.source else None
    tracked = validate_source(source, args.revision) if args.submit else set()
    manifest = load_manifest(args.manifest, args.factory, args.revision)
    binding = {"chainId": CHAIN, "factory": args.factory, "sourceRevision": args.revision}
    state = json.loads(args.state.read_text()) if args.state.exists() else {**binding, "contracts": {}}
    if any(state.get(key) != value for key, value in binding.items()):
        raise ValueError("State belongs to another factory, chain or source revision")
    snapshot, found = discover(args.rpc_url, args.factory, args.confirmations,
                               state.get("snapshot", {}).get("strategyCount"))
    found = attach_creation_txs(args.rpc_url, args.factory, found, state["contracts"], snapshot["number"],
                                now=int(time.time()))
    targets = merge_targets(found, manifest)
    state["snapshot"] = snapshot
    # Rebuild scope from this snapshot, not arbitrary addresses persisted in a state file.
    state["contracts"] = {t["address"]: state["contracts"].get(t["address"], {}) for t in targets}
    # Check every target's code now, while the snapshot is seconds old. Submissions take minutes each, and a
    # public RPC treats a block that old as archive state and refuses it, so checking between submissions
    # failed partway through a pass.
    for target in targets:
        if rpc(args.rpc_url, "eth_getCode", [target["address"], snapshot["number"]]) == "0x":
            raise ValueError(f"Target has no deployed code: {target['address']}")
    checked = set()
    for target in targets:
        addr = target["address"]
        state["contracts"][addr] = process_target(target, state["contracts"][addr], now=int(time.time()),
            publish=args.submit, source=source, url=args.rpc_url, tracked=tracked, checked=checked)
        save(args.state, state)
        tick()                              # a pass can take many minutes; show the loop is still alive
    save(args.state, state)
    if report:
        print(json.dumps({"publicationEnabled": args.submit, **state}, indent=2))
    return 1 if any(r["status"] == "error" for r in state["contracts"].values()) else 0


def latest_strategy_count(url, factory):
    """The factory's strategy count at the tip: one call, cheap enough to ask every few seconds."""
    return int(rpc(url, "eth_call", [{"to": factory, "data": calldata("strategyCount()")}, "latest"]), 16)


def pass_reason(state, latest_count, now, last_pass, full_every, retry_floor, last_attempt=None):
    """Why a verification pass should run now, or None. A pass rechecks every contract, so it is not free.

    `last_pass` is when the last pass completed; `last_attempt` when the last one started, completed or not.
    No two passes start closer together than the retry floor, whatever the reason, so a flapping strategy
    count or a pass that keeps failing cannot run passes back to back.
    """
    last_attempt = last_pass if last_attempt is None else last_attempt
    if now - last_attempt < retry_floor:
        return None
    if not state or "snapshot" not in state:
        return "first pass"
    # A launch past the last snapshot. Discovery lags the tip by the confirmation buffer, so this stays true
    # (and a pass runs again, after the floor) until the snapshot has caught up with the new strategy.
    if latest_count != state["snapshot"].get("strategyCount"):
        return "new launch"
    if now - last_pass >= full_every:
        return "periodic recheck"
    if any(record.get("status") != "verified" and record.get("nextAttemptAt", 0) <= now
           for record in state.get("contracts", {}).values()):
        return "retry due"
    return None


def summary(state):
    counts = {}
    for record in state.get("contracts", {}).values():
        counts[record.get("status", "unknown")] = counts.get(record.get("status", "unknown"), 0) + 1
    return {"snapshot": state.get("snapshot"), "status": counts}


def watch(args, sleep=time.sleep, clock=time.time, passes=None):
    """Run forever: a pass on a new launch, when a retry falls due, and at least every --full-every seconds.

    One pass holds the state lock; between passes only the strategy count is read. A failed pass is logged
    and retried after the retry floor, never fatal: this is a service loop, and the state file already records
    what failed and when to try again. A failed strategy-count read only skips that tick. The heartbeat file
    is written on every tick, whatever happened, and after each contract within a pass: it shows the loop is
    alive, not that the chain or Sourcify is reachable (the logs and state say that).
    """
    last_pass = float("-inf")               # the last pass that completed
    last_attempt = float("-inf")            # the last pass started, completed or failed
    heartbeat = args.state.with_suffix(".heartbeat")
    def beat():
        heartbeat.parent.mkdir(parents=True, exist_ok=True)
        heartbeat.write_text(str(int(clock())))
    def redact(error):
        return str(error).replace(args.rpc_url, "[RPC]")
    while passes is None or passes > 0:
        try:
            state = json.loads(args.state.read_text()) if args.state.exists() else None
            now = clock()
            reason = pass_reason(state, latest_strategy_count(args.rpc_url, args.factory), now, last_pass,
                                 args.full_every, args.retry_floor, last_attempt)
        except Exception as error:
            print(f"Tick skipped, no pass attempted: {redact(error)}", file=sys.stderr, flush=True)
            reason = None
        if reason:
            last_attempt = now
            try:
                with locked(args.state):
                    code = once(args, report=False, tick=beat)
                last_pass = clock()
                print(json.dumps({"pass": reason, "exit": code, **summary(json.loads(args.state.read_text()))}), flush=True)
            except Exception as error:
                print(f"Verification pass failed: {redact(error)}", file=sys.stderr, flush=True)
            if passes is not None:
                passes -= 1
        try:
            beat()
        except OSError as error:
            print(f"Heartbeat not written: {error}", file=sys.stderr, flush=True)
        if passes is None or passes > 0:
            sleep(args.watch)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC)
    parser.add_argument("--factory", type=address, default=FACTORY)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source", type=Path, help="Clean, separate deployment-source checkout; required for --submit")
    parser.add_argument("--revision", default=REVISION, help="Full deployment commit hash")
    parser.add_argument("--manifest", type=Path, help="Explicit operator-owned additional addresses / creation tx hashes")
    parser.add_argument("--confirmations", type=int, default=12)
    parser.add_argument("--submit", action="store_true", help="Publish compiler inputs to Sourcify (no chain transaction)")
    parser.add_argument("--watch", type=int, default=0, help="Seconds between strategy-count checks; 0 runs one pass")
    parser.add_argument("--full-every", type=int, default=3600, help="With --watch: recheck everything at least this often")
    parser.add_argument("--retry-floor", type=int, default=120, help="With --watch: minimum seconds between retry passes")
    args = parser.parse_args()
    if args.confirmations < 0 or (args.submit and not args.source):
        parser.error("Nonnegative confirmations and --source with --submit are required")
    if args.watch < 0 or args.full_every <= 0 or args.retry_floor < 0:
        parser.error("--watch, --full-every and --retry-floor must be nonnegative (--full-every positive)")
    if args.watch:
        return watch(args)
    try:
        with locked(args.state):
            return once(args)
    except Exception as error:
        print(f"Verification stopped: {str(error).replace(args.rpc_url, '[RPC]')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
