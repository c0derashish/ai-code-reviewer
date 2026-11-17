import json


def _describe(size) -> str:
    megabytes = size / (1024 * 1024)
    if megabytes >= 1:
        return f"{megabytes:.0f} MB"
    return f"{max(1, size // 1024)} KB"


async def _too_large(send, limit):
    text = f"The upload is too large. The limit is {_describe(limit)}."
    body = json.dumps({"detail": text}).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    })
    await send({"type": "http.response.body", "body": body})


def _content_length(scope):
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodySizeLimitMiddleware:
    """Reads the request body (up to max_bytes), then hands it on unchanged.

    The body is kept in memory, so max_bytes also limits memory per request.
    """

    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return

        length = _content_length(scope)
        if length is not None and length > self.max_bytes:
            await _too_large(send, self.max_bytes)
            return

        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return  # the client left
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await _too_large(send, self.max_bytes)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        data = b"".join(chunks)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": data, "more_body": False}
            return await receive()  # later calls: tell the app if the client disconnects

        await self.app(scope, replay, send)