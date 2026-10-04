#!/usr/bin/env bash
# Prepare the verifier's Docker build context: the tool, the Dockerfile, and a clean clone of just the deployment
# revision (and its history) with its submodules. Run from a checkout of this repository; prints the context directory.
#   tools/verifier/build-context.sh [revision] [out-dir]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(git -C "$here" rev-parse --show-toplevel)"
revision="${1:-$(python3 -c "import sys; sys.path.insert(0, '$repo/tools'); import verify_contracts as v; print(v.REVISION)")}"
out="${2:-$(mktemp -d)}"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo "revision must be a full commit hash" >&2; exit 1; }
rm -rf "$out/source"
# Fetch only the deployment commit and its history, not every branch and tag of this checkout: unpushed local
# branches must not end up in the image. A fetch copies objects into the new .git (no hard links into this
# checkout) and leaves no remote or branch behind; the result is a detached checkout of the exact commit.
git init --quiet "$out/source"
git -C "$out/source" fetch --quiet --no-tags --no-write-fetch-head "$repo" "$revision"
git -C "$out/source" -c advice.detachedHead=false checkout --quiet --detach "$revision"
[[ "$(git -C "$out/source" rev-parse HEAD)" == "$revision" ]] || { echo "checkout is not $revision" >&2; exit 1; }
[[ -z "$(git -C "$out/source" for-each-ref)" ]] || { echo "unexpected refs in the source clone" >&2; exit 1; }
git -C "$out/source" submodule update --quiet --init --recursive
[[ -z "$(git -C "$out/source" status --porcelain --untracked-files=all --ignore-submodules=none)" ]] \
  || { echo "deployment source is not clean" >&2; exit 1; }
[[ ! -e "$out/source/.env" ]] || { echo "deployment source contains .env" >&2; exit 1; }
cp "$repo/tools/verify_contracts.py" "$here/Dockerfile" "$here/docker-compose.yml" "$out/"
echo "$out"
