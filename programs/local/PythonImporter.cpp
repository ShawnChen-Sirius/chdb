#include "PythonImporter.h"
#include "PythonImportCacheItem.h"

namespace CHDB {

PythonImportCachePtr PythonImporter::python_import_cache = nullptr;

py::handle PythonImporter::Import(std::stack<PythonImportCacheItem *> & hierarchy, bool load) {
	auto & import_cache = ImportCache();
	py::handle source(nullptr);

	while (!hierarchy.empty()) {
		// From top to bottom, import them
		auto * item = hierarchy.top();
		hierarchy.pop();
		source = item->Load(import_cache, source, load);
		if (!source)
		{
			// If load is false, or the module load fails and is not required, we return early
			break;
		}
	}

	return source;
}

PythonImportCache & PythonImporter::ImportCache()
{
#ifdef CHDB_FREE_THREADING
	// ImportCache() sits on the per-row scan path (PandasScan -> isNone() ->
	// ImportCache()). A process-global mutex here would serialize every scan
	// thread once per row on FT, defeating the whole point of the FT build.
	// std::call_once gives us a one-shot first-init synchronization point and a
	// lock-free fast path thereafter. The initializer is pure C++ allocation —
	// no Python calls — so it cannot release any lock or recurse, sidestepping
	// the call_once + GIL deadlock concern that applies to module imports.
	static std::once_flag init_flag;
	std::call_once(init_flag, []() {
		python_import_cache = std::make_shared<PythonImportCache>();
	});
#else
	// Stock builds: GIL already serializes all callers, so the unguarded
	// null-check + assignment is safe.
	if (!python_import_cache)
		python_import_cache = std::make_shared<PythonImportCache>();
#endif
	return *python_import_cache;
}

void PythonImporter::destroy()
{
	// destroy() runs only at interpreter shutdown (via the _destroy_import_cache
	// capsule in LocalChdb.cpp), after all worker threads have joined, so no
	// reader can race with this reset. On FT, the once_flag remains "completed"
	// after this reset — re-init from the same process would be a no-op, which
	// is fine because destroy() is the shutdown path, not a re-init hook.
	python_import_cache.reset();
}

} // namespace CHDB
