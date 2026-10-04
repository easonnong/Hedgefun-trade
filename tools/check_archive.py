#!/usr/bin/env python3
"""Verify historical import integrity and local documentation links, offline."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive/hedgefund"
SOURCE_COMMIT = "48a41e2d53c8d24505e3313ae01a01c153b9e721"


def main():
    manifest = json.loads((ARCHIVE / "MANIFEST.json").read_text())
    errors = []
    if manifest["source_commit"] != SOURCE_COMMIT:
        errors.append("unexpected historical source commit")
    paths = set()
    docs = []
    for entry in manifest["files"]:
        relative = entry["path"]
        path = (ARCHIVE / relative).resolve()
        if not path.is_relative_to(ARCHIVE.resolve()) or relative in paths:
            errors.append(f"invalid or duplicate archive path: {relative}")
            continue
        paths.add(relative)
        if not path.is_file():
            errors.append(f"missing archived file: {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            errors.append(f"archive hash changed: {relative}")
        if path.suffix != ".md" and entry["source_sha256"] != entry["sha256"]:
            errors.append(f"non-Markdown source bytes were changed: {relative}")
        if path.suffix == ".md":
            if not path.read_text().startswith("> Historical source record"):
                errors.append(f"historical scope missing: {relative}")
            docs.append(path.relative_to(ROOT).as_posix())
    if len(paths) != 320:
        errors.append(f"expected 320 imported files, found {len(paths)}")
    spec = importlib.util.spec_from_file_location("archived_link_parser", ARCHIVE / "tools/check_docs.py")
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    parser.ROOT = str(ROOT)
    docs.extend([
        "README.md", "docs/OPERATIONS.md", "audit/README.md", "archive/hedgefund/README.md",
        "contractV2/README.md", "contractV2/docs/README.md", "contractV2/docs/V2_TWO_SIDED_FEES.md",
        "contractV2/docs/TESTNET_V2_FEE_UPGRADE.md",
    ])
    problems, count = parser.check_links(docs)
    errors.extend(problems)
    for name in ("DeployV2Testnet", "DeployV2FeeUpgradeTestnet"):
        script = (ROOT / f"contractV2/script/{name}.s.sol").read_text()
        if 'vm.serializeUint(o, "recommendedTaxBps", 100)' not in script and 'vm.serializeUint(k, "recommendedTaxBps", 100)' not in script:
            errors.append(f"current 1% recommendation missing in {name}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Verified {len(paths)} historical files and {count} local links in {len(docs)} Markdown files; current deployment recommendation is 1%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
