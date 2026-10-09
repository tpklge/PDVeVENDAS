"""Package the compiled application and incremental server update without private data."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
BUILD = ROOT / "firmware/build"
DIST = ROOT / "dist"


def main():
    binary = BUILD / "tab5_erp.bin"
    assert json.loads((BUILD / "project_description.json").read_text())["project_version"] == VERSION
    inputs = [file for folder in ["firmware/main", "firmware/core", "firmware/fonts"]
              for file in (ROOT / folder).rglob("*") if file.suffix in {".c", ".cpp", ".hpp", ".h"}]
    assert binary.stat().st_mtime >= max(file.stat().st_mtime for file in inputs), "Compile o firmware atualizado"
    DIST.mkdir(exist_ok=True)
    update_script = "update-stable.sh" if VERSION == "1.0.0" else "update-security.sh"
    app = DIST / f"TAB5_ERP-v{VERSION}-app-OTA.bin"
    shutil.copyfile(binary, app)
    files = [file for file in (ROOT / "api").rglob("*") if file.is_file()
             and file.suffix in {".py", ".ini", ".in", ".txt", ".lock"} and "__pycache__" not in file.parts]
    files += list((ROOT / "docker/scripts").glob("*.sh"))
    files += [ROOT / name for name in ["VERSION", "LICENSE", "CHANGELOG.md", "docker/api.Dockerfile",
              "docker/compose.yaml", f"docs/releases/v{VERSION}.md", "docs/api.md", "docs/security.md",
              "docs/recovery.md", "docs/final-validation.md", "docs/installation.md", "docs/wifi.md", "docs/traefik.md", "docker/README.md", "docs/synchronization.md", "docs/permissions.md", "docs/database.md",
              "docs/licenses/mbedtls.txt", "tools/audit_dependencies.py"]]
    server = DIST / f"TAB5_ERP-v{VERSION}-server-update.zip"
    with zipfile.ZipFile(server, "w", zipfile.ZIP_DEFLATED) as package:
        for file in sorted(set(files)):
            relative = file.relative_to(ROOT)
            assert not any(part in {"secrets", "backups", "private", "dist", ".venv"} or part.startswith(".env") for part in relative.parts)
            package.write(file, relative)
        package.writestr("README-update.txt", f"TAB5 ERP {VERSION}\n\nServidor antes do OTA:\n"
            f"cd /home/ubuntu/TAB5_ERP\nunzip -o TAB5_ERP-v{VERSION}-server-update.zip\n"
            f"bash docker/scripts/{update_script}\n\n"
            f"Depois instale TAB5_ERP-v{VERSION}-app-OTA.bin pelo launcher habitual.\n"
            "Preserve microSD, PIN, usuários/senhas, .env/secrets e volumes. Não reimportar SQL/initialize.\n"
            f"Leia docs/releases/v{VERSION}.md e docs/recovery.md.\n")
    with zipfile.ZipFile(server) as package:
        assert package.testzip() is None
        required = {"api/requirements.lock", "api/app/request_limits.py", "api/migrations/versions/008_offline.py",
                    "docker/scripts/update-security.sh", "docker/scripts/validate-security.sh"}
        required.add(f"docker/scripts/{update_script}")
        assert required <= set(package.namelist())
    licenses = DIST / f"TAB5_ERP-v{VERSION}-LICENSES.txt"
    licenses.write_text((ROOT / "LICENSE").read_text() + "\n\nMbed TLS — Apache-2.0 escolhida:\n" + (ROOT / "docs/licenses/mbedtls.txt").read_text())
    for artifact in [app, server, licenses]:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        (DIST / (artifact.name + ".sha256")).write_text(f"{digest}  {artifact.name}\n")
        print(artifact.name, artifact.stat().st_size, "bytes", digest)


if __name__ == "__main__":
    main()
