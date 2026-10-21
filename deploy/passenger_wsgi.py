"""
FitGate Production Passenger WSGI Entrypoint.

Configures production settings (fitgate.settings.prod), locates and loads the
external environment file outside public_html and outside the release directory
(e.g., /home/<user>/fitgate_env/.env), and exposes the WSGI `application`.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
# Release layout: if deploy/passenger_wsgi.py is run from deploy/, APP_DIR is parent
APP_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "deploy" else SCRIPT_DIR
BACKEND_DIR = APP_DIR / "backend" if (APP_DIR / "backend").exists() else APP_DIR

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Pinned to production settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fitgate.settings.prod")

# Locate external .env file outside public_html and release folder
# Priority order:
# 1. FITGATE_ENV_FILE environment variable (if explicitly set)
# 2. Standard user home directory: /home/<user>/fitgate_env/.env
# 3. Sibling folder outside release: <app_root>/../fitgate_env/.env
env_file = os.environ.get("FITGATE_ENV_FILE")
if not env_file or not Path(env_file).exists():
    candidates = [
        Path.home() / "fitgate_env" / ".env",
        APP_DIR.parent / "fitgate_env" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            env_file = str(candidate)
            break

if env_file and Path(env_file).exists():
    import environ

    environ.Env.read_env(env_file)
    os.environ["FITGATE_ENV_FILE"] = env_file

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
