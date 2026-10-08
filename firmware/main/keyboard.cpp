#include "platform.hpp"
#include "hid.hpp"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

namespace tab5 {
namespace {
constexpr auto TAG = "keyboard";
constexpr std::uint8_t address = 0x6d;
constexpr std::uint8_t mode_register = 0x10;
constexpr std::uint8_t count_register = 0x02;
constexpr std::uint8_t hid_register = 0x30;
i2c_master_bus_handle_t bus = nullptr;
i2c_master_dev_handle_t device = nullptr;
QueueHandle_t events = nullptr;
TaskHandle_t worker = nullptr;
std::uint32_t last_key = 0;

esp_err_t read_register(std::uint8_t reg, std::uint8_t* out, std::size_t size) {
    return i2c_master_transmit_receive(device, &reg, 1, out, size, 30);
}
esp_err_t write_register(std::uint8_t reg, std::uint8_t value) {
    const std::uint8_t bytes[] = {reg, value};
    return i2c_master_transmit(device, bytes, sizeof(bytes), 30);
}
std::uint32_t key_for(std::uint8_t usage, std::uint8_t modifier) {
    switch (usage) {
    case 0x28: return LV_KEY_ENTER;
    case 0x29: return LV_KEY_ESC;
    case 0x2a: return LV_KEY_BACKSPACE;
    case 0x2b: return modifier & 0x22 ? LV_KEY_PREV : LV_KEY_NEXT;
    case 0x4c: return LV_KEY_DEL;
    case 0x4f: return LV_KEY_RIGHT;
    case 0x50: return LV_KEY_LEFT;
    case 0x51: return LV_KEY_DOWN;
    case 0x52: return LV_KEY_UP;
    default: return hid_character(usage, modifier);
    }
}
void IRAM_ATTR interrupt(void*) {
    BaseType_t awakened = pdFALSE;
    vTaskNotifyGiveFromISR(worker, &awakened);
    if (awakened) portYIELD_FROM_ISR();
}
void poll(void*) {
    std::uint32_t held = 0;
    for (;;) {
        // Interrupt-driven wakeup with bounded polling fallback for missed edges.
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(20));
        std::uint8_t count = 0;
        if (read_register(count_register, &count, 1) != ESP_OK) continue;
        if (count > 32) { ESP_LOGW(TAG, "Fila inválida"); continue; }
        for (unsigned i = 0; i < count; ++i) {
            std::uint8_t frame[2]{};
            if (read_register(hid_register, frame, 2) != ESP_OK) break;
            if (frame[0] == 0xff && frame[1] == 0xff) break;
            const auto key = frame[1] ? key_for(frame[1], frame[0]) : held;
            if (!key) continue;
            held = key;
            KeyboardEvent event{key, frame[1] != 0, key == LV_KEY_PREV};
            if (xQueueSend(events, &event, pdMS_TO_TICKS(10)) != pdTRUE)
                ESP_LOGW(TAG, "Entrada excedeu a fila; repita a tecla");
        }
        if (write_register(0x01, 0) != ESP_OK) ESP_LOGW(TAG, "Falha ao liberar interrupção");
    }
}
}

esp_err_t keyboard_start(PlatformStatus& status) {
    i2c_master_bus_config_t config{};
    config.i2c_port = I2C_NUM_0;
    config.sda_io_num = GPIO_NUM_0;
    config.scl_io_num = GPIO_NUM_1;
    config.clk_source = I2C_CLK_SRC_DEFAULT;
    config.glitch_ignore_cnt = 7;
    config.flags.enable_internal_pullup = true;
    auto result = i2c_new_master_bus(&config, &bus);
    if (result != ESP_OK) return result;
    if (i2c_master_probe(bus, address, 100) != ESP_OK) return ESP_ERR_NOT_FOUND;
    i2c_device_config_t keyboard{};
    keyboard.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    keyboard.device_address = address;
    keyboard.scl_speed_hz = 400000;
    result = i2c_master_bus_add_device(bus, &keyboard, &device);
    if (result != ESP_OK) return result;
    result = read_register(0xfe, &status.keyboard_version, 1);
    if (result != ESP_OK) return result;
    // HID preserves navigation keys and modifiers; Character mode is not used here.
    if ((result = write_register(mode_register, 1)) != ESP_OK) return result;
    if ((result = write_register(count_register, 0)) != ESP_OK) return result;
    if ((result = write_register(0x00, 0x02)) != ESP_OK) return result;
    events = xQueueCreate(64, sizeof(KeyboardEvent));
    if (!events) return ESP_ERR_NO_MEM;
    gpio_config_t irq{};
    irq.pin_bit_mask = 1ULL << GPIO_NUM_50;
    irq.mode = GPIO_MODE_INPUT;
    irq.pull_up_en = GPIO_PULLUP_ENABLE;
    irq.intr_type = GPIO_INTR_NEGEDGE;
    if ((result = gpio_config(&irq)) != ESP_OK) return result;
    result = gpio_install_isr_service(0);
    if (result != ESP_OK && result != ESP_ERR_INVALID_STATE) return result;
    if (xTaskCreate(poll, "tab5_keyboard", 4096, nullptr, 4, &worker) != pdPASS) return ESP_ERR_NO_MEM;
    if ((result = gpio_isr_handler_add(GPIO_NUM_50, interrupt, nullptr)) != ESP_OK) {
        vTaskDelete(worker);
        worker = nullptr;
        return result;
    }
    status.keyboard = true;
    return ESP_OK;
}

void keyboard_read(lv_indev_t*, lv_indev_data_t* data) {
    KeyboardEvent event{};
    data->state = LV_INDEV_STATE_RELEASED;
    if (events && xQueueReceive(events, &event, 0) == pdTRUE) {
        last_key = event.key;
        data->state = event.pressed ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
        data->continue_reading = uxQueueMessagesWaiting(events) != 0;
    }
    data->key = last_key;
}
}
