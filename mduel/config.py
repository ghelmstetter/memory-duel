"""Settings, read from environment variables or a .env file in the project folder."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is optional
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("MDUEL_DATA_DIR", ROOT / "data"))
DATASETS_DIR = DATA_DIR / "datasets"
RESULTS_DIR = DATA_DIR / "results"
CACHE_DIR = DATA_DIR / "cache"
DEMO_DIR = ROOT / "demo"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Cheap, fast model for the bulk work: updating summaries, facts and notes, checking memory, grading.
WORK_MODEL = os.getenv("MDUEL_WORK_MODEL", "claude-haiku-5-5")
# Stronger model that writes the answers you compare.
ANSWER_MODEL = os.getenv("MDUEL_ANSWER_MODEL", "claude-sonnet-5-5")

# Prices in US dollars per million tokens, used for the cost meter and estimates.
# Check current prices at https://www.anthropic.com/pricing and update if they change.
PRICES = {
    WORK_MODEL: (float(os.getenv("MDUEL_WORK_PRICE_IN", "0.10")), float(os.getenv("MDUEL_WORK_PRICE_OUT", "0.50"))),
    ANSWER_MODEL: (float(os.getenv("MDUEL_ANSWER_PRICE_IN", "2.00")), float(os.getenv("MDUEL_ANSWER_PRICE_OUT", "10.00"))),
}

# Stop a run if it spends more than this many dollars.
MAX_RUN_DOLLARS = float(os.getenv("MDUEL_MAX_RUN_DOLLARS", "6.00"))

# How many calls to each model run at once. Lower these if you see rate-limit waits or errors
# (new Anthropic accounts have low per-minute limits); raise them on a higher usage tier.
ANSWER_CONCURRENCY = int(os.getenv("MDUEL_ANSWER_CONCURRENCY", "2"))
WORK_CONCURRENCY = int(os.getenv("MDUEL_WORK_CONCURRENCY", "4"))

# Contestant settings.
WINDOW_SESSIONS = int(os.getenv("MDUEL_WINDOW_SESSIONS", "3"))   # sliding window size, in sessions
SUMMARY_WORDS = int(os.getenv("MDUEL_SUMMARY_WORDS", "200"))      # rolling summary cap
NOTES_WORDS = int(os.getenv("MDUEL_NOTES_WORDS", "400"))          # self-editing notes cap
RAG_TOP_K = int(os.getenv("MDUEL_RAG_TOP_K", "4"))                # past messages retrieved per question

# "auto" uses fastembed if installed, otherwise a simple word-matching (TF-IDF) fallback.
EMBED_BACKEND = os.getenv("MDUEL_EMBED_BACKEND", "auto")
EMBED_MODEL = os.getenv("MDUEL_EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# For tests: a stand-in for Claude that returns canned JSON, so no key or network is needed.
FAKE_LLM = os.getenv("MDUEL_FAKE_LLM", "") == "1"

PORT = int(os.getenv("MDUEL_PORT", "8010"))

# Hosted public demo (e.g. Vercel): only the bundled demo with its saved results; never calls
# Claude, even if a key is set, so strangers can't run up a bill.
PUBLIC_DEMO = os.getenv("MDUEL_PUBLIC_DEMO", "") == "1"
REPO_URL = "https://github.com/ghelmstetter/memory-duel"


def has_key() -> bool:
    if PUBLIC_DEMO:
        return False
    return bool(ANTHROPIC_API_KEY) or FAKE_LLM
