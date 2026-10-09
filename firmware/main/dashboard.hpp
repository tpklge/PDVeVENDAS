#pragma once
#include "lvgl.h"
namespace tab5 {
enum class DashboardAction { Network, Password, Logout, Lock, Theme, Products, Customers, Sales, Inventory };
using DashboardCallback = void (*)(DashboardAction);
void dashboard_create(lv_display_t* display, DashboardCallback callback);
void dashboard_show(const char* identity, const char* permissions, bool light,const char* notice);
void dashboard_hide();
void dashboard_status(bool wifi, bool api, bool busy, bool light);
}
