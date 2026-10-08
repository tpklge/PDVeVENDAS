"""Record a locally generated device password; never send it through chat/Git."""
import argparse
from datetime import datetime, timezone
import getpass
import os
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--device", required=True)
args = parser.parse_args()
if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.device):
    parser.error("Identificador inválido")
password = getpass.getpass("Senha local escolhida no Tab5: ")
if not 20 <= len(password.encode()) <= 128:
    parser.error("Use entre 20 e 128 bytes")
if password != getpass.getpass("Confirme a senha local: "):
    parser.error("Confirmação diferente")
private = args.root / "docs/private"
private.mkdir(parents=True, exist_ok=True, mode=0o700)
private.chmod(0o700)
report = private / "INITIAL_CREDENTIALS.md"
section = f"## Dispositivo {args.device}"
if report.exists() and section in report.read_text():
    parser.error("Dispositivo já registrado; revise o registro existente localmente")
descriptor = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
os.fchmod(descriptor, 0o600)
with os.fdopen(descriptor, "w") as stream:
    stream.write(f"\n{section}\n\nUsuário: admin-local\nSenha inicial: `{password}`\n")
    stream.write(f"Registrada: {datetime.now(timezone.utc).isoformat()}\n")
    stream.write("Troca: menu Senha local. Recuperação física: docs/authentication.md.\n")
print("Registro privado criado; senha não exibida. Remova a senha inicial após a troca.")
