#!/usr/bin/env bash
set -e

echo "=== Setting up Multi-Course Anki Flashcard Environment ==="

# 1. Install uv if not already installed
if ! command -v uv &> /dev/null && [ ! -f "$HOME/.local/bin/uv" ]; then
    echo "Installing uv Python package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

UV_BIN=$(command -v uv || echo "$HOME/.local/bin/uv")

# 2. Create virtual environment and install dependencies
echo "Creating virtual environment (.venv) and installing Python dependencies..."
"$UV_BIN" venv --clear
"$UV_BIN" pip install \
    google-api-python-client \
    google-auth-httplib2 \
    google-auth-oauthlib \
    pymupdf \
    genanki \
    zstandard \
    pypdf

# 3. Symlink the skill globally so Antigravity discovers it from any directory
mkdir -p "$HOME/.gemini/config/skills"
ln -sfn "$(pwd)/.agents/skills/anki-card-generator" "$HOME/.gemini/config/skills/anki-card-generator"

# 4. Check Google Drive credentials
mkdir -p "$HOME/.config/gdrive"
if [ -f "credentials.json" ] && [ ! -f "$HOME/.config/gdrive/credentials.json" ]; then
    cp credentials.json "$HOME/.config/gdrive/credentials.json"
fi

if [ ! -f "$HOME/.config/gdrive/credentials.json" ]; then
    echo ""
    echo "IMPORTANT: Please place 'credentials.json' into ~/.config/gdrive/credentials.json"
    echo "Then run: .venv/bin/python auth_gdrive.py"
else
    if [ ! -f "$HOME/.config/gdrive/token.json" ]; then
        echo "Launching Google Drive browser authentication..."
        .venv/bin/python auth_gdrive.py
    else
        echo "Google Drive token already configured!"
    fi
fi

echo ""
echo "=== Setup Complete! ==="
echo "You can now launch 'agy' inside this folder ($(pwd)) to generate Anki flashcards."
