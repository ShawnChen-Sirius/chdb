# The file StorageSystemContributors.cpp is generated at release time and committed to the source tree.
# You can also regenerate it manually this way:
# execute_process(COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/StorageSystemContributors.sh")

get_property(TZDATA_VERSION GLOBAL PROPERTY TZDATA_VERSION_PROP)
get_property(OPENSSL_VERSION GLOBAL PROPERTY OPENSSL_VERSION_PROP)

function(generate_system_build_options)
    include(${ClickHouse_SOURCE_DIR}/src/configure_config.cmake)
    configure_file(StorageSystemBuildOptions.cpp.in StorageSystemBuildOptions.generated.cpp)
endfunction()

generate_system_build_options()

include("${ClickHouse_SOURCE_DIR}/cmake/dbms_glob_sources.cmake")
add_headers_and_sources(storages_system .)
list (APPEND storages_system_sources StorageSystemBuildOptions.generated.cpp)

if (NOT TARGET ch_contrib::icu)
    list(REMOVE_ITEM storages_system_sources StorageSystemUnicode.cpp)
endif()

add_custom_target(generate-contributors
    ./StorageSystemContributors.sh
    SOURCES StorageSystemContributors.sh
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    # BYPRODUCTS StorageSystemContributors.generated.cpp
)

if(NOT TARGET generate-source)
    add_custom_target(generate-source)
endif()

add_dependencies(generate-source generate-contributors)

set(GENERATED_LICENSES_SRC "${CMAKE_CURRENT_BINARY_DIR}/StorageSystemLicenses.generated.cpp")

# StorageSystemLicenses.sh shells out to `gfind`/`ggrep` on macOS (assumed
# present per upstream ClickHouse setup). When GNU findutils is missing, the
# script exits midway under `set -e -o pipefail` and the generated file is
# left with only the `library_licenses[] = {` prefix, breaking the build.
# Fall back to a syntactically valid empty stub in that case so downstream
# targets still compile; the system.licenses table is rarely queried in chDB
# embedded use.
add_custom_command(
    OUTPUT StorageSystemLicenses.generated.cpp
    COMMAND bash -c "./StorageSystemLicenses.sh '${CMAKE_SOURCE_DIR}' > '${GENERATED_LICENSES_SRC}' ; \
        if ! grep -q nullptr '${GENERATED_LICENSES_SRC}' ; then \
            printf '%s\\n' \
                '// stub: StorageSystemLicenses.sh produced no usable output (likely missing GNU findutils on macOS).' \
                'const char * library_licenses[] = {' \
                '    nullptr' \
                '};' > '${GENERATED_LICENSES_SRC}' ; \
        fi"
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

list (APPEND storages_system_sources ${GENERATED_LICENSES_SRC})

# Overlength strings
set_source_files_properties(${GENERATED_LICENSES_SRC} PROPERTIES COMPILE_FLAGS -w)

list (SORT storages_system_sources) # Reproducible build
add_library(clickhouse_storages_system ${storages_system_sources})

target_link_libraries(clickhouse_storages_system PRIVATE
    dbms
    common
    clickhouse_common_zookeeper_base
    clickhouse_common_zookeeper
    clickhouse_parsers
    Poco::JSON
)

if (TARGET ch_contrib::icu)
    target_link_libraries(clickhouse_storages_system PRIVATE ch_contrib::icu)
    target_compile_definitions(clickhouse_storages_system PRIVATE U_HIDE_DEPRECATED_API)
endif()