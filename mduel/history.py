"""A chat history to replay: sessions, the event log of facts (the answer key), and the quiz.

File format (history.json):
  sessions:    [{n, date, topic, turns: [{role: "user"|"assistant", text}]}]
  facts:       [{key, label, truth: [[session, value or null]], mentions: {session: value}}]
               truth: the fact's value from that session on; null means the user asked to forget it.
               mentions: sessions whose text states that value (used to score what a memory holds).
  checkpoints: [{after: session, questions: [{id, type, key, question, reference, outdated, forbidden}]}]
"""
import json
from functools import cached_property

from . import config
from .textutil import approx_tokens


class History:
    def __init__(self, slug, data):
        self.slug = slug
        self.data = data
        self.user = data.get("user", "the user")
        self.sessions = data["sessions"]
        self.facts = data.get("facts", [])
        self.checkpoints = data.get("checkpoints", [])
        self.fact_by_key = {f["key"]: f for f in self.facts}

    @classmethod
    def load(cls, slug):
        for base in (config.DATASETS_DIR, config.DEMO_DIR):
            p = base / slug / "history.json"
            if p.exists():
                return cls(slug, json.loads(p.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No history called {slug}.")

    @property
    def n(self):
        return len(self.sessions)

    def session_text(self, n):
        s = self.sessions[n - 1]
        lines = [f"### Session {n} · {s['date']} · {s['topic']}"]
        for t in s["turns"]:
            who = self.user if t["role"] == "user" else "Assistant"
            lines.append(f"{who}: {t['text']}")
        return "\n".join(lines)

    @cached_property
    def session_tokens(self):
        return [approx_tokens(self.session_text(i)) for i in range(1, self.n + 1)]

    @property
    def editable(self):
        return (config.DATASETS_DIR / self.slug / "history.json").exists()

    def truth_at(self, key, t):
        """(known, value) after session t. value None means forgotten on request."""
        known, val = False, None
        for s, v in self.fact_by_key[key]["truth"]:
            if s <= t:
                known, val = True, v
        return known, val

    def older_values(self, key, t):
        vals = [v for s, v in self.fact_by_key[key]["truth"] if s <= t and v is not None]
        return vals[:-1]

    def forgotten_values(self, key, t):
        """Values the user asked to forget, as of session t."""
        out, prev = [], None
        for s, v in self.fact_by_key[key]["truth"]:
            if s <= t and v is None and prev is not None:
                out.append(prev)
            prev = v
        return out

    def mentions(self, key):
        return {int(s): v for s, v in self.fact_by_key[key].get("mentions", {}).items()}

    def questions_at(self, cp):
        for c in self.checkpoints:
            if c["after"] == cp:
                return c["questions"]
        return []

    @property
    def checkpoint_list(self):
        return [c["after"] for c in self.checkpoints]

    def date_after(self, t):
        return self.sessions[min(t, self.n) - 1].get("date") or ""

    def public(self):
        """What the page needs: the history plus token counts."""
        return {**self.data, "slug": self.slug, "session_tokens": self.session_tokens, "editable": self.editable}
