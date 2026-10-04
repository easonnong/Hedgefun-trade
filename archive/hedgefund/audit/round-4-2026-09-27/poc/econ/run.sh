#!/usr/bin/env bash
# Round-4 economics lane: the Foundry proofs of concept behind lanes/econ.md. No network, no RPC, no env.
#
#   ./audit/round-4-2026-09-27/poc/econ/run.sh
#
# Expected: 11 passing, 0 failing. Stages AuditEcon4.t.sol into test/ (it inherits the repository's own
# V2FactoryFixture: real PoolManager, real hook, real factory; only the stock/USDG venue and the feeds are mocks),
# runs only that file, removes it again. Run from a checkout of codex/v2-strategy-engine (audited at 5aedceb).
#
#   X-1  the sandwich, measured on a constant-liquidity V3 step: 30 bps tier (attacker loses, treasury pays
#        ~50 bps more), 5 bps tier (attacker paid), and the deviation gate binding at 50 bps
#   X-2  the UTC-day turnover cap: 2x the daily budget in ten minutes around 00:00 UTC
#   X-3  closure / oraclePaused fail closed even where kind 0's band path is open; a stale print inside
#        maxStockAge is traded on when the pool sits within the gate of it
#   X-4  the graduation lot is sold down to target in minutes, none of it reaching the burn
#   X-5  deadband 1 bp / cooldown 1 s / unbounded day are accepted; every 0.5% print is then an action
#   X-6  execute() pays no bounty
#   X-7  rebalance gains never fund a buy-back
#   X-8  a donation triggers a sell and costs the donor more than the sale could ever return
#   X-9  the creator-side setter validates no number; the constructor is the only floor
#
# The two Python scripts beside this file run on their own:
#   python3 sandwich_model.py     the manipulation-cost grid (depth x maxTrade x fee tier x gates)
#   python3 constant_mix.py       kind 2 against kind 0 on lab/trend.py's paths, 90 days
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../../.." && pwd)"
cleanup() { rm -f "$root/test/AuditEcon4.t.sol"; }
trap cleanup EXIT
cp "$here/AuditEcon4.t.sol" "$root/test/"
cd "$root"
forge test --offline --match-path 'test/AuditEcon4.t.sol' -vv "$@"
