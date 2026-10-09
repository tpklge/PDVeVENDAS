#pragma once
#include <cstddef>
#include <string>
namespace tab5 {
// Worker only. No tokens or ERP passwords are persisted.
void offline_configure(const unsigned char* key,const char* api,const char* device);
void offline_lock();
std::string offline_scope();
bool offline_seal(const char* context,const char* plain,char* output,size_t capacity);
bool offline_open(const char* context,const char* sealed,char* output,size_t capacity);
// 0 missing, 1 success, negative error. Caller must not silently overwrite an error.
int offline_blob(const char* operation,const char* name,int user,char* data,size_t capacity);
bool offline_draft_exists();
int offline_draft_pending(int user,char* request,size_t capacity);
int offline_draft_link(int user,const char* request);
int offline_draft_settle(int user,const char* request,bool abandoned);
int offline_user();
void offline_set_user(int user);
}
