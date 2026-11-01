"""The Foreman's decision table, driven through `chantier event` and `chantier order`."""
import json
from pathlib import Path


def batch(repo, name="b1"):
    return json.loads((repo / ".agents/changes/batches" / name / "batch.json").read_text())


def status_of(repo, cr, name="b1"):
    return next(c for c in batch(repo, name)["crs"] if c["id"] == cr)["status"]


def test_open_creates_crs_branches_and_worktrees(ready, chantier):
    d = batch(ready)
    assert [c["id"] for c in d["crs"]] == ["CR-101", "CR-102", "CR-103"]
    for c in d["crs"]:
        assert Path(c["worktree"]).is_dir()
        assert c["branch"].startswith(f"chantier/b1/{c['id'].lower()}-")
    assert (ready / ".agents/changes/batches/b1/brief.md").exists()
    assert (ready / ".agents/changes/batches/b1/crs/CR-101/task.md").read_text() == "Fix login\n"


def test_start_fills_slots(ready, chantier):
    code, out, _ = chantier("event", "start")
    assert out == ["spawn CR-101", "spawn CR-102"]
    assert status_of(ready, "CR-103") == "queued"
    assert chantier("event", "start")[1] == ["none"]  # slots full


def test_ready_hand_back_frees_a_slot(ready, chantier):
    chantier("event", "start")
    code, out, _ = chantier("event", "hand-back-ready", "CR-101", "https://github.com/acme/demo/pull/7")
    assert out == ["spawn CR-103", "ask-chief-of-staff ready CR-101 https://github.com/acme/demo/pull/7"]
    assert status_of(ready, "CR-101") == "ready"


def test_anomaly_after_hand_back_resumes_with_a_new_driver(ready, chantier):
    chantier("event", "start")
    chantier("event", "hand-back-ready", "CR-101")
    assert chantier("event", "anomaly", "CR-101", "CI red on lint")[1] == \
        ["spawn CR-101 resume round: CI red on lint"]
    assert chantier("event", "anomaly", "CR-101", "still red")[1] == ["message CR-101 round still red"]


def test_round_limit_blocks(ready, chantier):
    chantier("event", "start")
    for _ in range(3):
        chantier("report", "CR-101", "round-done")
    code, out, _ = chantier("event", "anomaly", "CR-101", "flaky")
    assert out[0].startswith("ask-chief-of-staff blocked CR-101 round limit (3)")
    assert out[1] == "spawn CR-103"


def test_lost_driver_resumes_twice_then_blocks(ready, chantier):
    chantier("event", "start")
    assert chantier("event", "driver-done", "CR-101")[1] == ["spawn CR-101 resume"]
    assert chantier("event", "driver-lost", "CR-101")[1] == ["spawn CR-101 resume"]
    out = chantier("event", "driver-lost", "CR-101")[1]
    assert out[0].startswith("ask-chief-of-staff blocked CR-101") and out[1] == "spawn CR-103"


def test_driver_done_after_hand_back_is_quiet(ready, chantier):
    chantier("event", "start")
    chantier("event", "hand-back-ready", "CR-101")
    assert chantier("event", "driver-done", "CR-101")[1] == ["none"]


def test_orders_have_ids_and_are_idempotent(ready, chantier):
    chantier("event", "start")
    code, out, _ = chantier("order", "drop", "CR-103")
    assert out == ["[chief-of-staff→foreman] order O-1 drop CR-103"]
    assert chantier("event", "--order", "O-1")[1] == ["ok O-1 drop CR-103"]
    assert chantier("event", "--order", "O-1")[1] == ["ok O-1 already done"]
    assert status_of(ready, "CR-103") == "cancelled"


def test_drop_of_a_live_cr_asks_for_a_cancel(ready, chantier):
    chantier("event", "start")
    chantier("order", "drop", "CR-101")
    assert chantier("event", "--order", "O-1")[1] == ["cancel CR-101", "ok O-1 drop CR-101"]


def test_order_add_creates_a_cr_with_a_worktree(ready, chantier):
    chantier("event", "start")
    chantier("order", "add", "--note", "Rate limit the API")
    out = chantier("event", "--order", "O-1")[1]
    assert out == ["ok O-1 add CR-104"]
    c = batch(ready)["crs"][-1]
    assert c["title"] == "Rate limit the API" and Path(c["worktree"]).is_dir()


def test_pause_and_resume(ready, chantier):
    chantier("order", "pause")
    chantier("event", "--order", "O-1")
    assert chantier("event", "start")[1] == ["none"]
    chantier("order", "resume")
    assert chantier("event", "--order", "O-2")[1] == ["ok O-2 resume", "spawn CR-101", "spawn CR-102"]


def test_first_moves_a_cr_to_the_top(ready, chantier):
    chantier("order", "first", "CR-103")
    assert chantier("event", "--order", "O-1")[1] == \
        ["ok O-1 first CR-103", "spawn CR-103", "spawn CR-101"]


def test_all_merged_lands_and_land_is_refused_while_live(ready, chantier):
    chantier("event", "start")
    code, out, err = chantier("land")
    assert code == 2 and "live ['CR-101', 'CR-102']" in err
    for cr in ("CR-101", "CR-102"):
        chantier("event", "hand-back-ready", cr)
    chantier("event", "hand-back-ready", "CR-103")
    code, _, err = chantier("land")
    assert code == 2 and "not merged ['CR-101', 'CR-102', 'CR-103']" in err
    for i, cr in enumerate(("CR-101", "CR-102", "CR-103"), 1):
        chantier("order", "merged", cr)
        out = chantier("event", "--order", f"O-{i}")[1]
    assert out == ["ok O-3 merged CR-103", "land"]
    code, out, _ = chantier("land")
    assert code == 0 and out[0] == "landed b1: cleaned 3 worktrees"
    assert not Path(batch(ready)["crs"][0]["worktree"]).exists()
    assert chantier("event", "tick", "--batch", "b1")[1] == ["none landed"]


def test_stale_foreman_epoch_is_refused(ready, chantier):
    chantier("foreman", "set", "local_aaa")
    chantier("foreman", "set", "local_bbb")
    code, _, err = chantier("event", "start", "--epoch", 1)
    assert code == 3 and "stale Foreman" in err
    assert chantier("event", "start", "--epoch", 2)[0] == 0
    assert chantier("foreman", "get")[1] == ["local_bbb epoch 2"]


def test_qa_cr_goes_through_its_qa_driver(repo, chantier):
    chantier("setup")
    chantier("open", "q1", "Checkout flow", "--qa", "all", "--slots", 1)
    chantier("event", "start")
    assert chantier("event", "hand-back-ready", "CR-101")[1] == ["spawn qa:CR-101"]
    assert chantier("event", "qa-done", "CR-101", "2 findings")[1] == ["none"]
    chantier("event", "anomaly", "CR-101", "fix the 2 QA findings")
    assert chantier("event", "hand-back-ready", "CR-101")[1] == ["spawn qa:CR-101"]
    assert chantier("event", "qa-done", "CR-101", "0")[1] == ["ask-chief-of-staff ready CR-101 no-pr"]


def test_stack_mode_starts_then_messages_the_stack_driver(repo, chantier):
    chantier("setup")
    chantier("open", "s1", "Schema", "API", "--stack", "--slots", 2)
    chantier("event", "start")
    assert chantier("event", "hand-back-ready", "CR-101")[1] == ["none"]
    out = chantier("event", "hand-back-ready", "CR-102")[1]
    assert out == ["spawn stack", "ask-chief-of-staff stack-ready CR-101=no-pr CR-102=no-pr"]
    chantier("order", "change", "CR-101", "--note", "rename the column")
    chantier("event", "--order", "O-1")
    chantier("event", "start")
    out = chantier("event", "hand-back-ready", "CR-101")[1]
    assert out[0] == "message stack restack"
    chantier("event", "driver-done", "stack")
    assert batch(repo, "s1")["stack_live"] is False


def test_budget_stops_spawning_and_asks_once(repo, chantier):
    chantier("setup")
    chantier("open", "m1", "A", "B", "C", "--slots", 1, "--budget", 1)
    chantier("event", "start")
    d_path = repo / ".agents/changes/batches/m1/batch.json"
    d = json.loads(d_path.read_text())
    d["spent_usd"] = 1.5
    d_path.write_text(json.dumps(d))
    out = chantier("event", "hand-back-ready", "CR-101")[1]
    assert out[0] == "ask-chief-of-staff budget 1.50/1.0"
    assert chantier("event", "tick")[1] == ["none"]


def test_tick_pings_silent_drivers(ready, chantier):
    chantier("event", "start")
    p = ready / ".agents/changes/batches/b1/batch.json"
    d = json.loads(p.read_text())
    d["crs"][0]["updated"] = "2020-01-01T00:00:00Z"
    p.write_text(json.dumps(d))
    out = chantier("event", "tick")[1]
    assert out[0].startswith("message CR-101 ping")


def test_unknown_event_is_a_usage_error(ready, chantier):
    code, _, err = chantier("event", "explode", "CR-101")
    assert code == 1 and "unknown event kind" in err
