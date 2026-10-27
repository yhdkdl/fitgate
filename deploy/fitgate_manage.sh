#!/usr/bin/env bash
# FitGate Production Management Command Wrapper
# Activates the cPanel Python 3.11 virtualenv, sets DJANGO_SETTINGS_MODULE to production,
# changes to backend directory, and runs manage.py with all passed arguments.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"
BACKEND_DIR="$APP_DIR/backend"

if [ ! -d "$BACKEND_DIR" ] && [ -f "$APP_DIR/manage.py" ]; then
    BACKEND_DIR="$APP_DIR"
fi

# Locate external .env file if not already set
if [ -z "$FITGATE_ENV_FILE" ]; then
    if [ -f "$HOME/fitgate_env/.env" ]; then
        export FITGATE_ENV_FILE="$HOME/fitgate_env/.env"
    elif [ -f "$APP_DIR/../fitgate_env/.env" ]; then
        export FITGATE_ENV_FILE="$APP_DIR/../fitgate_env/.env"
    fi
fi

# Activate cPanel virtual environment if available
if [ -f "$HOME/virtualenv/fitgate/3.11/bin/activate" ]; then
    source "$HOME/virtualenv/fitgate/3.11/bin/activate"
fi

export DJANGO_SETTINGS_MODULE="fitgate.settings.prod"
cd "$BACKEND_DIR"
exec python manage.py "$@"
