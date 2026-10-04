# Treasury product profiles and percentage limits

Status: first implementation PR, stacked on #22. No registration or deployment has been broadcast.
The implemented new profile is **Strategy treasury → Rebalance → Continuous**. This is the first part of
the product consolidation, not a claim that all of its price/cycle/buyback/frontend work is complete.

## Product model

Creators choose a treasury mode, then a strategy, then parameters. Registry kind IDs, contract versions and
proxy implementation names are deployment details resolved from a verified address book.

| Product choice | Execution rule | Status in this PR |
|---|---|---|
| Buyback treasury | No stock strategy; buy FUN from eligible income | Existing #22 upgradeable implementation retained; percentage buyback remains pending |
| Strategy treasury / Price / Single round | Manage the current round, finish exiting, then stop opening new positions | Pending state machine; not an alias for the existing lot strategy |
| Strategy treasury / Price / Cycle | Manage a round and re-enter under explicit price/cooldown rules | Pending integration with the current price implementation |
| Strategy treasury / Rebalance / Continuous | Correct the tradable stock/USDG allocation towards its target | Implemented here, upgradeable, schema 3; not deployed |

The existing ordinary lot strategy already permits dip re-entry. The old Cycle implementation additionally
permits one recovery entry after an actual sale. Neither implements the proposed single/cycle product switch.
Changing their labels would not implement the desired behavior. Old kinds remain append-only and cannot be
disabled by deleting repository files; official launch selection needs a verified profile allowlist.

Income distribution is a separate choice. Production recurring dividends and percentage buyback sizing are
not implemented by schema 3. Its inherited buyback retains the existing fixed chunk and separate TWAP/anchor
guards. This version has no pending-dividend liability ledger; a future dividend successor must add and audit
that accounting before any cash balance is considered available for trading.

## Implemented schema-3 execution

The new proxy, `HedgeFunV2TradablePercentEngineTreasury`, uses the existing 48-hour controller. Its per-launch
logic has an independent storage-family identifier. It preserves configuration, policy/asset identity, inventory,
average cost, nonce, cooldown and trading-date spend through a compatible upgrade. It cannot be substituted for
an old schema-1/2 implementation by interpreting old monetary words as percentages.

The new `V2TradablePercentRebalancePolicy` only proposes a target gap. The treasury independently checks its
code, domain, nonce, direction and capability, and clips the proposed action against all budgets:

- **Buy limit:** available USDG cash × buy percentage, rounded down.
- **Sell limit:** tradable stock quantity × sell percentage, rounded down.
- **Daily limit:** (tradable stock's live oracle value + available USDG) × daily percentage, rounded down.
  Remaining capacity subtracts actual turnover already recorded for the same US trading date.
- Buys/sells are also bounded by the target gap, actual inventory and existing live-price/slippage guards.
  The legacy `sellChunkUsdg` no longer clips schema-3 stock strategy execution. A small percentage on a small
  treasury cannot be inflated to the minimum lot: it waits instead.

Tradable stock includes booked inventory and bookable incoming stock once, excluding reserved `buybackStock`.
Locked LP principal, parked vault assets, unclaimed LP fees and FUN's market value are excluded. All available
USDG is currently strategy cash; cash donations increase that basis. Stock donations are booked at the live
oracle. Sells count stock actually leaving strategy inventory, including realized-profit stock allocated to
buyback. Buys count USDG actually spent. Keeper rewards use actual swap output, and buy inventory/cost uses
stock retained after the reward. Failed transactions roll back trades and accounting atomically.

Daily capacity is dynamic: a price drop can reduce remaining capacity to zero, and a price rise or capital
inflow can increase it. Previously used USDG is never reset by a price change, donation, failed attempt or
upgrade. The trading-date boundary remains the oracle calendar's 20:00 New York boundary, including DST;
this is not a rolling 24-hour window. A preview describes the current snapshot, not a guaranteed fill.

### Configuration encoding

`EngineConfig` remains fixed width, with `engineVersion = 1`, `schema = 3` and the registered policy key:

| Field | Encoding / bounds |
|---|---|
| `words[0]` | Target bps [0..15], allocation band bps [16..31], cooldown seconds [32..63], realized-profit-to-buyback bps [64..79]; higher bits zero |
| Target | 20–90%; band must remain strictly inside the 0–100% allocation interval; zero band is accepted |
| Cooldown | At least 600 seconds |
| Profit share | 0–100% of realized stock profit, not graduation principal |
| `words[1]` | Buy bps [0..15], sell bps [16..31]; higher bits zero; each 1–10,000 bps |
| `words[2]` | Daily turnover bps, 1–10,000; no other bits |

The action and daily fractions use different denominators, so the daily percentage is not required to exceed
either action percentage. Schemas 1 (fixed money) and 2 (full external-asset percentages with a fixed listing
cap) keep their existing behavior. An immutable old factory checks schema-3 metadata but not all its words;
the constructor validates them authoritatively. Use the strict configuration adapter and a fresh launch
simulation rather than assuming that an old factory's address prediction validates the complete config.

## Registration and named configuration

`RegisterV2TradablePercent` appends one kind and policy. IDs are read from its result; never assume 3, 4 or 5.
Its five operator transactions deploy the policy, register it, create two code chunks, then register the kind.
Public `makeChunks` calls cannot move the operator's CREATE nonce. Before and after simulation, the guard
checks complete reviewed factory/graduation/registry/controller runtimes with every immutable bound. It also
checks actual chunks, policy code/metadata and the supplied dependency/audit manifest commitments.

Hashes must identify reviewed evidence for the exact release candidate. A nonzero hash alone is not audit
sign-off. Different compiler/runtime templates require their own compatibility review.

```sh
export OPERATOR=<owner> V2_FACTORY=<reviewed-factory>
export DEPENDENCY_MANIFEST_HASH=<reviewed-dependency-hash> AUDIT_MANIFEST_HASH=<reviewed-evidence-hash>
forge script script/RegisterV2TradablePercent.s.sol:RegisterV2TradablePercent \
  --rpc-url "$RPC_URL" --sender "$OPERATOR"
# Simulation only; this PR has not published a registration.

export TRADABLE_PERCENT_KIND=<returned-kind> TRADABLE_PERCENT_POLICY=<returned-policy>
export TRADABLE_PERCENT_POLICY_KEY=<returned-policy-key>
forge script script/RegisterV2TradablePercent.s.sol:VerifyV2TradablePercent --rpc-url "$RPC_URL"
```

`tools/treasury_profile_config.py` translates the named profile into schema 3. Percentages are decimal strings
with at most two fractional digits. All fields are required; there are no silently selected economic defaults.
For example (illustrative values, not a production recommendation), save:

```json
{
  "mode": "strategy", "strategy": "rebalance", "execution": "continuous",
  "targetPercent": "50", "bandPercent": "5", "buyPercent": "20", "sellPercent": "20",
  "dailyPercent": "50", "profitToBuybackPercent": "50", "cooldownSeconds": 600
}
```

After a registration has been verified, build the candidate and run the read-only adapter:

```sh
python3 tools/treasury_profile_config.py --rpc-url "$RPC_URL" --factory "$V2_FACTORY" \
  --kind "$TRADABLE_PERCENT_KIND" --policy-key "$TRADABLE_PERCENT_POLICY_KEY" \
  --creator <creator-address> --symbol <symbol> --nonce <nonce> --input <profile.json>
```

The adapter verifies live deployment identities at one block and simulates the selection with `eth_call`.
It emits the selection calldata and profile binding without sending a transaction. It rejects unsupported
price single/cycle profiles, legacy money fields, disabled policies and mismatched code. Selecting a profile
still requires the creator's transaction; launching then requires a new prediction and full simulation. The
frontend integration must perform equivalent checks and revalidate when the connected deployment changes.

## Remaining consolidation work

1. Price strategy lifecycle: define round ownership of incoming capital, partial exits, dust, stop behavior,
   completion and re-entry. Ordinary dip buys cannot silently reopen a completed single round.
2. Integrate recovery after both real take-profit and stop fills. The current All-in override does not call the
   old Cycle sale hook, so simply changing inheritance would lose recovery-after-profit behavior.
3. Implement percentage buyback and the price strategy's percentage/day budgets with reviewed module/layout
   boundaries. Current code-size headroom is limited; do not temporarily rewrite `_params` around delegatecalls.
4. Replace frontend kind choices with verified product profiles; retain legacy pool read/trade compatibility.
5. Complete full product E2E, audit the complete release, then publish and verify testnet registration/deployment.

These are explicit release follow-ups. This PR does not switch existing UI choices or deploy/upgrade any pool.
