#pragma once

#include <array>
#include <base/constexpr_helpers.h>

#include <Interpreters/HashJoin/HashJoin.h>


/** Used in implementation of Join to process different data structures.
  */

namespace DB
{

/// HashJoin::MapsOne is more efficient, it only store one row for each key in the map. It is recommended to use it whenever possible.
/// When only need to match only one row from right table, use HashJoin::MapsOne. For example, LEFT ANY/SEMI/ANTI.
///
/// HashJoin::MapsAll will store all rows for each key in the map. It is used when need to match multiple rows from right table.
/// For example, LEFT ALL, INNER ALL, RIGHT ALL/ANY.
///
/// prefer_use_maps_all is true when there is mixed inequal condition in the join condition. For example, `t1.a = t2.a AND t1.b > t2.b`.
/// In this case, we need to use HashJoin::MapsAll to store all rows for each key in the map. We will select all matched rows from the map
/// and filter them by `t1.b > t2.b`.
///
/// flagged indicates whether we need to store flags for each row whether it has been used in the join. See JoinUsedFlags.h.
template <JoinKind kind, JoinStrictness join_strictness, bool prefer_use_maps_all>
struct MapGetter;

template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Right, JoinStrictness::RightAny, prefer_use_maps_all> { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Full, JoinStrictness::RightAny, prefer_use_maps_all>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };

template <> struct MapGetter<JoinKind::Inner, JoinStrictness::RightAny, false> { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Inner, JoinStrictness::RightAny, true> { using Map = HashJoin::MapsAll; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Left, JoinStrictness::RightAny, false> { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Left, JoinStrictness::RightAny, true> { using Map = HashJoin::MapsAll; static constexpr bool flagged = false; };

template <> struct MapGetter<JoinKind::Left, JoinStrictness::Any, false>  { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Left, JoinStrictness::Any, true>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Inner, JoinStrictness::Any, true> { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <> struct MapGetter<JoinKind::Inner, JoinStrictness::Any, false> { using Map = HashJoin::MapsOne; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Right, JoinStrictness::Any, prefer_use_maps_all> { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Full, JoinStrictness::Any, prefer_use_maps_all>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };

template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Left, JoinStrictness::All, prefer_use_maps_all>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = false; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Inner, JoinStrictness::All, prefer_use_maps_all> { using Map = HashJoin::MapsAll; static constexpr bool flagged = false; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Right, JoinStrictness::All, prefer_use_maps_all> { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Full, JoinStrictness::All, prefer_use_maps_all>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };

/// Only SEMI LEFT and SEMI RIGHT are valid. INNER and FULL are here for templates instantiation.
template <> struct MapGetter<JoinKind::Left, JoinStrictness::Semi, false>  { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Left, JoinStrictness::Semi, true>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = false; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Inner, JoinStrictness::Semi, prefer_use_maps_all> { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Right, JoinStrictness::Semi, prefer_use_maps_all> { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Full, JoinStrictness::Semi, prefer_use_maps_all>  { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };

/// Only ANTI LEFT and ANTI RIGHT are valid. INNER and FULL are here for templates instantiation.
template <> struct MapGetter<JoinKind::Left, JoinStrictness::Anti, false>  { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <> struct MapGetter<JoinKind::Left, JoinStrictness::Anti, true>  { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Inner, JoinStrictness::Anti, prefer_use_maps_all> { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Right, JoinStrictness::Anti, prefer_use_maps_all> { using Map = HashJoin::MapsAll; static constexpr bool flagged = true; };
template <bool prefer_use_maps_all> struct MapGetter<JoinKind::Full, JoinStrictness::Anti, prefer_use_maps_all>  { using Map = HashJoin::MapsOne; static constexpr bool flagged = false; };

template <JoinKind kind, bool prefer_use_maps_all>
struct MapGetter<kind, JoinStrictness::Asof, prefer_use_maps_all> { using Map = HashJoin::MapsAsof; static constexpr bool flagged = false; };

#if defined(CHDB_MINIMAL_HASH_JOIN) && CHDB_MINIMAL_HASH_JOIN
/// Aggressive trim: drop Asof/Semi/Anti. WARNING: empirically this hangs SEMI/ANTI
/// queries on chdb (not a clean throw), so the flag is currently kept OFF.
static constexpr std::array<JoinStrictness, 3> STRICTNESSES = {
    JoinStrictness::RightAny,
    JoinStrictness::Any,
    JoinStrictness::All,
};
#elif defined(CHDB_TRIM_HASH_JOIN_ASOF) && CHDB_TRIM_HASH_JOIN_ASOF
/// Safer trim: drop only Asof. SEMI / ANTI keep working. ASOF JOIN queries
/// throw "Wrong JOIN combination" cleanly.
static constexpr std::array<JoinStrictness, 5> STRICTNESSES = {
    JoinStrictness::RightAny,
    JoinStrictness::Any,
    JoinStrictness::All,
    JoinStrictness::Semi,
    JoinStrictness::Anti,
};
#else
static constexpr std::array<JoinStrictness, 6> STRICTNESSES = {
    JoinStrictness::RightAny,
    JoinStrictness::Any,
    JoinStrictness::All,
    JoinStrictness::Asof,
    JoinStrictness::Semi,
    JoinStrictness::Anti,
};
#endif

static constexpr std::array<JoinKind, 4> KINDS = {
    JoinKind::Left,
    JoinKind::Inner,
    JoinKind::Full,
    JoinKind::Right
};

/// Inner/Full × Semi/Anti are template-only artifacts: the SQL parser already
/// rejects them ("SEMI|ANTI JOIN should be LEFT or RIGHT"), so the runtime
/// branches are unreachable. When CHDB_TRIM_HASH_JOIN_NICHE is on, we skip
/// their instantiation at compile time and drop the matching .cpp stubs from
/// the build.
template <JoinKind kind, JoinStrictness strictness>
constexpr bool is_niche_hash_join_combo_v =
#if defined(CHDB_TRIM_HASH_JOIN_NICHE) && CHDB_TRIM_HASH_JOIN_NICHE
    (kind == JoinKind::Inner || kind == JoinKind::Full)
    && (strictness == JoinStrictness::Semi || strictness == JoinStrictness::Anti);
#else
    false;
#endif

/// Init specified join map
inline bool joinDispatchInit(JoinKind kind, JoinStrictness strictness, HashJoin::MapsVariant & maps, bool prefer_use_maps_all = false)
{
    return static_for<0, KINDS.size() * STRICTNESSES.size()>([&](auto ij)
    {
        constexpr auto i = ij / STRICTNESSES.size();
        constexpr auto j = ij % STRICTNESSES.size();
        if (kind == KINDS[i] && strictness == STRICTNESSES[j])
        {
            if (prefer_use_maps_all)
                maps = typename MapGetter<KINDS[i], STRICTNESSES[j], true>::Map();
            else
                maps = typename MapGetter<KINDS[i], STRICTNESSES[j], false>::Map();
            return true;
        }
        return false;
    });
}

/// Call function on specified join map
template <typename MapsVariant, typename Func>
inline bool joinDispatch(JoinKind kind, JoinStrictness strictness, MapsVariant & maps, bool prefer_use_maps_all, Func && func)
{
    return static_for<0, KINDS.size() * STRICTNESSES.size()>([&](auto ij)
    {
        // NOTE: Avoid using nested static loop as GCC and CLANG have bugs in different ways
        // See https://stackoverflow.com/questions/44386415/gcc-and-clang-disagree-about-c17-constexpr-lambda-captures
        constexpr auto i = ij / STRICTNESSES.size();
        constexpr auto j = ij % STRICTNESSES.size();
        if constexpr (!is_niche_hash_join_combo_v<KINDS[i], STRICTNESSES[j]>)
        {
            if (kind == KINDS[i] && strictness == STRICTNESSES[j])
            {
                if (prefer_use_maps_all)
                    func(
                        std::integral_constant<JoinKind, KINDS[i]>(),
                        std::integral_constant<JoinStrictness, STRICTNESSES[j]>(),
                        std::get<typename MapGetter<KINDS[i], STRICTNESSES[j], true>::Map>(maps));
                else
                    func(
                        std::integral_constant<JoinKind, KINDS[i]>(),
                        std::integral_constant<JoinStrictness, STRICTNESSES[j]>(),
                        std::get<typename MapGetter<KINDS[i], STRICTNESSES[j], false>::Map>(maps));
                return true;
            }
        }
        return false;
    });
}

/// Call function on specified join map
template <typename MapsVariant, typename Func>
inline bool joinDispatch(JoinKind kind, JoinStrictness strictness, std::vector<const MapsVariant *> & mapsv, bool prefer_use_maps_all, Func && func)
{
    return static_for<0, KINDS.size() * STRICTNESSES.size()>([&](auto ij)
    {
        // NOTE: Avoid using nested static loop as GCC and CLANG have bugs in different ways
        // See https://stackoverflow.com/questions/44386415/gcc-and-clang-disagree-about-c17-constexpr-lambda-captures
        constexpr auto i = ij / STRICTNESSES.size();
        constexpr auto j = ij % STRICTNESSES.size();
        if constexpr (!is_niche_hash_join_combo_v<KINDS[i], STRICTNESSES[j]>)
        {
            if (kind == KINDS[i] && strictness == STRICTNESSES[j])
            {
                if (prefer_use_maps_all)
                {
                    using MapType = typename MapGetter<KINDS[i], STRICTNESSES[j], true>::Map;
                    std::vector<const MapType *> v;
                    v.reserve(mapsv.size());
                    for (const auto & el : mapsv)
                        v.push_back(&std::get<MapType>(*el));

                    func(
                        std::integral_constant<JoinKind, KINDS[i]>(), std::integral_constant<JoinStrictness, STRICTNESSES[j]>(), v
                        /*std::get<typename MapGetter<KINDS[i], STRICTNESSES[j]>::Map>(maps)*/);
                }
                else
                {
                    using MapType = typename MapGetter<KINDS[i], STRICTNESSES[j], false>::Map;
                    std::vector<const MapType *> v;
                    v.reserve(mapsv.size());
                    for (const auto & el : mapsv)
                        v.push_back(&std::get<MapType>(*el));

                    func(
                        std::integral_constant<JoinKind, KINDS[i]>(), std::integral_constant<JoinStrictness, STRICTNESSES[j]>(), v
                        /*std::get<typename MapGetter<KINDS[i], STRICTNESSES[j]>::Map>(maps)*/);

                }
                return true;
            }
        }
        return false;
    });
}


}
