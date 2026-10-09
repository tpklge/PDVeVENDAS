#pragma once
#include "products.hpp"
namespace tab5 {
// Worker-only encrypted journal: 0 missing, 1 success, negative error/scope mismatch.
using SaleJournal = int (*)(const char* operation,int user,char* request,size_t capacity);
void sales_create(lv_display_t* display,void (*home)());
void sales_open(const char* permissions,bool light);
void sales_hide(bool clear=false);
bool sales_handle_next(const char* permissions,bool online,ProductTransport transport,SaleJournal journal);
}
