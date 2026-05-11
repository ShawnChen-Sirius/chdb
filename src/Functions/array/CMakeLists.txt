include("${ClickHouse_SOURCE_DIR}/cmake/dbms_glob_sources.cmake")
include(CMakePrintHelpers)

add_headers_and_sources(clickhouse_functions_array .)

option(CHDB_TRIM_VECTOR_DISTANCE "Drop arrayDistance/distanceTransposed/arrayNormalizedGini/arrayDotProduct/arrayLevenshtein" OFF)
if (CHDB_TRIM_VECTOR_DISTANCE)
    message(STATUS "CHDB_TRIM_VECTOR_DISTANCE: dropping arrayDistance/distanceTransposed/arrayNormalizedGini/arrayDotProduct/arrayLevenshtein")
    foreach (_drop arrayDistance.cpp distanceTransposed.cpp arrayNormalizedGini.cpp arrayDotProduct.cpp arrayLevenshtein.cpp mapPopulateSeries.cpp mapOp.cpp arrayShingles.cpp arrayJaccardIndex.cpp arrayShiftRotate.cpp arrayCumSum.cpp arrayCumSumNonNegative.cpp arrayDifference.cpp arrayFold.cpp arrayAUC.cpp arrayRandomSample.cpp arrayShuffle.cpp arrayEnumerateDense.cpp arrayEnumerateDenseRanked.cpp arrayEnumerateUniqRanked.cpp)
        list(REMOVE_ITEM clickhouse_functions_array_sources "${_drop}" "./${_drop}")
    endforeach()
    set(_chdb_vec_stub "${CMAKE_CURRENT_BINARY_DIR}/chdbVectorStubs.cpp")
    file(WRITE "${_chdb_vec_stub}"
        "// chdb stubs: vector helpers throw at call site (functions register but error when invoked)\n"
        "#include <Functions/IFunction.h>\n"
        "#include <Interpreters/Context_fwd.h>\n"
        "#include <Common/Exception.h>\n"
        "namespace DB {\n"
        "namespace ErrorCodes { extern const int NOT_IMPLEMENTED; }\n"
        "#define CHDB_VEC_STUB { throw Exception(ErrorCodes::NOT_IMPLEMENTED, \"chdb: vector functions disabled at build time\"); }\n"
        "FunctionPtr createFunctionArrayL1Distance(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayL2Distance(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayL2SquaredDistance(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayLpDistance(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayLinfDistance(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayCosineDistance(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayL2DistanceTransposed(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayCosineDistanceTransposed(ContextPtr) CHDB_VEC_STUB\n"
        "FunctionPtr createFunctionArrayDotProduct(ContextPtr) CHDB_VEC_STUB\n"
        "}\n")
    list(APPEND clickhouse_functions_array_sources "${_chdb_vec_stub}")
endif()

# createInternalFunctionHasOverloadResolver, FunctionArrayResize,  FunctionEmptyArrayToSingle
# Used by ArrayExistsToHasPass.cpp and ArrayJoinAction.cpp
set(DBMS_ARRAY_FUNCTIONS
    arrayResize.cpp
    has.cpp
    emptyArrayToSingle.cpp
)
extract_into_parent_list(clickhouse_functions_array_sources dbms_sources ${DBMS_ARRAY_FUNCTIONS})
extract_into_parent_list(clickhouse_functions_headers dbms_headers arrayResize.h has.h emptyArrayToSingle.h)

add_library(clickhouse_functions_array OBJECT ${clickhouse_functions_array_sources} ${clickhouse_functions_array_headers})
target_link_libraries(clickhouse_functions_array PRIVATE dbms clickhouse_functions_gatherutils ch_contrib::stringzilla)

if (TARGET ch_contrib::vectorscan)
    target_link_libraries(clickhouse_functions_array PRIVATE ch_contrib::vectorscan)
endif()

# Libcxx hardening means out-of-bounds checks which causes noticeable degradations for some workflows.
# TUs where libcxx hardening needs to be disabled are specified here.
set_source_files_properties(array.cpp PROPERTIES COMPILE_FLAGS "-U_LIBCPP_HARDENING_MODE -D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_NONE")

if (OMIT_HEAVY_DEBUG_SYMBOLS)
    target_compile_options(clickhouse_functions_array PRIVATE "-g1")
endif()
