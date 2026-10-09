#pragma once
#include "sales.hpp"
namespace tab5 {
void inventory_create(lv_display_t* display,void(*home)());
void inventory_open(const char* permissions,bool light);
void inventory_hide();
bool inventory_handle_next(const char* permissions,bool online,ProductTransport transport,SaleJournal journal);
}
