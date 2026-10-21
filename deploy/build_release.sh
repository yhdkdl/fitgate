#!/usr/bin/env bash
# Build script for FitGate production staging release package (Bash / Linux / WSL)
# Usage:
#   bash deploy/build_release.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
DEPLOY_DIR="$ROOT_DIR/deploy"
OUTPUT_DIR="$ROOT_DIR/dist"

mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
ZIP_NAME="fitgate_release_${TIMESTAMP}.zip"
ZIP_PATH="$OUTPUT_DIR/$ZIP_NAME"
TEMP_DIR="$OUTPUT_DIR/temp_${TIMESTAMP}"

echo "============================================================"
echo "  FitGate Production Release Package Builder"
echo "============================================================"

echo ""
echo "[1/4] Building React frontend (npm run build)..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm ci
fi
npm run build
cd "$ROOT_DIR"

echo ""
echo "[2/4] Assembling release directory tree..."
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR/backend"
mkdir -p "$TEMP_DIR/frontend/dist"
mkdir -p "$TEMP_DIR/deploy"
mkdir -p "$TEMP_DIR/requirements"

# Copy backend excluding tests, cache, static, media, spike
rsync -av \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'tests/' \
    --exclude 'conftest.py' \
    --exclude 'pytest.ini' \
    --exclude 'deploy/' \
    --exclude 'spike/' \
    --exclude 'staticfiles/' \
    --exclude 'media/' \
    --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' \
    --exclude '.env' \
    --exclude 'htmlcov/' \
    --exclude '.coverage' \
    "$BACKEND_DIR/" "$TEMP_DIR/backend/"

# Copy frontend dist
cp -r "$FRONTEND_DIR/dist/"* "$TEMP_DIR/frontend/dist/"

# Copy passenger_wsgi.py to deploy/ and root
cp "$DEPLOY_DIR/passenger_wsgi.py" "$TEMP_DIR/deploy/passenger_wsgi.py"
cp "$DEPLOY_DIR/passenger_wsgi.py" "$TEMP_DIR/passenger_wsgi.py"

# Copy requirements
cp "$BACKEND_DIR/requirements/base.txt" "$TEMP_DIR/requirements/base.txt"
cp "$BACKEND_DIR/requirements/prod.txt" "$TEMP_DIR/requirements/prod.txt"

# Copy .env.production.example
cp "$ROOT_DIR/.env.production.example" "$TEMP_DIR/.env.production.example"

echo ""
echo "[3/4] Creating zip archive: $ZIP_NAME..."
cd "$TEMP_DIR"
zip -r -q "$ZIP_PATH" .
cd "$ROOT_DIR"

echo ""
echo "[4/4] Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo "============================================================"
echo "  SUCCESS: Release Package Created!"
echo "  Path: $ZIP_PATH"
echo "============================================================"
