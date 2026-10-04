#!/usr/bin/env bash
# Run the round-1 external-audit proofs of concept.
#
# They live outside `test/` on purpose. Four of the six inherit the repository's own test harnesses
# (`InteractFactoryTest`, `TreasuryV4Base`, `HookTaxBase`) to get a real Uniswap V4 PoolManager, real feeds
# and a real launch without duplicating 200 lines of setup. Solidity inheritance would make every inherited
# test run a second time under the PoC's own contract name, so keeping these files in `test/` permanently
# would double part of the suite. This script stages them, runs only the PoCs, and removes them again.
#
#   ./audit/round-1-2026-09-21/poc/run.sh
#
# Expected: 18 passing, 0 failing, across 7 suites.
#
# NOTE, and it is itself a finding of this round (see ISSUES.md, the path-dependence finding): this
# repository's compiled bytecode embeds a solc metadata hash derived from the source paths, so CREATE2
# addresses -- and therefore some of the repository's OWN brute-force ordering searches -- differ between
# checkouts at different absolute paths. These PoCs do not depend on those searches, but the surrounding
# suite may be red at your path for that reason. Setting `bytecode_hash = "none"` in foundry.toml fixes it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
cleanup() { for f in "$here"/ZZLead*.t.sol; do rm -f "$root/test/$(basename "$f")"; done; }
trap cleanup EXIT
cp "$here"/ZZLead*.t.sol "$root/test/"
cd "$root"
forge test --match-test 'test_lead_' -vv
