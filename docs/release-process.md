# Release process: notes and announcement

The mechanics of a release (version, tag, publication) are in
[CONTRIBUTING.md](../CONTRIBUTING.md) "Release". This file says what the user reviews in the
version PR: the release notes, the announcement thread and their images, in
`docs/release-notes/YYYY-MM-DD-vX.Y.Z/`. The folder is named by the date of the version PR. That
date may differ from the tag's, and nothing checks it.

The model is Markdown OKF-Schema Studio's release process. The generic default that other projects
get is [release-template](../skills/chantier/references/release-template.md); this file ranks above
it for chantier.

## The release folder

| File | Content |
| --- | --- |
| `release-notes.md` | The GitHub release notes, with images linked by bare file name |
| `tweet.md` | The announcement thread: three posts |
| Images (`*.png`) | The images of the notes and of the thread, directly in the folder |

`just check` runs `scripts/release_notes.py --check`. From version 0.8.0 on, it refuses a missing
or invalid folder.

## Release notes

They are written for a user of chantier from the commits since the previous tag
(`git log --no-merges vPREVIOUS..HEAD`; chantier has no `CHANGELOG.md`) and from the
specifications, PR descriptions and evidence of the CRs they come from. They contain no CR number
or slug, no batch number and no path under `.agents/changes/`. The role names (Chief of Staff,
Foreman, Driver) are product vocabulary and may be used. The structure, in order:

1. **Header**, centred:
   - `<h1 align="center">chantier X.Y</h1>`;
   - one bold line naming the two or three headline changes, as verbs;
   - one `<sub>` line: `N changes since X.Y'.Z' · Claude Code and GitHub Copilot · MIT`, where N
     is `git rev-list --no-merges --count vPREVIOUS..HEAD` on `main` before the version commit.
2. **Links**, centred, on one line: Install (`https://github.com/gsemet/chantier#install`) · the
   tutorial (`blob/vX.Y.Z/docs/tutorial-claude-code.md`) · the use cases
   (`blob/vX.Y.Z/docs/use-cases.md`) · Full changes (`compare/vPREVIOUS...vX.Y.Z`). Then a `---`
   rule.
3. **Two to four highlight sections**, `## <emoji> <what the reader can now do>`. Each has:
   - a short paragraph saying what changes for the reader;
   - a usage or call example: what the user says to the Chief of Staff (a quoted line), or a CLI
     call with its output in a code block;
   - one capture, or a before/after pair in a two-column table with a caption row;
   - a link to the doc that covers it, at the tag (`blob/vX.Y.Z/...`);
   - one closing sentence on why it matters.
4. **`## 🛠 Smaller changes`**: the smaller visible changes, one bullet each, with a bold lead.
5. **Folded sections**: `<details><summary><b>🐞 All fixes</b></summary>`, then
   `<details><summary><b>🛠 For contributors</b></summary>` (tooling, tests, docs process, known
   issues).

Every `feat:` and `fix:` commit since the previous tag appears exactly once: in a highlight, in
Smaller changes or in All fixes.

## Visuals

All of them come from the release's real batch: the release CR joins the batch whose work it ships
(see "Which batch"), so that batch's board and `STATUS.md` show the work. The sources are:

- the board and the batch's `STATUS.md` (`.agents/changes/4-batch/STATUS.md`);
- the Chief of Staff's latest Progress report, `report.md` in the release CR's folder;
- excerpts of a conversation with the Chief of Staff, `conversation.md` in the release CR's
  folder (the Chief of Staff writes both at `order confirm`);
- CLI output (`$CHANTIER status`, `cost`, ...).

The docs SVG diagrams are not used by default: one is shown only on the user's word in the release
CR's grill (the release CR's specification then names it). Rendering works like this:

- the release Driver writes each source as an HTML page in its work folder;
- it applies the anonymisation (below) to that page;
- it renders the page to PNG with headless Chrome, for example
  `chrome --headless=new --screenshot=<file>.png --window-size=1200,<h> file:///<page>.html`, at a
  width readable in a post;
- it saves the PNG into the release folder.

The HTML sources stay in the work folder and are not committed. If headless Chrome is missing,
nothing else is used in its place: the Driver hands back a `blocked question:` naming what is
missing.

## Images

Images sit directly in the release folder, and the notes and `tweet.md` link them by bare file
name. An image at a URL or in a subfolder fails the check, because a release must depend on no
branch. On publication, `--prepare` points the links to
`https://github.com/gsemet/chantier/releases/download/vX.Y.Z/<file>` and the images are attached
as release assets.

## Anonymisation

No personal path, user name, email, private repository or session id appears in any text or
image. The Driver applies these replacements to every source before rendering it:

| What | Replaced by |
| --- | --- |
| Home folder (`C:\Users\<name>`, `/Users/<name>`, `/home/<name>`) | `~` |
| Local login name, git user name | `user` |
| Email | `user@example.com` |
| Session id, transcript id (UUID) | `<session>` |
| Repository other than `gsemet/chantier` | `example/app`, unless the user said it is public |

How it is checked:

1. Before rendering, the Driver runs `uv run --script scripts/release_notes.py --scan <page>...`
   on each HTML source. It must exit 0.
2. The Driver reads each PNG it produced before committing it.
3. `just check` scans `release-notes.md` and `tweet.md`.
4. The user reviews every image in the version PR.

The scan cannot read pixels, so steps 2 and 4 cover the images, and step 1 covers their sources.

## Announcement thread

`tweet.md` starts with `# Announcement thread for X.Y.Z`, followed by three posts under `## 1/`,
`## 2/` and `## 3/`:

1. **The story** (it may be long). First person, as one would tell a colleague: start from a
   concrete moment of work with chantier that the release improves, then say what is different
   now. At most three changes, in plain words, not a feature list. This post carries the thread's
   only image: an `Image: <file>` line naming one of the notes' captures.
2. **The release notes**: one sentence inviting the reader to the details, then
   `https://github.com/gsemet/chantier/releases/tag/vX.Y.Z`.
3. **Install**: one sentence (install or update, free, MIT), then
   `https://github.com/gsemet/chantier#install`.

Tone: organic. No launch words ("excited to announce", "game changer", "supercharge"), at most two
emoji in the whole thread, and no list of hashtags. Only the user posts: no agent posts the thread.

## Which batch

A chantier release joins the batch whose work it ships (`order add --release --note <folder>`),
rather than running alone with `--release 1`: that batch's board and `STATUS.md` then show the
work the captures explain. At `order confirm` the Chief of Staff writes `report.md` (its latest
Progress report) and `conversation.md` (the excerpts it chooses) into the release CR's folder. A
docs SVG diagram goes into the notes only on the user's word in the release CR's grill.
