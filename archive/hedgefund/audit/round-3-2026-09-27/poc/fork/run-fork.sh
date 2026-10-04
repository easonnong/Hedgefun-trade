#!/usr/bin/env bash
# Round-3 chain-state measurements for M-2 (raise size vs venue depth) and M-3 (a curve that can never
# graduate). These are MEASUREMENT PROBES, not pass/fail tests: their emitted tables are the evidence, and
# every number in them is live pool state that moves between runs. They assert only on what is
# deterministic -- that each listing resolves, that its pool is the stock/USDG pair, that the graduation
# requirement is non-zero -- and report the rest.
#
#   ./audit/round-3-2026-09-27/poc/fork/run-fork.sh [rpc-url]
#
# Default RPC: Robinhood Chain's public endpoint. It is NOT an archive node -- state roughly 24k blocks
# back is already gone -- so the fork cannot be pinned to the block the report quotes, and a re-run reads
# a later chain. That is why ISSUES.md dates each figure in place: INTC's graduation shortfall read 104.1%,
# 115.9% and 126.1% of pool inventory at three points on 2026-09-27 alone, widening each time.
#
# All18 walks all 18 live listings and takes about 7 minutes. Expected: 5 passing, 0 failing.
#
# These four read only live chain state and need no `src/v2`, so they run from any checkout of this repo.
#
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../../.." && pwd)"
rpc="${1:-https://rpc.mainnet.chain.robinhood.com}"
cleanup() { for f in "$here"/*.t.sol; do rm -f "$root/test/$(basename "$f")"; done; }
trap cleanup EXIT
cp "$here"/*.t.sol "$root/test/"
cd "$root"
forge test --fork-url "$rpc" --match-path 'test/{All18,Rest7,Depth,Grad,Grad2}.t.sol' -vv
