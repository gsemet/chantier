# Style guide for the docs site

For whoever writes or reviews a page of the site (every page under `docs/`, except `docs/demo/`,
`docs/release-notes/` and the `*-texts.md` files). Each rule has an id: the review table and the
Inspector's items cite it. A bad example is quoted from a page as it was before the review.

## Structure

- **S1. One kind per page.** A page is a tutorial, a how-to guide, an explanation or a reference,
  sits in that section's folder and does not mix kinds. A how-to does not stop to explain the
  design, an explanation gives no steps, a reference lists and does not argue. Link the other kind.
- **S2. The reader is the user of chantier**, called "you". What the agents do among themselves
  (CLI subcommands only agents run, record fields, card rules) appears only where you see its
  effect, in your terms, with a link to the card on GitHub for the detail.
  - Bad: "`handback ready` requires it passed at the PR's head, and `ship` proves it by patch-ids."
  - Good: "The Driver does not open the PR until the long gate has passed at its head."
- **S3. The opening says what the page gives you**, in one or two sentences, and does not restate
  the title. No second introduction after it.
  - Bad: title "Your gates", then "The fast gate and the long gate that guard every change, and how
    to declare them." then "Two checks guard every change, in any project."
  - Good: "Declare the two checks that guard every change, in your `AGENTS.md`."
- **S4. No closing summary** that repeats the page. End on the last useful line or a "Next" link.
- **S5. A figure or a table where it reads better**: a flow of more than three steps, or a
  comparison of more than two items, gets an existing figure or a table.

## Sentences

- **S6. Short sentences**: one idea each. Split a sentence over 35 words.
  - Bad: "The long gate: the full check the Driver runs once before the PR with `chantier gate`, as
    many at once as your `chantier.yaml` allows (one by default, see below); when more wait, the CR
    you merge next goes first in a stack or series batch, then those the Foreman moved first, then
    arrival order."
  - Good: "The long gate is the full check, run once before the PR. It runs one at a time unless
    your `chantier.yaml` allows more. When several wait, the CR you merge next goes first."
- **S7. Exact terms, one meaning per word.** Use the words of the glossary
  (`skills/chantier/references/concepts.md`, "Words") with their meaning there. Say a term you have
  not met yet in plain words, or link it, at its first use on the page.
  - Bad: "the agent", "the worker" and "the session" for one role in one page.
  - Good: "the Driver", every time.
- **S8. A claim that can be checked, or nothing**: a number, a command, a file, a named behaviour.
  No hedge ("may help to", "in many cases", "it is worth noting") where the fact is known.
  - Bad: "It should take seconds to a minute."
  - Good: "Keep it under a minute: lint, type check, the tests near the change."
- **S9. No filler or hype words**: "seamless", "robust", "powerful", "leverage", "delve",
  "effortlessly", "comprehensive", "cutting-edge", "streamline", "unlock".
- **S10. No "simply", "just" or "easily" before a step.**
  - Bad: "Just run `claude plugin install`." Good: "Run `claude plugin install`."
- **S11. No triplets of adjectives**, no "not only ... but also" rhetoric.
- **S12. A sentence where a sentence says it**: no bullet list of fragments for one idea. A list is
  for items of the same kind.
  - Bad: three bullets, each a fragment of one explanation. Good: one short paragraph.

## Form

- **S13. Bold only for a term at its definition or a label in a list item**, never scattered
  through prose. No emoji in headings or prose.
- **S14. Visual elements with a purpose.** `sphinx-design` tabs where a page gives the same step
  for Claude Code and GitHub Copilot; cards on the home and the section indexes; an admonition
  (`note`, `warning`) only for what you must not miss, a few per page at most.
- **S15. Every image has alt text** that says what it shows, not its file name.
  - Bad: `![diagram](a.svg)`. Good: `![How a CR moves from the inbox to a merged PR](a.svg)`.
- **S16. Commands are copyable**: a fenced block with its language, one command per line, no
  prompt sign, so `sphinx-copybutton` copies what runs.
  - Bad: a block holding `$ uv sync` and a comment. Good: a block holding `uv sync`.

## Review

Check a page against S1 to S16 in order. Record, per page, the ids it broke and what changed. A
statement that is false against the cards or the CLI is not rewritten in a style fix: report it.
