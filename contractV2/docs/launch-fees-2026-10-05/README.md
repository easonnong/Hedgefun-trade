# V2 native launch fee and creator share cap

Applied on Robinhood **testnet (46630)** at block **129034324**, 2026-10-05 UTC.

Factory: `0xc9610d4A749b2A62a7327a0f40B59013D8fC415a`.

Transaction: `0xc15677ab95546ba7863685cff47ffc12a681f7db0d213b9f37e86898025c3e07`.

| Setting | Before | After |
| --- | --- | --- |
| Maximum creator share of collected trading tax | 30% (`3000` bps) | 10% (`1000` bps) |
| Launch fee currency | tUSDG (`2`) | Native ETH (`1`) |
| Launch fee | 25 tUSDG (`25000000`) | 0.0005 ETH (`500000000000000` wei) |

The creator chooses 0–10% of the **tax collected**, not 0–10% of trade volume. At the existing 1% UI tax default, a creator choosing 10% receives 0.1% of trade volume before rounding. The protocol's 20% tax share and the treasury's remainder are unchanged rules.

Only these three factory defaults changed. The complete snapshots in [plan.json](./plan.json) and [readback.json](./readback.json) confirm the other 19 fields and factory bytecode are unchanged. In particular: the allowed trading tax remains 1–15%, the LP swap fee remains 0.3%, and liquidity allocation, opening windows, strategies and buybacks were not changed. Existing launches retain their frozen rates; this cap is enforced on future launches through the existing owner-configurable defaults, not a new immutable protocol maximum. No mainnet transaction was sent.

The existing factory charges the exact native fee through `msg.value` and sends it to the existing protocol recipient. Creation does not require an ERC20 fee approval or a new launch router. Buying the first tokens is a separate trade. The frontend already reads the current fee currency, amount and creator-share ceiling from the factory; refresh its launch review after the configuration change.

## Source and validation

`V2LaunchFeeDefaults` applies the same three choices to fresh testnet deployments and cores that reuse the existing test market. `ConfigureV2LaunchFees` updates an existing V2 factory with explicit chain, owner and reviewed-defaults checks. No production Solidity implementation or storage layout changed.

Validation completed before broadcast:

- 35 targeted Foundry tests passed; the cap rejection test includes 256 fuzz cases.
- The actual configuration script passed on a public-testnet fork at block **129030873**. Both 0% and 10% creator shares launched with native ETH. Wrong payment values and 10.01% creator share were rejected. The complete unrelated defaults and an existing launch's frozen terms were preserved.
- Local regression tests also verify that a pre-existing 30% creator share remains frozen, stale launch quotes fail, exact ETH fees reach the recipient, fee ceilings are respected, and non-owners cannot change defaults.
- Existing frontend `src/lib/testnet/launch.test.ts`: 13 tests passed in the `testnet-redeploy-40` checkout. No frontend source change was needed.
- The live configuration transaction succeeded, used 78,615 gas, and its full defaults hash matched the reviewed plan at readback block **129034329**.

These are scoped fee/configuration checks, not a new audit of the whole protocol. No public test token was launched in this change; successful launches were exercised on the fork.

Reproduce the scoped contract checks from `contractV2/` (Foundry 1.5.0):

```sh
forge test --match-contract '(V2LaunchFeesTest|DeployV2TestnetTest|DeployV2FeeUpgradeTestnetTest|DeployV2CreatorTestnetTest|AddV2TestnetStocksTest)' -vv
LAUNCH_FEES_FORK=true LAUNCH_FEES_FORK_BLOCK=129030873 \
  forge test --match-contract TestnetV2LaunchFeesForkTest -vv
```

The public RPC may prune the recorded block; use a fresh block for a new rehearsal and record it separately.

## Post-configuration fork regression

The deployed append-only registry had **six** kinds at the reviewed L2 block **129058489**. The old upgrade and schema-three fork fixtures incorrectly required exactly three. They now snapshot every existing kind's chunk addresses, runtime hashes and manifest, require new registrations to append, and verify all existing entries remain unchanged. The fixtures retain a minimum of the original three legacy kinds without freezing the current count.

The pinned income, compatibility, treasury-upgrade, tradable-percent and launch-fee CI forks default to `https://robinhood-testnet.drpc.org`. Native-launch jobs keep using the official testnet RPC, so the jobs do not share one provider's quota. Each pinned suite has an explicit RPC override and uses one requested L2 block selected after compilation. PublicNode returned the same block hash but could not supply all of that block's historical state. The official endpoint also pruned the older validation block during a later rerun, so neither is a default provider for this pinned suite.

The launch-fee fork is now a required CI scenario, alongside the existing 23 income/compatibility/upgrade/percentage scenarios. CI fails on any RPC failure, skipped scenario or missing expected pass. No signed transaction or public-chain broadcast is needed for these checks.

## Future configuration operations

Do not rebroadcast the recorded transaction. For a different reviewed testnet factory, read and review all 22 defaults, record `keccak256(abi.encode(defaults))`, then dry-run with explicit `V2_FACTORY`, `OPERATOR`, and `EXPECTED_DEFAULTS_HASH`:

```sh
forge script script/ConfigureV2LaunchFees.s.sol:ConfigureV2LaunchFees \
  --rpc-url https://rpc.testnet.chain.robinhood.com --sender "$OPERATOR"
```

The owner may broadcast the reviewed result with their existing keystore. Re-read defaults and check there are no competing owner transactions immediately before signing: the existing `setDefaults` function does not provide an atomic compare-and-set guard. Verify the full post-transaction tuple. The recorded change used an equivalent direct `setDefaults` call; its exact calldata is in `plan.json`.

Historical address books and old deployment reports still describe their original transactions; they were not rewritten to imply this configuration existed at those earlier blocks.
