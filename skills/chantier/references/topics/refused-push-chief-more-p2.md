# A refused force push, the user's part (part 2 of 2)

- On the yes: run it once, unchanged. Accepted: `pushed <branch>`. Refused again: record it, show the user the exact text and the command so they can run or allow it, answer `push refused <branch>: <exact text>`; never a second try, another form, or a change to the permission settings. On the no: answer with their reason.
- The Foreman's `pushed <branch>` answers nothing (a report line); its `push failed <branch> <text>` is told to the user at once.
