#pragma once
#include <cstddef>
namespace tab5 {
bool protected_record_exists(const char* path);
// Same v1 envelope used since 0.7; never roll back an existing damaged request.
int protected_request(const char* operation,int user,char* request,size_t capacity,
                      const unsigned char* key,const char* api,const char* device,
                      const char* path,const char* aad);
}
