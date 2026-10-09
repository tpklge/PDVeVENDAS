#pragma once
#include "lvgl.h"
#include <cstddef>
namespace tab5 {
using ProductTransport = int (*)(const char* method,const char* path,const char* body,char* output,size_t capacity);
bool offline_product_get(int id,char* output,size_t capacity);
bool offline_product_search(const char* query,unsigned after,char* output,size_t capacity);
void products_create(lv_display_t* display,void (*home)());
void products_open(const char* permissions,bool light);
void products_hide();
void products_render();
bool products_handle_next(const char* permissions,const char* api,bool online,ProductTransport transport);
}
