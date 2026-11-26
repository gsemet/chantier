# A worker's prompt, phases and reply

- `$CHANTIER phase <cr> <phase> [detail]` before each step, one call alone: `investigator`, `inspector`, `review <name>`, `rebase`, `gate <name>`, `pr`, `ci`, `verifier`, `debugger`, `conflict-resolver`. `round` records `coder`; `take` and `handback` clear it. A stack or QA driver records none.
- `$CHANTIER note <cr> "<one sentence>"` after each step worth knowing; `note <cr> --draft <path>` for a file the user reviews in place.
- Your own `writes:` is your CR folder (plus the archive path when `take` printed one): your notes, `pr-body.md`, large outputs, the archive, nothing else. A raw log goes in `work/gates/` or a `*.log`, never in a published file. A CI artifact goes under `<CR folder>/work/scratch/artifacts-<run id>/`; copy only the small proof into `evidence/`; a brief that asks a worker to read it names that folder.
- Check each reply against its card's format before acting: Inspector and review steps, the JSON object alone, `verdict` exactly `APPROVE` or `FIX-REQUIRED`, `head` a SHA; Coder, Investigator, Debugger, their output file exists (`r<n>.md`, `investigation.md`, `diagnosis.md`) with each gate's command and result, a Coder's `Notes:` line naming the `r<n>.md`; Conflict resolver, `help conflicts`; Verifier, `help cr-ship`. Failures: `help trouble`.
- The record and a round: `help cr-workers`, `help cr-rounds`.
