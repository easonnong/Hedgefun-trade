> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Sandbox v2 rehearsal runbook

This runbook covers the **new, undeployed** sandbox in `script/Sandbox.s.sol`. It uses owner-minted `SBXSTK` and `SBXUSD`, both without monetary value. It uses the real Robinhood Chain V3/V4 contracts to rehearse protocol behavior, so a mainnet deployment would still spend native gas and face public trading in its pools. Do not send real USDG or other real assets to the sandbox contracts.

The commands below are **simulation examples only**: none includes `--broadcast`, signs a transaction, or creates persistent on-chain state. In particular, the `SANDBOX=` address printed by a simulated `stage()` is a simulated address. It cannot be used by a later independent command. For a full sequential rehearsal with durable state inside a disposable fork, run the fork tests. A human operator would need a separately reviewed deployment procedure before any mainnet broadcast.

The newer `script/SandboxFakeUsd.s.sol --tc SandboxFakeUsd` entry point shares the same v2 implementation and reads `FUSD_SANDBOX` instead of `SANDBOX`. It prints `FUSD_SANDBOX=` and has the same bounded `price` and `trade` signatures below. Both entry points stage test dollars. Neither accepts the pre-v2 `SandboxBook` or `FakeUsdBook`; migrate by staging a new rehearsal, not by pointing new commands at an old Book.

## Preconditions and checks

- Run from the `hedgefund` repository root with a configured RPC in `RH_RPC`. Never print or paste its value into a report.
- Use `--tc Sandbox` on every `forge script script/Sandbox.s.sol` invocation. The source file declares multiple contracts.
- For any existing `SANDBOX` address, require a **v2** `SandboxBook` created by the new script. The script checks the Book runtime hash, version, mock quote bytecode, LP wiring, and owner bindings. The old real-USDG Book is deliberately rejected.
- Confirm the intended operator owns the Book, mock stock, mock quote, and LP helper. `SandboxFeed` ownership belongs to the LP helper. Keep the `SANDBOX` Book address and contract addresses from a real deployment record; do not reuse addresses printed by a standalone simulation.
- The production 24/5 trading calendar still applies. `seed()` requires a healthy open-session price; during a closure, wait for the session or deliberately configure only this sandbox calendar through its owner. Fork fixtures force their own calendar open to test the rule independently of the wall-clock weekday.
- The V3 pool is public. Check its current `slot0`, active liquidity, and mock balances immediately before deciding a price cap or trade minimum. A previously calculated bound can become stale after another trade.

## 1. Stage and launch

Simulate a **10 test-dollar** stage. `10_000_000` is six-decimal `SBXUSD`; the script allocates about 80% to the pool and keeps the remainder idle with the LP helper. `stage()` returns the `SandboxBook` in Solidity and prints `SANDBOX=` in the script output.

```sh
forge script script/Sandbox.s.sol --tc Sandbox --sig "stage(uint256)" 10000000 --rpc-url "$RH_RPC"
```

For a persisted v2 Book, wait **at least 601 seconds after stage** before simulating `launch()`. The contract enforces this delay so the V3 observation ring can support the 600-second price window. The following and later commands assume `SANDBOX_BOOK` was recorded from an actual v2 deployment, not from the simulation above.

```sh
SANDBOX="$SANDBOX_BOOK" forge script script/Sandbox.s.sol --tc Sandbox --sig "launch()" --rpc-url "$RH_RPC"
```

`launch()` walks the mock pool to 100.2, refreshes its feeds, and creates the sandbox strategy. The hook, treasury deployer, token deployer, and factory are created and checked together inside `SandboxLaunchBundle.deploy`. The rest of the launch script is still multiple transactions if broadcast. Wait **another 601 seconds after launch** before `seed()` or a planned `price()` rehearsal so the 600-second mean can settle to the new spot. Check `status()` and treasury health first.

```sh
SANDBOX="$SANDBOX_BOOK" forge script script/Sandbox.s.sol --tc Sandbox --sig "status()" --rpc-url "$RH_RPC"
```

## 2. Seed, move price, and trade

`seed(stockQuote,reserveQuote)` values are six-decimal **test-dollar notionals**. The script mints mock stock for the first amount and mock quote for the reserve, gives both to the treasury, then calls `book()`. Tokens gifted to that treasury follow its immutable production behavior and have no direct withdrawal path. This example simulates 2 test dollars of stock plus 1 test dollar of reserve, after the post-launch wait and a healthy `status()`:

```sh
SANDBOX="$SANDBOX_BOOK" forge script script/Sandbox.s.sol --tc Sandbox --sig "seed(uint256,uint256)" 2000000 1000000 --rpc-url "$RH_RPC"
```

`price(priceE18,maxInput)` now invokes **one LP contract transaction**: the V3 swap must reach the exact target in active liquidity, then both stock and mock-quote feeds update atomically. Prices are 18-decimal test dollars per stock and must be between 25 and 400. `maxInput` is the **input token's raw units**:

| Direction | Token spent by LP | `maxInput` decimals |
| --- | --- | --- |
| Price up | `SBXUSD` mock quote | 6; `1_000_000` = 1 test dollar |
| Price down | `SBXSTK` mock stock | 18; `1_000_000_000_000_000_000` = 1 test stock |

Example simulation: target 112 with a maximum payment of 1 test dollar. This cap is an example, **not** a fresh quote or a guarantee of success; simulate against the current pool state and raise or lower the cap deliberately. A historical `eth_call` on the old pool and a fork test with the new 10-test-dollar pool each measured **0.922053** quote units for 100.2 → 112, correcting an earlier 8.96 estimate. Both measurements describe their specific fixture states, not a future public pool.

```sh
SANDBOX="$SANDBOX_BOOK" forge script script/Sandbox.s.sol --tc Sandbox --sig "price(uint256,uint256)" 112000000000000000000 1000000 --rpc-url "$RH_RPC"
```

For a downward move, express the cap in 18-decimal stock units. `repeg()` is a separate owner action that adopts the public pool's current in-range price into the feeds; use it only after checking that price.

`trade(quoteIn,minTokensOut,minQuoteOut)` buys the strategy token with mock quote and sells half back. Set **both** minimum outputs from a current simulation and an explicit tolerance: `minTokensOut` is 18-decimal strategy-token units and `minQuoteOut` is six-decimal mock-quote units. The code requires nonzero values but does not calculate safe bounds; an explicit `1` would still provide effectively no protection. Set the two shell variables to reviewed integer bounds before simulating:

```sh
SANDBOX="$SANDBOX_BOOK" forge script script/Sandbox.s.sol --tc Sandbox --sig "trade(uint256,uint256,uint256)" 1000000 "$MIN_TOKENS_OUT_WEI" "$MIN_QUOTE_OUT_MICROS" --rpc-url "$RH_RPC"
```

The buy and half-sale are separate broadcast transactions in this script. If the sale fails after a successful buy, the operator may retain bought strategy tokens; inspect balances before retrying.

## 3. Exit the LP position

`exit(min0,min1)` burns the LP helper's full remaining V3 position, collects principal and fees to the operator, and sweeps **idle mock assets** from the helper. Set `min0` and `min1` in the pool's **token0/token1 order**, not stock/quote label order. Obtain those addresses and expected principal amounts from the current pool before setting the minimums. Both minimums use their respective token's raw decimals. `exit(0,0)` explicitly waives principal slippage protection; avoid it unless that outcome is deliberate.

```sh
SANDBOX="$SANDBOX_BOOK" forge script script/Sandbox.s.sol --tc Sandbox --sig "exit(uint256,uint256)" "$MIN0" "$MIN1" --rpc-url "$RH_RPC"
```

The LP's burn and collect are atomic in `removeLiquidity`; the script's later idle-token sweeps are separate broadcast transactions. The **old** deployed LP helper lacks burn and collect, so only its idle balances can be moved through `sweep`. Its old treasury's 1 USDG snapshot has no direct withdrawal path. The new script cannot upgrade or recover those old deployed positions.

## Recommended verification

Run the security unit tests and the full sandbox fork path before using a new deployment plan:

```sh
forge test --match-path test/SandboxSecurity.t.sol
RH_FORK=1 forge test --match-path test/SandboxFork.t.sol
```

Fork tests are the practical way to rehearse `stage → wait → launch → wait → seed → price → trade → exit` as one sequence without persisting state on mainnet. They exercise a rehearsal with synthetic assets; they do not cover a real production token issuer, real quote settlement, or all public-market interference.
