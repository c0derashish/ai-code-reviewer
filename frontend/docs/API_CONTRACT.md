# VEDIX API contract (PROPOSED)

Status: **proposal.** The backend is not built. The frontend is written against this
file. Change the file and the frontend together.

## Conventions

- Base URL: `VITE_API_BASE_URL`, for example `http://localhost:8000`.
- JSON in and out. Field names are snake_case.
- Errors: HTTP 4xx or 5xx with `{"detail": "short message"}`. The frontend shows `detail`
  for 4xx only. Never put secrets or stack traces in it.
- Auth: httpOnly session cookie. The frontend sends `credentials: "include"`.
- CORS (FastAPI):
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173"],  # exact origins, never "*" with cookies
      allow_credentials=True,
      allow_methods=["GET", "POST"],
      allow_headers=["Content-Type"],
  )
  ```
- Job status values: `queued`, `running`, `done`, `failed`.

## Analysis (wired in the frontend)

### POST /analyses
Multipart form. Starts an analysis. Returns at once.

| Field | Type | Notes |
|---|---|---|
| `project_name` | text | up to 100 characters |
| `scope` | text | `file` or `project` |
| `paths` | text, repeated | project-relative path of each file |
| `files` | file, repeated | same order as `paths` |

`202`: `{ "id": "abc123", "status": "queued" }`
Errors: `413` too large, `422` bad input, `429` too many requests.

### GET /analyses/{id}
Frontend asks every 1.5 seconds, for up to 3 minutes.

`200`:
```json
{
  "id": "abc123",
  "status": "done",
  "score": 74,
  "error": null,
  "issues": [
    {
      "id": "i1",
      "file_path": "src/app.py",
      "line": 12,
      "severity": "high",
      "category": "security",
      "title": "SQL built from user input",
      "explanation": "...",
      "suggestion": "...",
      "before": "...",
      "after": "..."
    }
  ]
}
```
- `severity`: `critical`, `high`, `medium`, `low`, `info`. Unknown values become `info`.
- `category`: `security`, `bug`, `complexity`, `maintainability`, `code_smell`,
  `performance`, `style`. Unknown values become `code_smell`.
- `file_path` must be one of the sent paths. `line` is 1-based. Other rows are dropped.
- `status` `failed`: set `error` to a short reason.

## Repositories (submit wired, rest NOT wired)

### POST /repositories
Body `{ "url": "https://github.com/owner/repo" }`. `202`: `{ "id": "r1", "status": "queued" }`.

Next, not wired in the frontend yet:
- `GET /repositories/{id}`: status, and `error` if it failed.
- `GET /repositories/{id}/files`: `{ "files": [{ "path", "language", "content" }] }`,
  to open the repository in the workspace.

## Account and history (NOT wired, mock in the frontend)

| Endpoint | Purpose |
|---|---|
| `POST /auth/register` | `{ name, email, password }`. Sets the session cookie |
| `POST /auth/login` | `{ email, password }`. Sets the session cookie |
| `GET /auth/me` | The current user, or `401` |
| `POST /auth/logout` | Clears the cookie |
| `GET /analyses` | The user's past analyses |
| `GET /analyses/{id}` | One analysis (same endpoint as above) |

## Backend must (the browser is not trusted)

- Re-check every size, count, type, and path. Reject `..`, absolute paths, and
  backslashes in `paths`.
- Allow only `https://github.com/owner/repo` for repositories. Block redirects and private
  or internal addresses, so users cannot use the server to reach internal services.
- Limits: 2 MB per file, 500 files, 25 MB per request. Add rate limits.
- Hash passwords with argon2 or bcrypt. Rate-limit login. Cookie flags: `HttpOnly`,
  `Secure`, `SameSite=Lax` or `Strict`. Add CSRF protection for state-changing calls.
- Never log uploaded code or passwords.
- Treat uploaded code as data. Never execute it. Run any tooling in a sandbox.