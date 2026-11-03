"""Start the app:  python -m mduel"""
import threading
import webbrowser

import uvicorn

from . import config, pipeline


def main():
    pipeline.ensure_dirs()
    url = f"http://localhost:{config.PORT}"
    print(f"\n  Memory Duel is running at {url}")
    if not config.ANTHROPIC_API_KEY:
        print("  No ANTHROPIC_API_KEY found: the demo's saved results work, but live runs need a key in .env")
    print("  Press Ctrl+C to stop.\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("mduel.server:app", host="127.0.0.1", port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
