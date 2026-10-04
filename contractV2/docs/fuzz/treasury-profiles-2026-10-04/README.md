# Schema-3 treasury profile review and execution evidence

Candidate: `e9acecf693addcef5b180663bfdaa3988413e7fe`, stacked on #22 at
`7a2a626ba0c3ab24f3679c5fc49560e6080f2e03`. PR: [#26](https://github.com/0xHedgeHood/Hedgefun-trade/pull/26).
The follow-up evidence commit adds generated ABIs and documentation without changing the tested source.
Machine-readable results and SHA-256 identities are in [results.json](results.json).

## Review outcome

Three agents covered implementation and real-state execution, independent accounting/invariant tests,
and source/configuration-tool review. Root review reconciled the findings and ran the combined regression.
No confirmed unresolved P1/P2 was found in the implemented schema-3 profile. This bounded review does not
establish that the complete product or a future implementation is production-ready.

**Fixed during review:** checking a controller's `owner()` and `UPGRADE_DELAY()` getters alone does not prove
that it enforces that authority or delay. The registration guard and configuration adapter now reconstruct
the complete reviewed factory, graduation module, registry and controller runtimes with every immutable
binding. Both Solidity and Python negative tests reject a forged controller with matching getters. Unknown
compiler/runtime templates fail closed and require a separate compatibility review.

Accounting review covers cash-based buy limits, inventory-based sell limits, dynamic tradable-asset daily
limits, reserved buyback stock and LP exclusion, actual partial fills, keeper rewards, donations, adversarial
policy outputs, same-date turnover, delayed upgrades and migration rollback. The independent handler records
its own transfer/cost/nonce history. Early handler-only issues (prank consumption and missing conditional
braces around ghost date rollover) were corrected before the final three seeded runs; they were not findings
against production code. The archived logs here are the final passing campaigns.

## Completed validation

| Check | Result |
|---|---|
| Full offline suite | 1,073 passed, 0 failed, 44 opt-in skips; 121 suites |
| Python suites | 93 + 70 passed, including 17 new profile/identity tests |
| Combined fuzz/invariants | 121 passed per seed × 3 seeds; zero failures/skips |
| Combined fuzz volume | 55,296 cases across 18 fuzz properties × 1,024 runs × 3 seeds |
| Combined invariant volume | 983,040 calls across 5 properties × 512 runs × 128 depth × 3 seeds; zero handler reverts |
| Separate independent campaign | 13 passed per seed; 9,216 fuzz cases and 393,216 invariant calls; zero failures/skips/reverts |
| Real-state fork | Chain 46630, block 128847511: 23 passed, 0 failed/skipped |
| Local CLI E2E | Anvil chain 31337, fork 128845166: 5 registration transactions and 1 selection transaction passed |
| Build / ABI | Sizes pass; three new ABIs exported; existing contract ABIs unchanged |

The independent campaign repeats a subset of the combined campaign; its counts are separate, not additional
unique properties. Offline opt-in skips are not counted as fork coverage. The targeted fork above exercises
the relevant income, compatibility and upgrade scenarios; unrelated opt-in forks were not run locally here.

The schema-3 fork registers, launches, graduates, executes, waits through the upgrade delay, upgrades and
executes again on the deployed venue. Actual strategy turnovers were 3,639.306440 and 5,894.125386 tUSDG.
It checks 96 storage slots, custody, supply, old kind manifests/chunks and both LP positions. CLI E2E verifies
the live code identities, simulates selection without writing, then sends only to localhost and compares all
six configuration words and the selected kind. No private keys were used, no public transactions were sent,
and the dedicated Anvil process was stopped. Local E2E manifest hashes are fixture labels, not release sign-off.

## Reproduction

From `contractV2/`, use the pinned submodules, Foundry 1.5.0 and Solc 0.8.26:

```sh
forge build --sizes
forge test --offline
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s tools/tests -p 'test_*.py'
python3 tools/export_abi.py

for seed in 0x2026100401 0x2026100402 0x2026100403; do
  FOUNDRY_FUZZ_RUNS=1024 FOUNDRY_INVARIANT_RUNS=512 \
  FOUNDRY_INVARIANT_DEPTH=128 FOUNDRY_INVARIANT_FAIL_ON_REVERT=true \
  forge test --offline --fuzz-seed "$seed" --mc '^V2IncomeGraduation.*Test$|^V2StakingIncomeInvariantTest$|^V2StakingAllocationRegressionTest$|^V2StakingRemainderBoundaryTest$|^V2IncomeGasRegressionTest$|^V2BuybackTreasuryUpgradeTest$|^V2EngineTreasuryUpgradeTest$|^V2EngineTreasuryUpgradeInvariantTest$|^V2UpgradeableKindRegistrationTest$|^V2TradablePercent.*Test$' -vv || exit 1
done

# Compile first, then choose a fresh block: public testnet state is pruned.
export INCOME_KINDS_FORK=true INCOME_COMPAT_FORK=true
export UPGRADEABLE_KINDS_FORK=true TRADABLE_PERCENT_FORK=true
export INCOME_KINDS_FORK_BLOCK=$(cast block-number --rpc-url https://rpc.testnet.chain.robinhood.com)
export INCOME_COMPAT_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
export UPGRADEABLE_KINDS_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
export TRADABLE_PERCENT_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
forge test --threads 1 --mc '^TestnetV2IncomeKindsForkTest$|^TestnetV2IncomeCompatibilityForkTest$|^TestnetV2TreasuryUpgradeForkTest$|^TestnetV2TradablePercentForkTest$' -vv
```

Exact local CLI commands and readbacks are in [cli/commands.log](cli/commands.log); the summary is in
[cli/summary.json](cli/summary.json). Its broadcast flags point only to the dedicated localhost Anvil.
The combined campaigns use the same selectors and required suites as the updated CI workflow. GitHub CI
status remains separate from this locally captured evidence.

## Limits and release follow-ups

- Only **Strategy / Rebalance / Continuous** is implemented by the new profile. Price single/cycle lifecycle,
  recovery-after-profit integration, percentage buyback and frontend profile/E2E remain outstanding.
- There is no pending-dividend cash liability ledger in schema 3. All USDG cash is currently tradable;
  a dividend successor must introduce and audit liability accounting before reusing that basis.
- Logic runtime is 24,146 bytes (430 bytes headroom). The migration test logic retaining execution is
  24,419 bytes. Creation-code sizes in the build table omit arguments; separate tests include full arguments.
  Future strategy/dividend growth needs a reviewed module and storage design.
- Owner-scheduled upgrades remain a governance trust boundary even with the 48-hour delay. The configuration
  identity hash does not prove that a future implementation preserves storage or accounting.
- Old pools, kinds and schema 1/2 semantics remain unchanged. No public registration, deployment or upgrade
  was performed. #22's optional immutable income implementations are not dividend successors for this proxy.
