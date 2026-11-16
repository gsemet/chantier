"""Refresh the Copilot model catalog from GitHub's tables (`just copilot-models`; by hand, network).

Copies the tables of `github/docs` at one commit into `playbook/copilot_tables/`, writes
`SOURCE.json`, builds `playbook/copilot-models.json` from the copy and prints the commit, one row
per model, the differences between GitHub's sources and the differences with the Copilot agent
files. It exits 0 whatever the differences; any failed download, missing section or empty catalog
stops it with nothing written. The commit that follows is the maintainer's.

    just copilot-models [--ref <sha>]
"""

import argparse
import datetime
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from chantier.playbook import copilot_catalog as catalog

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "skills" / "chantier" / "scripts" / "cli" / "src" / "chantier" / "playbook"
AGENTS = ROOT / "com.github.copilot" / "agents"
REPOSITORY = "github/docs"
TABLE_DIR = "data/tables/copilot"
REFERENCE_PATH = "content/copilot/reference/copilot-cli-reference/cli-command-reference.md"
FILES = {
    catalog.CLIENTS: f"{TABLE_DIR}/{catalog.CLIENTS}",
    catalog.AUTO: f"{TABLE_DIR}/{catalog.AUTO}",
    catalog.STATUS: f"{TABLE_DIR}/{catalog.STATUS}",
    catalog.PLANS: f"{TABLE_DIR}/{catalog.PLANS}",
    catalog.CLI_REFERENCE: REFERENCE_PATH,
}
SECTION = "## Supported models"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "chantier-copilot-models"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            data: bytes = response.read()
    except (urllib.error.URLError, OSError) as error:
        raise SystemExit(f"{url}: {error}") from error
    return data


def head_commit() -> str:
    body = fetch(f"https://api.github.com/repos/{REPOSITORY}/commits/main")
    sha = json.loads(body).get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit(f"https://api.github.com/repos/{REPOSITORY}/commits/main: no commit sha")
    return str(sha)


def supported_models_section(reference: bytes) -> bytes:
    """The section's lines, from its heading to the next `## ` heading, verbatim."""
    lines = reference.decode("utf-8").splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == SECTION), None)
    if start is None:
        raise SystemExit(f'{REFERENCE_PATH}: no "{SECTION[3:]}" section')
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "".join(lines[start:end]).encode("utf-8")


def download(sha: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name, path in FILES.items():
        data = fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{sha}/{path}")
        files[name] = supported_models_section(data) if name == catalog.CLI_REFERENCE else data
    return files


def row(m: dict[str, object]) -> str:
    plans = m["plans"]
    shown = (
        "none" if plans is None else ",".join(k for k, v in plans.items() if v)  # type: ignore[attr-defined]
    )
    return (
        f"{m['id']} | {m['name']} | {m['release_status']} | cli {m['cli']} | app {m['app']}"
        f" | plans {shown} | in CLI reference {m['in_cli_reference']}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--ref", help="the github/docs commit to copy from (default: main's head)")
    sha = parser.parse_args(argv).ref or head_commit()
    files = download(sha)
    source = {
        "repository": REPOSITORY,
        "commit": sha,
        "date": datetime.datetime.now(datetime.UTC).date().isoformat(),
        "files": FILES,
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in files.items():
            (Path(tmp) / name).write_bytes(data)
        try:
            doc = catalog.document(source, Path(tmp))
        except ValueError as error:
            raise SystemExit(f"cannot parse the tables: {error}") from error
    if not doc["models"]:
        raise SystemExit("the catalog built from the tables is empty; nothing written")
    tables = PACKAGE / "copilot_tables"
    tables.mkdir(exist_ok=True)
    for name, data in files.items():
        (tables / name).write_bytes(data)
    (tables / "SOURCE.json").write_bytes(catalog.dump(source).encode("utf-8"))
    (PACKAGE / "copilot-models.json").write_bytes(catalog.dump(doc).encode("utf-8"))
    print(f"commit: {sha} ({REPOSITORY})")
    for m in doc["models"]:
        print(row(m))
    print("differences:" + ("" if doc["differences"] else " none"))
    for line in doc["differences"]:
        print(f"  {line}")
    agents = catalog.agent_file_differences(doc["models"], AGENTS)
    print("agent files:" + ("" if agents else " none"))
    for line in agents:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
