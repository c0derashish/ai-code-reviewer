from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool

from analyzer.languages import detect_language
from api.auth import (
    COOKIE_NAME,
    LoginLimiter,
    check_email,
    check_name,
    check_origin,
    check_password,
    clear_session_cookie,
    client_ip,
    set_session_cookie,
)
from api.jobs import JobStore
from api.limits import BodySizeLimitMiddleware
from api.repo_runner import run_fetch
from api.repos import RepoStore
from api.runner import run_job
from api.schemas import (
    AnalyticsOut,
    DeleteAccountRequest,
    HistoryDetailOut,
    HistoryItemOut,
    LoginRequest,
    RegisterRequest,
    RepoFileOut,
    RepositoryFilesOut,
    RepositoryRequest,
    RepositoryStatusOut,
    ResultOut,
    StartResponse,
    UserOut,
)
from api.settings import Settings
from app_db import analyses as history_db
from app_db import passwords, sessions, users
from app_db.connection import ensure_indexes
from app_db.licences import describe_storage
from input_manager import from_uploads
from input_manager.models import InputError
from input_manager.rules import MAX_FILE_BYTES
from repo_fetcher.github import FetchError, parse_github_url

MAX_UPLOAD_FILES = 1000  # also the default limit of the form parser
SCOPES = ("file", "project")
NO_ACCOUNTS = "Accounts are not set up on this server."
TOO_MANY_ATTEMPTS = "Too many failed attempts. Try again in 15 minutes."


def _read_flag(text):
    """True, False, or None when the request did not say. Unclear text means False."""
    if text is None:
        return None
    return text.strip().lower() in ("1", "true", "yes", "on")


def create_app(settings=None, ai_provider=None, open_url=None, database=None) -> FastAPI:
    """open_url: how to reach GitHub (None = the real network). database: a PyMongo database
    (None = no accounts). Tests give a fake open_url and a mongomock database."""
    settings = settings or Settings()
    docs = settings.docs_enabled

    app = FastAPI(
        title="VEDIX API",
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    store = JobStore(settings.job_ttl_seconds, settings.max_stored_jobs)
    repos = RepoStore(settings.repo_ttl_seconds, settings.max_stored_repos)
    pair_limiter = LoginLimiter(max_failures=5)   # per address and email
    ip_limiter = LoginLimiter(max_failures=20)    # per address
    app.state.store = store
    app.state.repos = repos
    app.state.database = database

    if database is not None:
        ensure_indexes(database)

    # The last middleware added is the outermost one. CORS must be outermost,
    # so that even a "too large" answer carries the CORS headers the browser needs.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # VEDIX reads "detail" only when it is text
        path = request.url.path
        if path.startswith("/repositories"):
            text = 'The request is not valid. Send JSON like {"url": "https://github.com/owner/repository"}.'
        elif path.startswith("/auth"):
            text = "The request is not valid. Send name, email and password."
        elif path.startswith("/history") or path.startswith("/analytics"):
            text = "The request is not valid. Check the values you sent."
        else:
            text = "The request is not valid. Send project_name, scope, paths and files."
        return JSONResponse(status_code=422, content={"detail": text})

    @app.exception_handler(PyMongoError)
    async def database_problem(request, error):
        return JSONResponse(
            status_code=503, content={"detail": "The database is not reachable. Try again later."}
        )

    # ---------- helpers for accounts ----------

    def need_database():
        # 400, not 503: VEDIX shows the message of a 4xx answer, but hides a 5xx message
        if database is None:
            raise HTTPException(status_code=400, detail=NO_ACCOUNTS)

    def current_user(request):
        need_database()
        return sessions.get_user_by_token(database, request.cookies.get(COOKIE_NAME))

    def require_user(request):
        user = current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Please sign in.")
        return user

    def optional_user(request):
        """The signed-in user, or None. Never an error: analysis also works signed out."""
        if database is None:
            return None
        return sessions.get_user_by_token(database, request.cookies.get(COOKIE_NAME))

    def start_session(response, user):
        token = sessions.create_session(database, user["_id"], settings.session_days)
        set_session_cookie(response, token, settings)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ---------- accounts ----------

    @app.post("/auth/register", status_code=201, response_model=UserOut)
    def register(body: RegisterRequest, request: Request, response: Response):
        check_origin(request, settings.allowed_origins)
        need_database()
        problem = check_name(body.name) or check_email(body.email) or check_password(body.password)
        if problem:
            raise HTTPException(status_code=422, detail=problem)

        try:
            user = users.create_user(database, body.name, body.email, body.password)
        except users.DuplicateEmail:
            raise HTTPException(
                status_code=409, detail="An account with this email already exists."
            ) from None

        start_session(response, user)
        return users.public_user(user)

    @app.post("/auth/login", response_model=UserOut)
    def login(body: LoginRequest, request: Request, response: Response):
        check_origin(request, settings.allowed_origins)
        need_database()

        email = body.email.strip().lower()
        ip = client_ip(request)
        pair_key = (ip, email)
        if pair_limiter.blocked(pair_key) or ip_limiter.blocked(ip):
            raise HTTPException(status_code=429, detail=TOO_MANY_ATTEMPTS)

        user = users.find_by_email(database, email)
        stored_hash = user["password_hash"] if user else None
        if not passwords.verify(stored_hash, body.password):
            pair_limiter.record_failure(pair_key)
            ip_limiter.record_failure(ip)
            # the same answer for an unknown email and a wrong password
            raise HTTPException(status_code=401, detail="Wrong email or password.")

        pair_limiter.reset(pair_key)
        start_session(response, user)
        return users.public_user(user)

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request):
        check_origin(request, settings.allowed_origins)
        if database is not None:
            sessions.delete_session(database, request.cookies.get(COOKIE_NAME))
        response = Response(status_code=204)
        clear_session_cookie(response, settings)
        return response

    @app.get("/auth/me", response_model=UserOut)
    def me(request: Request):
        return users.public_user(require_user(request))

    @app.delete("/auth/account", status_code=204)
    def delete_account(body: DeleteAccountRequest, request: Request):
        check_origin(request, settings.allowed_origins)
        user = require_user(request)

        key = (client_ip(request), user["email"])
        if pair_limiter.blocked(key):
            raise HTTPException(status_code=429, detail=TOO_MANY_ATTEMPTS)
        if not passwords.verify(user["password_hash"], body.password):
            pair_limiter.record_failure(key)
            raise HTTPException(status_code=401, detail="Wrong password.")

        users.delete_account(database, user["_id"])
        response = Response(status_code=204)
        clear_session_cookie(response, settings)
        return response

    # ---------- analysis of uploaded files ----------

    @app.post("/analyses", status_code=202, response_model=StartResponse)
    async def start_analysis(
        request: Request,
        background_tasks: BackgroundTasks,
        project_name: str = Form(..., max_length=200),
        scope: str = Form(...),
        paths: list[str] = Form(...),
        files: list[UploadFile] = File(...),
        ai_review: str | None = Form(None),
        save: str | None = Form(None),
        repo_id: str | None = Form(None, max_length=100),
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

        # A signed-in user's analysis is saved, unless the request says save=false.
        user = await run_in_threadpool(optional_user, request)
        save_target = None
        if user is not None:
            check_origin(request, settings.allowed_origins)  # the cookie came with this request
            if _read_flag(save) is not False:
                source, repo = "upload", None
                if repo_id:
                    entry = repos.get(repo_id)
                    if entry is None or entry.status != "done":
                        raise HTTPException(
                            status_code=422, detail="The repository has expired. Fetch it again."
                        )
                    source = "github"
                    repo = {
                        "owner": entry.owner,
                        "repo": entry.repo,
                        "url": f"https://github.com/{entry.owner}/{entry.repo}",
                        "licence": entry.licence,
                    }
                save_target = {
                    "database": database, "user_id": user["_id"], "source": source, "repo": repo,
                }

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
            save_target,
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

    # ---------- the saved history of a signed-in user ----------

    @app.get("/history", response_model=list[HistoryItemOut])
    def history_list(request: Request, limit: int = 50, skip: int = 0):
        user = require_user(request)
        return history_db.list_history(database, user["_id"], limit, skip)

    @app.get("/history/{analysis_id}", response_model=HistoryDetailOut)
    def history_detail(analysis_id: str, request: Request):
        user = require_user(request)
        document = history_db.get_analysis(database, user["_id"], analysis_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Analysis not found.")
        return history_db.history_detail(database, user["_id"], document)

    @app.get("/history/{analysis_id}/files", response_model=RepositoryFilesOut)
    def history_files(analysis_id: str, request: Request):
        user = require_user(request)
        document = history_db.get_analysis(database, user["_id"], analysis_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Analysis not found.")

        saved = history_db.get_files(database, user["_id"], document)
        if saved is None:
            reason = document.get("storage_reason") or "Only the link is stored."
            raise HTTPException(
                status_code=409, detail=f"{reason} Fetch the repository again to see the code."
            )
        return RepositoryFilesOut(
            project_name=document["project_name"], files=[RepoFileOut(**item) for item in saved]
        )

    @app.delete("/history/{analysis_id}", status_code=204)
    def history_delete(analysis_id: str, request: Request):
        check_origin(request, settings.allowed_origins)
        user = require_user(request)
        document = history_db.get_analysis(database, user["_id"], analysis_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Analysis not found.")
        history_db.delete_analysis(database, user["_id"], document)
        return Response(status_code=204)

    @app.get("/analytics", response_model=AnalyticsOut)
    def analytics_route(request: Request):
        user = require_user(request)
        return history_db.analytics(database, user["_id"])

    # ---------- public GitHub repositories ----------

    @app.post("/repositories", status_code=202, response_model=StartResponse)
    async def submit_repository(body: RepositoryRequest, background_tasks: BackgroundTasks):
        if not settings.repos_enabled:
            raise HTTPException(
                status_code=400,
                detail="Repository fetching is switched off on this server. Upload the code instead.",
            )
        try:
            owner, repo = parse_github_url(body.url)
        except FetchError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

        entry = repos.try_create(settings.max_active_fetches, owner, repo)
        if entry is None:
            raise HTTPException(
                status_code=429,
                detail="The server is busy fetching other repositories. Try again in a minute.",
            )

        background_tasks.add_task(run_fetch, repos, entry.id, owner, repo, open_url)
        return StartResponse(id=entry.id, status=entry.status)

    @app.get("/repositories/{repo_id}", response_model=RepositoryStatusOut)
    def get_repository(repo_id: str):
        entry = repos.get(repo_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Repository not found. It may have expired.")

        project = entry.project
        storage = describe_storage("github", entry.licence) if entry.status == "done" else None
        return RepositoryStatusOut(
            id=entry.id,
            status=entry.status,
            project_name=project.project_name if project else None,
            file_count=project.file_count if project else None,
            skipped_count=project.skipped_count if project else None,
            error=entry.error,
            licence=entry.licence,
            storage=storage["storage"] if storage else None,
            storage_reason=storage["reason"] if storage else None,
        )

    @app.get("/repositories/{repo_id}/files", response_model=RepositoryFilesOut)
    def get_repository_files(repo_id: str):
        entry = repos.get(repo_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Repository not found. It may have expired.")
        if entry.status != "done" or entry.project is None:
            raise HTTPException(
                status_code=409, detail=entry.error or "The repository is not ready yet."
            )

        files = [
            RepoFileOut(
                path=code_file.file_path,
                language=detect_language(code_file.file_path, code_file.source_code)["language"]
                or "plaintext",
                content=code_file.source_code,
            )
            for code_file in entry.project.files
        ]
        return RepositoryFilesOut(project_name=entry.project.project_name, files=files)

    return app