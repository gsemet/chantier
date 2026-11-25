# Where the CR goes

A CR grilled enough goes to the next batch (`3-ready`, the default) or, with a batch open (running or paused), the running batch (`4-batch/1-pending/`), in every mode.
- Asked at every spec-writer start, yours or a Griller's, with `A. Next batch (3-ready) (recommended)` and `B. Running batch <batch-id> (4-batch/1-pending/)`; the answer to "grilled enough?" is that ask. No batch open: nothing asked. A next run keeps the recorded destination. Record at once: `Destination: next batch (3-ready).` or `Destination: running batch batch-<n>.`
- That answer is the user's word for the move, and for the running batch the go. The spec is final when written, no writer runs, its critic (if due) ran and was applied, no question is open. Then: next batch, `triage <folder> --ready`; running batch, `order add --note <folder>` and handle it as usual (Foreman mode: relay to the Foreman; direct: take the CR when a slot frees). A Griller never runs `order`.
- Act on the last `Destination:` line (a board line counts). `Destination: back to the backlog (board)`: no `triage`, no `order`.
- `order add` refused (a release started, or the batch closed): `triage <folder> --ready`, which clears the mark, and one line "<slug> goes to the next batch: <why>". Writer not running: restart the server as the refusal says; the CR waits, marked.
- A `3-ready` CR is never marked. To put one in the running batch: `order add --note <folder>` at once.
