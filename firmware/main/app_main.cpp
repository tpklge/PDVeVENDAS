#include "platform.hpp"
#include "auth.hpp"
#include "bsp/esp-bsp.h"
#include "esp_chip_info.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_heap_caps.h"

extern "C" void app_main() {
    static tab5::PlatformStatus status;
    esp_chip_info_t chip{};
    esp_chip_info(&chip);
    ESP_LOGI("tab5_erp", "TAB5 ERP v0.6.0 | ESP-IDF %s | núcleos %d", esp_get_idf_version(), chip.cores);
    bsp_display_cfg_t display_config{};
    display_config.lvgl_port_cfg=ESP_LVGL_PORT_INIT_CONFIG();
    display_config.lvgl_port_cfg.task_stack=16384;
    display_config.buffer_size=BSP_LCD_H_RES*CONFIG_BSP_LCD_DRAW_BUF_HEIGHT;
    display_config.double_buffer=CONFIG_BSP_LCD_DRAW_BUF_DOUBLE;
    // ESP32-P4 supports DMA in PSRAM. Keep drawing/rotation buffers there
    // so SDIO and TLS retain enough internal RAM after Wi-Fi connects.
    static_assert(SOC_PSRAM_DMA_CAPABLE, "Display buffers require PSRAM DMA support");
    display_config.flags.buff_dma=true;display_config.flags.buff_spiram=true;display_config.flags.sw_rotate=true;
    lv_display_t* display = bsp_display_start_with_config(&display_config);
    if (!display) { ESP_LOGE("tab5_erp", "Falha ao inicializar display"); return; }
    bsp_display_rotate(display, LV_DISPLAY_ROTATION_90);
    ESP_ERROR_CHECK(bsp_display_backlight_on());
    const auto keyboard = tab5::keyboard_start(status);
    if (keyboard != ESP_OK) ESP_LOGW("tab5_erp", "Teclado indisponível: %s", esp_err_to_name(keyboard));
    const auto sd = tab5::storage_start(status);
    if (sd != ESP_OK) ESP_LOGW("tab5_erp", "microSD indisponível: %s", esp_err_to_name(sd));
    if (bsp_display_lock(5000)) {
        // Product forms exceed LVGL's default 64 KiB pool. Keep the extra
        // UI storage in PSRAM, preserving internal RAM for DMA and Wi-Fi.
        constexpr size_t ui_pool_bytes = 512 * 1024;
        static_assert(LV_MEM_SIZE + LV_MEM_POOL_EXPAND_SIZE >= ui_pool_bytes,
                      "LVGL TLSF must support the PSRAM UI pool size");
        void* ui_pool = heap_caps_malloc(ui_pool_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (!ui_pool || !lv_mem_add_pool(ui_pool, ui_pool_bytes)) {
            heap_caps_free(ui_pool);
            bsp_display_unlock();
            ESP_LOGE("tab5_erp", "Falha ao reservar memória PSRAM para a interface");
            return;
        }
        ESP_LOGI("tab5_erp", "LVGL: pool adicional de %u KiB na PSRAM", unsigned(ui_pool_bytes / 1024));
        tab5::create_platform_ui(status, display);
        tab5::authentication_start(display,status.sd_mounted && status.sd_writable);
        lv_mem_monitor_t ui_memory{};
        lv_mem_monitor(&ui_memory);
        ESP_LOGI("tab5_erp", "LVGL: %u bytes livres após criar a interface", unsigned(ui_memory.free_size));
        ESP_LOGI("tab5_erp", "DMA interna: livres %u bytes, maior bloco %u bytes",
                 unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA)),
                 unsigned(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA)));
        bsp_display_unlock();
    } else {
        ESP_LOGE("tab5_erp", "Não foi possível criar a interface");
    }
}
