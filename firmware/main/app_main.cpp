#include "platform.hpp"
#include "auth.hpp"
#include "bsp/esp-bsp.h"
#include "esp_chip_info.h"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"

extern "C" void app_main() {
    static tab5::PlatformStatus status;
    esp_chip_info_t chip{};
    esp_chip_info(&chip);
    ESP_LOGI("tab5_erp", "TAB5 ERP v0.3.0 | ESP-IDF %s | núcleos %d", esp_get_idf_version(), chip.cores);
    // Do not erase NVS automatically: future credentials/configuration must survive errors.
    ESP_ERROR_CHECK(nvs_flash_init());
    lv_display_t* display = bsp_display_start();
    if (!display) { ESP_LOGE("tab5_erp", "Falha ao inicializar display"); return; }
    bsp_display_rotate(display, LV_DISPLAY_ROTATION_90);
    ESP_ERROR_CHECK(bsp_display_backlight_on());
    const auto keyboard = tab5::keyboard_start(status);
    if (keyboard != ESP_OK) ESP_LOGW("tab5_erp", "Teclado indisponível: %s", esp_err_to_name(keyboard));
    const auto sd = tab5::storage_start(status);
    if (sd != ESP_OK) ESP_LOGW("tab5_erp", "microSD indisponível: %s", esp_err_to_name(sd));
    if (bsp_display_lock(5000)) {
        tab5::create_platform_ui(status, display);
        tab5::authentication_start(display);
        bsp_display_unlock();
    } else {
        ESP_LOGE("tab5_erp", "Não foi possível criar a interface");
    }
}
