#!python3

import os
import unittest
import platform
from chdb import session
from utils import is_musl_linux


def should_skip_delta_lake_test():
    """Skip on Linux x86_64 (glibc) and musl Linux due to S3 permission issues"""
    if platform.system() != "Linux":
        return True
    if is_musl_linux():
        return True
    return False

# chdb-core-lite disables ENABLE_DELTA_KERNEL_RS; the deltaLake() table function
# is absent from TableFunctionFactory and any call raises Code 46.
_LITE = os.environ.get("CHDB_LITE") == "1"


@unittest.skipIf(should_skip_delta_lake_test(), "Skipping on Linux x86_64 due to S3 access permissions")
class TestDeltaLake(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

    def test_delta_lake(self):
        sess = session.Session()

        sql = '''
            SELECT
                URL,
                UserAgent
            FROM deltaLake('https://clickhouse-public-datasets.s3.amazonaws.com/delta_lake/hits/', NOSIGN)
            WHERE URL IS NULL
            LIMIT 2
            '''
        if _LITE:
            with self.assertRaises(Exception) as ctx:
                sess.query(sql)
            self.assertIn("Code: 46", str(ctx.exception))
            return
        ret = sess.query(sql)
        self.assertEqual(ret.rows_read(), 0)


if __name__ == "__main__":
    unittest.main()
