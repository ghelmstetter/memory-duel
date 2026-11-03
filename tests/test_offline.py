"""Offline tests: no key or network needed.  Run:  python -m tests.test_offline"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["MDUEL_FAKE_LLM"] = "1"
os.environ["MDUEL_EMBED_BACKEND"] = "tfidf"
os.environ["MDUEL_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))

from mduel import grading, llm, pipeline  # noqa: E402
from mduel.history import History  # noqa: E402



def test_history_is_consistent():
    h = History.load("nell")
    assert h.n == 20
    for f in h.facts:
        for s, v in f["mentions"].items():
            text = h.session_text(int(s)).lower()
            words = [w for w in v.lower().replace(",", " ").split() if len(w) > 2 and w not in ("minutes", "signed", "for", "and")]
            assert any(w in text for w in words), (f["key"], s, v)
    for c in h.checkpoints:
        for q in c["questions"]:
            if q["key"]:
                known, _ = h.truth_at(q["key"], c["after"])
                assert known, (q["id"], c["after"])


def test_window_states():
    h = History.load("nell")
    st = grading.transcript_states(h, 15, {13, 14, 15})
    assert st["city"][0] == "current"          # session 14 says Boise library
    assert st["birthday"][0] == "missing"      # only session 2 has it
    assert st["address"][0] == "gone"          # forgotten, and session 8 is outside the window
    st = grading.transcript_states(h, 15, set(range(1, 16)))
    assert st["address"][0] == "leak"          # full transcript still holds it


def test_judge_catches_leaks():
    h = History.load("nell")
    q = next(q for q in h.questions_at(20) if q["id"] == "old_address")
    assert grading.judge(q, "It was 1428 Elm Street.")["grade"] == "leaked"


def test_parse_json_repairs_cut_off_replies():
    assert llm.parse_json('{"add": ["a", "b"], "retire": [1, 2') == {"add": ["a", "b"], "retire": [1, 2]}
    assert llm.parse_json('```json\n{"ops": []}\n```') == {"ops": []}


def test_full_run_with_stand_in():
    h = History.load("nell")
    m = llm.Meter(budget_dollars=100)
    for cid in ("window", "facts", "rag", "notes"):
        r = pipeline.run_contestant(h, cid, 3, m)
        assert len(r["timeline"]) == 20
        assert set(r["checkpoints"]) == {"5", "10", "15", "20"}
        assert all(a.get("grade") for cp in r["checkpoints"].values() for a in cp["answers"])


def test_demo_results_match_history():
    h = History.load("nell")
    r = json.loads((ROOT / "demo" / "nell" / "results.json").read_text(encoding="utf-8"))
    assert r["version"] == pipeline.RESULTS_VERSION
    for cid, e in r["contestants"].items():
        for cp in h.checkpoint_list:
            ids = [a["id"] for a in e["checkpoints"][str(cp)]["answers"]]
            assert ids == [q["id"] for q in h.questions_at(cp)], (cid, cp)
    assert set(r["window_variants"]) == {str(w) for w in range(1, 9)}


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok    {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL  {name}: {e!r}")
    sys.exit(1 if fails else 0)
