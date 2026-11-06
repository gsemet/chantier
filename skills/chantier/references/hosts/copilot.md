# Copilot (SDK host)

What is proper to this host: the tools, the heartbeat, the sessions. The cards say what a role
judges and point here. Read it with your card when you run on Copilot.

The lines below moved from the cards as they were, unchanged in substance. Copilot's marks:
nothing here was re-tried when they moved, so each line is **unproved** as to date and place
unless it says otherwise; no new Copilot finding. Never tell the user an unproved behaviour as a
fact.

## Tools

| Generic | Copilot |
| --- | --- |
| Start the Foreman's session | `create_session` with `model: "claude-opus-5.5"`, `workspace` = the repository, `worktree: false`, `title: Foreman [<batch>]` |
| Own session id | `$COPILOT_AGENT_SESSION_ID` (also the transcript's id) |
| Start a Driver or a worker | `task`, `mode: background`, `agent_type: <agent>`; the plugin's agent is `chantier-<role>`; no model, no effort |
| Message a Driver | `write_agent` to the agent id |
| Message the Chief of Staff | `send_message` to its session link |
| A Driver's hand-back to the Foreman | the Driver's final answer |
| Stop a Driver | `write_agent` `[foreman→driver <cr>] stop` |
| Agent ids of the project | a file in `.github/agents/` or `~/.copilot/agents/` |
| Preflight P2 | `create_session` and `send_message` load |

## Heartbeat

The Chief of Staff arms it: on the Foreman's `ready <batch>`, it sends the Foreman chat `/every
4m chantier status --refresh --batch <batch> --epoch <n>`. The Foreman cannot end `/every`. At
landing the Chief of Staff tells the user to delete the `/every` in the Foreman chat. The Foreman
also ends its heartbeat when every Driver has ended for 30 minutes (nothing can move): the Chief
of Staff then tells the user to delete the `/every`, and arms it again with the next order it
sends the Foreman.

## Compacting

Name no compacting command or setting to the user.

## Sessions

The Foreman is started by `create_session`. A refused start is reported with its exact text.
Nothing else is recorded here about Copilot's sessions.
