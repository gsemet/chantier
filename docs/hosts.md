# Supported hosts

The hosts Foreman and direct mode run on, the forges, and Windows.

For Foreman mode:

| Host | Nested session | Foreman heartbeat |
| --- | --- | --- |
| Claude Desktop | `start_session`, left linked | the configured steering wake (55 minutes by default) |
| Copilot SDK host | `create_session` + `send_message` | the configured steering wake (4 minutes by default, `/every`) |

The heartbeat stops on the first wake that sees no Driver run for 30 minutes or more, whatever the
wake's interval. On Claude Code the Foreman also runs a watcher of its own, which wakes it on a merge, a red CI or a met wait, so the wake is the safety net. The settings are `hosts.<host>.timing` ([your agents and models](agents-and-models.md)).

Foreman mode refuses every other host (a VS Code tab, the terminal, ...): with no argument the
batches are direct mode there, and a forced `foreman` is refused with the reason. An unattended run and a linked worktree are refused in both modes, with no
fallback.

Direct mode runs on any Claude Code entry point (the Desktop app, the terminal, VS Code, a
Remote Control session) and in a Copilot agent session, checked by `chantier preflight --direct`.
With no argument it is the mode under Remote Control and on a host that cannot start a Foreman;
a forced `foreman` under Remote Control starts the Foreman in the Chief of Staff's folder;
`direct` forces it anywhere. The heartbeat is the same, run in the Chief of Staff's own
session: `chantier status` prints "heartbeat N min" (since its last wake) or "heartbeat stopped"
(a loop ended on purpose).

On Copilot, chantier runs in the Copilot App (on the Copilot SDK, like Claude Desktop: the
table's "Copilot SDK host", Foreman and direct mode) and in the Copilot CLI, in direct mode (a
Copilot agent session in the terminal; the user's statement of 2026-11-16, unproved until a run).
VS Code's local harness is not supported (it does not use the Copilot CLI or SDK); the Copilot
harness in VS Code, arriving, uses them (unproved until a run).

On Copilot, until `copilot-close-end-event` lands, `close` tells that a Driver, the stack driver or a
QA driver still runs by its live lease (10 minutes, renewed by its commands), and the Foreman by a
heartbeat younger than 10 minutes; it no longer sees a Driver's leftover background work after its
hand-back. On Claude Code it reads the transcripts, the lease only shown beside them.

**Recommended on Claude Desktop:** turn on "Connect new sessions to Remote Control" in the app's
settings, so the Foreman's session can be reached from your phone. A host classifier may refuse
the Foreman an action (starting a Release driver, say) until you allow it in that session: type
one line there saying so, from your phone if you are away, and it does that action once, except a
Driver's force push, which goes to the Chief of Staff, not to you.

| Forge | CLI | Connector | Where |
| --- | --- | --- | --- |
| GitHub | `gh` | `github` | github.com, or GitHub Enterprise when `gh` is logged in to its host |
| GitLab | `glab` | `gitlab` | gitlab.com, or a self-managed server `glab` is logged in to |

chantier's own reads of a forge (the forge hub, the PRs page) go through a connector, read-only
([forge connectors](forge-connectors.md)); a link of another forge is named in the hub's error and
on the PRs page, never read; issues of any tracker come from an outside poller
([forge connectors](forge-connectors.md#writing-an-outside-poller)).

The agents use the forge's CLI as it is logged in (`gh auth login`, `glab auth login --hostname
<host>`), on the batch's git remote (`origin`, or `--remote`). Nothing is configured in chantier.

On Windows, the CLI runs natively (no WSL). `chantier gate` runs the long gate in `cmd.exe`, so
write it for it. `chantier cancel` ends a CR's processes at once, with no grace period, and
finds stray ones by their command line only, since Windows does not expose another process's
current directory.
