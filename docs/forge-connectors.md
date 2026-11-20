# Forge connectors

How chantier reads a forge, and how to add one. chantier polls the forge (it has no webhook), but
only for what someone waits on, and only read-only, with your own `gh` or `glab` login.

## What a connector reads

A connector reads through its program's GraphQL API, and only these facts of the PRs or MRs it is
asked about (and, for GitHub, the default branch's workflow folder and its last 100 commits, which
the facts need):

| Fact | GitHub (`gh api graphql`) | GitLab (`glab api graphql`) | Asked by |
| --- | --- | --- | --- |
| `state`, `conflicting`, `checking`, `base`, `head`, times | the PR's fields | the MR's fields | always |
| `checks` (green, failing, running, none) | `statusCheckRollup` of the head | `headPipeline.status` | always |
| `merged_on_default` | the merge commit is in the default branch's history | always null | always |
| `review` | `reviewDecision`: `approved`, `changes-requested`, `required`, or `unknown` (null: GitHub answers null both with no required review and when it cannot tell, so it never means approved) | `unproved` (GitLab's approvals are not proved yet), no field added to the query | an interest that asks for it |

A connector never reads an issue, a comment, a user, a diff or a file's content, and never writes:
the one function that calls the program refuses anything but `api [--hostname <host>] graphql`
with a `query` and no `mutation`.

## Who waits: the interest registry

An interest is a PR or MR someone waits for: its link (`ref`), the facts wanted, and who waits
(`by`, such as `batch-29 CR-3`). Each provider declares the interests of one kind of waiter and
judges them against what the forge said. The registry is derived at each cycle from the record,
never stored. Today there is one provider, `batch`: the PRs of a project's running batch, while
one of them is not held merged or cancelled.

## The budget

The forge hub reads at most once every 20 s, through the connector of its forge, one query per
project for which the registry holds a PR or MR, and only those: a project nobody waits on is not
read. The board's PRs page keeps its own read, at most once every 10 s per project and batch shown.
A project's PRs must sit in one repository: with two, nothing is read and the hub's error says so.

A link that no connector reads (a PR of another forge) is not read: the hub's error and the PRs
page's error line say `no connector reads <link>: chantier reads GitHub and GitLab`, and the other
PRs of the batch are read as usual.

## Adding a connector

A connector is one module in `chantier/connectors/`, one line in a table, a fake forge for the
tests and a row in [Supported hosts](hosts.md). There is no install step.

1. Implement the `Connector` protocol of `connectors/base.py`: `name`, `program` (the CLI on
   PATH), `word` (`PR` or `MR`), `claims(link)` (whether the link is one of its review requests),
   `place(link)` and `number(link)`, and `read(place, numbers, facts)`: exactly one call of the
   program, read-only, for every number, through `connectors/run.py`'s `run`, which holds the
   read-only guard.
2. Add it to `CONNECTORS` in `connectors/__init__.py`. `connector_for` takes the first connector
   that claims a link, so a link is claimed by one connector only.
3. Add its fake forge to the tests (`tests/test_connectors.py` is parametrized over the connectors)
   and its row, with its `Connector` name, to the forge table of [Supported hosts](hosts.md).

A connector inside chantier's package only: none is loaded from outside it.
