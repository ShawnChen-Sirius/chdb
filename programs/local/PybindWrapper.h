#pragma once

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

namespace pybind11
{

bool gil_check();
void gil_assert();

}

namespace CHDB
{

namespace py
{

using namespace pybind11;

template <class T>
bool try_cast(const handle & object, T & result)
{
	try
    {
		result = cast<T>(object);
	}
    catch (pybind11::cast_error &)
    {
		return false;
	}
	return true;
}

} // namespace py

struct PythonGILWrapper
{
    py::gil_scoped_acquire acquire;
};

} // namespace CHDB
