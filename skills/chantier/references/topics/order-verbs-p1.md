# The orders (part 1 of 2)

Orders are the user's word. Each is one `$CHANTIER order`, applied to the state at once and printed as the line to send the Foreman (by your host's means), who does what needs its hands and marks it done; in direct mode, do what it needs yourself. For `order qa`, send the order's line and the `qa-driver prompt` block it printed, together, as printed. `status` lists the open ones, those the CLI applied apart from those nothing has touched. A CR is named `CR-<n>` or `<n>`; a second drop of a dropped CR, and a note on a cancelled one, are refused (exit 2).
- `order add --note <prepared-folder or a release's fix file> [--fix-for <release-cr> | --release]`
- `order after <cr> --note "<cr>,<cr>"`: what a queued CR waits for, `-` for none (not a release's). `--add <cr>`: one more wait, the rest kept; `--remove` takes one out. A ref is an id, slug or path.
- `order drop <cr> --note trash|ready|P1..P4`: where it goes, with its work; never the inbox; a release or fix CR: trash only (`help order-drop`)
- `order note <cr> --note "<one line: a change, an answer, a priority>"`
