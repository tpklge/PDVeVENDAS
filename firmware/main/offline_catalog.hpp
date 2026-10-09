#pragma once
#include <cstdio>
#include <string>
#include "mbedtls/sha256.h"
namespace tab5 {
struct CatalogHeader {unsigned revision=0;long long time=0;char epoch[37]{},nonce[33]{};};
class CatalogFile {
    FILE* file=nullptr;char* plain=nullptr;char* encoded=nullptr;unsigned count=0;bool ended=false,writing=false;
    mbedtls_sha256_context hash;
    bool line(const char* input,unsigned index);
public:
    CatalogHeader header;
    CatalogFile();~CatalogFile();
    bool read(const std::string& path);
    bool write(const std::string& path,const CatalogHeader& metadata);
    int next(char* output,size_t capacity); // 1 row, 0 verified footer, -1 invalid
    bool append(const char* row);
    bool finish();
    bool valid();
};
bool catalog_path_valid(const std::string& path);
}
