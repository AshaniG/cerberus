#!/usr/bin/env bash
# Installs ddosctl as a real terminal command.
# Run once: bash cli/install.sh
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$HOME/.local/bin/ddosctl"

chmod +x "$ROOT/cli/ddosctl.py"
mkdir -p "$HOME/.local/bin"
ln -sf "$ROOT/cli/ddosctl.py" "$TARGET"
echo "Linked ddosctl -> $ROOT/cli/ddosctl.py"

if ! grep -q '.local/bin' "$HOME/.zshrc" 2>/dev/null; then
    {
        echo ''
        echo '# Cerberus: run ddosctl as a real command'
        echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "$HOME/.zshrc"
    echo "Added ~/.local/bin to PATH in ~/.zshrc"
else
    echo "~/.local/bin already on PATH in ~/.zshrc"
fi

echo "Done. Open a new terminal (or run: source ~/.zshrc), then try: ddosctl status"
