> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Automatic source verification

`tools/verify_contracts.py` discovers every Token and Treasury from the configured
factory's `strategyCount()` / `strategies(index)` at one confirmed block. It then
checks Sourcify. With `--submit`, it publishes the selected contract's compiler
input and dependencies. It has no signing code, sends no transactions and needs no
wallet, keystore, private key or explorer API key.

Source verification is publication of deployed Solidity source, **not publication
of the repository**, and not a security audit. A Sourcify match does not imply a
Blockscout/RobinScan match or a green GoPlus / DexScreener result.

## Production verification status: September 24, 2026

The service tracks 18 strategy contracts (each strategy's Token and Treasury). In
Sourcify, 14 have full matches (creation and runtime) and 4 match runtime only.
All four belong to strategies 1, 3 and 4, which were launched with a developer buy
or seed in the same transaction as the launch; Sourcify returns no creation match
for them even when given that creation transaction hash. Runtime-only is recorded
as such, never as verified, and the service keeps retrying on its backoff.

## Production verification snapshot: September 22, 2026 (dated)

This is the state on September 22 and is kept as a dated record; see the September
24 status above for the present one. On September 22, all 21 then-inventoried
HedgeFun production contracts had both creation and runtime matches in Sourcify.
RobinScan displayed 11 Exact Matches and 10 Similar Matches: the latter reuse
matching source and are not individual exact verifications.
CRCLGRID Token, Treasury, Factory and TokenDeployer have Exact Matches. The token's
Sourcify forwarding attempt hit Etherscan's rate limit; direct standard JSON
submission to RobinScan succeeded, as did the missing Factory/TokenDeployer entries.

GoPlus still returned `is_open_source=0` after token verification. These are
separate provider states, not a failed Solidity match; its indexing source and
refresh timing are not established. This dated snapshot does not promise the
status of future launches. Public source links:

- [CRCLGRID Token](https://robin.etherscan.io/address/0xF5501c0D85992dD59371e15e3e7b60654ebaF332#code)
- [Factory](https://robin.etherscan.io/address/0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961#code)
- [TokenDeployer](https://robin.etherscan.io/address/0x9C0440dCc1b651C4707aa44E0eA083Fa4E0E8A6b#code)

## Prepare the deployment source once

Use a separate, clean checkout of the actual deployment commit, including its
pinned submodules. Keep service code and deployment source in different checkouts.
For the September 22 production deployment:

```sh
git worktree add --detach /srv/hedgefun-source-3dc07eb 3dc07eb83212d5fac4abeb9b5606c8accb9f254c
git -C /srv/hedgefun-source-3dc07eb submodule update --init --recursive
```

The tool refuses a different commit, dirty source/dependencies, uninitialized or
mismatched submodules, and a root `.env`. It generates the selected target's
standard JSON input locally before publication and permits only tracked `.sol`
files under `src/` and `lib/`, with contents matching the checkout. Credentials and
unrelated files must never be added to that checkout. It does not inherit shell
`FOUNDRY_*`, RPC or private-key overrides. Do not modify the checkout while a run is
in progress. Do not use the live production checkout as the source workspace.

## Inspect first, publish explicitly

From the service checkout:

```sh
python3 tools/verify_contracts.py --state /var/lib/hedgefun-verifier/state.json
python3 tools/verify_contracts.py --state /var/lib/hedgefun-verifier/state.json \
  --source /srv/hedgefun-source-3dc07eb --submit
```

The first command only reads chain/API data and writes the local status file. The
second authorizes Solidity source publication to Sourcify and its downstream
explorer integrations. Submission uses `forge verify-contract --verifier sourcify
--watch`; `--chain 4663` selects Robinhood mainnet. Source publication itself costs
no chain gas. Requires Python 3.10+, Git, `cast` and `forge`, on macOS/Linux.

The default factory is `0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961` and reads use
the chain's own public RPC (`rpc.mainnet.chain.robinhood.com`, no key). PublicNode refuses the historical
state and wide log queries this needs from a cloud host. Each strategy's creation transaction is read once from
the factory's `Launched` log and passed to Sourcify: without it Sourcify matches a factory child's runtime code
only. The log must come from the factory address, carry the `Launched` topic and the strategy's id, not be
`removed`, and name the discovered token and treasury. A failed lookup scans the factory's logs from its
deployment block, so it is retried at most hourly per strategy (the failure time is kept in state as
`creationTxLookupFailedAt`). A remembered hash that was submitted and still gave no creation match (the job
completed, the contract is runtime-only) is dropped once, so it is read from the chain again, under the same
hourly limit. `strategyCount()` is bounded: a snapshot may add at most 1000 strategies over the previous one,
and a first snapshot may have at most 100000; anything more is refused. `--confirmations 12` pins a snapshot twelve blocks behind the
tip. That is a confirmation buffer, not a claim of consensus finality. The tool
checks the chain ID and rejects reorganization during discovery. Each run rescans
all strategy indices, so restarts catch existing and newly created strategies
without depending on an event subscription staying connected.

## Run it as a service

`--watch SECONDS` keeps the tool running. Between passes it reads only the factory's `strategyCount()` at the
tip. A pass runs on the first tick, whenever that count differs from the last snapshot's, when a recorded
retry falls due, and at least every `--full-every` seconds (default 3600). Whatever the reason, no pass starts
within `--retry-floor` (default 120 s) of the previous one, completed or failed, so a flapping count or a
failing pass cannot run passes back to back; a launch after a quiet spell still gets a pass on the next tick.
A launch inside the confirmation buffer keeps triggering passes, one per floor, until the snapshot includes it,
so a new strategy is published within a few minutes of landing. A failed pass is logged and retried after the
retry floor; it never stops the loop. A failed `strategyCount()` read only skips that tick: no pass, and the
time of the last pass is left alone, so it does not force a full recheck.

Each tick writes `state.heartbeat` next to the state file, whatever happened in it: between passes, after each
contract within a pass, after a failed pass and after a failed count read. The container is healthy while the
heartbeat is under fifteen minutes old (one submission is bounded at five). That is liveness only: an
unreachable RPC or Sourcify keeps the container healthy and shows in the logs and in the state file's errors.

`tools/verifier/` packages this for the API host, beside the indexer:

```sh
tools/verifier/build-context.sh "" /tmp/verifier      # tool + Dockerfile + a clean clone of the deployment revision
rsync -a /tmp/verifier/ ubuntu@<api-host>:hedgefun-verifier/
ssh ubuntu@<api-host> 'cd hedgefun-verifier && docker compose up -d --build'
ssh ubuntu@<api-host> 'docker logs --tail 20 hedgefun-verifier-verifier-1'
```

The image bakes in the deployment source, compiled at build time; its own build refuses a dirty checkout. It
needs no key, token or `.env`, publishes no ports, and keeps state in a named volume. After a factory upgrade,
rebuild with the new revision (`build-context.sh <revision>`) and a new state volume, since state is bound to
one source revision.

Hardening:

- Supply chain. The base image is pinned by digest (`python:3.12-slim@sha256:...`, a multi-arch index), and
  the Foundry v1.5.0 tarball is checked against its sha256 for amd64 or arm64 before it is extracted.
  `build-context.sh` fetches only the deployment commit and its history into a fresh repository (no branches,
  tags or remotes), so unpushed local branches never reach the image; submodules are cloned at their pinned
  commits.
- Filesystem. `/source` and `/app` are owned by root and read-only to the `verifier` user; only
  `/source/out` and `/source/cache` belong to it. The build compiles as root, then checks as `verifier` that
  the tool's source checks and compiler-input generation pass with even `out/` and `cache/` read-only: with the
  warm build cache, `forge verify-contract` writes nothing under `/source` (checked with Forge 1.5.0; a cold
  cache it would try to rewrite, and the check would fail). Git is told `/source` and its submodules are safe
  directories, since they belong to another user.
- Compiler. Forge 1.5 keeps solc in `$HOME/.svm` with no setting to move it, so the build installs it in
  `/home/verifier/.svm`, owned by root. HOME therefore stays in the image rather than on a tmpfs.
- Runtime (`docker-compose.yml`). `read_only: true`, with tmpfs only for `/tmp` and forge's scratch directory
  `/home/verifier/.foundry`; the state volume is the only persistent writable path. `cap_drop: [ALL]`,
  `no-new-privileges`, `pids_limit: 256`, 1 GB of memory and half a CPU.

## Optional explicit infrastructure manifest

A local operator-reviewed manifest can add self-owned deployed infrastructure or
provide creation transaction hashes for discovered children. It is never fetched
from an external token list. The service does **not** infer that any arbitrary
manifest address belongs to the team: listing it explicitly is the operator's
scope declaration. Do not include third-party pools, stock tokens or protocols.

```json
{
  "chainId": 4663,
  "factory": "0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961",
  "sourceRevision": "3dc07eb83212d5fac4abeb9b5606c8accb9f254c",
  "contracts": [
    {
      "address": "0x58F6Ced8d02cD2567f1458801440Bc4eb67fA961",
      "contract": "src/HedgeFunFactory.sol:HedgeFunFactory"
    }
  ]
}
```

Pass `--manifest /etc/hedgefun-verifier/production.json`. Each row may also have a
`creationTxHash` (a full `0x` transaction hash), passed to Sourcify for deployments
requiring creation-transaction lookup. Factory children need one: Sourcify does not
find a child's creation on its own, and without the hash it matches runtime code
only. The service reads it from the factory's `Launched` log itself (see above), so a
manifest hash is needed only for other deployments. Constructor arguments are **not** reconstructed
from mutable factory defaults: Sourcify resolves creation data and compares code.
An inability to obtain that data remains unverified/runtime-only, never success.

## Durable status and retries

The JSON report records snapshot height/hash, per-address runtime/creation match,
check/submission time, attempt count, next attempt, and any error. States:

- `verified`: both Sourcify runtime and creation are `match` or `exact_match`.
- `runtime_only`: creation has not been matched.
- `unverified`: Sourcify returned 404 or an explicit non-match.
- `pending`: submission has not produced both matches, or a recorded job is running.
- `error`: RPC/API/compiler/other operation failed; **not** evidence of verification.

A successful Forge exit never sets `verified` on its own. The contract API must
confirm both matches. HTTP errors other than 404 and malformed responses are
errors. Existing verified contracts are rechecked. After a submission that did not
produce both matches, the next one waits 60 s, then 120, 240 and so on, doubling
per `attempts` up to one day; a verified match resets it. An error (RPC, Sourcify,
compiler input or submission) counts in `failures`, which backs off the same way
whether or not a submission was reached, and resets when a submission runs without error or
the contract is verified; the wait is set by the larger of the two counts. A
running recorded job is polled on the same backoff, without resubmission. The authoritative contract status is checked before job
diagnostics; an expired or unavailable job endpoint cannot hide a verified match.
Completed job records need no further polling. A missing pending job is eligible
for replacement only after three consecutive HTTP 404 checks spanning at least
ten minutes and a fresh contract API check still showing no complete match.
HTTP 429/5xx or network failures retain the pending job and never authorize a
duplicate submission. Writes use an atomic rename, and an exclusive lock prevents
concurrent instances using the same state. Use exactly one state path per factory
and deployment revision. Do not run separate state files for the same deployment.

Forge's Sourcify job ID is retained, when returned, and its job endpoint reports
`externalVerifications` independently. An Etherscan GUID indicates a downstream
request, **not explorer verification success**. Blockscout 403s, forwarding rate
limits and other errors are recorded with HTML stripped and text bounded. A
Sourcify `already_verified` job error is resolved by reading the contract API;
it does not erase a valid source match. Re-submitting an already verified source
does not reliably re-run explorer forwarding. Resolve failed explorer submission
through that explorer's supported verification API/UI, then check GoPlus
separately. This tool does not promise or implement downstream green badges.

If the process is killed after a remote request but before its job ID is returned
and persisted, a later run first checks the contract API and may retry submission.
The same applies to the attempt count: `attempts` is saved with the record after the
submission returns, not before it, so a submission interrupted mid-flight does not
count towards the backoff.
Sourcify can return `already_verified`; publication is not a financial transaction.
A running job with no completion remains pending: inspect its saved URL rather
than deleting state to force duplicate requests.

## Optional timer (operator installation)

No daemon or schedule is installed by the script. A systemd oneshot plus timer can
run it every five minutes. Example service at
`/etc/systemd/system/hedgefun-verifier.service`:

```ini
[Unit]
Description=HedgeFun contract source verification
After=network-online.target

[Service]
Type=oneshot
User=hedgefun-verifier
WorkingDirectory=/srv/hedgefun-verification-service
Environment=PATH=/usr/local/bin:/usr/bin:/bin:/home/hedgefun-verifier/.foundry/bin
ExecStart=/usr/bin/python3 tools/verify_contracts.py --state /var/lib/hedgefun-verifier/state.json --source /srv/hedgefun-source-3dc07eb --submit
TimeoutStartSec=30min
```

Matching timer:

```ini
[Unit]
Description=Check new HedgeFun strategies every five minutes

[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
Unit=hedgefun-verifier.service

[Install]
WantedBy=timers.target
```

Provision the unprivileged user's writable state/cache directories and read access
to source; Forge may need to populate source build output/cache. Install/enable
only after reviewing the first dry-run and explicit publication. A newly deployed
factory/compiler revision needs its own pinned source and state, not a silent
switch of this configuration. For large deployment counts, staggered API reads
or an index cursor can be added after measuring provider limits.

## Checks

```sh
python3 -m unittest discover -s tests -v
```

Tests cover pinned discovery and reorg rejection, the `strategyCount()` bound,
clean deployment revision, read-only RPC allowlist and its retries (HTTP, JSON-RPC
rate limits, dropped connections), response size caps, compiler input publication
boundaries, the Sourcify match allowlist and bounded external text, durable
retry/lock, the attempt and failure backoffs, API failure vs unverified, pending job
resume and polling, creation transaction checks and their hourly retry, the watch
loop's floor, skipped ticks and heartbeat, and a successful submission that has not
completed verification. Tests do not contact a network or publish source.
