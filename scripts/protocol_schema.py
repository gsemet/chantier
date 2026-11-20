"""Write `board/api/protocol.json` from the models in `board/api/protocol.py` (`just
protocol-schema`). Protocol 1 changes only by addition: review the diff before committing it.

    just protocol-schema
"""

from pathlib import Path

from chantier.board.api import protocol

FILE = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "chantier"
    / "scripts"
    / "cli"
    / "src"
    / "chantier"
    / "board"
    / "api"
    / "protocol.json"
)


def main() -> None:
    data = protocol.canonical().encode("utf-8")
    if not FILE.is_file() or FILE.read_bytes() != data:
        FILE.write_bytes(data)
        print(f"wrote {FILE.name}")


if __name__ == "__main__":
    main()
