#pragma once

#include "PythonImportCache.h"
#include "PythonImportCacheItem.h"

#include <stack>

namespace CHDB {

struct PythonImporter {
public:
	static py::handle Import(std::stack<PythonImportCacheItem *> & hierarchy, bool load = true);

	// Returns a reference to the process-wide PythonImportCache singleton.
	// destroy() runs only at interpreter shutdown after all worker threads have
	// joined, so the reference remains valid for the duration of every caller's
	// use. On free-threaded builds, first-init is synchronized via std::call_once
	// inside ImportCache() and the steady-state read is lock-free; on stock
	// (GIL-bearing) builds, the GIL already provides that mutual exclusion.
	static PythonImportCache & ImportCache();

	static void destroy();

private:
	static PythonImportCachePtr python_import_cache;
};

} // namespace CHDB
