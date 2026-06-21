#!/usr/bin/env bash
# Install kitty-tab-note: copy the script into kitty's config dir and add a keybinding.
set -e

KITTY_DIR="${KITTY_CONFIG_DIRECTORY:-$HOME/.config/kitty}"
CONF="$KITTY_DIR/kitty.conf"
SRC="$(cd "$(dirname "$0")" && pwd)/tab-note.py"
DEST="$KITTY_DIR/tab-note.py"
KEY="${TABNOTE_KEY:-ctrl+shift+p}"

mkdir -p "$KITTY_DIR"
cp "$SRC" "$DEST"
echo "Installed $DEST"

if [ -f "$CONF" ] && grep -q "tab-note.py" "$CONF"; then
  echo "Keybinding already present in $CONF — leaving it as is."
else
  {
    echo ""
    echo "# kitty-tab-note: leave a big note over a parked tab (press a key to dismiss)"
    echo "map $KEY launch --type=overlay --title \"📌 note\" python3 $DEST"
  } >> "$CONF"
  echo "Added keybinding '$KEY' to $CONF"
fi

# Reload if kitty remote control is reachable.
if command -v kitty >/dev/null 2>&1 && kitty @ load-config >/dev/null 2>&1; then
  echo "Reloaded kitty config."
else
  echo "Reload kitty config manually (ctrl+shift+f5) to activate the keybinding."
fi

echo "Done. Press $KEY in a kitty tab, type a note, and it appears over the tab."
