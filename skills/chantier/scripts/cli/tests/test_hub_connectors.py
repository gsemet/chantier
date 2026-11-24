"""The forge hub through the real connectors: an unclaimed link, a batch in two repositories, the
providers' interests and one query per repository, GitHub and GitLab. The forge's own program is
replaced (`run`), never reached."""

from __future__ import annotations

from typing import Any

import pytest
from forge_world import (
    CYCLE,
    LINK,
    MAIN,
    T1,
    World,
    crs_of,
    merged,
    shape,
    write_batch,
)

from chantier import connectors
from chantier.board.projects import project_name
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY
from chantier.connectors import github, gitlab
from chantier.connectors import run as connectors_run
from chantier.core.repo import Repo
from chantier.hub import interests, journal, state
from chantier.hub.interests import Interest

REAL_READ = connectors.read  # the seam as shipped, before `World` replaces it
A = "a" * 40


def hub_error(world: World) -> str | None:
    mine = state.live_entry(world.repo("alpha").git_dir, state.HUB)
    assert mine is not None
    error: str | None = mine["projects"]["alpha"]["error"]
    return error


def test_a_link_no_connector_claims_is_named_and_the_other_prs_are_read_and_judged(
    world: World,
) -> None:
    crs = crs_of("alpha")
    crs[1]["pr"] = "https://example.org/acme/alpha/issues/11"
    write_batch(world.project("alpha"), "running", crs)
    world.forge = {10: merged(MAIN, T1)}
    world.hub.cycle(0.0)
    assert world.calls[0] == [LINK.format("alpha", 10)]  # one call naming the claimed link
    assert hub_error(world) == connectors.UNCLAIMED.format(link=crs[1]["pr"])
    assert shape(world.journal("alpha")) == [(1, "hub", "merged@1", "CR-1", None)]
    # the link is mended: the error is cleared by the next read
    write_batch(world.project("alpha"), "running", crs_of("alpha"))
    world.hub.cycle(CYCLE)
    assert hub_error(world) is None


def test_a_batch_in_two_repositories_is_not_read_and_the_entry_says_so(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never(*a: object, **k: object) -> None:
        raise AssertionError("the forge was called")

    crs = crs_of("alpha")
    crs[1]["pr"] = LINK.format("other", 11)
    write_batch(world.project("alpha"), "running", crs)
    monkeypatch.setattr(connectors, "read", REAL_READ)
    monkeypatch.setattr(github, "run", never)
    write_batch(world.project("beta"), "paused", crs_of("beta", "merged"))  # beta: no PR open
    world.hub.cycle(0.0)
    assert hub_error(world) == NOT_ONE_REPOSITORY
    assert world.journal("alpha") == []


class Asker:
    """A test provider: its `pr` interests on alpha's first PR, asking `review`."""

    def __init__(
        self, name: str, kinds: frozenset[str], link: str = LINK.format("alpha", 10)
    ) -> None:
        self.name, self.kinds, self.link = name, kinds, link
        self.collected, self.judged, self.review = 0, 0, None

    def collect(self, repo: Repo) -> list[Interest]:
        self.collected += 1
        if project_name(repo) != "alpha":
            return []
        facts = frozenset({"state", "checks", "review"})
        return [Interest("pr", self.link, facts, "t w1", self.name)]

    def judge(self, repo: Repo, mine: list[Interest], facts: dict[str, Any]) -> list[Any]:
        self.judged += 1
        assert facts[self.link]["state"] == "open"
        self.review = facts[self.link].get("review")
        return []


def test_two_providers_interests_on_one_repository_make_one_call(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    asker = Asker("asker", frozenset({"pr"}))
    monkeypatch.setattr(interests, "PROVIDERS", (*interests.PROVIDERS, asker))
    world.hub.cycle(0.0)
    alpha = [i for i, c in enumerate(world.calls) if LINK.format("alpha", 10) in c]
    assert len(alpha) == 1 and world.calls[alpha[0]].count(LINK.format("alpha", 10)) == 1
    assert world.asked[alpha[0]] == frozenset({"review"}) and asker.judged >= 1


def test_a_provider_of_another_kind_is_not_called_and_makes_no_forge_call(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = Asker("other", frozenset({"other"}))
    monkeypatch.setattr(interests, "PROVIDERS", (other,))
    world.hub.cycle(0.0)
    assert (other.collected, other.judged, world.calls) == (0, 0, [])


GL_LINK = "https://gitlab.com/grp/alpha/-/merge_requests/{}"
GH_MR = {"state": "OPEN", "baseRefName": "main", "headRefOid": A, "mergeable": "MERGEABLE"}
GL_MR = {"state": "opened", "targetBranch": "main", "diffHeadSha": A}


class Forge:
    """The connectors' own `run`, replaced: it checks the guard, keeps each call's argv and
    answers every number asked with `node` (GitHub's or GitLab's shape)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, gitlab_nodes: dict[int, Any]) -> None:
        self.calls: list[list[str]] = []
        self.gitlab_nodes = gitlab_nodes
        monkeypatch.setattr(connectors, "read", REAL_READ)
        monkeypatch.setattr(github, "run", self.github)
        monkeypatch.setattr(gitlab, "run", self.gitlab)

    def query(self) -> str:
        return next(a for a in self.calls[-1] if a.startswith("query="))

    def github(self, program: str, call: list[str]) -> dict[str, Any]:
        connectors_run.guard(call)
        self.calls.append(call)
        got = {f"p{n}": GH_MR for n in (10, 11)}
        return {"data": {"repository": got}}

    def gitlab(self, program: str, call: list[str]) -> dict[str, Any]:
        connectors_run.guard(call)
        self.calls.append(call)
        return {"data": {"project": {f"m{n}": n_ for n, n_ in self.gitlab_nodes.items()}}}


def gitlab_alpha(world: World) -> None:
    crs = crs_of("alpha")
    for i, cr in enumerate(crs):
        cr["pr"] = GL_LINK.format(10 + i)
    write_batch(world.project("alpha"), "running", crs)
    write_batch(world.project("beta"), "paused", crs_of("beta", "merged"))


def test_a_gitlab_batch_is_read_in_one_query_and_told_as_before(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    done = {**GL_MR, "state": "merged", "mergedAt": T1}
    forge = Forge(monkeypatch, {10: done, 11: GL_MR})
    gitlab_alpha(world)
    world.hub.cycle(0.0)
    assert len(forge.calls) == 1 and forge.calls[0][-2:] == ["-f", "path=grp/alpha"]
    assert "mergeRequest(iid" in forge.query() and "reviewDecision" not in forge.query()
    (line,) = world.journal("alpha")
    assert shape([line]) == [(1, "hub", "merged@1", "CR-1", None)]
    assert journal.event_text(line) == (
        f"forge saw merged: CR-1 {GL_LINK.format(10)} into main at {T1}; "
        "for the steering session: order merged CR-1"
    )
    assert hub_error(world) is None


@pytest.mark.parametrize(("kind", "link"), [("github", LINK.format("alpha", 10)), ("gitlab", None)])
def test_an_interest_asking_review_makes_the_one_query_carry_it_where_the_forge_proves_it(
    world: World, monkeypatch: pytest.MonkeyPatch, kind: str, link: str | None
) -> None:
    forge = Forge(monkeypatch, {10: GL_MR, 11: GL_MR})
    if kind == "gitlab":
        gitlab_alpha(world)
        link = GL_LINK.format(10)
    else:
        write_batch(world.project("beta"), "paused", crs_of("beta", "merged"))
    asker = Asker("asker", frozenset({"pr"}), str(link))
    monkeypatch.setattr(interests, "PROVIDERS", (*interests.PROVIDERS, asker))
    world.hub.cycle(0.0)
    assert len(forge.calls) == 1
    assert ("reviewDecision" in forge.query()) is (kind == "github")
    assert asker.review == ("unknown" if kind == "github" else "unproved")
