# A lost Driver

For every kind (CR, release, stack, QA order), and in direct mode.
- Waiting on its own background work, its CR `working`: not ended. Claude Code says `Agent "<name>" is waiting on its own background work`: send no message, no ping, no `agents set -`. It wakes itself, and the `activity` line covers it (`gate running`, `gate queued`, an age). Only `Agent "<name>" finished`, or a host refusal, is an end.
- An ended Driver that wakes again (its hand-back already in the record, no message from you since): its hand-back line a second time, a line answering nothing you sent, or the waiting notice with no `gate running` or `gate queued` for it. With a gate running, leave it. Else act on no line: stop it by the host's means, `note <cr> "stopped: leftover background work after its hand-back"`, `agents set <cr> - --epoch <n>`, in one turn. A Driver still recorded on a `blocked` CR that answers your note is not concerned.
- Suspect: no activity, no `gate running`, no `gate queued` for a full heartbeat interval (55 minutes by default; the project's `AGENTS.md` ranks above). `not measured` and `no Driver recorded` are no activity.

- The proof of a death, and a Driver that ended with no hand-back: `help lost-silent`; a restart: `help lost-restart`.
