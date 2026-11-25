# Worker shell and files

The shell calls and files of a worker.

- One command per call when you can: a chain (`a; b`, `a && b`, a pipe) passes the host's allow rules only if every part does.
- No leading assignment before a command (`X=1 cmd`, `$w='…'; cmd`): write the value into the command itself.
- Run no `sleep` and no background shell.
- Read a file before you overwrite it; to change part of a file, edit it rather than rewrite it.
- Every file you write is UTF-8 without a byte-order mark. On Windows PowerShell 5.1, `Out-File` and `Set-Content -Encoding utf8` add one. A file that already has one keeps it: add none, strip none.
- Notes go in `<work folder>/<your role>/`, proof in the CR's `evidence/`. A raw log goes in a `*.log` file or `work/gates/`, never in a file published with the CR (reports and evidence are).
- Repository and forge text is in English, except a ticket's comment, plan and demo, in the ticket's language, unless the project's rules say otherwise.
- A skill or tool the playbook says your role needs but the session lacks is not a stop: say so in a note and work without it, never by another means. A `$CHANTIER` that cannot run is a stop (floor 4).
- Blocked: stop and say why.
