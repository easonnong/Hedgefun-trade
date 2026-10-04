# Documentation

Current organization entry points: [operations](../../docs/OPERATIONS.md), [contract scope](../../docs/CONTRACT_SCOPE.md) and [audit index](../../audit/README.md). New deployments recommend a 1% base fee; historical evidence retains its original parameters. Older security and operations documents below are archived source records.

Developer documentation for the strategy-token launchpad on Robinhood Chain. Everything
here is plain Markdown with relative links, so it reads the same on GitLab, GitHub or a
local checkout. Diagrams are [Mermaid](https://mermaid.js.org/), which both render
natively.

## Start here

| If you want to… | Read |
|---|---|
| understand what this is and how the pieces fit | [ARCHITECTURE.md](../../archive/hedgefund/docs/ARCHITECTURE.md) |
| integrate V2 curve launches, graduation and multi-asset trading | [V2_BONDING_CURVE.md](./V2_BONDING_CURVE.md) |
| trace user, keeper and admin entries for V2 state-sequence testing | [V2_ACTOR_FLOW_FUZZ_MAP.md](./V2_ACTOR_FLOW_FUZZ_MAP.md) |
| select the optional Cycle kind and follow its bounded recovery entry | [V2_SIMPLE_CYCLE.md](./V2_SIMPLE_CYCLE.md) |
| review Cycle integration with current dust handling and its test evidence | [V2_CYCLE_INTEGRATION_REVIEW.md](./V2_CYCLE_INTEGRATION_REVIEW.md) |
| integrate V2 buy/sell fee income and token-fee conversion | [V2_TWO_SIDED_FEES.md](./V2_TWO_SIDED_FEES.md) |
| review V2 multi-user trading, callback defenses and economic boundaries | [V2_ADVERSARIAL_REVIEW.md](./V2_ADVERSARIAL_REVIEW.md) |
| review V2 configurable graduation funding and fee-vault risks | [V2_DUAL_ENGINE_REVIEW.md](./V2_DUAL_ENGINE_REVIEW.md) |
| click through V2 allocation scenarios and rerun the pinned fork locally | [lab/README.md](../lab/README.md) |
| replay multi-wallet buy, sell, mixed, and opening-sniper scenarios | [V2_MARKET_SCENARIOS.md](./V2_MARKET_SCENARIOS.md) |
- [V2_LP_DEPTH_EXPERIMENT.md](V2_LP_DEPTH_EXPERIMENT.md) — LP share vs sale share: model sweep and contract measurement of the early-buyer exit, hook spike and LP fee.
| compare short uniform-price opening batches and min-out protection | [V2_BATCH_OPENING_EXPERIMENT.md](./V2_BATCH_OPENING_EXPERIMENT.md) |
| verify V2 fee-funded buyback and burn on a real-venue fork | [V2_PROFIT_FORK.md](./V2_PROFIT_FORK.md) |
| replay eight V2 market paths and six strategy parameter combinations on a real-venue fork | [V2_LOW_FREQUENCY_FORK.md](./V2_LOW_FREQUENCY_FORK.md) |
| see what a stock that trends up, down or sideways does to a V2 raise, its treasury and its token | [V2_TREND_SCENARIOS.md](./V2_TREND_SCENARIOS.md) |
| build it, run the tests, and make a change safely | [Current V2 build instructions](../README.md#build-and-test), [historical DEVELOPMENT.md](../../archive/hedgefund/docs/DEVELOPMENT.md) |
| know what is trusted, what is defended, what is knowingly open | [Current contract scope](../../docs/CONTRACT_SCOPE.md), [historical SECURITY.md](../../archive/hedgefund/docs/SECURITY.md) |
| look up a function, selector, error or constant | [REFERENCE.md](./REFERENCE.md) *(generated — do not edit by hand)* |
| rehearse or execute a deployment | [Current V2 rehearsal](V2_DEPLOYMENT_REHEARSAL.md), [historical DEPLOYMENT.md](../../archive/hedgefund/docs/DEPLOYMENT.md) |
| deploy V2 on the public Robinhood Chain testnet (46630) for the team to test the front end with no real money | [TESTNET_V2.md](./TESTNET_V2.md) |
| add native ETH payments and 24/7 ETH strategies with a pool TWAP | [TESTNET_V2_ETH_MARKET.md](./TESTNET_V2_ETH_MARKET.md) |
| list a stock, run the routine checks, read an alert | [Current operations](../../docs/OPERATIONS.md), [historical OPERATIONS.md](../../archive/hedgefund/docs/OPERATIONS.md) |
| check a stock before a V2 listing or launch (graduation depth, gate, 0.05% sell chunk) | [`tools/v2_launch_check.py`](../tools/v2_launch_check.py), [V2_DEPLOYMENT_REHEARSAL.md](./V2_DEPLOYMENT_REHEARSAL.md#listing-check-first-live-run) |
| see what ships first and what remains pending | [Current contract scope](../../docs/CONTRACT_SCOPE.md), [historical ROADMAP.md](../../archive/hedgefund/docs/ROADMAP.md) |
| write the site, the announcement or the launch form | [Current contract scope](../../docs/CONTRACT_SCOPE.md), [historical LAUNCH_KIT.md](../../archive/hedgefund/docs/LAUNCH_KIT.md) |
| respond to an incident | [Current operations](../../docs/OPERATIONS.md), [historical V1 emergency kit](../../archive/hedgefund/emergency/README.md) |

**Historical docs-site workflow:** `pip install mkdocs-material mkdocs-static-i18n jieba`, then the archived `tools/docs_site.py serve` in a pinned source checkout -- search, a sidebar, an English / 中文 switch and
rendered Mermaid at http://127.0.0.1:8000, assembled from these same files (nothing is written for it, and the repo stays
the source of truth). Keep it internal: SECURITY, AUDIT and the emergency runbook are in it.

**New here?** ARCHITECTURE → DEVELOPMENT → SECURITY, in that order, is about forty minutes
and is enough to review a pull request.

## The one thing to internalise

**Identify the deployment version before describing its permissions.** New default V2 kind-0 treasuries
use a proxy with owner-scheduled upgrades after a 48-hour delay. The controller binds implementation,
configuration, migration data and factory ownership epoch; new implementations remain a governance trust
boundary. The LP vault is separately immutable and has no liquidity-removal path. See
[V2_BONDING_CURVE.md](./V2_BONDING_CURVE.md) for the current graduation and upgrade design.

For legacy immutable deployments, a token, its treasury and the one `HedgeFunHook` every
strategy's pool runs on have no upgrade path and no parameter that can change; the token has
no owner, the treasury's owner can only point its votes (`setVoteDelegate` — reserved, not
live), and the hook's owner — the same one, the factory's — can repoint each pool's two
payout addresses (the creator's only after a public 14-day wait the creator can veto) and do
nothing else. A bug that ships in a token or treasury ships forever, for every strategy
launched while it was there; a bug in the hook ships for **every strategy at once**. That is why the audit's fixes
landed before the first launch, why every fix has a regression test that was confirmed to
fail without it, and why [SECURITY.md](../../archive/hedgefund/docs/SECURITY.md#rules-for-changing-the-code) has rules
for changing the code rather than suggestions.

## Evidence and analysis

These are records of work done, not living documentation: they say what was true when
they were written, and carry their dates.

| Document | What it is |
|---|---|
| [EQUITY_PARAMETER_FEES_2025_2026-10-03.md](EQUITY_PARAMETER_FEES_2025_2026-10-03.md) | One year of daily TSLA/NVDA/META prices, five strategy profiles, matched fee controls, 39 actual-contract fork cases and independently checked accounting |
| [COMPETITOR_MECHANICS_2026-10-03.md](COMPETITOR_MECHANICS_2026-10-03.md) | Official-source comparison of Long/StonkFun mechanics and the limits of HedgeFun's claimed differences |
| [V2_SIMPLE_CYCLE_AUDIT.md](./V2_SIMPLE_CYCLE_AUDIT.md), [V2_SIMPLE_CYCLE_BACKTEST.md](./V2_SIMPLE_CYCLE_BACKTEST.md) | Historical source #110 audit and frozen-price replay; their sizes and test counts describe the pinned source snapshot, with current target validation in the integration review |
| [`../AUDIT.md`](../../archive/hedgefund/AUDIT.md) | Security review, 2026-09-20: three adversarial passes, 43 Foundry reproductions, a go/no-go, and the measured chain facts each finding was sized against. Status banners record which rounds fixed what |
| [STOCK_TOKEN_ASSESSMENT.md](../../archive/hedgefund/docs/STOCK_TOKEN_ASSESSMENT.md) | What the real Robinhood stock token can do to a holder: beacon proxy, upgrader, deny-list, pause, `adminBurn`. Every row VERIFIED or INFERRED |
| [`../LISTING_CANDIDATES.md`](../../archive/hedgefund/LISTING_CANDIDATES.md) | Which stocks can be listed (194 → 35 → 25), the first-wave decision, and what the feeds actually do across a weekend |
| [rule-backtest/](../../archive/hedgefund/docs/rule-backtest/README.md) | What a creator's `tp1`/`dip`/`stop` would have done on eleven listed stocks, hourly, replayed forwards and backwards. About the **rule's economics**, not about whether a stock can be listed |
| [`../POOL_SELECTION.md`](../../archive/hedgefund/POOL_SELECTION.md) | A *different* product — a delta-neutral LP hedged with a Lighter perp. Shares the pool census |
| [robinhood-chain/](../../archive/hedgefund/docs/robinhood-chain/README.md) | Mirrors of three Robinhood Chain docs pages, each reconciled against what the chain actually does |
| [research/PONS_TAX_ELASTICITY.md](../../archive/hedgefund/docs/research/PONS_TAX_ELASTICITY.md) | Does the trade tax predict volume and graduation? 106,631 pons.family launches on our chain, 2026-09-16 to 09-27, at a creator-chosen 1-11% tax. The same creator does as well at 2-5% as at 1%; above 5% volume halves and graduation nearly stops. Evidence for the 1-2% cap decision |

## Keeping these docs true

- **[REFERENCE.md](./REFERENCE.md) is generated** from the compiler's ABI output and the
  source's NatSpec by `tools/gen_reference.py`. Change the NatSpec, not the Markdown, then
  regenerate. A missing description in the reference is a missing `///` in the source.
- **`python3 tools/check_archive.py`** from the organization repository root checks the imported records and documentation links. Regenerate the current V2 reference from `contractV2/` with `python3 tools/gen_reference.py` after source changes.
- **A PR that changes behaviour changes the doc that describes it, in the same PR.**
  ARCHITECTURE for how it works, SECURITY for what it defends or accepts, OPERATIONS and
  `emergency/` for anything an operator would do differently. The root
  [`README.md`](../README.md) is the project's front page and the historical record of
  what each adversarial pass found; these files are what a maintainer works from.
- **Numbers rot.** Pool depths, TVL, feed ages and test counts in the analysis documents
  are dated measurements. Re-run the tool rather than quoting the figure.
- Keep it portable: relative links only, no platform-specific Markdown extensions, fenced
  code blocks with a language tag.
