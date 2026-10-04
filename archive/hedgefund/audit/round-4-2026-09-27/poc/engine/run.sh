#!/usr/bin/env bash
# Run the round-4 engine-lane proofs of concept.
#
#   ./audit/round-4-2026-09-27/poc/engine/run.sh
#
# No network, no RPC, no environment variables. The files live outside `test/` for the reason round 3 gave: they
# inherit the repository's own V2FactoryFixture, and leaving them in `test/` permanently would re-run part of the
# suite under the PoC contract names. This script stages them, runs only the PoCs, and removes them again.
#
#   AuditEngineFixture.sol       shared setup: V2FactoryFixture + a flat-price V3 venue in either token order
#   AuditEngineConfig.t.sol      E-1 inert maxTrade, E-2 deadband churn, E-3 no bounty, E-4 UTC epoch,
#                                E-6 opaque launch failure, E-8 writable launched-salt record
#   AuditEnginePolicy.t.sol      the policy boundary end to end; E-5 dead action check; E-7 mutable/proxy policies
#   AuditEngineCustody.t.sol     custody: only the swap moves assets, no allowances, re-entry refused, buyback
#                                bucket unreachable; USDG-as-token0 and 6-decimal stocks
#
# RUN IT FROM A CHECKOUT OF THE CODE UNDER AUDIT (origin/codex/v2-strategy-engine @ 5aedceb):
#   git checkout codex/v2-strategy-engine
#   git checkout <audit-branch> -- audit/
#   ./audit/round-4-2026-09-27/poc/engine/run.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../../.." && pwd)"
cleanup() { for f in "$here"/AuditEngine*.sol; do rm -f "$root/test/$(basename "$f")"; done; }
trap cleanup EXIT
for f in "$here"/AuditEngine*.sol; do
  # the PoCs import the repository by a path relative to their home directory; rewrite it for test/
  sed 's#\.\./\.\./\.\./\.\./#../#g' "$f" > "$root/test/$(basename "$f")"
done
cd "$root"
forge test --offline --match-path 'test/AuditEngine*.t.sol' -vv "$@"
