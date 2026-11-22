# The board's design rules

The rules every page of the board follows, and the features no design pass may lose. Any change
under `skills/chantier/scripts/cli/src/chantier/clients/web/` reads this file first and keeps it true
(`AGENTS.md` says the same). `css/tokens.css` is the single source of every value; this file holds
the rules and a table of the tokens, and a test (`tests/test_board_design.py`, in `just check`)
fails when the table and `tokens.css` disagree.

## Rules

- **Tokens.** Every colour, radius, spacing and type size is a token of `css/tokens.css`; a sheet
  names it through `var()` and writes no literal. A margin, a padding or a gap takes a `space`
  token, or a `size` token for a frame's offset (`--bar-height`); a radius takes a `radius` token;
  a font size a `type` token. Allowed as they are: `0`, `auto`, `inherit`, `initial`, `unset`, and
  `calc()` of tokens with unitless numbers (a negative margin is `calc(-1 * var(--space-2))`). A
  custom property declared in a view sheet holds an angle, an opacity or a width, never a value of
  those kinds (test).
- **No side accent border.** No element has a border on its left or right side only, by any means
  (a `border-left`, `border-right` or `border-inline*` declaration, a one-side inset shadow, a
  pseudo-element bar), above all one that follows a rounded corner. One exception: a plain
  straight separator between two regions of a page (the sidebar's edge, the drawer tree's edge,
  the Batch stack rail): `1px solid` in a separator colour (`--line`, `--side-line`), on an element
  with no radius, never on a component. A card shows its priority with the priority chip (test).
- **Components.** A component (card, column, chip) is styled in its own sheet only, with its
  variants. A page's sheet only lays components out (its grid or flex container, gaps, and on a
  component only placement and size: `grid-*`, `flex*`, `order`, `*-self`, `width`, `min-width`,
  `max-width`, `height`, `min-height`, `max-height`, `overflow*`, `scroll-snap-*`, `margin*`), and
  never restyles one (test).
- **One card, one column, one chip.** Every card is built by `js/ui/card.js` (test): a hairline all
  around, no side accent, the priority chip, when the item has a priority, first in its top row at
  the top left. Every board column (Triage, Kanban, the Batch page's Kanban) is built by `js/ui/column.js`: a light area, a
  hairline, a plain head (dot, name, count) and a one-line grey sub-line saying what it holds; a
  column that appears on both pages has the same dot colour on both. The chip lives in
  `css/components/chip.css`; the priority chip is Triage's, filled with the priority colour, on
  every card that has a priority (inbox, P1 to P4, 3-ready); a card of a CR in the batch shows in
  that place its batch folder (1-pending, 2-actives, 3-done) in a neutral grey chip, never a
  priority; a chip used as a filter toggle (Triage's priorities, the Inbox's kinds) is the
  same chip, filled when on, outlined grey when off (`.tag.st.off`), the same size in both states. A lane, built by
  the same module (`lane(parts)`), sits in a column's body and has no dot: a Backlog lane's head is
  its priority chip, its count, its grill counts and its fold chevron; Triage's last column holds two named lanes,
  "Running batch" over "Next batch", each with its name, count, grill counts and own grey sub-line.
- **One-line titles.** A CR's title in a card, a row or a table cell is drawn on one line, cut with
  an ellipsis, its full text in the element's `title` attribute; the side panel shows it whole
  (test).
- **Words.** Every string the board shows goes through the i18n keys (`t()`, `tn()`), in every
  language file; data (titles, slugs, file contents) is shown as it is.
- **One transport.** The page talks to the server through `js/core/transport.js` only (`call`,
  `subscribe`, `fileUrl`), over the WebSocket of protocol 1, or over HTTP (`POST api/v1/call/<op>`
  and the long-poll) when the socket never opens or the address says `?transport=http`, which the
  sidebar footer shows as " (HTTP)". A view names a published op or topic and no address; no file
  but the transport's three opens a socket (test).
- **The reference look.** This file describes the column, the card and the chip in words only; no
  picture ships in the package, and a pull request's screenshots are the visual record.

## The last column of Triage

- The last column holds two halves, "running batch" over "next batch" (`3-ready`), always drawn: in
  every mode, with or without a batch.
- Each half is a named lane of `js/ui/column.js`, with its head (name, count, grill counts) and its
  own one-line sub-line; `css/views/triage.css` only places the two halves.
- The top half is greyed (`column-idle`, existing tokens only) with "no running batch" when no
  batch is open; it stays a drop target, and a drop on it goes to `3-ready`.
- A CR marked for the open batch (`running_batch` on its item) is drawn in the top half only, as a
  post-it, never in its inbox or priority row.
- The batch's pending CRs are plain cards there, neither draggable nor selectable.
- The three state words ("waiting for its spec", "spec written: joins soon", "waiting for a slot")
  are words only, in the card's meta line: no new colour, size or icon.

## Tokens

One row per custom property of `css/tokens.css`, in its order. Kind: `colour`, `space`, `radius`,
`type`, `shadow`, `font`, `size` or `other`.

| Token                  | Value                                                                                                                                                                   | Kind   | Use                                                             |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------------- |
| `--bg`                 | `#fff`                                                                                                                                                                  | colour | page and panel surface                                          |
| `--panel`              | `#fff`                                                                                                                                                                  | colour | page and panel surface                                          |
| `--side`               | `#f6f9f9`                                                                                                                                                               | colour | sidebar fill, its edge, its hover                               |
| `--side-line`          | `#e3eced`                                                                                                                                                               | colour | sidebar fill, its edge, its hover                               |
| `--side-hover`         | `#edf3f3`                                                                                                                                                               | colour | sidebar fill, its edge, its hover                               |
| `--line`               | `#ececef`                                                                                                                                                               | colour | hairlines (--line, --side-line are the separator colours)       |
| `--line2`              | `#eff0f2`                                                                                                                                                               | colour | hairlines (--line, --side-line are the separator colours)       |
| `--card-line`          | `#ebecef`                                                                                                                                                               | colour | hairlines (--line, --side-line are the separator colours)       |
| `--card-hover`         | `#d6d9de`                                                                                                                                                               | colour | hairlines (--line, --side-line are the separator colours)       |
| `--ink`                | `#1a1c21`                                                                                                                                                               | colour | text ink, three greys                                           |
| `--ink2`               | `#545862`                                                                                                                                                               | colour | text ink, three greys                                           |
| `--ink3`               | `#868a94`                                                                                                                                                               | colour | text ink, three greys                                           |
| `--white`              | `#fff`                                                                                                                                                                  | colour | white                                                           |
| `--chip`               | `#f2f3f5`                                                                                                                                                               | colour | chip and pill fills                                             |
| `--chip-2`             | `#eceef1`                                                                                                                                                               | colour | chip and pill fills                                             |
| `--pill`               | `#f1f2f4`                                                                                                                                                               | colour | chip and pill fills                                             |
| `--hover`              | `#f6f7f8`                                                                                                                                                               | colour | hover and band fills                                            |
| `--hover-soft`         | `#f6f7f8`                                                                                                                                                               | colour | hover and band fills                                            |
| `--band`               | `#f6f7f8`                                                                                                                                                               | colour | hover and band fills                                            |
| `--band-line`          | `#eff0f2`                                                                                                                                                               | colour | hover and band fills                                            |
| `--caption`            | `#8d919a`                                                                                                                                                               | colour | caption, count and separator greys                              |
| `--count`              | `#a3a7af`                                                                                                                                                               | colour | caption, count and separator greys                              |
| `--sep`                | `#c4c7cd`                                                                                                                                                               | colour | caption, count and separator greys                              |
| `--selection`          | `#d6e2fa`                                                                                                                                                               | colour | text selection, scrollbar                                       |
| `--scroll`             | `#cdd1d8`                                                                                                                                                               | colour | text selection, scrollbar                                       |
| `--warn-ink`           | `#8a5208`                                                                                                                                                               | colour | warning, error and ok ink                                       |
| `--bad-ink`            | `#c03552`                                                                                                                                                               | colour | warning, error and ok ink                                       |
| `--accent`             | `#1d5c63`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--accent-dark`        | `#123d42`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--accent-mid`         | `#5f8d93`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--accent-light`       | `#8fb6ba`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--accent-tint`        | `#e9f1f1`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--accent-tint-2`      | `#e7f0f0`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--accent-line`        | `#d2e3e4`                                                                                                                                                               | colour | the accent, deep teal, and its shades                           |
| `--link`               | `var(--accent)`                                                                                                                                                         | colour | the accent, deep teal, and its shades                           |
| `--pri-1`              | `#1d5c63`                                                                                                                                                               | colour | priority ramp, P1 dark to P4 pale                               |
| `--pri-2`              | `#4a7e83`                                                                                                                                                               | colour | priority ramp, P1 dark to P4 pale                               |
| `--pri-3`              | `#88acb0`                                                                                                                                                               | colour | priority ramp, P1 dark to P4 pale                               |
| `--pri-4`              | `#cfe2e3`                                                                                                                                                               | colour | priority ramp, P1 dark to P4 pale                               |
| `--state-blocked`      | `#d14b5e`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-working`      | `#4a76d9`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-ready`        | `#2f9e6b`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-draft`        | `#a77b4f`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-local`        | `#8b6bd8`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-waits`        | `#d08a1f`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-queued`       | `#a3a7af`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--state-merged`       | `#2a7a55`                                                                                                                                                               | colour | a state's colour, for its icon, dot or badge                    |
| `--red`                | `var(--state-blocked)`                                                                                                                                                  | colour | a state's colour by its hue name                                |
| `--blue`               | `var(--state-working)`                                                                                                                                                  | colour | a state's colour by its hue name                                |
| `--green`              | `var(--state-ready)`                                                                                                                                                    | colour | a state's colour by its hue name                                |
| `--brown`              | `var(--state-draft)`                                                                                                                                                    | colour | a state's colour by its hue name                                |
| `--violet`             | `var(--state-local)`                                                                                                                                                    | colour | a state's colour by its hue name                                |
| `--amber`              | `var(--state-waits)`                                                                                                                                                    | colour | a state's colour by its hue name                                |
| `--grey`               | `var(--state-queued)`                                                                                                                                                   | colour | a state's colour by its hue name                                |
| `--ok-ink`             | `var(--state-merged)`                                                                                                                                                   | colour | warning, error and ok ink                                       |
| `--state-working-tint` | `#e7eefb`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-ready-tint`   | `#e4f4ec`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-blocked-tint` | `#fbe7ea`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-waits-tint`   | `#fbf0de`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-merged-tint`  | `#e3f1ea`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-draft-tint`   | `#f4eee8`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-local-tint`   | `#f0ecfa`                                                                                                                                                               | colour | tint of a state, for its chip or badge only                     |
| `--state-queued-tint`  | `var(--chip)`                                                                                                                                                           | colour | tint of a state, for its chip or badge only                     |
| `--queued-bar`         | `#c9cdd6`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--edge-line`          | `#c7ccd6`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--edge-arrow`         | `#aab1bf`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--halo`               | `#dbe5fb`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--grid-bg`            | `#fcfcfd`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--grid-dot`           | `#dfe2e7`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--col-fill`           | `#fbfbfc`                                                                                                                                                               | colour | bars, arrows, halos and the Batch graph's grid; the column fill |
| `--row-hover`          | `#f6f7f8`                                                                                                                                                               | colour | hover and band fills                                            |
| `--gs-grill-rest`      | `#f3e2c4`                                                                                                                                                               | colour | Triage: grill-state post-its, the column over a drag            |
| `--drop-fill`          | `var(--accent-tint)`                                                                                                                                                    | colour | Triage: grill-state post-its, the column over a drag            |
| `--drop-edge`          | `var(--accent-light)`                                                                                                                                                   | colour | Triage: grill-state post-its, the column over a drag            |
| `--label-0`            | `#2a56b8`                                                                                                                                                               | colour | a project label's colour, by its place                          |
| `--label-1`            | `#8f5400`                                                                                                                                                               | colour | a project label's colour, by its place                          |
| `--label-2`            | `#1c6e44`                                                                                                                                                               | colour | a project label's colour, by its place                          |
| `--label-3`            | `#7440c0`                                                                                                                                                               | colour | a project label's colour, by its place                          |
| `--label-4`            | `#b02f4b`                                                                                                                                                               | colour | a project label's colour, by its place                          |
| `--label-5`            | `#515867`                                                                                                                                                               | colour | a project label's colour, by its place                          |
| `--dark`               | `#16181d`                                                                                                                                                               | colour | dark surfaces: the selection bar, the toast                     |
| `--dark-button`        | `#2c2f37`                                                                                                                                                               | colour | dark surfaces: the selection bar, the toast                     |
| `--dark-button-hover`  | `#3a3e48`                                                                                                                                                               | colour | dark surfaces: the selection bar, the toast                     |
| `--dark-ink`           | `#fff`                                                                                                                                                                  | colour | dark surfaces: the selection bar, the toast                     |
| `--dark-ink-soft`      | `#c9ccd4`                                                                                                                                                               | colour | dark surfaces: the selection bar, the toast                     |
| `--mark-0`             | `#a02e78`                                                                                                                                                               | colour | a project's mark colour                                         |
| `--mark-1`             | `#1a6c88`                                                                                                                                                               | colour | a project's mark colour                                         |
| `--mark-2`             | `#3a7222`                                                                                                                                                               | colour | a project's mark colour                                         |
| `--mark-3`             | `#8a3aa8`                                                                                                                                                               | colour | a project's mark colour                                         |
| `--mark-4`             | `#666c12`                                                                                                                                                               | colour | a project's mark colour                                         |
| `--mark-5`             | `#1a736d`                                                                                                                                                               | colour | a project's mark colour                                         |
| `--mark-0-tint`        | `#f2e2ec`                                                                                                                                                               | colour | pale tint of a project mark                                     |
| `--mark-1-tint`        | `#dfeaee`                                                                                                                                                               | colour | pale tint of a project mark                                     |
| `--mark-2-tint`        | `#e3ebe0`                                                                                                                                                               | colour | pale tint of a project mark                                     |
| `--mark-3-tint`        | `#efe3f3`                                                                                                                                                               | colour | pale tint of a project mark                                     |
| `--mark-4-tint`        | `#eaeade`                                                                                                                                                               | colour | pale tint of a project mark                                     |
| `--mark-5-tint`        | `#dfebeb`                                                                                                                                                               | colour | pale tint of a project mark                                     |
| `--writer-synced`      | `#23805a`                                                                                                                                                               | colour | the surface's writer pill and box                               |
| `--writer-pending`     | `#2f6fb5`                                                                                                                                                               | colour | the surface's writer pill and box                               |
| `--writer-offline`     | `#8b909c`                                                                                                                                                               | colour | the surface's writer pill and box                               |
| `--writer-blocked`     | `#c03552`                                                                                                                                                               | colour | the surface's writer pill and box                               |
| `--writer-ko-fill`     | `#fff4f5`                                                                                                                                                               | colour | the surface's writer pill and box                               |
| `--writer-ko-ink`      | `#9c2a41`                                                                                                                                                               | colour | the surface's writer pill and box                               |
| `--paper`              | `#fffefb`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-line`         | `#efefe9`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-rule`         | `#d9dbe0`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-sum`          | `#e6e7ea`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-cut`          | `#dfe2e7`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-scissors`     | `#b0b3ba`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-ink`          | `#2a2c31`                                                                                                                                                               | colour | the Costs receipt's paper, lines and ink                        |
| `--paper-grain`        | `repeating-linear-gradient(0deg, rgb(120 110 90 / 2.5%) 0 1px, transparent 1px 3px), repeating-linear-gradient(90deg, rgb(120 110 90 / 2%) 0 1px, transparent 1px 4px)` | other  | the receipt's faint grain                                       |
| `--shadow-ticket`      | `0 1px 2px rgb(22 24 29 / 6%), 0 12px 28px rgb(22 24 29 / 10%)`                                                                                                         | shadow | a shadow of a surface                                           |
| `--shadow-ticket-edge` | `drop-shadow(0 3px 2px rgb(22 24 29 / 6%))`                                                                                                                             | shadow | a shadow of a surface                                           |
| `--ticket-width`       | `420px`                                                                                                                                                                 | size   | the receipt's width                                             |
| `--stamp-hand`         | `#4b3f9e`                                                                                                                                                               | colour | a time card's hand stamp ink                                    |
| `--stamp-rework`       | `var(--state-waits)`                                                                                                                                                    | colour | a time card's rework stamp                                      |
| `--m1`                 | `#d96c4a`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m2`                 | `#3a7bd5`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m3`                 | `#1f9d8b`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m4`                 | `#8b6bd8`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m5`                 | `#d9a32e`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m6`                 | `#c4488a`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m7`                 | `#5b8c3a`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--m8`                 | `#6b7a90`                                                                                                                                                               | colour | the Costs card's model colours, in cost order                   |
| `--spend-chief`        | `#a3a7af`                                                                                                                                                               | colour | the Costs card's chief grey, hatch and over-budget mark         |
| `--spend-hatch`        | `#d6d9de`                                                                                                                                                               | colour | the Costs card's chief grey, hatch and over-budget mark         |
| `--spend-hatch-bg`     | `#f6f7f8`                                                                                                                                                               | colour | the Costs card's chief grey, hatch and over-budget mark         |
| `--spend-over`         | `var(--bad-ink)`                                                                                                                                                        | colour | the Costs card's chief grey, hatch and over-budget mark         |
| `--logo-anthropic`     | `#d97757`                                                                                                                                                               | colour | a provider's mark                                               |
| `--logo-google-blue`   | `#3186ff`                                                                                                                                                               | colour | a provider's mark                                               |
| `--logo-google-green`  | `#08b962`                                                                                                                                                               | colour | a provider's mark                                               |
| `--logo-google-red`    | `#f94543`                                                                                                                                                               | colour | a provider's mark                                               |
| `--logo-google-yellow` | `#fabc12`                                                                                                                                                               | colour | a provider's mark                                               |
| `--shadow-card`        | `0 1px 2px rgb(16 24 40 / 4%), 0 8px 24px -10px rgb(16 24 40 / 14%)`                                                                                                    | shadow | a shadow of a surface                                           |
| `--shadow-card-soft`   | `0 1px 2px rgb(16 24 40 / 3%), 0 6px 18px -10px rgb(16 24 40 / 10%)`                                                                                                    | shadow | a shadow of a surface                                           |
| `--shadow-menu`        | `0 10px 30px rgb(16 24 40 / 12%)`                                                                                                                                       | shadow | a shadow of a surface                                           |
| `--shadow-head`        | `0 1px 8px rgb(16 24 40 / 6%)`                                                                                                                                          | shadow | a shadow of a surface                                           |
| `--shadow-panel`       | `-14px 0 40px rgb(15 18 28 / 14%)`                                                                                                                                      | shadow | a shadow of a surface                                           |
| `--shadow-note`        | `0 1px 1px rgb(0 0 0 / 6%), 0 3px 8px rgb(30 30 50 / 7%)`                                                                                                               | shadow | a shadow of a surface                                           |
| `--shadow-note-hover`  | `0 6px 16px rgb(30 30 50 / 12%)`                                                                                                                                        | shadow | a shadow of a surface                                           |
| `--shadow-float`       | `0 10px 30px rgb(0 0 0 / 25%)`                                                                                                                                          | shadow | a shadow of a surface                                           |
| `--shadow-dialog`      | `0 0 0 1px rgb(20 24 31 / 6%), 0 10px 30px rgb(0 0 0 / 12%)`                                                                                                            | shadow | a shadow of a surface                                           |
| `--font`               | `"Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", sans-serif`                                                                 | font   | the board's faces                                               |
| `--mono`               | `ui-monospace, consolas, monospace`                                                                                                                                     | font   | the board's faces                                               |
| `--text`               | `14px`                                                                                                                                                                  | type   | a type size                                                     |
| `--text-small`         | `12px`                                                                                                                                                                  | type   | a type size                                                     |
| `--text-badge`         | `11px`                                                                                                                                                                  | type   | a type size                                                     |
| `--title`              | `24px`                                                                                                                                                                  | type   | a type size                                                     |
| `--title-spacing`      | `-0.02em`                                                                                                                                                               | type   | letter spacing                                                  |
| `--caption-spacing`    | `0.08em`                                                                                                                                                                | type   | letter spacing                                                  |
| `--text-stat`          | `13px`                                                                                                                                                                  | type   | a type size                                                     |
| `--title-phone`        | `24px`                                                                                                                                                                  | type   | a type size                                                     |
| `--space-1`            | `4px`                                                                                                                                                                   | space  | margin, padding and gap                                         |
| `--space-2`            | `8px`                                                                                                                                                                   | space  | margin, padding and gap                                         |
| `--space-3`            | `12px`                                                                                                                                                                  | space  | margin, padding and gap                                         |
| `--space-4`            | `16px`                                                                                                                                                                  | space  | margin, padding and gap                                         |
| `--space-5`            | `24px`                                                                                                                                                                  | space  | margin, padding and gap                                         |
| `--radius-s`           | `6px`                                                                                                                                                                   | radius | a corner radius                                                 |
| `--radius-m`           | `9px`                                                                                                                                                                   | radius | a corner radius                                                 |
| `--radius`             | `16px`                                                                                                                                                                  | radius | a corner radius                                                 |
| `--radius-card`        | `14px`                                                                                                                                                                  | radius | a corner radius                                                 |
| `--radius-nav`         | `8px`                                                                                                                                                                   | radius | a corner radius                                                 |
| `--side-width`         | `248px`                                                                                                                                                                 | size   | a frame's size                                                  |
| `--panel-width`        | `680px`                                                                                                                                                                 | size   | a frame's size                                                  |
| `--panel-share`        | `45vw`                                                                                                                                                                  | size   | a frame's size                                                  |
| `--pi-w`               | `320px`                                                                                                                                                                 | size   | a frame's size                                                  |
| `--bar-height`         | `62px`                                                                                                                                                                  | size   | a frame's size                                                  |
| `--crumb-height`       | `58px`                                                                                                                                                                  | size   | a frame's size                                                  |
| `--nav-height`         | `36px`                                                                                                                                                                  | size   | a frame's size                                                  |
| `--gap-main`           | `32px`                                                                                                                                                                  | space  | the gap between a page's main regions                           |
| `--phone-max`          | `760px`                                                                                                                                                                 | size   | a frame's size                                                  |
| `--chart-height`       | `160px`                                                                                                                                                                 | size   | a chart's plot height                                           |

### Off-scale values, kept as they were

Each is the exact value a sheet used before every length was a token, named for it. Folding them
into the scale is a design change of its own.

| Token             | Value    | Kind   | Use                     |
| ----------------- | -------- | ------ | ----------------------- |
| `--space-off-1`   | `1px`    | space  | margin, padding and gap |
| `--space-off-2`   | `2px`    | space  | margin, padding and gap |
| `--space-off-3`   | `3px`    | space  | margin, padding and gap |
| `--space-off-5`   | `5px`    | space  | margin, padding and gap |
| `--space-off-6`   | `6px`    | space  | margin, padding and gap |
| `--space-off-7`   | `7px`    | space  | margin, padding and gap |
| `--space-off-9`   | `9px`    | space  | margin, padding and gap |
| `--space-off-10`  | `10px`   | space  | margin, padding and gap |
| `--space-off-14`  | `14px`   | space  | margin, padding and gap |
| `--space-off-18`  | `18px`   | space  | margin, padding and gap |
| `--space-off-20`  | `20px`   | space  | margin, padding and gap |
| `--space-off-22`  | `22px`   | space  | margin, padding and gap |
| `--space-off-23`  | `23px`   | space  | margin, padding and gap |
| `--space-off-28`  | `28px`   | space  | margin, padding and gap |
| `--space-off-30`  | `30px`   | space  | margin, padding and gap |
| `--space-off-40`  | `40px`   | space  | margin, padding and gap |
| `--space-off-50`  | `50px`   | space  | margin, padding and gap |
| `--space-off-90`  | `90px`   | space  | margin, padding and gap |
| `--radius-off-2`  | `2px`    | radius | a corner radius         |
| `--radius-off-3`  | `3px`    | radius | a corner radius         |
| `--radius-off-4`  | `4px`    | radius | a corner radius         |
| `--radius-off-7`  | `7px`    | radius | a corner radius         |
| `--radius-off-10` | `10px`   | radius | a corner radius         |
| `--radius-pill`   | `999px`  | radius | a corner radius         |
| `--radius-round`  | `50%`    | radius | a corner radius         |
| `--text-off-12-5` | `12.5px` | type   | a type size             |
| `--text-off-13-5` | `13.5px` | type   | a type size             |
| `--text-off-15`   | `15px`   | type   | a type size             |
| `--text-off-15-5` | `15.5px` | type   | a type size             |
| `--text-off-16`   | `16px`   | type   | a type size             |
| `--text-off-17`   | `17px`   | type   | a type size             |
| `--text-off-18`   | `18px`   | type   | a type size             |
| `--text-off-22`   | `22px`   | type   | a type size             |
| `--text-off-34`   | `34px`   | type   | a type size             |
| `--text-off-40`   | `40px`   | type   | a type size             |

## Components

The classes in backticks; a trailing `-*` is a prefix.

| Component | Sheet                       | Builder           | Classes                         |
| --------- | --------------------------- | ----------------- | ------------------------------- |
| card      | `css/components/card.css`   | `js/ui/card.js`   | `card`, `card-*`                |
| column    | `css/components/column.css` | `js/ui/column.js` | `column`, `column-*`            |
| chip      | `css/components/chip.css`   | `js/ui/parts.js`  | `tag`, `lbl`, `lab`, `si`, `sb` |
| chart     | `css/components/chart.css`  | `js/ui/chart.js`  | `chart`, `chart-*`              |

## Protected features

No design pass removes, flattens or restyles these; a change to one is a change request of its own,
on the user's word.

- The Costs page's paper receipt: warm paper, grain, perforation, scissors
  (`css/views/costs-receipt.css`, the `--paper-*` tokens).
- Its red "NOT FINISHED" / "PAS FINI" stamp on a batch that is not closed
  (`css/views/costs-stamp.css`).
- The receipt's "Copy as image", which carries both (`js/views/costs-image.js`).
- The Batch page's time card: a paper card, the receipt's paper, ink and shadow, one ruled line per
  round and its rubber stamps tilted (the `paper` variant and the `card-stamp-*` classes of
  `css/components/card.css`, built by `js/ui/card.js`; `js/views/batch-timecards.js`).

## A batch with no CR yet

A batch opened with no CR (paused, `crs_total` 0, `model/semantics.js`'s `noCrYet`) is drawn with
what exists and no more. The Batch page shows its four figures, the mode in the title row and the page's empty
state (`batch.no_cr_yet`), with no graph, Gantt or time cards. The Home batch card keeps its head,
replaces the bar and its legend by the same line, shows `none yet` under Spent with no meter,
`0/<total>` slots and `—` for the steering sign, never marked late. No new colour, size or class.

## The Batch page's title row

The mode (`<mode> · <steering>`, its sentence in a tooltip at every width), the "States and arrows"
legend and the Stack / Series / Parallel switch sit in the title row, built by
`js/views/batch-head.js` and styled under `.bmode` (the title row is outside `.batch`).

- No full-width band or legend line sits between the figures and the view switch.
- On a phone the switch and the legend's hint are hidden; the two pills stay.
- On a phone a tip anchors at the slot's left edge, no wider than the slot, so it stays within the
  screen.
- Both pills show `cursor: help`.
- On a live batch, each word of the Stack / Series / Parallel switch carries a tooltip on the legend
  pill's pattern (hover, focus, focus-within; `cursor: help`). The tooltip is anchored at the
  word's right edge, so it stays within the screen. It says how to ask the Chief of Staff to switch
  (`mode.switch_to`), or "This batch's mode." (`mode.current`). There is none on a closed batch. A
  click does nothing.
- No new colour, size or token.

## The Batch graph's arrows

- An arrow goes from the right edge of a CR to the middle of the left edge of the CR that waits for
  it, and arrives level.
- All of a CR's arrows share that point, under one arrowhead drawn once per CR
  (`path.head[data-to]`), never one per arrow.
- Unlit arrows are drawn behind the cards.
- On hover or focus, the lit arrows and their heads are drawn again in `--accent` in a layer above
  the cards (`svg.edges.top`, `z-index` 2, no pointer events), so an arrow that skips a level can
  be followed end to end.
- No routing around cards, and no new colour, size or token.
- Only the transitive reduction of the waits among the drawn CRs is drawn (`reducedEdges`); the
  Gantt keeps every declared wait.
- A hover still lights every declared wait's card, the implied ones included.
- A node's wait count holds every declared wait, and names them in its `title`.
- The Gantt keeps its own markers.

## The Batch graph's layout

- The levels share the central column (`flex: 1 1 0`, 180px to 300px, 30px apart); the box scrolls
  sideways only when they do not fit.
- The canvas is measured from zero at each draw, so it is as tall as the tallest drawn level.
- Within a level, cards follow a three-pass barycentre order of the drawn arrows, ties in record
  order, never a state or a time.
- A card's place changes when a wait changes or, while folded, when a CR merges or is cancelled;
  the rule that each CR keeps one place for its whole life no longer holds.
- On a live batch the merged and cancelled CRs are folded behind the "N merged" toggle chip
  (`.gbar`), unfolded back into today's levels; a closed record has no fold.
- On a level narrower than 240px the state badge shows its icon only (`graph-level` container,
  `chip.css`).
- No new colour, size or token.

## Waits on a card

A CR with an open wait (a row's or an item's `open_waits`: answer, approval, pipeline, merge) shows
one more words-only span in its card's meta line, `waits: <types>` (`card.waits`, `wait.<type>`),
built by `js/ui/item-card.js`'s `waitsMeta` for the Kanban's CR card and the shared item card
(Triage and Kanban backlog). It is plain text: no new colour, size, icon or class, and no span
with no open wait. The board only shows a wait; the steering session clears it.

## Dashboard

A read-only view whose figures come from the server's `dashboard.get` op (`board/dashboard_page.py`),
computed from the closed batch records and apart from the drawing: the views compute no figure.

- One point per closed batch, never per day. A figure a record lacks is no point (a cut line, an
  empty bar slot), never a zero, and each tile says how many batches it covers.
- Charts are drawn by the `chart` component as inline SVG (lines, and stacked bars for the stacked
  tiles), no chart library, no `style` attribute (colours reach the sheet as `data-vars`).
- Colours are existing tokens: the Costs card's part shades, `--m1` to `--m8` by the project's
  all-time model cost order (`--m8` is also "other models" when there are more than eight),
  `--queued-bar` for "not split", `--accent-light` dashed and `--state-merged` for held and merged.
- Never a series by colour alone: its word in the legend, a dash for a line, the stack's order, and
  every value in the readout. A value is read on hover, on focus and on a tap.
- The tile is the figure card; the range selector reuses `.seg` of `css/views/costs-models.css`
  unchanged (not a component; moving it is a separate CR). Every word is an i18n key of
  `en-dashboard.js` and `fr-dashboard.js`.
- No protected feature is added; the Costs page and its protected features are untouched.

## The Inbox page

The second view, after Home: what waits for the user, in one list, newest first. It reads only the
project line's `needs_you` of the `board` topic (built by the server from the record and the
backlog's waits) and draws nothing of its own: each entry is one card built by `js/ui/card.js`
(through `js/inbox/entry.js`), with its kind as a chip, a one-line title, the CR, how long it has
waited, and its actions (Open, Snooze 1 h, Later, Discard). Four kinds: question, approval, merge,
blocked; kind chips filter the list, and the filter is a preference.

- **Hides stay in the browser.** Snooze (1 hour), Later (next 08:00) and Discard (while the fact
  lasts) are kept in `localStorage` through `core/store.js`'s `pref`/`setPref`, keyed by the entry's
  `key` (one occurrence of a fact: a new occurrence has a new key and shows again). Nothing is sent
  to the server; hidden entries sit in a closed `details` below the list, with Restore.
- **The count.** The bar's Inbox badge counts the entries not hidden, of the scope shown.
  `js/model/inbox.js` is pure (no storage, no transport); `js/inbox/marks.js` writes storage only
  and never calls `update()`, so drawing the page cannot redraw it.
- **Notifications.** Off until the user turns them on from the page; a new entry then raises one
  browser notification, once (`js/inbox/watch.js`), every call guarded: a browser with none shows
  nothing and breaks nothing.
- **Look.** Tokens, the shared card, chip and column components; `css/views/inbox.css` only lays
  out. No new colour, size or side border. Words in both languages (`en-inbox.js`, `fr-inbox.js`,
  with `mr.inbox.sub` for GitLab).

## History

A read-only view (`js/views/history.js`), fed by the `history` topic only (`js/views/history-feed.js`;
no field of the project state). Its address keys are `hp` (day, week, month) and `hd` (a date), each
only when not the default. Its rows are words, the existing chip and one-line titles (the state
chip's variants only: merged, blocked, draft, ready), five plain figures, and a day head; a row opens
its CR in the side panel, its batch name goes to the Batch view and its PR number is a link. There
is no chart (charts are not this page's), and no new token, component or colour: `css/views/history.css`
only lays things out. Its every word is an i18n key of `js/i18n/en-history.js` and `fr-history.js`.

## Triage: folded rows and the writes count

Each Backlog row, P1 to P4, folds on a click on its head: `lane(parts)`'s `fold`, `folded` and
`foldLabel` parts, the `column-folded` variant and the `column-fold` chevron, a real button with
`aria-expanded` and a label in both languages. A folded row keeps its head (priority chip, count and
grill-state counts), hides its post-its, groups and empty-row text, stays a drop target and is open by
default. The choice is the device's preference `triageFolded`, the same for every project; a value
that cannot be read reads as open. No other column or lane folds, and nothing folds by itself.

The journal panel opens on three lines (what the count is, why the Chief of Staff may not know of
those writes, what to type), then the list; the button carries a one-sentence tooltip. No new colour,
size or token.

## The Help page

The `help` view sits after Home (and the Inbox) in the sidebar, the same on every project and on
"All projects", with no count. On the phone it is one more item of the bottom bar, which scrolls
sideways (`css/shell.css`'s `.bnav`, `overflow-x: auto`) when its items no longer fit a narrow
phone, so its last item stays reachable. It needs no project data (the registry's `offline`: `ui/host.js`
draws it before a record has arrived, and while the board is unreachable) and calls no op or topic.
Every word is an i18n key of `js/i18n/en-help.js` and `fr-help.js`; the topics' list (ids, group,
link to chantier's documentation) is in `js/views/help-topics.js`. A topic's card and its detail
are the one card (`help-card`, `help-detail`, the `sel` variant for the open one), laid out by
`css/views/help.css`'s grid, with no picture or diagram. The open topic is the address's `h=`:
Escape, its close button, a second click on its card or Back closes it. A close adds no history
entry (the router's `closeTopic()`), so Back never reopens a closed detail. The token table does
not change.

## The key notice

When the server refuses the page's key after the page loaded (`state.denied`: a WebSocket closed
4401, an HTTP 401, `--new-key` while the page is open, a cookie expired or cleared), the header's
notice (`ui/header.js`'s `notice`, drawn by `main.js`'s `drawNotice`) holds its line, a text field
and an "Open" button (`js/ui/key-notice.js`). "Open", or Enter in the field, navigates to the page's
own address with `k` set to the field's text; the server's exchange reads a key or a whole link,
sets its `HttpOnly` cookie and answers `303` to the same page with no `k`. The text is never kept:
no store field, no `localStorage`, no `sessionStorage`, no cookie written by script (a test reads
the scripts for it). The field and the button are the existing form controls' look (`css/shell.css`
beside `.notice`, tokens only; no new token). The server's own refusal page, shown before any page
loads (a link with no key, a browser with no cookie), belongs to the server (`board/key_page.py`),
not to this client, and shows with `--ui none` too. Another tab of the same board that is denied
too recovers at its next reload, the cookie being the browser's.

## The board's Griller

A discussion with a Griller, in the file panel, for an item of the inbox, the backlog (P1 to P4) or
`3-ready` only: never a CR of the batch or a merged one (`js/panel/griller.js`).

- **The button.** "Grill" (`data-grill`) sits in the panel's actions place, built with the existing
  button classes, filled while the discussion is on. A host that is not proved or not told gets it
  disabled, the server's reason in its `title`.
- **The discussion** replaces the file view in the document region; the tree stays, so the files the
  Griller writes appear, and a click on a file, or a second click on Grill, goes back to the files.
  It follows the `griller` topic through `js/core/transport.js` (`js/api/griller.js`), and the box
  with the typed text is kept between redraws.
- **Before the first message:** the notice (the CLI, the machine and the model the server names, the
  first message is the yes), the sentence that the conversation is shared, and the plain-HTTP warning
  with the server's command (`BOARD_COMMAND` of `js/panel/griller-view.js`, the one place that names
  it). The last two stay under the conversation once it has started.
- **Turns.** One turn at a time: while one runs, a working mark in words, the text box and Send
  disabled, and Stop for every holder of the private key; End after one confirmation, with no turn running.
  No streaming: the answer shows at the turn's end. The typed text is plain text, the answer goes
  through the panel's Markdown renderer. A turn sent from another client says so in words (the page's
  client id lives in `sessionStorage`). A turn that stopped, timed out or failed shows its one line,
  and the files it wrote, saying the turn was cut when it was. Another item's turn running disables
  Send with its project and slug.
- **Look.** `css/griller.css` lays out only, with tokens: a turn is told apart by its fill (`--band`
  for the typed text, `--panel` for the answer) and the hairline all around; no side accent, no new
  component, token or colour; states are words only. Every word is an i18n key of `en-griller.js` and
  `fr-griller.js`.
