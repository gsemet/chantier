# GitLab forms

- Use `glab`'s option that reads the description from a file (settle the exact form from `glab mr create --help`), with no text in the command and no shell substitution such as `"$(cat file)"`. Unproved: the forge's description matching `pr-body.md` byte for byte when it holds backticks, `$` and quotes.
- Unproved on GitLab: the `draft` field on a real instance.
- Unproved on GitHub Copilot: one Driver that turns its PR ready and runs `ship`, the CR reading `ready to merge`.
