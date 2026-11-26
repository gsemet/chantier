# The local run

Where the rules ask a local run of the long gate (`$CHANTIER rules`), a CR owes it unless a rule exempts it (checked as `help long-gate` does).
- The stack's top handed back `--no-gate`, an exemption such as docs only included: `take <cr> --note "long gate: the stack's top runs <command> locally"`, no ask.
- A parallel or series CR handed back ready with `--no-gate`, or whose record holds no passed or carried long gate at its head (`log <cr>`): `take <cr> --note "long gate: this CR runs <command> locally"`, no ask. An exempt CR does not go back.
- A waived CR that owes it and holds no pass at its head (`status` shows it `waived`) goes back the same way; its ask then carries `long gate waived: …` and the clause. A fix CR you merge under the grant owes it too.
- The ask of a CR that owes it carries, after its gaps, `local gate <cr> at <sha7>: passed`, and goes only with `passed` (`judge <cr> --local-gate` adds the clause). With no such rule, no clause.
- At a `deliver by <time>` order note (any mode), a CR not yet passed is not sent back: its ask goes as it stands with `local gate <cr> at <sha7>: not run` (or `failed`), after `no long gate: <reason>` when it has one. A gate still running is not stopped.
