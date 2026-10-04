> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# How round 1 was produced, and what it could not reach

Companion to [`00-SCOPE.md`](./00-SCOPE.md) (what was audited) and [`ISSUES.md`](./ISSUES.md) (the graded
findings). This file exists so that nobody has to guess which conclusions are load-bearing and which are not,
and so the next round starts from the gaps rather than from scratch.

## Independence, and why it is the point of this round

`docs/SECURITY.md` says "No external security review has been done." That is accurate, and it is the reason
this round exists.

Every commit in this repository is authored by one person and co-authored by Claude models — 24 commits by
`0xfff <…keyuyuan@users.noreply.github.com>`, one by `Keyu Yuan <leoyuan0099@gmail.com>`, with
`Co-Authored-By: Claude Fable 5.1` on 59 of them, `Claude Opus 5 (1M context)` on 19 and `Claude Sonnet 5` on
two. The four audit commits (`5d70434`, `4deb193`, `e1c35bb`, `9a291aa`) are all by the same author, and
`AUDIT.md` describes its passes as adversarial lanes whose "synthesis, cross-verification and the go/no-go
below are the lead's" — the lead being that author.

Author rounds 1–5 are therefore **one reviewer's five passes, not five independent confirmations**. Where they
agree with each other that is evidence of a shared model of the protocol, which is exactly the thing an
outside round is for. This round accordingly treats "author round N found this safe" as a hypothesis to test,
not as a settled result, and it spent a whole lane ([`06-prior-rounds`](#lanes)) on re-verifying their stated
dispositions against the code as it actually stands at `9a291aa`.

## Method

Five phases, in order, following the `evm-audit` methodology.

**A · Mechanism.** The lead read all 2,965 lines of `src/` before any lane started and before forming any
opinion on severity, then wrote its own notes as an independent source that entered triage with no more
standing than a lane's.

**B · Baseline.** Pinned before any lane was launched, because a wrong baseline is a wrong severity on every
finding at once. This is where the audit established that **nothing is deployed** (three `cast code` calls,
all empty) and that `docs/DEPLOYMENT.md`'s description of the protocol Safe is already stale (2-of-4 and
nonce 1 on chain, against 2-of-3 and nonce 0 in the document). Both facts are in `00-SCOPE.md` with the date
they were read.

**C · Parallel lanes.** Six lanes, run concurrently, deliberately differing in **what information they were
given** rather than in how their prompts were worded — identical context with different phrasing produces
overlapping results, and the diversity that matters comes from isolation.

<a id="lanes"></a>

| lane | what it was given | what it was denied |
|---|---|---|
| clean | `src/` and `lib/` only | every `.md`, `test/`, `script/`, and any statement of what the protocol is for |
| historical exploits | full repo; required to research ≥20 named real-world exploits **first** and then match each against the code | — |
| checklist | full repo, plus nine mandatory headings covering roles, visibility, pausability, fix cost, events, parameter pairing, getters, setter bounds and deployment-time validation | — |
| economic / mechanism | full repo **and** all docs, backtests and chain access — the one lane given everything | — |
| test quality | `src/` and `test/` | who wrote the tests |
| prior rounds | `AUDIT.md`, the four audit commits, and the whole git history | — |

Every lane received the same pinned ref, the same deployment baseline, and the same severity rubric, all
reproduced verbatim in its prompt. Every lane was required to label each conclusion **EXECUTED** or
**REASONED** and to deliver a "checked and found safe" section with the specific line that makes each item
safe.

**D · Verification.** Triage by an agent that ran no lane; adversarial falsification by an agent that did not
run triage and was told to attack the exonerations as well as the findings; a review of the test suite's
actual killing power, including a 24-mutation kill-rate measurement; and a review of this report and its
rubric carried out **without** the source, to catch bias in the method rather than in the findings. Both
of the last two are reproduced in full in [`VERIFICATION.md`](./VERIFICATION.md), because what a review
changed is only legible next to what it said.

**E · Grading and delivery.** The lead wrote the final report from the lanes' material rather than assembling
their outputs, and went through every finding line by line. That step is not ceremony: in this round it
retracted one of the lead's own findings outright and cut another from a claimed attack to a missing bound —
see below.

## What this round got wrong about itself, and corrected

Recorded because a round that reports only its successes is not usable as an input to the next one.

- The lead's first reading concluded that the factory owner could substitute `Defaults` underneath a pending
  launch, since only `maxFee` and `expectedOpenPriceE18` are restated in the `Request`. **That is false.**
  Every default reaches either the token's CREATE2 arguments, the treasury's, or the hook's, so any change
  invalidates the mined hook salt and the launch reverts. The lead falsified this with a test before triage,
  and what survived is the much narrower finding that three `Defaults` fields are under-bounded. The
  mined-salt mechanism is a complete restatement guard over all nineteen fields and nothing in the repository
  names it as one.
- The lead flagged a `q = L.qty / 2 == 0` path on a one-wei lot. A one-wei lot cannot exist — `_book` refuses
  anything below `minLotUsdg` and a lot only ever halves once — so the path is unreachable. Retracted, and
  recorded in `ISSUES.md`'s "checked and found safe" so the next round does not re-derive it.

## Known weaknesses of this round

1. **Fork tests were run against live chain state, not a pinned archive block.** Results that depend on a
   pool's depth or a feed's freshness are true for 2026-09-21 and are dated as such. A finding whose severity
   turns on such a number is flagged UNMEASURED or dated in place.
2. **The stock token is taken as given.** Its issuer can upgrade all 194 tokens from one code-less address
   with no timelock, and can `adminBurn` past both the pause and the deny-list. Every conclusion here is
   conditional on today's implementation, and `test/StockTokenFork.t.sol` is the tripwire, not this audit.
3. **No economic conclusion in this round is backed by a live launch.** Nothing is deployed, so every number
   about pool depth, manipulation cost and tax drag is modelled from chain reads of *other* pools plus the
   repo's own measurements. The ratio that decides several parameter bounds — the treasury's size against its
   launch pool's depth — cannot be measured before a launch exists.
4. **The V4 stock-leg venue is barely exercised in production terms.** It ships disabled
   (`v4ListingEnabled == false`), and this round did not treat "the owner will leave it off" as a security
   property, because a boolean an owner can flip is not one.
5. **Half the value of an audit is in what it decided not to report.** Where this round checked something and
   concluded it was safe, the line that makes it safe is cited. Where it could not reach a conclusion, it
   says UNMEASURED rather than picking a side.

6. **Zero Criticals is mostly a fact about the architecture, not a result.** Critical requires an
   unprivileged actor to take or destroy treasury funds, buyer funds or the seeded liquidity. This protocol
   has **no treasury withdrawal path for anyone**, custodies no buyer funds, and its seed liquidity is
   provably unremovable — so two of the three objects the tier names have no extraction path at all and the
   third cannot be touched. The tier is close to unreachable here by construction. Read "0 Critical" as a
   statement about the shape of the protocol, not as a clean bill of health. Relatedly, **32 of the 41
   findings report zero gain to any actor**: the rubric asks what an attacker takes, and for most of what is
   wrong with this system nobody takes anything — the loss is to the treasury, to holders, or to the
   product's own premise. Three of the four Highs had to be graded *against* that framing rather than with
   it. A rubric shaped for a lending protocol is the wrong instrument for one with no redemption, and the
   next round should write its own.

7. **The fix list is not the decision.** Six measurements this report itself calls decisive are absent from
   the urgency table, and three of them gate the severity of three of the four Highs: weekend liquidity
   thinning; the buy-back's real impact on a genuinely single-sided seeded pool; arbitrage bleed over a
   600-second hold; the longest weeknight Chainlink gap over a full year rather than 27 days; the equity
   feeds' `minAnswer` / `maxAnswer` bounds; and the price of this chain's native gas token, which the
   repository never states and this audit could not establish. Working down the urgency table and stopping
   is not a launch decision.

8. **The safe list has had a second reviewer, but only one, and everything here shares a model family.**
   The consolidated "checked and found safe" section is the part a future round is told not to re-derive and
   therefore the part where a miss is most expensive. It was reviewed by the adversarial pass — that pass was
   explicitly asked to attack the exonerations and the rejected list, not only the findings — but by nothing
   else. And the independence this round gained over the author's five is from **authorship and information
   isolation, not from a second kind of mind**: the same model family produced all eight sources here. The
   argument this report makes about the author's rounds applies to this one, with one fewer degree of freedom
   removed than the framing implies.

9. **The audit could not determine the price of the chain's native gas token.** It is not in the repository
   and was not established on chain. Every conclusion about whether a bounty covers its own gas — and
   therefore whether the permissionless functions get called at all — is conditional on it.
