#include "PyDateTimeHelper.h"

#include <stdexcept>

namespace CHDB
{

namespace
{

PyObject * attr_toordinal = nullptr;

/// date(1970, 1, 1).toordinal()
constexpr int32_t EPOCH_ORDINAL = 719163;

} // anonymous namespace

void PyDateTimeHelper::initialize()
{
    attr_toordinal = PyUnicode_InternFromString("toordinal");
}

int32_t PyDateTimeHelper::daysSinceEpoch(const py::handle & obj)
{
    if (!attr_toordinal)
        throw std::runtime_error("PyDateTimeHelper::initialize() has not been called");

    PyObject * result = PyObject_CallMethodObjArgs(obj.ptr(), attr_toordinal, nullptr);
    if (!result)
        throw py::error_already_set();

    int64_t ordinal = static_cast<int64_t>(PyLong_AsLong(result));
    Py_DECREF(result);

    if (ordinal == -1 && PyErr_Occurred())
        throw py::error_already_set();

    return static_cast<int32_t>(ordinal) - EPOCH_ORDINAL;
}

} // namespace CHDB
