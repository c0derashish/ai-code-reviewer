from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from api.jobs import JobStore
from api.limits import BodySizeLimitMiddleware
from api.runner import run_job
from api.schemas import ResultOut, StartResponse
from api.settings import Settings
from input_manager import from_uploads
from input_manager.models import InputError
from input_manager.rules import MAX_FILE_BYTES

MAX_UPLOAD_FILES = 1000  # also the default limit of the form parser
SCOPES = ("file", "project")


def _read_flag(text):
    """True, False, or None when the request did not say. Unclear text means False."""
    if text is None:
        return None
    return text.strip().lower() in ("1", "true", "yes", "on")


def create_app(settings=None, ai_provider=None) -> FastAPI:
    settings = settings or Settings()
    docs = settings.docs_enabled

    app = FastAPI(
        title="VEDIX API",
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    store = JobStore(settings.job_ttl_seconds, settings.max_stored_jobs)
    app.state.store = store

    # The last middleware added is the outermost one. CORS must be outermost,
    # so that even a "too large" answer carries the CORS headers the browser needs.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # VEDIX reads "detail" only when it is text
        return JSONResponse(
            status_code=422,
            content={"detail": "The request is not valid. Send project_name, scope, paths and files."},
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/analyses", status_code=202, response_model=StartResponse)
    async def start_analysis(
        background_tasks: BackgroundTasks,
        project_name: str = Form(..., max_length=200),
        scope: str = Form(...),
        paths: list[str] = Form(...),
        files: list[UploadFile] = File(...),
        ai_review: str | None = Form(None),
    ):
        if scope not in SCOPES:
            raise HTTPException(status_code=422, detail="scope must be 'file' or 'project'.")
        if not files or len(paths) != len(files):
            raise HTTPException(status_code=422, detail="Send one path for every file.")
        if len(files) > MAX_UPLOAD_FILES:
            raise HTTPException(
                status_code=422, detail=f"Too many files. The limit is {MAX_UPLOAD_FILES}."
            )

        # The path comes from the "paths" field. The upload's own file name is not used.
        items = []
        for path, upload in zip(paths, files):
            items.append((path, await upload.read(MAX_FILE_BYTES + 1)))

        try:
            project = await run_in_threadpool(from_uploads, project_name, items)
        except InputError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

        asked = _read_flag(ai_review)
        wants_ai = settings.ai_default_on if asked is None else asked
        provider = ai_provider if wants_ai else None

        job = store.try_create(settings.max_active_jobs)
        if job is None:
            raise HTTPException(
                status_code=429,
                detail="The server is busy with other analyses. Try again in a minute.",
            )

        background_tasks.add_task(
            run_job,
            store,
            job.id,
            project,
            scope,
            provider,
            settings.ai_max_files,
            settings.ai_time_budget_seconds,
        )
        return StartResponse(id=job.id, status=job.status)

    @app.get("/analyses/{analysis_id}", response_model=ResultOut)
    def get_analysis(analysis_id: str):
        job = store.get(analysis_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis not found. It may have expired.")
        return ResultOut(
            id=job.id,
            status=job.status,
            score=None,
            error=job.error,
            issues=job.issues,
            summary=job.summary,
        )

    @app.post("/repositories")
    def submit_repository():
        # 400, not 501: VEDIX shows the message of a 4xx answer, but hides a 5xx message.
        raise HTTPException(
            status_code=400,
            detail="Repository analysis is not available yet. Upload the code instead.",
        )

    return app