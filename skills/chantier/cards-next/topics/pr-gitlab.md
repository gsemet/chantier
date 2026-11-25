# GitLab forms

- Use `glab`'s option that reads the description from a file (settle the exact form from `glab mr create --help`), with no text in the command and no shell substitution such as `"$(cat file)"`. Unproved; trial: an MR opened and edited from `pr-body.md` whose body holds backticks, `$` and quotes, with the description on the forge matching the file byte for byte.
- Unproved on GitLab: the `draft` field on a real instance; trial: one `ship` of a draft MR and of a ready MR, the recorded draft state matching the forge.
- Unproved on GitHub Copilot: one Driver that turns its PR ready and runs `ship`, the CR reading `ready to merge`.
