#!/usr/bin/env bash
# Run the round-4 claims-lane proofs of concept: the tests the mutation campaign showed to be missing.
#
#   ./audit/round-4-2026-09-27/poc/claims/run.sh
#
# Expected on the audited tip (codex/v2-strategy-engine @ 5aedceb): all AuditClaims4 tests pass. No network.
# The file is staged into test/ and removed again, because it inherits V2FactoryFixture and imports the
# repository's own test fixtures (EngineAccountingVenue, StrategyPolicyMocks), which only resolve from test/.
#
# To replay a mutation: apply one diff from mutations.md (or diffs/*.diff) with `git apply`, run this script
# and the V2 subset (`forge test --match-path 'test/V2*'`), then `git checkout -- src`.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../../.." && pwd)"
cleanup() { rm -f "$root/test/AuditClaims4.t.sol"; }
trap cleanup EXIT
cp "$here/AuditClaims4.t.sol" "$root/test/"
cd "$root"
forge test --match-path 'test/AuditClaims4.t.sol' -vv
