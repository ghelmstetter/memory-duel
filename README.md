# Memory Duel

**This app compares six memory strategies for AI chat, side by side:** full transcript, sliding window, rolling summary, fact memory, RAG over past chats, and self-editing memory. It's also a hands-on tutorial. A fictional user, Nell, chats with an assistant 20 times over five months while her life changes. Each memory strategy replays those chats and keeps whatever its strategy keeps. At four checkpoints the assistant is quizzed using only that memory, and a judge grades each answer against an exact answer key.

It's built for learning, not production. Everything is small, visible and explained. It's the sequel to [Retrieval Duel](https://github.com/ghelmstetter/retrieval-duel).

## What's inside

1. **Basics**: an 11-screen walkthrough: the context window, why long memory costs more, kinds of memory, write policies, updating and forgetting, summaries, retrieval, memory in the weights, privacy, and how memory gets tested.
2. **History**: read Nell's 20 chats, and see the answer key: what was true about her after each session.
3. **Duel**: a memory map for each contestant shows what it held about each fact after every session (current, stale, conflicting, missing, or something it should have forgotten). Then the checkpoint quiz: every contestant's answer, its grade, and the memory it answered from.
4. **Debrief**: accuracy at each checkpoint against the tokens each strategy sends with every answer, results by question type, what each one cost, and when to use which.

The quiz has six kinds of question: recall, updates, time order, combining facts, forgetting ("What was my old address?" after Nell asked the assistant to forget it), and false memory (asking about a cat she never mentioned).

## Quick start (Windows)

1. Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/). During setup, tick **"Add python.exe to PATH."**
2. Get the code: `git clone https://github.com/ghelmstetter/memory-duel.git`, then open the folder.
3. **Double-click `run.bat`.** The first time, it creates a private Python environment, installs the libraries (a few minutes), creates a `.env` file, and opens the app in your browser at http://localhost:8010.
4. For live runs, open `.env` in Notepad, paste your key after `ANTHROPIC_API_KEY=`, save, close the black window, and double-click `run.bat` again.

To update later: `git pull`, then `run.bat`.

<details><summary>Manual setup (Mac, Linux, or if you prefer the terminal)</summary>

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install fastembed        # optional but recommended: meaning-based search for the RAG contestant
cp .env.example .env         # Windows: copy .env.example .env   then add your key
python -m mduel
```
</details>

## Saved results and live runs

Without a key, the app shows **saved demo results**. These are scripted: three contestants (full transcript, sliding window, RAG) are computed from the chat text itself, including a word-matching search; the other three need a model to write their memory, so their memory contents were written by hand to show typical behavior and typical mistakes. The page labels them as scripted.

With a key, **Run it live** replays the history through every contestant with Claude: a cheap model (Haiku) updates the summary, facts and notes after each session and checks what each memory holds; a stronger model (Sonnet) answers the quiz; the cheap model grades. You can run all six or only the ones shown, and rerun just the sliding window at a different size.

To make your live results the demo's saved results: `python tools/build_demo.py --from-live`.

## Your own chat history

On the History step, **+ Add a history** imports a JSON file of your chats: a list of sessions, each with an optional date and topic, and its turns (`{"role": "user" | "assistant", "text": "..."}`). From the command line, `tools/import_history.py` also reads a **ChatGPT export** or a **Claude export** (`conversations.json`), or a database from Hablemos (the author's Spanish-tutor app), detecting the format by itself:

```
.venv\Scripts\python tools\import_history.py path\to\conversations.json --user "Your name"
```

Each conversation becomes one session, in date order. `--since 2026-01-01` or `--limit 40` trims a big export. Then refresh the page.

An imported history needs an answer key before it can be quizzed. **Draft the answer key with Claude** reads every session once with the answer model (roughly $0.01 per session) and proposes the facts about you, the session where each became true, changed or was forgotten, and questions at four checkpoints. Then **review and edit it**: only you know what's true, and speech-recognition errors can mislead the draft. Saving the key clears results graded against an older version. Your chats stay on your computer except when you draft a key or run the duel, when they're sent to the Anthropic API.

## Costs and safety

- **A full live run is about $3** with the default models and prices. Almost all of it is the full transcript contestant, which sends the whole history (about 50,000 tokens by session 20) with every answer. That is the lesson in miniature.
- The page shows an estimate before every run, and `MDUEL_MAX_RUN_DOLLARS` in `.env` (default $6) stops a run that goes over.
- **Every AI call is cached** in `data/cache`, so running the same thing again is free. "Run again with fresh calls" skips the cache.
- Your key lives only in `.env`, which is excluded from git.

## How the contestants work

| Contestant | After each session | Sent with each answer |
|---|---|---|
| Full transcript | nothing | every past session |
| Sliding window | nothing | the last N sessions (N set on the Duel page) |
| Rolling summary | the cheap model rewrites a summary, capped at 200 words | the summary |
| Fact memory | the cheap model adds new facts and retires outdated ones (the add/retire design many chat apps use) | the active facts |
| RAG over past chats | nothing (every message is stored in a search index) | the 4 past messages closest to the question |
| Self-editing memory | the cheap model edits its own notebook (writes, rewrites and deletes notes), capped at 400 words | the notebook |

**The answer key is an event log, not prose.** Each fact about Nell has a value and the session where it became true (her city is Denver from session 1 and Boise from session 11; her old address is forgotten on request at session 13). The quiz questions and reference answers come straight from it, and the memory maps are checked against it: for the transcript contestants by which sessions they hold; for the summary, facts and notes by a cheap model that reads the memory and reports each fact's state.

**Simplifications, on purpose:** self-editing memory edits its notes once at the end of each session rather than with tool calls during the chat (a simplified MemGPT/Letta pattern). RAG stores each user message with the reply to it. Grading uses one judge call per answer. Scripted results show typical behavior; live runs can differ, and a single run on 31 questions is a small sample.

## Project layout

```
mduel/              Python package
  config.py         settings from .env
  llm.py            Claude calls, disk cache, token and cost metering (from Retrieval Duel)
  history.py        loading a chat history and its answer key
  datasets.py       importing your own histories, drafting and saving their answer keys
  contestants.py    the six memory strategies, and the answer prompt
  grading.py        memory maps (what each memory holds) and the judge
  pipeline.py       the run: replay, checkpoint quizzes, saving results
  embed.py          fastembed or word-matching embeddings for RAG
  server.py         web API (Starlette)
web/                the page (HTML, CSS, plain JS and SVG)
demo/nell/          the demo history (history.json) and its saved results (results.json)
tools/make_nell.py  writes the demo history from readable Python
tools/build_demo.py builds the saved demo results
tools/import_history.py   imports ChatGPT or Claude exports, Hablemos lessons, or a chat file
docs/USER-GUIDE.md  full walkthrough
run.bat             one-click setup and start for Windows
api/index.py        Vercel entry point (public demo mode)
tests/              offline tests (python -m tests.test_offline)
```

## Ideas for later

- Import samples of LongMemEval and LoCoMo.
- Hablemos's own memory code as a seventh contestant.
- A second track for agents: a long task interrupted after each step and resumed by a fresh session (no memory, compaction, a notes file, notes plus progress files).
- Prompt caching for the long-context contestants, to show how it changes the cost picture.
- A replay tool for apps with their own memory code, so the app's real memory logic can run as a contestant.

## License

[MIT](LICENSE) © 2026 Greg Helmstetter.
