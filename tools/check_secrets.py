"""Small deterministic guard, not a substitute for a full secret scanner."""
import re
import subprocess
from pathlib import Path

files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
blocked = []
for name in filter(None, files):
    if name.startswith(("docs/private/", "docker/secrets/", "docker/backups/")) or name in {".env", "docker/.env"}:
        blocked.append(name)
        continue
    path = Path(name)
    if not path.is_file():
        continue
    data = path.read_text(errors="ignore")
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
        blocked.append(name)
    if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})", data):
        blocked.append(name)
if blocked:
    raise SystemExit("Possíveis segredos/arquivos privados: " + ", ".join(blocked))
print("Verificação de arquivos privados e padrões de secrets aprovada.")
