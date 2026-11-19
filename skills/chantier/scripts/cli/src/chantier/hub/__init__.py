"""The forge hub and `chantier watch`.

One process holds the OS file lock in the git folder (`chantier/hub.lock`) per planning surface
(or repository) and machine: the hub, the only process that reads the forge. It is the surface
server (`chantier board`, `loop.py`) while one runs, else the one watcher that wins the lock, and
that watcher yields it when a server starts (`state.py` holds `server.json`, which names both).
The hub reads the forge, for every project of the surface, at most once every 20 s, and appends the
events it finds to each project's `forge-journal.jsonl`. Each watcher reads only its project's
journal (the hub's lines and the board's writes) and reads the lines for it (see `journal.py`:
every line is addressed), and ends 20 s after the last new event for it that wakes, and no sooner
than `events.wake_every` after its start, which wakes its session, or when the project's seat is
another session's. It runs with or
without a batch. Each watcher also holds
a lock of its own per project and session (`chantier/watch-<project>/<session>.lock`, `lock.py`);
`status`, `open`, `take`, `order` and the switch to direct mode read it to print the
`watch: not running` line (`autostart.py`) when no watcher of the session runs.

The one test seam: the environment variable `CHANTIER_HUB_TEST_TIMES`, read only by `times.py`,
as `<cycle>:<quiet>` in seconds (for example `0.5:3`), shortens the 20 s cycle and the 20 s quiet
for the scenario. There is no command-line option for them."""
