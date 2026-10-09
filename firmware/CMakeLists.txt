cmake_minimum_required(VERSION 3.16)
# Security fixes from the vendor's maintained 3.6.7 fork, isolated to this build.
find_program(TAB5_PYTHON NAMES python3 REQUIRED)
execute_process(COMMAND "${TAB5_PYTHON}" "${CMAKE_CURRENT_SOURCE_DIR}/../tools/prepare_crypto.py"
    "$ENV{IDF_PATH}" "${CMAKE_BINARY_DIR}" RESULT_VARIABLE TAB5_CRYPTO_RESULT
    OUTPUT_VARIABLE TAB5_CRYPTO_DIR OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT TAB5_CRYPTO_RESULT EQUAL 0)
    message(FATAL_ERROR "Could not prepare verified Mbed TLS 3.6.7")
endif()
list(APPEND EXTRA_COMPONENT_DIRS "${TAB5_CRYPTO_DIR}")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(tab5_erp VERSION 0.12.0)
