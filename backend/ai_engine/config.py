import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ai_engine.providers import AnthropicProvider, OpenAICompatibleProvider

PROVIDERS = ["none", "anthropic", "openai_compatible"]
DEFAULT_BASE_URLS = {
    "anthropic": "https://api.anthropic.com",
    "openai_compatible": "https://api.openai.com/v1",
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ConfigError(Exception):
    """The AI settings are wrong. The message says what to fix and never contains the key."""


@dataclass
class AIConfig:
    provider: str = "none"
    model: str = ""
    api_key: str = field(default="", repr=False)  # repr=False: never shown when printed
    base_url: str = ""


def load_env_file(path=".env", environ=None):
    """Read KEY=VALUE lines from a file into the environment.
    A value that is already set is NOT replaced."""
    environ = os.environ if environ is None else environ
    try:
        with open(path, encoding="utf-8-sig") as source:  # utf-8-sig removes a BOM
            lines = source.read().splitlines()
    except OSError:
        return

    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        name, value = text.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in environ:
            environ[name] = value


def _check_base_url(url) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ConfigError(
            "VEDIX_AI_BASE_URL must be a full web address, like https://api.example.com/v1"
        )
    if parsed.username or parsed.password:
        raise ConfigError("VEDIX_AI_BASE_URL must not contain a user name or password.")
    if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS:
        raise ConfigError(
            "VEDIX_AI_BASE_URL must start with https:// (http:// is only allowed for localhost)."
        )
    return url.rstrip("/")


def load_ai_config(environ=None) -> AIConfig:
    environ = os.environ if environ is None else environ

    provider = environ.get("VEDIX_AI_PROVIDER", "none").strip().lower() or "none"
    if provider not in PROVIDERS:
        raise ConfigError(f"VEDIX_AI_PROVIDER must be one of: {', '.join(PROVIDERS)}.")
    if provider == "none":
        return AIConfig()

    model = environ.get("VEDIX_AI_MODEL", "").strip()
    if not model:
        raise ConfigError("VEDIX_AI_MODEL is not set. Choose a model name from your provider.")

    url = environ.get("VEDIX_AI_BASE_URL", "").strip() or DEFAULT_BASE_URLS[provider]
    base_url = _check_base_url(url)

    api_key = environ.get("VEDIX_AI_API_KEY", "").strip()
    is_local = urlparse(base_url).hostname in LOCAL_HOSTS
    if not api_key and not (provider == "openai_compatible" and is_local):
        raise ConfigError("VEDIX_AI_API_KEY is not set.")

    return AIConfig(provider=provider, model=model, api_key=api_key, base_url=base_url)


def create_provider(config):
    """The provider object for these settings, or None when AI review is off."""
    if config.provider == "anthropic":
        return AnthropicProvider(config.api_key, config.model, config.base_url)
    if config.provider == "openai_compatible":
        return OpenAICompatibleProvider(config.api_key, config.model, config.base_url)
    return None