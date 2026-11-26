# Steering a batch yourself (part 1 of 3)

In direct mode no Foreman session starts; the CR lifecycle, frame, folders, reports and the user's boundaries are the same. Read the Foreman card and, for a stack, `help stack`, and do what they say of the Foreman, with these differences.
- Leases: `take` is refused while a unit's lease is live (`--reclaim` only on the user's word) or not confirmed (check with the host that it ended, then `take <cr> --reclaim --note "resume: lease not confirmed"`; a QA order `agents set O-k <id> --reclaim`; the stack `take stack --reclaim`); `agents set <cr>|O-k|stack -` after a reported end ends its lease (`help lease`). A refusal you do not understand: `$CHANTIER access <cr> --epoch <n>` before you ask.
- Escalation is yours (`help escalation`; the model is the `escalate:` line of `playbook`), as are the two rounds routes: once per CR, then the user; a CR with no rounds blocked twice goes straight to the user. A restack that fails runs the stack driver's `conflict-resolver` on the escalation model.
- Titles: at `open --direct`, rename yourself `[<code>] 💬 Project · CoS (Batch <nn>)`; after `close --yes`, `[<code>] 💬 Project · CoS` (`help titles`).
