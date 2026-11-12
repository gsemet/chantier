# Supported hosts

The hosts Foreman and direct mode run on, the forges, and Windows.

For Foreman mode:

| Host | Nested session | Foreman heartbeat |
| --- | --- | --- |
| Claude Desktop | `start_session`, left linked | 30 minutes |
| Copilot SDK host | `create_session` + `send_message` | 4 minutes (`/every`) |

Foreman mode refuses every other host (a VS Code tab, the terminal, ...): with no argument the
batches are direct mode there, and a forced `foreman` is refused with the reason. An unattended run and a linked worktree are refused in both modes, with no
fallback.

Direct mode runs on any Claude Code entry point (the Desktop app, the terminal, VS Code, a
Remote Control session) and in a Copilot agent session, checked by `chantier preflight --direct`.
With no argument it is the mode under Remote Control and on a host that cannot start a Foreman;
`direct` forces it anywhere. The heartbeat is the same, run in the Chief of Staff's own
session: `chantier status` prints "heartbeat N min" (since its last wake) or "heartbeat stopped"
(a loop ended on purpose).

**Recommended on Claude Desktop:** turn on "Connect new sessions to Remote Control" in the app's
settings, so the Foreman's session can be reached from your phone. A host classifier may refuse
the Foreman an action (starting a Release driver, say) until you allow it in that session: type
one line there saying so, from your phone if you are away, and it does that action once.

| Forge | CLI | Where |
| --- | --- | --- |
| GitHub | `gh` | github.com, or GitHub Enterprise when `gh` is logged in to its host |
| GitLab | `glab` | gitlab.com, or a self-managed server when `glab` is logged in to its host |

The agents use the forge's CLI as it is logged in (`gh auth login`, `glab auth login --hostname
<host>`), on the batch's git remote (`origin`, or `--remote`). Nothing is configured in chantier.

On Windows, the CLI runs natively (no WSL). `chantier gate` runs the long gate in `cmd.exe`, so
write it for it. `chantier cancel` ends a CR's processes at once, with no grace period, and
finds stray ones by their command line only, since Windows does not expose another process's
current directory.
