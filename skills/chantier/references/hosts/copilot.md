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
| Start the Foreman's session | `create_session` with `model: "claude-opus-5.5"`, `workspace` = the repository, `worktree: false`, `title: "<title>"` |
| Set the Foreman's own title, first | when the host offers a way; else the title stays |
| Own session id | `$COPILOT_AGENT_SESSION_ID` (also the transcript's id) |
| Start a Driver or a worker | `task`, `mode: background`, `agent_type: <agent>`; the plugin's agent is `chantier-<role>`; no model, no effort |
| Start the Spec-writer (Chief of Staff) | `task`, `mode: background`, `agent_type: chantier-spec-writer`; no model, no effort |
| Message a Driver | `write_agent` to the agent id |
| Message the Chief of Staff | `send_message` to its session link |
| A Driver's hand-back to its steering session (the Foreman; in direct mode the Chief of Staff) | the Driver's final answer; in direct mode it returns to the Chief of Staff that started the Driver: unproved |
| Stop a Driver | `write_agent` `[foreman→driver <cr>] stop` |
| Agent ids of the project | a file in `.github/agents/` or `~/.copilot/agents/` |
| Preflight P2 | `create_session` and `send_message` load |
| The skills | the same four, same names: `skills/chantier` (the router), `skills/chief-of-staff`, `skills/griller`, `skills/status`, declared in `.github/plugin/plugin.json`; how Copilot passes the argument `direct` is not known (unproved) |
| Set a session's own title (the Chief of Staff, a Griller) | when the host offers a way; else nothing (unproved) |
| List the sessions; is the seat's session alive | not known: the seat's session always "looks stopped" to a new session, and the "looks stopped" line of `session-start.md` is asked (unproved) |
| Message another session of the user (hand-over, a Griller's line) | `send_message` to its link (unproved) |
| A Griller in a worktree | its files sent as for a Griller on Claude Code (unproved) |

## Heartbeat

In direct mode there is no Foreman chat: the Chief of Staff runs the same `/every` in its own session (unproved).
Otherwise the Chief of Staff arms it: on the Foreman's `ready <batch>`, it sends the Foreman chat `/every
4m chantier status --refresh --batch <batch> --epoch <n>`. The Foreman cannot end `/every`. At
the pause the Chief of Staff tells the user to delete the `/every` in the Foreman chat. The Foreman
also ends its heartbeat when every Driver has ended for 30 minutes (nothing can move): the Chief
of Staff then tells the user to delete the `/every`, and arms it again with the next order it
sends the Foreman.

## Configuration

- Prerequisites, the same as Claude Code's for a batch: `git` and `uv` (P5), `gh` or `glab`
  logged in (P9). P10 does not run on Copilot.
- No permission configuration is recorded for Copilot: **unproved**; nothing is recommended
  until a Copilot trial records one.
- The command hygiene of `concepts.md` rule 9 applies on both hosts.

## Compacting

Name no compacting command or setting to the user.

## Sessions

The Foreman is started by `create_session`. A refused start is reported with its exact text.
Nothing else is recorded here about Copilot's sessions.
