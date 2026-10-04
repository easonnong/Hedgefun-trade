> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Ten-wallet SBOX rehearsal

This is a controlled test of the existing **SBOX / real NVDA** strategy on chain **4663**. Its settlement currency is **real USDG**, and gas is real ETH. It does not use the attacked SBXSTK pool or the new fake-dollar sandbox. The ten addresses are all controlled by the operator; neither the generated chart nor the trades are evidence of independent users or organic demand.

The user budget is **20 USDG maximum**. The first funding batch allocates **1 USDG and 0.0002 ETH to each of ten wallets** (10 USDG + 0.002 ETH total, plus the funder's transaction fees). The other 10 USDG stays with the operator. The first trade batch spends **0.5 USDG per wallet**, then a separate sell batch sells **50% of each wallet's SBOX**. Gas is an allocation, not an estimate of the amount that will be consumed. Balances left after the test remain in the wallets you control.

## Verified target

The public configuration is [`data/sbox-multiwallet.json`](../data/sbox-multiwallet.json). The CLI verifies its chain, pair, canonical V3 pool, factory/strategy/router bindings, token decimals, and router runtime hash before use.

| Item | Address |
| --- | --- |
| Operator (must match `--account sandbox-deployer`) | `0x97fbf8e94b5e2873afb5c67bfe4546978670c48b` |
| Factory / strategy ID | `0xc403504bc500d6aef82128ca3e312a7af15955c5` / `0` |
| SBOX token | `0xed9288aab3c09f8ec899ca5f10a69b7c407df831` |
| Trade router | `0x9937bf2edf733f7f960e7fe78904045ad81d33cd` |
| NVDA / USDG pool | `0xd4eb21209c4d6093f80b5b84f5c45cc093ea14a3` |

The router's deployed runtime was compared against the repository's compiled `HedgeFunTradeRouter`, excluding immutable slots, and matched. Its full runtime hash, including the live immutable values, is pinned in the configuration.

## 1. Prepare the terminal and generate the ten addresses

Run from this repository's isolated worktree. Only Python 3.9+ and Foundry `cast` are needed. Load the RPC without printing it:

```sh
cd /Users/keyuyuan/hedgefund-multiwallet-test
set -a
source /Users/keyuyuan/rh/.env
set +a
sbox() { python3 tools/sandbox_wallets.py --config data/sbox-multiwallet.json "$@"; }
```

Run the following command **by itself**, finish both hidden password prompts, and wait for the ten addresses before running funding commands. Do not paste multiple interactive commands together.

```sh
sbox init --execute
```

`init` generates cryptographically random wallets in encrypted Foundry keystores. Set a new keystore password at the hidden prompt, enter it again to confirm, and keep it: it will be needed for funding verification and later trades. Typed characters are not displayed. This step does **not** make a blockchain transaction. No private key is printed or written into the repository. The output includes the ten public addresses.

Default local state is `~/.local/share/hedgefund-sandbox/sbox-ten/`: `wallets.json` maps addresses to encrypted files under `keystores/`, and `journal.json` records submitted operations. Back up the encrypted keystores and keep the password separately. `init` refuses to overwrite an existing wallet set. The deterministic identities used by the Solidity fork test are unrelated and must never receive live funds.

If an older failed initialization left an **empty** `keystores/` directory, rerun `init --execute`: it can safely reuse that empty directory. If any key file exists but the manifest is missing, it stops and preserves all keys for recovery. Do not remove a nonempty keystore directory to retry. Empty or mismatched passwords are rejected before creating a new wallet directory.

## 2. Preview and fund

```sh
sbox fund --account sandbox-deployer
```

Inspect the plan, then run the next command separately and finish its password prompts:

```sh
sbox fund --account sandbox-deployer --execute
```

After funding finishes:

```sh
sbox status
```

The first command is a read-only funding plan. The second asks for the **ten-wallet keystore password** to verify every destination, then the password for **`sandbox-deployer`** to sign the transfers. A password is not a private key. If they differ, enter the appropriate password at each labeled prompt.

An existing `sandbox-deployer` keystore may have an empty password: press Enter at **Funding account password** in that case. The tool passes an empty password to Foundry, which must still decrypt the account and match its address to the pinned operator. The ten newly generated wallets still require their nonempty password; do not press Enter at the **Ten wallets password** prompt.

If funding stops at the second password prompt with an account unlock error, independently check the named account with `cast wallet address --account sandbox-deployer`. This command only decrypts locally and prints the public address; it does not sign or broadcast. Use the password originally set when importing that account, which may differ from the password just created for the ten wallets. The resulting address must match the pinned operator above. Do not reinitialize the ten wallets or delete their state to fix an account-password error.

Funding tops up to the target balance, rather than always adding another 1 USDG. A repeated confirmed batch is skipped, even if a wallet later spent its balance. Do not change the batch name merely to work around an error. Existing exact transfers are retained in the journal; interrupted funding does not discard its progress.

## 3. Buy, inspect, then sell half

```sh
sbox buy --amount 0.5 --batch buy-1
sbox buy --amount 0.5 --batch buy-1 --execute
sbox status
sbox sell --fraction-bps 5000 --batch sell-1
sbox sell --fraction-bps 5000 --batch sell-1 --execute
sbox status
```

Each command without `--execute` only previews the plan. An executed batch processes wallets sequentially, approves the exact input, obtains a current quote from the real router via `eth_call`, then signs with a nonzero minimum output and a short deadline. The default slippage tolerance is 100 basis points (1%). This tolerance is applied to the router's **after-tax quote**; it does not mean taxes are limited to 1%.

The batch identifiers `buy-1` and `sell-1` prevent accidentally repeating confirmed trades. A deliberate second round must use a new identifier and fit within the remaining budget. Add `--wallet 1` to a command to operate on just the first address. The basic commands do not run a background loop. The optional fixed player schedule below spaces a finite set of trades apart.

Current buy and sell tax rates are printed in the plan. The default `--max-tax-bps 1000` refuses a trade whose current tax exceeds 10%, and checks again after approving. This is an **off-chain preflight check**: a concurrent rate change is ultimately constrained by the transaction's on-chain minimum output, not by a separate tax-cap parameter in the router.

### Optional: four player roles in one finite run

After all ten wallets are funded, the operator can run the fixed schedule:

```sh
python3 tools/sbox_players.py --config data/sbox-multiwallet.json
```

Then run this command separately to execute it:

```sh
python3 tools/sbox_players.py --config data/sbox-multiwallet.json --execute
```

It asks for the ten-wallet password once. The funding account is not used. The schedule has **17 trades** with 15 seconds between steps (plus confirmation and quote time), spending **4.5 USDG total** on buys:

| Wallets | Role | Actions per wallet |
| --- | --- | --- |
| 1–3 | Holders | Buy 0.50 USDG, retain SBOX |
| 4–6 | Split buyers | Buy 0.25 USDG twice, retain SBOX |
| 7–8 | Short-term traders | Buy 0.50 USDG, later sell 50% of SBOX |
| 9–10 | Late arrivals | Buy 0.25 USDG later, then sell 25% of SBOX |

All ten addresses belong to one controlled test. Late arrivals use a fixed schedule; they do not detect dips or imply independent demand. Buys and partial sells use current after-tax quotes, the existing 10% tax preflight cap, 1% slippage tolerance, short deadlines, exact approvals and persistent transaction journal. The script never tops up wallets and stops on any error. Taxes and gas are real costs.

Step batch identifiers are fixed and versioned. Running the same command again skips confirmed steps, and uncertain transactions still block execution. Do not edit the schedule or change journal records to repeat it. After completion, use the chart command below to inspect actual receipts. The basic all-wallet buy/sell commands and this schedule are alternatives; their budgets are not combined automatically.

### Parallel groups with independent timing

The parallel runner starts four workers with disjoint wallet groups. The holder, split-entry, short-term exit and late-arrival groups each follow their own timing and random waits. Transactions from different groups can be in flight together; transactions for one wallet remain sequential. The randomness changes timing, not the budget or trade sizes. These are controlled behavioral scenarios, not autonomous price-predicting strategies.

```sh
python3 tools/sbox_parallel_players.py
```

Run the execution command by itself and enter the ten-wallet password once:

```sh
python3 tools/sbox_parallel_players.py --execute
```

This is a **new round** with separate fixed batch identifiers. It does not replay or replace the original `players-v1` round. The new round buys at most **4.5 USDG**, with at most 0.5 USDG of buy input per wallet (0.25 for wallets 9–10). Running both rounds brings total buy input to **9 USDG**. No extra funding is performed. Partial sells use a fraction of the wallet's **entire current SBOX balance**, including retained tokens from the first round.

A process lock excludes other runners using the same state. Within the parallel run, only brief journal updates use a shared lock; network requests and transaction submissions can overlap. Each worker may save only its own batch entries, merging them into the single main journal used by `status`, recovery and charts. Startup refuses unresolved transactions. A failure stops new work across groups; transactions already in progress may still complete, so the runner waits for workers to finish recording their state before releasing the password and process lock. Resume uses the same batch identifiers and skips confirmed trades. Random waits restart on resume.

After the original sequential round on September 22, all **17 trades** were confirmed: 4.5 USDG buy input and 0.506013 USDG returned from partial sells, with SBOX retained. From the first recorded post-swap observation to the last, the SBOX/NVDA spot rose approximately 0.0607%; that comparison excludes the movement caused by the first buy. The parallel round has not been executed by the agent.

### Small price-reactive session

```sh
python3 tools/sbox_reactive_players.py
```

The default prints a plan without unlocking keys or placing trades. The operator starts the new session separately:

```sh
python3 tools/sbox_reactive_players.py --execute
```

The fixed `reactive-v1` session permits **at most 0.8 USDG of buy input**, 0.1 USDG each for wallets 1–8. Wallets 9–10 can sell **10% of their current SBOX holdings**; this includes tokens retained from earlier rounds. No wallet is topped up. This session has separate identifiers from the earlier sequential and parallel rounds, so starting it authorizes additional trades within its own cap.

Four concurrent groups react to one observed SBOX/NVDA pool price: wallets 1–2 make small initial buys; wallets 3–5 require two upward price changes and a rise of at least 10 parts per million (0.001%) from the session baseline; wallets 6–8 require three upward changes and a rise of at least 30 ppm (0.003%). Flat samples do not count as upward changes. Wallets 9–10 can exit a small fraction after a 60 ppm rise, or after a 15 ppm retracement from a peak that was at least 30 ppm above the baseline. These thresholds refer to **pool spot movement, not after-tax profit**. Buy and sell taxes can dominate such small movements.

The baseline, session deadline and trigger decisions are persisted. Resume does not restart the observation window or repeat confirmed trades. The window is bounded to at most five minutes; unmet conditions expire without a forced trade. A signal may not develop, and no rising price path is promised. Trading decisions remain constrained by the existing per-trade tax check, quote, slippage, balance, nonce and durable journal checks.

The price reader follows the vendored V4 `StateLibrary` layout, pins both pool lookup and price read to one block, checks that block is still canonical, and uses exact rational arithmetic with the correct token ordering. The observed price is NVDA per SBOX, not USDG per SBOX or account return. These ten addresses remain a disclosed, operator-controlled behavioral test. If the window expires after an approval confirms but before its trade is admitted, the exact approval and its journal entry remain; inspect status and allowance before any later session. No expired trade is forced through to consume the approval.

### What the rehearsal showed

On a mainnet fork at block **69,388,025**, the existing router charged **10% buy tax and 10% sell tax**. Ten buys of 0.5 USDG moved the SBOX/NVDA spot **+0.0881%**. Selling half of each resulting holding ended **+0.0484%** above the initial spot and returned **2.023461 USDG in total**, while retaining half the purchased SBOX. These values are measured simulation output, not live execution promises. Future quotes depend on the current pools and tax rates, including the sell-tax spike after a treasury buyback.

The fixture locally sets wallet USDG balances; it neither mints nor transfers real USDG. Gas figures measured inside the test omit some transaction overhead and benefit from warmed state, so they are not live gas estimates.

## 4. Draw the actual trades

```sh
python3 tools/sbox_trade_chart.py --state "$HOME/.local/share/hedgefund-sandbox/sbox-ten"
```

Open `~/.local/share/hedgefund-sandbox/sbox-ten/reports/sbox-trades.html`. The adjacent CSV contains the underlying observations. This command only reads public transaction receipts; it never opens keystores. Run it after buys and again after sells to see the change.

The first line shows the V4 pool's **NVDA price per SBOX immediately after each recorded swap**. The second shows each wallet's **actual net USDG execution price**, including taxes and trading fees. Gas is excluded. These are different quantities and use separate charts. The vertical scale adapts to the observations, so a visually large movement can still be less than 0.1%; read the axis labels. Only trades from this test's journal are included, not intervening third-party activity. An empty journal produces no invented price history.

## Interrupted or failed commands

Every send is recorded before signing. If submission times out or returns an ambiguous result, the script stops and blocks further sends rather than guessing whether it landed. `status` refreshes receipts for known hashes. If a hash was lost, locate it in the sender's transaction history, then reconcile it:

```sh
sbox reconcile --operation OPERATION_ID --tx-hash TRANSACTION_HASH
```

Reconciliation requires the exact recorded sender, nonce, recipient, calldata, and value. If no transaction was broadcast and no hash exists, keep the state files and investigate; do not delete the journal or blindly repeat the transfers. A reverted trade may leave an earlier approval in place, but only for the exact input amount authorized for that trade.

The tools default to planning. Mainnet signing and broadcasting happen only when the operator runs `--execute`. The agent's project rules prohibit it from signing or broadcasting on the operator's behalf.
