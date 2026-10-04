> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# Development guide

For a developer who has never seen this repository. It gets you from a fresh clone to a reviewed change
without breaking anything permanent. Deploying is a separate document: [DEPLOYMENT.md](./DEPLOYMENT.md).

**The one fact that shapes everything here:** a launched strategy is a token, a treasury and a pool on the one
shared `HedgeFunHook`, with no proxy and no setter for anything but that pool's two payout addresses and whom the treasury's stock votes through (both the factory owner's; see
[SECURITY.md](./SECURITY.md#who-is-trusted-and-with-exactly-what)). Whatever bytecode `main` holds on the day of a launch is that strategy's bytecode for good.
A bug found the day after cannot be patched into it, only avoided in the next launch. Tests and review are the only
patch window this protocol has.

Every command and number below was run on 2026-09-21 with Foundry 1.5.0 against the singleton-hook release
(branch `feat/singleton-hook`, on top of `b03fb03`) — except the fork row of section 3, which needs the network and
was not re-run for this revision.

## 1. Prerequisites

| tool | version | why |
|---|---|---|
| Foundry (`forge`, `cast`, `anvil`) | **v1.5.0**, the version CI pins (`FOUNDRY_VERSION` in [`.github/workflows/test.yml`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/.github/workflows/test.yml)) | `TreasuryDeployer` sits 967 bytes under the contract size limit (`HedgeFunFactory`: 5,626); a different compiler front end can move that. Do not use `nightly`. |
| solc | 0.8.26, fetched by forge (`solc_version` in [`foundry.toml`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/foundry.toml)) | nothing to install |
| Python | 3.x, **standard library only** (tested on 3.12) | `tools/*.py` and `emergency/*.py` import nothing from PyPI. There is no `requirements.txt` and there must not be one. |
| git | any, with submodule support | see below |

```bash
foundryup --install v1.5.0
forge --version        # forge Version: 1.5.0-stable
```

### Submodules: a fresh clone has empty `lib/`

The dependencies are git submodules: `lib/forge-std`, `lib/openzeppelin-contracts`, `lib/v4-core` (which nests
its own `solmate`, `forge-std` and `openzeppelin-contracts`). A plain `git clone`, and **every new
`git worktree`**, leaves those directories empty, and `forge build` then fails on the first import.

```bash
git clone <repo-url> && cd <repo>
git submodule update --init --recursive
```

Run the second line again in every worktree you create.

## 2. Repo map

| path | what lives there |
|---|---|
| `src/` | the contracts, one per file. The launchpad: `HedgeFunFactory.sol`, `HedgeFunDeployers.sol` (the treasury's and the token's CREATE2 deployers -- creation code the factory has no room for), `HedgeFunToken.sol` (the ERC-20, and its launch-time creator's metadata in pons' shape), `HedgeFunTreasuryBase.sol` (the rule, and the vote-only owner), `HedgeFunTreasury.sol` (the stock leg, on a V3 pool -- the only stock venue), and two pieces of periphery the factory knows nothing about: `HedgeFunLaunchRouter.sol` (launch + first buy + first lot in one transaction) and `HedgeFunTradeRouter.sol` (USDG ↔ strategy token in one transaction). Shared with the fund work and used unchanged: `PriceOracle.sol` (stock price in USDG from two Chainlink feeds, fails closed), `TradingCalendar.sol` (the 24/5 NYSE calendar, the only contract here that keeps an owner after launch), `PoolTrader.sol` (V3 execution, both token orderings, TWAP gate) |
| `src/hooks/` | `HedgeFunHook.sol`: the V4 tax hook -- **one** instance serves every strategy, state per `PoolId` |
| `src/interfaces/` | every interface the contracts call through, ours (`IHedgeFunHook`, `IHedgeFunTreasury`, `IHedgeFunToken`, `IOwned`) and other people's (`IUniswapV3`, `IAggregatorV3`, `IStockToken`, `ITradingCalendar`). Nothing declares an interface inline |
| `src/libraries/` | `HedgeFunMath.sol` (`BPS` and the basis-point arithmetic, on OpenZeppelin's `mulDiv`; independent mathematical references and explicit legacy-overflow regressions in `test/HedgeFunMath.t.sol`, explained below), `HedgeFunLimits.sol` (every bound, ONE copy: the factory, the hook and the treasury all read it), `TwapRing.sol` (the hook's per-pool observation ring). A number in a contract is a named constant here or in that contract; the exceptions are the civil-calendar algorithm in `TradingCalendar.sol` and unit words (`1e18`, `1 days`) |
| `test/` | Foundry suites, one line each in section 4 |
| `test/mocks/` | `Mocks.sol`: `MockToken`, `MockFeed`, `MockV3Factory`, a flat-price `MockPool`. Most suites use a **real** local v4-core `PoolManager` instead; the mocks are for feeds and tokens |
| `script/` | `DeployStrategyLaunchpad.s.sol` (the deployment, see DEPLOYMENT.md), `LaunchStrategy.s.sol` (one launch against a listed stock: what a front end does, as a script — rehearsed end to end on a fork) and `V3Survey.s.sol` (read-only: which V3 pools have a real USDG book and a long enough observation ring) |
| `tools/` | read-only Python measurement scripts. `listability.py` (which stocks pass every listing gate), `verify_feeds.py` (feed vs pool vs perp mark), and the pool-ranking pipeline `scan_v3_pools.py` → `sample_fees.py` / `sample_vol.py` → `rank_pools.py` → `shortlist.py`. They sign nothing, but **several rewrite files under `data/`** (`listability.py` overwrites `data/listability.json` on every run, and takes no `--help`). `git checkout -- data/` if you did not mean to refresh a measurement |
| `emergency/` | the Safe's runbook and `build.py`, which writes Safe Transaction Builder JSON for the six emergency levers (and names, but refuses to sign off on, the owner's configuration functions). Never signs. Read [`emergency/README.md`](../emergency/README.md) |
| `data/` | measured inputs checked into git: the token registry (`rh_stock_tokens.json`), Chainlink feed addresses (`chainlink_feeds.json`), pool census, listability. `foundry.toml` grants forge **read-only** access to this directory and nothing else |
| `docs/` | these guides, [`STOCK_TOKEN_ASSESSMENT.md`](./STOCK_TOKEN_ASSESSMENT.md), and `robinhood-chain/`, a mirror of the chain's own developer docs |
| `ref/` | third-party reference source: Pons, PunkStrategy, Fake World Assets, fetched from Sourcify or the project's own repo, indexed by `ref/CLAUDE.md`. **Not compiled into anything.** `foundry.toml` sets `src = "src"` and no file imports from `ref/`; after a full build `out/` contains no artifact from its 16 `.sol` files. Read it, never import it |
| `lib/` | submodules |
| `out/`, `cache/`, `broadcast/` | build output, git-ignored. `broadcast/` and `cache/` appear after a rehearsal deploy |

Root documents: [`README.md`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/README.md) (what the protocol is), [`AUDIT.md`](../AUDIT.md) (every finding, by
id), [`LISTING_CANDIDATES.md`](../LISTING_CANDIDATES.md) (which stocks can be listed, measured),
`POOL_SELECTION.md` (the fund's pool work, background only).

## 3. Build and test

```bash
forge build --sizes
```

`--sizes` prints every contract's runtime and initcode size and **exits non-zero** if any exceeds EIP-170
(24,576 B runtime) or EIP-3860 (49,152 B initcode). The rows to read:

```text
| Contract           | Runtime Size (B) | Initcode Size (B) | Runtime Margin (B) | Initcode Margin (B) |
| HedgeFunFactory    | 18,950           | 22,697            | 5,626              | 26,455              |
| TreasuryDeployer   | 23,755           | 23,783            |   821              | 25,369              |
| HedgeFunTreasury   | 18,520           | 22,955            | 6,056              | 26,197              |
| HedgeFunHook       | 18,362           | 18,647            | 6,214              | 30,505              |
| TokenDeployer      |  9,327           |  9,355            | 15,249             | 39,797              |
| HedgeFunToken      |  7,301           |  8,527            | 17,275             | 40,625              |
| HedgeFunLaunchRouter       |  7,688           |  8,191            | 16,888             | 40,961              |
| HedgeFunTradeRouter        |  5,668           |  6,161            | 18,908             | 42,991              |
```

The tight row is `TreasuryDeployer`, not the factory: it embeds `HedgeFunTreasury`'s creation code, so every byte
added to the treasury or to `HedgeFunTreasuryBase` comes off its 967. (Removing the V4 stock venue gave the factory
back ~2,800 B net; partial fills and the vote hatch took ~390 B from the deployer. The token grew from 1.9 KB to
6.8 KB with its metadata, which is why its creation code moved out of the factory into `TokenDeployer`: the factory
got ~2,900 B back instead of losing ~5,000.) The way out for the treasury is in [ROADMAP.md](./ROADMAP.md): minimal-proxy
clones of one implementation.

### The four ways tests run

| # | command | network | result on `main` today | what it is for |
|---|---|---|---|---|
| 1 | `forge test` | none | **1,420 passed**, 0 failed, **51 skipped** (1,471 tests, 98 suites) | everything that can be proven locally, against a real v4-core `PoolManager` deployed in the test |
| 2 | `RH_FORK=1 RH_RPC=blockmachine forge test --threads 1 --mc "StrategyForkTest\|StrategyMultiPartyFork\|StockTokenFork\|DeployGuardsForkTest\|V2LowFrequencyForkTest\|StrategyForkTestV2LiveVenue" -vv` | live + archive RPC | selects the fork suites; all must pass, 0 skipped | the same contracts against real chain state: real PoolManager, real stock/USDG pools, real Chainlink feeds, and real stock tokens |
| 3 | `FOUNDRY_PROFILE=emergency forge test --mc Emergency` | none | **7 passed** | proves the Python in `emergency/build.py` |
| 4 | `forge test --mt <name> -vvvv` | none | one test, full trace | debugging |

**1. Default.** No environment, no network. The 51 fork tests report `[SKIP]`, not `[PASS]`.

**2. Fork.** The fork suites begin every test with `vm.skip(RH_FORK unset)`. That is deliberate (audit
FA-11): they used to `return` early and report PASS having asserted nothing, including
`test_fork_liquidityIsUnremovable_byAnyone`, the proof that the seeded liquidity can never be withdrawn. They select
the RPC by alias. Legacy head-state suites hardcode `robinhood`, the chain's official endpoint. Pinned V2 suites
read `RH_RPC`; use the allowlisted `blockmachine` archive alias locally, while CI may supply a higher-quota
`RH_ARCHIVE_RPC_URL`. You pass no `--fork-url`. The free archive service returns HTTP 429 after a small compute-unit
budget, so the lab and CI wait for the reset and retry with the same Foundry RPC cache. A 429 is not a contract
failure; a final red run after the bounded retries is. Neither `robinhood` nor `publicnode` can serve the pinned
historical block.

**3. The `emergency` profile.** `foundry.toml` turns `ffi` on for `[profile.emergency]` and for nothing else.
Under the default profile `test/Emergency.t.sol` executes calldata built with `abi.encodeCall` and asserts every
effect and non-effect of each playbook. Under the `emergency` profile it additionally shells out to
`python3 emergency/build.py encode ...` through `vm.ffi`, asserts the Python's output **byte-equal** to the
`abi.encodeCall` expectation, and executes the Python's bytes. Run it whenever you touch `emergency/` or any owner
function. Never enable `ffi` globally: it lets any test run any command on your machine.

**4. Single tests and verbosity.**

```bash
forge test --mc InteractFactory                    # one contract (regex)
forge test --mt test_HK2_ -vv                      # one test (regex); -vv prints console2.log output
forge test --mt test_HK2_aShoveHeld -vvvv          # full call trace, including passing calls
forge test --mp test/AuditTreasury.t.sol           # one file
```

A test name usually matches twice, because most suites are compiled once per token ordering (section 6):

```text
Ran 1 test for test/AuditHookRegression.t.sol:AuditHookRegressionTokenIsCurrency0
[PASS] test_HK2_aShoveHeldForZeroSecondsLeavesNothingInTheMean() (gas: 4733947)
Ran 1 test for test/AuditHookRegression.t.sol:AuditHookRegressionStockIsCurrency0
[PASS] test_HK2_aShoveHeldForZeroSecondsLeavesNothingInTheMean() (gas: 4734142)
```

Many tests print the number they measured (an attacker's profit, a tick delta). `-vv` is how you see it.

### Math behavior and regression tests

PR #44 extracted the strategy arithmetic into `HedgeFunMath` using OpenZeppelin's `Math.mulDiv`. It preserves
the mathematical thresholds and rounding, but intentionally expands the range of inputs that can execute:

- The old take-profit expression added `1e4 + tp1Bps` (or `tp2Bps`) as a `uint16`. Although construction accepted
  the full uint16 rate range, rates from **55,536 through 65,535 bps** made that addition panic when take-profit
  was attempted. The helper widens the rate to uint256, so those thresholds now work. This fixes a prior execution
  failure; it is not literal equivalence to the old checked-arithmetic behavior.
- `mulDiv` also permits an intermediate product larger than uint256 when its final quotient fits. It does not
  make arbitrary inputs safe: the final result, including upward rounding, must still fit uint256; `BPS + rate`
  must fit, and downward calculations require `rate <= BPS`. Production configuration supplies bounded rates.
- `reached` and `short` round the threshold up; `fellTo` and `exceeds` round it down. Their inclusive/strict
  comparisons are checked at the threshold and its adjacent integer, including non-divisible cases.

[`HedgeFunMath.t.sol`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/test/HedgeFunMath.t.sol) keeps a literal legacy uint16 expression to demonstrate the
old panic separately from the intended mathematical rule. Its full-width reference uses quotient/remainder
decomposition rather than `mulDiv`, so the expectation does not share the implementation under test.
[`HedgeFunTreasuryMath.t.sol`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/test/HedgeFunTreasuryMath.t.sol) tests the production treasury at 55,535,
55,536 and 65,535 bps for both take-profit stages and both token orderings. A price one feed unit below the
threshold must be refused; the exact threshold must execute and leave the stock ledger consistent. This fixture
uses a flat-price V3 mock to isolate the threshold and bookkeeping; it does not model AMM price impact or MEV.

```bash
forge test --mc 'HedgeFunMathTest|HedgeFunTreasuryMathTest' --fuzz-runs 10000
```

## 4. The test suites

Test totals change as suites are added. The per-file numbers below are size estimates, not assertions;
several were taken before round 5's fixes landed. For the current count of any file, run `forge test --list`.
Use the test run's summary for passed, failed and skipped totals.

| file | tests | what it is for |
|---|---|---|
| `HedgeFunMath.t.sol` | 14 | all six math helpers, full-width independent references, rounding boundaries, and the intentional legacy uint16 overflow fix |
| `HedgeFunTreasuryMath.t.sol` | 2 | high tp1/tp2 thresholds on the production treasury; each test checks three rates and both token orderings using a flat-price V3 mock |
| `StrategyTreasuryUnit.t.sol` | 18 × 2 orderings | the rule (book, take-profit, dip, stop, buy-back) on the production `HedgeFunTreasury`, its V3 pool a real v4-core pool behind the V3 ABI (`MirrorV3Pool`); holds the short-fill regression a flat mock cannot see (`test_aSellThePoolCannotFullyFill_sellsWhatFits_andTheLedgerFollowsTheStockThatLeft`). Was `StrategyTreasuryV4Unit.t.sol` |
| `StockDecimals.t.sol` | 4 × 5 | a stock token whose `decimals()` is not 18 -- 6 and 8, both orderings, and 18 as the control -- through price, book, take-profit (stock -> USDG) and dip (USDG -> stock), every assertion in dollars and whole tokens. The rest of the suite only ever builds 18-decimal stocks. Hard-coding the stock's decimals to 18 in `HedgeFunTreasury` and `PoolTrader` fails all 16 non-18 cases and leaves the control green |
| `SandboxFakeUsdFork.t.sol` | 6 (fork) | the `FUSD_SANDBOX` entry point shares sandbox v2: synthetic stock and `SandboxQuote`, operator-only mint, bounded price/trade calls, and refusal of non-v2 books. Its deeper-pool rule, tax and pause scenarios remain covered; both sandbox entry points now use test dollars |
| `PartialFill.t.sol` | 8 × 2 | sales fill short: a lot bigger than the pool sells what fits and keeps the rest at cost, tp1 owes what it has not given up, a sale that sells nothing reverts and pays nobody, the closed-market pace is spent only by a sale that happened, re-entry after a short fill, and the measured sandwich of one (shortfall ≤ slippage + fee) |
| `TreasuryVote.t.sol` | 14 × 2 | the treasury's vote-only owner: `owner()` is the factory's read live, follows a two-step handover and remains unchanged when factory renunciation is refused; `setVoteDelegate` on a stock with no `delegate`, a real one, a reverting / garbage / gas-burning / re-entering one; and that the owner has **no other** call — every other selector in the bytecode, sent by the owner, writes nothing |
| `StrategyTokenMetadata.t.sol` | 19 | the token's page: only the `deployer` (the launch-time creator) and its one `editor` write it, the editor can neither appoint nor lock, a lock is for good, the byte caps are checked before any write, the readers have pons' selectors, every change is an event with the whole new value — and that no metadata call moves a balance, an allowance or the supply, the factory that minted the token has no say, and a creator contract that cannot call leaves the entry empty for ever. Reports the gas of the largest possible write |
| `InteractHookTax.t.sol` | 36 × 2 | adversarial: the hook's tax paths, exact-output (a flat-rate buy costs what the exact-input buy costs and its tax is split; everything else is refused), the split, an unpayable recipient (HK-3) |
| `SingletonHook.t.sol` | 11, plus 1 invariant | what only a **shared** hook can get wrong: three strategies on one hook, two of them on the same stock in opposite orderings. A sweep touches only its own pool; an issuer burn scales every parked claim on that stock and nothing else; a donation belongs to no pool; `bind` once, `register` factory-only and once per pool; a treasury reaches only its own ring and spike |
| `SnipeTax.t.sol` | 6 (+ the 14 it inherits) | the buy-side launch window: 99% / 66% / 33% / flat, the launch-transaction exemption and where it ends. **Every test is isolated** — see the convention below |
| `SellChunk.t.sol` | 10 (+ the 18 it inherits) × 2 | `sellChunkUsdg`, per listing and capped for a banded launch: a lot leaves in chunks, tp1's half is fixed when it first fires, a looped caller stops at the deviation gate, odd and one-wei lots |
| `InteractFactory.t.sol` | 47 | adversarial: launch lifecycle, squatting, fee currencies, `Restated` (fee, open price, and every default, gate or listing chunk behind `terms`), liquidity permanence, hostile fee recipient |
| `InteractRuleMev.t.sol` | 23 × 2, plus 7 invariants | what a searcher gains by choosing when and in what order to call the permissionless rule |
| `InteractVenueParity.t.sol` | 22 × 2 | **was** a differential suite (a V3 and a V4 treasury through identical pools had to agree bit for bit) until the V4 stock venue was removed; what is left is every test that states a property of the V3 treasury by itself. The names (`VenueParityBase`, `t3`, `pm3`…) are kept because four other suites build on them. Exports `MirrorV3Pool`, a V3 ABI over a real v4-core pool |
| `AuditFactory.t.sol` | 12 | audit findings FA-*: what the owner can and cannot reach, deployer binding, `setDefaults` bounds; disabled renunciation, two-step vote-authority handover and pending-owner cancellation |
| `AuditHookRegression.t.sol` | 41 × 2 | audit findings HK-1, HK-2, HK-4, written the way each was found, asserting it no longer reproduces |
| `AuditLedgerRound4.t.sol` | 9 (+ the 36 it inherits) × 2 | round 4 on the ledger, L4-*: re-entry from inside a payout, a deny-listed treasury, the gas-starved sweep (L4-3: at no gas limit is tax redeemed and owned by nobody) |
| `AuditOwnerRound4.t.sol` | 12 (+ 36 inherited), plus 1 invariant | round 4 on the owner's two payout powers, O4-*: re-entering owner, the accept window, the veto as proof of life |
| `AuditRouterRound4.t.sol` | 20 (+ the 8 it inherits) | round 4 on `HedgeFunLaunchRouter`, R4-*: the launcher must be the creator, forged callbacks, nested unlocks, exact `minTokensOut` |
| `AuditTradeRouter.t.sol` | 9 (+ the 8 it inherits) | the adversarial pass on `HedgeFunTradeRouter`, ids T5-* (the findings live in this file's comments; `AUDIT.md` has no section for them): a stock that calls back, a pool posing as the factory's, the all-or-nothing V3 hop (`PartialFill`), nothing left in the router |
| `AuditRound5Singleton.t.sol`, `AuditRound5Tax.t.sol`, `AuditRound5Treasury.t.sol` | `forge test --mc AuditRound5`: 255 passed. The number is large because each file inherits its harness's tests and runs them again; per file, run `forge test --list` | round 5, S5-* / X5-* / R5-*, now regression suites: each fix's test was confirmed to fail with the fix reverted (the two exceptions are named in the banner), and the `test_holds_*` tests record something that was attacked and held. The table of outcomes is the banner at the top of `AUDIT.md` |
| `AuditRound6Treasury.t.sol` | 12 × 2 | round 6, T6-*: partial fills, the per-listing chunk, the vote-only owner, the V4 venue's removal. Stateful campaigns over the ledger (`tp1Left` never outlives the lot, nothing unaccounted); the measured self-sandwich of looped short fills, take-profit and stop; T6-1 characterised (a short fill parks the rule and pays its caller); the T6-2 regression (a dust tail does not spend the closed-market hour); T6-3 characterised (a lot due at the stale print sells unpaced); the TR-1 bound (49 sales in 48 hours); and **the treasury's ABI pinned at 52 selectors** (T6-4, below) |
| `AuditTreasury.t.sol` | 17, plus 2 × 2 thin-pool | audit findings TR-*: the closed-market pin (TR-1), cost basis, execution floor, the calendar override |
| `TradingCalendar.t.sol` | 8 | NYSE holidays, DST boundaries, the 20:00 ET session roll, checked against independently looked-up dates |
| `DeployScriptGuards.t.sol` | 23, plus 1 fork | the deploy script's refusals on chain 4663 (FA-7), the `LP_FEE` refusal (FA-5), and the hook-salt miner |
| `HedgeFunLaunchRouter.t.sol` | 13, inherited ones included | the router against the real factory, hook, treasury and PoolManager: one-tx launch + first buy + first lot, fee forwarding, weekend seeds, no residue |
| `TradeRouterFork.t.sol` | 3 (fork) | USDG -> GMESTR -> USDG against the live GME pools: listed on the 0.05% pool, routed through the 1% one; buy tax held for burning, sell tax to the treasury, the opening spike applies, nothing left in the router; refuses a thin quote, a stale one, a pool that is not the factory's, and a callback from outside its own swap |
| `SandboxFork.t.sol` | 12 (fork) | sandbox v2 with owner-controlled stock and a valueless test dollar: the full V3/V4 rule, original public-mint exploit replay versus its fix, real USDG unchanged, atomic price rollback, V3 exit, ten-dollar budget, and legacy deployment rejection. See [sandbox runbook](./SANDBOX.md) and [incident audit](./SANDBOX_AUDIT.md) |
| `SandboxSecurity.t.sol` | 9 | offline adversarial coverage for explicit CREATE2 ownership, mint/control permissions, canonical callbacks and cumulative input limits, failed token transfers, feed rollback, and withdrawal bounds; both token orderings |
| `SandboxLaunchBundle.t.sol` | 5 | owner-only, single-use atomic hook/deployer/factory deployment; failed binding leaves no partially deployed components |
| `Emergency.t.sol` | 7 | every emergency playbook executed as the Safe; also asserts what the Safe **cannot** do |
| `StrategyFork.t.sol` | 6, fork | a full strategy life on real chain state (NVDA on its V3 pool), all three fee currencies, the permanence proof |
| `FirstBatchFork.t.sol` | 1, fork | the first batch's rules (from `docs/rule-backtest`) against the live chain: each feed prices its stock, each pool is the right tier, each rule clears the constructor's floor |
| `StrategyMultiPartyFork.t.sol` | 7, fork | several independent parties against one live launch |
| `StockTokenFork.t.sol` | 13, fork | the real NVDA token: pause, deny-list, `adminBurn`, multiplier, and the pinned-implementation snapshot |

Two stale pointers you will meet in comments: `AuditTreasury.t.sol` refers to `AUDIT_TREASURY.md` and `AUDIT.md`
refers to `test/AuditHook.t.sol` and `test/AuditHookLaunch.t.sol`. None of the three exists; the findings are all
in `AUDIT.md` and the hook regressions are in `AuditHookRegression.t.sol`.

### Four conventions you will trip over

**0. Anything that depends on the launch transaction must run isolated.** The creator's exemption from the launch
window is **transient storage** — the pool id and the launcher's address — which `register` sets and the EVM clears
when the transaction ends. A forge test is otherwise *one* transaction, so without isolation the flag never clears:
every later buy whose swap `sender` is the launcher still looks exempt, and "the exemption ends with the launch
transaction" cannot be tested at all. (Since X5-1 a stranger's swap through another router is charged the window
either way; it is the launcher's own later buys that leak.) Put this above each such test, as every test in
`SnipeTax.t.sol` has it:

```solidity
/// forge-config: default.isolate = true
function test_aStrangersBuyInTheLaunchSecond...() public {
```

With `isolate` each top-level call in the test is its own transaction. Do not turn it on globally: it is slower, and it
changes the gas figures other suites print.

**1. A regression test names the bug, and was seen to fail without the fix.** Test names are sentences about
behaviour (`test_aShoveHeldForZeroSecondsLeavesNothingInTheMean`), and every fix in `AUDIT.md` carries the note
"confirmed to fail with its fix reverted". A test that has never failed proves nothing. For a new fix:

```bash
# 1. with your fix in place, the new test passes
forge test --mt test_yourNewTest -vv
# 2. revert ONLY the src/ change, keep the test
git diff origin/main -- src/ > /tmp/fix.patch
git apply -R /tmp/fix.patch
forge test --mt test_yourNewTest -vv      # must FAIL, and for the reason the test names
# 3. restore the fix
git apply /tmp/fix.patch
```

(Commit first if your diff against `origin/main` holds more than the fix, and diff against that commit. Avoid
`git stash`: the stash is shared across worktrees, and other sessions use it.) If step 2 passes,
the test does not test the fix. Say in the PR that you ran this check.

**2. `test_BUG_*` means "passes while a known bug is present".** Such a test asserts the *bad* behaviour, so it is
green while the bug exists. It is a way to pin a reproduction before the fix lands. CI fails on any function
matching `function test(Fuzz|Fail)?_?BUG_` under `test/`, so one can never reach `main`: fix the bug, flip the
assertions, rename the test to state the fixed behaviour. There are none on `main` today.

**3. Prefixes map to [`AUDIT.md`](../AUDIT.md).** `test_audit_*` (factory and owner findings, FA-*),
`test_HK1_` … `test_HK4_` (hook), `test_TR1_` and `test_F1_` … `test_F6_` (treasury, oracle, calendar; the `F`
numbers are the treasury auditor's own working ids, so match one to a TR finding by what the test name says), `test_S*` (things checked and found
sound), `test_mainnet_*` / `test_rehearsal_*` (deploy-script guards on chain 4663 and off it), `test_fork_*`
(needs `RH_FORK=1`). When you read a finding, grep its id under `test/` to find its proof.

## 5. Solidity constraints that bite here

The project compiles with `optimizer = true`, `optimizer_runs = 1`, `evm_version = "cancun"` (the hook's
launch-transaction flag needs Cancun's `TSTORE`/`TLOAD`), and **without `via_ir`**. Do not turn `via_ir` on to get
past an error: it changes every contract's bytecode and size.

| constraint | symptom | what to do |
|---|---|---|
| **`TreasuryDeployer` is 23,609 B: 821 bytes under EIP-170**, with the optimiser already at its size-minimising setting; it is the treasury's creation code plus a few hundred bytes, so that is what the treasury has left. `HedgeFunFactory` is 18,107 B / 6,469 (it was 765 until the V4 stock venue came out, 3,574 until the token's creation code moved to `TokenDeployer`) | `forge build --sizes` exits non-zero with a negative margin. `forge test` does **not** catch it | run `forge build --sizes` before and after **any** change to `HedgeFunFactory.sol`, to `HedgeFunToken` (embedded by `TokenDeployer`, 15.7 KB to spare), and to `HedgeFunTreasury`/`HedgeFunTreasuryBase` (embedded by `TreasuryDeployer`). Put the margin in the PR. The next sizeable change to the treasury means making room first |
| **The treasury's external ABI is pinned: 52 selectors, nine non-view, one owner-privileged** (`test_holds_theAbiIs52Selectors_allVisibleToThePush4Walk_nineNonView_ownerPrivilegedInOne` in `test/AuditRound6Treasury.t.sol`). `TreasuryVote`'s "every selector in the bytecode" closure test walks `PUSH4` constants only, and solc emits a selector with a leading zero byte as `PUSH3` — one in 256 — so a state-changing function behind one would be invisible to it and the test would stay green (audit T6-4) | none until it matters: a new external function passes the closure test without being examined | **adding any external function to the treasury must update that pin deliberately**, in the same PR, saying who may call it; if its selector starts with `0x00`, rename it. Get the list from `forge inspect HedgeFunTreasury methodIdentifiers` |
| **`Stack too deep` from a `public` struct state variable** with more than about 12 fields: the auto-getter returns every field as a separate stack value | `Compiler error: Stack too deep ... Variable value0 is 2 slot(s) too deep` (reproduced with `HedgeFunFactory.Request public req;`) | keep it `internal` and expose a function returning the struct in memory. That is why the factory has `Defaults internal defaults` plus `getDefaults()`, and why `test/InteractFactory.t.sol` declares `Request internal req` |
| **`treasury.params()` is a hand-written getter.** `Params` has 14 fields; as a `public` struct its auto-getter was one slot past the stack, so the struct is `internal _params` with `params() returns (Params memory)`. The ABI encodes that as the same 14 words in the same order — same selector, `bandBpsPerHour` still last, where the emergency kit reads it | none today; it bites if you make it `public` again or reorder a field | in Solidity use `treasury.params().minLotUsdg`; never reorder `Params`, and append new fields **before** `bandBpsPerHour` (`Emergency.t.sol`, `_tradesClosures`, reads the last word of the raw return data). Older tests rebuild the expected struct instead (`InteractRuleMev.t.sol`, `_minLotUsdg`) — that predates the getter and still works |
| **`lots(i)` returns four values** `(qty, cost, half, tp1Left)` since the sell chunk. `tp1Left` was appended last so the first three keep their positions | a three-value destructure of `lots(i)` no longer compiles | add the fourth slot: `(uint256 qty, uint256 cost, bool half,) = treasury.lots(i);` |
| **Wide struct literals.** `Request` has 15 fields, `Defaults` 22, `Params` 14. A literal evaluates every field onto the stack at once | a literal on its own does compile (the deploy script has a 22-field one), but it leaves no room for anything else, and the error appears when you later add a local variable or parameter to that function | build these structs by **field assignment** into a named return, as every test helper does: `_defaults()` and `_req()` in `test/InteractFactory.t.sol`. It never fails and the diff is one line per field |
| **`launch()` is one stack slot from the limit** | adding a parameter to `launch(Request, bytes32)` does not compile | new launch inputs go **inside `Request`**. That is why `maxFee` and `expectedOpenPriceE18` are struct fields and not arguments. The second argument is `terms`, the hash `predict(q)` returned |
| **A constructor's revert reason does not survive CREATE2.** `TreasuryDeployer` and `TokenDeployer` use assembly `create2`, which returns `address(0)` on failure and discards the reason | a launch reverts `TreasuryDeployFailed()` (selector `0xb94a14a6`; the string `treasury deploy` until 2026-09-21) and nothing else, whatever the actual cause | `HedgeFunFactory._setDefaults` and `setListingGates` **mirror every bound the treasury constructor enforces**, so a bad value is refused with `BadRequest` when it is set, not at every later launch. If you add or tighten a constructor check, mirror it there in the same PR and add a case to `test_audit_setDefaultsRefusesWhatAConstructorWould`. Creator-chosen fields can still fail this way; see the troubleshooting table. (The hook is not deployed by a launch any more: its bounds are checked by `register`, whose custom error does survive — and are mirrored in `_setDefaults` anyway, because a default that fails there fails every launch) |
| **The hook's address is its permission set.** V4 reads a hook's permissions from the low 14 bits of its address; `HedgeFunHook`'s constructor reverts `BadConfig` unless `address & 0x3FFF == 0x2844` (`BEFORE_INITIALIZE \| BEFORE_ADD_LIQUIDITY \| AFTER_SWAP \| AFTER_SWAP_RETURNS_DELTA`) | the hook's deployment reverts | **mine** the CREATE2 salt, once per hook: about 16,384 tries on average. See below |
| **A hook binds once.** `bind()` sets `factory` for good, and `HedgeFunFactory`'s constructor calls it | a second factory built on the same hook reverts `AlreadyBound` | a suite that deploys N factories deploys N hooks |

### Deploying the hook in a test, and the `terms` a launch needs

Nothing is mined per launch any more. A suite deploys **the** hook once, through `test/utils/HookMiner.sol`
(`_deployHook(pm)` — the same CREATE2 search the deploy script does, with a cursor so a second hook does not
re-walk the first one's salts), and hands it, unbound, to the `HedgeFunFactory` constructor. Every launch is then:

```solidity
(,, bytes32 terms) = factory.predict(q);
uint256 id = factory.launch(q, terms);
(, address treasury, address hook,,) = factory.strategies(id);
PoolId pid = HedgeFunHook(hook).poolOfTreasury(treasury);      // every hook getter and action takes this
```

`terms` commits to the predicted token and treasury addresses — which commit to the `Request`, the listing, the
listing's gates and every treasury default — and to `lpFee`, `tickSpacing`, the rates, and the launch fee's
currency and amount. **Change any field of the request, any default, the listing or its gates, and the `terms` are
void** (`Restated`). Call `predict` last.

**`vm.prank` the creator.** `launch` reverts `BadRequest` unless `msg.sender == q.creator` or the sender is a
launcher the owner vouched for; a suite that launches through `HedgeFunLaunchRouter` first does
`vm.prank(safe); factory.setLauncher(address(router), true);`. And compute `terms` in its own statement: `_terms`
calls `predict`, and a `vm.prank` or `vm.expectRevert` armed before it is spent on that call, not on `launch`.

## 6. Chain facts that change how you write code and tests

| fact | consequence |
|---|---|
| **Blocks are about 0.1 s** (measured: 10,000 blocks in 1,011 s) | anything "per block" happens ten times a second. PunkStrategy decays its sell spike per block; here that would be over before anyone saw it, so the spike is timed in **seconds** (`spikeSeconds`). Think in `block.timestamp`, never `block.number`. A one-second window is ten blocks, which is what HK-2 exploited |
| **USDG has 6 decimals, stock tokens 18** | every price conversion carries a `1e30` scale (`SCALE` in the tests). A feed answer has 8 decimals on top. Unit mistakes here produce numbers that look plausible |
| **Token ordering varies per pool.** V3 and V4 sort by address; USDG is token0 in some `<stock>/USDG` pools and token1 in others. A launched `<token>/<stock>` pool can fall either way too | assuming one ordering reads as "no liquidity" with no error; that bug shipped twice in the parent repo. **Every suite runs both orderings**: an abstract base holds the tests and two concrete contracts pick the ordering by CREATE2-mining the mock token's address (`...StockCurrency0Test` / `...UsdgCurrency0Test`, `...TokenIsCurrency0` / `...StockIsCurrency0`). Put new tests in the base |
| **Chainlink equity feeds are 24/5.** They publish on a 0.5% deviation. The directory advertises an 86,400 s heartbeat, but **no heartbeat fires off-hours**: across a weekend the feed returns Friday's close for about 65 hours, and `latestRoundData()` does not revert | `updatedAt` is the only liveness signal. There is no L2 sequencer uptime feed on this chain. `PriceOracle.tryPrice()` fails closed on the calendar, `oraclePaused()`, and age. On a quiet day a feed can also sit for hours inside the 0.5% band (AUDIT TR-4). In tests, move `MockFeed` and `vm.warp` together or you will be testing staleness by accident. `src/PriceOracle.sol`'s header still says "a 24h heartbeat"; the measurement in `AUDIT.md` supersedes it |
| **The feed answer already includes the token's `uiMultiplier()`** | never multiply by it again; that double-counts every corporate action |
| **Feed `description()` strings come in three formats**: `RHNVDA / USD`, `Robinhood AAPL / USD`, `Robinhood SGOV-USD`. Chainlink's directory calls the NVDA feed `Robinhood NVDA / USD` while the contract itself answers `RHNVDA / USD` | never look a feed up by name. **Resolve by address** from `data/chainlink_feeds.json` and check it with `python3 tools/verify_feeds.py NVDA` |
| **Every stock token is a `BeaconProxy` on one beacon** that a single address can upgrade with no timelock | conclusions about token behaviour (no transfer callback, no fee) hold for the implementation pinned in `StockTokenFork.t.sol` and nothing else. See [STOCK_TOKEN_ASSESSMENT.md](./STOCK_TOKEN_ASSESSMENT.md) |

## 7. Making a change safely

1. **Never push to `main`.** Branch, in a worktree, and open a PR:

   ```bash
   git fetch origin
   git worktree add ../launchpad-my-change -b fix/my-change origin/main
   cd ../launchpad-my-change && git submodule update --init --recursive
   ```

   Other sessions work this repository concurrently. Re-read the PR and `origin/main` before you act on either.
2. `forge build --sizes`, `forge test`, the fork suite, and the `emergency` profile if you touched `emergency/` or
   an owner function.
3. For a fix: the revert check from section 4.
4. Open the PR. State the factory's new size margin if it moved.

### How much review does a change need?

Ask what the change can still reach after a launch.

| you are changing | who is affected | can it be corrected later? | review |
|---|---|---|---|
| `HedgeFunHook` | **every strategy, at once**: there is one instance, the factory's `hook` is immutable, and its address is what a router allowlists | **never**. A corrected hook is a new hook, a new factory, new addresses and a new allowlist review; every strategy already launched stays on the old one | adversarial review, a regression test seen to fail, fork suite, a line in `AUDIT.md`, and a full deployment rehearsal |
| `HedgeFunToken`, `HedgeFunTreasury*`, `TwapRing`, `PoolTrader`, and the bytecode the factory deploys | every strategy launched from that commit on | **never**, for anything launched before the correction | adversarial review, a regression test seen to fail, fork suite, and a line in `AUDIT.md` |
| `HedgeFunFactory` itself, `PriceOracle`, `TradingCalendar` | the deployed instance is immutable; a change means a **new deployment**, new addresses, a new emergency kit — and, for the factory, a **new hook** (a hook binds once) | only by redeploying; strategies launched from the old factory stay on the old oracle and calendar | as above, plus a full deployment rehearsal |
| factory **defaults**, **listings**, **band ceilings** and **per-listing gates** (owner transactions, not code) | future launches only. A strategy is born with a copy of the values of that moment | yes for the future, never for the past | the Safe's signers; rehearse on a fork; a loosened gate needs a measured basis report ([OPERATIONS.md](./OPERATIONS.md#loosening-a-listings-gates)) |
| `script/`, `tools/`, `emergency/`, docs, CI | nobody on chain | freely | normal review. `emergency/` additionally needs the `emergency` profile green |

### What CI runs

[`.github/workflows/test.yml`](https://github.com/keyuyuan/hedgefund/blob/48a41e2d53c8d24505e3313ae01a01c153b9e721/.github/workflows/test.yml), on every push, every pull request, and **daily at
06:17 UTC**. Foundry is pinned to `v1.5.0`.

| job | what it does | fails when |
|---|---|---|
| `unit` | checkout with recursive submodules, `forge build --sizes`, `forge test` (no `RH_FORK`, so the fork tests are reported skipped here) | any contract is over a size limit; any test fails |
| `fork` | `forge build`, then the required fork suites with `RH_FORK=1`, one test thread and an archive RPC (`RH_ARCHIVE_RPC_URL`, falling back to `blockmachine`). Explicit 5000 and 7000 LP-share live-venue replays run serially. Only an HTTP 429/rate-limit failure is retried, at most eight attempts with 65 s resets; the job has a 45-minute budget. Push/PR fork jobs for the same branch share a concurrency slot | any non-rate-limit test failure (immediate); exhausted 429 retries; **any `[SKIP]`**; missing permanence/snapshot/low-frequency/sandwich/tight-minOut/lifecycle/kind-1 proof; or a requested/frozen LP share other than the pinned 5000/7000. It is not `continue-on-error` |
| `no-known-bug-tests` | greps `test/` for `test_BUG_*` function definitions | one exists |

The daily run exists for one test, `test_fork_snapshot_beaconProxy_pinnedImplementation_andRoles`. It pins the
stock token implementation's code hash and role holders. The issuer can replace the code of all 194 stock tokens in
one transaction, and nothing in this repository would otherwise notice. The day that happens the scheduled run goes
red with no commit of ours involved. Treat that as an incident: re-run the assessment before the next listing or
launch.

## 8. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| `forge build` cannot resolve `forge-std/...`, `v4-core/...` or `@openzeppelin/...`; `lib/*` directories are empty | fresh clone or new worktree | `git submodule update --init --recursive` |
| `Stack too deep` | section 5: a public struct getter, a new `launch` parameter, or a local added beside a wide struct literal | keep wide structs `internal` with a memory getter; build them by field assignment; put new launch inputs in `Request`. Do not enable `via_ir` |
| `forge build --sizes` exits non-zero | a contract crossed EIP-170 or EIP-3860, almost certainly `HedgeFunFactory` | shrink or split. There is no flag that helps; the optimiser is already at `runs = 1` |
| a launch reverts `TreasuryDeployFailed()` (`0xb94a14a6`) | a creator-chosen rule field failed a treasury constructor check. The usual one (TR-3): `tp1Bps` and `dipBps` must each be at least `2 × (maxSlippageBps + pool fee in bps)`, which is **210** on a 0.05% pool and 260 on a 0.30% pool with the shipped 100 bps slippage — **and moves if the owner has given the stock its own gates**: read `factory.listingGates(stock)` first. Also `tp2Bps` must be 0 or greater than `tp1Bps`; `lotBps` in 1…10000; `stopBps` under 10000 | fix the field, call `predict` again for fresh `terms` |
| a launch reverts `TokenDeployFailed()` (`0x3e11a3a5`; **no reason at all** before the token moved to `TokenDeployer`) | the same `(symbol, creator, nonce)` already launched: the token's CREATE2 address is occupied, which fails before the treasury deploy. The token's constructor has no other way to refuse | bump `nonce`, call `predict` again |
| `predict` or `launch` reverts `BadRequest` for one stock only, and the request is in bounds | the listing's `sellChunkUsdg` is under the current `minLotUsdg`: it was checked when set, and the default has been raised since | the owner resets the chunk with `setListingGates` (OPERATIONS.md) |
| a launch reverts with selector `0x5945191f` (cast may print a garbled `YE`) | `Restated()`: `maxFee` is below the current launch fee, `expectedOpenPriceE18` differs from the listing, or the `terms` you passed are not what the factory computes now — a default, the listing, its gates or a field of the request changed since `predict` | re-read `getDefaults()`, `listings(stock)` and `listingGates(stock)`, show the launcher what changed, and call `predict` again. `cast sig "Restated()"` confirms the selector |
| a launch fails with **status 0, all gas consumed and empty revert data**, and the same call passes in `cast call` | it was sent with exactly the node's `eth_estimateGas` figure. Measured on a fork, 2026-09-21: estimate 5,874,408, failed using 5,863,564; identical call with headroom used 5,752,452. Borderline, not systematic (three later launches passed at their estimate): a launch deploys a ~18 KB treasury and a ~7 KB token three call frames deep, each frame keeps 1/64 of the gas, and the estimate is against a different block. On the final code the estimate is 6,955,894 and 1.25× of it used 6,830,498 | `cast send … --gas-limit 12000000`; a front end sends at least 1.25× the estimate. Unused gas is refunded ([DEPLOYMENT.md section 8](./DEPLOYMENT.md#8-a-launch-from-a-front-ends-point-of-view)) |
| a launch reverts `BadRequest` though every number is in bounds | the sender is not `q.creator`, and is not a vouched launcher (X5-2). Through `HedgeFunLaunchRouter`: the owner never called `setLauncher(router, true)` | launch from the creator's address; or have the Safe vouch for the router |
| a swap reverts `ExactOutputRefused` | an exact-output sell (always), or an exact-output buy while the launch window holds the buy rate above the flat tax. A sell spike does not refuse a buy: the buy rate is flat then | quote it as exact input |
| a swap or `sweep` on the hook reverts `WrongPool` | the `PoolId` is not one the factory registered (wrong `lpFee`/`tickSpacing`/ordering in the key, or an id from another deployment) | `hook.poolOfTreasury(treasury)`, or `keccak256(abi.encode(currency0, currency1, lpFee, tickSpacing, hook))` with the currencies in address order |
| a launch-window test sees the flat tax where it expected 99% for the launcher's second buy | the test is one transaction, so the launch-transaction exemption never ended | `/// forge-config: default.isolate = true` above the test (section 4) |
| fork tests show `[SKIP]` | `RH_FORK` unset | `RH_FORK=1 forge test --mc "StrategyForkTest\|StrategyMultiPartyFork\|StockTokenFork"` |
| head-state fork tests fail with HTTP 429, a timeout or a connection reset | the free public endpoint throttled or dropped the run | wait and re-run against the `robinhood` alias before debugging the contract |
| a pinned V2 fork fails with HTTP 429 from `blockmachine` | the free archive endpoint exhausted its 60-CU/minute budget | keep Foundry's global RPC cache, wait for the reset and retry; the lab does this within its timeout and CI makes up to eight cached attempts, preferring the higher-quota `RH_ARCHIVE_RPC_URL` secret when configured |
| HTTP 403 `Archive requests require a personal token` (publicnode) or `historical state ... is not available` (the chain's own RPC) | you asked for state at an old block. **Neither public endpoint is an archive node.** Measured: the chain's own RPC served state about 4,100 blocks (7 minutes) back and refused it 7,600 blocks (13 minutes) back; publicnode refuses any historical state | for historical reads use `https://rpc-robinhood.blockmachine.io`, the endpoint `tools/scan_v3_pools.py` and `tools/sample_fees.py` use. It rate-limits hard: pace requests. It also means a long-lived `anvil` fork of the chain's own RPC loses the ability to fetch state it has not cached; restart it rather than debug it |
| `vm.ffi: FFI is disabled; add the --ffi flag` | a test calls `vm.ffi` under the default profile | `FOUNDRY_PROFILE=emergency forge test --mc Emergency`. Do not add `ffi = true` to the default profile |
| `git status` shows `data/listability.json` or `tools/__pycache__/*.pyc` modified after running a tool | the tool rewrote its output; the `.pyc` is tracked in git by accident | `git checkout -- data/ tools/__pycache__` unless you meant to refresh the measurement |
