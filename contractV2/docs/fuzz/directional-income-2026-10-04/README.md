# Directional quota / realized income evidence

**This evidence describes commit `f3aeaec`, not the tree it is merged into.** The merged tree also contains
`79cf822` (the schema-3 band floor became one trade's cost, `poolFeeBps + bountyBps`, where this candidate used
`2 * (maxSlippageBps + poolFeeBps + bountyBps)`), the percentage buy-back hook in `HedgeFunTreasuryBase`, and a
later change to the schema-3 minimum-size check. Five of the sources hashed in `results.json` differ there, and
the sizes below are this candidate's. The logs are kept as the record of what was run on this candidate; they
are not evidence for the merged code, which needs its own run.

Candidate source commit: `f3aeaec` (full hash and source SHA-256s in `results.json`). The commits after it on its
own branch export ABI and add this evidence/report; they do not change executable source. Foundry 1.5.0, solc 0.8.26, optimizer runs 1,
Cancun; repository foundry.toml settings unchanged. The code includes PR #28 hardening, PR #29 weekend sizing,
and the reviewed-registry identity patch from PR #30. None of the commands broadcasts a public transaction.

- `offline.log`: 1,115 passed, 0 failed, 46 opt-in skips (128 suites).
- `python-tests.log`, `python-tools.log`: 93 + 72 passed, Python 3.11+ and `cast` on PATH.
- `fork.log`: 25 passed, 0 failed/skipped, chain 46630 at block 128957524; real deployed registration/controller,
  graduation, trading, staking and upgrades, all mutations confined to the local fork.
- `seed-*.log`: 48 passed for each of 3 seeds; 1,024 fuzz runs, 512 invariant runs × 128 calls, fail-on-revert.
- `sizes.log`: successful build; schema-3 logic 24,072 bytes, migration fixture 24,354, registry initcode 49,116.
  Constructor tests also check initcode **including arguments** and both stored creation-code chunks.
- `abi-export.log`: ABI and selector surface regenerated from candidate source.
- `lp-comparison.log/json`: numerical production-V4 comparison extracted from the first final seeded run.
  Stock/USDG price is mocked; the curve, FUN pool, LP vault, router, fees and buybacks execute real contract code.

Run from `contractV2/`, with repository submodules/dependencies installed:

```sh
forge test
forge build --sizes
python3 -m unittest discover -s tests
python3 -m unittest discover -s tools/tests
python3 tools/export_abi.py

FOUNDRY_FUZZ_RUNS=1024 FOUNDRY_INVARIANT_RUNS=512 FOUNDRY_INVARIANT_DEPTH=128 \
FOUNDRY_INVARIANT_FAIL_ON_REVERT=true forge test --fuzz-seed 0x2026100401 \
  --mc '^V2TradablePercent.*Test$|^V2Directional.*Test$|^V2RealizedIncomeTest$|^V2UpgradeableKindRegistrationTest$' -vv
# Repeat with 0x2026100402 and 0x2026100403.

# Compile before selecting the block: the public node prunes historical state.
export INCOME_KINDS_FORK_BLOCK=$(cast block-number --rpc-url https://rpc.testnet.chain.robinhood.com)
export INCOME_COMPAT_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
export UPGRADEABLE_KINDS_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
export TRADABLE_PERCENT_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
export WEEKEND_BUYBACK_FORK_BLOCK="$INCOME_KINDS_FORK_BLOCK"
INCOME_KINDS_FORK=true INCOME_COMPAT_FORK=true UPGRADEABLE_KINDS_FORK=true \
TRADABLE_PERCENT_FORK=true WEEKEND_BUYBACK_FORK=true forge test --threads 1 \
  --mc '^TestnetV2IncomeKindsForkTest$|^TestnetV2IncomeCompatibilityForkTest$|^TestnetV2TreasuryUpgradeForkTest$|^TestnetV2TradablePercentForkTest$|^TestnetV2DirectionalBudgetForkTest$' -vv
```

The last suite intentionally shares the weekend test's fork fixture/configuration variables, but exercises
open-session directional trading. The historical weekend regression itself has explicit closure/cache
preconditions and is not in this fresh-block gate. See the preceding weekend evidence for that comparison.
The directional old-to-new migration test requires the sample's original deployed implementation; if the
public sample is upgraded later, choose an eligible original sample or an archive block, rather than bypassing
its assertions. The legacy usage unit regression is independent of public testnet state.
