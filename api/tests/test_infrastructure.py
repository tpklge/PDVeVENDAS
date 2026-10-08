import importlib.util
from pathlib import Path
import stat
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_network_boundary():
    config = yaml.safe_load((ROOT / "docker/compose.yaml").read_text())
    services = config["services"]
    assert "ports" not in services["mariadb"]
    assert "ports" not in services["api"]
    assert config["networks"]["backend"]["internal"]
    assert services["api"]["environment"]["DB_USER"] != services["migrate"]["environment"]["DB_USER"]
    assert services["api"]["secrets"] == ["db_app_password"]
    assert services["mariadb"]["networks"] == ["backend"]
    # Child file mounts need writable parent mountpoints during OCI setup.
    assert not any(mount.split(":")[1] == "/docker-entrypoint-initdb.d"
                   for mount in services["mariadb"]["volumes"])
    assert services["mariadb"]["labels"]["traefik.enable"] == "false"
    assert services["migrate"]["labels"]["traefik.enable"] == "false"
    assert config["networks"]["traefik"]["external"]
    labels = services["api"]["labels"]
    assert labels["traefik.enable"] == "true"
    assert labels["traefik.http.services.tab5-api.loadbalancer.server.port"] == "8000"
    assert "tab5api.ampere.diadiatech.com.br" in labels["traefik.http.routers.tab5-api.rule"]
    assert services["api"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    for filename in ("schema.sql", "initial_data.sql"):
        assert any(f"../database/{filename}:" in mount for mount in services["mariadb"]["volumes"])
        assert (ROOT / "database" / filename).is_file()


def test_credentials_distinct_protected_and_idempotent(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("credentials", ROOT / "tools/generate_credentials.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(tmp_path, "test-installation")
    secrets = tmp_path / "docker/secrets"
    contents = [(secrets / name).read_text() for name in module.IDENTITIES]
    assert len(set(contents)) == 5
    assert all(len(value.strip()) >= 20 for value in contents)
    report = tmp_path / "docs/private/INITIAL_CREDENTIALS.md"
    assert stat.S_IMODE(report.stat().st_mode) == 0o600
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o700
    previous = report.read_bytes()
    module.generate(tmp_path, "test-installation")
    assert report.read_bytes() == previous
    assert all(value.strip() not in capsys.readouterr().out for value in contents)
