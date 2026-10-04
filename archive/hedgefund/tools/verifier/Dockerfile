# The source verifier as a long-running service. It needs no key of any kind: it reads the chain, reads Sourcify,
# and publishes Solidity source to Sourcify. It never signs or sends a transaction.
#
# The build context is prepared by build-context.sh: this Dockerfile, the tool, and `source/`, a clone of just the
# deployment revision with its submodules. The tool refuses anything but that exact clean checkout.
#
# Base image pinned by digest (a multi-arch index: amd64 and arm64 both resolve through it).
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

ARG TARGETARCH
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 verifier \
 && install -d -o verifier -g verifier /state   # a new named volume takes this owner; the service is not root

# Foundry pinned to one release and checked against its sha256 before anything is extracted: the compiler input
# it generates must match what verified the deployment. The checksums belong to v1.5.0 only.
RUN set -eu; \
    version=v1.5.0; \
    arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "$arch" in \
      amd64) sum=5cd98f9092bcc28be087939491f786b2bf3ed55e492996a409e29519b8ab4dc8 ;; \
      arm64) sum=8138e1615568bfcca5999773830892d93a569370eb0ae4b7dd97db46e2af47f9 ;; \
      *) echo "no pinned Foundry checksum for $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/foundry.tar.gz \
      "https://github.com/foundry-rs/foundry/releases/download/${version}/foundry_${version}_linux_${arch}.tar.gz"; \
    echo "$sum  /tmp/foundry.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/foundry.tar.gz -C /usr/local/bin forge cast; \
    rm /tmp/foundry.tar.gz; \
    forge --version

# Source and tool belong to root and are read-only to the service user.
COPY source /source
COPY verify_contracts.py /app/verify_contracts.py
# Compile once at build time, as root: solc is fetched and the cache warmed, so a submission does not wait on either.
# out/ and cache/ are gitignored, so the checkout stays clean for the tool's own check, which runs here too.
# Forge 1.5 keeps solc in $HOME/.svm, with no setting to move it, so the build uses the service user's HOME: solc
# lands in /home/verifier/.svm, root-owned, and stays there (at run time only ~/.foundry is a tmpfs).
# Only out/ and cache/ go to the service user, in case forge rebuilds; verify-contract writes nowhere else in /source.
RUN cd /source \
 && HOME=/home/verifier forge build --skip test --skip script >/dev/null \
 && test -z "$(git status --porcelain --untracked-files=all --ignore-submodules=none)" \
 && ls /home/verifier/.svm/*/solc-* >/dev/null \
 && chown -R root:root /source /app /home/verifier/.svm \
 && chmod -R go-w /source /app /home/verifier/.svm \
 && chown -R verifier:verifier /source/out /source/cache \
 && rm -rf /home/verifier/.foundry \
 && install -d -o verifier -g verifier -m 0700 /home/verifier/.foundry \
 && git config --system --add safe.directory /source \
 && git -C /source submodule foreach --quiet --recursive 'echo "$toplevel/$sm_path"' \
    | while read -r path; do git config --system --add safe.directory "$path"; done
# git refuses a repository another user owns; the list above names exactly the source and its submodules.

USER verifier
# Prove, as the service user, that the checks the tool runs before every submission pass against the read-only
# source, and that the source and the compiler really are read-only to it. out/ and cache/ are made read-only for
# the check too, as `read_only: true` makes them at run time: with the warm cache forge writes nothing (a cold
# cache it would try to rewrite, and the check would fail).
RUN chmod -R a-w /source/out /source/cache \
 && python3 -c "import sys; sys.path.insert(0, '/app'); import verify_contracts as v; from pathlib import Path; \
t = v.validate_source(Path('/source'), v.REVISION); v.validate_input(Path('/source'), v.TEMPLATES['token'], t)" \
 && chmod -R u+w /source/out /source/cache \
 && ! touch /source/.write-probe 2>/dev/null \
 && ! touch /home/verifier/.svm/.write-probe 2>/dev/null

VOLUME /state
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/app/verify_contracts.py", "--state", "/state/state.json", "--source", "/source", "--submit"]
CMD ["--watch", "30"]
# Alive means the loop ticked in the last fifteen minutes: it beats every 30 s between passes, after each contract
# within one, after a failed pass and after a failed strategy-count read, and one submission is bounded at five
# minutes. It is liveness only: an unreachable RPC or Sourcify shows in the logs and the state file, not here.
HEALTHCHECK --interval=60s --timeout=5s --start-period=900s \
  CMD python3 -c "import os,sys,time; sys.exit(0 if time.time() - os.path.getmtime('/state/state.heartbeat') < 900 else 1)"
