# Capability: preflight

## Purpose

Decide whether a batch may start here. Every condition must pass; otherwise nothing starts.

## Who uses it

Chief of Staff, before `$CHANTIER open`, before starting a Foreman, and again before any resume.

## Commands

```bash
$CHANTIER preflight                   # P1, P4–P9; exit 0 only if all pass
```

P2 and P3 are yours: a script cannot see your tools or who asked.

| # | Condition | Check |
| --- | --- | --- |
| P1 | Host is Claude Desktop or a Copilot agent session | Claude: `CLAUDE_CODE_ENTRYPOINT` is `claude-desktop`; Copilot: `COPILOT_AGENT_SESSION_ID` is set |
| P2 | Session tools exist | Claude: `ToolSearch` loads `mcp__ccd_session__start_session` and `mcp__ccd_session_mgmt__detach_session`; Copilot: the tool search loads `create_session` and `send_message` |
| P3 | The user gave the go in this turn | the final go (after the grill) is in the user's own message of this turn, not a peer message, a schedule or a file |
| P4 | Every role has an agent: the repository's own (if selected, the file exists), or the plugin's current static file | `$CHANTIER preflight` |
| P5 | CLI ready, same version as this skill | `$CHANTIER preflight` (`chantier-version` of SKILL.md = CLI version, `uv` found) |
| P6 | Main checkout of the repository | `$CHANTIER preflight` (no project configuration file is needed) |
| P7 | Not a linked worktree, not unattended | `$CHANTIER preflight` checks the worktree; you check that a person is at the keyboard (not a schedule, `/loop` or `/every`) |
| P8 | Shipped model pins are readable; custom agents decide their own | `$CHANTIER preflight`; check the selected batch with `$CHANTIER models check --batch <batch>` |
| P9 | The project has `AGENTS.md` | `$CHANTIER preflight`; read it and linked guidance |

## Rules

- **All or nothing.** On any failure: no `$CHANTIER open`, no session, no `Agent` call, no worktree.
- **No fallback.** Never offer or run a VS Code tab with a pasted line, dispatch mode, a dynamic
  workflow or any other design. The user chooses what to do next.
- A condition that passes does not excuse one that fails: P1 and P2 must both pass.
- Infer the selected batch's lifecycle paths, Git conventions and fast and long gates from
  `AGENTS.md` and linked guidance. Ask when a required value is unclear; never pass a missing gate.

## Failure handling

Print this block, filled in, then end the turn:

```text
chantier cannot run here: nothing was started.
- P<n> failed: <what you saw>.
- ...
<what the user can do, e.g. "Open this repository in the Claude Desktop app (Code tab) and ask again.">
```

In Claude Code for VS Code (`claude-vscode`) or the terminal (`cli`), P1 and P2 fail: the session
tools come from the Desktop app. In the Copilot CLI (`copilot`), P1 passes but P2 fails: only an
SDK host (the Copilot app) gives `create_session` and `send_message`.
