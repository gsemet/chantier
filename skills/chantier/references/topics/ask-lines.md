# Asks: the lines

`$CHANTIER asks "<text>"` records what the Chief of Staff must hear and prints the line to send:
send it (a lost line loses nothing). `judge` words a CR's ready asks, and `next` and `conflicts`
print theirs; word these in plain words, a CR named by its number and slug:

- `merged <cr> <link>`, `released <cr> <link>`;
- `blocked <cr> <reason>`, `question <cr> <text>`, `budget <text>`;
- `refused <cr> <text>`: first record `$CHANTIER note <cr> "refused: <the exact command> -> <the
  host's exact text>"`; but a refusal of your push of a Driver's refused force push is the `push`
  line (`help refused-push`).

A hand-back or note saying an image with the username or home folder was uploaded and replaced, or the user's screenshot was not uploaded, goes with that CR's ask.

`question` and `blocked` asks are never superseded; ready asks are (`help ready-asks`). Others:
`stack-ready-to-merge` (`help stack-asks`), `heavy-ci` (`help stack-drop`), `conflict`
(`help conflict-check`).
