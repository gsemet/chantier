"""The forge hub and `chantier watch`.

The forge hub is the surface server (`chantier serve`, `loop.py`), one per planning surface (or
repository) and machine: it holds the OS file lock in the git folder (`chantier/hub.lock`), which
no other process takes, and it is the only process that reads the forge (`state.py` holds
`server.json`, which names the server and its hub). While a client observes it, it reads the forge,
for every project of the surface, at most once every 20 s, and appends the events it finds to each
project's `forge-journal.jsonl`.

Each watcher (`watch.py`) is a client of that server: it subscribes to the `events` topic of its
project from its cursor (`feed.py`) and reads no journal file and no forge. With no server running
it starts one, detached, when the project's seat is this session's, else it ends and says why. It
reads the lines for it (see `journal.py`: every line is addressed), and ends 20 s after the last
new event for it that wakes, and no sooner than `events.wake_every` after its start, which wakes
its session; or 2 h after its start with no such event; or when the project's seat is another
session's. It runs with or without a batch. Each watcher holds a lock of its own per project and
session (`chantier/watch-<project>/<session>.lock`, `lock.py`); `status`, `open`, `take`, `order`
and the switch to direct mode read it to print the `watch: not running` line (`autostart.py`) when
no watcher of the session runs.

The one test seam: the environment variable `CHANTIER_HUB_TEST_TIMES`, read only by `times.py`,
as `<cycle>:<quiet>[:<idle_end>]` in seconds (for example `0.5:3` or `0.5:3:10`), shortens the
20 s cycle, the 20 s quiet and the watcher's 2 h idle end for the scenario. There is no
command-line option for them."""
