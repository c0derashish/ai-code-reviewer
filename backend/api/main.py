"""Start with:  python -m uvicorn api.main:app --port 8000"""
from pymongo.errors import PyMongoError

from ai_engine.config import ConfigError, create_provider, load_ai_config, load_env_file
from api.app import create_app
from api.settings import SettingsError, load_settings
from app_db.connection import connect

load_env_file()  # reads .env from the folder you start the server in

try:
    settings = load_settings()
    provider = create_provider(load_ai_config())

    database = None
    if settings.mongo_uri:
        try:
            database = connect(settings.mongo_uri, settings.mongo_db)
        except PyMongoError:
            # the error text is not shown: it can contain the address and the user name
            raise SystemExit(
                "VEDIX API: cannot reach MongoDB. Check MONGODB_URI, that the server is "
                "running, and your network."
            )
        print(f"VEDIX API: accounts are ON (database '{settings.mongo_db}').")
    else:
        print("VEDIX API: accounts are OFF (MONGODB_URI is not set).")

    app = create_app(settings, provider, database=database)
except (ConfigError, SettingsError) as error:
    raise SystemExit(f"VEDIX API settings problem: {error}")