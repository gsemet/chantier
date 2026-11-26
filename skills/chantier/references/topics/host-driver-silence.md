# Claude Code: a Driver's silence

Between its start and its final report a Driver sends nothing to a Claude Desktop steering
session. Silence is no sign of a lost Driver, however long, and no reason to start another.

- Read a Driver's life from two things only: the `activity` line of `$CHANTIER status --refresh`
  (an age, `gate running`, `gate queued`) and the host's notices (`help host-subagent-signs`).
  `Agent "<name>" is waiting on its own background work` is not an end.
- An `anomaly` comes as a note on the CR (`$CHANTIER status --notes`) and again in the final
  report; handle it when the report arrives.
- The `ping`: no `pong` can come. A `ping` to a suspect still goes (it wakes a waiting Driver). At
  the next wake the proof of life is that unit's `activity` age younger than the ping; an older
  age with no `gate running` or `gate queued` is the missing `pong` of the proof of death
  (`help lost-silent`). **Unproved**.
- A second Driver for a unit (a CR, the stack, a QA order) starts only by the restart path
  (`help lost-restart`), after a proof of death or the first one's final report: never on silence
  alone. For the stack, `agents set stack -` only once its report arrived or a proof of death
  holds.
