"""The six memory strategies. Each one replays the history session by session and keeps
whatever its strategy keeps; at a checkpoint it hands the answer model a context to answer from.

Every contestant has:
  after_session(t, meter)  update memory after session t (some call the cheap work model)
  context(question, t)     the memory text the answer model sees for this question, plus evidence
  memory_text()            what's in memory right now (for the memory panel and the inspector)
"""
import numpy as np

from . import config, llm
from .textutil import approx_tokens

INFO = {
    "full": {"name": "Full transcript", "color": "#6ff0a8",
             "how": "Sends every past message with each answer."},
    "window": {"name": "Sliding window", "color": "#ff8f5a",
               "how": "Sends only the most recent sessions."},
    "summary": {"name": "Rolling summary", "color": "#ffd95e",
                "how": "After each session, rewrites a short running summary."},
    "facts": {"name": "Fact memory", "color": "#7cc8ff",
              "how": "After each session, adds and retires short facts in a list."},
    "rag": {"name": "RAG over past chats", "color": "#f28bb8",
            "how": "Stores every message and sends the closest few to each question. The map shows what's stored; the search decides what's sent."},
    "notes": {"name": "Self-editing memory", "color": "#c4b0ff",
              "how": "The assistant writes, edits and deletes its own notes."},
}
ORDER = ["full", "window", "summary", "facts", "rag", "notes"]


class Contestant:
    id = ""

    def __init__(self, history, window=None):
        self.h = history
        self.t = 0

    def after_session(self, t, meter=None):
        self.t = t

    def memory_text(self):
        return ""

    def context(self, question, t):
        text = self.memory_text()
        return text, {"kind": "text", "text": text}

    @property
    def name(self):
        return INFO[self.id]["name"]


class Full(Contestant):
    id = "full"

    def memory_text(self):
        return "\n\n".join(self.h.session_text(i) for i in range(1, self.t + 1))

    def context(self, question, t):
        return self.memory_text(), {"kind": "sessions", "sessions": list(range(1, t + 1))}


class Window(Contestant):
    id = "window"

    def __init__(self, history, window=None):
        super().__init__(history)
        self.w = window or config.WINDOW_SESSIONS

    def span(self):
        return list(range(max(1, self.t - self.w + 1), self.t + 1))

    def memory_text(self):
        return "\n\n".join(self.h.session_text(i) for i in self.span())

    def context(self, question, t):
        return self.memory_text(), {"kind": "sessions", "sessions": self.span()}


SUMMARY_SYSTEM = f"""You keep a running summary of what an assistant knows about a user, from their chats.
After each chat you rewrite the summary to include anything new and durable about the user's life, and update anything that changed.
Keep it under {config.SUMMARY_WORDS} words. Write plain prose. Don't record the details of tasks the assistant helped with.
If the user asked the assistant to forget something, remove it from the summary.
Reply with only the new summary."""


class Summary(Contestant):
    id = "summary"

    def __init__(self, history, window=None):
        super().__init__(history)
        self.summary = ""

    def after_session(self, t, meter=None):
        self.t = t
        user = (f"Current summary:\n{self.summary or '(empty: this is the first chat)'}\n\n"
                f"New chat:\n{self.h.session_text(t)}")
        self.summary = llm.complete(SUMMARY_SYSTEM, user, task="summary_update", max_tokens=1500, meter=meter).strip()

    def memory_text(self):
        return self.summary


FACTS_SYSTEM = """You maintain an assistant's memory of a user after each chat, like a friend who listens well.
You read the chat and update a list of short facts about the user.
Keep facts short, specific and durable (e.g. "Has a sister named Ana who lives in Denver"). Skip the details of tasks the assistant helped with.
When a fact changes or turns out wrong, retire the old fact and add the new one.
If the user asks the assistant to forget something, retire every fact that contains it.
Never store passwords, ID numbers or financial account numbers.
Reply with ONLY JSON: {"add": ["new facts"], "retire": [ids of facts now outdated, wrong, or to forget]}"""


class Facts(Contestant):
    """Mirrors the add/retire design many chat apps use (including Hablemos's consolidator)."""
    id = "facts"

    def __init__(self, history, window=None):
        super().__init__(history)
        self.facts = []     # {id, text, added, retired}
        self.next_id = 1

    def active(self):
        return [f for f in self.facts if not f.get("retired")]

    def after_session(self, t, meter=None):
        self.t = t
        current = "\n".join(f"{f['id']}: {f['text']}" for f in self.active()) or "(nothing yet)"
        user = f"Current facts (id: fact):\n{current}\n\nNew chat:\n{self.h.session_text(t)}"
        r = llm.complete_json(FACTS_SYSTEM, user, task="facts_update", max_tokens=1500, meter=meter)
        for fid in r.get("retire") or []:
            for f in self.facts:
                if str(f["id"]) == str(fid) and not f.get("retired"):
                    f["retired"] = t
        for text in r.get("add") or []:
            if isinstance(text, str) and text.strip():
                self.facts.append({"id": self.next_id, "text": text.strip(), "added": t})
                self.next_id += 1

    def memory_text(self):
        return "\n".join(f"- {f['text']}" for f in self.active())

    def context(self, question, t):
        return self.memory_text(), {"kind": "facts", "active": self.active(),
                                    "retired": [f for f in self.facts if f.get("retired")]}


class Rag(Contestant):
    """Each user message, paired with the reply to it, is one searchable chunk."""
    id = "rag"

    def __init__(self, history, window=None, embedder=None):
        super().__init__(history)
        self.chunks = []
        for s in history.sessions:
            turns = s["turns"]
            for i, tr in enumerate(turns):
                if tr["role"] != "user":
                    continue
                reply = turns[i + 1]["text"] if i + 1 < len(turns) and turns[i + 1]["role"] == "assistant" else ""
                self.chunks.append({"session": s["n"], "date": s["date"],
                                    "text": f"{history.user}: {tr['text']}\nAssistant: {reply}"})
        from .embed import make_embedder
        self.emb = embedder or make_embedder()
        texts = [c["text"] for c in self.chunks]
        self.emb.fit(texts)
        self.vecs = self.emb.embed(texts)

    def search(self, question, t, k=None):
        k = k or config.RAG_TOP_K
        idx = [i for i, c in enumerate(self.chunks) if c["session"] <= t]
        if not idx:
            return []
        q = self.emb.embed([question])[0]
        scores = self.vecs[idx] @ q
        order = np.argsort(-scores)[:k]
        hits = [dict(self.chunks[idx[j]], score=round(float(scores[j]), 3)) for j in order]
        return sorted(hits, key=lambda c: c["session"])

    def memory_text(self):
        n = sum(1 for c in self.chunks if c["session"] <= self.t)
        return f"{n} past messages stored in a search index."

    def context(self, question, t):
        hits = self.search(question, t)
        text = "\n\n".join(f"[Session {c['session']} · {c['date']}]\n{c['text']}" for c in hits)
        return text, {"kind": "hits", "hits": hits}


NOTES_SYSTEM = f"""You are an assistant with a private notebook about the user you chat with. After each chat you edit your notes so that future chats go well.
You decide what is worth keeping and how to organize it. Good notebooks usually have notes like: Profile (current facts), Timeline (what changed and when), Preferences (how they like things done), and Open threads (things to follow up on).
Update notes when things change, and keep a short record of what changed when it might matter later.
If the user asks you to forget something, delete it from every note.
Keep the whole notebook under {config.NOTES_WORDS} words.
Reply with ONLY JSON: {{"ops": [{{"op": "write", "note": "title", "text": "full new text of the note"}}, {{"op": "delete", "note": "title"}}]}}
"write" creates or replaces a note. List only notes you change. Reply {{"ops": []}} if nothing needs changing."""


class Notes(Contestant):
    """A simplified MemGPT/Letta-style memory: the assistant edits its own notes after each chat."""
    id = "notes"

    def __init__(self, history, window=None):
        super().__init__(history)
        self.notes = {}
        self.log = []

    def after_session(self, t, meter=None):
        self.t = t
        book = "\n\n".join(f"## {k}\n{v}" for k, v in self.notes.items()) or "(empty)"
        user = f"Your notes now:\n{book}\n\nThe chat that just ended:\n{self.h.session_text(t)}"
        r = llm.complete_json(NOTES_SYSTEM, user, task="notes_update", max_tokens=2500, meter=meter)
        for op in r.get("ops") or []:
            if not isinstance(op, dict) or not op.get("note"):
                continue
            title = str(op["note"]).strip()
            if op.get("op") == "delete":
                if self.notes.pop(title, None) is not None:
                    self.log.append({"t": t, "op": "delete", "note": title})
            elif isinstance(op.get("text"), str):
                self.notes[title] = op["text"].strip()
                self.log.append({"t": t, "op": "write", "note": title})

    def memory_text(self):
        return "\n\n".join(f"## {k}\n{v}" for k, v in self.notes.items())


CLASSES = {"full": Full, "window": Window, "summary": Summary, "facts": Facts, "rag": Rag, "notes": Notes}

ANSWER_SYSTEM = """You are a friendly assistant who has chatted with {user} many times. Below is your memory of past chats, prepared by your memory system.
Answer {user}'s new message using only this memory.
- If the memory doesn't contain the answer, say you don't know or don't remember. Never guess.
- If something changed over time, give what is true now.
- If {user} asked you to forget something, don't use or repeat it.
- Answer in one or two sentences."""


def answer(h, context_text, question, t, meter=None):
    system = ANSWER_SYSTEM.format(user=h.user)
    memory = context_text.strip() or "(empty)"
    when = f"Today's date: {h.date_after(t)} (after session {t})." if h.date_after(t) else f"This is after session {t}."
    user = f"Your memory:\n{memory}\n\n{when}\n{h.user}'s message: {question}"
    text = llm.complete(system, user, model=config.ANSWER_MODEL, task="answer", max_tokens=1500, meter=meter).strip()
    return text, approx_tokens(system + user)
