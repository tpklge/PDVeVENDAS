idf_component_register(SRCS "app_main.cpp" "auth.cpp" "dashboard.cpp" "products.cpp" "contacts.cpp" "sales.cpp" "inventory.cpp" "cash.cpp" "reports.cpp" "platform_ui.cpp" "keyboard.cpp" "storage.cpp" "../fonts/erp_font_pt_20.c" "../fonts/erp_font_pt_28.c"
    INCLUDE_DIRS "." "../fonts" "../core"
    REQUIRES m5stack_tab5 esp_driver_i2c esp_driver_gpio esp_timer esp_psram esp_wifi esp_netif esp_http_client mbedtls json bootloader_support esp_hw_support)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)

# Contact forms live in PSRAM; reject accidental large stack frames.
set_source_files_properties(contacts.cpp sales.cpp inventory.cpp cash.cpp reports.cpp PROPERTIES COMPILE_OPTIONS "-Wframe-larger-than=4096")
