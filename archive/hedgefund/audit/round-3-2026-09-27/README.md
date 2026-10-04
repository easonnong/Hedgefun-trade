> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# How round 3 was produced, and everything it got wrong along the way

Companion to [`00-SCOPE.md`](./00-SCOPE.md) and [`ISSUES.md`](./ISSUES.md).

## Six layers

Four information-isolated lanes ran in parallel, then triage by an agent that ran none of them, then an
adversarial pass that did neither, then a review of this report's own rubric and framing written **without
the source code**.

| lane | what it was given | what it owned |
|---|---|---|
| v2 surface | the nine new contracts, `docs/V2_*` for intent only | the curve, the vault, graduation, the routers, the deployers |
| v1 delta | the ~55 changed lines **and rounds 1-2's "checked and found safe" sections** | which prior conclusions this PR invalidates |
| economics | everything — all ten v2 documents, chain access | mechanism design, incentives, manipulation cost |
| claims | the ten `docs/V2_*.md` | whether the code and tests say what the documents say |

The lead read the curve and the vault in full before any lane reported and entered triage as a fifth source
with no special weight.

**The claims lane is new to this track and it earned its place.** It reported 27 claims checked — 14
supported, 6 narrower than stated, 2 unsupported, **5 contradicted** — and it worked by mutation rather than
by reading: break the property, see whether the suite notices. That is how it found that
`V2LiquidityVault.seed`'s `onlyFactory` can be deleted with all 1,412 tests green.

**Everything graded EXECUTED is shipped as a runnable PoC.** `poc/run.sh` stages six files into `test/`,
runs 32 tests and removes them again — no network, no RPC, no environment variables — and they inherit the
repository's own `V2FactoryFixture` rather than duplicating its setup. Both of the v2-surface lane's passes
are shipped, overlapping tests and all, because both were run. The chain-state work is separate, under
`poc/fork/`, and is labelled a measurement rather than a test: Robinhood Chain's public RPC is not an
archive node, so those probes cannot be pinned to the block this report quotes, and they therefore assert
only on what is deterministic and report the rest. M-3's headline number moved three times in one day
while this round was running; the probe is what makes that checkable rather than a claim.

## What this round got wrong

Recorded up front, because a report that lists only its successes cannot be used as an input to the next one.

**The lead published two wrong numbers in the baseline that all four lanes were working from.** The base hook
was given as 18,362; it is **18,481**. That figure was round 2's, measured at an older ref and carried
forward without re-measuring — the exact mistake this report criticises the v2 documents for in M-5. And the
size table omitted `TreasuryDeployer` entirely, so every treasury-side fix was being costed against 2,158
bytes when the real number is **1,020**. Both were caught by a lane, re-measured by the lead, corrected in
the baseline mid-round, and pushed to the three lanes still running.

**The lead's most-promoted structural result was false.** M-1's "the only correct fix is 36 bytes over
EIP-170, therefore `CurveDeployer` must be split in two" was relayed to the client as the round's most
actionable finding. The adversarial pass rebuilt all three candidate fixes, reproduced the byte table to the
byte, and then showed the fix **fits** — one `public`→`private` on an accumulator, plus deleting
`predictVault`, which is dead code on chain. **And the lead's synthesis built on top of it went with it**: the
argument that the untested `onlyFactory` guard was a tripwire, because the splitting refactor was the most
likely future change, has no refactor to stand on.

**One finding was a false positive on its central sentence.** I-11 claimed `collectFees()` returns (0,0) at
`lpFee = 1`, killing the vault and M-0's fuel line. Executed: a 100-stock buy yields 1e14 wei, credited in
full. The arithmetic it started from was right and the inference was not — and resolving it withdrew one of
the method review's criticisms, which had used I-11 to argue M-0 contradicted itself.

**The one High did not survive the lead's own reading of the rubric.** Filed High by a lane, executed by
triage, re-derived by the adversarial pass — and graded on language closer to the Medium text than to any
limb of the High one. It is Medium.

## What this round did not do

1. **No context-free lane.** Rounds 1 and 2 ran a source-only lane that was told nothing about the protocol,
   and in round 1 it produced the single most reachable finding. This round did not, and every lane was
   pointed at four "most valuable places to look" in the baseline — three of which map onto findings that
   came back. What that arrangement systematically misses is the ordinary implementation defect nobody
   hypothesised: decimals and units, storage packing, event correctness, ERC-20 return values, initialisation
   order. **No source claims to have read all 1,458 new lines**; the strongest statement available is that
   every line cited in a merged finding was read.
2. **The deployment configuration could not be audited** — no v2 `Defaults` exist. Four graded findings live
   inside parameters nobody has set, including M-0.
3. **The runbook, the launch UI and the ABI/front-end surface were not audited**, and two contracts have
   27 and 176 bytes of margin, so nothing can be fixed there after deployment.
4. **Every source shares one model family.** The contracts, the ten v2 documents, the author's two reviews,
   the four lanes, the lead's notes and the triage all came from it. Six correlated samples were treated as
   five independent sources, and the independence this round gained over the author's own v2 reviews is from
   authorship and information isolation, not from a second kind of mind.
5. **The live-venue fork suites were not run** (they need `RH_FORK=1` and an archive RPC), so the author's
   "13/13" fork claims are UNMEASURED here — while M-0's write-up cites one of those very files as
   corroboration.
6. **Severity inverts along this report's own fix path in one place**, and a reader triaging by severity
   would miss it: see M-1 and I-14.

## What would have made this round say "do not ship"

Stated so that its absence means something. An unprivileged path to take or destroy the curve's reserves, a
buyer's stock, or the locked LP position; a defect in the immutable per-launch contracts with no
configuration that avoids it; or an accounting break in the curve. **None was found**, and the two places a
Critical would have lived — the curve's solvency invariant and the vault's "fee-only" property — were
attacked hardest and held, each verified independently by more than one layer.

What was found instead is a system whose safety rests on parameters nobody has set yet, documented in
documents that no longer match it, with two of its six remediation budgets already spent.
