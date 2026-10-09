"""Real handshakes with the firmware's vendor crypto and disposable local certificates."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile


def command(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


with tempfile.TemporaryDirectory(prefix="tab5-tls-") as folder:
    root = Path(folder)
    ca, key, cert, csr = [root / name for name in ("ca.pem", "ca.key", "server.pem", "server.csr")]
    server_key = root / "server.key"
    command("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
            "-out", str(ca), "-days", "2", "-subj", "/CN=TAB5 Test CA")
    command("openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", str(server_key),
            "-out", str(csr), "-subj", "/CN=api.tab5.test")
    extension = root / "extensions"
    extension.write_text("subjectAltName=DNS:api.tab5.test\nbasicConstraints=critical,CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
    command("openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca), "-CAkey", str(key),
            "-CAcreateserial", "-out", str(cert), "-days", "1", "-extfile", str(extension))
    other = root / "untrusted.pem"
    command("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(root/"other.key"),
            "-out", str(other), "-days", "2", "-subj", "/CN=Untrusted Test CA")
    (root/"index").write_text("");(root/"serial").write_text("01\n")
    config=root/"ca.conf"
    config.write_text(f"[ca]\ndefault_ca=local\n[local]\ndatabase={root}/index\nnew_certs_dir={root}\nserial={root}/serial\ncertificate={ca}\nprivate_key={key}\ndefault_md=sha256\npolicy=policy\n[policy]\ncommonName=supplied\n")
    expired=root/"expired.pem"
    command("openssl","ca","-batch","-config",str(config),"-in",str(csr),"-out",str(expired),
            "-startdate","20000101000000Z","-enddate","20010101000000Z","-extfile",str(extension),"-notext")

    def check(certificate, trust, hostname, expected):
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.maximum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certificate,server_key)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0));listener.listen(1);listener.settimeout(10)
            def server():
                connection,_=listener.accept();connection.settimeout(5)
                try:
                    with context.wrap_socket(connection,server_side=True) as stream:
                        return stream.recv(32)
                except (ssl.SSLError, OSError):
                    connection.close();return b""
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(server)
                subprocess.run([sys.argv[1],str(listener.getsockname()[1]),str(trust),hostname,expected],check=True,timeout=10)
                data=future.result(timeout=10)
            assert data==(b"verified" if expected=="valid" else b""),"Application bytes before verified TLS"
    check(cert,ca,"api.tab5.test","valid")
    check(cert,ca,"wrong.tab5.test","invalid")
    check(cert,other,"api.tab5.test","invalid")
    check(expired,ca,"api.tab5.test","invalid")
print("PASS: TLS real — CA/hostname válidos, CA desconhecida, hostname incorreto e certificado expirado; nenhum dado enviado em TLS inválido.")
