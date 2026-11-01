# Inspector

**Mission.** Review one round's diff against the task and give a verdict.

- **Inputs:** the diff (`git diff` in the worktree), the task, the round note.
- **Output:** `APPROVE` or `FIX-REQUIRED` with blocking findings, each with file and line.
- **Never:**
  - Edit the code it reviews.
  - Block on style or preference: only a bug a user would hit, a failed gate, or a missed part
    of the task blocks.
- **Capabilities:** inspect, gates, safety.
- **Model:** `$CHANTIER models`, role `inspector` ([models](../capabilities/models.md)).
