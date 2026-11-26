# A watcher's notification or end (part 2 of 2)

- `config changed on the board: batch.slots <old> -> <new>`: tell the user, offer `order slots --note <new>` for the running batch, send nothing before their word. A `specifying.parallel` or role-key line: one line of a few words, no tool call, no action.
- `tracker saw ...`: one line to the user, no tool call, record nothing. `surface pull brought` / `another session wrote`: one line naming folder and stage; the CR is not claimed, moved or grilled.
- What it tells: the project's forge events, board writes, tracker and pull lines and this session's, 20 s after the last new one that wakes and at most every `events.wake_every` after its start or last telling. Streaming (`--stream`): it prints them, closes with `watch: <name> told up to cursor <n>; still watching` and runs on; plain: it ends there.
- It ends 2 h after the latest of its start, its last waking event and the last moment a batch was in flight (one running, or paused with a PR neither merged nor cancelled), only with none in flight.
- Then one message, in the report format, of what was recorded and told; start an ended watcher again from its last line.
