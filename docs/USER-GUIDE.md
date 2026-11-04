# Memory Duel user guide

## The four steps

**1. Basics.** Eleven short screens. If memory for AI chat is new to you, read them in order; each has a diagram. The key idea: a model remembers nothing between calls, so every memory system is a decision about what to copy back into the context window.

**2. History.** The demo user, Nell, and her 20 chats. Click a session circle to read it. Chips above the chat show which facts changed in that session. On the right, the answer key: each row is a fact, each bar a value and the sessions it was true for. The orange line marks the session you're reading.

**3. Duel.** From top to bottom:

- **Results panel.** Says whether you're looking at the saved demo results (scripted) or your own live results, with run buttons if you have a key.
- **Quiz after session.** Pick a checkpoint: 5, 10, 15 or 20.
- **Sliding window size.** How many recent sessions the sliding window keeps. With the demo results the page switches instantly. With live results, a button offers to rerun just the sliding window at the new size.
- **Replay sessions.** Animates the memory maps filling in, session by session.
- **Contestants shown.** Click a name to hide or show it. Live runs use the contestants shown.
- **Memory maps.** One per contestant. Rows are facts about Nell, columns are sessions. Each square says what that memory held about that fact after that session:
  - green: current (the right value now)
  - amber: stale (an old value, as if still true)
  - yellow: partial; striped yellow: conflicting (old and new values both held as true)
  - dashed outline: missing
  - red: should be forgotten (Nell asked to forget it, but it's still stored)
  - small green dot: forgotten as asked
  The bar under each name shows how many tokens of memory it sends with each answer, compared with the others.
- **Score.** Right counts 1, partly ½. "Still stored" also counts ½: the answer declined, but the memory kept what Nell asked it to forget.
- **Questions.** Click one. The dots on each card are the contestants' grades.
- **Answer cards.** The answer, its grade, what that memory held when it answered (relevant parts highlighted), why it got that grade, and what the answer cost.

**4. Debrief.** Accuracy at each checkpoint; tokens sent with each answer (on a log scale, so the cheap strategies stay visible); every answer as a colored square by question type (hover for details); a cost table; and a guide to when to use which.

## Grades

| Grade | Meaning |
|---|---|
| Right | matches the answer key (declining is right when the key says it should) |
| Partly | some of it |
| Still stored | declined to share what Nell asked it to forget, but the memory still holds it |
| Stale | gave a value that used to be true |
| Missed | said it doesn't know, though the answer was told |
| Invented | made up an answer to something never said |
| Wrong | anything else incorrect |
| Leaked | repeated what Nell asked it to forget |

## Your own chat history

1. **Import it.** On the History step, click **+ Add a history**, give it a name and your name, and choose a JSON file. The format: a list of sessions, each like `{"date": "2026-10-20", "topic": "…", "turns": [{"role": "user", "text": "…"}, {"role": "assistant", "text": "…"}]}`. Roles can also be human/ai or learner/tutor, and "content" works in place of "text". A file with one session per line (JSON Lines) works too.
   - **From a ChatGPT or Claude export, or Hablemos:** in a Command Prompt in the memory-duel folder, run
     `.venv\Scripts\python tools\import_history.py "C:\path\to\file" --user "Your name"`
     and refresh the page. The file can be ChatGPT's `conversations.json` (Settings → Data controls → Export data), Claude's `conversations.json` (Settings → Privacy → Export data), or `hablemos.db` (close Hablemos first, or use a copy; it reads only lessons and their turns, never the settings table where your Gemini key is stored). Each conversation becomes one session, in date order. Sessions with fewer than 2 turns (4 for Hablemos) are skipped; `--min-turns 1` keeps them. `--since 2026-01-01` or `--limit 40` trims a big export, since drafting an answer key costs about a cent per session.
2. **Draft the answer key.** Pick the history, then **Draft the answer key with Claude**. The page shows the cost first (about a cent per session). Claude reads each session in order, noting facts about you as they appear, change or get forgotten, keeps the 12 that make the best test (ones that changed come first), and writes questions for four checkpoints.
3. **Review it.** The editor opens when the draft is done. For each fact, check its values and the session each one starts from; tick "forgotten" for something you asked the assistant to forget. For each question, check the wording, the answer key, and any outdated values. "Other facts Claude found" lists facts left out of the test; click one to add it. **Save answer key.**
4. **Run the duel** on the Duel step, as with the demo.

Your chats stay on your computer, except when you draft an answer key or run the duel: then the session text is sent to the Anthropic API. **Delete this history** removes it and its results from the app.

## Running it live

1. Put your Anthropic API key in `.env` (see the README) and restart with `run.bat`.
2. On the Duel step, click **Run it live**. The page shows an estimate first (about $3 for all six); click **Start**.
3. Progress bars show each contestant's session and quiz. Contestants run in parallel and fail independently: if one fails, the others still finish and its cards show the reason.
4. When it finishes, the page shows your live results. **Show the scripted demo** deletes your live results and goes back to the demo.

To spend less, hide the full transcript (it’s nearly three-quarters of the cost) or run only one or two contestants.

## Settings (.env)

| Setting | Default | What it does |
|---|---|---|
| `MDUEL_WORK_MODEL` | claude-haiku-5-5 | updates memory, checks memory, grades |
| `MDUEL_ANSWER_MODEL` | claude-sonnet-5-5 | answers the quiz |
| `MDUEL_MAX_RUN_DOLLARS` | 6.00 | stops a run that spends more |
| `MDUEL_WINDOW_SESSIONS` | 3 | default sliding window size |
| `MDUEL_SUMMARY_WORDS` | 200 | rolling summary cap |
| `MDUEL_NOTES_WORDS` | 400 | self-editing notebook cap |
| `MDUEL_RAG_TOP_K` | 4 | past messages RAG sends |
| `MDUEL_EMBED_BACKEND` | auto | fastembed if installed, otherwise word matching |
| `MDUEL_PORT` | 8010 | the local web address's port |

## Changing the demo history

The history lives in `tools/make_nell.py` as readable Python: the sessions, the facts with the session each became true, and the quiz. Edit it and run `python tools/make_nell.py`, then `python tools/build_demo.py` to rebuild the saved results. The longer back-and-forth in each session (ordinary help with no new facts about Nell) is in `demo/nell/extra/`.

## Troubleshooting

- **"Claude rejected the API key."** Check `ANTHROPIC_API_KEY` in `.env`, then close the black window and run `run.bat` again.
- **Rate limits.** New Anthropic accounts allow only so many tokens per minute, and the full transcript sends a lot. The app runs at most two answer calls at once and waits and retries when it hits a limit, so runs are slower but complete. If answers still fail, click **Retry failed answers** (answers that worked are reused for free), or lower `MDUEL_ANSWER_CONCURRENCY` in `.env` to 1.
- **"Stopped: this run passed the budget."** Raise `MDUEL_MAX_RUN_DOLLARS` in `.env`, or run fewer contestants. Calls already made are cached, so the next run picks up where it stopped at no extra cost.
- **The page looks stuck after a `git pull`.** Press Ctrl+F5 to reload it without the browser's cache.
- **The RAG contestant uses word matching.** Install fastembed (`run.bat` tries automatically) for meaning-based search. The scripted demo always uses word matching, so it behaves as described.
