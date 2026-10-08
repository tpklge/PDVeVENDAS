#pragma once
#include <cstdint>
#include "esp_err.h"
#include "lvgl.h"

namespace tab5 {
struct KeyboardEvent { std::uint32_t key; bool pressed; bool previous; };
struct PlatformStatus {
    bool keyboard = false;
    std::uint8_t keyboard_version = 0;
    bool sd_mounted = false;
    bool sd_writable = false;
    esp_err_t sd_error = ESP_OK;
    std::uint32_t touch_events = 0;
};
esp_err_t keyboard_start(PlatformStatus& status);
void keyboard_read(lv_indev_t* input, lv_indev_data_t* data);
esp_err_t storage_start(PlatformStatus& status);
void create_platform_ui(PlatformStatus& status, lv_display_t* display);
}
