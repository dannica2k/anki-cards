# Windows 11 PowerShell Setup Script for Multi-Course Anki Flashcard Generator
$ErrorActionPreference = "Stop"

Write-Host "=== Setting up Multi-Course Anki Flashcard Environment (Windows 11) ===" -ForegroundColor Cyan

# 1. Install uv if not already installed
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv Python package manager..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$HOME\.local\bin;$HOME\.cargo\bin;$env:Path"
}

$uvCmd = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uvCmd) {
    $uvCmd = "$HOME\.local\bin\uv.exe"
}

# 2. Create virtual environment (auto-downloads Python 3.12 if Python isn't installed!)
Write-Host "Creating Python virtual environment (.venv) and installing dependencies..." -ForegroundColor Yellow
& $uvCmd venv --python 3.12 --clear
& $uvCmd pip install `
    google-api-python-client `
    google-auth-httplib2 `
    google-auth-oauthlib `
    pymupdf `
    genanki `
    zstandard `
    pypdf

# 3. Copy skill to global ~/.gemini/config/skills so Antigravity discovers it from any directory
$globalSkillsDir = Join-Path $HOME ".gemini\config\skills"
New-Item -ItemType Directory -Force -Path $globalSkillsDir | Out-Null
$targetSkillDir = Join-Path $globalSkillsDir "anki-card-generator"
if (Test-Path $targetSkillDir) {
    Remove-Item -Recurse -Force $targetSkillDir
}
Copy-Item -Recurse -Force ".agents\skills\anki-card-generator" $targetSkillDir

# 4. Configure Google Drive credentials
$gdriveDir = Join-Path $HOME ".config\gdrive"
New-Item -ItemType Directory -Force -Path $gdriveDir | Out-Null
$credDest = Join-Path $gdriveDir "credentials.json"
$tokenDest = Join-Path $gdriveDir "token.json"

if ((Test-Path "credentials.json") -and (-not (Test-Path $credDest))) {
    Copy-Item "credentials.json" $credDest -Force
}

if (-not (Test-Path $credDest)) {
    Write-Host "`nIMPORTANT: Please place 'credentials.json' into $credDest" -ForegroundColor Red
} else {
    if (-not (Test-Path $tokenDest)) {
        Write-Host "`nLaunching Google Drive browser authentication..." -ForegroundColor Green
        & ".\.venv\Scripts\python.exe" auth_gdrive.py
    } else {
        Write-Host "`nGoogle Drive token already configured at $tokenDest!" -ForegroundColor Green
    }
}

Write-Host "`n=== Setup Complete! ===" -ForegroundColor Cyan
Write-Host "You can now launch 'agy' inside this folder ($PWD) to generate Anki flashcards." -ForegroundColor Green
