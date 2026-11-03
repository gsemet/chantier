# Capability: steering

## Purpose

Carry the user's orders to the running batch, one message per order.

## Who uses it

Chief of Staff.

## Commands

```bash
$CHANTIER order add --note "@<prepared-folder-or-spec>" # a selected, grilled CR
$CHANTIER order drop CR-104
$CHANTIER order first CR-103
$CHANTIER order change CR-102 --note "<one-line change>"
$CHANTIER order merged CR-101                 # the user merged its PR
$CHANTIER order pause | resume
```

Each prints one line, `[chief-of-staff→foreman] order O-<k> …`: send exactly that line to the Foreman with
`SendMessage`. `ping` and `answer <cr> <text>` need no order.

Read progress with `$CHANTIER status`, never by reading the Foreman's transcript or files.

## Rules

- One message per order; the Foreman confirms each with `ok O-<k>`. A repeated order is
  harmless: the CLI does it once.
- An order sent while the Foreman is mid-turn arrives when the turn ends. Do not resend.
- In the Foreman's own session the user may type only "stop" or "pause"; anything else is
  redirected to you.
- Never retry an action the Foreman reports as refused; tell the user.
- Prepare and grill a CR before an `add` order. Dropping it returns the folder to its original
  inbox or priority backlog; the branch and worktree are preserved for the user to inspect.

## Failure handling

No confirmation within about two minutes: ping once, then [recovery](recovery.md).
