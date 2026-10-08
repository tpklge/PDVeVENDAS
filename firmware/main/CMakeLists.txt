idf_component_register(SRCS "app_main.cpp" "platform_ui.cpp" "keyboard.cpp" "storage.cpp"
    INCLUDE_DIRS "." "../core"
    REQUIRES m5stack_tab5 nvs_flash esp_driver_i2c esp_driver_gpio esp_timer esp_psram)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
