#!/bin/bash
set -e

# Build wheels and test free-threading on macOS.
# Driven by the build_ft_wheels.yml workflow's test job. Caller is responsible
# for setting up pyenv and downloading the cross-compiled FT artifacts.
#
# Required env vars:
#   WHEEL_PLATFORM_TAG — e.g. macosx_11_0_arm64, macosx_10_15_x86_64
#
# Optional env vars:
#   FT_VERSIONS — space-separated list (default: "3.13t 3.14t")
#
# Expects: ft_artifacts/chdb/_chdb.cpython-*t-darwin.so already present.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${WHEEL_PLATFORM_TAG:?WHEEL_PLATFORM_TAG is required}"
: "${FT_VERSIONS:=3.13t 3.14t}"

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"

cd "$PROJ_DIR"

# ── 1. Install free-threading Python versions ────────────────────
# pyenv's `:latest` syntax doesn't support the "t" suffix, so we resolve manually
for ft_version in $FT_VERSIONS; do
    base_ver=${ft_version%t}  # 3.13t → 3.13
    ft_latest=$(pyenv install --list | grep -E "^\s*${base_ver}\.[0-9].*t$" | tail -1 | tr -d ' ')
    if [ -z "$ft_latest" ]; then
        echo "ERROR: no free-threading Python matching ${ft_version} found in pyenv" >&2
        exit 1
    fi
    echo "Resolved ${ft_version} → ${ft_latest}"
    # Retry pyenv install — python.org occasionally times out / 403s.
    for attempt in 1 2 3; do
        if pyenv install "$ft_latest" -s; then
            break
        fi
        if [ "$attempt" = "3" ]; then
            echo "ERROR: pyenv install $ft_latest failed after 3 attempts" >&2
            exit 1
        fi
        echo "pyenv install $ft_latest failed (attempt $attempt/3); retrying in $((attempt * 10))s..."
        sleep $((attempt * 10))
    done
done

for ft_version in $FT_VERSIONS; do
    ft_full=$(pyenv versions --bare | grep "^${ft_version%t}\." | grep 't$' | head -1)
    if [ -n "$ft_full" ]; then
        echo "Installing deps for Python $ft_full"
        PYENV_VERSION=$ft_full python -m pip install --upgrade pip
        PYENV_VERSION=$ft_full python -m pip install setuptools wheel tox pandas pyarrow psutil
    fi
done

# ── 2. Build wheels and test ─────────────────────────────────────
mkdir -p ft_dist

for ft_version in $FT_VERSIONS; do
    ft_full=$(pyenv versions --bare | grep "^${ft_version%t}\." | grep 't$' | head -1)
    if [ -z "$ft_full" ]; then
        echo "ERROR: Python $ft_version not available" >&2
        exit 1
    fi

    py_tag=${ft_version//./}
    so_file="ft_artifacts/chdb/_chdb.cpython-${py_tag}-darwin.so"
    if [ ! -f "$so_file" ]; then
        echo "ERROR: $so_file not found" >&2
        exit 1
    fi

    echo "=============================================="
    echo "Building & testing FT wheel: Python $ft_full ($ft_version)"
    echo "=============================================="

    # Place the correct ft module in chdb/ (setup.py picks it up via EXT_SUFFIX)
    rm -f chdb/_chdb.abi3.so chdb/_chdb.cpython-*-darwin.so 2>/dev/null || true
    cp "$so_file" "chdb/_chdb.cpython-${py_tag}-darwin.so"
    codesign -f -s - "chdb/_chdb.cpython-${py_tag}-darwin.so"

    export CHDB_FREE_THREADING=1
    export CHDB_FREE_THREADING_PYTHON_VERSION=$ft_version
    export PYENV_VERSION=$ft_full

    rm -rf dist/
    python -m pip install "build[virtualenv]" -q
    python -m build --wheel

    python -m wheel tags --platform-tag="$WHEEL_PLATFORM_TAG" --remove dist/*.whl

    whl=$(ls dist/*"cp${py_tag}"*.whl 2>/dev/null | head -1)
    if [ -n "$whl" ]; then
        python -m pip install "$whl" --force-reinstall --no-cache-dir
        # Skip deltalake tests (not available for free-threading Python)
        mv tests/test_arrow_record_reader_deltalake.py tests/test_arrow_record_reader_deltalake.py.skip 2>/dev/null || true
        make test
        mv tests/test_arrow_record_reader_deltalake.py.skip tests/test_arrow_record_reader_deltalake.py 2>/dev/null || true
        echo "✓ Tests PASSED on free-threading Python $ft_version"
        mv "$whl" ft_dist/
    fi

    python -m pip uninstall -y chdb-core 2>/dev/null || true
    unset PYENV_VERSION CHDB_FREE_THREADING CHDB_FREE_THREADING_PYTHON_VERSION
done

echo "=============================================="
echo "All FT macOS builds complete. Wheels in ft_dist/:"
ls -lh ft_dist/
