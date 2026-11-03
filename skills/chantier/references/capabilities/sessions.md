# Capability: sessions

## Purpose

Start, detach, find and talk to the Foreman's session: Claude Desktop, or a Copilot SDK host.

## Who uses it

Chief of Staff (start, detach, ping); Foreman (reply to the Chief of Staff).

## Commands

Start, in the turn where the user asked, after preflight and `$CHANTIER open`:

```json
{"initiation": "user_asked", "title": "Foreman <batch> (<project>)", "name": "foreman-<batch>",
 "context": "fresh", "use_worktree": false, "model": "<the id `$CHANTIER models get foreman` prints, or omit>",
 "effort": "<the level `$CHANTIER models get foreman` prints, or omit>", "permission_mode": "<the user's current mode, stated>",
 "prompt": "/chantier foreman <batch> --chief-of-staff <your session id> --epoch <n>\nskill: <absolute skill folder>\nchanges: <absolute changes root>",
 "background": "<content of the batch brief>"}
```

The Foreman passes `--changes-dir "<changes>"` before every CLI subcommand and copies both paths
into every worker spawn. Do not rely on an export surviving separate shell calls. Use the actual
changes root, including the default `<project-root>/.agents/changes`, not a relative path.

The epoch is the current one plus one (`$CHANTIER foreman get`; `1` for a new batch). Then, in the
same turn: `$CHANTIER foreman set <returned id>` (it must print that epoch) and
`detach_session(<returned id>)`; check the result says `detached`.
Find your own session id with `get_session("self")`.

Messages: `SendMessage` with `to` set to the session id. Ask for one idle notice with
`notify_when_idle: true` only when you must know the Foreman finished a turn.

### Copilot SDK host

The host has `create_session`, `send_message` and `get_session_context`, and none of `start_session`
or `detach_session`.

1. `create_session` with `model` = the id `$CHANTIER models get foreman` prints, `workspace` = this
   repository, `worktree: false`, `title: Foreman <batch>`, and
   `prompt: /chantier foreman <batch> --chief-of-staff <your session link> --epoch <n>`,
   followed by the same `skill:` and `changes:` lines. Pass nothing else:
   `create_session` takes no agent and no effort, so the Foreman runs at the session's effort
   (the accepted exception `$CHANTIER models audit` reports as a NOTE).
2. `$CHANTIER foreman set <returned chat id>`. The Foreman records its own runtime uuid
   (`$COPILOT_AGENT_SESSION_ID`, not the chat id) with `$CHANTIER foreman transcript`.
3. On `[foreman→chief-of-staff] ready <batch>`: `send_message` to the Foreman chat
   `/every <heartbeat> chantier heartbeat <batch> epoch <n>` (the `heartbeat:` value of
   `$CHANTIER models get foreman`). It is a host command: no model turn, no cost.
4. `$CHANTIER models audit`: it must list that schedule; MISSING or MISMATCH is a stop.
5. On `[foreman→chief-of-staff] final …`: no tool can delete the schedule (only the host's `/every` dialog,
   key `x`). Tell the user, in that turn: "Open the Foreman chat, type `/every`, delete
   `chantier heartbeat <batch> epoch <n>`." Until then each wake costs one short Foreman turn.

A nested chat cannot be detached; there is nothing to detach. `/agent foreman` cannot be
selected from here (the host deselects it): never rely on it. In the Copilot CLI, the user starts
the Foreman with `copilot --agent foreman` instead.

## Rules

- Never start a session from a turn the user did not start (peer message, schedule, note): the
  app refuses it, and so do you.
- Detach at once (Claude Desktop): a linked Foreman wakes the Chief of Staff after every turn ($0.03–0.05 each).
- A message to a busy session waits until its turn ends: 15–54 s measured. Keep turns short.
- The Foreman cannot start sessions. Its team is subagents.

## Failure handling

- `start_session` or `create_session` refused: report the app's text to the user; do not retry with other settings.
- `detach_session` fails: stop the Foreman (`stop_session`), tell the user with the app's text,
  and start nothing else.
- The Foreman is not listed or does not answer a ping in about two minutes: read
  [recovery](recovery.md).
