"""A crude stand-in for Claude, used only by tests (MDUEL_FAKE_LLM=1).

It returns well-formed replies so the whole pipeline can run without a key or network.
The content is mechanical and not meant to be good.
"""
import json
import re


def _chat_user_lines(user):
    chat = user.split("chat:", 1)[-1] if "chat:" in user else user
    return [l.split(":", 1)[1].strip() for l in chat.splitlines() if l and not l.startswith(("Assistant", "###")) and ":" in l]


def fake_complete(task, system, user):
    if task == "summary_update":
        old = user.split("Current summary:\n", 1)[-1].split("\n\nNew chat:", 1)[0]
        old = "" if old.startswith("(empty") else old
        first = (_chat_user_lines(user) or [""])[0][:120]
        return (old + " " + first).strip()[-900:]
    if task == "facts_update":
        first = (_chat_user_lines(user) or [""])[0][:100]
        return json.dumps({"add": [first] if first else [], "retire": []})
    if task == "notes_update":
        first = (_chat_user_lines(user) or [""])[0][:100]
        old = re.search(r"## Profile\n(.*?)(?:\n\n##|\Z)", user, re.S)
        text = ((old.group(1) + "\n") if old else "") + "- " + first
        return json.dumps({"ops": [{"op": "write", "note": "Profile", "text": text[-1500:]}]})
    if task == "inspect":
        keys = re.findall(r"^- (\w+) \(", user, re.M)
        return json.dumps({"states": {k: "missing" for k in keys}})
    if task == "answer":
        mem = user.split("Your memory:\n", 1)[-1].split("\n\nToday's date", 1)[0]
        line = next((l for l in mem.splitlines() if l.strip() and not l.startswith("###")), "")
        return "From memory: " + line[:160] if line and line != "(empty)" else "I don't remember that."
    if task == "judge":
        return json.dumps({"grade": "partly", "why": "Stand-in judge."})
    return "{}"
