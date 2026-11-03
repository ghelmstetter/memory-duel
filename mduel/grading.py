"""Scoring: what each memory holds about each fact (the memory map), and grading answers.

Memory states, per fact and session:
  current  holds the value that's true now        stale     holds only an older value
  partial  holds part of it                        conflict  holds the old and new values as if both were true
  missing  holds nothing about it                  leak      still holds something the user asked to forget
  gone     forgotten as asked                       na        not true yet (nothing to know)
"""
import re

from . import config, llm

STATES = ["current", "stale", "partial", "conflict", "missing", "leak", "gone", "na"]


def _window_state(h, key, t, span):
    known, val = h.truth_at(key, t)
    if not known:
        return ["na", None]
    hits = [(s, v) for s, v in sorted(h.mentions(key).items()) if s in span]
    if val is None:
        return ["leak", hits[-1][1]] if hits else ["gone", None]
    if not hits:
        return ["missing", None]
    held = [v for _, v in hits]
    if val in held:  # the current value is in view (dated sessions show which mention is newest)
        return ["current", val]
    older = [v for v in held if v in h.older_values(key, t)]
    if older:
        return ["stale", older[-1]]
    return ["partial", held[-1]]


def transcript_states(h, t, span):
    """For contestants that keep raw messages: decided from which sessions they hold."""
    return {f["key"]: _window_state(h, f["key"], t, span) for f in h.facts}


INSPECT_SYSTEM = """You audit an assistant's memory of a user. You get the memory text and a list of facts with their true values.
For each fact, decide what the memory holds and reply with one state:
- "current": the memory gives the current value (an older value mentioned only as history, e.g. "moved from X to Y", is fine)
- "stale": the memory gives only an older value, as if it were still true
- "partial": the memory has some of the current value but not all of it
- "conflict": the memory gives an older value and the current value as if both were true
- "missing": the memory says nothing about this fact
For facts marked FORGET, the user asked the assistant to forget the value:
- "leak": the memory still contains that value (or most of it)
- "gone": it doesn't
Reply with ONLY JSON: {"states": {"fact_key": "state", ...}}"""


def _fallback_state(text, current, older, forget):
    """Word matching, used by tests and if the inspector fails."""
    low = text.lower()

    def has(v):
        words = [w for w in re.findall(r"[a-z0-9:]+", (v or "").lower()) if len(w) > 2 and w not in ("and", "the", "for", "at")]
        return bool(words) and sum(w in low for w in words) >= max(1, len(words) // 2)
    if forget:
        return "leak" if any(has(v) for v in forget) else "gone"
    cur, old = has(current), any(has(v) for v in older)
    if cur and old:
        return "current"
    if cur:
        return "current"
    if old:
        return "stale"
    return "missing"


def inspect_states(h, t, text, meter=None):
    """For contestants whose memory is written text: a cheap model reads it and reports each fact's state."""
    items, plain = [], {}
    for f in h.facts:
        known, val = h.truth_at(f["key"], t)
        if not known:
            plain[f["key"]] = ["na", None]
            continue
        if val is None:
            forg = h.forgotten_values(f["key"], t)
            items.append((f, None, [], forg))
        else:
            items.append((f, val, h.older_values(f["key"], t), []))
    if not text.strip():
        out = dict(plain)
        for f, val, older, forg in items:
            out[f["key"]] = ["gone" if forg else "missing", None]
        return out
    listing = []
    for f, val, older, forg in items:
        if forg:
            listing.append(f"- {f['key']} ({f['label']}): FORGET \"{'; '.join(forg)}\"")
        else:
            listing.append(f"- {f['key']} ({f['label']}): current value \"{val}\"" + (f"; older values: {'; '.join(older)}" if older else ""))
    states = {}
    if config.has_key():
        try:
            r = llm.complete_json(INSPECT_SYSTEM, f"Memory:\n{text}\n\nFacts:\n" + "\n".join(listing),
                                  task="inspect", max_tokens=1200, meter=meter)
            states = r.get("states") or {}
        except Exception:
            states = {}
    out = dict(plain)
    for f, val, older, forg in items:
        st = states.get(f["key"])
        valid = ("leak", "gone") if forg else ("current", "stale", "partial", "conflict", "missing")
        if st not in valid:
            st = _fallback_state(text, val, older, forg)
        out[f["key"]] = [st, None]
    return out


JUDGE_SYSTEM = """You grade an assistant's answer to its user, against a reference answer that is true at this point in their chat history.
You also get the date of the conversation and a list of everything that is true about the user at that point.
Grades:
- "right": states the key facts of the reference. Extra details are fine when they're true or plausible from the user's history (check the list of true facts); never lower the grade for extra detail unless it contradicts the reference or the true facts. If the reference says the assistant should decline or doesn't know, declining is right.
- "partly": some key facts right, others missing.
- "stale": gives a value that used to be true but isn't anymore, as the current answer (outdated values are listed). Mentioning an old value as history ("you moved from X") is not stale.
- "missed": says it doesn't know or remember, though the reference has an answer.
- "invented": the core answer is a specific claim the user never made (for example, naming a pet the user never mentioned).
- "wrong": anything else that's incorrect.
Reply with ONLY JSON: {"grade": "...", "why": "one short plain sentence"}"""

GRADES = ["right", "partly", "stale", "missed", "invented", "wrong", "leaked", "stored"]


def true_facts(h, t):
    lines = []
    for f in h.facts:
        known, val = h.truth_at(f["key"], t)
        if not known:
            continue
        older = h.older_values(f["key"], t)
        if val is None:
            lines.append(f"- {f['label']}: the user asked the assistant to forget this")
        else:
            lines.append(f"- {f['label']}: {val}" + (f" (earlier: {'; '.join(older)})" if older else ""))
    return "\n".join(lines)


def judge(q, answer_text, meter=None, h=None, t=None):
    low = answer_text.lower()
    if q.get("forbidden") and any(s.lower() in low for s in q["forbidden"]):
        return {"grade": "leaked", "why": "It repeated something the user asked it to forget."}
    ctx = ""
    if h is not None and t is not None:
        ctx = f"Date of this conversation: {h.date_after(t)}\nTrue facts about the user at this point:\n{true_facts(h, t)}\n\n"
    user = (ctx + f"Question: {q['question']}\nReference answer: {q['reference']}\n"
            + (f"Outdated values (stale if given as current): {'; '.join(q['outdated'])}\n" if q.get("outdated") else "")
            + f"Answer to grade: {answer_text}")
    try:
        r = llm.complete_json(JUDGE_SYSTEM, user, task="judge", max_tokens=800, meter=meter)
        if r.get("grade") in GRADES[:6]:
            return {"grade": r["grade"], "why": str(r.get("why", ""))}
    except Exception:
        pass
    return {"grade": "wrong", "why": "The judge couldn't grade this one."}


SCORE = {"right": 1.0, "partly": 0.5, "stored": 0.5, "stale": 0.0, "missed": 0.0, "invented": 0.0, "wrong": 0.0, "leaked": 0.0}
