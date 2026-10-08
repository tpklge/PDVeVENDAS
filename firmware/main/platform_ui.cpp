#include "platform.hpp"
#include "erp_fonts.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include <cstdio>
#include <cstdint>

namespace tab5 {
namespace {
PlatformStatus* state = nullptr;
lv_obj_t* pages[3]{};
lv_obj_t* diagnostic = nullptr;
lv_obj_t* storage_label = nullptr;
lv_obj_t* input_text = nullptr;
lv_obj_t* virtual_keyboard = nullptr;
lv_obj_t* menu[3]{};
lv_group_t* group = nullptr;

void touch_event(lv_event_t* event) {
    auto input = lv_event_get_indev(event);
    if (input && lv_indev_get_type(input) == LV_INDEV_TYPE_POINTER) ++state->touch_events;
}
void select_page(unsigned index) {
    for (unsigned i = 0; i < 3; ++i) {
        if (i == index) lv_obj_remove_flag(pages[i], LV_OBJ_FLAG_HIDDEN);
        else lv_obj_add_flag(pages[i], LV_OBJ_FLAG_HIDDEN);
    }
    lv_group_remove_all_objs(group);
    for (auto button : menu) lv_group_add_obj(group, button);
    if (index == 1) lv_group_add_obj(group, input_text);
}
void show_page(lv_event_t* event) {
    select_page(static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(lv_event_get_user_data(event))));
    touch_event(event);
}
void navigate(lv_event_t* event) {
    const auto key = lv_event_get_key(event);
    if (key == LV_KEY_ESC) {
        select_page(0);
        lv_group_focus_obj(menu[0]);
        return;
    }
    auto target = lv_event_get_target_obj(event);
    if (target == input_text) return; // Keep cursor movement in text input.
    if (key == LV_KEY_LEFT || key == LV_KEY_UP) lv_group_focus_prev(group);
    if (key == LV_KEY_RIGHT || key == LV_KEY_DOWN) lv_group_focus_next(group);
}
void refresh(lv_timer_t*) {
    char text[512];
    snprintf(text, sizeof(text),
        "ESP32-P4 / M5Stack Tab5\nTela: 1280 x 720, paisagem\n"
        "Teclado: %s (firmware 0x%02x)\n"
        "Toques detectados: %lu\n"
        "microSD: %s | escrita: %s\n"
        "Heap interno livre: %lu bytes\nPSRAM livre: %lu bytes\n"
        "Tempo ligado: %lld segundos\n\n"
        "Use Tab e Shift+Tab para navegar. Enter confirma.\n"
        "Wi-Fi e login estão no menu de acesso. Funções comerciais futuras.",
        state->keyboard ? "detectado" : "não detectado", state->keyboard_version,
        static_cast<unsigned long>(state->touch_events),
        state->sd_mounted ? "montado" : "indisponível", state->sd_writable ? "verificada" : "indisponível",
        static_cast<unsigned long>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)),
        static_cast<unsigned long>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),
        static_cast<long long>(esp_timer_get_time() / 1000000));
    lv_label_set_text(diagnostic, text);
    snprintf(text, sizeof(text), "Armazenamento local\n\nmicroSD: %s\nEscrita: %s\nResultado: %s\n\n"
        "Logs da plataforma: /ERP/logs/platform.log\n"
        "Nenhum cartão é formatado automaticamente.\n"
        "Sem cartão, o menu continua disponível.\n"
        "Cache e fila persistente ainda não estão implementados.",
        state->sd_mounted ? "montado" : "indisponível", state->sd_writable ? "verificada" : "indisponível",
        esp_err_to_name(state->sd_error));
    lv_label_set_text(storage_label, text);
}
}
void create_platform_ui(PlatformStatus& status, lv_display_t* display) {
    state = &status;
    auto theme = lv_theme_default_init(display, lv_palette_main(LV_PALETTE_BLUE),
        lv_palette_main(LV_PALETTE_TEAL), true, &erp_font_pt_20);
    lv_display_set_theme(display, theme);
    auto screen = lv_display_get_screen_active(display);
    lv_obj_set_style_text_font(screen, &erp_font_pt_20, 0);
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x111827), 0);
    lv_obj_set_style_text_color(screen, lv_color_hex(0xf8fafc), 0);
    auto title = lv_label_create(screen);
    lv_label_set_text(title, "TAB5 ERP | Plataforma e diagnóstico");
    lv_obj_set_style_text_font(title, &erp_font_pt_28, 0);
    lv_obj_set_pos(title, 32, 24);
    group = lv_group_create();
    lv_group_set_default(group);
    constexpr const char* names[] = {"Diagnóstico", "Teste de entrada", "Armazenamento"};
    for (unsigned i = 0; i < 3; ++i) {
        menu[i] = lv_button_create(screen);
        lv_obj_set_pos(menu[i], 32 + i * 306, 80);
        lv_obj_set_size(menu[i], 282, 64);
        lv_obj_set_style_bg_color(menu[i], lv_color_hex(0x334155), 0);
        lv_obj_set_style_text_color(menu[i], lv_color_hex(0xf8fafc), 0);
        auto text = lv_label_create(menu[i]);
        lv_label_set_text(text, names[i]);
        lv_obj_center(text);
        lv_obj_add_event_cb(menu[i], show_page, LV_EVENT_CLICKED, reinterpret_cast<void*>(static_cast<std::uintptr_t>(i)));
        lv_obj_add_event_cb(menu[i], navigate, LV_EVENT_KEY, nullptr);
        lv_group_add_obj(group, menu[i]);
        pages[i] = lv_obj_create(screen);
        lv_obj_set_pos(pages[i], 32, 164);
        lv_obj_set_size(pages[i], 1216, 486);
        lv_obj_set_style_bg_color(pages[i], lv_color_hex(0x1f2937), 0);
        lv_obj_set_style_text_color(pages[i], lv_color_hex(0xf8fafc), 0);
        if (i) lv_obj_add_flag(pages[i], LV_OBJ_FLAG_HIDDEN);
    }
    diagnostic = lv_label_create(pages[0]);
    lv_obj_set_width(diagnostic, 1160);
    storage_label = lv_label_create(pages[2]);
    lv_obj_set_width(storage_label, 1160);
    auto instructions = lv_label_create(pages[1]);
    lv_label_set_text(instructions, "Teste de letras, números, símbolos e navegação. Não digite senhas nesta tela.\nAcentos: ação, café, órgão, maçã, Ç, Ã, Ê, Ó, Ú");
    input_text = lv_textarea_create(pages[1]);
    lv_obj_set_pos(input_text, 0, 64);
    lv_obj_set_size(input_text, 1140, 96);
    lv_textarea_set_max_length(input_text, 128);
    lv_textarea_set_placeholder_text(input_text, "Digite aqui...");
    lv_obj_add_event_cb(input_text, touch_event, LV_EVENT_PRESSED, nullptr);
    lv_obj_add_event_cb(input_text, navigate, LV_EVENT_KEY, nullptr);
    if (!status.keyboard) {
        virtual_keyboard = lv_keyboard_create(pages[1]);
        lv_keyboard_set_textarea(virtual_keyboard, input_text);
        lv_obj_set_size(virtual_keyboard, 1140, 260);
        lv_obj_set_pos(virtual_keyboard, 0, 184);
    }
    if (status.keyboard) {
        auto keyboard = lv_indev_create();
        lv_indev_set_type(keyboard, LV_INDEV_TYPE_KEYPAD);
        lv_indev_set_read_cb(keyboard, keyboard_read);
        lv_indev_set_group(keyboard, group);
        lv_indev_set_display(keyboard, display);
    }
    auto footer = lv_label_create(screen);
    lv_label_set_text(footer, "v0.4.0 | Desenvolvimento | Nenhuma venda é realizada nesta etapa");
    lv_obj_set_pos(footer, 32, 676);
    select_page(0);
    refresh(nullptr);
    lv_timer_create(refresh, 1000, nullptr);
}
}
