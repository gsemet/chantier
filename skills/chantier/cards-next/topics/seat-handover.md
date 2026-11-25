# Handing the seat over

Rules only; the models judge the rest.
- The seat moves only on the user's word, and only on the new session's explicit acknowledgement.
- A running Driver is never stopped nor moved. On the user's agreement the old Chief of Staff finishes the running work itself or through its Foreman: it starts no new Driver (`order slots --note 0` while CRs are queued). Once every Driver has finished (a PR may still be open) it sends `[chief-of-staff→chief-of-staff] your turn, you are the Chief of Staff`.
- The new one answers `I have the batch`, then `$CHANTIER seat take <own id> --over <old id> ...`. A direct batch: it claims the next number (`help direct-mode-epoch`) and gives the slots back if a hold was set. A Foreman batch: it sends the Foreman `chief-of-staff <own session id>`.
- The old one becomes a Griller (or ends) and renames itself. Its board stops when the seat moves (or 30 minutes after its last client); the new one's watcher, from the line of its `seat take` on its yes, registers on a board still running or starts one (a hand-started board joins). The old watcher ends once the new session takes the seat; the new one starts its own from that line or `status` (another session's does not count).
- With no batch active the hand-over is the seat alone: `seat take --over` on the user's word.
