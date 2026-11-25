# The release's end

Once the publication step is done, every item below, in this order, before the host's hand-back; none waits for a word, except a go the procedure asks (`handback blocked approval: <step>`) or a failure.
- [ ] `$CHANTIER release published <cr> --note "<version> <link>" --lease <n>`.
- [ ] The procedure's checks, and any watch of the deploys it names (a package registry, pages).
- [ ] `<work folder>/retro.md`: what went wrong or slowly, the long-term fix for each, one line `- [<tag>] <problem>: <long-term fix>`, the tag `project` or `chantier`.
- [ ] Every background task of yours stopped (`$CHANTIER host stop-own-background-task`), a deploy watch included.
- [ ] `$CHANTIER handback <cr> ready <release link or tag> --lease <n>`, then the host's hand-back, its first line the line `handback` printed. When this release is the batch's last CR, `handback` also prints the merged CRs' `cleanup:` lines and `paused <batch>`; say nothing more about it.
