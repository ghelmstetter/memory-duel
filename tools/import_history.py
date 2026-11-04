"""Imports a chat history into Memory Duel from the command line.

Usage (from the memory-duel folder):
    .venv\\Scripts\\python tools\\import_history.py FILE [--name "My chats"] [--user "Your name"]

FILE can be any of these; the format is detected automatically:
  - A ChatGPT export: conversations.json from Settings > Data controls > Export data
  - A Claude export: conversations.json from Settings > Privacy > Export data
  - A simple JSON or JSON Lines file of sessions, the same format the page's import accepts:
      [{"date": "2026-10-20", "topic": "...", "turns": [{"role": "user", "text": "..."}, ...]}]

Each conversation (or lesson) becomes one session, in date order.
Options:
    --name        name shown in Memory Duel
    --user        your name, as the assistant would address you
    --min-turns   skip sessions with fewer turns than this (default 2)
    --since       only sessions on or after this date (YYYY-MM-DD)
    --limit       keep only the most recent N sessions (big exports can have hundreds)
Nothing is sent anywhere by this tool. Text is sent to the Anthropic API only later, when you
draft an answer key or run the duel in the app.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mduel import datasets  # noqa: E402


def _date(v):
    if v in (None, ""):
        return ""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")
    return str(v)[:10]


def _text(content):
    """Message content in the ChatGPT or Claude export: a string, a list of parts, or a dict."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(c) for c in content if c is not None).strip()
    if isinstance(content, dict):
        if isinstance(content.get("parts"), list):
            return "\n".join(p for p in content["parts"] if isinstance(p, str)).strip()
        if content.get("type") in (None, "text") and isinstance(content.get("text"), str):
            return content["text"]
    return ""


# ---------------- formats ----------------
def from_chatgpt(convs, min_turns):
    sessions = []
    for c in convs:
        mapping = c.get("mapping") or {}
        # follow the branch that was showing when the chat was exported
        node, chain = c.get("current_node"), []
        while node and node in mapping:
            chain.append(mapping[node])
            node = mapping[node].get("parent")
        msgs = []
        for n in reversed(chain):
            m = n.get("message") or {}
            role = (m.get("author") or {}).get("role")
            if role not in ("user", "assistant") or (m.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
                continue
            text = _text(m.get("content")).strip()
            if text:
                msgs.append({"role": role, "text": text})
        if len(msgs) >= min_turns:
            sessions.append({"date": _date(c.get("create_time")), "topic": (c.get("title") or "Chat")[:100], "turns": msgs})
    return sessions, len(convs), "Chats exported from ChatGPT."


def from_claude(convs, min_turns):
    sessions = []
    for c in convs:
        msgs = []
        for m in c.get("chat_messages") or []:
            role = {"human": "user", "assistant": "assistant"}.get(m.get("sender"))
            text = (m.get("text") or _text(m.get("content"))).strip()
            if role and text:
                msgs.append({"role": role, "text": text})
        if len(msgs) >= min_turns:
            sessions.append({"date": _date(c.get("created_at")), "topic": (c.get("name") or "Chat")[:100], "turns": msgs})
    return sessions, len(convs), "Chats exported from Claude."


def load(path, min_turns):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = [json.loads(l) for l in text.splitlines() if l.strip()]  # JSON Lines
    mt = min_turns if min_turns is not None else 2
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if "mapping" in data[0]:
            return from_chatgpt(data, mt), "ChatGPT export", None
        if "chat_messages" in data[0]:
            return from_claude(data, mt), "Claude export", None
    hist = datasets.normalize(data)  # the simple format
    sessions = [s for s in hist["sessions"] if len(s["turns"]) >= mt]
    named = isinstance(data, dict) and data.get("name")
    return (sessions, len(hist["sessions"]), hist.get("description") or ""), "chat file", named


def main():
    ap = argparse.ArgumentParser(description="Import a chat history into Memory Duel.")
    ap.add_argument("file", help="ChatGPT or Claude conversations.json, or a JSON file of sessions")
    ap.add_argument("--name")
    ap.add_argument("--user", default="the user")
    ap.add_argument("--min-turns", type=int)
    ap.add_argument("--since", help="only sessions on or after this date (YYYY-MM-DD)")
    ap.add_argument("--limit", type=int, help="keep only the most recent N sessions")
    a = ap.parse_args()
    if not Path(a.file).exists():
        sys.exit(f"Can't find {a.file}")
    (sessions, total, desc), kind, named = load(a.file, a.min_turns)
    sessions.sort(key=lambda s: s["date"] or "")
    if a.since:
        sessions = [s for s in sessions if (s["date"] or "") >= a.since]
    if a.limit:
        sessions = sessions[-a.limit:]
    if not sessions:
        sys.exit(f"Read a {kind} with {total} session{'s' if total != 1 else ''}, but none were kept. Short sessions are skipped: "
                 "add --min-turns 1 to include them. (A useful memory test needs many sessions, ideally 10 or more.)")
    name = a.name or named or {"ChatGPT export": "My ChatGPT chats", "Claude export": "My Claude chats"}.get(kind, Path(a.file).stem)
    data = {"name": name, "user": a.user, "description": f"{len(sessions)} sessions. {desc}".strip(), "sessions": sessions}
    out = datasets.create(name, data, a.user)
    print(f"Read a {kind}: imported {out['sessions']} of {total} sessions as '{out['slug']}'.")
    if out["sessions"] > 60:
        print("That's a lot of sessions: drafting an answer key costs about a cent each. --since or --limit can trim it.")
    print("Open Memory Duel (or refresh the page), pick it on the History step, and draft its answer key.")


if __name__ == "__main__":
    main()
