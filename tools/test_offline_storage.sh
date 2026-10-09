#!/usr/bin/env bash
set -Eeuo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${IDF_PATH:?Ative o ESP-IDF antes de executar}"
TASK_TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TASK_TEST_DIR"' EXIT
TASK_CRYPTO_DIR="$(python3 "$TASK_ROOT/tools/prepare_crypto.py" "$IDF_PATH" "$TASK_ROOT/firmware/build")"
TASK_MBEDTLS="$TASK_CRYPTO_DIR/mbedtls"
TASK_CJSON="$IDF_PATH/components/json/cJSON"
TASK_FLAGS=()
if [[ -n "${SDKROOT:-}" ]]; then TASK_FLAGS+=(-DCMAKE_OSX_SYSROOT="$SDKROOT"); fi
cmake -S "$TASK_MBEDTLS" -B "$TASK_TEST_DIR/crypto" -DENABLE_TESTING=OFF -DENABLE_PROGRAMS=OFF -DMBEDTLS_FATAL_WARNINGS=OFF "${TASK_FLAGS[@]}" > "$TASK_TEST_DIR/build.log" 2>&1 || { cat "$TASK_TEST_DIR/build.log"; exit 1; }
cmake --build "$TASK_TEST_DIR/crypto" --target mbedtls -j 4 >> "$TASK_TEST_DIR/build.log" 2>&1 || { tail -n 50 "$TASK_TEST_DIR/build.log"; exit 1; }
TASK_CXX_FLAGS=()
if [[ -n "${SDKROOT:-}" ]]; then TASK_CXX_FLAGS+=(-isysroot "$SDKROOT"); fi
cc "${TASK_CXX_FLAGS[@]}" -I "$TASK_CJSON" -c "$TASK_CJSON/cJSON.c" -o "$TASK_TEST_DIR/cjson.o"
c++ "${TASK_CXX_FLAGS[@]}" -std=c++17 -DTAB5_HOST_TEST -Wall -Wextra -Werror -I "$TASK_ROOT/firmware/tests/host_shims" -I "$TASK_ROOT/firmware/main" -I "$TASK_ROOT/firmware/core" -I "$TASK_MBEDTLS/include" -I "$TASK_CJSON" \
    "-DTAB5_OFFLINE_DIRECTORY=\"$TASK_TEST_DIR/store\"" "$TASK_ROOT/firmware/tests/offline_storage_test.cpp" "$TASK_ROOT/firmware/main/journal.cpp" "$TASK_ROOT/firmware/main/offline.cpp" "$TASK_ROOT/firmware/main/offline_catalog.cpp" "$TASK_TEST_DIR/cjson.o" "$TASK_TEST_DIR/crypto/library/libmbedcrypto.a" -o "$TASK_TEST_DIR/test"
"$TASK_TEST_DIR/test"
c++ "${TASK_CXX_FLAGS[@]}" -std=c++17 -Wall -Wextra -Werror -I "$TASK_MBEDTLS/include" \
    "$TASK_ROOT/firmware/tests/tls_client_test.cpp" "$TASK_TEST_DIR/crypto/library/libmbedtls.a" \
    "$TASK_TEST_DIR/crypto/library/libmbedx509.a" "$TASK_TEST_DIR/crypto/library/libmbedcrypto.a" -o "$TASK_TEST_DIR/tls-test"
python3 "$TASK_ROOT/tools/test_tls.py" "$TASK_TEST_DIR/tls-test"
