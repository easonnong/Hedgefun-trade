> Historical source record from `keyuyuan/hedgefund` at `48a41e2d53c8d24505e3313ae01a01c153b9e721`; see [archive scope](../../README.md). Dates, fee settings, permissions and validation results describe the original reviewed versions, not the current organization release.

# How round 2 was produced

Companion to [`00-SCOPE.md`](./00-SCOPE.md) and [`ISSUES.md`](./ISSUES.md).

Round 2 answers one question — what the release did to round 1's findings, and whether the code it
introduced is sound. Two information-isolated lanes ran in parallel: one worked round 1's list finding by
finding, the other audited only what was new and was told explicitly not to re-cover the old ground. The
lead pinned the baseline first, measured the test state at multiple checkouts, and did his own reading of
the partial-fill arithmetic, `setVoteDelegate`, the singleton's blast-radius disclosure and the toolchain
failures before either lane reported.

Round 1's rubric is reproduced in the baseline and was binding on both lanes: grade the **post-launch state
of an immutable contract**, name the loser, split certain from option gain, date every on-chain number
including ones a finding argues against, and label every conclusion EXECUTED or REASONED.

## What this round did NOT do, and why it matters

1. **No adversarial pass.** Round 1 ran one, and it downgraded two of four Highs and broke the lead's own
   headline argument. Round 2 has no equivalent layer. Its findings are 4 Low and 4 Info, so the cost of
   being wrong is lower — but the two "attacked hard and did not break" conclusions about the shared pot
   and the transient slots are exactly the kind of negative result an adversary is best at overturning, and
   they have had one reviewer each.
2. **No third-party review of this round's own framing.** Round 1's produced fifteen criticisms, several
   of which changed the report. Nothing here has been through that.
3. **Nothing is deployed, so nothing could be observed.** Every economic conclusion is still modelled or
   measured on *other* pools.
4. **The same model family produced every source here**, as in round 1. The independence gained is from
   authorship and information isolation, not from a second kind of mind.
5. **The suite could not be run as CI runs it.** CI pins Foundry `v1.5.0`; this round measured on `1.8.1`
   and did not change the machine's toolchain to match. The conclusion that both path-independent failures
   are toolchain drift is supported by direct probes, not by running the pinned version.

## Corrections this round made

Listed in [`ISSUES.md`](./ISSUES.md) under "Corrections this round made to itself and to round 1". The
short version: round 1's fix for the path dependence was withdrawn for this ref after being re-tested; the
lead's claim that the launch-window exemption was untested was disproved by his own mutation and is not
published; and a source claim the lead repeated without checking turned out to be false.
