import json
import urllib.error
import urllib.request

REQUEST_TIMEOUT_SECONDS = 60
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MAX_TOKENS = 2500


class ProviderError(Exception):
    """A request to the AI service failed. The message is safe to show.
    It never contains the API key."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect. A redirect could send the API key to another server."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _message_for_status(status) -> str:
    if status in (401, 403):
        return "The AI service refused the API key, or the model is not allowed for it."
    if status == 404:
        return "The AI service did not find this address or model. Check VEDIX_AI_BASE_URL and VEDIX_AI_MODEL."
    if status == 400:
        return "The AI service rejected the request (400). Check VEDIX_AI_MODEL."
    if status == 429:
        return "The AI service says there are too many requests (429). Wait and try again."
    if 300 <= status < 400:
        return "The AI service redirected the request. Check VEDIX_AI_BASE_URL."
    if status >= 500:
        return f"The AI service had a problem ({status}). Try again later."
    return f"The AI service answered with status {status}."


def _post_json(url, headers, body, timeout=REQUEST_TIMEOUT_SECONDS):
    """Send JSON, get JSON back. Only raises ProviderError."""
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:  # must come before OSError
        status = error.code
        error.close()
        raise ProviderError(_message_for_status(status)) from None
    except OSError:
        # covers connection problems and timeouts
        raise ProviderError("Cannot reach the AI service, or it took too long to answer.") from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("The AI service sent too much data.")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ProviderError("The AI service sent an unreadable answer.") from None


class BaseProvider:
    """All providers have a name, a model and complete(system, user) -> text."""

    name = "base"

    def __init__(self, model):
        self.model = model

    def complete(self, system, user) -> str:
        raise NotImplementedError


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, api_key, model, base_url="https://api.anthropic.com"):
        super().__init__(model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def complete(self, system, user) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = _post_json(f"{self.base_url}/v1/messages", headers, body)

        blocks = data.get("content") if isinstance(data, dict) else None
        text = ""
        if isinstance(blocks, list):
            text = "".join(
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if not text.strip():
            raise ProviderError("The AI service sent an empty answer.")
        return text


class OpenAICompatibleProvider(BaseProvider):
    """Works with any service that offers an OpenAI-style /chat/completions endpoint.

    No token limit is sent: some services reject the older name and some reject
    the newer one. The prompt asks for a short answer instead.
    """

    name = "openai_compatible"

    def __init__(self, api_key, model, base_url="https://api.openai.com/v1"):
        super().__init__(model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def complete(self, system, user) -> str:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = _post_json(f"{self.base_url}/chat/completions", headers, body)

        choices = data.get("choices") if isinstance(data, dict) else None
        text = None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("The AI service sent an empty answer.")
        return text