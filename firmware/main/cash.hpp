#pragma once
#include "sales.hpp"
namespace tab5 {
void cash_create(lv_display_t* display,void(*home)());
void cash_open(const char* permissions,bool light);
void cash_hide();
bool cash_handle_next(const char* permissions,bool online,ProductTransport transport,SaleJournal journal);
}
