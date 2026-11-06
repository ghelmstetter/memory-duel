"""Builds demo/nell/results.json: the saved results the keyless demo shows.

These are SCRIPTED, not live: they show how each strategy typically behaves, so the demo
works with no API key. Three contestants are computed from the real text:
  - full transcript and sliding window: which sessions they hold
  - RAG: a real word-matching search over the past messages for each question
The other three (rolling summary, fact memory, self-editing notes) need a model to write their
memory, so their memory contents below are written by hand, including typical mistakes.

To replace these with real results from your own run: run the duel live in the app, then
  python tools/build_demo.py --from-live
which copies data/results/nell.json into the demo.

Run from the project folder:  python tools/build_demo.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MDUEL_EMBED_BACKEND", "tfidf")

from mduel import config, grading  # noqa: E402
from mduel.contestants import INFO, Full, Rag, Window  # noqa: E402
from mduel.history import History  # noqa: E402
from mduel.pipeline import RESULTS_VERSION  # noqa: E402
from mduel.textutil import approx_tokens  # noqa: E402

OUT = ROOT / "demo" / "nell" / "results.json"
P_ANS = config.PRICES[config.ANSWER_MODEL]
P_WORK = config.PRICES[config.WORK_MODEL]
ANSWER_SYS = 250  # tokens of instructions around the memory

h = History.load("nell")
N = h.n
CPS = h.checkpoint_list

# ---------------------------------------------------------------- hand-written memories
# Fact memory: what an extractor wrote after each session. Typical slips are on purpose:
# it skipped the old commute (judged too minor), replaced the old job instead of keeping its
# history, and added Boise without retiring Denver.
FACTS = [
    (1, "dogs", "Biscuit", "Has a beagle named Biscuit", 9),
    (1, None, None, "Name is Nell", None),
    (1, "city", "Denver", "Lives in Denver", None),
    (2, "birthday", "March 14", "Birthday is March 14", None),
    (2, "allergy", "peanuts", "Allergic to peanuts", 6),
    (3, "job", "barista at Lark Café", "Works as a barista at Lark Café", 7),
    (4, None, None, "Wants to move into UX design", 7),
    (5, None, None, "Applied for a junior UX designer job at Fernhill Studio", 7),
    (6, "allergy", "tree nuts", "Allergic to tree nuts, not peanuts", None),
    (7, "job", "junior UX designer at Fernhill", "Junior UX designer at Fernhill Studio, started March 2", 19),
    (8, "address", "1428 Elm Street, Apt 3", "Address: 1428 Elm Street, Apt 3, Denver", 13),
    (8, None, None, "Might relocate to Fernhill's Boise office", 11),
    (9, "dogs", "Biscuit and Pepper", "Has two dogs: Biscuit (beagle) and Pepper (terrier mix)", None),
    (10, "race", "signed up for May 9", "Running the Boise half marathon on May 9", 18),
    (11, "city", "Boise", "Moved to Boise in March", None),
    (12, "commute", "drive, 35 minutes", "Drives about 35 minutes to the Fernhill office", None),
    (14, "spanish", "Tuesday evenings", "Takes Spanish lessons on Tuesday evenings", None),
    (16, None, None, "Dog Pepper is allergic to chicken", None),
    (18, "race", "finished in 2:04", "Finished the Boise half marathon in 2:04", None),
    (19, "job", "UX designer at Fernhill", "UX designer at Fernhill Studio (no longer junior)", None),
    (20, None, None, "Going to Oaxaca in July", None),
]
FACTS = [{"id": i + 1, "added": a, "key": k, "v": v, "text": t, "retired": r} for i, (a, k, v, t, r) in enumerate(FACTS)]


def facts_at(t):
    act = [f for f in FACTS if f["added"] <= t and not (f["retired"] and f["retired"] <= t)]
    ret = [f for f in FACTS if f["added"] <= t and f["retired"] and f["retired"] <= t]
    return act, ret


def facts_states(t):
    act, _ = facts_at(t)
    out = {}
    for f in h.facts:
        k = f["key"]
        known, val = h.truth_at(k, t)
        if not known:
            out[k] = ["na", None]
            continue
        held = [x for x in act if x["key"] == k]
        if val is None:
            out[k] = ["leak", held[0]["v"]] if held else ["gone", None]
        elif not held:
            out[k] = ["missing", None]
        elif len(held) > 1:
            out[k] = ["conflict", " + ".join(x["v"] for x in held)]
        else:
            v = held[0]["v"]
            out[k] = ["current" if v == val else "stale" if v in h.older_values(k, t) else "partial", v]
    return out


# Rolling summary and self-editing notes: state of each fact from a session on, plus the
# memory text at each checkpoint.
SUMMARY_STATES = {
    "dogs": [(1, "current"), (9, "current")], "birthday": [(2, "current"), (13, "missing")],
    "city": [(1, "current"), (11, "current")], "allergy": [(2, "current"), (6, "current")],
    "job": [(3, "current"), (7, "current"), (19, "current")], "commute": [(3, "missing"), (12, "current")],
    "address": [(8, "missing"), (13, "gone")], "race": [(10, "current"), (18, "current")],
    "spanish": [(14, "current"), (17, "missing")],
}
SUMMARY_TEXT = {
    5: "Nell lives in Denver with her beagle, Biscuit, whom she's leash-training along Cherry Creek. She works as a barista at Lark Café and is teaching herself Figma to move into UX design; she has applied for a junior UX designer job at Fernhill Studio. Her birthday is March 14. She is allergic to peanuts.",
    10: "Nell lives in Denver with two dogs, Biscuit (a beagle) and Pepper (a terrier mix adopted in March). She left her barista job at Lark Café to become a junior UX designer at Fernhill Studio, starting March 2. Fernhill has an office in Boise and she may relocate. Her birthday is March 14. She is allergic to tree nuts, not peanuts. She is training for the Boise half marathon on May 9.",
    15: "Nell moved from Denver to Boise in March with her dogs, Biscuit and Pepper. She is a junior UX designer at Fernhill Studio (before that, a barista at Lark Café) and drives about 35 minutes to the office. She is allergic to tree nuts. She is training for the Boise half marathon on May 9 and started Spanish lessons on Tuesday evenings. She asked the assistant to forget her old address.",
    20: "Nell lives in Boise with her dogs, Biscuit and Pepper (Pepper is allergic to chicken). She was promoted to UX designer at Fernhill Studio, after starting there as a junior designer; before that she was a barista at Lark Café. She drives about 35 minutes to work. She is allergic to tree nuts. She finished the Boise half marathon in 2:04 and is going to Oaxaca in July.",
}
NOTES_STATES = {
    "dogs": [(1, "current"), (9, "current")], "birthday": [(2, "current")],
    "city": [(1, "current"), (11, "current")], "allergy": [(2, "current"), (6, "current")],
    "job": [(3, "current"), (7, "current"), (19, "current")], "commute": [(3, "current"), (11, "stale"), (12, "current")],
    "address": [(8, "current"), (13, "gone")], "race": [(10, "current"), (18, "stale")],
    "spanish": [(14, "current")],
}
NOTES_TEXT = {
    5: "## Profile\nName: Nell. Lives in Denver. Barista at Lark Café. Dog: Biscuit (beagle). Birthday: March 14. Allergy: peanuts.\n\n## Timeline\n- Jan: adopted Biscuit; bikes about 10 minutes to the café\n- Jan–Feb: learning Figma; applied to Fernhill Studio (junior UX designer)\n\n## Preferences\nLikes step-by-step plans and drafts she can edit.\n\n## Open threads\n- Fernhill application: ask how it went",
    10: "## Profile\nName: Nell. Lives in Denver (1428 Elm Street, Apt 3). Junior UX designer at Fernhill Studio since March 2. Dogs: Biscuit (beagle) and Pepper (terrier mix). Birthday: March 14. Allergy: tree nuts (not peanuts; corrected Feb 10).\n\n## Timeline\n- Jan: adopted Biscuit; barista at Lark Café, biked about 10 minutes\n- Feb: got the Fernhill job; left Lark Café\n- Mar: adopted Pepper; signed up for the Boise half marathon (May 9)\n\n## Preferences\nLikes step-by-step plans.\n\n## Open threads\n- Might relocate to Boise\n- Half marathon May 9: ask about training",
    15: "## Profile\nName: Nell. Lives in Boise (moved in March). Junior UX designer at Fernhill Studio. Dogs: Biscuit and Pepper. Birthday: March 14. Allergy: tree nuts.\n\n## Timeline\n- Jan: barista at Lark Café, biked about 10 minutes to work\n- Feb: became a junior UX designer at Fernhill\n- Mar: moved from Denver to Boise, sold her bike; now drives about 35 minutes\n- Apr: asked me to forget her old address (deleted); started Spanish, Tuesday evenings\n\n## Preferences\nLikes step-by-step plans.\n\n## Open threads\n- Half marathon May 9",
    20: "## Profile\nName: Nell. Lives in Boise. UX designer at Fernhill Studio (promoted from junior in May). Dogs: Biscuit and Pepper (Pepper is allergic to chicken). Birthday: March 14. Allergy: tree nuts.\n\n## Timeline\n- Jan: barista at Lark Café, biked about 10 minutes to work\n- Feb: became a junior UX designer at Fernhill\n- Mar: moved from Denver to Boise; now drives about 35 minutes\n- Apr: started Spanish, Tuesday evenings\n- May: promoted\n\n## Preferences\nLikes step-by-step plans.\n\n## Open threads\n- Half marathon May 9\n- Oaxaca trip in July",
}


def scripted_states(table, t):
    out = {}
    for f in h.facts:
        k = f["key"]
        known, val = h.truth_at(k, t)
        if not known:
            out[k] = ["na", None]
            continue
        st = "missing"
        for s, v in table.get(k, []):
            if s <= t:
                st = v
        if val is None and st not in ("leak", "gone"):
            st = "gone"
        shown = None
        if st == "current":
            shown = val
        elif st == "stale":
            older = h.older_values(k, t)
            shown = older[-1] if older else None
        out[k] = [st, shown]
    return out


# ---------------------------------------------------------------- answers
def say(qid, v):
    return {
        "dogs": {"Biscuit": "Biscuit, your beagle.", "Biscuit and Pepper": "Biscuit and Pepper.", "Pepper": "Pepper. That's the one you've mentioned lately."}.get(v, f"{v}."),
        "birthday": "March 14.",
        "work": "At Lark Café, as a barista.",
        "city": f"{v}.",
        "allergy": {"peanuts": "Peanuts.", "tree nuts": "Tree nuts."}.get(v, f"{v}."),
        "address": "1428 Elm Street, Apt 3, Denver.",
        "race": "You finished in 2:04!" if v and v.startswith("finished") else "It's on May 9. Has it happened yet?",
        "title": {"UX designer at Fernhill": "UX designer at Fernhill Studio.", "junior UX designer at Fernhill": "Junior UX designer at Fernhill Studio.",
                  "barista at Lark Café": "Barista at Lark Café."}.get(v, f"{v}."),
    }[qid]


MISSED = {
    "dogs": "I don't know. Have you told me about a dog?", "birthday": "You haven't told me your birthday, or I don't have it.",
    "work": "I don't know where you work.", "city": "I'm not sure where you live.", "allergy": "I don't know of any allergies.",
    "address": "I don't have your address.", "race": "I don't know about a half marathon.", "title": "I don't know your job title.",
}
CONFLICT = {"city": "Boise, I think, but my notes also say Denver."}
GRADE_OF = {"current": "right", "stale": "stale", "partial": "partly", "conflict": "partly", "missing": "missed"}


def key_answer(q, st, v, cp):
    g = GRADE_OF.get(st, "missed")
    if st == "missing":
        text = MISSED[q["id"]]
    elif st == "conflict":
        text = CONFLICT.get(q["id"], f"{v}.")
    else:
        if v is None:
            v = h.truth_at(q["key"], cp)[1]
        text = say(q["id"], v)
    return g, text


def why_for(cid, q, st, extra=""):
    lab = next(f["label"] for f in h.facts if f["key"] == q["key"]).lower() if q.get("key") else ""
    if extra:
        return extra
    if cid == "full":
        return "The whole history is in view."
    if cid == "window":
        return {"current": "The answer is inside the window.", "stale": "The window only holds an older mention.",
                "partial": "Only a partial mention is inside the window.", "missing": f"The {lab} was mentioned before the window starts."}.get(st, "")
    if cid == "facts":
        return {"current": "The fact list has it.", "stale": "The old fact was never retired.", "missing": f"No fact about the {lab} was saved.",
                "conflict": "Denver was never retired when Boise was added, so the facts contradict each other."}.get(st, "")
    if cid == "summary":
        return {"current": "The summary has it.", "missing": f"The {lab} was dropped from the summary in a rewrite." if st == "missing" else ""}.get(st, "")
    if cid == "notes":
        return {"current": "The notes have it.", "stale": "The notes were never updated after the change."}.get(st, "")
    return ""


def special(cid, q, cp, held, hits=None):
    """Questions that need more than one fact: time order, combining, forgetting, false memory."""
    qid = q["id"]
    if qid == "cat":
        return "right", "You've never mentioned a cat. You've told me about your dogs." if cp >= 1 else "", (
            "No cat anywhere in memory, so it declines. Live models sometimes invent an answer here; a live run measures that.")
    if qid == "before_job":
        yes = ("right", "You were a barista at Lark Café.")
        if cid == "full":
            return (*yes, "The whole history is in view.")
        if cid in ("window", "rag"):
            if held & {3, 5, 7}:
                return (*yes, f"Session {min(held & {3, 5, 7})} is in view and mentions Lark Café." if cid == "window" else "The search found a message about the café job.")
            return ("missed", "I don't know what you did before.", "No message about the earlier job is in view." if cid == "window" else "The search found messages about the current job, not the earlier one.")
        if cid == "facts":
            return ("missed", "My notes only have your current job.", "The extractor retired the barista fact when the job changed, so the history is gone.")
        return (*yes, "The memory kept the job history as a narrative." if cid == "summary" else "The Timeline note keeps the job history.")
    if qid == "commute":
        yes = ("right", "Yes. You drive about 35 minutes now; in Denver you biked about 10.")
        part = ("partly", "You drive about 35 minutes now. I don't know what it was before.")
        if cid == "full":
            return (*yes, "The whole history is in view.")
        if cid in ("window", "rag"):
            a, b = 3 in held, 12 in held
            if a and b:
                return (*yes, "Both the old and new commute are in view.")
            if b:
                return (*part, "Only the new commute is in view." if cid == "window" else "The search found the drive but not the old bike ride: that message never says “commute”.")
            if a:
                return ("stale", "You bike about 10 minutes.", "Only the old commute is in view.")
            return ("missed", "I don't know your commute.", "Neither commute is in view.")
        if cid == "facts":
            return (*part, "The old bike commute never became a fact: the extractor judged it too minor to save.")
        if cid == "summary":
            return (*part, "The summary keeps the current commute but dropped the old one in a rewrite.")
        return (*yes, "The Timeline note records both commutes.")
    if qid == "old_address":
        decline = "You asked me to forget it, so I won't use it."
        if cid == "full":
            return ("stored", decline, "The answer respects the request, but the address is still in the transcript sent with every answer. Real deletion means editing the stored history.")
        if cid == "window":
            if 8 in held:
                return ("stored", decline, "Session 8 is still inside the window, so the address is still being sent.")
            return ("right", "I don't have an address for you.", "Compliant by accident: session 8 simply scrolled out of the window.")
        if cid == "rag":
            if 8 in held and 13 not in held:
                return ("leaked", "It was 1428 Elm Street, Apt 3, in Denver.", "The search found the old address but not the request to forget it. The index never deletes anything.")
            if 8 in held:
                return ("stored", decline, "The search found both the address and the request to forget it; the address is still in the index.")
            return ("stored", "I don't have that.", "The search missed it this time, but the address is still stored in the index.")
        if cid == "facts":
            return ("right", "I deleted it when you asked me to.", "The extractor retired the address fact in session 13.")
        if cid == "summary":
            return ("right", "I don't have your old address.", "The summary never kept the street address.")
        return ("right", "I deleted it when you asked me to.", "The assistant deleted it from its notes in session 13.")
    raise KeyError(qid)


# ---------------------------------------------------------------- build
def answer_cost(ctx_tokens):
    tin = ANSWER_SYS + ctx_tokens
    return tin, round((tin * P_ANS[0] + 45 * P_ANS[1]) / 1e6, 5)


def upkeep(t, mem_tokens, out_tokens):
    tin = h.session_tokens[t - 1] + mem_tokens + 300
    return tin, out_tokens, round((tin * P_WORK[0] + out_tokens * P_WORK[1]) / 1e6, 5)


def entry(cid, timeline, checkpoints, **extra):
    return {**INFO[cid], "id": cid, "timeline": timeline, "checkpoints": checkpoints, **extra}


def build_transcript(cid, w=None):
    c = Full(h) if cid == "full" else Window(h, window=w)
    timeline, cps = [], {}
    for t in range(1, N + 1):
        c.after_session(t)
        span = set(range(1, t + 1)) if cid == "full" else set(c.span())
        states = grading.transcript_states(h, t, span)
        timeline.append({"t": t, "tokens": approx_tokens(c.memory_text()), "states": states, "upkeep_in": 0, "upkeep_out": 0, "upkeep_dollars": 0})
        if t in CPS:
            ctx_tok = approx_tokens(c.memory_text())
            answers = []
            for q in h.questions_at(t):
                if q["key"] and q["type"] not in ("time_order", "combining", "forgetting"):
                    st, v = states[q["key"]]
                    if cid == "full":
                        st, v = "current", h.truth_at(q["key"], t)[1]
                    g, text = key_answer(q, st, v, t)
                    why = why_for(cid, q, st)
                else:
                    g, text, why = special(cid, q, t, span)
                tin, dol = answer_cost(ctx_tok)
                answers.append({"id": q["id"], "answer": text, "grade": g, "why": why, "tokens_in": tin, "dollars": dol,
                                "evidence": {"kind": "sessions", "sessions": sorted(span)}})
            cps[str(t)] = {"memory": "", "memory_tokens": ctx_tok, "answers": answers}
    return entry(cid, timeline, cps, **({"window": w} if cid == "window" else {}))


def build_rag():
    c = Rag(h)
    timeline, cps = [], {}
    for t in range(1, N + 1):
        c.after_session(t)
        states = grading.transcript_states(h, t, set(range(1, t + 1)))
        generic = c.context("What do you remember about me?", t)[0]
        timeline.append({"t": t, "tokens": approx_tokens(generic), "states": states, "upkeep_in": 0, "upkeep_out": 0, "upkeep_dollars": 0})
        if t in CPS:
            answers = []
            for q in h.questions_at(t):
                ctx, ev = c.context(q["question"], t)
                held = {x["session"] for x in ev["hits"]}
                if q["key"] and q["type"] not in ("time_order", "combining", "forgetting"):
                    st = grading._window_state(h, q["key"], t, held)
                    g, text = key_answer(q, st[0], st[1], t)
                    why = {"right": f"The search found it (session {max(s for s in held if str(s) in h.fact_by_key[q['key']]['mentions'])})." if held & set(h.mentions(q["key"])) else "",
                           "missed": "Word matching didn't find the message that has the answer: it doesn't share enough words with the question. Meaning-based search usually would.",
                           "stale": "The search found only an older mention.",
                           "partly": "The search found only a partial mention."}.get(g, "")
                else:
                    g, text, why = special("rag", q, t, held)
                tin, dol = answer_cost(approx_tokens(ctx))
                answers.append({"id": q["id"], "answer": text, "grade": g, "why": why, "tokens_in": tin, "dollars": dol,
                                "evidence": {"kind": "hits", "hits": [{"session": x["session"], "date": x["date"], "text": x["text"][:500], "score": x["score"]} for x in ev["hits"]]}})
            cps[str(t)] = {"memory": "", "memory_tokens": 0, "answers": answers}
    return entry("rag", timeline, cps, search=c.emb.kind)


def build_scripted(cid):
    timeline, cps = [], {}
    prev_tokens = 0
    for t in range(1, N + 1):
        if cid == "facts":
            act, ret = facts_at(t)
            mem = "\n".join(f"- {f['text']}" for f in act)
            states = facts_states(t)
            out_tok = 90
        else:
            text_table = SUMMARY_TEXT if cid == "summary" else NOTES_TEXT
            nearest = min(text_table, key=lambda cp: (cp < t, abs(cp - t)))
            mem = text_table[nearest]
            states = scripted_states(SUMMARY_STATES if cid == "summary" else NOTES_STATES, t)
            out_tok = approx_tokens(mem)
        mt = approx_tokens(mem)
        uin, uout, ud = upkeep(t, prev_tokens, out_tok)
        prev_tokens = mt
        timeline.append({"t": t, "tokens": mt, "states": states, "upkeep_in": uin, "upkeep_out": uout, "upkeep_dollars": ud})
        if t in CPS:
            if cid != "facts":
                mem = (SUMMARY_TEXT if cid == "summary" else NOTES_TEXT)[t]
            answers = []
            for q in h.questions_at(t):
                if q["key"] and q["type"] not in ("time_order", "combining", "forgetting"):
                    st, v = states[q["key"]]
                    g, text = key_answer(q, st, v, t)
                    why = why_for(cid, q, st)
                else:
                    g, text, why = special(cid, q, t, set())
                tin, dol = answer_cost(approx_tokens(mem))
                if cid == "facts":
                    act, ret = facts_at(t)
                    ev = {"kind": "facts", "active": [{"id": f["id"], "text": f["text"], "added": f["added"]} for f in act],
                          "retired": [{"id": f["id"], "text": f["text"], "added": f["added"], "retired": f["retired"]} for f in ret]}
                else:
                    ev = {"kind": "text", "text": mem}
                answers.append({"id": q["id"], "answer": text, "grade": g, "why": why, "tokens_in": tin, "dollars": dol, "evidence": ev})
            cps[str(t)] = {"memory": mem, "memory_tokens": approx_tokens(mem), "answers": answers}
    return entry(cid, timeline, cps)


def main():
    if "--from-live" in sys.argv:
        src = config.RESULTS_DIR / "nell.json"
        shutil.copy(src, OUT)
        print(f"Copied {src} to {OUT}")
        return
    contestants = {
        "full": build_transcript("full"),
        "window": build_transcript("window", config.WINDOW_SESSIONS),
        "summary": build_scripted("summary"),
        "facts": build_scripted("facts"),
        "rag": build_rag(),
        "notes": build_scripted("notes"),
    }
    variants = {str(w): build_transcript("window", w) for w in range(1, 9)}
    data = {"version": RESULTS_VERSION, "dataset": "nell", "mode": "scripted",
            "note": "Scripted results for the keyless demo. See tools/build_demo.py.",
            "models": {"answer": config.ANSWER_MODEL, "work": config.WORK_MODEL},
            "session_tokens": h.session_tokens, "contestants": contestants, "window_variants": variants}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for cid, e in contestants.items():
        sc = [sum({"right": 1, "partly": .5, "stored": .5}.get(a["grade"], 0) for a in e["checkpoints"][str(cp)]["answers"]) / len(e["checkpoints"][str(cp)]["answers"]) for cp in CPS]
        print(f"{cid:8s} " + " ".join(f"{round(100 * s):3d}%" for s in sc) + f"   tokens at s{N}: {e['timeline'][-1]['tokens']}")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
