# The stack driver

You run `take stack --epoch <n>`, never the stack driver: its output goes in the stack driver's prompt, you start it, then `agents set stack <id> --epoch <n>`. The stack driver reads the stack again with `$CHANTIER stack`. `take stack` prints the stack as it stands, each CR with its base; after a partial merge what remains is another stack of the same batch, its first CR on the default branch. A fix CR is outside it; the release CR is its top; an `order add` CR goes on top. Each hand-back ends it: `agents set stack - --epoch <n>` before the next `take stack`. Steer it with `[foreman→stack] note <text>`. Its end is one native stack on the forge (on GitLab a chain of MRs checked by `forge-stack`, merged from the bottom; unproved), merged in one action from the top or one PR at a time from the bottom.

Hand-backs and asks: `help stack-asks`; other ends: `help stack-ends`.
