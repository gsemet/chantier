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
never stored. There are three providers:

- `batch`, of kind `pr`: the PRs of a project's running batch, while one of them is not held
  merged or cancelled. The forge hub reads them.
- `waits`, of kind `pr`: the PRs or MRs that the open approval, pipeline and merge waits of the
  running batch's CRs name (`by` is `<batch> <cr> <wait id>`), which join the same query: a wait
  met (the PR merged, the head's checks green, the review approved) becomes one `wait-cleared@1`
  line, and the steering session clears the wait. A wait on a link of another repository, one no
  connector claims, a GitLab approval (its review is `unproved`) and a backlog CR's wait are not
  read: they are cleared by hand. Waits the forge can no longer show met (a review it cannot tell,
  a head that moved past the wait's sha, a closed request) are named in the hub's entry
  (`waits_unseen`), and `wait` and `status` say so.
- `issues`, of kind `issue`: the issues the CRs' `issue:` lines name (a CR folder of any stage but
  the archives and the trash; its `ref` is the line's link, exactly as written). Only an outside
  poller reads them, never the hub: see [Writing an outside
  poller](#writing-an-outside-poller).

`chantier --project <p> interests [--kind pr|issue] [--json]` lists them, read-only.

## The budget

The forge hub reads at most once every 20 s, through the connector of its forge, one query per
project for which the registry holds a PR or MR, and only those: a project nobody waits on is not
read; and only while a client is subscribed to the server (always, for a board started with
`--forge-always` on a host that cannot run the watcher). The board's PRs page keeps its own read, at most once every 10 s per project and batch shown.
A project's PRs must sit in one repository: with two, nothing is read and the hub's error says so.

A link that no connector reads (a PR of another forge) is not read: the hub's error and the PRs
page's error line say `no connector reads <link>: chantier reads GitHub and GitLab`, and the other
PRs of the batch are read as usual.

## Adding a connector

A connector is one module in `chantier/connectors/`, one line in a table, a fake forge for the
tests, a row in [Supported hosts](hosts.md) and its forge reference. There is no install step.

1. Implement the `Connector` protocol of `connectors/base.py`: `name`, `program` (the CLI on
   PATH), `word` (`PR` or `MR`), `claims(link)` (whether the link is one of its review requests),
   `place(link)` and `number(link)`, and `read(place, numbers, facts)`: exactly one call of the
   program, read-only, for every number, through `connectors/run.py`'s `run`, which holds the
   read-only guard.
2. Add it to `CONNECTORS` in `connectors/__init__.py`. `connector_for` takes the first connector
   that claims a link, so a link is claimed by one connector only.
3. Add its fake forge to the tests (`tests/test_connectors.py` is parametrized over the connectors)
   and its row, with its `Connector` name, to the forge table of [Supported hosts](hosts.md).
4. Add its `skills/chantier/references/forges/<name>.md`, the forge's reference: its command-line
   tool and its word, as `forges/github.md` does.

A connector inside chantier's package only: none is loaded from outside it.

## Writing an outside poller

chantier's hub never reads an issue. An outside poller, your own program (a script, a cron job, a
scheduled task, a service), asks chantier which issues are awaited, polls your tracker (Jira,
GitHub, GitLab, any other) for them, and writes what it finds into the project's journal. A CR
waits for an issue when its intent or specification names it on an `issue:` line. The Chief of
Staff's watcher then tells you, in one line (`tracker saw ...`), and ends on it unless the poller
says the event wakes no one.

The contract:

1. Run `chantier --project <p> interests --kind issue --json`. Poll your tracker for each `ref`,
   once per `ref`: two CRs may name one issue. Exit 2 means the list is incomplete (see its
   `errors`).
2. For each event, run `chantier --project <p> journal add issue@1 --json -` with the payload on
   stdin. A duplicate is harmless (`journal: already there (seq <n>)`); a refusal is printed and
   nothing is written.

The payload is one JSON object with these keys and no other (`cr`, `type`, `source`, `audience`,
`folders`, `v`, `seq` and `t` are refused: chantier fills `folders` and the header):

| Key | Holds |
| --- | --- |
| `tracker` | `jira`, `github`, `gitlab` or `other` (`interests` prints it) |
| `ref` | the issue's link, as `interests` prints it |
| `event` | `opened`, `commented`, `changed`, `closed` or `reopened` |
| `at` | the tracker's time of the event, ISO 8601 (`Z` accepted), kept as given |
| `text` | one line, 1 to 300 characters: what happened, in your words |
| `wakes` | `true` (default) to wake the watcher, `false` to ride along with the next waking line |

It gives this line of the journal (see [The event journal](planning-folder.md#the-event-journal)):

```json
{"v":2,"seq":57,"t":"2026-11-20T09:15:02Z","type":"issue@1","source":"poller","audience":["project"],"tracker":"jira","ref":"https://acme.atlassian.net/browse/PAY-12","event":"commented","at":"2026-11-20T09:14:00Z","text":"a comment asks to keep the old column order","wakes":true,"folders":["2-backlog/P2/export-columns"]}
```

An event on an issue no CR names is refused (exit 2), as is a type other than `issue@1`.

The rules:

- chantier never starts, stops or supervises the poller, and sets no rate.
- Reading your tracker, read-only, and its credentials are the poller's business.
- Keep `at` as the tracker gives it: the duplicate key is `ref`, `event` and `at`.
- `text` is one line and needs no personal data.
- Run from the project's root, or the surface's root with `--project <name>`.

A short example (UTF-8, standard library only); `fetch_events` is yours:

```python
import json
import subprocess
import time

CHANTIER = ["uvx", "--from", "<chantier's plugin folder>", "chantier", "--project", "<project>"]

def fetch_events(tracker: str, ref: str) -> list[dict]:
    """Yours: this issue's events since your last poll, each {"event", "at", "text"}."""
    return []

while True:
    out = subprocess.run([*CHANTIER, "interests", "--kind", "issue", "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    refs = {i["ref"]: i["tracker"] for i in json.loads(out.stdout)["interests"]}
    for ref, tracker in refs.items():
        for e in fetch_events(tracker, ref):
            payload = json.dumps({"tracker": tracker, "ref": ref, **e})
            subprocess.run([*CHANTIER, "journal", "add", "issue@1", "--json", "-"],
                           input=payload, text=True, encoding="utf-8")
    time.sleep(300)
```
