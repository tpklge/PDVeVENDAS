import argparse
import getpass
import re
from pathlib import Path
from sqlalchemy import select, update
from .db import SessionFactory
from .models import AuditLog, Role, Session, User
from .security import hasher
from .seed import seed


def main():
    parser = argparse.ArgumentParser(description="Administração local do servidor TAB5 ERP")
    parser.add_argument("operation", choices=["seed", "provision-admin", "revoke-sessions", "reset-password"])
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password-file")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_.@+-]{1,80}", args.username):
        parser.error("Usuário inválido")
    password = None
    if args.operation == "reset-password":
        # Do not hold a database row lock while waiting for keyboard input.
        password = getpass.getpass("Nova senha ERP (mínimo 8 caracteres): ")
        confirmation = getpass.getpass("Confirme a nova senha: ")
        if password != confirmation or not 8 <= len(password) <= 128:
            raise SystemExit("Senhas diferentes ou tamanho inválido. Nenhuma alteração aplicada.")
    with SessionFactory.begin() as db:
        if args.operation == "seed":
            seed(db)
        elif args.operation == "provision-admin":
            if db.scalar(select(User.id).limit(1)):
                raise SystemExit("Provisionamento encerrado: já existem usuários. Nenhuma credencial alterada.")
            if not args.password_file:
                parser.error("Informe --password-file")
            password = Path(args.password_file).read_text().strip()
            if not 8 <= len(password) <= 128:
                raise SystemExit("A senha deve ter entre 8 e 128 caracteres.")
            role = db.scalar(select(Role).where(Role.name == "Administrador"))
            if not role:
                raise SystemExit("Execute as migrações e seed antes do provisionamento.")
            db.add(User(username=args.username, password_hash=hasher.hash(password), roles=[role]))
        else:
            user = db.scalar(select(User).where(User.username == args.username).with_for_update())
            if not user:
                raise SystemExit("Usuário não encontrado.")
            if args.operation == "reset-password":
                user.password_hash = hasher.hash(password)
                user.must_change_password = False
            db.execute(update(Session).where(Session.user_id == user.id).values(revoked=True))
            db.add(AuditLog(user_id=None, operation="auth.reset_password" if args.operation == "reset-password" else "auth.revoke", entity="users", entity_id=str(user.id),
                result="success", origin="server-cli", correlation_id="server-cli"))
    print("Operação concluída; credenciais não são exibidas.")

if __name__ == "__main__":
    main()
