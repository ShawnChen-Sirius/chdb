#!/bin/bash

set -e

# Build type: RelWithDebInfo (release with debug info)
build_type="RelWithDebInfo"

export CXX=/usr/bin/clang++-19
export CC=/usr/bin/clang-19

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

. ${DIR}/vars.sh

BUILD_DIR=${PROJ_DIR}/buildlib

# Linux ARM specific configuration
if [ "$(uname)" != "Linux" ]; then
    echo "This script is for Linux only"
    exit 1
fi

if [ "$(uname -m)" != "aarch64" ]; then
    echo "This script is for Linux ARM64 (aarch64) only"
    exit 1
fi

GLIBC_COMPATIBILITY="-DGLIBC_COMPATIBILITY=1"
UNWIND="-DUSE_UNWIND=1"
JEMALLOC="-DENABLE_JEMALLOC=1"
ICU="-DENABLE_ICU=1"
SED_INPLACE="sed -i"
CPU_FEATURES="-DENABLE_AVX=0 -DENABLE_AVX2=0"
LLVM="-DENABLE_EMBEDDED_COMPILER=0 -DENABLE_DWARF_PARSER=0"
HDFS="-DENABLE_HDFS=1 -DENABLE_GSASL_LIBRARY=1 -DENABLE_KRB5=1"
MYSQL="-DENABLE_MYSQL=1"
RUST_FEATURES="-DENABLE_RUST=1 -DENABLE_DELTA_KERNEL_RS=1"

CORROSION_CMAKE_FILE="${PROJ_DIR}/contrib/corrosion-cmake/CMakeLists.txt"
if [ -f "${CORROSION_CMAKE_FILE}" ]; then
    if ! grep -q 'OPENSSL_NO_DEPRECATED_3_0' "${CORROSION_CMAKE_FILE}"; then
        echo "Modifying corrosion CMakeLists.txt for Linux aarch64..."
        ${SED_INPLACE} 's/corrosion_set_env_vars(${target_name} "RUSTFLAGS=${RUSTFLAGS}")/corrosion_set_env_vars(${target_name} "RUSTFLAGS=${RUSTFLAGS} --cfg osslconf=\\\"OPENSSL_NO_DEPRECATED_3_0\\\"")/g' "${CORROSION_CMAKE_FILE}"
    else
        echo "corrosion CMakeLists.txt already modified, skipping..."
    fi
else
    echo "Warning: corrosion CMakeLists.txt not found at ${CORROSION_CMAKE_FILE}"
fi

if [ ! -d $BUILD_DIR ]; then
    mkdir $BUILD_DIR
fi

cd ${BUILD_DIR}
CMAKE_ARGS="-DCMAKE_BUILD_TYPE=${build_type} -DENABLE_THINLTO=0 -DENABLE_XRAY=0 -DENABLE_TESTS=0 -DENABLE_CLICKHOUSE_SERVER=0 -DENABLE_CLICKHOUSE_CLIENT=0 \
    -DENABLE_CLICKHOUSE_KEEPER=0 -DENABLE_CLICKHOUSE_KEEPER_CONVERTER=0 -DENABLE_CLICKHOUSE_LOCAL=1 -DENABLE_CLICKHOUSE_SU=0 -DENABLE_CLICKHOUSE_BENCHMARK=0 \
    -DENABLE_AZURE_BLOB_STORAGE=1 -DENABLE_CLICKHOUSE_COPIER=0 -DENABLE_CLICKHOUSE_DISKS=0 -DENABLE_CLICKHOUSE_FORMAT=0 -DENABLE_CLICKHOUSE_GIT_IMPORT=0 \
    -DENABLE_AWS_S3=1 -DENABLE_HIVE=0 -DENABLE_AVRO=1 \
    -DENABLE_CLICKHOUSE_OBFUSCATOR=0 -DENABLE_CLICKHOUSE_ODBC_BRIDGE=0 -DENABLE_CLICKHOUSE_STATIC_FILES_DISK_UPLOADER=0 \
    -DENABLE_KAFKA=1 -DENABLE_LIBPQXX=1 -DENABLE_NATS=0 -DENABLE_AMQPCPP=0 -DENABLE_NURAFT=0 \
    -DENABLE_CASSANDRA=0 -DENABLE_ODBC=0 -DENABLE_NLP=0 \
    -DENABLE_LDAP=0 \
    -DENABLE_CLIENT_AI=1 \
    ${MYSQL} \
    ${HDFS} \
    -DENABLE_LIBRARIES=0 ${RUST_FEATURES} \
    ${GLIBC_COMPATIBILITY} \
    -DENABLE_UTILS=0 ${LLVM} ${UNWIND} \
    ${ICU} -DENABLE_UTF8PROC=1 ${JEMALLOC} \
    -DENABLE_PARQUET=1 -DENABLE_ROCKSDB=1 -DENABLE_SQLITE=1 -DENABLE_VECTORSCAN=1 \
    -DENABLE_PROTOBUF=1 -DENABLE_THRIFT=1 -DENABLE_MSGPACK=1 \
    -DENABLE_BROTLI=1 -DENABLE_H3=1 -DENABLE_CURL=1 \
    -DENABLE_CLICKHOUSE_ALL=0 -DUSE_STATIC_LIBRARIES=1 -DSPLIT_SHARED_LIBRARIES=0 \
    -DENABLE_SIMDJSON=1 -DENABLE_RAPIDJSON=1 \
    ${CPU_FEATURES} \
    -DENABLE_AVX512=0 -DENABLE_AVX512_VBMI=0 \
    -DENABLE_BASE64=1 \
    -DENABLE_LIBFIU=1 \
    -DCHDB_VERSION=${CHDB_VERSION} \
    "

# Build chdb python module for Python 3.13 only
py_version="3.13"
current_py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$current_py_version" != "$py_version" ]; then
    echo "Error: Current Python version is $current_py_version, but required version is $py_version"
    echo "Please switch to Python $py_version"
    exit 1
fi
echo "Using Python version: $current_py_version"
cmake ${CMAKE_ARGS} -DENABLE_PYTHON=1 -DPYBIND11_NONLIMITEDAPI_PYTHON_HEADERS_VERSION=${py_version} ..
ninja -d keeprsp || true

BINARY=${BUILD_DIR}/programs/clickhouse

# del the binary and run ninja -v again to capture the command, then modify it to generate CHDB_PY_MODULE
/bin/rm -f ${BINARY}
cd ${BUILD_DIR}
ninja -d keeprsp -v > build.log || true

USING_RESPONSE_FILE=$(grep -m 1 'clang++.*-o programs/clickhouse .*' build.log | grep '@CMakeFiles/clickhouse.rsp' || true)

if [ ! "${USING_RESPONSE_FILE}" == "" ]; then
    if [ -f CMakeFiles/clickhouse.rsp ]; then
        cp -a CMakeFiles/clickhouse.rsp CMakeFiles/pychdb.rsp
    else
        echo "CMakeFiles/clickhouse.rsp not found"
        exit 1
    fi
fi

# extract the command to generate CHDB_PY_MODULE
PYCHDB_CMD=$(grep -m 1 'clang++.*-o programs/clickhouse .*' build.log \
    | sed "s/-o programs\/clickhouse/-fPIC -Wl,-undefined,dynamic_lookup -shared -o ${CHDB_PY_MODULE}/" \
    | sed 's/^[^&]*&& //' | sed 's/&&.*//' \
    | sed 's/ -Wl,-undefined,error/ -Wl,-undefined,dynamic_lookup/g' \
    | sed 's/ -Xlinker --no-undefined//g' \
    | sed 's/@CMakeFiles\/clickhouse.rsp/@CMakeFiles\/pychdb.rsp/g' \
     )

# Linux specific: remove stubFree.c.o and add wrap options
PYCHDB_CMD=$(echo ${PYCHDB_CMD} | sed 's/ src\/CMakeFiles\/clickhouse_malloc.dir\/Common\/stubFree.c.o//g')
PYCHDB_CMD=$(echo ${PYCHDB_CMD} | sed 's/ -DUSE_JEMALLOC=1/ -DUSE_JEMALLOC=1 -Wl,-wrap,malloc -Wl,-wrap,valloc -Wl,-wrap,pvalloc -Wl,-wrap,calloc -Wl,-wrap,realloc -Wl,-wrap,memalign -Wl,-wrap,aligned_alloc -Wl,-wrap,posix_memalign -Wl,-wrap,free/g')
if [ ! "${USING_RESPONSE_FILE}" == "" ]; then
    ${SED_INPLACE} 's/ src\/CMakeFiles\/clickhouse_malloc.dir\/Common\/stubFree.c.o//g' CMakeFiles/pychdb.rsp
    ${SED_INPLACE} 's/ -DUSE_JEMALLOC=1/ -DUSE_JEMALLOC=1 -Wl,-wrap,malloc -Wl,-wrap,valloc -Wl,-wrap,pvalloc -Wl,-wrap,calloc -Wl,-wrap,realloc -Wl,-wrap,memalign -Wl,-wrap,aligned_alloc -Wl,-wrap,posix_memalign -Wl,-wrap,free/g' CMakeFiles/pychdb.rsp
fi

PYCHDB_CMD=$(echo ${PYCHDB_CMD} | sed 's|-Wl,-rpath,/[^[:space:]]*/pybind11-cmake|-Wl,-rpath,\$ORIGIN|g')
PYCHDB_CMD="${PYCHDB_CMD} -Wl,--undefined=PyInit__chdb -Wl,--version-script=${CHDB_DIR}/pychdb_export.map"

# save the command to a file for debug
echo ${PYCHDB_CMD} > pychdb_cmd.sh

${PYCHDB_CMD}

ls -lh ${CHDB_PY_MODULE}

## check all the so files
LIBCHDB_DIR=${BUILD_DIR}/
PYCHDB=${LIBCHDB_DIR}/${CHDB_PY_MODULE}

rm -f ${CHDB_DIR}/*.so
cp -a ${PYCHDB} ${CHDB_DIR}/${CHDB_PY_MODULE}

cd ${PROJ_DIR} && pwd

ccache -s || true

# Build pybind11 for Python 3.13 only
CMAKE_ARGS="${CMAKE_ARGS}" bash ${DIR}/build_pybind11.sh --version=3.13

echo -e "\nBuild completed for Python ${py_version} on Linux ARM64"
