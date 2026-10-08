from pathlib import Path
import re
version = Path("VERSION").read_text().strip()
assert re.fullmatch(r"\d+\.\d+\.\d+", version)
firmware_version = Path("firmware/VERSION").read_text().strip() if Path("firmware/VERSION").exists() else version
assert f"VERSION {firmware_version}" in Path("firmware/CMakeLists.txt").read_text()
assert f"## {version}" in Path("CHANGELOG.md").read_text()
assert Path(f"docs/releases/v{version}.md").is_file()
print("VERSION, CMake, CHANGELOG e relatório coerentes.")
