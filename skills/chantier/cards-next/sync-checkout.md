# Sync the checkout

Read by the session that syncs, in the dev mode only (the skill's launcher paragraph). A sync runs
at the session's start, at a batch's start and after a merge that changes `uv.lock`. In the plugin
mode nothing syncs.

Run the launcher with `--sync` as its first argument, before any `--project` (the skill gives the
line); it prints one line:

1. `in sync`: `uv sync --locked --check` exited 0; nothing to do.
2. `synced`: the check said "The environment is outdated", no process held `<plugin root>/.venv`,
   and `uv sync --locked` ran.
3. `sync pending: held by <holders>`: a gate, watcher, board or hub (of any project, this session's
   own included) holds the environment, or the sync failed with os error 32 (`an unlisted
   process`). Stop or kill nothing and ask no one to: go on unsynced and try again at each next
   turn but a reload. Judge a sync by this line, never by `$CHANTIER status` (this surface's
   batch only).
4. Any other failure (a stale `uv.lock`, a missing `uv`, exit 127): an ordinary failure, never
   `sync pending`; at a session's start a stop, else one line with uv's text and you go on.

Pending 3 minutes after the first try: `help sync-offer`.
