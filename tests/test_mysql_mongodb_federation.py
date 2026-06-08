#!/usr/bin/env python3
"""End-to-end federation roundtrip tests for MySQL and MongoDB (issue #82).

Like test_remote_query.py (the remote()/remoteSecure() suite), these need a live
server and are therefore env-gated: each class skips unless its connection env
vars are set AND the corresponding Python driver (pymysql / pymongo) is
installed. They are NOT expected to run in the default CI wheel jobs (no DB
server there) -- the always-on wiring checks live in
test_mysql_mongodb_integration.py. Run locally with, e.g.:

    CHDB_TEST_MYSQL_HOST=127.0.0.1:3306 CHDB_TEST_MYSQL_USER=root \
    CHDB_TEST_MYSQL_PASSWORD=secret CHDB_TEST_MYSQL_DB=test \
        python -m unittest tests.test_mysql_mongodb_federation -v

Fixtures are created/torn down via the native driver (mirroring how ClickHouse's
own integration tests seed MySQL/MongoDB), then queried through chDB's mysql()/
mongodb() table functions to prove a real cross-engine roundtrip:
read, count pushdown, JOIN with a local table, and (MySQL) write-back.

Skipped under CHDB_LITE=1.
"""

import os
import unittest
import uuid

from chdb import session as chs

_LITE = os.environ.get("CHDB_LITE") == "1"
_SUFFIX = uuid.uuid4().hex[:8]


def _split_host_port(hostport, default_port):
    host, _, port = hostport.partition(":")
    return host, int(port) if port else default_port


# --------------------------------------------------------------------------- #
# MySQL
# --------------------------------------------------------------------------- #
_MYSQL_HOST = os.environ.get("CHDB_TEST_MYSQL_HOST")
_MYSQL_USER = os.environ.get("CHDB_TEST_MYSQL_USER")
_MYSQL_PASSWORD = os.environ.get("CHDB_TEST_MYSQL_PASSWORD", "")
_MYSQL_DB = os.environ.get("CHDB_TEST_MYSQL_DB", "test")

try:
    import pymysql  # noqa: F401
    _HAVE_PYMYSQL = True
except ImportError:
    _HAVE_PYMYSQL = False


@unittest.skipIf(_LITE, "MySQL is intentionally absent in chdb-core-lite")
@unittest.skipUnless(_MYSQL_HOST and _MYSQL_USER, "set CHDB_TEST_MYSQL_HOST/USER to run")
@unittest.skipUnless(_HAVE_PYMYSQL, "pymysql not installed (needed to seed the MySQL fixture)")
class TestMySQLFederationRoundtrip(unittest.TestCase):
    table = f"chdb_fed_{_SUFFIX}"

    @classmethod
    def setUpClass(cls):
        import pymysql
        host, port = _split_host_port(_MYSQL_HOST, 3306)
        cls.conn = pymysql.connect(host=host, port=port, user=_MYSQL_USER,
                                   password=_MYSQL_PASSWORD, database=_MYSQL_DB,
                                   autocommit=True)
        with cls.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {cls.table}")
            cur.execute(f"CREATE TABLE {cls.table} (id INT PRIMARY KEY, name VARCHAR(64))")
            cur.executemany(
                f"INSERT INTO {cls.table} (id, name) VALUES (%s, %s)",
                [(1, "alice"), (2, "bob"), (3, "carol")],
            )

    @classmethod
    def tearDownClass(cls):
        with cls.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {cls.table}")
        cls.conn.close()

    def setUp(self):
        self.s = chs.Session()
        self.tf = (f"mysql('{_MYSQL_HOST}', '{_MYSQL_DB}', '{self.table}', "
                   f"'{_MYSQL_USER}', '{_MYSQL_PASSWORD}')")

    def tearDown(self):
        self.s.close()

    def _csv(self, sql):
        return str(self.s.query(sql, "CSV")).strip()

    def test_read_all_rows(self):
        out = self._csv(f"SELECT id, name FROM {self.tf} ORDER BY id")
        self.assertEqual('1,"alice"\n2,"bob"\n3,"carol"', out)

    def test_count_and_filter_pushdown(self):
        self.assertEqual("3", self._csv(f"SELECT count() FROM {self.tf}"))
        self.assertEqual('"bob"', self._csv(f"SELECT name FROM {self.tf} WHERE id = 2"))

    def test_join_remote_with_local(self):
        # Join MySQL rows against a local table -> proves cross-engine federation.
        out = self._csv(
            f"SELECT m.name FROM {self.tf} AS m "
            f"INNER JOIN (SELECT 2 AS id UNION ALL SELECT 3) AS l ON m.id = l.id "
            f"ORDER BY m.id"
        )
        self.assertEqual('"bob"\n"carol"', out)

    def test_write_back_via_insert_into_function(self):
        self.s.query(f"INSERT INTO FUNCTION {self.tf} (id, name) VALUES (4, 'dave')")
        self.assertEqual("4", self._csv(f"SELECT count() FROM {self.tf}"))
        self.assertEqual('"dave"', self._csv(f"SELECT name FROM {self.tf} WHERE id = 4"))


# --------------------------------------------------------------------------- #
# MongoDB
# --------------------------------------------------------------------------- #
_MONGO_HOST = os.environ.get("CHDB_TEST_MONGODB_HOST")
_MONGO_USER = os.environ.get("CHDB_TEST_MONGODB_USER", "")
_MONGO_PASSWORD = os.environ.get("CHDB_TEST_MONGODB_PASSWORD", "")
_MONGO_DB = os.environ.get("CHDB_TEST_MONGODB_DB", "test")

try:
    import pymongo  # noqa: F401
    _HAVE_PYMONGO = True
except ImportError:
    _HAVE_PYMONGO = False


@unittest.skipIf(_LITE, "MongoDB is intentionally absent in chdb-core-lite")
@unittest.skipUnless(_MONGO_HOST, "set CHDB_TEST_MONGODB_HOST to run")
@unittest.skipUnless(_HAVE_PYMONGO, "pymongo not installed (needed to seed the MongoDB fixture)")
class TestMongoDBFederationRoundtrip(unittest.TestCase):
    collection = f"chdb_fed_{_SUFFIX}"

    @classmethod
    def setUpClass(cls):
        import pymongo
        host, port = _split_host_port(_MONGO_HOST, 27017)
        kwargs = dict(host=host, port=port)
        if _MONGO_USER:
            kwargs.update(username=_MONGO_USER, password=_MONGO_PASSWORD)
        cls.client = pymongo.MongoClient(**kwargs)
        coll = cls.client[_MONGO_DB][cls.collection]
        coll.drop()
        coll.insert_many([
            {"id": 1, "name": "alice"},
            {"id": 2, "name": "bob"},
            {"id": 3, "name": "carol"},
        ])

    @classmethod
    def tearDownClass(cls):
        cls.client[_MONGO_DB][cls.collection].drop()
        cls.client.close()

    def setUp(self):
        self.s = chs.Session()
        self.tf = (f"mongodb('{_MONGO_HOST}', '{_MONGO_DB}', '{self.collection}', "
                   f"'{_MONGO_USER}', '{_MONGO_PASSWORD}', 'id Int32, name String')")

    def tearDown(self):
        self.s.close()

    def _csv(self, sql):
        return str(self.s.query(sql, "CSV")).strip()

    def test_read_all_rows(self):
        out = self._csv(f"SELECT id, name FROM {self.tf} ORDER BY id")
        self.assertEqual('1,"alice"\n2,"bob"\n3,"carol"', out)

    def test_count_and_filter(self):
        self.assertEqual("3", self._csv(f"SELECT count() FROM {self.tf}"))
        self.assertEqual('"carol"', self._csv(f"SELECT name FROM {self.tf} WHERE id = 3"))

    def test_join_remote_with_local(self):
        out = self._csv(
            f"SELECT m.name FROM {self.tf} AS m "
            f"INNER JOIN (SELECT 1 AS id UNION ALL SELECT 3) AS l ON m.id = l.id "
            f"ORDER BY m.id"
        )
        self.assertEqual('"alice"\n"carol"', out)


if __name__ == "__main__":
    unittest.main()
