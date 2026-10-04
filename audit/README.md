# Audit and verification index

Current development and review take place in `0xHedgeHood/Hedgefun-trade`. Identify the exact commit, deployment and strategy kind before applying any finding. Historical evidence from the development repository is available locally in the [Hedgefund archive](../archive/hedgefund/README.md).

## Current organization baseline

The migration is based on default-branch commit `9be8cf48a723f1ab65412505e231f98b8fac450e`, after Cycle integration, testnet replay and the supply-preserving treasury-upgrade change. Start with [contract scope](../docs/CONTRACT_SCOPE.md), [operations](../docs/OPERATIONS.md), [V2 architecture](../contractV2/docs/V2_BONDING_CURVE.md) and the [actor flow and fuzz map](../contractV2/docs/V2_ACTOR_FLOW_FUZZ_MAP.md).

| Review area | Evidence |
|---|---|
| V2 trading and callbacks | [Adversarial review](../contractV2/docs/V2_ADVERSARIAL_REVIEW.md), [testnet review](../contractV2/docs/V2_TESTNET_REVIEW.md) |
| Graduation allocation and locked liquidity | [Dual-engine review](../contractV2/docs/V2_DUAL_ENGINE_REVIEW.md), [current supply and upgrade design](../contractV2/docs/V2_BONDING_CURVE.md#treasury-upgrades-and-lp-isolation) |
| Optional Cycle and current dust handling | [Integration review](../contractV2/docs/V2_CYCLE_INTEGRATION_REVIEW.md) |
| NAV limits, execution costs and dust progress | [Fuzz supplement](../contractV2/docs/V2_FUZZ_SUPPLEMENT_REPORT.md) |
| Public testnet state and receipts | [Deployment handoff](../contractV2/docs/TESTNET_LAUNCH_HANDOFF_2026-10-03.md) |
| Default-treasury supply preservation and delayed upgrades | [Merged PR #25](https://github.com/0xHedgeHood/Hedgefun-trade/pull/25) |

These records distinguish source review, local tests, explicit fork checks and actual public deployment. Passing a replay or importing a report does not register a new kind or upgrade a deployed treasury.

## Historical audit record

The [internal audit history](../archive/hedgefund/AUDIT.md) and [external audit track](../archive/hedgefund/audit/README.md) retain the reviewed refs, findings, PoCs, mutation patches and verification notes. Rounds [1](../archive/hedgefund/audit/round-1-2026-09-21/README.md), [2](../archive/hedgefund/audit/round-2-2026-09-21/README.md), [3](../archive/hedgefund/audit/round-3-2026-09-27/README.md) and [4](../archive/hedgefund/audit/round-4-2026-09-27/README.md) are archived independently of later remediation. Use the [manifest](../archive/hedgefund/MANIFEST.json) to trace every imported file to its original source.

For current remediation, reproduce against the current organization checkout, identify the affected deployment, and check that a regression fails when its guard is removed. Keep runtime/initcode size, ABI and source-generated documentation checks with changes to production Solidity. Historical size margins and test totals are evidence of their original revisions.
