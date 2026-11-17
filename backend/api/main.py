"""Start with:  python -m uvicorn api.main:app --port 8000"""
from ai_engine.config import ConfigError, create_provider, load_ai_config, load_env_file
from api.app import create_app
from api.settings import SettingsError, load_settings

load_env_file()  # reads .env from the folder you start the server in

try:
    app = create_app(load_settings(), create_provider(load_ai_config()))
except (ConfigError, SettingsError) as error:
    raise SystemExit(f"VEDIX API settings problem: {error}")