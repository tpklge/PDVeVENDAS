"""Generate installation credentials only on the provisioning server."""
import argparse
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

IDENTITIES = {
    "db_root_password": "root", "db_app_password": "tab5_app",
    "db_migration_password": "tab5_migrator", "api_admin_password": "admin",
    "local_admin_password": "admin-local",
}


def generate(root, installation):
    folder = root / "docker/secrets"
    private = root / "docs/private"
    for directory in (folder, private):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    report = private / "INITIAL_CREDENTIALS.md"
    expected = [folder / name for name in IDENTITIES]
    exists = [p.exists() for p in expected]
    if all(exists) and report.exists():
        print("Credenciais existentes preservadas.")
        return
    if any(exists) or report.exists():
        raise SystemExit("Provisionamento parcial detectado; recupere os arquivos existentes antes de continuar.")
    values = {name: secrets.token_urlsafe(32) for name in IDENTITIES}
    generated = datetime.now(timezone.utc).isoformat()
    text = f"# Credenciais iniciais — {installation}\n\nGeradas em {generated} (UTC).\n\n"
    for name, username in IDENTITIES.items():
        # 0444 allows unprivileged container users to read a bind-mounted secret.
        # The enclosing directory is 0700, protecting host access.
        with open(folder / name, "x") as stream:
            stream.write(values[name] + "\n")
        (folder / name).chmod(0o444)
        text += f"## {name}\n\nUsuário: `{username}`\n\nSenha inicial: `{values[name]}`\n\n"
    text += "Troca API: /api/v1/auth/change-password; revoga todas as sessões.\n"
    text += "Credencial admin-local: reservada; ainda NÃO aplicada ao dispositivo nesta versão.\n"
    text += "Troca SQL: ALTER USER em sessão local de manutenção, atualizar secret e reiniciar consumidores.\n"
    text += "Recuperação: manter cópia criptografada; CLI de recuperação será implementado em versão futura.\n"
    text += "Após troca das senhas humanas, eliminar suas senhas iniciais e cópias deste relatório.\n"
    descriptor = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    print("Credenciais geradas em docs/private/INITIAL_CREDENTIALS.md; nenhuma senha exibida.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--installation", default="TAB5 ERP")
    args = parser.parse_args()
    generate(args.root, args.installation)
