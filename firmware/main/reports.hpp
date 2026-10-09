#pragma once
#include "products.hpp"
namespace tab5 {
void reports_create(lv_display_t* display,void(*home)());
void reports_open(const char* permissions,bool light);
void reports_hide();
bool reports_handle_next(const char* permissions,bool online,ProductTransport transport);
}
