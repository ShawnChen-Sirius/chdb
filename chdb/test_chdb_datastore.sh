#!/bin/bash
# Run chdb's DataStore test suite against the freshly-built chdb-core wheel.
#
# This script fetches the latest chdb (chdb-io/chdb) release tag, clones the
# repository at that tag, layers the chdb wrapper package on top of the
# already-installed chdb-core wheel, and executes datastore/tests/ via pytest.
# A local ClickHouse server is started automatically by the datastore tests'
# conftest.py for integration tests that need a remote server.
#
# Pre-requisites:
#   - chdb-core wheel must already be installed in the active Python env
#     (e.g. via `pip install dist/*.whl`).
#
# Optional environment variables:
#   CHDB_TAG       - pin to a specific chdb tag (default: latest release tag)
#   PYTHON         - python binary to use (default: python from PATH)
#   PYTEST_ARGS    - additional pytest args (default: "-v --tb=short")
#   KEEP_WORKDIR   - if set, do not remove the cloned chdb directory on exit

set -euo pipefail

PYTHON="${PYTHON:-python}"
PYTEST_ARGS="${PYTEST_ARGS:--v --tb=short}"

echo "=============================================="
echo "chdb DataStore tests against chdb-core build"
echo "=============================================="
echo "Python: $(${PYTHON} --version) ($(command -v ${PYTHON}))"

if ! ${PYTHON} -c "import chdb" 2>/dev/null; then
    echo "ERROR: chdb (engine from chdb-core) is not importable in this Python." >&2
    echo "Install the chdb-core wheel first: pip install dist/*.whl" >&2
    exit 1
fi

CORE_VERSION=$(${PYTHON} -c "import chdb; print(chdb.query('SELECT version()', 'CSV').bytes().decode().strip())" 2>/dev/null || echo "unknown")
echo "chdb-core engine version: ${CORE_VERSION}"

if [ -z "${CHDB_TAG:-}" ]; then
    echo "Resolving latest chdb release tag from GitHub..."
    CHDB_TAG=$(curl -fsSL \
        ${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"} \
        https://api.github.com/repos/chdb-io/chdb/releases/latest \
        | ${PYTHON} -c "import json, sys; print(json.load(sys.stdin)['tag_name'])")
fi
echo "Using chdb tag: ${CHDB_TAG}"

WORKDIR=$(mktemp -d -t chdb-tests-XXXXXX)
if [ -z "${KEEP_WORKDIR:-}" ]; then
    trap 'rm -rf "${WORKDIR}"' EXIT
else
    echo "KEEP_WORKDIR set; workdir will remain at ${WORKDIR}"
fi

CHDB_SRC="${WORKDIR}/chdb"
echo "Cloning chdb-io/chdb@${CHDB_TAG} into ${CHDB_SRC}..."
git clone --depth 1 --branch "${CHDB_TAG}" https://github.com/chdb-io/chdb.git "${CHDB_SRC}"

echo "Installing chdb wrapper on top of chdb-core (no deps to preserve local chdb-core)..."
${PYTHON} -m pip install --no-deps --force-reinstall "${CHDB_SRC}"

echo "Installing test dependencies (pytest, pytest-timeout, hypothesis)..."
${PYTHON} -m pip install --upgrade pytest pytest-timeout hypothesis

cd "${CHDB_SRC}"

echo "Sanity check: chdb wrapper version after install"
${PYTHON} -c "import chdb; print('chdb pkg version:', getattr(chdb, '__version__', 'unknown'))"
${PYTHON} -c "from datastore import DataStore; print('datastore import OK')"

echo "=============================================="
echo "Running pytest from datastore/ on tests/"
echo "(cwd=datastore so 'from tests.test_utils import ...' resolves to datastore/tests/)"
echo "=============================================="
cd "${CHDB_SRC}/datastore"

# These upstream tests are marked strict-xfail for bugs that chdb-core has
# since fixed (non-ASCII string values scanned through Python(df) used to
# carry a trailing NUL byte, breaking SQL string equality), so they now
# XPASS(strict) and would fail the run. Deselect them until the upstream
# chdb tag drops the xfail markers.
# Both path forms are passed because pytest resolves --deselect node ids
# against the rootdir (the clone root, where the configfile lives) on
# pytest >= 9, but against the invocation dir on older versions; deselect
# silently ignores whichever form does not match.
DESELECT_FIXED_XFAILS="\
 --deselect datastore/tests/test_exploratory_batch11_advanced_indexing.py::TestAdvancedStringOperations::test_str_normalize \
 --deselect datastore/tests/test_exploratory_batch16_index_copy_edge.py::TestUnicodeAndSpecialCharacters::test_unicode_string_values \
 --deselect tests/test_exploratory_batch11_advanced_indexing.py::TestAdvancedStringOperations::test_str_normalize \
 --deselect tests/test_exploratory_batch16_index_copy_edge.py::TestUnicodeAndSpecialCharacters::test_unicode_string_values"

set +e
${PYTHON} -m pytest tests/ ${PYTEST_ARGS} ${DESELECT_FIXED_XFAILS}
TEST_EXIT_CODE=$?
set -e

echo "Stopping ClickHouse test server (best effort)..."
bash tests/stop_clickhouse_server.sh || true

if [ ${TEST_EXIT_CODE} -ne 0 ]; then
    echo "DataStore tests FAILED (exit code ${TEST_EXIT_CODE}) on chdb tag ${CHDB_TAG}"
    exit ${TEST_EXIT_CODE}
fi

echo "=============================================="
echo "DataStore tests PASSED on chdb tag ${CHDB_TAG}"
echo "=============================================="
