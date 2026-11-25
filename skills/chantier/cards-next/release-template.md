# Release template

The default release notes and announcement thread, written by the release Driver. The pictures and the thread are in `help release-evidence`.

## Scope and precedence

- The project's own release procedure, and what `$CHANTIER rules` reaches, rank above it. Where the project says how its notes or announcement are written, follow it as written; this file fills only where it is silent.
- The mechanics (version, tag, publication, gates) are the project's own; this file adds none.

## The notes

Written for the project's users, with no CR, batch or agent-role reference. The structure, in order:

- a title: the product name and the full version (`X.Y.Z`, never `X.Y`); then a subtitle that names the release's kind first, then the two or three main changes in the kind's words; then a `<sub>` line with the number of changes since the previous version, what it runs on and the licence;
- a line of links: install, docs, full changes;
- two to four highlights;
- the smaller changes, one line each;
- every fix and every detail, in folded sections.

Every changelog line (each `feat:` and `fix:` commit since the previous version) appears once: as a highlight, a smaller change or a folded line.

### The kind

- Decide the kind from what ships, before writing a line:
  - **feature**: the user can do something they could not do before;
  - **fix**: something that should have worked now works; nothing new;
  - **restore**: it undoes a mistake of an earlier release;
  - **breaking**: something the user relied on is removed or behaves differently and they must act;
  - **internal**: nothing the user sees changes.
- The subtitle names the kind in its first words ("A bug-fix release: ...", "Restores ... that 1.12.0 broke", "A breaking release: ..."), and every highlight and line keeps that tone: a fix release has no "you can now", a restore is never shown as new.
- Several kinds: the subtitle names first the one that comes first in this order: breaking, feature, restore, fix, internal; each line keeps its own change's tone.
- When the kind the notes need does not match the version (a patch whose content needs feature wording, a minor that ships only fixes), the notes take the tone of the real kind and the version PR's description says the version is probably wrong and why; the user decides, the Driver never changes the version itself.

### Writing rules

- Write like a maintainer telling a colleague what changed: short complete sentences, plain verbs, "you". For the user: no ticket number, no internal term, no implementation.
- Never "Before:" or "Now:" labels, an invented scene, a punchy fragment ("Two gestures."), a praise word (seamless, powerful, effortless, easily), or a closing "why it matters" line.
- Banned constructions:

| Banned | Before | After |
| --- | --- | --- |
| A fix worded as a new ability | "You can now edit a block without losing your cursor." | "Fixed: the cursor stays in the block you are editing." |
| A restore shown as new | "New: paste whole blocks at once." | "Restored: pasting whole blocks, which 1.12.0 broke." |
| A closing "why it matters" line | "... This means you stay in the flow." | (line removed) |
| Mechanism instead of consequence | "The parser now debounces change events on the block node." | "Typing fast in a long block no longer freezes the editor." |
| Bad news softened or buried | "We streamlined the settings (the `legacy.view` option is gone) and ..." | "Removed: the setting `legacy.view`; the new view is the only one." |
| A sentence about a missing image | "No screenshot: this change has nothing to show." | (sentence removed) |
| Feature tone in a fix release | subtitle "Faster editing, smarter blocks" | subtitle "A bug-fix release: block editing works again" |

### A highlight

- In order: a heading saying the change in its kind's words, at most two sentences, then the picture. Feature: what you can now do. Fix: "Fixed: <what works again>". Restore: what works again and, in one clause, that the earlier release broke it. Breaking: what changed and what the user must do.
- A change that replaces a visible behaviour: one image with the before and the after side by side; the text does not describe the before again. A picture that shows the whole change needs no text.
- A setting is named as a setting ("the setting `full.name`"), with its default and where to turn it on.

### One line per change

- Each smaller change and folded line is one sentence. A fix starts "Fixed:" and says what works now as the user sees it. A restore owns the earlier release's mistake in one clause ("Restored: copy and paste of whole blocks, which 1.12.0 broke."), no apology, no blame. Say the consequence for the user, not the mechanism.

### Bad news

- A removal, a change of behaviour the user relies on and a user-facing known issue each get a labelled line in the visible part, above the folded sections, starting `Removed:`, `Changed:` or `Known issue:`, one sentence, with what the user should do. Never only in a folded section, never inside a paragraph about something else, never softened ("streamlined") when the truth is "removed".

### Length

A judgement, not a check. Subtitle at most 16 words; each smaller change or folded line at most 20; each highlight's text at most 40 (heading included, picture excluded). The visible part (above the first folded section, links and HTML tags not counted) at most 120 words for a fix, restore or internal release and 250 for a feature or breaking one; a release of several kinds takes the budget of the kind its subtitle names first. Over a budget, cut words, not facts: a fact that does not fit moves to a folded line.

### Self-check

Before the notes are final (before `note --draft` on the last version and before the version PR's body is refreshed), answer yes or no and fix each "no":

1. Does the subtitle name the release's kind in its first words?
2. Does the title carry the full version (`X.Y.Z`)?
3. Does every highlight and line keep the tone of the release's kind?
4. Does every fix start with "Fixed:" and say what works now?
5. Does every restore own, in one clause, the earlier release that broke it?
6. Is every removal, behaviour change and user-facing known issue on a `Removed:`, `Changed:` or `Known issue:` line in the visible part?
7. Is each smaller change and folded line one sentence, and is every budget of "Length" kept?
8. Does every line say the consequence for the user, with none of the banned constructions?
9. Does every image show only the changed element, within the size `help release-evidence` gives, its alt text saying what it shows, with no sentence about a missing image?
10. Does the version match the kind, or does the version PR say it is probably wrong?
