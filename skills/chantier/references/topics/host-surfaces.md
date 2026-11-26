# Claude Code: where the user is, and the options that fit

Surfaces: the phone on Remote Control; the desktop app, typed; a terminal. The
desktop app adds a Remote Control notice to the conversation when the user works through Remote
Control (seen). A terminal gives no signal, and no notice does not prove the user is at the
machine: offer every option that fits, each with its condition. The notice also brings the offer to fork and a
no-argument batch's mode: direct. Whether it appears on a desktop-typed turn of a
Remote Control session is **unproved**. The rest is **unproved** unless marked seen.

| Option | Desktop | Remote Control | Terminal |
| --- | --- | --- | --- |
| Switch to Foreman mode | yes | yes: new, or reused (seen) | no: P1 fails |
| Switch to direct mode | yes | yes, but not stopping a Foreman that does not answer | yes |
| Run a command in a terminal | yes | no shell | yes |
| Open `localhost` or a file path | yes | no: send a link | yes |
| `/permissions`, `/config` | the app's settings | no | yes |
| Restart, `/reload-plugins`, an editor | yes | no | restart the CLI |
| `/chantier-board` | yes | the pane does not show | yes |
| The remote board (`chantier serve`) | yes | from the local network once `board.host: network` (or `--host`) | yes |
| Review and merge a PR | yes | yes | yes |
| A host feature (wake, start a session) | where it exists | `start_session` with no `cwd` or `preset` works; with either, refused (seen) | where it exists |

[Trials](../../../../docs/proofs/claude-code.md#other-surfaces-and-options)
