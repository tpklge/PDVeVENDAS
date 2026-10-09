#pragma once
#include <cstdlib>
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
inline int tab5_alloc_fail_after=-1;
inline int tab5_alloc_live=0;
inline bool tab5_alloc_allowed(){if(tab5_alloc_fail_after==0)return false;if(tab5_alloc_fail_after>0)--tab5_alloc_fail_after;return true;}
inline void* heap_caps_malloc(size_t size,unsigned){if(!tab5_alloc_allowed())return nullptr;auto* p=std::malloc(size);if(p)++tab5_alloc_live;return p;}
inline void* heap_caps_calloc(size_t count,size_t size,unsigned){if(!tab5_alloc_allowed())return nullptr;auto* p=std::calloc(count,size);if(p)++tab5_alloc_live;return p;}
inline void heap_caps_free(void* pointer){if(pointer)--tab5_alloc_live;std::free(pointer);}
