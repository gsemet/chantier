# Verifier: the scratch project

A throwaway you make (a scratch planning folder, a probe project, a hand-run smoke run) goes under the `scratch:` folder of your facts (`<CR folder>/work/scratch`), never a temporary folder or any path outside your `writes:` folders. You remove it at your end.

- The scratch project is its own git repository: run `git init <scratch project>` before anything else there, and before any chantier command.
- Every `chantier` or `chantier serve` call aimed at it names it: `--project <the scratch project's folder>` (a scratch planning surface), or runs with the scratch repository as its working folder and no `--project` and no `CHANTIER_ROOT` that points elsewhere.
- Never use the prompt's `$CHANTIER` line as printed: it names the live project.
- The project's own tests keep their fixtures and tmp folders as they are.
- The scratch folder sits under the user's home folder: a capture of it shows the user's paths (`help verifier-images`).

A path under the scratch folder that is too long for Windows (a write, a `git` command or a tool failing on its length) is a stop. Report it to your Driver with the exact error text, as for any refusal: no shorter folder outside your `writes:` folders, no other workaround. The claim that needed the scratch project is then not proved, and the verdict follows the rule for evidence that cannot be captured.
