# Another machine and the board's link

- "Board on my phone", "where is the board?": `$CHANTIER webui` prints the link and starts the server when none runs. It holds the private key, for the user only; the `read-only:` link can be shared. Its PRs page is the live view of the batch's PRs. To reach it from another device on the local network, on the user's word, `board.host: network` in `chantier.yaml` (or `--host` for one start), then the board started again (`help board-restart`). A page that lost its cookie asks for the link: the user pastes it.
- "Run chantier from another machine", "log in to the board": on the other machine `chantier login <private link> [--project <id>]`; every command for that project there then runs on this server (other projects stay local). The server must listen on the local network. `--profile local` or `chantier logout` runs locally again.
- A Chief of Staff working through a profile has no watcher: it reads `status` at each turn.
