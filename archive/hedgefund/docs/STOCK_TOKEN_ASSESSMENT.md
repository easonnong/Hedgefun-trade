> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# The real stock token, assessed

Closes the item AUDIT.md left open: *"Nobody has assessed the real ERC-8056 stock token: transfer callbacks and
blocklist behaviour are assumed."* Read-only against Robinhood Chain (chainId 4663) on **2026-09-20, block ≈ 68.28M**.
Nothing was signed or broadcast; issuer actions were reproduced on a local fork by pranking the live role holders.

> **Everything below is "as of implementation `0xb35490d6f9163DE4F80d88dc75c3516eb64C5aE2`" (runtime codehash
> `0xdc07e86e…d1eec7`).** The token is upgradeable by a single EOA with no timelock, and one transaction changes the
> code of **every** stock token at once. None of these findings is a property of the token; they are properties of
> the code it points at today. `test_fork_snapshot_beaconProxy_pinnedImplementation_andRoles` fails the day that
> changes — run it before every listing and on a schedule.

Status tags: **VERIFIED** (how is stated) · **INFERRED** (reasoned from verified facts, not executed).
Source = Sourcify `exact_match` (creation + runtime) for the implementation `src/Stock.sol:Stock` and for the
registry `src/AccessControlsRegistry.sol`, both solc 0.8.33, verified 2026-09-08. Blockscout's API sits behind a
Cloudflare challenge and was not readable from a script; Sourcify's match is against the same on-chain bytecode.
Fork tests are in `test/StockTokenFork.t.sol` (`RH_FORK=1 forge test --mc StockTokenFork -vv`).

## Findings

| # | Question | Answer | Evidence | Consequence here |
|---|---|---|---|---|
| 1 | Is it a proxy? | **Yes: OpenZeppelin `BeaconProxy`.** NVDA, AAPL and GOOGL are byte-identical proxies (codehash `0x6c1fdd40…5630`) on the **same beacon** `0xe10b6f6B275de231345c20D14Ab812db62151b00`. The beacon is also the access-control registry (roles, blocklist, global pause). | VERIFIED. EIP-1967 beacon slot `0xa3f0ad74…3d50` = the registry on all three; implementation slot `0x360894a1…2bbc` and admin slot `0xb5312768…6103` are zero; `implementation()` = `0xb354…5aE2`. Fork test `snapshot_*`. | One upgrade re-codes every listed stock simultaneously. A per-stock "we checked this token" is really "we checked the beacon". |
| 2 | Who can upgrade, and how fast? | `upgradeTo(address)` on the registry, gated by `BEACON_UPGRADER_ROLE`, held by **`0xCd8C6182…e094`, an address with no code (EOA), nonce 1**. `DEFAULT_ADMIN_ROLE` (can grant any role) is `0xd6f8378f…b66d`, also no code. **No timelock, no delay, no multisig visible on-chain.** The only check in `upgradeTo` is `code.length != 0`. | VERIFIED: registry source l.36-42; complete `RoleGranted/RoleRevoked/Upgraded` history of the registry pulled from the official RPC (24 admin events, block 7,662 → 657,134) and each current holder confirmed with `hasRole`. The deployer's admin and upgrader roles were revoked at blocks 8,692/8,695. Two `Upgraded` events, both to the current implementation. | Whether these EOAs are MPC/HSM-custodied is not knowable on-chain. Treat as: the issuer can change transfer semantics (add a callback, a fee, a rebase) in one block with no notice. |
| 3 | Transfer callbacks? | **None.** `_update` is `super._update` (unmodified OZ v5.5 `ERC20Upgradeable`: two balance writes and an event) plus one extra event, `TransferWithScaledUI`. No ERC-777, no ERC-1363, no call to `from`/`to` anywhere in the first-party source. The only external calls on the transfer path are `staticcall`-shaped views into the registry (`isBlocked`, `paused`). | VERIFIED: `ERC20ScaledUIUpgradeable.sol` l.97-100, `Stock.sol` l.57-78, OZ `_update` l.199-228. Fork: `transfer_makesNoCallToRecipient_andIsExact` sends to a contract that reverts on every call under `vm.expectCall(recipient, "", 0)` — transfer and transferFrom both succeed, zero calls reach the recipient. | TR-5 not reachable today (verdict below). |
| 4 | Fee on transfer / rebasing? | **No.** Received == sent, sender debited == sent, supply unchanged. | VERIFIED: same source; same fork test (3e18+1 wei in, 3e18+1 out). | V4 `sync/settle` accounting and the hook's claim arithmetic are exact. |
| 5 | Blocklist? | **Yes, a deny-list, shared by all stocks, in active use.** `transfer` checks `to` and `msg.sender`; `transferFrom` checks `from`, `to` **and the operator** (`msg.sender`); `approve` and `permit` check owner, spender and caller. `BLOCKER_ROLE` = `0x913cA873…28fD` (EOA, nonce 250). 246 `Blocked` events / 177 unique addresses / 4 `Unblocked`, all between blocks 43,543 and 495,841 (nothing in the ~67.8M blocks since); **none of the blocked addresses has code**, and the PoolManager is not blocked. | VERIFIED: `Stock.sol` l.57-100, `AccessControlled.sol` l.35-40, registry l.44-56; full event history; `isBlocked(PM) == false`; fork `blocklist_operatorOfTransferFrom`. | See scenarios below. Note the operator check: a blocked router/aggregator cannot move stock between two clean parties. |
| 6 | Pause? | **Two independent switches.** Per-token `pause()` (`TOKEN_PAUSER_ROLE`, `0xFCcF56B6…Ab23`) and registry-wide `pause()` (`PAUSER_ROLE`, `0xe7BCB188…F22A`) that stops every stock at once. Either stops `transfer`, `transferFrom`, **`approve`**, `permit`, `mint`, `burn` and `updateMultiplier`. The global pause has been used once on mainnet: blocks 611,101 → 611,243 (142 blocks, early in the chain's life). No per-token pause has ever fired on NVDA/AAPL/GOOGL. | VERIFIED: `Stock.sol` l.30-35, l.137-157; registry l.26-34; event history; fork `pause_tokenAndGlobal`. | See scenarios below. |
| 7 | Seize / force-transfer? | **`adminBurn(from, amount)`**: `ADMIN_BURNER_ROLE` (`0x957B6de6…74D4`, EOA, nonce 1) burns any amount from **any** address. It carries **no `onlyNotPaused` and no `onlyNotBlocked`** — it works while the token is paused and against blocked or unblocked holders alike. There is no `forceTransfer`; seizure is burn-then-mint (`MINTER_ROLE`). | VERIFIED: `Stock.sol` l.124-126. Fork `adminBurn_canEmptyThePoolManager_evenWhilePaused` burns the PoolManager's entire NVDA balance during a global pause. Whether it has ever been used on mainnet was **not determined** (it emits only a plain `Transfer` to zero, indistinguishable from `burn` without tracing). | **This is the one way raw balances change under a holder.** The docs' "balances stay fixed" is about corporate actions only. An `adminBurn` against the PoolManager makes V4 insolvent in that currency for every pool that holds it; nothing in this protocol can detect or repair that. |
| 8 | `uiMultiplier()` mechanics | A stored multiplier with a scheduled successor (`_newMultiplier`, `_effectiveAt`); `uiMultiplier()` flips by timestamp, with no transaction at the moment of effect. `balanceOf`/`totalSupply` never read it; only `balanceOfUI`/`totalSupplyUI` and the extra event do. | VERIFIED three ways. Source l.36-73. **History**: NVDA `UIMultiplierUpdated(1e18 → 1.000775159164630595e18, effectiveAt 1788998430)` at block 58,952,659; on the archive node at blocks 58,958,492 → 58,958,493 (the flip) `uiMultiplier` changes while `totalSupply` (85,313.395e18), `balanceOf(PoolManager)` (29,326.133…e18) and `balanceOf(V3 pool)` are identical to the wei. AAPL and GOOGL each have exactly one update too. **Fork**: `multiplierUpdate_leavesRawBalancesAlone` applies a 10× multiplier: raw balance and supply unchanged, UI view ×10. | V4 accounting is safe across corporate actions. The economic meaning of one raw token changes (a 10:1 split makes a raw token worth 10 shares); `PriceOracle` is correct only because the RH feeds already include the multiplier — keep the "never multiply again" rule. `updateMultiplier` itself reverts while paused. |
| 9 | `oraclePaused()` | **A bare flag.** Set/cleared by `ORACLE_PAUSER_ROLE` (`0x7369d100…4aBC`); nothing in the token reads it; transfers continue. Never set on NVDA/AAPL/GOOGL so far (0 `OraclePaused` events). | VERIFIED: `OraclePausable.sol` (whole file), `Stock.sol` l.171-177; event history; fork `oraclePause_doesNotStopTransfers_butStopsOurOracle`: a transfer and a launch-pool swap succeed, `takeProfit` reverts. | "Advisory, not enforced on-chain" is accurate. Our `PriceOracle.tryPrice` failing closed on it is the only enforcement there is; the launch pool keeps trading and taxing through it, which is intended. |
| 10 | Does `deal()` work? | Yes. Balances live in OZ's namespaced ERC-20 storage (`0x52c63247…ce00`), a plain mapping. | VERIFIED: fork `deal_worksOnThisToken`. | Fork tests need not borrow from the V3 pool. (`deal(..., true)` to adjust supply was not tried.) |
| 11 | Does the PoolManager already hold these? | **Yes, at scale.** PoolManager `0x8366a39C…0951` holds 33,396 of 91,796 NVDA (**36%** of supply), 6,064 of 16,315 AAPL (37%), 4,816 of 15,901 GOOGL (30%), 18,592 of 33,945 SPY (55%). | VERIFIED: `balanceOf` / `totalSupply` at block ≈ 68.28M. | Strong precedent that the issuer tolerates V4 custody; it also means blocking or burning the PoolManager would strand a third of each float, which makes it an unlikely first resort. That is an incentive argument (INFERRED), not a guarantee. |
| 12 | Anything else on the surface? | `setMetadata` can rename the token (name feeds the EIP-712 domain, so outstanding permits die). `mint`/`burn` for the issuer's own flow. `terms()` returns a URL. Nothing else. | VERIFIED: `Stock.sol` in full (192 lines). | None for this protocol: it never uses `permit` or `approve` on the stock (grep of `src/`: no approve on `_stock`). |

## Verdicts

### TR-5 — is the `takeProfit` / `book()` reentrancy reachable with the real token?

> **Hardened in the PR that carries this file**, on exactly the argument made below: `book()` is `nonReentrant`, and
> `takeProfit`, `stopLoss` and `buyDip` write every effect before they pay the bounty. The audit's reproduction
> (`test_F5_…`) now asserts the re-entry reverts, and was confirmed to fail with the old ordering restored.

**No, not with the implementation live today.** The bounty is paid with `transfer`, and the verified transfer path
makes no call to the recipient (finding 3). `test_fork_TR5_bountyTransferDoesNotReenter` runs the attack for real: a
contract whose fallback calls `treasury.book()` takes the profit on real NVDA; it receives the bounty, its fallback
never fires, and no lot is booked from inside.

**But it is one un-timelocked EOA transaction from reachable** (finding 2), so "Info, not exploitable" holds only as
long as the snapshot test passes. The fix is two lines and costs nothing: make `book()` `nonReentrant` (with an
internal `_book()` for `takeProfit`'s own call) and move the bounty transfer after `buybackStock`/`lastSalePrice` are
written. Do that rather than rely on the issuer never adding ERC-1363.

### Blocklist and pause — what breaks, and does it come back?

All VERIFIED on the fork with the V3-venue treasury (`HedgeFunTreasury`) unless marked.

| Issuer action | Launch-pool swaps | `sweep` | Treasury rule | Buy-back | When lifted |
|---|---|---|---|---|---|
| **Block the PoolManager** (`blocklist_poolManager`) | **Both directions revert** (buy: `to == PM`; sell: `sender == PM`). Every V4 pool holding any stock stops. | Does not revert. Token leg still burns. Stock tax stays as ERC-6909 claims. | `takeProfit` **still works** — the V3 venue never touches the PoolManager. V4-venue treasuries (`StrategyTreasuryV4`) would be stuck: INFERRED. | Reverts. | **Fully recoverable**: swaps resume, claims redeem, buy-back runs. |
| **Block a treasury** (`blocklist_treasury`) | Unaffected. | Does not revert. Redeem succeeds (PM → hook), then **the whole stock leg parks in the hook**: the treasury is paid first and unguarded, so protocol, creator and caller get nothing either. | `takeProfit` reverts (sender blocked). `book()` moves no tokens, so it still works on stock already there. | Reverts. | **Recoverable**: next sweep distributes the parked stock; `takeProfit` runs. Funds are frozen, not lost. |
| **Block the hook** (`blocklist_hook`) | **Unaffected** — the tax is a 6909 mint, no stock transfer touches the hook. | Does not revert. `take` to the hook refused; claims accumulate. | Starved of new stock; existing lots fine. | Fine. | **Recoverable**: one sweep redeems everything. |
| **Block the creator** (`blocklist_creator_costsOnlyItsOwnCut`) | — | Treasury and protocol paid; creator's cut stays in the hook and is re-split next sweep. | — | — | HK-3's fix does what it says against the real token. |
| **Pause NVDA, or pause the registry** (`pause_tokenAndGlobal`) | Both directions revert. | Does not revert; claims wait. | `takeProfit` reverts. | Reverts (INFERRED from the same transfer). | **Fully recoverable** on unpause. |
| **`adminBurn` the PoolManager** (`adminBurn_…`) | Sells revert once the PM cannot pay out. | Does not revert; the stock claim is **unredeemable**. | — | — | **Not recoverable by anyone but the issuer** (re-mint). Permanent otherwise. |
| `adminBurn` a treasury | — | — | INFERRED: `bookedStock + buybackStock` exceeds the balance; `unbookedStock()` clamps to 0, sales of the missing stock revert, new tax is silently absorbed into the hole before any new lot is booked. | | Not recoverable without a gift of stock. |

Permanent blocks are permanent freezes: none of the four custody points has an escape hatch, by design. A block on a
*treasury* or *hook* that is never lifted strands that strategy's stock forever; a block on the *PoolManager* strands
every strategy and every other V4 pool on the chain.

## What the protocol should change or document

1. **Fix TR-5 anyway** (`book()` non-reentrant, bounty last). The token's "no callback" is a revocable fact.
2. **Pin the implementation.** Keep `test_fork_snapshot_…` in a scheduled job (not only PR CI), and have the listing
   runbook require a green run. Consider an on-chain guard at `factory.list`: record `beacon.implementation()` at
   listing and surface a view that says whether it still matches — cheap, and it turns a silent upgrade into a
   visible one for front-ends. (A hard revert on mismatch would brick strategies on a benign upgrade; do not do that.)
3. **Rewrite disclosure (3).** It currently reads as "a pausable/blocklisting stock bricks the sweep". Accurate text:
   the issuer can (a) pause one stock or all stocks, (b) block any address including the PoolManager, the hook or a
   treasury, (c) **burn any holder's balance, including the PoolManager's, even while paused**, and (d) replace the
   token's code, all from EOAs with no on-chain delay. (a)/(b) freeze and are fully reversible; (c) is not.
4. ~~**Document the treasury-blocked case in `distributeStock`'s comment**~~ — overtaken twice. `distributeStock` no
   longer exists. Since audit L4-2 the treasury is credited on the ledger like everyone else (`owedTreasury(id)`), so
   a blocked treasury parks its own share and stops nobody's; and since the singleton hook (2026-09-21) the stock
   leg is `settleStock(id, caller)`: redeem, credit and pay in one `try`ed call, per pool.
   **What the singleton changes for this assessment:** there is now ONE hook address for every strategy, so (b)
   above — blocking the hook — stops the stock leg of every strategy's sweep at once, and (c) — burning the hook's
   balance — writes down every claim parked on that stock across every pool, pro rata. Both used to need one action
   per strategy. See [SECURITY.md](./SECURITY.md#one-hook-address-holds-every-strategys-stock-side-payouts).
5. **Keepers/front-ends should read `paused()`, `registry.isBlocked(PM|hook|treasury)` and `oraclePaused()`** and
   stop calling rather than burn gas on reverts; `sweep` in particular *succeeds* while doing nothing on the stock
   side, so a keeper sees a successful transaction, a zero tip, and no error to alert on.
6. **No change needed for corporate actions** at the accounting level. Do note for users that a split changes what
   one raw token is worth (lot `qty` is raw; `cost` is per raw token from a multiplier-inclusive feed, so the rule's
   percentages stay right *provided the feed and the multiplier flip together* — that coupling is the issuer's and
   is exactly what `oraclePaused()` exists to cover).

## What could not be determined

- **Who holds the EOAs' keys** (MPC, HSM, a person) and whether an off-chain process delays upgrades. On-chain: no code, no delay.
- **Whether `adminBurn` has ever been used.** It emits the same `Transfer(from, 0)` as the ordinary `burn`; telling them apart needs tx-level tracing over ~68M blocks.
- **Blockscout's own verification status** (API behind a bot challenge). Sourcify's `exact_match` on creation and runtime bytecode is at least as strong.
- **The other stocks' proxy bytecode.** All 194 tokens in `data/rh_stock_tokens.json` were checked for the beacon slot and **all 194 point at the same beacon** (VERIFIED, `eth_getStorageAt`, 2026-09-20), so they run the same implementation. Only NVDA/AAPL/GOOGL had their proxy codehash compared; extend the snapshot test to each stock at listing time.
- **Issuer policy**: when they would block a contract. History shows only code-less addresses blocked, in the first ~500k blocks (consistent with a sanctions preload), and one 142-block global pause. That is history, not a commitment. The public docs (building-with-stock-tokens, fetched 2026-09-20) say nothing about upgradeability, the blocklist, pause or `adminBurn`.
- **`StrategyTreasuryV4` under each scenario** was reasoned, not run — and is moot since 2026-09-21: the V4 stock venue was removed, and `HedgeFunTreasury` (V3) is the only treasury.
- **Votes.** Today's implementation has no `delegate`, no checkpoints, no vote surface of any kind. The treasury carries `setVoteDelegate` anyway (owner-only, one `try`ed `stock.delegate(d)`, nothing else reachable) because this token can be upgraded and a launched treasury cannot. If an upgrade ever adds votes, re-run this assessment before the hatch is used — including what `delegate` does besides delegating.

## Test output (2026-09-20)

```
$ forge test
Ran 20 test suites in 1.51s (7.78s CPU time): 332 tests passed, 0 failed, 13 skipped (345 total tests)

$ RH_FORK=1 forge test --mc StockTokenFork -vv
Ran 13 tests for test/StockTokenFork.t.sol:StockTokenForkTest
[PASS] test_fork_TR5_bountyTransferDoesNotReenter() (gas: 31734862)
[PASS] test_fork_adminBurn_canEmptyThePoolManager_evenWhilePaused() (gas: 30874604)
[PASS] test_fork_blocklist_creator_costsOnlyItsOwnCut() (gas: 30922727)
[PASS] test_fork_blocklist_hook() (gas: 31121700)
[PASS] test_fork_blocklist_operatorOfTransferFrom() (gas: 242751)
[PASS] test_fork_blocklist_poolManager() (gas: 32425696)
[PASS] test_fork_blocklist_treasury() (gas: 32168275)
[PASS] test_fork_deal_worksOnThisToken() (gas: 223409)
[PASS] test_fork_multiplierUpdate_leavesRawBalancesAlone() (gas: 62385)
[PASS] test_fork_oraclePause_doesNotStopTransfers_butStopsOurOracle() (gas: 31548729)
[PASS] test_fork_pause_tokenAndGlobal() (gas: 32703115)
[PASS] test_fork_snapshot_beaconProxy_pinnedImplementation_andRoles() (gas: 62335)
Logs:
  PoolManager holds NVDA (whole): 33251  of supply 91795
[PASS] test_fork_transfer_makesNoCallToRecipient_andIsExact() (gas: 270676)
Suite result: ok. 13 passed; 0 failed; 0 skipped; finished in 4.20s (33.27s CPU time)
```
