"""The roles `chantier brief` writes a start brief for: each role's card, whether it has a wrapper,
the unit its facts come from, what its short prompt lets it write and the host rows it gets. The
table is data `brief` prints, not a rule the CLI applies: a test holds it to the shipped wrappers
and `startup-manifest.json`, so the two cannot drift."""

from __future__ import annotations

from dataclasses import dataclass

from chantier.driver_prompt import driver_table

CR, ORDER, STACK, FOLDER, NONE = "cr", "order", "stack", "folder", "none"
WRITES_NONE, WRITES_WORKTREE, WRITES_CR_FOLDER = "none", "worktree", "cr-folder"

MESSAGE_STEERING = ("driver-messages-steering-direct", "driver-hand-back")
START_A_CHILD = ("start-driver", "start-generic-agent")
ENDING = ("end-turn-background",)
DRIVER_ENDING = (*ENDING, "stop-own-background-task")
COMPACTING = ("compact",)
WRITE_GUARD = ("write-guard",)

DRIVER_ROWS = (*MESSAGE_STEERING, *START_A_CHILD, *DRIVER_ENDING, *COMPACTING, *WRITE_GUARD)
GRILLER_ROWS = ("start-spec-critic", *ENDING, *COMPACTING, "reload-after-compact")


@dataclass(frozen=True)
class RoleData:
    """One role. `first` is the wrapper's first-line template, `None` for a role with no wrapper;
    `rows` the capability ids of the host rows it gets (`None`: every row)."""

    name: str
    card: str
    wrapper: bool
    first: str | None
    unit: str
    writes: str
    rows: tuple[str, ...] | None


NO_WRAPPER = ("chief-of-staff", "griller", "foreman")


def _role(name: str, card: str, unit: str, writes: str, rows: tuple[str, ...] | None) -> RoleData:
    return RoleData(name, card, name not in NO_WRAPPER, None, unit, writes, rows)


WORKERS = ("coder", "conflict-resolver", "debugger", "inspector", "investigator", "verifier")
DRIVERS = {
    "cr-driver": CR,
    "release-driver": CR,
    "stack-driver": STACK,
    "qa-driver": ORDER,
}


def roles() -> tuple[RoleData, ...]:
    """The 18 roles. The four Drivers' card and `writes` come from the Driver's prompt table
    (`concepts.md`), read now: the plugin's folder is known once a command runs."""
    table = {cells[0].strip("`"): cells for cells in driver_table()}
    drivers = [
        _role(
            name,
            table[name][2].strip("`"),
            unit,
            WRITES_CR_FOLDER if table[name][3].strip("`").lower() != "none" else WRITES_NONE,
            DRIVER_ROWS,
        )
        for name, unit in DRIVERS.items()
    ]
    workers = [_role(w, f"{w}.md", CR, WRITES_WORKTREE, ENDING) for w in WORKERS]
    return (
        *drivers,
        *workers,
        _role("spec-writer", "spec-writer.md", FOLDER, WRITES_NONE, ENDING),
        _role("spec-critic", "spec-critic.md", FOLDER, WRITES_NONE, ENDING),
        _role("board-griller", "griller.md", FOLDER, WRITES_NONE, ()),
        _role("retro-critic", "retro-critic.md", NONE, WRITES_NONE, ENDING),
        _role("demo-explorer", "demo-explorer.md", NONE, WRITES_NONE, ENDING),
        _role("chief-of-staff", "../../chief-of-staff/SKILL.md", NONE, WRITES_NONE, None),
        _role("griller", "../../griller/SKILL.md", NONE, WRITES_NONE, GRILLER_ROWS),
        _role("foreman", "foreman.md", NONE, WRITES_NONE, None),
    )


def names() -> list[str]:
    return [r.name for r in roles()]
