# Capability: batch brief

## Purpose

Turn the user's request into a batch the Foreman can run without asking.

## Who uses it

Chief of Staff.

## Commands

```bash
$CHANTIER open <batch> <item>... [--stack] [--slots N] [--budget USD] [--qa all|1,3] [--chief-of-staff <session>]
# an <item> is a title or @path/to/backlog-item.md
$CHANTIER status --batch <batch>
```

`$CHANTIER open` creates the batch folder, CR folders, worktrees and branches from the fresh default
branch, and a `brief.md` skeleton. Complete it from the grill:

```markdown
# Batch <batch>
- CRs, in order: CR-101 (P1, QA), CR-102 (P1), ...
- Mode: parallel | stack. Slots: 3. Budget: $<n> (stop at 100 %).
- Models (optional; `role=id` or `role@CR-n=id`, exact ids from `chantier models`; empty = agent file default): coder@CR-102=gpt-6.1-sol
- Night policy card: one extra round per CR; a red PR goes to the top; infra re-runs within budget.
- Autonomous decisions: ...
- Questions the Foreman must bring back: ...
```

## Rules

- Agent files must be installed before the Foreman starts (P4); `$CHANTIER setup` installs them.
- **Models** holds exact ids from `$CHANTIER models` only; run `$CHANTIER models check` after writing it.
  On Copilot it may change only the Foreman and roles left on `inherit` (agent files pin the
  others with `model-policy: required`); see [models](models.md).
  A model the user names that is not listed exactly is a question for the user
  ([models](models.md)).
- The brief is the Foreman's whole mission; never send the mission later by message only.

## Failure handling

`$CHANTIER open` exits 2 (dirty default branch, missing item, no slot): fix with the user, then retry.
