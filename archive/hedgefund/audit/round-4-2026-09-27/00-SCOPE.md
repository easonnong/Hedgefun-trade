> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# 00-SCOPE — external audit, round 4: the strategy-engine tip

*Round 4 of an audit track numbered separately from [`AUDIT.md`](../../AUDIT.md). "Author round N" always
means one of theirs. See [`../README.md`](../README.md). Round 3's documents are on branch
`audit/round-3-v2-review` (PR #90, unmerged as of 2026-09-28) under `audit/round-3-2026-09-27/`; where this
report cites them it means that branch.*

## What was audited

| | |
|---|---|
| Ref | **`5aedceb`**, the tip of `origin/codex/v2-strategy-engine` |
| | = PR #84 `codex/v2-main-integration` @ **`9679614`** (→ `main`), merged with PR #91 "bounded strategy engine" (→ `codex/v2-main-integration`) |
| Round 3 audited | `03ad70e`, an earlier tip of the same PR #84 branch |
| Audited | 2026-09-27/28 |
| Rubric | round 3's, unchanged — reproduced in its `FINDINGS-FULL.md` §1 and applied by every lane |

**The merge commit changed nothing of its own** (delta lane, EXECUTED): `git diff 7027539 5aedceb -- src` is
hunk-for-hunk identical to `git diff d5218ee 9679614 -- src`, and the reverse pair likewise. The only files
the merge touched beyond the union are `abi/*.json` and `abi/SURFACE.md`, which regenerate byte-for-byte at
`5aedceb` except their provenance line (I4-9).

### What changed since round 3

```
03ad70e (round 3)
  └─ d5218ee  fix: harden PR84 strategy launch and fork gates      HedgeFunTreasuryBase +5 −1; kind-1 relabel; CI, lab, tools
       ├─ 0d9fca8  fix(v2): isolate LP fee legs, buybacks at flat sell tax    V2LiquidityVault, HedgeFunV2Factory, CurveDeployer
       │    └─ 9679614  docs(v2): align evidence and launch checks      docs only            ← PR #84 tip
       └─ 7252ab2  feat: add bounded V2 strategy engine                    ← PR #91
            └─ 7027539  fix: harden strategy execution and audit gates   one engine check; tools
                 └─ 5aedceb  merge of 9679614 into 7027539               abi/ regenerated
```

**PR #84's delta since round 3 (~40 source lines, four contracts):** round 3's M-0 fix (`HedgeFunV2Factory`
freezes `rates.spikeBps = 0` for every V2 pool), round 3's M-1 fix (`V2LiquidityVault` parks a refused stock
fee in `pendingStockFee` and retries it through a `try this.creditPendingStock()` self-call; `CurveDeployer.predictVault`
deleted to pay for it), one line in `HedgeFunTreasuryBase.buyback()` that refreshes `lastGoodPrice` when the
oracle is live, and comment/label changes (kind 1 goes from "DRAFT" to "Opt-in: production must register its
exact code chunks").

**PR #91, all new (~870 lines):** `HedgeFunV2EngineTreasury` (409) — a third treasury kind that holds a
constant-mix target between the stock and USDG and trades toward it through the inherited V3 path;
`strategy/IStrategyPolicy.sol` (81) and `strategy/V2RebalancePolicy.sol` (107) — the advisory policy the engine
`STATICCALL`s; `V2TreasuryDeployer` +272 lines (a policy registry with codehash pinning, engine kinds, a
per-salt `setEngineConfig`); a 4-line `Action` enum append in `HedgeFunV2Treasury`; `docs/STRATEGY_ENGINE.md`;
`test/V2StrategyEngine*.t.sol` and the invariant suite.

## The deployment reality

**V1 is live on chain 4663** — 9 strategies, 18 listings, read on chain by round 3 on 2026-09-27. **This round
made no chain reads** except one read-only `eth_call` for I4-10, so every depth, listing and pool figure in
this report is round 3's, a day old, and the pool-depth numbers that M4-1 leans on moved 10–37% inside round 3's
own day. **`docs/ADDRESSES.md` records twelve listings; the chain has eighteen** (round 3), which is why the
economics lane's "four of twelve listings are 0.05% pools" is a statement about the document, not the chain.

**Nothing at `5aedceb` can reach the V1 estate.** `HedgeFunFactory`, `HedgeFunToken`, both routers,
`PriceOracle`, `TradingCalendar` and `TokenDeployer` compile byte-identically at `main` (`5c28050`) and at
`5aedceb` (delta lane, EXECUTED). `HedgeFunTreasury` differs from the live 18,289 bytes: 18,363, of which +55
was already in round 3's ref and **+19 is the delta's `_notePrice` line** (I4-8) — this is what a V1
*re*-deployment from this tree would get, and the nine live treasuries cannot take it.

**No V2 contract, no V2 `Defaults`, no engine kind and no policy exist on chain.** The only candidate
configuration is `script/RehearseV2Launchpad.s.sol`'s `_defaults()` (`lpFee 3000`, `minTaxBps 100`,
`maxBuybackImpactBps 300`, `spikeBps 0`, `maxSlippageBps 100`, `maxDeviationBps 50`, `minLotUsdg 5e6`,
`buybackChunkUsdg 500e6`); it is examined here as a candidate and certifies nothing. **Two of the three
Mediums (M4-1, M4-2) and four of the nine Lows (L4-1, L4-2, L4-3, and L4-5 through the choice to register kind
1) live inside parameters or registrations nobody has made yet.** This audit certifies no configuration.

## The remediation budget

Measured by triage on 2026-09-28 from the merged tree (`forge build --sizes`, `optimizer_runs = 1`, `via_ir`
off, `bytecode_hash = "none"`); every figure agrees with the three lanes that measured independently.

| a fix here | is really scored against | bytes free | note |
|---|---|---:|---|
| `HedgeFunV2Factory` | itself (24,551) | **25** | round 3: 27; `rates.spikeBps = 0` cost 2 |
| `HedgeFunBondingCurve` **or** `V2LiquidityVault` | **`CurveDeployer`** (24,564) | **12** | round 3: 176; the M-1 fix cost 164 net of deleting `predictVault` |
| `HedgeFunV2Treasury` (kind 0) | itself; initcode 26,216 is chunked | 2,974 | round 3: 2,993 |
| `HedgeFunV2EngineTreasury` (kind 2) | itself — **runtime** 21,574 | **3,002** | initcode 27,866, chunked; 21,286 under the 49,152 initcode limit |
| `V2RebalancePolicy` | itself | 22,777 | |
| `V2TreasuryDeployer` | itself — **initcode** 38,024 / 49,152 | **11,128** | runtime 10,737 leaves 13,839, but initcode binds first |
| `HedgeFunV2BuybackTreasury` (kind 1) | itself, own chunked initcode | 9,717 | |
| `HedgeFunHook` | itself | 5,222 | unchanged since round 3 |
| `HedgeFunTreasury` (v1) | **`TreasuryDeployer`** (23,575) | **1,001** | round 3: 1,020 |
| `HedgeFunFactory` (v1) | itself | 5,647 | byte-identical to `main` |

Three things about this table that a single contract's own size line hides:

- **Round 3's two effectively-zero budgets are now 25 and 12 bytes.** Nothing can be added to `CurveDeployer`
  or `HedgeFunV2Factory` without first removing something. Round 3's L-1 (delete the dead `graduate(uint256)`)
  is still the only proposal in either round that *adds* factory margin. Nothing in this report proposes a byte
  on either.
- **Constructor-only checks cost initcode, not runtime.** The engine's `_validateEngineConfig` is `private
  view` and called only from the constructor, so every floor this report asks for (M4-2, L4-1) is scored
  against the engine's 21,286 bytes of initcode margin, not its 3,002 of runtime. The engine lane applied two
  of them and measured **0 runtime bytes, +47 initcode**; the economics lane's "~80 bytes of 3,002" for the
  same class of fix costed it against the wrong budget. Mirroring the floors in `setEngineConfig` does cost
  deployer runtime, against 13,839 (initcode 11,128).
- **The engine's runtime margin is real and would mislead.** "3,002 bytes free" is true of the engine and
  says nothing about the release: the contracts that gate every V2 launch have 25 and 12.

## Test state

Round 3 named a trap: at the default 2^30 gas cap the stateful-campaign test truncated and surfaced a
different assertion depending on where it cut, so a first `forge test` read as rule regressions that were not
there. **At `5aedceb` the trap did not fire**: the full offline suite is **104 suites, 1,474 passed, 0 failed,
52 skipped** at default gas (triage, re-run 2026-09-28 04:49 UTC with `--offline`; the claims and delta lanes
independently) and with
`--gas-limit 9999999999` (the delta and engine lanes). The 52 skips are all `RH_FORK=1` fork tests.
`foundry.toml` still sets no `gas_limit`, so the trap is not disarmed, only not sprung at this ref.

Round 3's own 32 offline PoCs **no longer compile verbatim** at the tip (one file calls the deleted
`predictVault`); with that file patched to compute the CREATE2 address locally, **27 pass and 5 fail, and all
five failures are round 3's fixes landing** (delta lane, EXECUTED — the table is in `ISSUES.md`).

## Explicitly NOT covered

- **The live-venue fork suites** (`RH_FORK=1` + an archive RPC; the 52 skipped tests). The author's "13/13
  low-frequency replays" and the four live-venue cases including the kind-1 lifecycle are **UNMEASURED** here.
  The engine against a real V3 pool with real, multi-tick depth is unmeasured: every venue in every PoC is a
  flat mock or a single constant-liquidity step, so every slippage and sandwich figure is a bound or a model,
  not a measurement.
- **Chain re-measurement.** Round 3's M-2/M-3 depth figures were not re-read; the count of 0.05%-tier listings
  among the eighteen is unmeasured; whether `blockmachine` serves archive state at the CI's pinned block
  70,786,980 is unmeasured.
- **The deployment configuration** — see above. No V2 `Defaults`, no listing gates, no engine kind, no
  registered policy exist. The rehearsal script's values are examined as a candidate only.
- **The deployment runbook's execution**, the launch UI, the lab UI beyond the diffs, the front end, and the
  owner's operational procedures. `docs/V2_DEPLOYMENT_REHEARSAL.md` was read for what it promises (the
  round-3 ledger), not run.
- **EIP-7702** behaviour is REASONED only (`evm_version = cancun`).
- **No context-free lane, no adversarial pass, no method review ran this round.** Round 3 had the latter two
  and they killed its most-promoted conclusion. Everything graded here is single-layer on its grade — see
  `README.md`. No source claims to have read every line of the ~910 changed or new lines; the engine lane read
  its four files in full, and every other lane cites what it read.
- `lib/`, formal verification, gas optimisation, and the Robinhood stock token itself — whose issuer can still
  upgrade all 194 tokens from one code-less address with no timelock. Every conclusion is conditional on
  today's implementation.

## Result

| | Critical | High | Medium | Low | Info | total |
|---|---|---|---|---|---|---|
| **everything found at `5aedceb`** | **0** | **0** | **3** | **9** | **14** | **26** |
| only new in PR #91 (the engine, its policy, the registry, its documents) | 0 | 0 | 3 | 8 | 8 | 19 |
| only on PR #84's delta since round 3 (the vault fix, the spike freeze, the base line, the merge) | 0 | 0 | 0 | 1 | 6 | 7 |

By ID: PR #91 is all three Mediums, L4-1 to L4-4, L4-6 to L4-9, I4-1 to I4-5, I4-11, I4-13 and I4-14; PR #84's
side is L4-5, I4-6 to I4-10 and I4-12 (a check `HedgeFunV2Treasury` already had at round 3's ref, untested then
and now). Mixed items are counted where most of them live.

Of round 3's findings (its table says 35; its report files 36 IDs, M-0 to M-6 being seven): **3 Mediums fixed, 1
fixed for V2 with residue, 3 partially; 0 of 6 Lows addressed; 2 Infos fixed, 2 partially, 1 worsened to a Low
here (L4-5), 1 regressed.** See [`ISSUES.md`](./ISSUES.md) for the findings, the
ledger, the merged safe list and the recommended floors; [`README.md`](./README.md) for how the round was
produced and what it got wrong; [`VERIFICATION.md`](./VERIFICATION.md) for how to re-run everything; the four
lane reports in full under [`lanes/`](./lanes/) and their runnable evidence under [`poc/`](./poc/) — 58 Foundry
tests, 41 mutation diffs and two Python models, no network.
