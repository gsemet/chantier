# Message formats

One line each, prefixed by `[sender→receiver]`. Links are full URLs. This file is the only
definition.

## Chief of Staff → Foreman

Print an order with `$CHANTIER order …`: the line carries the order id the Foreman needs.

```text
[chief-of-staff→foreman] order O-<k> add @<prepared-folder> | order O-<k> drop <cr> | order O-<k> first <cr>
[chief-of-staff→foreman] order O-<k> change <cr> <text> | order O-<k> merged <cr>
[chief-of-staff→foreman] order O-<k> pause | order O-<k> resume
[chief-of-staff→foreman] order O-<k> fix <release-cr> @<prepared-folder> | order O-<k> approve <release-cr> <action>
[chief-of-staff→foreman] order O-<k> grant <release-cr> releases=<n> auto-merge=<method|off> budget=<usd>
[chief-of-staff→foreman] ping
```

## Foreman → Chief of Staff

```text
[foreman→chief-of-staff] ready <batch>
[foreman→chief-of-staff] ok O-<k> <what>
[foreman→chief-of-staff] ask question - <text> | ask blocked <cr> <reason> | ask refused <cr> <exact text>
[foreman→chief-of-staff] ask ready <cr> <pr-link> | ask stack-ready <cr>=<link>… | ask budget <spent>/<budget>
[foreman→chief-of-staff] ask merged <cr> <pr-link> | ask released <cr> <release link or tag>
[foreman→chief-of-staff] pong <status line>
[foreman→chief-of-staff] final <report path>
```

## Foreman → Driver

```text
[foreman→driver <cr>] round <note> | change <text> | first: you are top priority
[foreman→driver <cr>] ping: reply with your state | stop
[foreman→stack] restack
```

## Driver → Foreman

```text
[driver <cr>→foreman] hand-back ready <pr-link> | hand-back blocked <reason>
[driver <cr>→foreman] hand-back blocked question: <text> | approval: <action> | fix: <text>; <path> | infra: <text> | budget: <action>
[driver <cr>→foreman] anomaly <text>
[qa <cr>→foreman] qa done <cr> <n> findings
[stack→foreman] hand-back ready <cr>=<link>… | anomaly <cr> <text>
```

## Spawns

A spawn's prompt is not a message: `$CHANTIER spawn <role> <cr> --note "<…>"` prints it whole,
and the parent passes it unchanged.
