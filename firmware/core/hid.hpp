#pragma once
#include <cstdint>
namespace tab5 {
// USB HID usage table. Returns Unicode ASCII or 0 for unsupported/modifier usages.
inline std::uint32_t hid_character(std::uint8_t usage, std::uint8_t modifier) {
    const bool shift = (modifier & 0x22) != 0;
    if (usage >= 0x04 && usage <= 0x1d) return (shift ? 'A' : 'a') + usage - 0x04;
    if (usage >= 0x1e && usage <= 0x27) {
        constexpr char digits[] = "1234567890";
        constexpr char symbols[] = "!@#$%^&*()";
        return shift ? symbols[usage - 0x1e] : digits[usage - 0x1e];
    }
    switch (usage) {
    case 0x2c: return ' ';
    case 0x2d: return shift ? '_' : '-';
    case 0x2e: return shift ? '+' : '=';
    case 0x2f: return shift ? '{' : '[';
    case 0x30: return shift ? '}' : ']';
    case 0x31: return shift ? '|' : '\\';
    case 0x33: return shift ? ':' : ';';
    case 0x34: return shift ? '"' : '\'';
    case 0x35: return shift ? '~' : '`';
    case 0x36: return shift ? '<' : ',';
    case 0x37: return shift ? '>' : '.';
    case 0x38: return shift ? '?' : '/';
    default: return 0;
    }
}
}
