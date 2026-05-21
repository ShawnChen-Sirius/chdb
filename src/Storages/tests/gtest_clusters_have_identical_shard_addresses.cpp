/// Unit tests for StorageDistributed::clustersHaveIdenticalShardAddresses.
///
/// The helper is the field-by-field comparator that StorageDistributed's
/// per-shard pushdown uses to detect equivalent sibling remote()/remoteSecure()
/// table function calls. It must return true iff the two clusters have
/// identical shard topology AND, replica-by-replica, identical host_name,
/// port, user, password, default_database, and secure flag.

#include <Storages/StorageDistributed.h>
#include <Interpreters/Cluster.h>
#include <Core/Settings.h>
#include <Common/Priority.h>

#include <gtest/gtest.h>

#include <memory>
#include <string>
#include <vector>

using namespace DB;

namespace
{

/// All by-reference members of ClusterConnectionParameters live in this RAII bundle so
/// the resulting Cluster does not dangle on a temporary.
struct Bundle
{
    Settings settings;
    String user;
    String password;
    String bind_host;
    UInt16 port;
    bool secure;

    Bundle(String user_, String password_, UInt16 port_, bool secure_)
        : user(std::move(user_)), password(std::move(password_)), bind_host(""), port(port_), secure(secure_) {}

    ClusterConnectionParameters params() const
    {
        return ClusterConnectionParameters{
            user,
            password,
            port,
            /*treat_local_as_remote=*/false,
            /*treat_local_port_as_remote=*/false,
            secure,
            bind_host,
            /*priority=*/Priority{1},
            /*cluster_name=*/"",
            /*cluster_secret=*/"",
        };
    }

    std::shared_ptr<Cluster> cluster(const std::vector<std::vector<String>> & shard_hosts) const
    {
        auto p = params();
        return std::make_shared<Cluster>(settings, shard_hosts, p);
    }
};

} // namespace


TEST(ClustersHaveIdenticalShardAddresses, IdenticalSingleShardSingleReplica)
{
    Bundle b{"default", "", 9440, /*secure=*/true};
    auto a = b.cluster({{"py19xfh7zn.us-east-1.vpce.aws.clickhouse.cloud:9440"}});
    auto c = b.cluster({{"py19xfh7zn.us-east-1.vpce.aws.clickhouse.cloud:9440"}});
    EXPECT_TRUE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentHostName)
{
    Bundle b{"default", "", 9440, /*secure=*/true};
    auto a = b.cluster({{"py19xfh7zn.us-east-1.vpce.aws.clickhouse.cloud:9440"}});
    auto c = b.cluster({{"127.0.0.1:9440"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentPort)
{
    Bundle b1{"default", "", 9440, /*secure=*/true};
    Bundle b2{"default", "",  9000, /*secure=*/true};
    auto a = b1.cluster({{"example.com:9440"}});
    auto c = b2.cluster({{"example.com:9000"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentUser)
{
    Bundle b_default{"default", "", 9440, /*secure=*/true};
    Bundle b_readonly{"readonly", "", 9440, /*secure=*/true};
    auto a = b_default.cluster({{"example.com:9440"}});
    auto c = b_readonly.cluster({{"example.com:9440"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentPassword)
{
    Bundle b_a{"default", "secret-a", 9440, /*secure=*/true};
    Bundle b_b{"default", "secret-b", 9440, /*secure=*/true};
    auto a = b_a.cluster({{"example.com:9440"}});
    auto c = b_b.cluster({{"example.com:9440"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentSecureFlag)
{
    Bundle b_secure{"default", "", 9440, /*secure=*/true};
    Bundle b_plain {"default", "", 9440, /*secure=*/false};
    auto a = b_secure.cluster({{"example.com:9440"}});
    auto c = b_plain.cluster ({{"example.com:9440"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentNumberOfShards)
{
    Bundle b{"default", "", 9440, /*secure=*/true};
    auto one_shard  = b.cluster({{"a.example.com:9440"}});
    auto two_shards = b.cluster({{"a.example.com:9440"}, {"b.example.com:9440"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*one_shard, *two_shards));
}

TEST(ClustersHaveIdenticalShardAddresses, DifferentNumberOfReplicas)
{
    Bundle b{"default", "", 9440, /*secure=*/true};
    auto one_replica  = b.cluster({{"a.example.com:9440"}});
    auto two_replicas = b.cluster({{"a.example.com:9440", "b.example.com:9440"}});
    EXPECT_FALSE(StorageDistributed::clustersHaveIdenticalShardAddresses(*one_replica, *two_replicas));
}

TEST(ClustersHaveIdenticalShardAddresses, IdenticalMultiShardMultiReplica)
{
    Bundle b{"default", "", 9440, /*secure=*/true};
    auto a = b.cluster({{"a.example.com:9440", "b.example.com:9440"}, {"c.example.com:9440"}});
    auto c = b.cluster({{"a.example.com:9440", "b.example.com:9440"}, {"c.example.com:9440"}});
    EXPECT_TRUE(StorageDistributed::clustersHaveIdenticalShardAddresses(*a, *c));
}
