#include "platform.hpp"
#include "bsp/esp-bsp.h"
#include "esp_log.h"
#include <cerrno>
#include <initializer_list>
#include <cstdio>
#include <sys/stat.h>
#include <unistd.h>

namespace tab5 {
esp_err_t storage_start(PlatformStatus& status) {
    status.sd_error = bsp_sdcard_mount();
    if (status.sd_error != ESP_OK) return status.sd_error;
    status.sd_mounted = true;
    for (const char* path : {"/sdcard/ERP", "/sdcard/ERP/logs", "/sdcard/ERP/config"}) {
        if (mkdir(path, 0755) != 0 && errno != EEXIST) return status.sd_error = ESP_FAIL;
    }
    const char* probe = "/sdcard/ERP/.platform-write-test.tmp";
    auto file = fopen(probe, "w");
    if (!file) return status.sd_error = ESP_FAIL;
    bool ok = fputs("TAB5 ERP: teste de escrita", file) >= 0;
    ok = fflush(file) == 0 && ok;
    ok = fsync(fileno(file)) == 0 && ok;
    ok = fclose(file) == 0 && ok;
    unlink(probe);
    status.sd_writable = ok;
    if (!ok) return status.sd_error = ESP_FAIL;
    struct stat info{};
    const char* path = "/sdcard/ERP/logs/platform.log";
    if (stat(path, &info) == 0 && info.st_size > 65536) {
        unlink("/sdcard/ERP/logs/platform.log.1");
        if (rename(path, "/sdcard/ERP/logs/platform.log.1") != 0) return status.sd_error = ESP_FAIL;
    }
    file = fopen(path, "a");
    if (!file) return status.sd_error = ESP_FAIL;
    ok = fputs("v0.7.0: plataforma iniciou; microSD gravável\n", file) >= 0;
    ok = fflush(file) == 0 && ok;
    ok = fsync(fileno(file)) == 0 && ok;
    ok = fclose(file) == 0 && ok;
    if (!ok) return status.sd_error = ESP_FAIL;
    ESP_LOGI("storage", "microSD montado e escrita verificada");
    return ESP_OK;
}
}
