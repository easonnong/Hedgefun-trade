#!/usr/bin/env bash
# Round-4 external audit, delta lane: proofs of concept for audit/round-4-2026-09-27/lanes/delta.md.
#
#   ./audit/round-4-2026-09-27/poc/delta/run.sh
#
# Expected: 13 passing, 0 failing, across 4 suites. No network, no RPC, no environment variables.
# Same staging pattern as round 3's poc/run.sh: the files inherit `test/utils/V2FactoryFixture.sol`, so they
# are copied into test/, run alone, and removed again.
#
#   AuditDelta4Vault.t.sol    the M-1 fix: a refused stock fee is parked and delivered exactly once; the event
#                             stream sums to the credited stock; gas starvation cannot force a park; only the
#                             vault can drive the retry; a blocklisted vault still fails both legs (by design);
#                             the parked amount has no getter and no event (D-1).
#   AuditDelta4Spike.t.sol    the M-0 fix: spikeBps is frozen at 0 by the factory whatever the Defaults say; the
#                             one-wei buy-back arms nothing but still consumes the cooldown (D-2).
#   AuditDelta4Buyback.t.sol  the base change: a live buy-back refreshes the sizing cache; a closed-market one
#                             cannot; the writer is gated by tryPrice() and not health() (D-3).
#   AuditDelta4Kind1.t.sol    kind 1 is now opt-in production and its scorecard denominator is 0 for life (D-4,
#                             round 3's I-8 with its "registered by nobody" condition gone).
#
# Run from a checkout of the code under audit (origin/codex/v2-strategy-engine @ 5aedceb), not from the audit
# branch alone.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../../.." && pwd)"
cleanup() { for f in "$here"/AuditDelta4*.t.sol; do rm -f "$root/test/$(basename "$f")"; done; }
trap cleanup EXIT
cp "$here"/AuditDelta4*.t.sol "$root/test/"
cd "$root"
forge test --match-path 'test/AuditDelta4*.t.sol' -vv
