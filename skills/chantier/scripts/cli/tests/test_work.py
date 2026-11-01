"""Work in a CR worktree: gates, ship, CI waits and classification, cancel."""
import json
import os
import subprocess
import time
from pathlib import Path

from conftest import sh


def cr(repo, cr_id, name="b1"):
    d = json.loads((repo / ".agents/changes/batches" / name / "batch.json").read_text())
    return next(c for c in d["crs"] if c["id"] == cr_id)


def set_gates(repo, fast=(), long=()):
    p = repo / ".agents/chantier.json"
    cfg = json.loads(p.read_text())
    cfg["gates"] = {"fast": list(fast), "long": list(long)}
    p.write_text(json.dumps(cfg))


def commit_in(wt: Path, name="feature.txt"):
    (wt / name).write_text("change\n")
    sh("git", "add", ".", cwd=wt)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "--quiet",
       "-m", f"add {name}", cwd=wt)


def body(repo, cr_id, name="b1"):
    (repo / ".agents/changes/batches" / name / "crs" / cr_id / "pr-body.md").write_text("Body\n")


def test_gate_pass_and_fail(ready, chantier):
    set_gates(ready, fast=["test -f README.md"])
    code, out, _ = chantier("gate", "CR-101")
    assert code == 0 and out[0].startswith("pass 1 fast gates")
    set_gates(ready, fast=["echo boom; exit 3"])
    code, out, _ = chantier("gate", "CR-101")
    assert code == 4 and out[0].startswith("FAIL echo boom; exit 3 (exit 3)")
    assert "boom" in out
    assert cr(ready, "CR-101")["pgids"] == []


def test_ship_opens_then_updates_the_pr(ready, chantier, gh_state):
    wt = Path(cr(ready, "CR-101")["worktree"])
    commit_in(wt)
    code, _, err = chantier("ship", "CR-101")
    assert code == 2 and "pr-body.md" in err
    body(ready, "CR-101")
    code, out, err = chantier("ship", "CR-101")
    assert code == 0, err
    assert out == ["opened https://github.com/acme/demo/pull/1 (base main)"]
    branch = cr(ready, "CR-101")["branch"]
    assert sh("git", "ls-remote", "--heads", "origin", branch, cwd=ready)
    create = next(c for c in gh_state.calls() if c[:2] == ["pr", "create"])
    assert create[create.index("--base") + 1] == "main"
    commit_in(wt, "more.txt")
    assert chantier("ship", "CR-101")[1] == ["updated https://github.com/acme/demo/pull/1 (base main)"]


def test_ship_refuses_a_dirty_worktree(ready, chantier):
    wt = Path(cr(ready, "CR-101")["worktree"])
    (wt / "README.md").write_text("edited\n")
    (wt / "loose.txt").write_text("a new file the coder forgot to add")
    body(ready, "CR-101")
    code, _, err = chantier("ship", "CR-101")
    assert code == 2 and "uncommitted" in err and "README.md" in err


def test_ship_refuses_a_forgotten_new_file(ready, chantier):
    wt = Path(cr(ready, "CR-101")["worktree"])
    commit_in(wt, "done.txt")
    (wt / "strutil.py").write_text("def f(): ...\n")
    body(ready, "CR-101")
    code, _, err = chantier("ship", "CR-101")
    assert code == 2 and "untracked files" in err and "strutil.py" in err
    (wt / ".gitignore").write_text("strutil.py\n.gitignore\n")
    assert chantier("ship", "CR-101")[0] == 0


def test_stack_ship_bases_on_the_previous_cr(repo, chantier, gh_state):
    chantier("setup")
    chantier("open", "s1", "Schema", "API", "--stack")
    first, second = cr(repo, "CR-101", "s1"), cr(repo, "CR-102", "s1")
    commit_in(Path(first["worktree"]), "schema.txt")
    body(repo, "CR-101", "s1")
    assert chantier("ship", "CR-101")[0] == 0
    commit_in(Path(second["worktree"]), "api.txt")
    body(repo, "CR-102", "s1")
    code, out, err = chantier("ship", "CR-102")
    assert code == 0, err
    assert out == [f"opened https://github.com/acme/demo/pull/2 (base {first['branch']})"]
    code, out, _ = chantier("stack", "restack")
    assert out == ["restacked 2: CR-101 CR-102"]


def test_wait_ci_pass_and_fail(ready, chantier, gh_state):
    code, _, err = chantier("wait", "ci", "CR-101")
    assert code == 2 and "no PR" in err
    chantier("report", "CR-101", "pr-opened", "https://github.com/acme/demo/pull/9")
    gh_state.set(checks_seq=[[{"name": "test", "bucket": "pending", "link": ""}],
                             [{"name": "test", "bucket": "pass", "link": ""}]])
    code, out, _ = chantier("wait", "ci", "CR-101")
    assert (code, out) == (0, ["ci pass https://github.com/acme/demo/pull/9"])
    assert cr(ready, "CR-101")["ci"] == "green" and cr(ready, "CR-101")["pids"] == []
    gh_state.set(checks_seq=None, checks=[{"name": "lint", "bucket": "fail", "link": ""}])
    code, out, _ = chantier("wait", "ci", "CR-101")
    assert code == 4 and out == ["ci fail https://github.com/acme/demo/pull/9", "failed: lint"]


def test_wait_times_out(ready, chantier, gh_state):
    chantier("report", "CR-101", "pr-opened", "https://github.com/acme/demo/pull/9")
    gh_state.set(checks=[{"name": "test", "bucket": "pending", "link": ""}])
    code, out, _ = chantier("wait", "ci", "CR-101", "--max", "0.2")
    assert code == 0 and out[0].startswith("ci timeout")


def test_ci_classify(ready, chantier, gh_state):
    chantier("report", "CR-101", "pr-opened", "https://github.com/acme/demo/pull/9")
    link = "https://github.com/acme/demo/actions/runs/123/job/4"
    gh_state.set(checks=[{"name": "e2e", "bucket": "fail", "link": link}],
                 runs=[{"name": "e2e", "conclusion": "failure", "status": "completed"}])
    assert chantier("ci", "classify", "CR-101")[1][0] == "known-red-on-main"
    gh_state.set(runs=[], log="Error: The runner has received a shutdown signal")
    assert chantier("ci", "classify", "CR-101")[1][0] == "infra"
    gh_state.set(log="AssertionError: expected 2, got 3")
    assert chantier("ci", "classify", "CR-101")[1][0] == "product"
    gh_state.set(checks=[{"name": "e2e", "bucket": "pass", "link": ""}])
    assert chantier("ci", "classify", "CR-101")[1] == ["none"]


def test_gitlab_is_refused(ready, chantier):
    p = ready / ".agents/chantier.json"
    cfg = json.loads(p.read_text())
    cfg["forge"] = "gitlab"
    p.write_text(json.dumps(cfg))
    chantier("report", "CR-101", "pr-opened", "https://gitlab.example.com/x/-/merge_requests/1")
    code, _, err = chantier("ci", "classify", "CR-101")
    assert code == 4 and "only github" in err


def test_cancel_stops_processes_in_the_worktree(ready, chantier):
    chantier("event", "start")
    wt = Path(cr(ready, "CR-101")["worktree"])
    stray = subprocess.Popen(["sleep", "300"], cwd=wt)
    group = subprocess.Popen(["sleep", "301"], start_new_session=True)
    p = ready / ".agents/changes/batches/b1/batch.json"
    d = json.loads(p.read_text())
    d["crs"][0]["pgids"] = [group.pid]
    p.write_text(json.dumps(d))
    code, out, _ = chantier("cancel", "CR-101")
    assert code == 0
    assert out[0].startswith("cancelled CR-101; stopped")
    assert out[1] == "spawn CR-103"
    for proc in (stray, group):
        deadline = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert proc.poll() is not None
    assert cr(ready, "CR-101")["status"] == "cancelled"
    assert os.getpid()  # the test process survived
