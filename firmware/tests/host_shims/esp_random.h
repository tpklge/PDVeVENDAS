#pragma once
#include <cstdio>
#include <cstdlib>
inline void esp_fill_random(void* data,size_t size){FILE* file=std::fopen("/dev/urandom","rb");if(!file||std::fread(data,1,size,file)!=size)std::abort();std::fclose(file);}
