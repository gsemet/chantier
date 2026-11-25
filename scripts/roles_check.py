"""Check both hosts' hand-written agent files against `skills/chantier/roles.yaml` (`just roles`).

Reads only files under `--root` (the repository by default) and writes nothing. Each problem prints
one line, `roles: <role> (<host>): <what>`; a clean tree prints one summary line. `--write <role>`
prints the agent file the data expects (for one host with `--host`, else both), for a person
editing a wrapper by hand to copy from: nothing writes it for them.

    just roles
    just roles --write coder --host copilot
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from chantier.core.errors import ChantierError
from chantier.roles_data import HOSTS, Role, load_roles

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = {"claude": "agents", "copilot": "com.github.copilot/agents"}
FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.S)
MUST_START = re.compile(r"My prompt must start with `([^`]*)`")
CARD_LINE = re.compile(r"Your card is `([^`]*)`")
REFERENCES = "skills/chantier/references"


def _lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _agent_name(role: str, host: str) -> str:
    return role if host == "claude" else f"chantier-{role}"


def _description(role: Role) -> str:
    return f"{role.description} Prompt starts with: `{role.first}`"


def _split(text: str) -> tuple[str, str] | None:
    """The frontmatter's text (between the two `---` lines) and the body after it."""
    m = FRONTMATTER.match(text)
    return (m[1], text[m.end() :]) if m else None


def _tools(host: str, value: object) -> list[str] | None:
    if host == "claude":
        return value.split(", ") if isinstance(value, str) else None
    return [str(v) for v in value] if isinstance(value, list) else None


class Checker:
    def __init__(self, root: Path, roles: tuple[Role, ...]) -> None:
        self.root, self.roles = root, roles
        self.problems: list[str] = []

    def bad(self, role: str, host: str, what: str) -> None:
        self.problems.append(f"roles: {role} ({host}): {what}")

    def run(self) -> list[str]:
        self.wrapper_set()
        for role in self.roles:
            self.references(role)
            bodies: dict[str, str] = {}
            for host in HOSTS:
                path = role.hosts[host].wrapper
                if path is None or not (self.root / path).is_file():
                    continue
                body = self.wrapper(role, host, self.root / path)
                if body is not None:
                    bodies[host] = body
            if len(bodies) == len(HOSTS) and len(set(bodies.values())) > 1:
                self.bad(role.name, HOSTS[-1], f"body differs from the {HOSTS[0]} host's")
        return self.problems

    def wrapper_set(self) -> None:
        for host, folder in FOLDERS.items():
            named = {r.hosts[host].wrapper: r.name for r in self.roles if r.hosts[host].wrapper}
            base = self.root / folder
            found = {f"{folder}/{p.name}" for p in base.glob("*.md")} if base.is_dir() else set()
            for path in sorted(found - set(named)):
                self.bad(Path(path).stem, host, f"{path} has no entry in roles.yaml")
            for path in sorted(set(named) - found):
                self.bad(named[path], host, f"no file {path}")

    def references(self, role: Role) -> None:
        refs = self.root / REFERENCES
        if not (refs / role.card).is_file():
            self.bad(role.name, "data", f"card {role.card}: no such file under references/")
        if role.reply == "none":
            return
        file, _, heading = role.reply.partition("#")
        if not (refs / file).is_file():
            self.bad(role.name, "data", f"reply {role.reply}: no file {file} under references/")
        elif heading and not any(
            line in (f"# {heading}", f"## {heading}") for line in _lf(refs / file).split("\n")
        ):
            self.bad(role.name, "data", f"reply {role.reply}: no heading `{heading}` in {file}")

    def parse(self, role: Role, host: str, path: Path) -> tuple[dict[str, object], str] | None:
        """An agent file's frontmatter and body, or None (a problem said) when it cannot be read."""
        from ruamel.yaml import YAML
        from ruamel.yaml.error import YAMLError

        parts = _split(_lf(path))
        if parts is None:
            self.bad(role.name, host, f"{path.name}: no frontmatter")
            return None
        try:
            front = YAML(typ="safe", pure=True).load(parts[0])
        except YAMLError as e:
            self.bad(role.name, host, f"{path.name}: the frontmatter does not parse: {e}")
            return None
        return (front if isinstance(front, dict) else {}), parts[1]

    def wrapper(self, role: Role, host: str, path: Path) -> str | None:
        """Check one agent file; its body, or None when it cannot be read."""
        parsed = self.parse(role, host, path)
        if parsed is None:
            return None
        front, body = parsed
        self.frontmatter(role, host, front)
        self.body(role, host, body)
        return body

    def frontmatter(self, role: Role, host: str, front: dict[str, object]) -> None:
        name = _agent_name(role.name, host)
        if front.get("name") != name:
            self.bad(role.name, host, f"name is {front.get('name')!r}, not {name!r}")
        if front.get("description") != _description(role):
            self.bad(
                role.name, host, f"description differs from roles.yaml's: {_description(role)}"
            )
        tools = _tools(host, front.get("tools"))
        if tools != list(role.hosts[host].tools):
            self.bad(
                role.name,
                host,
                f"tools {tools} differ from roles.yaml's {list(role.hosts[host].tools)}",
            )

    def body(self, role: Role, host: str, body: str) -> None:
        if f"My prompt must start with `{role.first}`" not in body:
            self.bad(
                role.name,
                host,
                f"the body does not hold `My prompt must start with `{role.first}``",
            )
        if f"does not start with `chantier {role.name}" not in body:
            self.bad(
                role.name,
                host,
                f"the body does not hold `does not start with `chantier {role.name}`",
            )
        card = Path(role.card).name
        for m in CARD_LINE.finditer(body):
            if m[1] != card:
                self.bad(role.name, host, f"the body's card is `{m[1]}`, not `{card}`")


def _expected(root: Path, role: Role, host: str) -> str:
    """The agent file the data expects on `host`: its committed frontmatter with the name, the
    description and the tools from the data, then the claude host's body with the data's first
    line and card name."""
    committed = _split(_lf(root / str(role.hosts[host].wrapper)))
    claude = _split(_lf(root / str(role.hosts["claude"].wrapper)))
    if committed is None or claude is None:
        raise ChantierError(f"{role.name}: an agent file has no frontmatter")
    tools = role.hosts[host].tools
    keys = {
        "name": _agent_name(role.name, host),
        "description": "'" + _description(role).replace("'", "''") + "'",
        "tools": ", ".join(tools)
        if host == "claude"
        else "[" + ", ".join(f'"{t}"' for t in tools) + "]",
    }
    front = [
        f"{key}: {keys[key]}" if (key := line.partition(":")[0]) in keys else line
        for line in committed[0].split("\n")
    ]
    body = MUST_START.sub(lambda _: f"My prompt must start with `{role.first}`", claude[1])
    body = CARD_LINE.sub(lambda _: f"Your card is `{Path(role.card).name}`", body)
    return "---\n" + "\n".join(front) + "---\n" + body


def _write(root: Path, roles: tuple[Role, ...], name: str, host: str | None) -> int:
    role = next((r for r in roles if r.name == name), None)
    if role is None:
        print(f"roles: no role {name}; roles: {', '.join(r.name for r in roles)}")
        return 1
    if role.hosts["claude"].wrapper is None:
        print(f"{name} has no wrapper")
        return 1
    for h in [host] if host else list(HOSTS):
        print(f"=== {role.hosts[h].wrapper}")
        sys.stdout.write(_expected(root, role, h))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="roles_check", description=__doc__.split("\n")[0])
    parser.add_argument(
        "--root", type=Path, default=ROOT, help="the repository (default: this one)"
    )
    parser.add_argument("--write", metavar="ROLE", help="print the agent file the data expects")
    parser.add_argument("--host", choices=HOSTS, help="with --write: one host only")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    data = root / "skills" / "chantier" / "roles.yaml"
    if not data.is_file():
        print(f"roles: no file {data.as_posix()}")
        return 1
    try:
        roles = load_roles(data)
    except ChantierError as e:
        print(f"roles: {e}")
        return 1
    if args.write:
        return _write(root, roles, args.write, args.host)
    if args.host:
        parser.error("--host goes with --write")
    problems = Checker(root, roles).run()
    for line in problems:
        print(line)
    if problems:
        print(f"roles: {len(problems)} problem(s)")
        return 1
    wrapped = sum(1 for r in roles if r.hosts["claude"].wrapper is not None)
    print(f"roles: {len(roles)} roles, {wrapped} wrappers on {len(HOSTS)} hosts agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
