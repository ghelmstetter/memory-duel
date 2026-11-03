"""Running the duel: replay a history through each contestant, quiz at checkpoints, grade, save.

Each contestant runs on its own thread with its own error handling, so one failure shows up
on that contestant's cards and the others still finish.
"""
import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import config, grading, llm
from .contestants import CLASSES, INFO, ORDER, answer
from .history import History
from .textutil import approx_tokens

RESULTS_VERSION = 1
JOBS = {}
_LOCK = threading.Lock()


def _read(p, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


# ---------------- datasets and results ----------------
def list_histories():
    out = []
    for base, kind in ((config.DEMO_DIR, "demo"), (config.DATASETS_DIR, "yours")):
        if not base.exists():
            continue
        for d in sorted(base.iterdir()):
            p = d / "history.json"
            if p.exists():
                data = _read(p)
                out.append({"slug": d.name, "name": data.get("name", d.name), "kind": kind,
                            "description": data.get("description", ""), "sessions": len(data.get("sessions", [])),
                            "has_live": (config.RESULTS_DIR / f"{d.name}.json").exists()})
    return out


def results_for(slug):
    """Live results from your own runs if there are any; otherwise the demo's saved results."""
    live = _read(config.RESULTS_DIR / f"{slug}.json")
    if live and live.get("version") == RESULTS_VERSION:
        return live
    demo = _read(config.DEMO_DIR / slug / "results.json")
    return demo


def clear_live(slug):
    p = config.RESULTS_DIR / f"{slug}.json"
    if p.exists():
        p.unlink()


# ---------------- cost ----------------
class Tee(llm.Meter):
    """A meter that also adds every call to a shared run meter (which holds the budget)."""

    def __init__(self, run_meter):
        super().__init__(fresh=run_meter.fresh)
        self.run = run_meter

    def add(self, model, tin, tout, cached=False):
        super().add(model, tin, tout, cached)
        self.run.add(model, tin, tout, cached)

    def over_budget(self):
        return self.run.over_budget()


def _ctx_tokens(h, cid, t, window):
    tok = h.session_tokens
    if cid == "full":
        return sum(tok[:t])
    if cid == "window":
        return sum(tok[max(0, t - window):t])
    if cid == "rag":
        return config.RAG_TOP_K * 220
    return {"summary": 330, "facts": 300, "notes": 650}[cid]


def estimate(slug, contestants=None, window=None):
    h = History.load(slug)
    window = window or config.WINDOW_SESSIONS
    cids = contestants or ORDER
    p_ans, p_work = config.PRICES[config.ANSWER_MODEL], config.PRICES[config.WORK_MODEL]
    d = {"answers": 0.0, "upkeep": 0.0, "grading": 0.0}
    nq = 0
    for cp in h.checkpoint_list:
        qs = h.questions_at(cp)
        for cid in cids:
            tin = 250 + _ctx_tokens(h, cid, cp, window)
            d["answers"] += len(qs) * (tin * p_ans[0] + 60 * p_ans[1]) / 1e6
            d["grading"] += len(qs) * (260 * p_work[0] + 50 * p_work[1]) / 1e6
            nq += len(qs)
    for cid in cids:
        if cid in ("summary", "facts", "notes"):
            for t in range(1, h.n + 1):
                d["upkeep"] += ((h.session_tokens[t - 1] + 700) * p_work[0] + 350 * p_work[1]) / 1e6
                d["grading"] += (900 * p_work[0] + 120 * p_work[1]) / 1e6
    total = sum(d.values())
    return {"dollars": round(total, 3), "parts": {k: round(v, 3) for k, v in d.items()}, "answers": nq,
            "budget": config.MAX_RUN_DOLLARS, "models": {"answer": config.ANSWER_MODEL, "work": config.WORK_MODEL}}


# ---------------- running ----------------
def start_run(slug, contestants=None, window=None, fresh=False):
    if not config.has_key():
        raise PermissionError("Live runs need an Anthropic API key in your .env file.")
    h = History.load(slug)
    cids = [c for c in (contestants or ORDER) if c in CLASSES]
    window = int(window or config.WINDOW_SESSIONS)
    job_id = uuid.uuid4().hex[:10]
    steps_per = h.n + sum(len(h.questions_at(cp)) for cp in h.checkpoint_list)
    job = {"id": job_id, "slug": slug, "status": "running", "started": time.time(), "contestants": cids,
           "progress": {c: {"done": 0, "total": steps_per, "stage": "waiting", "error": None} for c in cids},
           "meter": None, "error": None}
    with _LOCK:
        JOBS[job_id] = job
    threading.Thread(target=_run, args=(h, job, cids, window, fresh), daemon=True).start()
    return job


def _run(h, job, cids, window, fresh):
    run_meter = llm.Meter(budget_dollars=config.MAX_RUN_DOLLARS, fresh=fresh)
    out = {}

    def one(cid):
        prog = job["progress"][cid]
        try:
            out[cid] = run_contestant(h, cid, window, run_meter, prog)
            prog["stage"] = "done"
        except Exception as e:
            traceback.print_exc()
            prog["error"] = friendly_error(e)
            prog["stage"] = "failed"

    with ThreadPoolExecutor(max_workers=len(cids)) as ex:
        list(ex.map(one, cids))
    job["meter"] = run_meter.as_dict()
    if out:
        p = config.RESULTS_DIR / f"{h.slug}.json"
        res = _read(p)
        if not res or res.get("version") != RESULTS_VERSION:
            res = {"version": RESULTS_VERSION, "dataset": h.slug, "mode": "live", "contestants": {}}
        res["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        res["models"] = {"answer": config.ANSWER_MODEL, "work": config.WORK_MODEL}
        res["session_tokens"] = h.session_tokens
        res["contestants"].update(out)
        _write(p, res)
    failed = [c for c in cids if job["progress"][c]["error"]]
    job["status"] = "done" if not failed else ("partial" if out else "failed")
    if failed and not out:
        job["error"] = job["progress"][failed[0]]["error"]


def run_contestant(h, cid, window, run_meter, prog=None):
    """Replay the whole history through one contestant. Returns its results entry."""
    prog = prog if prog is not None else {"done": 0, "total": 0, "stage": ""}
    upkeep, answers_m, grading_m = Tee(run_meter), Tee(run_meter), Tee(run_meter)
    c = CLASSES[cid](h, window=window)
    timeline, checkpoints = [], {}
    for t in range(1, h.n + 1):
        prog["stage"] = f"session {t}"
        before = (upkeep.tokens_in, upkeep.tokens_out, upkeep.dollars)
        c.after_session(t, upkeep)
        if cid in ("full", "rag"):
            states = grading.transcript_states(h, t, set(range(1, t + 1)))
        elif cid == "window":
            states = grading.transcript_states(h, t, set(c.span()))
        else:
            states = grading.inspect_states(h, t, c.memory_text(), grading_m)
        ctx_tok = approx_tokens(c.context("What do you remember about me?", t)[0]) if cid == "rag" else approx_tokens(c.memory_text())
        timeline.append({"t": t, "tokens": ctx_tok, "states": states,
                         "upkeep_in": upkeep.tokens_in - before[0], "upkeep_out": upkeep.tokens_out - before[1],
                         "upkeep_dollars": round(upkeep.dollars - before[2], 5)})
        prog["done"] += 1
        if t in h.checkpoint_list:
            prog["stage"] = f"quiz after session {t}"
            checkpoints[str(t)] = _quiz(h, c, cid, t, states, answers_m, grading_m, prog)
        if run_meter.over_budget():
            raise llm.BudgetExceeded(f"Stopped: this run passed the ${run_meter.budget:.2f} budget (MDUEL_MAX_RUN_DOLLARS).")
    entry = {**INFO[cid], "id": cid, "timeline": timeline, "checkpoints": checkpoints,
             "meter": {"answers": answers_m.as_dict(), "upkeep": upkeep.as_dict(), "grading": grading_m.as_dict()}}
    if cid == "window":
        entry["window"] = window
    return entry


def _evidence(ev):
    if ev["kind"] == "hits":
        return {"kind": "hits", "hits": [{"session": x["session"], "date": x["date"], "text": x["text"][:500], "score": x["score"]} for x in ev["hits"]]}
    if ev["kind"] == "facts":
        return {"kind": "facts", "active": [{"id": f["id"], "text": f["text"], "added": f["added"]} for f in ev["active"]],
                "retired": [{"id": f["id"], "text": f["text"], "added": f["added"], "retired": f["retired"]} for f in ev["retired"]]}
    return ev


def _quiz(h, c, cid, t, states, answers_m, grading_m, prog):
    qs = h.questions_at(t)

    def ask(q):
        ctx, ev = c.context(q["question"], t)
        before = answers_m.dollars
        try:
            text, tin = answer(h, ctx, q["question"], t, answers_m)
        except Exception as e:
            return {"id": q["id"], "error": friendly_error(e)}
        g = grading.judge(q, text, grading_m, h=h, t=t)
        if q["type"] == "forgetting" and g["grade"] == "right" and q.get("key") and states.get(q["key"], ["", None])[0] == "leak":
            g = {"grade": "stored", "why": "The answer declines, but the memory still holds what the user asked to forget."}
        prog["done"] += 1
        return {"id": q["id"], "answer": text, "grade": g["grade"], "why": g["why"], "tokens_in": tin,
                "dollars": round(answers_m.dollars - before, 5), "evidence": _evidence(ev)}

    with ThreadPoolExecutor(max_workers=4) as ex:
        answers = list(ex.map(ask, qs))
    memory = c.memory_text() if cid not in ("full", "window") else ""
    return {"memory": memory, "memory_tokens": approx_tokens(c.memory_text()), "answers": answers}


def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        raise ValueError("That run isn't running any more (the app may have restarted).")
    return {**job, "elapsed": round(time.time() - job["started"], 1)}


def friendly_error(e):
    msg = str(e)
    low = msg.lower()
    if "authentication" in low or "api key" in low or "401" in msg:
        return "Claude rejected the API key. Check ANTHROPIC_API_KEY in your .env file."
    if "credit" in low or "billing" in low:
        return "Your Anthropic account is out of credit. Add credit in the Anthropic console."
    if ("rate" in low and "limit" in low) or "429" in msg or "overloaded" in low:
        return ("Claude's rate limit was still hit after several waits. Click \u201cRetry failed answers\u201d in a minute, "
                "or lower MDUEL_ANSWER_CONCURRENCY in .env.")
    if isinstance(e, llm.BudgetExceeded):
        return msg
    if isinstance(e, llm.EmptyReply):
        return msg
    return f"Something went wrong: {msg[:300]}"


def ensure_dirs():
    for d in (config.DATA_DIR, config.RESULTS_DIR, config.DATASETS_DIR):
        d.mkdir(parents=True, exist_ok=True)

