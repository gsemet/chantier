"""Write the missing entries of the journal's shipped JSON Schemas (`just journal-schemas`).

Adds, to `hub/schemas.json`, the schema of each type in `hub/schemas.py`'s `PUBLISHED` that the
file lacks; never changes an existing entry. Prints one line per entry added and one per existing
entry that differs from its model (publish the next version instead); nothing when there is
neither. The commit that follows is the maintainer's.

    just journal-schemas
"""

import json
from pathlib import Path

from chantier.hub import schemas

FILE = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "chantier"
    / "scripts"
    / "cli"
    / "src"
    / "chantier"
    / "hub"
    / "schemas.json"
)


def main() -> None:
    shipped = json.loads(FILE.read_text(encoding="utf-8")) if FILE.is_file() else {}
    merged, said = schemas.merge(shipped)
    data = schemas.canonical(merged).encode("utf-8")
    if not FILE.is_file() or FILE.read_bytes() != data:
        FILE.write_bytes(data)
    for line in said:
        print(line)


if __name__ == "__main__":
    main()
