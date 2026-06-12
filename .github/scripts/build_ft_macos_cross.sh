#!/bin/bash
set -e

# Cross-compile free-threading Python modules for macOS on Linux.
#
# Required env vars:
#   MAC_ARCH — arm64 or x86_64
#
# Optional env vars:
#   FT_VERSIONS — space-separated list (default: "3.13t 3.14t")
#
# Output: ft_artifacts/chdb/_chdb.cpython-*t-darwin.so

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${MAC_ARCH:?MAC_ARCH is required (arm64 or x86_64)}"
: "${FT_VERSIONS:=3.13t 3.14t}"

source ~/.cargo/env 2>/dev/null || true

cd "$PROJ_DIR"
mkdir -p ft_artifacts/chdb

# build_mac_on_linux.sh does `rm -f chdb/*.so` which would clobber a pre-existing
# _chdb.abi3.so. Save/restore is a no-op in the dedicated FT workflow (no abi3.so
# present) but stays defensive in case this script is invoked alongside a regular
# build.
SAVED_DIR=$(mktemp -d)
cp -a chdb/_chdb.abi3.so "$SAVED_DIR/" 2>/dev/null || true

for ft_version in $FT_VERSIONS; do
    echo "=============================================="
    echo "Cross-compiling FT for macOS ${MAC_ARCH} — Python $ft_version"
    echo "=============================================="

    export CHDB_FREE_THREADING=1
    export CHDB_FREE_THREADING_PYTHON_VERSION=$ft_version
    export CHDB_CROSSCOMPILING=1

    bash ./chdb/build_mac_on_linux.sh "$MAC_ARCH" Release

    py_tag=${ft_version//./}   # 3.13t → 313t
    mac_name="chdb/_chdb.cpython-${py_tag}-darwin.so"
    if [ -f "$mac_name" ]; then
        cp "$mac_name" "ft_artifacts/$mac_name"
    else
        echo "ERROR: expected $mac_name not found" >&2
        exit 1
    fi

    unset CHDB_FREE_THREADING CHDB_FREE_THREADING_PYTHON_VERSION CHDB_CROSSCOMPILING
done

# Restore main build artifacts destroyed by build_mac_on_linux.sh
cp -a "$SAVED_DIR"/* chdb/ 2>/dev/null || true
rm -rf "$SAVED_DIR"

echo "FT cross-compile artifacts:"
ls -lhR ft_artifacts/
