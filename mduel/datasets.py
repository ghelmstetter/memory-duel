"""Your own chat histories: importing them, drafting an answer key with Claude, and saving edits.

An imported history starts with sessions only. The answer key (facts with the session each
became true, and checkpoint questions) is drafted by Claude, then reviewed and edited by you.
"""
import json
import re
import shutil
import threading
import time
import traceback
import uuid

from . import config, llm
from .history import History

QUESTION_TYPES = {
    "recall": "Recall", "update": "Update", "time_order": "Time order", "combining": "Combining facts",
    "forgetting": "Forgetting", "false_memory": "False memory",
}
MAX_FACTS = 12


def _slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40] or "history"
    base, i = s, 2
    while (config.DATASETS_DIR / s).exists() or (config.DEMO_DIR / s).exists():
        s = f"{base}-{i}"
        i += 1
    return s


def _role(r):
    r = str(r or "").lower()
    if r in ("user", "human", "learner", "me"):
        return "user"
    if r in ("assistant", "ai", "bot", "tutor", "model", "claude", "gpt"):
        return "assistant"
    return None


def normalize(data, name=None):
    """Accept a Memory Duel history.json, or a simple chats file, and return a history dict.

    Simple formats accepted:
      [{"date": "...", "topic": "...", "turns": [{"role": "user", "text": "..."}, ...]}, ...]
      {"name": "...", "user": "...", "sessions": [ ...same... ]}
    Also accepted per turn: "content" for "text"; roles human/ai/learner/tutor.
    """
    if isinstance(data, list):
        data = {"sessions": data}
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list) or not data["sessions"]:
        raise ValueError("The file needs a list of sessions, each with a list of turns. See the user guide for the format.")
    sessions = []
    for i, s in enumerate(data["sessions"]):
        turns = []
        for t in (s.get("turns") or s.get("messages") or []):
            role = _role(t.get("role") or t.get("speaker"))
            text = str(t.get("text") or t.get("content") or "").strip()
            if role and text:
                turns.append({"role": role, "text": text})
        if turns:
            sessions.append({"n": len(sessions) + 1, "date": str(s.get("date") or "")[:10],
                             "topic": str(s.get("topic") or s.get("title") or f"Session {len(sessions) + 1}")[:120], "turns": turns})
    if not sessions:
        raise ValueError("No sessions with user or assistant messages were found in the file.")
    out = {
        "name": name or data.get("name") or "My history",
        "user": data.get("user") or "the user",
        "description": data.get("description") or f"{len(sessions)} imported chat sessions.",
        "sessions": sessions,
        "facts": data.get("facts") or [],
        "checkpoints": data.get("checkpoints") or [],
        "question_types": QUESTION_TYPES,
    }
    for c in out["checkpoints"]:
        c["after"] = int(c["after"])
    return out


def create(name, data, user=None):
    hist = normalize(data, name)
    if user:
        hist["user"] = user
    slug = _slugify(hist["name"])
    d = config.DATASETS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "history.json").write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"slug": slug, "sessions": len(hist["sessions"])}


def delete(slug):
    d = config.DATASETS_DIR / slug
    if not d.exists():
        raise ValueError("Only histories you added can be deleted.")
    shutil.rmtree(d)
    r = config.RESULTS_DIR / f"{slug}.json"
    if r.exists():
        r.unlink()


def save_key(slug, facts, checkpoints, user=None, name=None, reviewed=False):
    d = config.DATASETS_DIR / slug
    p = d / "history.json"
    if not p.exists():
        raise ValueError("Only histories you added can be edited.")
    hist = json.loads(p.read_text(encoding="utf-8"))
    n = len(hist["sessions"])
    clean_facts, keys = [], set()
    for f in facts:
        key = re.sub(r"[^a-z0-9_]+", "_", str(f.get("key") or f.get("label") or "").lower()).strip("_")[:40]
        if not key or key in keys:
            continue
        truth = []
        for s, v in f.get("truth") or []:
            s = int(s)
            if 1 <= s <= n:
                truth.append([s, None if v in (None, "") else str(v)])
        truth.sort(key=lambda x: x[0])
        if not truth:
            continue
        keys.add(key)
        mentions = {str(int(s)): str(v) for s, v in (f.get("mentions") or {}).items() if v and 1 <= int(s) <= n}
        for s, v in truth:  # every change is also a mention
            if v is not None:
                mentions.setdefault(str(s), v)
        clean_facts.append({"key": key, "label": str(f.get("label") or key)[:40], "truth": truth, "mentions": mentions})
    clean_cps = []
    for c in checkpoints:
        after = int(c["after"])
        if not 1 <= after <= n:
            continue
        qs = []
        for i, q in enumerate(c.get("questions") or []):
            if not str(q.get("question") or "").strip():
                continue
            qs.append({"id": re.sub(r"[^a-z0-9_]+", "_", str(q.get("id") or f"q{i + 1}").lower())[:40] or f"q{i + 1}",
                       "type": q.get("type") if q.get("type") in QUESTION_TYPES else "recall",
                       "key": q.get("key") if q.get("key") in keys else None,
                       "question": str(q["question"]).strip(), "reference": str(q.get("reference") or "").strip(),
                       "outdated": [str(x).strip() for x in (q.get("outdated") or []) if str(x).strip()],
                       "forbidden": [str(x).strip() for x in (q.get("forbidden") or []) if str(x).strip()]})
        if qs:
            clean_cps.append({"after": after, "questions": qs})
    clean_cps.sort(key=lambda c: c["after"])
    hist["facts"], hist["checkpoints"] = clean_facts, clean_cps
    if user:
        hist["user"] = user
    if name:
        hist["name"] = name
    if reviewed:
        hist["key_reviewed"] = True
    p.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    old = config.RESULTS_DIR / f"{slug}.json"  # results graded against the old key no longer apply
    if old.exists():
        old.unlink()
    return {"facts": len(clean_facts), "questions": sum(len(c["questions"]) for c in clean_cps)}


# ---------------- drafting the answer key with Claude ----------------
EVENTS_SYSTEM = """You help build the answer key for a memory test. A user has many chats with an assistant. You read one chat, plus the facts about the user known so far, and list what this chat establishes or changes about the user's life.
Only durable facts the user states about themselves or the people, pets and things in their life: where they live, work, family, pets, health or diet, plans with dates, preferences, goals, and so on. Facts may be stated in any language; write values in English.
Skip the details of tasks the assistant helped with, and anything only the assistant said.
- "new": a fact not in the list yet. Pick a short snake_case key and a short label.
- "update": a fact in the list changes or is corrected. Reuse its key.
- "forget": the user asks the assistant to forget it. Reuse its key; value is empty.
Keep values short (a few words). At most 6 events. If nothing durable comes up, return an empty list.
Reply with ONLY JSON: {"events": [{"kind": "new"|"update"|"forget", "key": "...", "label": "...", "value": "..."}]}"""

QUESTIONS_SYSTEM = """You write quiz questions for a memory test. An assistant has chatted with a user many times; at this checkpoint it will be asked questions, in the user's own voice, that it can only answer if it remembers earlier chats.
You get the facts about the user as of this checkpoint, with how each one changed over time.
Write 6 to 9 questions, mixing these types where the facts allow:
- "recall": a fact that hasn't changed. ("When is my birthday?")
- "update": a fact that changed; the reference is the current value, and the outdated values are listed. ("Where do I live?")
- "time_order": what came before a change. ("What did I do before my current job?")
- "combining": needs two facts or a fact and its history. ("Is my commute longer than it used to be?")
- "forgetting": only for facts the user asked to forget. The reference says the assistant should decline. List words from the forgotten value under "forbidden".
- "false_memory": ask about something plausible the user never mentioned. The reference says it should say it doesn't know.
Write questions as the user would ask them, in English. Each question's "key" is the fact it tests (null for false_memory).
Reply with ONLY JSON: {"questions": [{"id": "short_snake_id", "type": "...", "key": "...", "question": "...", "reference": "...", "outdated": [], "forbidden": []}]}"""

JOBS = {}


def draft_estimate(slug):
    h = History.load(slug)
    p = config.PRICES[config.ANSWER_MODEL]
    tin = sum(h.session_tokens) + h.n * 900 + 4 * 1500
    tout = h.n * 200 + 4 * 900
    return {"dollars": round((tin * p[0] + tout * p[1]) / 1e6, 3), "sessions": h.n, "model": config.ANSWER_MODEL}


def start_draft(slug, fresh=False):
    if not config.has_key():
        raise PermissionError("Drafting an answer key needs an Anthropic API key in your .env file.")
    if not (config.DATASETS_DIR / slug / "history.json").exists():
        raise ValueError("Only histories you added can get a drafted answer key.")
    job_id = uuid.uuid4().hex[:10]
    h = History.load(slug)
    job = {"id": job_id, "slug": slug, "status": "running", "started": time.time(), "done": 0, "total": h.n + 4,
           "stage": "reading sessions", "error": None, "meter": None}
    JOBS[job_id] = job
    threading.Thread(target=_draft, args=(slug, job, fresh), daemon=True).start()
    return job


def draft_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        raise ValueError("That draft isn't running any more (the app may have restarted).")
    return {**job, "elapsed": round(time.time() - job["started"], 1)}


def checkpoint_sessions(n):
    return sorted({max(1, round(n * k / 4)) for k in (1, 2, 3, 4)})


def _draft(slug, job, fresh):
    meter = llm.Meter(budget_dollars=config.MAX_RUN_DOLLARS, fresh=fresh)
    try:
        h = History.load(slug)
        facts = {}   # key -> {key, label, truth: [[s, v]], events}
        for t in range(1, h.n + 1):
            job["stage"] = f"reading session {t} of {h.n}"
            known = "\n".join(f"- {f['key']} ({f['label']}): {f['truth'][-1][1] if f['truth'][-1][1] is not None else '(forgotten)'}"
                              for f in facts.values()) or "(none yet)"
            user = f"Facts known so far:\n{known}\n\nChat:\n{h.session_text(t)}"
            try:
                r = llm.complete_json(EVENTS_SYSTEM, user, model=config.ANSWER_MODEL, task="key_events", max_tokens=1500, meter=meter)
            except ValueError:
                r = {"events": []}
            for ev in (r.get("events") or [])[:6]:
                if not isinstance(ev, dict):
                    continue
                key = re.sub(r"[^a-z0-9_]+", "_", str(ev.get("key") or "").lower()).strip("_")[:40]
                if not key:
                    continue
                kind = ev.get("kind")
                val = str(ev.get("value") or "").strip()
                if key not in facts:
                    if kind == "forget" or not val:
                        continue
                    facts[key] = {"key": key, "label": str(ev.get("label") or key.replace("_", " ").capitalize())[:40], "truth": [], "events": 0}
                f = facts[key]
                v = None if kind == "forget" else val
                if f["truth"] and f["truth"][-1][0] == t:
                    f["truth"][-1][1] = v
                elif not f["truth"] or f["truth"][-1][1] != v:
                    f["truth"].append([t, v])
                f["events"] += 1
            job["done"] += 1
            if meter.over_budget():
                raise llm.BudgetExceeded(f"Stopped: drafting passed the ${meter.budget:.2f} budget.")
        # keep the facts that make the best test: ones that changed or were forgotten first
        ranked = sorted(facts.values(), key=lambda f: (-(len(f["truth"]) > 1), -any(v is None for _, v in f["truth"]), f["truth"][0][0]))
        chosen, unused = ranked[:MAX_FACTS], ranked[MAX_FACTS:]
        out_facts = [{"key": f["key"], "label": f["label"], "truth": f["truth"],
                      "mentions": {str(s): v for s, v in f["truth"] if v is not None}} for f in chosen]
        checkpoints = []
        for cp in checkpoint_sessions(h.n):
            job["stage"] = f"writing questions for session {cp}"
            lines = []
            for f in out_facts:
                hist = [(s, v) for s, v in f["truth"] if s <= cp]
                if not hist:
                    continue
                desc = "; ".join(f"from session {s}: {v if v is not None else 'ASKED TO FORGET'}" for s, v in hist)
                lines.append(f"- {f['key']} ({f['label']}): {desc}")
            user = f"Checkpoint: after session {cp} of {h.n}.\nFacts so far:\n" + ("\n".join(lines) or "(none)")
            try:
                r = llm.complete_json(QUESTIONS_SYSTEM, user, model=config.ANSWER_MODEL, task="key_questions", max_tokens=3000, meter=meter)
                qs = r.get("questions") or []
            except ValueError:
                qs = []
            checkpoints.append({"after": cp, "questions": qs})
            job["done"] += 1
        save_key(slug, out_facts, checkpoints)
        p = config.DATASETS_DIR / slug / "history.json"
        hist = json.loads(p.read_text(encoding="utf-8"))
        hist["unused_facts"] = [{"key": f["key"], "label": f["label"], "truth": f["truth"]} for f in unused]
        hist["key_drafted"] = True
        hist["key_reviewed"] = False
        p.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
        job["status"] = "done"
    except Exception as e:
        traceback.print_exc()
        from .pipeline import friendly_error
        job["error"] = friendly_error(e)
        job["status"] = "failed"
    job["meter"] = meter.as_dict()
    job["stage"] = "done" if job["status"] == "done" else "failed"

