# Restart the board

On `board runs another build`, `board runs a build of chantier <v> older than this notice`, `board is chantier <v>: restart it to run this version`, or after a merge that changes the board's code (`board/`, `hub/`, `writer/`, `clients/web/`) in the dev mode, offer the restart once, in one line with its cost: the board, the writer and the hub are off for every project of the surface for up to two minutes, and a board Griller run in progress ends.
- On the user's yes, each time (a yes covers one restart): `$CHANTIER serve --restart --seat <id>` (with `--forge-always` on a host that cannot run the watcher) in the background by the host row; read its first lines and pass them on.
- A refusal: one line with the printed stop command, never run by you. No answer or a no: say nothing more until the next such line.
- With `sync pending`, the sync goes first (`help sync`).
- A dev-mode board of another build is replaced by `serve --restart` on the user's yes; other projects' watchers start no board while a dev session holds the seat.
- "A new key", "the link leaked": on the user's word `$CHANTIER serve --seat <id> --new-key`; both keys change, old links and pages stop; give the new links.
