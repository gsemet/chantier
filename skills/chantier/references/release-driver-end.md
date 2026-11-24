# Release driver: the end

## Release driver: the end

Once the release is out (the procedure's publication step done), every item below, in this order,
before the host's hand-back: the run is not over while one is undone, and none waits for a word
from the steering session or the user, except as the bullets above already require (a go the
procedure itself asks for: `handback blocked approval: <step>`; a failure: "Half-done irreversible
work: stop").

- [ ] `$CHANTIER release published <cr> --note "<version> <link>"`.
- [ ] The procedure's checks, and any watch of the deploys it names (a package registry, pages).
- [ ] `<work folder>/retro.md`: what went wrong or slowly, the long-term fix for each, one line
  `- [<tag>] <problem>: <long-term fix>`, the tag `project` or `chantier` as the Foreman's retro
  defines it in `foreman.md`.
- [ ] Every background task of yours stopped (a deploy watch included), as "Means: context and your folder" says.
- [ ] `$CHANTIER handback <cr> ready <release link or tag>`, then the host's hand-back, as "Means: your end" orders it (its first line is the line `handback` printed). When this release CR is the
  batch's last, `handback` also prints the merged CRs' `cleanup:` lines and `paused <batch>`: the
  CLI paused the batch; say nothing more about it.
