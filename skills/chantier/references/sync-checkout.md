# Sync the checkout

Read before the first sync of a dev-mode session, by the session that syncs (the `SKILL.md` launch paragraph says who; `$CHANTIER`'s mode is set there). A sync runs at the session's start, at a batch's start and after a merge that changes `uv.lock`. Four steps:

1. Check, writing nothing: run `uv sync --locked --check --project "<plugin root>"` (the command inside the rule P10 prints for it) and read its exit: 0 is in sync, nothing to sync, stop here; 1 with uv's text "The environment is outdated" goes to step 2; any other exit is an ordinary sync failure, handled as below, never `sync pending` (a stale `uv.lock` also gives 1 with that text, and the real sync of step 3 then fails with its lock error, handled the same way).

2. Name the holders before syncing, on every system: list the processes that hold `<plugin root>/.venv` by the host's means (`$CHANTIER host name-env-holders`).

3. With none, run `uv sync --locked --project "<plugin root>"`.

4. With any holder (a gate, a watcher, the board or hub, of any project or surface, this session's own included), or when the sync fails with os error 32 (a holder the listing missed, or one that started in between), never stop or kill a process and ask no one to: go on unsynced, saying `sync pending: held by <holders>` (each holder as `PID <n> <subcommand> <project>`, a server `$CHANTIER webui` started (`serve --stop-idle`, no `--seat`) as `PID <n> serve <project> (started by webui)`, or `an unlisted process` when the listing found none), and try again from step 1 at each next turn but a reload (`help reload`: a reload runs no `uv sync`).

Pending 3 minutes after the first try: `help sync-offer`. An ordinary sync failure is, at the session's start, a stop (floor 4); at a batch's start or after a merge, one line to the user with uv's text, and you go on.
