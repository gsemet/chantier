# Leases, from the steering side

A Driver's lease on its CR runs out when the Driver is gone; `next` names a stale one as an item. Read it before you act: a live Driver renews it with its commands.
- A stale lease on a `working` CR whose Driver the host shows ended: `agents set <cr> - --epoch <n>` (it ends the live lease, so the restart does not wait), then the lost-Driver path (`help lost-driver`).
- `take --reclaim` of a live lease only on the user's word, never on your own judgement.
- When a Driver ends, with its hand-back or without, record `agents set <cr>|O-k|stack - --epoch <n>` before the unit's next `take`.
- A `lease not confirmed since …` mark of `status` is no Driver gone (a Driver waiting for its worker cannot renew): only once the host shows it ended, `take <cr> --reclaim --note "resume: lease not confirmed"` (a QA order: the restart path with `agents set O-k <id> --reclaim`; the stack: `take stack --reclaim`).
- A refusal you do not understand: `access <cr> --epoch <n>` before you ask; it changes nothing.
- A Driver waiting more than 3 minutes on a claim or a lease holds with `lease hold` (45 minutes by default, 90 at most); it runs nothing and keeps the lease live. Do not read a held lease as lost.
- A `--lease` refusal or `claim lost` in a Driver's line is its own to settle with `take --reclaim`'s output; steer nothing around it.
