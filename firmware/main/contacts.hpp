#pragma once
#include "products.hpp"
namespace tab5 {
void contacts_create(lv_display_t* display, void (*home)());
void contacts_open(const char* permissions, bool light, bool supplier);
void contacts_hide();
bool contacts_handle_next(const char* permissions, bool online, ProductTransport transport);
}
