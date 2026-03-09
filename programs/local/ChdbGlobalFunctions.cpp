#include "ChdbGlobalFunctions.h"
#include "ChdbPyType.h"
#include "PythonUDFRegistry.h"

#include <Common/Exception.h>


namespace CHDB
{

namespace
{

std::shared_ptr<ChdbPyType> toChdbPyType(const py::object & obj)
{
    if (py::isinstance<ChdbPyType>(obj))
        return obj.cast<std::shared_ptr<ChdbPyType>>();
    if (py::isinstance<py::str>(obj))
        return std::make_shared<ChdbPyType>(obj.cast<std::string>());
    throw std::runtime_error("return_type must be a ChdbType or a string, got " + std::string(py::str(obj.get_type())));
}

void createFunction(
    const std::string & name,
    const py::function & func,
    const py::object & arg_types,
    const py::object & return_type)
{
    try
    {
        DB::DataTypePtr data_type = nullptr;
        if (!return_type.is_none())
            data_type = toChdbPyType(return_type)->dataType();

        py::list arg_types_list;
        if (!arg_types.is_none())
        {
            if (!py::isinstance<py::list>(arg_types))
                throw std::runtime_error("arg_types must be a list, got " + std::string(py::str(arg_types.get_type())));
            arg_types_list = arg_types.cast<py::list>();
        }

        registerPythonUDF(name, func, std::move(data_type), arg_types_list);
    }
    catch (const DB::Exception & e)
    {
        throw std::runtime_error("Failed to create function '" + name + "': " + e.message());
    }
}

void dropFunction(const std::string & name)
{
    try
    {
        removePythonUDF(name);
    }
    catch (const DB::Exception & e)
    {
        throw std::runtime_error("Failed to drop function '" + name + "': " + e.message());
    }
}

} // anonymous namespace


void registerGlobalFunctions(py::module_ & m)
{
    m.def(
        "create_function",
        &createFunction,
        py::arg("name"),
        py::arg("func"),
        py::arg("arg_types") = py::none(),
        py::arg("return_type") = py::none(),
        "Register a Python scalar UDF globally.\n\n"
        "Args:\n"
        "    name (str): Function name to use in SQL queries.\n"
        "    func (callable): Python function to call for each row.\n"
        "    arg_types: List of argument types (ChdbType, str, or Python type).\n"
        "              Optional; if omitted, inferred from parameter annotations.\n"
        "              If provided, must specify types for ALL parameters.\n"
        "    return_type: Return type (ChdbType or str). Optional; if omitted,\n"
        "                 inferred from the function's return type annotation.\n"
        "Example:\n"
        "    import chdb\n"
        "    from chdb.sqltypes import INT64\n"
        "    chdb.create_function('add_int', lambda a, b: a + b, [INT64, INT64], INT64)\n"
        "    # Or with annotation:\n"
        "    def add_int(a: int, b: int) -> int: return a + b\n"
        "    chdb.create_function('add_int', add_int)");

    m.def(
        "drop_function",
        &dropFunction,
        py::arg("name"),
        "Remove a previously registered Python scalar UDF.\n\n"
        "Args:\n"
        "    name (str): Name of the function to remove.\n"
        "Raises:\n"
        "    RuntimeError: If the function is not registered.\n"
        "Example:\n"
        "    chdb.drop_function('add_int')");
}

} // namespace CHDB
