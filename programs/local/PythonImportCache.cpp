#include "PythonImportCache.h"
#include "PythonImporter.h"

#include <Common/Exception.h>
#include <stack>

#if USE_JEMALLOC
#    include <Common/memory.h>
#endif

namespace DB
{

namespace ErrorCodes
{
    extern const int LOGICAL_ERROR;
}

}

namespace CHDB {

py::handle PythonImportCacheItem::operator()(bool load) {
#ifndef CHDB_FREE_THREADING
	// On stock (GIL-bearing) builds the GIL serializes this read against the
	// call_once initializer's write to `object`, so the unsynchronized
	// pre-check is a safe fast path that avoids rebuilding the hierarchy
	// stack and re-entering PythonImporter::Import on every steady-state
	// attribute access.
	if (IsLoaded())
		return object;
#endif
	// Free-threaded: no unsynchronized pre-check on `object`. Reading `object`
	// concurrently with the call_once initializer's write is a C++ data race.
	// std::call_once already provides the necessary happens-before — every
	// passive call_once on the same flag synchronizes with the completion of
	// the initializer, so the post-call_once read of `object` is well-defined.
	std::stack<PythonImportCacheItem *> hierarchy;

	PythonImportCacheItem * item = this;
	while (item)
	{
		hierarchy.emplace(item);
		item = item->parent;
	}

	return PythonImporter::Import(hierarchy, load);
}

bool PythonImportCacheItem::LoadSucceeded() const
{
	return load_succeeded;
}

bool PythonImportCacheItem::IsLoaded() const
{
	return object.ptr() != nullptr;
}

py::handle PythonImportCacheItem::AddCache(PythonImportCache & cache, py::object object)
{
	return cache.AddCache(std::move(object));
}

void PythonImportCacheItem::LoadModule(PythonImportCache & cache)
{
#if USE_JEMALLOC
	::Memory::MemoryCheckScope memory_check_scope;
#endif
	try
	{
		py::gil_assert();
		object = AddCache(cache, std::move(py::module::import(name.c_str())));
		load_succeeded = true;
	}
	catch (py::error_already_set &e)
	{
		if (IsRequired())
		{
#if USE_JEMALLOC
			::Memory::MemoryCheckScope memory_check_scope;
#endif
			throw DB::Exception(DB::ErrorCodes::LOGICAL_ERROR,
			    				"Required module {} failed to import, due to the following Python exception:\n {}", name, e.what());
		}
		object = nullptr;
		return;
	}
}

void PythonImportCacheItem::LoadAttribute(PythonImportCache & cache, py::handle source)
{
#if USE_JEMALLOC
	::Memory::MemoryCheckScope memory_check_scope;
#endif
	if (py::hasattr(source, name.c_str()))
		object = AddCache(cache, std::move(source.attr(name.c_str())));
	else
		object = nullptr;
}

py::handle PythonImportCacheItem::Load(PythonImportCache & cache, py::handle source, bool load)
{
#ifndef CHDB_FREE_THREADING
	// Stock (GIL-bearing) builds: the GIL already serializes all callers, so a
	// direct call is correct and avoids a std::call_once + GIL deadlock window.
	// LoadModule() invokes py::module::import(), and CPython's import machinery
	// may release the GIL internally (per-module import lock, file I/O,
	// arbitrary module top-level code). If one thread were stuck inside
	// std::call_once while another acquired the GIL and reached the same
	// call_once, the second thread would block in call_once *while holding the
	// GIL*, leaving no thread able to re-acquire the GIL and finish the
	// initializer. Calling LoadModule()/LoadAttribute() directly under the GIL
	// avoids that window entirely.
	if (IsLoaded())
		return object;
	if (!load)
		return object;
	if (is_module)
		LoadModule(cache);
	else
		LoadAttribute(cache, source);
	return object;
#else
	// Free-threaded: no GIL to serialize callers, so use std::call_once. The
	// initializer's write to `object` happens-before every passive call_once on
	// the same flag, so the post-call_once read below is well-defined.
	if (!load)
		return object;

	std::call_once(load_flag, [&]() {
		if (is_module)
			LoadModule(cache);
		else
			LoadAttribute(cache, source);
	});

	return object;
#endif
}

PythonImportCache::~PythonImportCache()
{
	try
	{
		py::gil_scoped_acquire acquire;
#if USE_JEMALLOC
		::Memory::MemoryCheckScope memory_check_scope;
#endif
		owned_objects.clear();
	}
	catch (...)
	{
	}
}

py::handle PythonImportCache::AddCache(py::object item)
{
	auto object_ptr = item.ptr();
	std::lock_guard<std::mutex> lock(cache_mutex);
	owned_objects.push_back(std::move(item));
	return object_ptr;
}

} // namespace CHDB
