#!/usr/bin/env bash
# Creates a desktop shortcut (Linux) for the ESP-Claw Serial Control GUI.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3)"
APP_NAME="ESP-Claw Serial Control"
DESKTOP_FILE_NAME="espclaw-serial-ctl.desktop"

DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"

cat > "$APPS_DIR/$DESKTOP_FILE_NAME" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Control ESP-Claw (ESP32-S3) over USB serial
Exec=$PYTHON_BIN -m espclaw_ctl.gui
Path=$REPO_DIR
Terminal=false
Categories=Utility;Development;
EOF
chmod +x "$APPS_DIR/$DESKTOP_FILE_NAME"

if [ -d "$DESKTOP_DIR" ]; then
    cp "$APPS_DIR/$DESKTOP_FILE_NAME" "$DESKTOP_DIR/$DESKTOP_FILE_NAME"
    chmod +x "$DESKTOP_DIR/$DESKTOP_FILE_NAME"
    if command -v gio >/dev/null 2>&1; then
        gio set "$DESKTOP_DIR/$DESKTOP_FILE_NAME" metadata::trusted true 2>/dev/null || true
    fi
    echo "Shortcut created at: $DESKTOP_DIR/$DESKTOP_FILE_NAME"
fi

echo "Shortcut also registered in the app launcher: $APPS_DIR/$DESKTOP_FILE_NAME"
echo "Make sure dependencies are installed: pip install -r requirements.txt (or pip install -e .)"
