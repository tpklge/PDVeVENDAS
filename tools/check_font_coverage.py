"""Validate rendered glyph coverage against every UTF-8 literal in the UI."""
import ast
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ui = "\n".join((root / "firmware/main" / name).read_text(encoding="utf-8")
               for name in ("platform_ui.cpp", "auth.cpp", "dashboard.cpp", "products.cpp") if (root / "firmware/main" / name).exists())
strings = [ast.literal_eval('"' + value + '"') for value in re.findall(r'"((?:\\.|[^"\\])*)"', ui)]
required = set("".join(strings)) | set("çÇãÃõÕáÁéÉíÍóÓúÚâÂêÊôÔàÀüÜ")
required -= set("\n\r\t")
for size in (20, 28):
    data = (root / f"firmware/fonts/erp_font_pt_{size}.c").read_text(encoding="utf-8")
    cmap = data.split("cmaps[]", 1)[1].split("/*--------------------", 1)[0]
    ranges = [(int(start), int(length), int(glyph)) for start, length, glyph in
        re.findall(r"\.range_start = (\d+), \.range_length = (\d+), \.glyph_id_start = (\d+)", cmap)]
    descriptors = data.split("glyph_dsc[]", 1)[1].split("};", 1)[0]
    boxes = [(int(width), int(height)) for width, height in
        re.findall(r"\.box_w = (\d+), \.box_h = (\d+)", descriptors)]
    missing = []
    for char in sorted(required):
        glyph = next((base + ord(char) - start for start, length, base in ranges
                      if start <= ord(char) < start + length), 0)
        if not glyph or glyph >= len(boxes) or (not char.isspace() and 0 in boxes[glyph]):
            missing.append(f"{char!r} U+{ord(char):04X}")
    assert not missing, f"Fonte {size}px sem glifos: " + ", ".join(missing)
    print(f"Fonte {size}px: {len(required)} caracteres da UI/pt-BR com glifos válidos.")
