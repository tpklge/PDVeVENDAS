"""Build-local Espressif Mbed TLS 3.6.7 override; never modifies the installed SDK."""
import hashlib
import io
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request

COMMIT = "2b96dd8eebe880f304c69976b3c2fa0c5100cbb6"
SHA256 = "1b3c8ee0d78a6b0b492d1e0732ae11a7451180e010ed4109b5f4f299c6c210a3"
URL = f"https://codeload.github.com/espressif/mbedtls/tar.gz/{COMMIT}"


def prepare(idf, build):
    source = idf.resolve() / "components/mbedtls"
    destination = build.resolve() / "security/mbedtls"
    marker = destination / ".tab5-crypto"
    # Also fingerprint the integration/port, so changing SDK regenerates the copy.
    fingerprint = hashlib.sha256()
    for entry in sorted(source.rglob("*")):
        if entry.is_file() and entry.relative_to(source).parts[0] not in {"mbedtls", ".git", "test_apps"}:
            fingerprint.update(str(entry.relative_to(source)).encode())
            fingerprint.update(entry.read_bytes())
    expected = f"{COMMIT}\n{SHA256}\n{source}\n{fingerprint.hexdigest()}\n"
    if marker.exists() and marker.read_text() == expected and (destination / "mbedtls/library/ssl_tls.c").is_file():
        return destination
    archive = build.resolve() / f"security/{COMMIT}.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError("Arquivo Mbed TLS não corresponde ao SHA-256 fixado")
        archive.write_bytes(data)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for entry in source.iterdir():
        if entry.name in {"mbedtls", ".git", "test_apps"}:
            continue
        if entry.is_dir():
            shutil.copytree(entry, destination / entry.name)
        else:
            shutil.copy2(entry, destination / entry.name)
    prefix = f"mbedtls-{COMMIT}/"
    with tarfile.open(fileobj=io.BytesIO(archive.read_bytes())) as bundle:
        for member in bundle.getmembers():
            if not member.name.startswith(prefix):
                continue
            relative = Path(member.name[len(prefix):])
            if relative.is_absolute() or ".." in relative.parts or member.issym() or member.islnk():
                raise ValueError("Caminho inválido no arquivo Mbed TLS")
            target = destination / "mbedtls" / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as content:
                    target.write_bytes(content.read())
    marker.write_text(expected)
    return destination


if __name__ == "__main__":
    print(prepare(Path(sys.argv[1]), Path(sys.argv[2])))
