#!/usr/bin/env bash
# Run the round-3 external-audit proofs of concept.
#
#   ./audit/round-3-2026-09-27/poc/run.sh
#
# Expected: 32 passing, 0 failing, across 6 suites. No network, no RPC, no environment variables.
#
# They live outside `test/` on purpose. Five of the six inherit this repository's own `V2FactoryFixture`
# to get a real PoolManager, a real hook at a mined address, real feeds and a real launch without
# duplicating its setup. Solidity inheritance would make every inherited test run a second time under the
# PoC's own contract name, so keeping these files in `test/` permanently would duplicate part of the suite.
# This script stages them, runs only the PoCs, and removes them again.
#
# What each file is evidence for (see ISSUES.md):
#
#   AuditTriage3.t.sol    M-0  a 1-wei buyback pot arms the 90% sell spike, and re-arms every 240s
#   AuditTriage3b.t.sol   M-0  the same, end to end, driven by an unprivileged caller
#   AuditAdv3.t.sol       M-0  the adversarial pass's attempts to kill it -- including the two that worked:
#                              spikeBps = 0 removes the mechanism, and lpFee = 1 was claimed to starve the
#                              fuel line (it does not; that claim is published as a false positive, I-11)
#   AuditLane13V2.t.sol   the v2 surface: curve solvency under fuzz, vault principal cannot leave by any
#   AuditLane13V2b.t.sol  route, graduation's value split and delegatecall isolation, the last seller is
#                         always redeemable. The two files overlap -- they are two passes by the same lane,
#                         both shipped because both were run.
#   AuditV1Delta.t.sol    the ~55 changed lines in the already-deployed contracts: the v1 factory still
#                         refuses every non-zero lpFee, the v2 one accepts 1..3000, a pool cannot be
#                         registered twice nor through both paths, and the hook accepts any contract as
#                         the vault.
#
# Chain-state measurements for M-2 and M-3 are separate and need an RPC: see ./fork/run-fork.sh.
#
# RUN IT FROM A CHECKOUT OF THE CODE UNDER AUDIT, not from the audit branch. These PoCs exercise `src/v2`,
# which exists only on the PR branch:
#
#   git checkout codex/v2-main-integration   # audited at 03ad70e
#   git checkout <audit-branch> -- audit/     # bring this directory across
#   ./audit/round-3-2026-09-27/poc/run.sh
#
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
cleanup() { for f in "$here"/Audit*.t.sol; do rm -f "$root/test/$(basename "$f")"; done; }
trap cleanup EXIT
cp "$here"/Audit*.t.sol "$root/test/"
cd "$root"
forge test --match-path 'test/Audit{Triage3,Triage3b,Adv3,Lane13V2,Lane13V2b,V1Delta}*.t.sol' -vv
