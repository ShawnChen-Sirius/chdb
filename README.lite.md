<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/chdb-io/chdb/raw/main/docs/_static/snake-chdb-dark.png" height="130">
  <img src="https://github.com/chdb-io/chdb/raw/main/docs/_static/snake-chdb.png" height="130">
</picture>
</div>

# chdb-core-lite

> A lightweight build of [chdb-core](https://pypi.org/project/chdb-core/) — the in-process OLAP SQL engine powered by ClickHouse, trimmed down for environments where install footprint matters.

`chdb-core-lite` keeps the full ClickHouse SQL engine and all the most commonly used chdb-core APIs (`Session`, `Connection`, DB-API, Parquet / Arrow / JSON I/O, S3, HTTP, the standard SQL functions and data types). To shrink the wheel, a set of optional integration libraries is disabled at build time.

It is **API-compatible** with `chdb-core`: code written against `chdb-core` runs unchanged against `chdb-core-lite`, as long as it doesn't rely on one of the disabled integrations.

## When to use chdb-core-lite

Pick `chdb-core-lite` whenever the package or installed footprint matters more to you than every optional integration, for example:

- **Serverless functions** with strict deployment-size limits (AWS Lambda, Google Cloud Functions, Azure Functions, Cloudflare Workers).
- **Container images** where a smaller base layer means faster cold starts, cheaper registry storage, and quicker autoscaling.
- **Edge / embedded / IoT** deployments with limited disk space.
- **CI pipelines** where install time and bandwidth dominate the run.
- **Notebook / sandbox environments** (Pyodide-style, ephemeral VMs) where every megabyte counts.

If you need any of the integrations that are turned off in lite (HDFS, MySQL, PostgreSQL, MongoDB, Kafka, NATS, AMQP, Cassandra, RocksDB, SQLite, Avro, Hive, Azure Blob Storage, ICU, embedded compiler, etc.), install the full [`chdb-core`](https://pypi.org/project/chdb-core/) instead.

## Installation

```bash
pip install chdb-core-lite
```

`chdb-core` and `chdb-core-lite` install the same Python module (`_chdb`) and therefore **must not be installed in the same environment**. Pick one.

## Documentation

For the full feature documentation, API reference and examples, see the chdb-core docs: <https://chdb.readthedocs.io/>

## License

Apache 2.0 — see [LICENSE.txt](https://github.com/chdb-io/chdb-core/blob/main/LICENSE.txt).
