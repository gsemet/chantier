"""The plugin's agent files by role: a wrapper's first line and its contract lines. Apart from
`plugin_files`, which holds the folder reads, to keep that file small."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chantier.plugin_files import _agent_files, contract_lines, recorded_escalation


def agent_file(host: str, role: str) -> Path | None:
    """The plugin's agent file of `role` on this host; None for a role with none."""
    wanted = f"chantier-{role}.agent.md" if host == "copilot" else f"{role}.md"
    return next((p for p in _agent_files(host)[1] if p.name == wanted), None)


FIRST_LINE = re.compile(r"Prompt starts with: `(chantier [a-z-]+ for [^`]*)`")


def first_line_template(host: str, role: str) -> str | None:
    """The first line of `role`'s agent on this host, its `<…>` unfilled (the wrapper's
    `Prompt starts with:` text); None for a role with no agent file."""
    path = agent_file(host, role)
    found = FIRST_LINE.search(path.read_text(encoding="utf-8")) if path else None
    return found[1] if found else None


def role_contract_lines(host: str, role: str, record: Any) -> list[str]:
    """The contract lines of one role (`contract_lines`) for the batch `record`'s playbook and
    escalation: its agent's body when the configuration starts it as a generic agent."""
    path = agent_file(host, role)
    if path is None:
        return []
    return contract_lines(
        role, path.read_text(encoding="utf-8"), record.playbook, recorded_escalation(record)
    )
