"""Audit pinned Python artifacts against the primary PyPI advisory API; fail closed."""
import concurrent.futures
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def audit(block):
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)(.*)", block, re.S)
    if not match:
        raise ValueError("Entrada inválida no lockfile")
    name, version, tail = match.groups()
    hashes = set(re.findall(r"--hash=sha256:([a-f0-9]{64})", tail))
    if not hashes or re.sub(r"--hash=sha256:[a-f0-9]{64}", "", tail).strip():
        raise ValueError(f"Hashes inválidos: {name}")
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        data = json.load(response)
    published = {artifact["digests"]["sha256"] for artifact in data["urls"]}
    if not hashes <= published:
        raise ValueError(f"Hash não publicado pelo PyPI: {name}")
    active = [advisory["id"] for advisory in data.get("vulnerabilities", []) if not advisory.get("withdrawn")]
    if active:
        raise ValueError(f"Avisos de segurança em {name} {version}: {', '.join(active)}")
    return {"name": name, "version": version, "artifact_hashes": len(hashes), "active_advisories": 0}


def main():
    lines = [line for line in (ROOT / "api/requirements.lock").read_text().splitlines() if line.strip() and not line.startswith("#")]
    blocks = "\n".join(lines).replace("\\\n", " ").splitlines()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(audit, blocks))
    print(json.dumps({"source": "https://pypi.org", "packages": rows}, indent=2))


if __name__ == "__main__":
    main()
