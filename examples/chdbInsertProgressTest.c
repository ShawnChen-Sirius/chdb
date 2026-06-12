/**
 * chdbInsertProgressTest.c
 *
 * Smoke test for INSERT write-progress accessors on chdb_result
 * (chdb_result_rows_written / chdb_result_bytes_written), issue #88.
 *
 * Verifies:
 *   1. SELECT reports zero write progress.
 *   2. Plain INSERT reports the number of rows written.
 *   3. INSERT ... SELECT reports the number of rows written.
 *   4. INSERT into a table with an attached materialized view includes the
 *      cascaded MV writes (same semantics as the HTTP interface's
 *      X-ClickHouse-Summary.written_rows).
 *
 * Build (against an already-built libchdb.so):
 *   clang examples/chdbInsertProgressTest.c -I./programs/local \
 *         -L. -lchdb -o examples/chdbInsertProgressTest
 *   LD_LIBRARY_PATH=. ./examples/chdbInsertProgressTest
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "chdb.h"

static int g_failed_assertions = 0;

#define CHECK(cond, msg)                                                   \
    do {                                                                   \
        if (!(cond)) {                                                     \
            fprintf(stderr, "  ASSERT FAIL: %s (%s:%d)\n",                 \
                    (msg), __FILE__, __LINE__);                            \
            g_failed_assertions += 1;                                      \
        }                                                                  \
    } while (0)

/* Runs a query, asserts it succeeded, and returns the result handle. */
static chdb_result * run(chdb_connection conn, const char * query)
{
    chdb_result * result = chdb_query(conn, query, "CSV");
    CHECK(result != NULL, query);
    if (result) {
        const char * error = chdb_result_error(result);
        if (error) {
            fprintf(stderr, "  query error: %s\n  query: %s\n", error, query);
            g_failed_assertions += 1;
        }
    }
    return result;
}

static void test_select_reports_zero_written(chdb_connection conn)
{
    printf("== test_select_reports_zero_written ==\n");
    chdb_result * result = run(conn, "SELECT number FROM numbers(10)");
    if (!result)
        return;

    CHECK(chdb_result_rows_read(result) == 10, "rows_read == 10");
    CHECK(chdb_result_rows_written(result) == 0, "rows_written == 0 for SELECT");
    CHECK(chdb_result_bytes_written(result) == 0, "bytes_written == 0 for SELECT");
    chdb_destroy_query_result(result);
}

static void test_plain_insert_reports_written(chdb_connection conn)
{
    printf("== test_plain_insert_reports_written ==\n");
    chdb_result * setup = run(conn,
        "CREATE TABLE insert_progress_plain (k UInt32, v String) ENGINE = MergeTree ORDER BY k");
    if (setup)
        chdb_destroy_query_result(setup);

    chdb_result * result = run(conn,
        "INSERT INTO insert_progress_plain FORMAT JSONEachRow\n"
        "{\"k\":1,\"v\":\"a\"}\n{\"k\":2,\"v\":\"b\"}\n{\"k\":3,\"v\":\"c\"}\n");
    if (!result)
        return;

    uint64_t rows_written = chdb_result_rows_written(result);
    uint64_t bytes_written = chdb_result_bytes_written(result);
    printf("  rows_written=%" PRIu64 " bytes_written=%" PRIu64 "\n", rows_written, bytes_written);
    CHECK(rows_written == 3, "rows_written == 3 for 3-row INSERT");
    CHECK(bytes_written > 0, "bytes_written > 0 for 3-row INSERT");
    chdb_destroy_query_result(result);
}

static void test_insert_select_reports_written(chdb_connection conn)
{
    printf("== test_insert_select_reports_written ==\n");
    chdb_result * setup = run(conn,
        "CREATE TABLE insert_progress_sel (n UInt64) ENGINE = MergeTree ORDER BY n");
    if (setup)
        chdb_destroy_query_result(setup);

    chdb_result * result = run(conn,
        "INSERT INTO insert_progress_sel SELECT number FROM numbers(1000)");
    if (!result)
        return;

    uint64_t rows_written = chdb_result_rows_written(result);
    printf("  rows_written=%" PRIu64 "\n", rows_written);
    CHECK(rows_written == 1000, "rows_written == 1000 for INSERT SELECT");
    CHECK(chdb_result_bytes_written(result) > 0, "bytes_written > 0 for INSERT SELECT");
    chdb_destroy_query_result(result);
}

static void test_insert_with_mv_includes_cascade(chdb_connection conn)
{
    printf("== test_insert_with_mv_includes_cascade ==\n");
    chdb_result * setup;
    setup = run(conn,
        "CREATE TABLE insert_progress_src (k UInt32) ENGINE = MergeTree ORDER BY k");
    if (setup)
        chdb_destroy_query_result(setup);
    setup = run(conn,
        "CREATE MATERIALIZED VIEW insert_progress_mv "
        "ENGINE = MergeTree ORDER BY k AS SELECT k FROM insert_progress_src");
    if (setup)
        chdb_destroy_query_result(setup);

    chdb_result * result = run(conn,
        "INSERT INTO insert_progress_src VALUES (1), (2)");
    if (!result)
        return;

    uint64_t rows_written = chdb_result_rows_written(result);
    printf("  rows_written=%" PRIu64 " (2 source + 2 cascaded MV)\n", rows_written);
    CHECK(rows_written == 4, "rows_written == 4: includes cascaded MV writes");
    chdb_destroy_query_result(result);
}

int main(int argc, char ** argv)
{
    (void)argc; (void)argv;

    char arg0[] = "clickhouse";
    char arg1[] = "--multiquery";
    char * args[] = {arg0, arg1};
    chdb_connection * conn = chdb_connect(2, args);
    if (!conn) {
        fprintf(stderr, "chdb_connect failed\n");
        return 1;
    }

    test_select_reports_zero_written(*conn);
    test_plain_insert_reports_written(*conn);
    test_insert_select_reports_written(*conn);
    test_insert_with_mv_includes_cascade(*conn);

    chdb_close_conn(conn);

    printf("\n== summary: %d failed assertions ==\n", g_failed_assertions);
    return g_failed_assertions == 0 ? 0 : 1;
}
