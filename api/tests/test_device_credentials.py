import getpass
import runpy
import stat
import sys
from pathlib import Path


def test_private_device_record_does_not_echo_password(tmp_path, monkeypatch, capsys):
    password = "fixture-only-local-password-123456"
    monkeypatch.setattr(getpass, "getpass", lambda prompt: password)
    monkeypatch.setattr(sys, "argv", ["record_device_credentials.py", "--root", str(tmp_path), "--device", "test-device"])
    script = Path(__file__).resolve().parents[2] / "tools/record_device_credentials.py"
    runpy.run_path(str(script), run_name="__main__")
    report = tmp_path / "docs/private/INITIAL_CREDENTIALS.md"
    assert password in report.read_text()
    assert stat.S_IMODE(report.stat().st_mode) == 0o600
    assert stat.S_IMODE(report.parent.stat().st_mode) == 0o700
    assert password not in capsys.readouterr().out
