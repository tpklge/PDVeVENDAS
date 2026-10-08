#pragma once
#include <cstdint>
#include <limits>
#include <optional>

namespace tab5 {
// Values are cents; quantities are thousandths. Negative stock is forbidden.
// The API revalidates all prices, discounts and permissions when confirming.
inline std::optional<std::int64_t> line_total(std::int64_t unit_cents,
        std::int64_t quantity_milli, std::int64_t discount_cents = 0) {
    constexpr auto maximum = std::numeric_limits<std::int64_t>::max();
    if (unit_cents < 0 || quantity_milli <= 0 || discount_cents < 0)
        return std::nullopt;
    if (unit_cents != 0 && quantity_milli > maximum / unit_cents)
        return std::nullopt;
    const auto product = unit_cents * quantity_milli;
    const auto subtotal = product / 1000 + (product % 1000 >= 500 ? 1 : 0);
    if (discount_cents > subtotal) return std::nullopt;
    return subtotal - discount_cents;
}
}
