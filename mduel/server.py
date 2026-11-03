"""The web server: serves the page and a small JSON API."""
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import config, pipeline
from .contestants import INFO, ORDER
from .history import History

WEB = config.ROOT / "web"


def ok(data, status=200):
    return JSONResponse(data, status_code=status)


def fail(msg, status=400):
    return JSONResponse({"error": msg}, status_code=status)


def guarded(fn):
    async def wrapper(request):
        try:
            return await fn(request)
        except (ValueError, FileNotFoundError) as e:
            return fail(str(e))
        except PermissionError as e:
            return fail(str(e), 403)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return fail(pipeline.friendly_error(e), 500)
    return wrapper


LOCAL_ONLY = ("The hosted demo shows saved results only. To run the contestants live, "
              "run Memory Duel on your computer: " + config.REPO_URL)


def _local_only():
    if config.PUBLIC_DEMO:
        raise PermissionError(LOCAL_ONLY)


async def index(request):
    return FileResponse(WEB / "index.html")


@guarded
async def status(request):
    return ok({"has_key": config.has_key(), "public": config.PUBLIC_DEMO, "fake": config.FAKE_LLM,
               "answer_model": config.ANSWER_MODEL, "work_model": config.WORK_MODEL,
               "prices": {m: list(p) for m, p in config.PRICES.items()},
               "window": config.WINDOW_SESSIONS, "budget": config.MAX_RUN_DOLLARS,
               "contestants": [{"id": c, **INFO[c]} for c in ORDER], "repo": config.REPO_URL})


@guarded
async def histories(request):
    return ok(pipeline.list_histories())


@guarded
async def history(request):
    return ok(History.load(request.path_params["slug"]).public())


@guarded
async def results(request):
    return ok(pipeline.results_for(request.path_params["slug"]) or {})


@guarded
async def estimate(request):
    q = request.query_params
    only = [c for c in q.get("only", "").split(",") if c] or None
    return ok(pipeline.estimate(request.path_params["slug"], only, int(q.get("window") or config.WINDOW_SESSIONS)))


@guarded
async def run(request):
    _local_only()
    body = await request.json()
    job = await run_in_threadpool(pipeline.start_run, request.path_params["slug"], body.get("only"),
                                  body.get("window"), bool(body.get("fresh")))
    return ok({"job": job["id"]})


@guarded
async def job(request):
    return ok(pipeline.job_status(request.path_params["id"]))


@guarded
async def clear(request):
    _local_only()
    pipeline.clear_live(request.path_params["slug"])
    return ok({"cleared": True})


routes = [
    Route("/", index),
    Route("/api/status", status),
    Route("/api/histories", histories),
    Route("/api/history/{slug}", history),
    Route("/api/results/{slug}", results),
    Route("/api/estimate/{slug}", estimate),
    Route("/api/run/{slug}", run, methods=["POST"]),
    Route("/api/jobs/{id}", job),
    Route("/api/results/{slug}/clear", clear, methods=["POST"]),
    Mount("/static", StaticFiles(directory=WEB), name="static"),
]

app = Starlette(routes=routes)
