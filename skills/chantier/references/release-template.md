# Release template

The default release notes and announcement thread, written by the release Driver.

## Scope and precedence

- It is the default form of a release's notes and announcement thread, written by the release
  Driver. The project's own release procedure, and what `$CHANTIER rules` reaches, rank above it.
  Where the project says how its notes or its announcement are written, the Driver follows the
  project as written, and this file only fills where the project is silent.
- The mechanics (version, tag, publication, gates) are always the project's own, and this file
  adds none.

## The notes

Written for the project's users, with no CR, batch or agent-role reference, as in
[pr-template](pr-template.md). The structure, in order:

- a title: the product name and the full version (`X.Y.Z`, never `X.Y`), then a subtitle line that
  names the release's kind first, then the two or three main changes, in the kind's words (not "as
  verbs" whatever ships), and a `<sub>` line with N changes since the previous version, what it runs on, and the
  licence;
- a line of links: install, docs, full changes;
- two to four highlights;
- the smaller changes, one line each;
- every fix and every detail, in folded sections.

Every changelog line (each `feat:` and `fix:` commit since the previous version) appears once, as a
highlight, a smaller change or a folded line, never twice.

### The kind

- Before writing a line, decide the release's kind from what ships, one of five:
  - **feature**: the user can do something they could not do before;
  - **fix**: something that should have worked now works; nothing new;
  - **restore**: it undoes a mistake of an earlier release (a revert, a behaviour put back);
  - **breaking**: something the user relied on is removed or behaves differently and they must act;
  - **internal**: nothing the user sees changes (tooling, tests, docs process).
- The subtitle names the kind in its first words (for instance "A bug-fix release: ...", "Restores
  ... that 1.12.0 broke", "A breaking release: ..."), and every highlight and line keeps the tone
  of that kind: a fix release has no "you can now" heading, a restore is never shown as new.
- A release that holds several kinds: the subtitle names first the kind that comes first in this
  order: breaking, feature, restore, fix, internal. Each highlight and line keeps the tone of its
  own change's kind (a fix inside a feature release still starts "Fixed:").
- When the kind the notes need does not match the version (a patch version whose content needs
  feature wording, or a minor version that ships only fixes), the notes take the tone of the real
  kind; the version PR's description says the version is probably wrong and why, and the user
  decides. The Driver does not change the version on its own: this is a statement in the PR, not a
  question.

### Writing rules

- Write like a maintainer telling a colleague what changed: short, complete sentences, plain verbs,
  "you".
- For the user: no ticket number, no internal term, no implementation.
- Never use "Before:" or "Now:" labels, an invented scene, a punchy fragment ("Two gestures."), a
  praise word (seamless, powerful, effortless, easily), or a closing "why it matters" line.
- Banned constructions, each with its fix:

| Banned | Before | After |
| --- | --- | --- |
| A fix worded as a new ability | "You can now edit a block without losing your cursor." | "Fixed: the cursor stays in the block you are editing." |
| A restore shown as new | "New: paste whole blocks at once." | "Restored: pasting whole blocks, which 1.12.0 broke." |
| A closing "why it matters" line | "... This means you stay in the flow." | (line removed) |
| Mechanism instead of consequence | "The parser now debounces change events on the block node." | "Typing fast in a long block no longer freezes the editor." |
| Bad news softened or buried | "We streamlined the settings (the `legacy.view` option is gone) and ..." | "Removed: the setting `legacy.view`; the new view is the only one." |
| A sentence about a missing image | "No screenshot: this change has nothing to show." | (sentence removed; the change has no picture) |
| Feature tone in a fix release | subtitle "Faster editing, smarter blocks" for a fix release | subtitle "A bug-fix release: block editing works again" |

### A highlight

- In this order: a heading saying the change in its kind's words, at most two sentences, then the
  picture. A feature: what you can now do; a fix: "Fixed: <what works again>"; a restore: what
  works again and, in one clause, that the earlier release broke it ("<X> works again; 1.12.0 broke
  it"); a breaking change: what changed and what the user must do.
- When the change replaces a visible behaviour, the picture puts the before and the after side by
  side in one image, built from the Verifier's before/after (below), and the text does not describe
  the before again.
- When the picture shows the whole change, the highlight is the heading and the picture, with no
  text.
- A setting is named as a setting: "the setting `full.name`", with its default value and where to
  turn it on.

### One line per change

- Each smaller change and each folded line is one sentence.
- A fix starts with "Fixed:" and says what works now, as the user sees it: "Fixed: the editor keeps
  the cursor in the block you were editing." Never a fix worded as a new ability.
- A restore owns the earlier release's mistake in one clause: "Restored: copy and paste of whole
  blocks, which 1.12.0 broke." No apology paragraph, no blame.
- Say the consequence for the user, not the mechanism: what they see or can do, not how the code
  does it.

### Bad news

- A removal, a change of behaviour the user relies on, and a user-facing known issue each get a
  labelled line in the visible part (above the folded sections), starting `Removed:`, `Changed:` or
  `Known issue:`, one sentence each, with what the user should do when there is something to do.
- Never only in a folded section (a user-facing known issue is not a contributor's detail), never
  inside a paragraph about something else, never softened ("streamlined", "simplified") when the
  truth is "removed".

### Length

A judgement, not a check.

- Subtitle at most 16 words; each smaller change or folded line at most 20 words; each highlight's
  text at most 40 words (heading included, picture excluded).
- The visible part (everything above the first folded section, the link line and HTML tags not
  counted) at most 120 words for a fix, restore or internal release, at most 250 for a feature
  release, at most 250 for a breaking release. A release of several kinds takes the budget of the
  kind its subtitle names first.
- Over a budget, cut words, not facts: a fact that does not fit moves to a folded line.

### Self-check

Before the notes are final (before `note --draft` on the last version and before the version PR's
body is refreshed from them), answer these ten yes/no questions; fix each "no" first:

1. Does the subtitle name the release's kind in its first words?
2. Does the title carry the full version (`X.Y.Z`)?
3. Does every highlight and line keep the tone of the release's kind?
4. Does every fix start with "Fixed:" and say what works now, with no fix worded as a new ability?
5. Does every restore own, in one clause, the earlier release that broke it?
6. Is every removal, behaviour change and user-facing known issue on a `Removed:`, `Changed:` or
   `Known issue:` line in the visible part?
7. Is each smaller change and folded line one sentence, and is every budget of "Length" kept?
8. Does every line say the consequence for the user, not the mechanism, with none of the banned
   constructions?
9. Does every image show only the changed element, within the size of "Visible evidence", its alt
   text saying what it shows, with no sentence about a missing image?
10. Does the version match the kind, or does the version PR say it is probably wrong?

## Visible evidence

Each highlight shows what ships, with one image: for a change that replaces a visible behaviour,
the before and the after side by side, built from the Verifier's before/after. The sources are:

- the Verifier's before/after in the merged CRs' `evidence/` folders (`4-batch/3-done/`, and `5-archives/` for earlier batches);
- the screenshots in the merged PRs' Deliverables sections;
- captures of the product running, made by the Driver;
- CLI output.

When the release CR's folder holds `report.md` or `conversation.md`, they are sources too. They
are anonymised: no personal path, user name, email, private repository or session id, replaced by
`~`, `user`, `user@example.com`, `<session>` and `example/app`. The Driver reads each image it
produced before it keeps it. The image protocol:

- Only a visible change gets an image; one image per change.
- Crop to the changed element (the control, the panel, the lines of output), never the whole window
  or page; 900 to 1200 px wide, at most 600 px high.
- A before/after is one joined image, both halves the same region at the same scale.
- The alt text is the caption: it says what the image shows, in one plain phrase; no separate
  caption line.
- The Driver crops with the project's own means and names no tool.
- A visible change, a fix included, whose sources hold no image: the Driver captures it itself with
  the project's own capture means before the notes are final.
- When the capture is impossible, or the image cannot be cropped to the changed element within the
  bounds (900 to 1200 px wide, at most 600 px high): the notes go out without that image and say
  nothing about it; the version PR's Known gaps names it as `no picture for <change>: <why>`. The
  project's own capture means are tried first.
- A release whose procedure opens no version PR has no Known gaps: the missing picture is named,
  with the same words, in a `note` (`$CHANTIER note`) and in the Driver's hand-back report. The
  notes still say nothing about it.
- Nothing visible to show: no image and no sentence about it.
- The Release Driver reads each image it produced before it keeps it and checks there: the crop
  shows the change, the size is within the bounds, the alt text matches, and the look of
  [driver](driver.md) ("Means: images and the look") passes.

A diagram of the project's docs is shown only on the user's word in the release CR's grill.

In the skeleton, name an image in `<img src="...">` form or in prose, never as a Markdown image
link to a file that may not exist. The same goes for the version PR's body.

## The thread

Three posts:

1. the story, which may be long: first person, a concrete moment of work the release improves,
   then what is different now, at most three changes in plain words; it carries the thread's one
   image;
2. the link to the release notes;
3. one sentence (install or update, the price, the licence) and the install link.

The tone is organic: no launch words ("excited to announce", "game changer"), at most two emoji,
no list of hashtags. No agent posts: the thread is a draft for the user.

## Where they go

By default the Driver writes `release-notes.md`, `tweet.md` and the images in `<work folder>/release/`
and runs `note --draft` on each text, as [driver](driver.md) says. When the release has a version PR, the Driver also shows
`release-notes.md` and then `tweet.md` in the PR's body, under the PR's own description, rendered,
each after a `---` rule, the thread headed as a draft the user posts. The files stay the source
and the body is refreshed from them before the merge, as [driver](driver.md) says. An image shows
in the body once it is on the forge (its upload is an irreversible action, `release go`), else it
is named in prose. What the forge's size limit leaves out is named by its path. A release with no
PR keeps the drafts only. Where the procedure publishes
notes (a forge release, a changelog entry), the Driver uses the reviewed text there. The images
are attached with the forge's own CLI, and that is an irreversible action (`release go`). Where
the procedure publishes no notes, they stay a draft for the user.
