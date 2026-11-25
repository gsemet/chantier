# Refusals to say before they are met (part 2 of 2)

- D. "Close the batch" while something still runs: `close` is refused while a CR is not merged or cancelled, an order is open, or a stack or held agent runs or cannot be read. Ways: wait for the agent's end and run `close` again; a held agent that ended with no transcript: `agents set <cr> - --epoch <n>` on the user's word; a CR left open: merge it or `order drop <cr> --note ...` with the user's destination. More: `help refusals-to-say-more`.
