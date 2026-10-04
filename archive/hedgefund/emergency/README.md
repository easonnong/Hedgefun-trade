> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Emergency kit

**V2 scope:** [V2 curves](../docs/V2_BONDING_CURVE.md) use a separate factory and hook. Its treasury
reports `health() == (false, 0)` until graduation, so booking and stock strategy execution wait even
when the oracle is healthy. After graduation the existing calendar/oracle controls apply unchanged.
Stopping launches or delisting a stock does not stop an existing curve or seize its reserves. The final
buy and migration are atomic: a failed seed rolls back the buy and leaves the prior curve tradable,
subject to the stock issuer still allowing transfers. There is no owner reserve rescue or curve pause.
This kit's existing deployment configuration targets V1; do not reuse a V1 address set for V2.

> **HARD RULE. Nothing in this directory signs or broadcasts a transaction, holds a private key, or calls
> `cast send` / `forge script --broadcast`.** `build.py` makes read-only requests (`eth_chainId`,
> `eth_getBlockByNumber`, `eth_getCode`, `eth_call`; anything else is refused in code) and writes a Safe
> **Transaction Builder** JSON file. Humans load that file into the Safe UI and sign it there. The one file that
> changes state anywhere is `drill_apply.py`, and the only state it can change is a throwaway `anvil` on your own
> machine: it refuses any non-local URL, refuses any node that is not anvil, and sends unsigned transactions that
> a real node rejects.

Everything launched is immutable. The Safe owns two contracts, `HedgeFunFactory` and `TradingCalendar`, and the
levers below are all there is in an emergency. (As the factory's owner the Safe can also repoint the two payout
addresses of a launched pool on the hook — one hook serves every strategy, and each call takes the pool's id — and
point a launched treasury's votes with `setVoteDelegate`. Neither stops anything, so neither is a lever and neither
is in this kit: section 3.) **Read "What the Safe cannot do" before you need it**, not during.

## 1. Decide (30 seconds)

| What you are seeing | Lever | Command |
|---|---|---|
| Bad launches, a scam wave, a launch-path bug, spam | **L1** stop public launches | `build.py stop-launches` |
| One stock's oracle, feed or pool is wrong, thin or being gamed, and you do not want NEW strategies on it | **L2** delist it | `build.py delist NVDA` |
| Treasuries are trading at a wrong price, or a rule bug is being farmed (`takeProfit` / `buyDip` / `stopLoss` / `book`) | **L3** halt the rule | `build.py halt --days 5` |
| You do not know yet, and it is bad | **L4** everything | `build.py everything --days 5` |
| A halt is in force and the cause is not fixed | extend it | `build.py extend --days 5` |
| Someone is dumping / sniping / sandwiching a **token's own pool**, or draining buy-backs | **No lever.** See section 3 | -- |
| A real market crash, and launched strategies have `stopBps` set | **Do NOT halt.** A halt switches `stopLoss` off. See section 8 | -- |
| A Chainlink outage, a stale feed, `oraclePaused()` | Already fails closed by itself. Halt only if you want to choose WHEN it comes back | (`halt`) |

Always start with `python3 emergency/build.py status`. It is read-only and takes seconds.

**How fast is this?** As fast as your Safe threshold can sign. Blocks are 0.1 s; a multisig is minutes to hours.
No lever here stops an attack that is already in flight. They stop the bleeding after it.

## 2. What each lever actually does (verified in source and in `test/Emergency.t.sol`)

- **L1 `setPublicLaunch(false)`**: `launch()` reverts `NotOpen` for everyone except the Safe. The Safe can still
  launch directly (as its own `q.creator`: a launch is sent by its creator). Launches through `HedgeFunLaunchRouter` stop
  for everyone, the Safe included: the factory sees the router as the sender. Nothing launched is touched.
- **L2 `list(...)` again with `enabled=false`**, every other argument read back from
  `factory.listings(stock)`. `launch()` against that stock reverts `NotListed` for everyone, **the Safe included**.
  Launched strategies on that stock are untouched and keep trading it. One transaction per stock, one shape: every
  listing is a V3 listing (the V4 stock venue, and the three-transaction flag dance it needed, were removed on
  2026-09-21).
- **L3 `setOverride(day, 1)`** on every calendar, for N consecutive trading dates starting today. On a
  forced-shut day `PriceOracle.tryPrice()` fails, so `health()` is false in every treasury priced through that
  calendar and `takeProfit`, `buyDip`, `stopLoss` revert `Unhealthy`; `book()` returns false. This holds on a weekday
  AND on a weekend (commit 8015343: `isScheduledClosure` is false on any overridden day, so the closed-market
  path is shut too). **Which configuration ships:** a listing's `bandCeiling` is 0 until the Safe raises it, so a
  treasury born with `bandBpsPerHour = 0` sleeps through weekends and holidays and a halt changes nothing for it on
  those days. A treasury launched with a band, after `setBandCeiling(stock, bps)`, DOES trade closures, and the halt
  is what stops it; the test proves that case.
- **Overrides are per trading date, and a trading date rolls at 20:00 ET.** After 20:00 ET "today" is already
  tomorrow's index. `build.py` reads the index from `calendar.tradingDate(latest block time)`; never compute it by
  hand. **A halt lapses by itself at 20:00 ET on its last date**, silently, and every trigger that came due during
  the halt becomes callable in that block. `status` prints the exact lapse time. Put it in a calendar.
- **L4** is L3, then L1, then L2 for every enabled listing, in one batch.

Each `PriceOracle` has its own immutable `calendar()`. `build.py` reads it from every listed stock's oracle and
from every treasury's `oracle()`, de-duplicates, and unions that with `addresses.json`. Re-listing a stock with a
new oracle leaves old launches on the old one; the kit finds those through the treasury, but a read that fails in
an emergency is skipped rather than fatal, so **`addresses.json` must list every calendar ever used**. The real check is after the fact: `status` must show `health = false` for every
strategy. Any strategy still healthy after a halt is on a calendar you missed.

## 3. What the Safe CANNOT do

If the incident is in this list, no batch will help. Say so early.

- **It cannot stop a token from trading.** The hook has no pause, and the only thing its owner (the factory's owner, read live) can
  do to it is repoint two payout addresses per pool. **There is one hook for every strategy**, so a flaw in it is a
  flaw in all of them at once, and there is still no lever. The token's V4 pool keeps filling
  buys and sells through any halt, and **keeps charging the tax**. Holders keep paying a tax that funds a rule
  that is not running.
- **It cannot stop `sweep(id)`.** Tax keeps flowing to the treasury, the creator and the protocol. During a halt the
  treasury's share arrives and sits unbooked; the first `book()` after the halt books all of it as one lot at that
  moment's price.
- **It cannot stop `buyback()`.** `buyback()` asks `tryPrice()` first, and when that fails (as it does under a halt)
  sizes its chunk off `lastGoodPrice` as long as that is no older than `MAX_SIZING_AGE = 5 days`. The clock is
  `lastGoodPriceAt`, which is written only by `book`, `takeProfit`, `stopLoss` and `buyDip` -- so buy-backs stop by
  themselves **five days after the last rule action, not five days after the halt**, or earlier when
  `buybackStock` runs out. Each call spends at most `buybackChunkUsdg`, once per `buybackCooldown`. Execution is
  bounded by the hook's own 600 s mean when its ring can serve it, otherwise by the treasury's ratcheting anchor.
  `status` shows the cut-off per strategy. Outside a halt (`tryPrice()` fine, pool merely off), buy-backs run
  indefinitely. A halt is therefore the only thing that ever stops them, and it takes up to five days.
- **It cannot move treasury funds, remove the seeded liquidity, change a pool's tax, launch window, split or
  treasury, change a launched rule (its gates and chunks included), or upgrade anything.** No such function exists
  on the treasury, hook or token. The Safe's whole handle on anything launched is each pool's two payout addresses
  on the hook (`test_theSafesHandleOnAnythingLaunchedIsTheTwoPayoutAddresses`; liquidity permanence is in
  `test/InteractFactory.t.sol`) and each treasury's vote delegate — `setVoteDelegate(delegatee)`, which points the
  votes of the stock held there (reserved, not live: the stock token has no vote surface today), moves no asset and
  cannot reach the rule (`test/TreasuryVote.t.sol`). `decode` names it and refuses it: "a governance action, not an
  emergency lever". The payout addresses: `setProtocol(id, next)` moves the protocol's own payout in that pool at once, and
  `proposeCreator(id, next)` → 14 days → `acceptCreator(id)` moves a vanished creator's unless the creator calls
  `vetoCreator(id)`. Neither stops, slows or reverses anything, so neither is an emergency lever: **this kit does not
  build them, and `build.py decode` flags their selectors as DO NOT SIGN, on purpose** (it would flag the target
  too: the hook is not in `addresses.json`). They are prepared by hand, one transaction per pool — get the id from
  `hook.poolOfTreasury(treasury)`; see [`docs/OPERATIONS.md`](../docs/OPERATIONS.md#moving-a-payout-address) — and
  never belong in an emergency batch. `setDefaults`, `setBandCeiling`, `setListingGates`, `setLauncher` and listings affect future
  launches only. There is no rescue of stock held by the hook — parked or donated — no migration and no refund path.
- **It cannot lift an issuer's deny-list, pause or burn — and the hook is now one address.** If the stock's issuer
  deny-lists the hook, the stock leg of every sweep of every strategy stops at once (tax keeps accruing as claims
  and is paid when it is lifted; trading is unaffected). An `adminBurn` of the hook's stock writes down every claim
  parked on that stock, in every pool, pro rata. No batch helps with either. `hook.totalOwed(stock)` rising on
  every stock at once is the symptom.
- **It cannot halt a calendar it does not own.** `build.py` refuses, or with `--skip-unowned` halts the rest and
  tells you the halt is partial. AUDIT FA-1 proposes renouncing calendar ownership; if that is ever done, L3 and
  the halting half of L4 stop existing.
- **It cannot un-halt selectively.** An override is per calendar per day: every strategy on that calendar, or none.

**What users experience during a halt.** They can buy and sell the token exactly as before and are taxed exactly
as before (the sell spike still arms after each buy-back). The treasury holds its stock unmanaged: no take-profit,
no dip buy, **no stop-loss**. Buy-backs continue for up to five days, then stop. There was never a redemption or a
claim on the treasury, and there still is not. Tell them that, in those words, when you halt.

## 4. Before anything: signer checklist

The Transaction Builder uses the raw `data` field when it is present and ignores `contractMethod` /
`contractInputsValues`, so the UI shows custom hex, not a decoded call. The decoded fields are in the file for
people; the check below is what makes them trustworthy.

Every signer, on their own machine, on the file they were sent:

```
python3 emergency/build.py decode <file>.json
```

1. `VERDICT consistent`. It fails on: a checksum that does not match the contents, a target that is not the
   factory or a calendar in `addresses.json`, any selector outside the three functions this kit emits
   (`setOverride`, `setPublicLaunch`, `list`), non-zero value, `mode 2` (forced
   OPEN -- no playbook emits it), and decoded fields that disagree with the raw data. Four selectors it refuses **by
   name, with their arguments decoded**: `setBandCeiling`, `setListingGates` and `setLauncher` -- "a configuration change, not an
   emergency lever -- it does not belong in an emergency batch" -- and the treasury's `setVoteDelegate` -- "a
   governance action, not an emergency lever". Everything else (`transferOwnership`,
   `renounceOwnership`, `setDefaults`, anything on the hook) is refused as an unknown selector.
2. **chainId is 4663**, in the file and in the Safe UI's network selector.
3. Each `to` matches `addresses.json`; the method and arguments match the `.txt` summary the builder sent.
4. **The batch digest** printed by `decode` equals the one the builder reads to you by voice. `meta.checksum` must
   match too, and the Safe UI must not warn that the file was modified.
5. In the Safe: Simulate succeeds; the transaction count equals the summary's; the safeTxHash on your hardware
   wallet equals the one the other signers see.
6. Never sign an "emergency" batch that arrived any other way, however urgent the message.

Loading: Safe UI -> Apps -> Transaction Builder -> drag the JSON onto the page -> Create Batch -> Simulate ->
Send Batch. If another transaction is queued at the next nonce, this one waits behind it: replace or execute it.

## 5. Playbooks

All commands run from the repo root and write `emergency/out/<utc>-<playbook>.json` plus a `.txt` summary.
Every build prints each transaction, simulates each one with `eth_call` from the Safe, and refuses to write a
batch that reverts. A playbook with nothing to change writes nothing and says so. `build.py` refuses to run while
`addresses.json` holds placeholders, on a chainId mismatch, and when `owner()` of the factory is not the Safe.

Set once for the verify lines: `RPC=https://robinhood-rpc.publicnode.com`, `F=<factory>`, `CAL=<calendar>`.

### L1 stop-launches
- **When:** the problem is what is being launched, not what is already live.
- **Command:** `python3 emergency/build.py stop-launches` -- one tx, `setPublicLaunch(false)`.
- **Verify:** `cast call $F "publicLaunch()(bool)" --rpc-url $RPC` -> `false`
- **Undo:** `build.py resume-launches`. First check `status`: every ENABLED listing becomes launchable by anyone,
  and `getDefaults()` is what those launches will be born with, forever.

### L2 delist
- **When:** one stock should get no new strategies. It does nothing for strategies already on that stock.
- **Command:** `python3 emergency/build.py delist NVDA SPY` (symbols from `addresses.json`, or stock addresses).
  One `list(..., false)` per stock.
- **Verify:** `cast call $F "listings(address)(address,address,uint256,bool)" <stock> --rpc-url $RPC`
  -> oracle, V3 pool, open price, then `false`; every line but the last unchanged.
- **Undo:** `build.py relist NVDA`. It re-enables the terms currently stored. If the oracle, pool or open price
  should change, that is a new listing decision, not a resume: do it by hand, deliberately.

### L3 halt
- **When:** the rule is, or may be, trading at a wrong price. Read section 8 first if stops are configured.
- **Command:** `python3 emergency/build.py halt --days 5` -- one `setOverride(day, 1)` per calendar per date. Choose
  N by the DATE the summary prints as the last one, not by arithmetic; cover the weekend and the first day you
  could realistically have signers again. A batch that executes after a 20:00 ET roll only wastes its first
  date: the dates are absolute.
- **Verify:** `python3 emergency/build.py status` -> `HALT IN FORCE through <date>`, and
  `0 of N strategies have health() == true`. By hand:
  `cast call $CAL "override_(uint256)(uint8)" <day> --rpc-url $RPC` -> `1`;
  `cast call $CAL "isClosed(uint256)(bool)" $(date +%s) --rpc-url $RPC` -> `true`;
  `cast call <treasury> "health()(bool,uint256)" --rpc-url $RPC` -> `false` / `0`.
- **Extend:** `python3 emergency/build.py extend --days 5` appends N dates after the last forced-shut one. If the
  halt has already lapsed it refuses and tells you the rule is live: use `halt`.
- **Undo:** `build.py resume-halt`, section 6. Days already past need no clearing.

### L4 everything
- **Command:** `python3 emergency/build.py everything --days 5`. Halt first, then launches, then every enabled
  listing. **Keep the output file**: `resume-everything --from <that file>` undoes exactly what it did.
- **Verify:** `status`: no healthy strategy, `publicLaunch False`, every listing `disabled`.

## 6. Resuming is the dangerous direction

A halt cannot lose treasury money. A resume can. The moment the override clears, every trigger that came due
during the halt is callable by anyone, in the same block, for a bounty, at whatever the price is then --
including every `stopLoss`. Verify all of this BEFORE building the resume batch:

1. The cause is understood and no longer reachable -- not merely quiet. Nothing launched can be patched, so
   "fixed" usually means "the external condition is gone".
2. **Resume during a live US session, never into a closure.** For a treasury born with a band, clearing a weekend override
   re-opens the pool-only price path (AUDIT TR-1: whoever holds the pool for 600 s picks the price).
3. For every listed oracle: the stock feed's `updatedAt` is recent, `oraclePaused()` is false, and the pool's spot
   sits within `maxDeviationBps` of the feed. If not, `health()` stays false after the resume and you have learned
   nothing about whether it is safe.
4. Look at what is due. For each strategy, which lots cross `tp1` / `tp2` / `stop` at the current price? That is what
   executes in the first block. If the price gapped during the halt, stops fire at the gap.
5. No day of mourning or other deliberate closure sits inside the window: `resume-halt` clears EVERY forced-shut day
   from today on. Keep one with `--keep <day>`. A day that was forced OPEN (mode 2) before the halt comes back as
   none, not as open.
6. Listings: the oracle and pool are still the ones you want for every future launch, forever. Launches: see L1.

Commands, smallest first: `resume-halt`, `relist <SYM>...`, `resume-launches`, or the mirror
`resume-everything --from emergency/out/<the everything batch>.json` (listings, then launches, then the rule
last; it re-enables only what that batch disabled and reopens launches only if that batch closed them).
**Verify:** `status` shows the healthy count you expected from step 3, not merely "more than zero".

## 7. Filling in `addresses.json`

`cp emergency/addresses.example.json emergency/addresses.json`, fill it, and commit it: it holds no secrets.

- `safe`: the Safe. It must equal the `OWNER` env var given to `script/DeployStrategyLaunchpad.s.sol`. On chain 4663
  that script refuses to run unless `OWNER`, `PROTOCOL` and `CALENDAR_OWNER` are set explicitly, are not the
  broadcaster, and have code; on any other chain id they still default to the deployer, and `build.py` refuses a
  factory whose `owner()` is not this address. See [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).
- `factory`: the `factory` line of that script's output.
- `calendars`: the deploy script deploys one `TradingCalendar` (or reuses `CALENDAR`) and prints it; it deploys no
  oracles. List that calendar, and for every oracle ever passed to `list`:
  `cast call <oracle> "calendar()(address)" --rpc-url $RPC`. Each must be owned by the Safe
  (`Ownable2Step`: `transferOwnership` by the deployer, then `acceptOwnership` by the Safe).
- `stocks`: `SYMBOL -> address` for every `stock` ever passed to `list`. The `listings` mapping cannot be
  enumerated on chain, so this list IS the kit's view of it; `status` warns when a launched strategy trades a
  stock that is missing. Update the file in the same PR as every new listing.

## 8. When the right move is NOT to halt

- **A real crash, with stops configured.** `stopLoss` needs `health()`. A halt turns a falling position with a stop
  into a falling position without one, in every treasury at once.
- **Someone is shoving a stock pool while the market is open.** `health()` already refuses any pool more than
  `maxDeviationBps` (0.5%) off Chainlink, so a real shove parks the rule by itself; inside the gate the rule is
  mean-reverting and takes the other side of the shove. A halt adds nothing and removes the treasury's fills.
- **The attack is on a token's own pool or on buy-backs.** A halt does not reach the pool, and reaches buy-backs only
  after up to five days.
- **The feed is stale or paused.** Already failed closed.
- **You cannot staff the resume.** A halt that lapses unattended at 20:00 ET is an unplanned resume with none of
  section 6 done.

Also true: the batch is visible in the Safe queue and on chain before and after it executes, and the lapse time
is public. Anyone can position for the resume block.

## 9. Owner functions this kit never emits

The Safe's real surface is larger than the three functions this kit emits. The full inventory of owner-only
functions, as of 2026-09-21 (V4 stock venue removed, vote-only treasury owner added):

| contract | function | in this kit? |
|---|---|---|
| `TradingCalendar` | `setOverride(day, mode)` | **yes** (mode 1 and 0 only; mode 2 is flagged) |
| `HedgeFunFactory` | `setPublicLaunch(bool)` | **yes** |
| `HedgeFunFactory` | `list(stock, oracle, v3Pool, openPriceE18, enabled)` | **yes** (to delist and relist, every other argument read back) |
| `HedgeFunFactory` | `setDefaults(Defaults)` | no — future launches only |
| `HedgeFunFactory` | `setBandCeiling(stock, bps)` | no — named and refused by `decode` |
| `HedgeFunFactory` | `setListingGates(stock, dev, slip, sellChunkUsdg)` | no — named and refused by `decode` |
| `HedgeFunFactory` | `setLauncher(launcher, ok)` | no — named and refused by `decode` |
| `HedgeFunHook` (owner read live from the factory) | `setProtocol(id, next)`, `proposeCreator(id, next)`, `acceptCreator(id)` (and `vetoCreator(id)` to withdraw its own proposal) | no — per pool, not levers; section 3 |
| every launched `HedgeFunTreasury` (owner read live from the factory) | `setVoteDelegate(delegatee)` | no — votes only, not a lever; named and refused by `decode` ("a governance action"); section 3 |
| both `Ownable2Step` contracts | `transferOwnership` (and `acceptOwnership` for the incoming owner) | no |
| `TradingCalendar` | `renounceOwnership` — remains available; factory renunciation is disabled | no |

Six on the factory, one on the calendar, three on the hook, one on each treasury. Factory `renounceOwnership`
reverts `OwnershipRenunciationDisabled`; its owner can still hand over through `transferOwnership` →
`acceptOwnership`, and the hook and treasuries follow that owner live. One signed calendar `renounceOwnership`
permanently deletes the calendar's owner controls. The kit refuses ownership calls for both contracts.
`setDefaults` changes what future launches are born with. `setBandCeiling(stock, bps)` decides whether
a future launch on that stock may trade closures at all. Lowering it stops nothing that exists: a launched treasury's
band is frozen at birth, so the `everything` playbook does not touch it; delisting already stops new launches, and
the calendar halt is what stops a banded treasury. `setListingGates(stock, dev, slip, sellChunkUsdg)` is the same
kind of thing: it sets the deviation and slippage gates, and the sell chunk, a **future** treasury on that stock is
born with; a launched treasury's gates and chunk are frozen at birth (`test_theSafesHandleOnAnythingLaunchedIsTheTwoPayoutAddresses` asserts it at the loosest
pair the factory accepts), so tightening it in an incident protects nobody who is already exposed — delist instead.
Loosening it has its own runbook and needs a measured basis report
([`docs/OPERATIONS.md`](../docs/OPERATIONS.md#loosening-a-listings-gates)). `status` prints each listed stock's
`listingGates` — deviation, slippage, sell chunk — under its `bandCeiling`. `setLauncher(launcher, ok)` vouches for a periphery contract
(`HedgeFunLaunchRouter`) that may call `launch` on its caller's behalf. Revoking it stops launches *through that router*
and nothing else — `stop-launches` already stops every public launch, router included — so it is not a lever
either. If a vouched router itself is found to be wrong, revoke it by hand after L1; it holds nothing. `setOverride(day, 2)` forces a day OPEN: on a weekend that serves Friday's close as a live price
for as long as the feed is inside `maxStockAge` (<= 48 h), behind the normal 0.5% gate. `decode` flags every one
of these. `status` warns when a `pendingOwner` is set.

## 10. Drill, every quarter

Before deployment, and on every change to `src/` or this directory:

```
forge test --mc Emergency                              # effects and non-effects, calldata from abi.encodeCall
FOUNDRY_PROFILE=emergency forge test --mc Emergency    # the same, calldata from build.py via ffi, asserted byte-equal
```

After deployment, on a fork (the chain's own RPC; publicnode refuses some fork reads):

```
anvil --fork-url https://rpc.mainnet.chain.robinhood.com --port 8545
L=http://127.0.0.1:8545
python3 emergency/build.py --rpc $L status
python3 emergency/build.py --rpc $L everything --days 3
python3 emergency/build.py decode emergency/out/<file>.json          # each signer, on their own machine
python3 emergency/drill_apply.py emergency/out/<file>.json $L        # impersonates the Safe on the LOCAL fork only
python3 emergency/build.py --rpc $L status                           # expect: no healthy strategy, launches closed, all delisted
python3 emergency/build.py --rpc $L resume-everything --from emergency/out/<file>.json
python3 emergency/drill_apply.py emergency/out/<resume file>.json $L
python3 emergency/build.py --rpc $L status                           # expect: identical to the first status
```

Then load the real `everything` JSON into the real Safe's Transaction Builder, confirm it imports with no
"modified" warning and simulates, and **discard it without signing**. Record: who took part, wall-clock time from
"go" to "every signer ready", anything in `status` that surprised you. Delete `emergency/out/*` afterwards.
