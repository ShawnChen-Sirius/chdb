/*
 * je_vsallocx: like je_sallocx but returns 0 for pointers not owned by jemalloc.
 *
 * Lives here (outside contrib/jemalloc/) so that we do not have to patch the
 * pristine jemalloc submodule.  It is compiled into the _jemalloc target
 * alongside the upstream jemalloc sources and sees the same internal headers,
 * so it can call ivsalloc() which uses the rtree with dependent=false.
 *
 * Use case: chdb's malloc.cpp intercepts free().  glibc internals such as
 * realpath() and getcwd() allocate via __libc_malloc@GLIBC_PRIVATE (a
 * versioned symbol that bypasses ELF symbol interposition), returning
 * pointers that jemalloc does not own.  If free() then calls je_sallocx() or
 * je_free() on those pointers, jemalloc's rtree lookup (dependent=true)
 * crashes.  je_vsallocx() lets the wrapper detect foreign pointers safely
 * and route them to the real glibc free().
 */

#include "jemalloc/internal/jemalloc_preamble.h"
#include "jemalloc/internal/jemalloc_internal_includes.h"

JEMALLOC_EXPORT size_t JEMALLOC_NOTHROW
JEMALLOC_ATTR(pure)
je_vsallocx(const void *ptr, int flags) {
	(void)flags;

	if (unlikely(ptr == NULL) || unlikely(!malloc_initialized())) {
		return 0;
	}

	/* check_entry_exit_locking() is a static helper inside jemalloc.c used
	 * only when config_debug is true; omitted here (release builds) so we
	 * do not need to include that private symbol. */
	tsdn_t *tsdn = tsdn_fetch();
	return ivsalloc(tsdn, ptr);
}
