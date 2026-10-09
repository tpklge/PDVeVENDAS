from pathlib import Path
import re
version = Path("VERSION").read_text().strip()
assert re.fullmatch(r"\d+\.\d+\.\d+", version)
firmware_version = Path("firmware/VERSION").read_text().strip() if Path("firmware/VERSION").exists() else version
assert firmware_version == version
assert f"VERSION {firmware_version}" in Path("firmware/CMakeLists.txt").read_text()
assert f"## {version}" in Path("CHANGELOG.md").read_text()
assert Path(f"docs/releases/v{version}.md").is_file()
assert f'VERSION = "{version}"' in Path("api/app/config.py").read_text()
assert f"image: tab5-erp-api:{version}" in Path("docker/compose.yaml").read_text()
assert f"tab5-erp-v{version}-usb" in Path(".github/workflows/platform.yml").read_text()
print("VERSION, firmware, API, Docker, CI, CHANGELOG e relatório coerentes.")
