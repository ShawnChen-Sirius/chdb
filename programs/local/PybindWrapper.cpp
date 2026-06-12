#include "PybindWrapper.h"

#ifndef CHDB_FREE_THREADING
#include <pybind11/detail/non_limited_api.h>
#endif

#include <Common/Exception.h>

using namespace DB;

namespace DB
{

namespace ErrorCodes
{
    extern const int LOGICAL_ERROR;
}

}

namespace pybind11
{

bool gil_check()
{
#ifdef CHDB_FREE_THREADING
    // Free-threading builds don't go through the limited-API trampoline, so
    // call the CPython symbol directly. Returning true unconditionally would
    // turn every chassert(py::gil_check()) / py::gil_assert() into a no-op
    // and mask missing thread-state setup. PyGILState_Check returns 0 when
    // the current OS thread has no Python thread state attached — exactly
    // the invariant callers want, with or without a GIL.
    return static_cast<bool>(::PyGILState_Check());
#else
    return static_cast<bool>(pybind11::non_limited_api::PyGILState_Check());
#endif
}

void gil_assert()
{
    if (!gil_check())
        throw Exception(ErrorCodes::LOGICAL_ERROR,
                        "The GIL should be held for this operation, but it's not!");
}

} // namespace pybind11
