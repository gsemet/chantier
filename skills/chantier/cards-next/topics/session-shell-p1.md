# Driver and steering shells (part 1 of 2)

The shell calls of a Driver, a steering session, a Griller and a specification or retro agent. Write `$CHANTIER` out in full in each call, never in a shell variable.

- No `sleep`, no polling loop (`until grep …; do sleep …; done` is one). A wait is the forge's own watch or the gate, in a background task. Two bounded waits, each once: before a second CI look (`help ci-no-check`), and, after GitHub answers a merge `pending`, one `sleep` of at most 30 s then one read.
- A background task is a background shell or a host monitor (it streams a command's output to its owner). Stop yours by its id (`$CHANTIER host stop-own-background-task`) once its result is read or no longer counts; a `$CHANTIER gate` shell is the gate, stopped only with `gate <cr> --stop`. The board and the watcher have their own rules (`help board`, `help watcher`).
