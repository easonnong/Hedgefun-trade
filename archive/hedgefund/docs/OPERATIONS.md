> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Operations

Running the protocol after it is deployed: deciding what to list, the routine checks, what
the alerts mean, and where the emergency procedures are. Deployment itself is in
[DEPLOYMENT.md](./DEPLOYMENT.md).

**Nothing in this repository signs or broadcasts a mainnet transaction.** Every owner
action is a Safe transaction, signed by the Safe's owners in the Safe UI. The tools here
read the chain and, at most, write a Transaction Builder JSON for humans to load.

## Listing a stock

A listing is permanent for every strategy launched against it: the treasury keeps its
birth oracle and pool forever, and re-listing only affects later launches. Get it right
the first time.

### 1. Is it listable at all?

```bash
python3 tools/listability.py          # writes data/listability.json
```

A stock must pass every gate: a **Chainlink push feed** (the binding one — 35 of 194
registry tokens have one), `oraclePaused()` on the token, a live `<stock>/USDG` V3 pool,
an observation ring of at least 660 slots (`PoolTrader` refuses less), and enough depth
that a lot does not move the pool. Current results and the reasoning are in
[`LISTING_CANDIDATES.md`](../LISTING_CANDIDATES.md).

### 2. Is it deep enough, and does its feed tick?

Two filters the chain data alone does not give you, both from the audit:

- **Depth.** The "+30% walk" figures this filter was first written against were overstated 8-25x (external audit
  F-03; [DEPLOYMENT.md](./DEPLOYMENT.md) 7.2), so no listed pool is deep enough for depth to be the defence: a pin is
  affordable on all of them ([SECURITY.md](./SECURITY.md#tr-1-the-staleness-band-bounds-the-pin-it-does-not-remove-it)).
  What bounds a pin's take is the band and the pace. So: `setBandCeiling` only after a replay with
  `tools/band_backtest.py`, set just above what the stock's own closures needed, **never above 10**, and size the
  listing's sell chunk to the pool (an $80k pool does not get a 2,000 USDG chunk). If in doubt, 0: the treasury
  sleeps through closures and nothing is lost but hours.
  Depth moves — these pools changed 2–9× in 17 days — so re-measure; do not reuse a table.
- **Feed cadence.** A low-volatility name (SPY, QQQ, SGOV) can go 15 hours without a
  print, and a quiet feed parks the rule. Expect downtime, or list something else.

First wave, decided 2026-09-20: **NVDA, AAPL, GOOGL**, optionally SPCX.

### 3. Verify the three prices agree

```bash
python3 tools/verify_feeds.py NVDA AAPL GOOGL
```

Compares the Chainlink feed (÷ USDG), the pool's spot and Lighter's mark. They should
agree within ~1% in open hours. **Resolve the feed by address**: `description()` comes in
three formats on this chain (`RH<T> / USD`, `Robinhood <T> / USD`, `Robinhood <T>-USD`) and
a name match silently misses most of the roster. `STALE` outside market hours is expected.

### 4. Pick the pool deliberately

The deepest `<stock>/USDG` pool is not always the fee tier you expect (AAPL's deepest is
the 0.05% pool, not the 0.30% one). The treasury trades whichever pool is listed, forever.

Depth also decides what a lot **gets** when it leaves. A sale fills as far as the slippage
limit under the oracle lets it and keeps the rest in the lot, so a thin pool can no longer
stop a sale — it makes it expensive. Measured 2026-09-21, depth inside ~0.85% of room is
about $4.4k on USAR, $19k on META, $51k on CRCL, $83k on GME's 0.05% pool and $120k on AMZN.
Measure the candidate's depth here, because step 5 sizes the listing's `sellChunkUsdg` from
it ([Sizing a listing's sell chunk](#sizing-a-listings-sell-chunk)) — a treasury's chunk is
frozen at birth. And the pool that tracks Chainlink
best is not always the deepest (GME: listed on the 0.05% pool, 1% pool eight times deeper);
if the pool you want sits further from the feed than the default gates allow, that is what
[per-listing gates](#loosening-a-listings-gates) are for, not a reason to widen the defaults.

### 5. Deploy the oracle, then list

Both are Safe transactions; the exact arguments and checks are in
[DEPLOYMENT.md](./DEPLOYMENT.md). Set the listing's sell chunk (and gates, if it needs its
own) **before** anyone launches on it. After listing, add the stock **and its oracle's
calendar** to `emergency/addresses.json` — `listings` is a mapping and cannot be
enumerated on chain, so the emergency kit only knows what that file tells it.

## Routine checks

| When | What | How |
|---|---|---|
| Daily (automated) | Has the issuer upgraded the stock token? | CI's scheduled fork job runs `test_fork_snapshot_beaconProxy_pinnedImplementation_andRoles`. **Red means the implementation or a role holder changed**: re-read [STOCK_TOKEN_ASSESSMENT.md](./STOCK_TOKEN_ASSESSMENT.md), re-run `RH_FORK=1 forge test --mc StockTokenFork -vv`, and do not list anything new until the assessment is updated and the pin moved |
| Daily | Protocol state | `python3 emergency/build.py status` — `publicLaunch`, every listing with its band ceiling and gates, every calendar's overrides, `health()` of every strategy, any `pendingOwner` |
| Daily | Is the hook's stock leg being paid? | for each stock, `hook.totalOwed(stock)` should be 0 or falling. Rising across **every** stock means the hook's address cannot receive — the issuer's deny-list is shared by all stock tokens, and there is one hook. Trading is unaffected and the tax keeps accruing as claims (`accrued(id)`); nothing here can lift a deny-list. See [SECURITY.md](./SECURITY.md#one-hook-address-holds-every-strategys-stock-side-payouts) |
| At every open (Sun 20:00 ET, and after a holiday) | Book what arrived while the market was shut | `treasury.book()` on every strategy with `unbookedStock() > 0`. A lot is booked only at a LIVE Chainlink print, so tax swept in over a closure -- and a seed from a closed-market launch -- waits as `unbookedStock()` and becomes a lot at the open's price. Nothing is lost while it waits and no bounty pays for the call; every `takeProfit` books first, so an active strategy catches up by itself, a quiet one needs the keeper |
| Before every listing | Steps 1–4 above | — |
| Weekly | Did a halt lapse or is one about to? | `status` prints the exact lapse time. A halt ends **by itself** at 20:00 ET on its last date |
| Quarterly | Emergency drill | [`emergency/README.md`](../emergency/README.md), the drill section: build a batch, replay it on a local anvil fork, verify, resume |
| After any PR touching an owner lever, a calendar or `health()` | The runbook still matches the contracts | `FOUNDRY_PROFILE=emergency forge test --mc EmergencyTest` |

`health() == false` for a strategy is normal outside market hours (the shipped treasuries
sleep through closures) and during a quiet-feed stretch. It is a problem when it is false
for *every* strategy in open hours without a halt in force: check the feed's `updatedAt`,
`oraclePaused()` on the stock, and the calendar's override for today.

## Moving a payout address

Two of the things the Safe can change on a strategy already launched (the others: a halt
through the calendar, and [a treasury's vote delegate](#pointing-a-treasurys-votes)), both
on **the hook** — one contract for every strategy (`factory.hook()`; `strategies(i).hook` reads the
same address for every `i`) — and both **per pool**: every call takes the strategy's
`PoolId`. The hook has no owner of its own: `owner()` reads the factory's owner live, so
the caller is the Safe that owns the factory. Neither is an emergency lever, so
`emergency/build.py` does not build them and `build.py decode` will flag their selectors as
DO NOT SIGN — that is the kit working as intended. Prepare them by hand, and have every
signer check the calldata against the `cast calldata` line below. One transaction per pool:
the `to` is always the same hook, the pool id differs, and nothing moves them all at once.
**A wrong pool id is a valid call on somebody else's strategy** — every signer derives it
themselves.

```bash
export RPC=https://rpc.mainnet.chain.robinhood.com
export F=<factory>
export H=$(cast call $F "hook()(address)" --rpc-url $RPC)
cast call $F "strategies(uint256)(address,address,address,address,address)" <i> --rpc-url $RPC   # token, treasury, hook, stock, creator-at-birth
export PID=$(cast call $H "poolOfTreasury(address)(bytes32)" <treasury> --rpc-url $RPC)           # the PoolId. 0x00…00 = not a treasury of this hook
cast call $H "treasuryOf(bytes32)(address)" $PID --rpc-url $RPC   # round trip: must read <treasury> back
cast call $H "owner()(address)"             --rpc-url $RPC        # must be the Safe that will sign
cast call $H "protocolOf(bytes32)(address)" $PID --rpc-url $RPC
cast call $H "creatorOf(bytes32)(address)"  $PID --rpc-url $RPC
```

### The protocol's own payout — `setProtocol(PoolId id, address next)`

Instant. What is already parked for the protocol in that pool (`owedProtocol(id)`) goes to
`next` with it. `next` must be non-zero, and should be a Safe verified the way
DEPLOYMENT.md section 5 verifies `PROTOCOL`. The factory's own `protocol` is immutable:
launch fees, and the birth recipient of every *new* pool, stay where they were, so a
rotation means this transaction for every launched pool and again for every pool launched
afterwards.

```bash
cast calldata "setProtocol(bytes32,address)" $PID 0x<next>      # data; to = $H, value = 0
```

Load it into Safe Transaction Builder (to = the hook, value 0, the hex as custom data), one
entry per pool — they batch well, since the `to` never changes. Afterwards
`protocolOf(id)` reads `next` and the hook emitted `ProtocolChanged(id, from, to)`.

### A vanished creator's payout — `proposeCreator`, 14 days, `acceptCreator`

**Rule of thumb: propose only for a creator who is demonstrably unreachable** — every
contact route tried and recorded, and ideally cuts piling up in `owed(id, creator)` or landing
at an address that has not moved in months. The proposal is public and vetoable by design.
Proposing against a creator who is merely quiet costs the protocol its word, and their veto
locks the door for 180 days.

```bash
cast calldata "proposeCreator(bytes32,address)" $PID 0x<next>   # 1. starts the clock; emits CreatorProposed(id, …)
cast call $H "pendingCreator(bytes32)(address)"   $PID --rpc-url $RPC
cast call $H "pendingCreatorAt(bytes32)(uint256)" $PID --rpc-url $RPC   # unix time; acceptCreator reverts TooEarly before it
cast calldata "acceptCreator(bytes32)" $PID                    # 2. no sooner than pendingCreatorAt; owner only
cast calldata "vetoCreator(bytes32)" $PID                      # to withdraw your own proposal
```

All with `to = $H`. An unregistered id reverts `WrongPool`.

- `TAKEOVER_DELAY` is 14 days. `pendingCreatorAt` = proposal time + 14 days; 0 means nothing
  is pending. Compare it with `cast block latest -f timestamp --rpc-url $RPC`.
- Proposing again — even the same address — **restarts** the 14 days.
- A matured proposal must be accepted within `ACCEPT_WINDOW` (another 14 days) **by the owner that made it**
  (`pendingBy(id)`), or `acceptCreator(id)` reverts `Expired` and it has to be proposed again. So a proposal cannot be
  parked on a pool to be used years later on no notice, and an owner who takes over the factory gives its own
  14 days.
- The creator cancels with one `vetoCreator(id)` from the `creator` address. It needs no
  stock, so an issuer deny-list does not stop it. After a creator's veto,
  `proposeCreator` reverts `TooEarly` until `noProposalBefore(id)` (veto time + `VETO_QUIET`,
  180 days): a veto proves the creator is there. The owner withdrawing its own proposal
  buys no quiet period. The creator may also call `vetoCreator(id)` with **nothing pending**, as
  proof of life; it starts the same 180 days. A creator who does that twice a year can never be
  proposed against.
- The veto can only come from the `creator` address. A creator that is a contract which cannot
  make an arbitrary call (a splitter, a vesting vault) can never veto, and is takeable by
  construction. Tell creators: an EOA, or a Safe.
- `sweep(id)`, `claim`, `claimFor`, `setProtocol`, `proposeCreator` and `acceptCreator` all revert
  `Reentered` from inside a payout — of **any** pool: the latch is the hook's, not the pool's. You will never see
  it unless the stock token grows a recipient callback.
- **Give `sweep(id)` a fixed gas limit (3M).** What changed with the singleton: the stock leg — redeem, credit,
  pay — is now **one** `try`ed call, so a starved sweep can no longer succeed half-done. Swept across 276 gas
  limits in `test_L4_3_atNoGasLimitDoesASweepLeaveTaxRedeemedAndOwnedByNobody_…`: 106 reverted, 163 settled every
  wei (paid or parked), and **7 still returned success having done nothing** on the stock leg — the tax stayed
  where it was, as this pool's claims. So nothing can be lost or orphaned at any limit, but `eth_estimateGas` can
  still settle on one of those few, and a bot that estimates can look like it is working while doing nothing.
  Check `accrued(id)` after a sweep, not the receipt's status. Past a recipient that burns the gas it is handed
  (possible only if the stock grows a callback), paying the treasury took 3M.
- Until `acceptCreator(id)` the old creator is still paid on every sweep and may `claim`.
  What is still parked (`owedCreator(id)`) at acceptance goes with the role.
- `acceptCreator(id)` emits `CreatorChanged(id, from, to)`. The factory's `strategies(i).creator`
  is a birth record and keeps the old address; the hook's `creatorOf(id)` is the truth.
- The owner has no way to take the stock directly. If `next` cannot receive the stock
  either, it waits on the ledger for `next` to `claim(id, to)`.

## A creator's page: setting a token's metadata

Not an owner action — the Safe has no say here — but creators ask. The token carries a logo, a description, five
links and an `extraURI`. Only `token.deployer()` — the address that launched, fixed for ever — or the one `editor` it
appoints can write them, and a takeover of the payout (previous section) does **not** move that right. Each write
replaces the **whole** entry, empty strings included, so restate what you are keeping. Caps are bytes: 256 per link,
1024 for the description (`TooLong()` = `0x4ee45b56`, and nothing is written). A stranger gets `NotAllowed()` =
`0x3d693ada`; anyone after a lock, `IsLocked()` = `0xcaa30f55`.

```bash
export TOKEN=<token>
cast call $TOKEN "deployer()(address)" --rpc-url $RPC                     # must be the address that will send
# logo, description, (twitter, telegram, discord, website, farcaster), extraURI
cast send $TOKEN "setMetadata(string,string,(string,string,string,string,string),string)" \
  "ipfs://<cid>" "What this strategy does, in under 1024 bytes." \
  '("https://x.com/<handle>","","","https://<site>","")' "" --rpc-url $RPC --account <creator>
cast call $TOKEN "getTokenInfo()(address,string,string,(string,string,string,string,string))" --rpc-url $RPC
cast call $TOKEN "updatedAt()(uint64)" --rpc-url $RPC

cast send $TOKEN "setEditor(address)" 0x<editor> --rpc-url $RPC --account <creator>   # optional; address(0) dismisses. The editor can write, not appoint or lock
cast send $TOKEN "lock()" --rpc-url $RPC --account <creator>                          # FOR EVER: the entry and the editor freeze as they stand
```

A typical write costs 35–220k gas (221,010 in the rehearsal), a maximum-size first write about 2.2M. **Read the entry
back before `lock()`, and send the two as separate transactions**: a lock on a typo is permanent. Use `https` and
`ipfs` links only; a careful front end shows nothing else ([SECURITY.md](./SECURITY.md#the-tokens-page-belongs-to-whoever-launched-it)).
A creator that is a contract with no way to make this call has an empty page for ever. The protocol cannot write,
fix or remove an entry; a phishing page is hidden by the front end's own off-chain list, nowhere else.

### When the deployer is a Safe

A strategy the Safe launched has the Safe as its `deployer`, so every edit above is a 3-of-4 signing ceremony.
[`tools/metadata_batch.py`](../tools/metadata_batch.py) builds that transaction from a reviewed plan in
[`deploy/`](../deploy) — the same shape as `tools/listing_batch.py`, and like it and the emergency kit it never signs
and never broadcasts:

```bash
python3 tools/metadata_batch.py deploy/metadata-crclgrid-2026-09-22.json --check   # checks and simulates only
python3 tools/metadata_batch.py deploy/metadata-crclgrid-2026-09-22.json           # ... and writes deploy/safe/<stamp>-*.json
python3 tools/metadata_batch.py --decode deploy/safe/<file>.json                   # what each signer runs on what they were sent
```

It refuses unless `deployer()` is the plan's Safe, `locked()` is false, every string is inside the caps the token
itself reports, every non-empty link is `https://`, and — because a write replaces the whole entry — the plan's
description is byte-identical to the one on chain unless the plan says in as many words that it is replacing it.

**The logo must be a published icon**, `https://<iconHost>/media/icons/<sha256>.png`: the site writes these into its
R2 bucket keyed by the sha256 of the bytes and refuses to overwrite a key, so the URL cannot be repointed at
different bytes later. The tool GETs it and checks the served bytes hash to the name; an unpublished icon refuses the
batch rather than putting a dead URL on chain. Upload through the site's own form, which normalises the image in the
browser — a PNG resized by `sips` on the command line carries an `eXIf` chunk that the uploader rejects (415),
because it admits only `sRGB`, `gAMA`, `cHRM` and `pHYs`.

Appointing an `editor` is the way out of signing for a Telegram link; the plan carries it as `"editor"`. Remember the
order `lock()` forces: dismiss the editor, read the entry back, then lock.

## Pointing a treasury's votes

`setVoteDelegate(address delegatee)` on a launched **treasury** — the one owner call there is on one. `owner()` on
the treasury reads the factory's owner live, so the caller is the Safe and follows a two-step ownership handover.
`renounceOwnership` on the factory is disabled (`OwnershipRenunciationDisabled`). `setVoteDelegate` makes one
`try`ed call, `stock.delegate(delegatee)`, and emits
`VoteDelegateSet(by, delegatee, accepted)`. It keeps no state of its own (only the reentrancy guard's slot, set and restored), and it cannot move, approve, pledge or sell
anything, or touch the rule.

**It is reserved, not live.** The stock token has no vote or delegate surface today, so the call does nothing and
emits `accepted = false`; nobody can vote tokenised stock on this chain, and a front end must say so rather than
show "governance". It exists because the stock token is upgradeable by its issuer and a launched treasury is not:
a hatch that is not there at birth can never be added. Before ever *using* it, settle the legal question first
([SECURITY.md](./SECURITY.md#the-treasurys-owner-can-only-point-its-votes)). There is no `declare()`: a
statement about how the votes will be used is made off chain, or by a separate notice contract.

```bash
cast call $T "owner()(address)" --rpc-url $RPC                  # $T = the treasury; must be the Safe that will sign
cast calldata "setVoteDelegate(address)" 0x<delegatee>          # data; to = $T, value = 0. One transaction per treasury
```

`build.py decode` names this call and flags it DO NOT SIGN in an emergency batch — a governance action, not an
emergency lever. Afterwards read the event: `accepted = false` means the token refused or has no such function.

## Sizing a listing's sell chunk

`sellChunkUsdg` is the most one `takeProfit` or `stopLoss` call **offers** the pool. On an open market it is a
price-quality knob, not a safety one: a sale fills as far as `oracle × (1 − maxSlippageBps)` allows and the rest
stays in the lot, so an oversized chunk cannot brick a sale — it walks the pool to the limit on every call.
Measured (2,400-stock lot, ~500 stock of depth inside 1%, no effective chunk): the treasury fell 55–104 bps short
of the oracle (always ≤ slippage + pool fee), and a caller who merely back-ran their own call earned +107 USDG on
a 0.3% pool, +240 on a 0.05% one. Pushing the pool first earned less.

**The rule: a listing's chunk is no more than the pool's measured depth between the deviation edge and the slippage
limit** — with the shipped gates, the stock the pool takes between −50 and −100 bps of the oracle, in USDG. Not the
depth from the peg: a caller may shove the pool to the gate's edge before calling, and what is left under that is all
a call can count on. A chunk that fits there fills whole even then; one that does not fills short, parks the rule
(below) and pays the caller for it (audit T6-1). Well under that ceiling is better still — about a tenth of the depth
inside the slippage band costs ≈ 5 bps a call. Measured as a self-sandwich (600-stock lot, ~500 stock inside 1%, 0.30%
pool, the attacker shoves to −49 bps before every call): oversized, 3 calls, the treasury 102 bps short, the attacker
+100 USDG before bounty (+89 on a stop); at 2,000 USDG, 34 / 27 calls, 80 bps short, the attacker **−31.6 / −27**.
Never more than slippage + pool fee (130 bps) either way. Set it with the fourth argument of `setListingGates` (below); `0` means the factory default
(2,000 USDG as shipped), anything else must be ≥ `minLotUsdg`, checked when set **and again at launch**: raise
`minLotUsdg` past a listing's chunk and `predict`/`launch` revert `BadRequest` for that stock until you reset it.

- **A big treasury sells by many small calls, not by a big chunk.** There is no cooldown on an open market, so a
  keeper can loop calls inside one transaction; the loop stops itself at the deviation gate, after about the depth
  inside `maxDeviationBps`.
- **A short fill leaves the pool on the limit**, outside the deviation gate: every rule call on that treasury
  reads `Unhealthy` until someone re-pegs the pool. That is arbitrage's job — about 50 bps is on the table — and
  usually takes seconds; if `health()` stays false in open hours with a fresh feed, look at the pool. If it keeps
  happening on one stock, the listing's chunk is too big for today's depth: re-measure and lower it for future
  launches. A launched treasury keeps the chunk it was born with.
- **On the closed-market path the chunk is still a safety knob.** A banded treasury sells one chunk an hour at a
  pool that may be pinned, and each such sale is `min(chunk, depth)`. So a launch with `bandBpsPerHour > 0` is born
  with `min(listing's chunk or the default, the default)`: a listing can lower a banded treasury's chunk, never
  raise it. Keep the **default** sized for the pin, not for price.

## Loosening a listing's gates

`setListingGates(stock, maxDeviationBps, maxSlippageBps, sellChunkUsdg)` gives one stock its own pair of execution
gates in place of the factory defaults (50 / 100 as shipped), and its own sell chunk (previous section), for
**future** launches on that stock. `(0, 0)` clears the pair back to the defaults; the chunk falls back on its own
(`0`), so **every call restates all three** — read the current values first and pass the ones you are not changing. Anything else must satisfy `0 < dev < slip ≤ 300`, the same bounds `setDefaults` enforces. It is
owner-only and never a creator's choice, because **`maxSlippageBps` is the most a sandwich can take from the
holders' treasury on every trade that treasury ever makes**, and a treasury keeps the pair it was born with for
good. Tightening is cheap to decide. Loosening is the most consequential thing the Safe can do to the future holders
of one stock, so:

**No Safe transaction that loosens a listing's gates is signed without a measured basis report attached to it.**

1. **Measure.** Sample the listed pool against its feed over at least two weeks including a weekend, from an
   archive RPC, and replay it under the current and the proposed gates:

   ```bash
   RH_RPC=<archive url> python3 tools/band_backtest.py sample --pool <v3Pool> --feed <stockFeed> --days 14 --step 300 out.json
   python3 tools/band_backtest.py report out.json --label <T>/USDG --max-deviation-bps 50  --max-slippage-bps 100 --out current
   python3 tools/band_backtest.py report out.json --label <T>/USDG --max-deviation-bps <dev> --max-slippage-bps <slip> --out proposed
   ```

   The top panel is the basis — pool vs Chainlink, in bps — and the report says how often the rule could act under
   each pair. For scale, measured: a 1% fee-tier pool sits a median 56 bps from Chainlink; a 0.05% or 0.3% pool
   about 15.
2. **Justify the number, not the direction.** `dev` should clear the pool's ordinary open-hours basis and no more;
   `slip` should clear `dev` plus the pool fee and no more. If the basis is wide because the pool is thin, the answer
   is a different pool or no listing, not a wider gate.
3. **State what it costs creators.** The rule floor moves with it: `tp1`, `dip` ≥ `2 × (slip + pool fee)`, enforced
   in the treasury constructor. At 200 bps on a 1% pool that is 600 bps, and a rule under it fails as an opaque
   `TreasuryDeployFailed()` (`0xb94a14a6`). Tell the front end before the transaction executes — it must read `listingGates(stock)`.
4. **Announce it.** Every launch quoted before the change reverts `Restated` (the gates are in the treasury's
   address, which is in `terms`) — or, if the new slippage lifts the rule floor past the quoted `tp1`/`dip`, as the
   opaque `TreasuryDeployFailed()`, because the constructor runs before the terms are compared (R5-5, accepted). Harmless,
   but a creator mid-launch deserves to know why.
5. **Prepare and sign.** Attach both reports (CSV and PNG) and the sample file's pool, feed, dates and block range
   to the Safe transaction's description.

   ```bash
   cast call $F "listingGates(address)(uint16,uint16,uint64)" $STOCK --rpc-url $RPC   # before: dev, slip, chunk. 0 0 = default gates; chunk 0 = default chunk
   cast calldata "setListingGates(address,uint16,uint16,uint64)" $STOCK <dev> <slip> <chunk>   # data; to = $F, value = 0. Selector 0xc8ed517d
   ```

   `build.py decode` names this call and flags it **DO NOT SIGN in an emergency batch**: it is a configuration
   change, not an emergency lever, and does not belong in one. That is the kit working as intended; sign it as its
   own, reviewed transaction. Afterwards `listingGates(stock)` reads the new values and the factory emitted
   `ListingGatesSet(stock, dev, slip, sellChunkUsdg)`; `build.py status` prints it next to the stock's band ceiling.

It reaches nothing already launched (`test/Emergency.t.sol` asserts a launched treasury's `params()` do not move).
To undo it for future launches, set `(0, 0)` — with the chunk you mean to keep as the fourth argument.

A chunk-only change (pair untouched) tightens or loosens nothing a sandwich can take per trade and needs no basis
report; it needs the depth measurement the chunk was sized from, attached the same way.

## When something is wrong

Go to [`emergency/README.md`](../emergency/README.md). Its first screen is a decision
table. Three things worth knowing before you need them:

- **No lever stops an attack in flight.** Blocks are 0.1 s; a multisig is minutes to
  hours. The levers stop the bleeding afterwards.
- **Do not halt into a real crash** if launched strategies have a stop configured — a halt
  switches `stopLoss` off in every treasury at once.
- **An attack on a token's own pool has no lever at all.** The hook has no pause — and it
  is one hook for every strategy, so a flaw in it is a flaw in all of them at once. Its owner
  can repoint two payout addresses per pool and nothing else; a treasury's owner can point
  its votes and nothing else.

Every signer should run `python3 emergency/build.py decode <file>` on the batch they were
sent: the Safe UI shows raw hex for these transactions, not a decoded call.

## The measurement tools

All read-only (`eth_call`, public GETs), stdlib-only Python, no keys.

| Tool | Purpose | Output |
|---|---|---|
| `tools/listability.py` | which registry tokens pass every listing gate, and why the rest fail | `data/listability.json` |
| `tools/v2_launch_check.py` | V2 listing rule on a pinned fork: can the pool deliver the curve's graduation stock, does that buy keep `health()` inside the gate, is a 0.05% pool's sell chunk at most 10% of its depth per 1%. Must exit 0 before any V2 launch on the stock ([rehearsal item 3](./V2_DEPLOYMENT_REHEARSAL.md#listing-check-first-live-run)) | table, exit code |
| `tools/verify_feeds.py` | feed vs pool vs Lighter mark, feed age | stdout |
| `tools/scan_v3_pools.py` | census of every `<stock>/USDG` V3 pool: price, TVL, active liquidity, liquidity share at a given deposit | `data/v3_pool_census.json` |
| `tools/sample_fees.py` | `feeGrowthGlobal` at both ends of a trading window (archive RPC, cached, resumable) | `data/fee_samples.json` |
| `tools/sample_vol.py` | tick samples across the window → realised variance | `data/vol_samples.json` |
| `tools/rank_pools.py`, `tools/shortlist.py` | fees-vs-adverse-selection ranking, joined with Lighter's perp list | `data/pool_ranking.json`, `data/shortlist.json` |
| `tools/rule_backtest.py`, `tools/band_backtest.py` | replay the treasury's rule, or a staleness band, over a stock's price history (price data is not committed) | `docs/rule-backtest/` |
| `tools/gen_reference.py` | regenerate [REFERENCE.md](./REFERENCE.md) from the compiler's output | `docs/REFERENCE.md` |
| `tools/check_docs.py` | every relative link resolves; the reference is not stale | exit code |
| `emergency/build.py` | owner playbooks → Safe Transaction Builder JSON; `status`; `decode` | `emergency/out/` |

The ranking tools serve a different product (a delta-neutral LP hedged on Lighter,
[`POOL_SELECTION.md`](../POOL_SELECTION.md)); they share the pool census with the
launchpad's listing analysis.

### RPC endpoints

| Endpoint | Use | Limits worth knowing |
|---|---|---|
| `https://robinhood-rpc.publicnode.com` | head state, fork tests | not an archive; free tier may refuse some historical calls |
| `https://rpc-robinhood.blockmachine.io` | historical state (archive) | rate-limits hard (small batches, pause between them); `eth_getLogs` capped at 10,000 blocks inclusive |
| `https://rpc.mainnet.chain.robinhood.com` | full-range logs | no historical state |

Limits change. Read the JSON-RPC error rather than trusting this table.
