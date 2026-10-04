> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# How round 4 was produced, and what it got wrong

Companion to [`00-SCOPE.md`](./00-SCOPE.md) and [`ISSUES.md`](./ISSUES.md). Re-running everything:
[`VERIFICATION.md`](./VERIFICATION.md).

## Two layers, where round 3 had six

Four lanes ran in parallel against `5aedceb`, then triage merged them. **That is all.** Round 3 added an
adversarial pass that treated every finding as false until proved, and a review of the report's rubric and
framing written without the source. **This round ran neither, and ran no context-free lane.** Round 3's
adversarial pass killed that round's most-promoted conclusion and moved its only High; nothing in this report
has faced that test. Every grade here is single-layer. Three grade disputes between lanes (M4-2, L4-2, L4-4), and
two mechanisms one lane filed as safe and another as Medium (M4-1, M4-3), were settled by triage alone.

| lane | what it worked from, as its own report states it | what it owned | reported |
|---|---|---|---|
| engine | every line of `HedgeFunV2EngineTreasury`, `IStrategyPolicy`, `V2RebalancePolicy` and `V2TreasuryDeployer`, and of everything they inherit and call; `docs/STRATEGY_ENGINE.md` for intent only | custody, the policy boundary, the registry, configuration validation, sizes | 11 (0/0/0/2/9); 21 PoCs |
| delta | round 3's findings, rubric and 32 PoCs (branch `audit/round-3-v2-review`) and the five commits since `03ad70e`, the engine excluded | the round-3 ledger, the vault and spike fixes, V1 byte identity, the merge | 6 (0/0/0/1/5); 13 PoCs; round 3's PoCs re-run |
| claims | `docs/STRATEGY_ENGINE.md`, PR #91's and PR #84's descriptions and PR #84's last three commits, the delta's edits to two V2 documents, `abi/SURFACE.md`, `docs/REFERENCE.md`, the engine's NatSpec | whether the code and tests say what the documents say — **by mutation**: break the guard, see whether the suite notices | 73 claims, 41 mutations (22 unnoticed), 12 findings (0/0/0/4/8); 13 PoCs |
| economics | the engine and its inherited trade path, round 3's pool-depth reads, `docs/ADDRESSES.md`, and the project's own `lab/trend.py` (vendored from `research/v2-trend-scenarios` @ `f1af82e`) | manipulation cost, mechanism design, parameter floors, kind 2 against kind 0 | 8 (0/0/3/3/2, the two Infos being safe verdicts); 11 PoCs; two Python models |

The lead's briefs to the lanes are not shipped; the second column is each lane's own account of its scope.
Every lane worked offline: no transaction, one read-only `eth_call` (delta, for I4-10), no fork RPC.

**Triage ran in two sittings, by two agents, neither of which ran a lane.** The first merged the four reports
and wrote `00-SCOPE.md` and `ISSUES.md`, then stopped (spend limit) before this file, `VERIFICATION.md` and the
PR body. The second checked both documents line by line against the four lane reports, re-ran all four
runners and both models, re-measured the full suite and the size table, replayed fifteen of the claims lane's
mutations against the PoCs that claim to catch them, corrected what is listed below, and wrote the rest.

**Every source is a Claude model.** The lanes' commits carry Claude Fable 5.1 trailers and this round's triage
commit carries Claude Opus 5.5's; the author of the code under audit works with Claude as well. As round 3 said,
the independence gained is from information isolation and authorship, not from a second kind of mind.

## What this round got wrong, and what triage corrected

Recorded up front, because a report that lists only its successes cannot be used as an input to the next one.

**One shipped PoC proves nothing, and the report told the fix branch to copy it.** The claims lane says its 13
tests "would have turned the green mutations red", and its replay instructions say that with the nonce check
deleted "C1 fails". It does not: `WrongNonceStrategyPolicy` proposes a buy of `amountIn = 1`, so with the nonce
check gone the engine refuses it on the minimum-lot floor with the same `NotDue` that C1 expects. C1 passes on
the clean tip *and* under the mutation. Triage replayed every claimed pairing: C2, C3, C4, C5, C7, C9 (three
mutations), C10, C11, C12 and C13 each turn red as claimed; C1 does not. A corrected nonce pin — a wrong-nonce
policy proposing an *executable* buy — was run and is in `VERIFICATION.md`. L4-6's fix line now says so, and the
fix branch was told on 2026-09-28. The lane's PoC is left as shipped.

**The economics lane's worst day for a 1 bp band was two orders of magnitude too high, and the first triage
sitting carried it into M4-2.** "$1,300–$3,400 a day on a treasury that need not be larger than $10,000"
assumes every Chainlink print forces a full `maxTrade`. The engine only trades back toward its target, so a
0.5% print forces about 0.13% of value — the lane's own measurement ($14.24 and $12.42 on $9,980). The day is
≈ 0.03–0.09% of value, which is the engine lane's ≈ 0.08%. M4-2 stays Medium on the rubric's "recurring leak"
limb; its figure, its preamble sentence and the grade paragraph are corrected.

**The engine lane named the wrong quantity as the sandwicher's take.** E-2 says "certain gain to a sandwicher:
up to `maxSlippageBps` of each trade". That is the treasury's cost bound. The economics lane measured the
attacker's take as `maxDeviationBps − 2 × poolFeeBps` less impact, which is negative on every 0.30% and 1% pool.
The first triage sitting carried the engine lane's phrase into M4-2's impact line; it is corrected.

**A headline number is not reproducible from the shipped evidence.** M4-1's breakeven — "`maxTrade` ≈ 10.1% of
the pool's USDG-per-1% depth, independent of the depth" — comes from a sweep the economics lane ran and did not
ship. `sandwich_model.py` prints a grid that brackets the breakeven between 5% and 15% of depth. The finding and
its sign are reproducible; the 10.1% is not, and M4-1's fix line now recommends margin below it.

**Corrections the first triage sitting had already made, kept:** the economics lane's "a target of 1 bp
deploys" (the constructor requires `0 < deadband < target`, so 2 bp is the floor); its "~80 bytes of 3,002" for
the floors (constructor code is initcode; the engine lane measured two of them at 0 runtime bytes, +47
initcode); and its "four of twelve live listings are 0.05% pools" (`docs/ADDRESSES.md` records twelve; the
chain has eighteen, and the tier of the other six is unmeasured).

**Bookkeeping errors in the first sitting's `ISSUES.md`, fixed:** a lane ID "X-9" that is the name of an
economics PoC, not a lane finding; round 3's Info tally said "16 unchanged" where its own ledger lists 17
(thirteen not addressed, three accepted by design, one moot); most Infos, and two Lows, had no sentence saying
why the grade was what it was. And one inherited from round 3: its counts table says 35 findings with six
Mediums, but it files seven Medium IDs, M-0 to M-6. The ledger here tracks all 36 IDs and says so.

## Where the lanes disagreed, and whether they contradict

### The engine lane's safe list against the claims lane's UNSUPPORTED list

The engine lane says a guard is **present and correct**, proved by reading and, for most, by its own PoC. The
claims lane says the repository's **suite would not notice its removal**. Those are two different properties,
and for every guard below both statements are true.

| guard | engine lane | claims lane | contradiction? |
|---|---|---|---|
| nonce check (`E:375`) | not on its safe list (item 23 is about the nonce *advancing*, item 3 about a dirty nonce word) | K-4 UNSUPPORTED, `E01` green | no; and neither lane's evidence pins it, since C1 is vacuous |
| policy codehash at execution (`E:394`) | item 12, "codehash pinned four times" | K-5 NARROWER, `E03` green | no — one word, two meanings: the engine lane's "pinned" means *checked at*; the claims lane's means *held fixed by a test* |
| gas bound (`E:400`) | item 16, with its own gas-bomb PoC | K-6 UNSUPPORTED, `E04` green | no — the engine lane's PoC is the pin the repository lacks |
| capability at execution (`E:328,348`) | item 17, with PoC | K-9 UNSUPPORTED, `E08` green | no |
| direction gates (`E:328,348`) | item 18, by reading | K-11 UNSUPPORTED, `E10` green | no |
| oracle/venue health (`E:252-255`) | item 24, citing that "the invariant handler pauses the oracle, stales the feeds and shoves the venue" | K-8 UNSUPPORTED — `E06` and `E07` pass **the invariant campaign too** | **on evidence, yes.** The conclusion stands on the code and the engine lane's own PoCs; the invariant suite, cited alongside them, asserts nothing about the gate |
| configuration bounds (`E:137-139`) | item 26 relies on them; item 27 calls the policy's looser validator harmless *because* the constructor refuses what it accepts | C-4 UNSUPPORTED, `E17` green | no, but a dependency: item 27 is only as durable as L4-9's missing tests |
| registry owner-only, `deploy()` factory-only | item 14, "only the owner registers" | C-3 UNSUPPORTED, `D01`–`D03`, `D05` green | no |

No guard the engine lane calls present is absent. The merged safe list marks the unpinned ones † so the two
properties are never read as one.

### Byte figures quoted by more than one lane

Every contract size quoted by more than one lane agrees with every other lane and with triage's re-measurement
on 2026-09-28: the engine at 21,574 / 27,866 with 3,002 runtime and 21,286 initcode free; `HedgeFunV2Factory`
24,551 with 25 free; `CurveDeployer` 24,564 with 12; `V2TreasuryDeployer` 10,737 / 38,024 with 13,839 / 11,128;
`TreasuryDeployer` 1,001; `V2RebalancePolicy` 1,799. Two things differ, and neither is a measurement disagreement:

- **Fix costs.** The engine lane *measured* its two floors at 0 runtime bytes, +47 initcode. The economics lane
  *estimated* five floors at "~80 bytes of 3,002" — the wrong budget, since the checks run only in the
  constructor. Every other byte cost in the report is an estimate no lane measured: the economics lane's ~150
  (M4-1's spot bound), ~300 (a rolling limiter), ~120 (a bounty), ~250 (a high-water mark), and the delta lane's
  ~40 (a vault getter), ~15 (the `noteEvent` gate) and ~20 (kind 1's scorecard). Treat them as orders of magnitude.
- **`HedgeFunTreasury` against the live V1 build.** The economics lane cites round 3's +55 bytes; at the tip it is
  +74 (the delta's `_notePrice` line adds 19). The argument it supports — the V1 byte-identity objection to
  touching that file is already gone — is unaffected.

### The economics lane's sandwich against the engine lane's gates

The engine lane's safe item 25 says a venue shoved past the deviation gate gives `Unhealthy`, and inside it the
fill costs "at most `maxSlippageBps` — the same bound as V1". The economics lane's M4-1 lives entirely inside
that bound. **These are two true statements, not a contradiction:** the bound holds, and the attacker's room is
where inside it the fill starts. The engine lane itself names the sandwicher as the only paid caller (E-2, E-3)
and filed the question as design. What differs is the grade — safe and Info against Medium — and one quantity,
the attacker's take, where the economics lane's measurement replaces the engine lane's phrase (above). Triage
kept the economics lane's Medium and marks item 25 ‡ in the safe list: the bound is safe, what is inside it is
the finding. The two lanes agree that the pool cannot *trigger* an action (engine item 25, economics §1) and
that closures and `oraclePaused()` fail closed (engine item 24, economics X-3).

## What this round did not do

1. **No adversarial pass, no source-free method review, no context-free lane** (above). What a context-free lane
   exists to catch — the ordinary defect nobody hypothesised: units, packing, event correctness, return values,
   initialisation order — had no dedicated reader. **No source claims to have read all ~910 changed or new
   lines**; the engine lane read its four files and their inheritance in full, and every other lane cites what it
   read.
2. **No live venue.** The 52 `RH_FORK=1` tests, the author's "13/13 low-frequency replays" and the four live-venue
   cases, including the kind-1 lifecycle, are UNMEASURED. Every venue in every PoC is a flat mock or one
   constant-liquidity step, so every slippage and sandwich figure is a bound or a model. Arbitrage between actions
   is modelled as an instant refill, and attacker P&L is gross of gas (economics lane).
3. **No chain re-measurement.** Round 3's depth reads are a day old and moved 10–37% inside round 3's own day;
   the fee tier of six of the eighteen live listings is unmeasured; whether `blockmachine` serves archive state at
   the CI's pinned block is unmeasured (delta lane).
4. **No configuration.** No V2 `Defaults`, engine kind or policy exists on chain. The rehearsal script's values
   were examined as a candidate; the runbook, the rehearsal script's own run, the launch UI, the lab UI beyond its
   diffs and the front end were not audited.
5. **Gaps inside the lanes.** The engine lane traced `HedgeFunHook` and `V2LiquidityVault` only for their calls
   into a treasury. The claims lane mutated `src/v2` only, ran its mutations against the 28-suite V2 subset with
   two full-suite controls, and wrote no PoC for the oracle-live limb of the health gate (`E07`), which is
   therefore unpinned by anything in this round. The delta lane did not read `docs/STRATEGY_ENGINE.md` or run round
   3's fork probes. The economics lane did not cover registry governance, the options reservation, the hook and
   vault beyond `buybackStock`, or the ABI surface.
6. **EIP-7702** is REASONED only; the suite runs at Cancun.
7. **Triage replayed fifteen of 41 mutations**, the ones with a claimed catching PoC; the other 26, round 3's PoCs
   at the tip, the gas-cap-lifted suite and the documentation regeneration checks are the lanes' results, not
   re-run here (`VERIFICATION.md` lists exactly what was).

## What would have made this round say "do not merge"

Stated so that its absence means something. An unprivileged path for a policy, keeper, creator or caller to move
the engine's stock or USDG anywhere but the listed pool's swap callback and the buy-back's `settle()`; an
accounting break between `bookedStock`, `buybackStock` and the balance; any path from this tree to the nine live
V1 strategies; or a regression of round 3's fixes. **None was found**: custody was attacked by two lanes and held;
`HedgeFunFactory` and six other V1 contracts are byte-identical to `main`, and the one V1 contract that differs
(`HedgeFunTreasury`, +74 bytes) matters only to a future V1 re-deployment; and round 3's PoCs, re-run by the delta
lane, fail exactly where its fixes landed and nowhere else.

What was found instead is an engine that is sound in custody and unsafe in configuration: its protective floors
are the creator's to choose, one class of listing pays a sandwicher, its gains never reach the burn and nobody is
told, and half its documented execution checks are pinned by no test — one of them by a test that looks like a pin
and is not.
