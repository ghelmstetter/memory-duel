"""Imports your Hablemos lessons into Memory Duel as a chat history.

Usage (from the memory-duel folder, with Memory Duel's Python environment active, or via run.bat's .venv):
    python tools/import_hablemos.py "C:\\path\\to\\hablemos\\data\\hablemos.db"
Options:
    --name "Hablemos lessons"   name shown in Memory Duel
    --user "Greg"               your name, as the assistant would address you
    --min-turns 4               skip lessons shorter than this (e.g. ones cut off at the start)

It reads only the lessons and turns tables. It never reads the settings table, which holds
your Gemini API key. Your learner speech becomes "user" turns and the tutor's becomes
"assistant" turns; app notes ([[ ]]) are skipped. Nothing is sent anywhere by this tool.
Close Hablemos first, or copy hablemos.db somewhere and point at the copy.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mduel import datasets  # noqa: E402


def read_lessons(db_path, min_turns=4):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    lessons = con.execute("SELECT id, started_at, kind, plan_json, summary, status FROM lessons ORDER BY started_at, id").fetchall()
    sessions = []
    for les in lessons:
        turns = con.execute("SELECT role, text FROM turns WHERE lesson_id = ? ORDER BY idx", (les["id"],)).fetchall()
        msgs = [{"role": "user" if t["role"] == "learner" else "assistant", "text": t["text"].strip()}
                for t in turns if t["role"] in ("learner", "tutor") and (t["text"] or "").strip()]
        if len(msgs) < min_turns:
            continue
        topic = ""
        try:
            plan = json.loads(les["plan_json"] or "{}")
            topic = (plan.get("useIt") or {}).get("topic") or plan.get("goal") or ""
        except (ValueError, TypeError):
            pass
        if les["kind"] == "placement":
            topic = "First conversation (placement)"
        sessions.append({"date": (les["started_at"] or "")[:10], "topic": (topic or les["summary"] or f"Lesson {les['id']}")[:100],
                         "turns": msgs})
    con.close()
    return sessions


def main():
    ap = argparse.ArgumentParser(description="Import Hablemos lessons into Memory Duel.")
    ap.add_argument("db", help="path to hablemos.db")
    ap.add_argument("--name", default="Hablemos lessons")
    ap.add_argument("--user", default="the learner")
    ap.add_argument("--min-turns", type=int, default=4)
    a = ap.parse_args()
    if not Path(a.db).exists():
        sys.exit(f"Can't find {a.db}")
    sessions = read_lessons(a.db, a.min_turns)
    if not sessions:
        sys.exit("No lessons with enough turns were found.")
    data = {"name": a.name, "user": a.user,
            "description": f"{len(sessions)} Hablemos voice lessons, imported from hablemos.db. Learner speech was transcribed automatically and may contain recognition errors.",
            "sessions": sessions}
    out = datasets.create(a.name, data, a.user)
    print(f"Imported {out['sessions']} lessons as '{out['slug']}'. Open Memory Duel, pick it on the History step, and draft its answer key.")


if __name__ == "__main__":
    main()
