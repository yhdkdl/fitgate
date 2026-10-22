# Build script for FitGate production staging release package (Windows PowerShell)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\deploy\build_release.ps1

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  FitGate Production Release Package Builder" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$RootDir = (Get-Item $PSScriptRoot).Parent.FullName
$FrontendDir = Join-Path $RootDir "frontend"
$BackendDir = Join-Path $RootDir "backend"
$DeployDir = Join-Path $RootDir "deploy"
$ReleaseOutputDir = Join-Path $RootDir "dist"

if (-not (Test-Path $ReleaseOutputDir)) {
    New-Item -ItemType Directory -Path $ReleaseOutputDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ReleaseZipName = "fitgate_release_$Timestamp.zip"
$ReleaseZipPath = Join-Path $ReleaseOutputDir $ReleaseZipName
$StagingTempDir = Join-Path $ReleaseOutputDir "temp_$Timestamp"

Write-Host "`n[1/4] Building React frontend (npm run build)..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing frontend dependencies with npm ci..."
        npm ci
    }
    npm run build
} finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $FrontendDir "dist/index.html"))) {
    Write-Error "Frontend build failed: dist/index.html not found."
}
Write-Host "Frontend build completed successfully." -ForegroundColor Green

Write-Host "`n[2/4] Assembling release contents into temporary staging tree..." -ForegroundColor Yellow
if (Test-Path $StagingTempDir) {
    Remove-Item -Recurse -Force $StagingTempDir
}
New-Item -ItemType Directory -Path $StagingTempDir | Out-Null

$BackendDest = Join-Path $StagingTempDir "backend"
New-Item -ItemType Directory -Path $BackendDest | Out-Null

$BackendExclude = @(
    "__pycache__",
    "*.pyc",
    "tests",
    "conftest.py",
    "pytest.ini",
    "deploy",
    "spike",
    "staticfiles",
    "media",
    ".pytest_cache",
    ".ruff_cache",
    ".env",
    "htmlcov",
    ".coverage"
)

Get-ChildItem -Path $BackendDir -Recurse | Where-Object {
    $item = $_
    $rel = $item.FullName.Substring($BackendDir.Length).TrimStart("\", "/")
    $skip = $false
    foreach ($pat in $BackendExclude) {
        if ($rel -like "*\$pat" -or $rel -like "*\$pat\*" -or $rel -like "$pat\*" -or $rel -like "$pat" -or $item.Name -like $pat) {
            $skip = $true
            break
        }
    }
    -not $skip
} | ForEach-Object {
    $src = $_.FullName
    $dest = Join-Path $BackendDest ($src.Substring($BackendDir.Length).TrimStart("\", "/"))
    if ($_.PSIsContainer) {
        if (-not (Test-Path $dest)) {
            New-Item -ItemType Directory -Path $dest | Out-Null
        }
    } else {
        $parent = Split-Path -Parent $dest
        if (-not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent | Out-Null
        }
        Copy-Item -Path $src -Destination $dest -Force
    }
}

# Copy compiled frontend dist
$FrontendDest = Join-Path $StagingTempDir "frontend\dist"
New-Item -ItemType Directory -Path (Split-Path -Parent $FrontendDest) | Out-Null
Copy-Item -Path (Join-Path $FrontendDir "dist") -Destination $FrontendDest -Recurse -Force

# Copy single passenger_wsgi.py to release root (only one startup file)
Copy-Item -Path (Join-Path $DeployDir "passenger_wsgi.py") -Destination (Join-Path $StagingTempDir "passenger_wsgi.py") -Force

# Copy production requirements
$ReqsDest = Join-Path $StagingTempDir "requirements"
New-Item -ItemType Directory -Path $ReqsDest | Out-Null
Copy-Item -Path (Join-Path $BackendDir "requirements\base.txt") -Destination (Join-Path $ReqsDest "base.txt") -Force
Copy-Item -Path (Join-Path $BackendDir "requirements\prod.txt") -Destination (Join-Path $ReqsDest "prod.txt") -Force

# Copy .env.production.example for reference
Copy-Item -Path (Join-Path $RootDir ".env.production.example") -Destination (Join-Path $StagingTempDir ".env.production.example") -Force

Write-Host "`n[3/4] Creating zip archive: $ReleaseZipName..." -ForegroundColor Yellow
if (Test-Path $ReleaseZipPath) {
    Remove-Item -Force $ReleaseZipPath
}
Compress-Archive -Path "$StagingTempDir\*" -DestinationPath $ReleaseZipPath -Force

Write-Host "`n[4/4] Cleaning up temporary files..." -ForegroundColor Yellow
Remove-Item -Recurse -Force $StagingTempDir

$ZipSizeMB = [math]::Round(((Get-Item $ReleaseZipPath).Length / 1MB), 2)

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  SUCCESS: Release Package Created!" -ForegroundColor Green
Write-Host "  Path: $ReleaseZipPath" -ForegroundColor Green
Write-Host "  Size: $ZipSizeMB MB" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
