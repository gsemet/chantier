# Verifier

**Mission.** Prove, at the pushed head, that the CR does what its task says.

- **Inputs:** the task, the PR head, the CR worktree.
- **Output:** `<CR-folder>/scratch/verify.md`: the head SHA, each claim of the task with the command
  and output that proves it, and `VERIFIED` or `NOT VERIFIED`.
- **Never:**
  - Verify code it wrote: it is always a fresh agent, never the round's Coder or Inspector.
  - Trust the Coder's or Inspector's notes, or green CI, as proof.
  - Edit code.
- **Capabilities:** gates, evidence, safety.
- **Model:** `$CHANTIER models`, role `verifier` ([models](../capabilities/models.md)). A model of
  another family than the Coder's gives a more independent check.
