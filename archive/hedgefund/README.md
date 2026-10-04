# Historical Hedgefund audit and operations records

This archive brings the audit and operations material from `keyuyuan/hedgefund` into the organization repository. The source is merged commit [`48a41e2d53c8d24505e3313ae01a01c153b9e721`](https://github.com/keyuyuan/hedgefund/tree/48a41e2d53c8d24505e3313ae01a01c153b9e721), captured on 2026-10-04. New development uses this repository's default branch, `codex/contract-v1`, and the current [operations guide](../../docs/OPERATIONS.md) and [audit index](../../audit/README.md).

## Contents and provenance

| Material | Local copy |
|---|---|
| Internal audit history and external review rounds with PoCs and mutations | [AUDIT.md](AUDIT.md), [audit/](audit/README.md) |
| Security, deployment, operations, stock-token assessment and listing decisions | [docs/](docs/README.md), [listing candidates](LISTING_CANDIDATES.md) |
| Safe emergency batch builder, local drill and historical address configuration | [emergency/](emergency/README.md) |
| Survey, listing, monitoring, verification and research tooling | [tools/](tools/) |
| Historical deployment and rehearsal scripts | [script/](script/) |
| Public address books, Safe batch records and dated measurements | [deploy/](deploy/), [data/](data/) |
| Separate pool-selection research | [POOL_SELECTION.md](POOL_SELECTION.md) |

[MANIFEST.json](MANIFEST.json) inventories 320 imported files, with their original source SHA-256, imported SHA-256 and pinned source URL. Markdown files gain a historical-scope banner; links to source, tests or reference files omitted from this archive point to the pinned original checkout. Executable tools, scripts, JSON evidence and other non-Markdown files retain their original bytes. No original report findings, historical fee settings, transaction receipts or measured results are rewritten.

Run `python3 tools/check_archive.py` from the organization repository root to check file integrity, local documentation links and the current 1% recommendation.

## Version boundaries

These are historical engineering reviews, not an audit certification of the current organization release. A round's findings and GO/NO-GO decision apply to the ref and deployment described in that round. The new default V2 treasury has a 48-hour upgrade mechanism; older claims that every treasury is immutable do not describe it. Current permissions are in [CONTRACT_SCOPE.md](../../docs/CONTRACT_SCOPE.md).

The organization's recommended base trading fee for new deployments is **1% (`taxBps=100`)**. Historical 3% tests and proof books preserve their original terms. The source repository's unmerged 1.5% proposal, external LP prototype and lending branch are not imported by this archive.

## Using historical tools

The archived tools retain the original `src/`, `test/`, `lib/` and working-directory assumptions. They are reproducibility material, not a second current contract project. Replay them in a separate checkout of the pinned source commit with its recursive submodules and Foundry 1.5.0; use the organization repository's `contractV1/` and `contractV2/` projects for current builds.

The archived emergency configuration targets its recorded V1 deployment. It does not establish the addresses or complete owner surface of a current V2 deployment. Recheck the target factory, calendar, owner and deployed ABI before preparing a Safe batch. The current guide links the version-specific deployment and upgrade procedures. Historical public evidence is preserved here; credentials and local signer files are not part of this import.
