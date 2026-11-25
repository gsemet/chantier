# A watcher's notification or end

Read its output, each line handled the same way.
- `forge saw merged ... order merged <cr>`, also at the next `status`: check the forge first (`gh pr view <pr> --json state,baseRefName,mergedAt`, `glab mr view <iid>`): merged into the default branch, or for `landed with` its base's PR merged there. Then `order merged <cr>` with no word from the user (Foreman mode: send its line to the Foreman); `already merged` is harmless. Not confirmed: record nothing, tell the user what the forge shows. `not landed`: tell where the PR went, record nothing. In Foreman mode with `foreman watch: running`, merge, red-CI and met-wait lines are the Foreman's: tell the user, record nothing, send nothing; a Foreman's `unconfirmed <cr> <pr>: ...` is checked on the forge by you.
- `forge saw checks red`: tell the user (CR, PR, head), record nothing; with `foreman watch: not running`, send the Foreman `checks red <cr> <pr> at <head7>`.
- `config changed on the board: batch.slots <old> -> <new>`: tell the user, offer `order slots --note <new>` for the running batch, send nothing before their word. A `specifying.parallel` or role-key line: one line, no action.
- `tracker saw ...`: one line, record nothing. `surface pull brought` / `another session wrote`: one line naming folder and stage; the CR is not claimed, moved or grilled.
- Then one message with what was recorded and told; when the watcher ended, start it again from its last line.
