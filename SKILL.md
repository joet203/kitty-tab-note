---
name: kitty-tab-note
description: Leave a big bold note overlaid on a kitty terminal tab so you remember where you left off or why it's parked. Use when the user wants to tag/park/annotate/flag a kitty tab with a visual reminder, asks to "leave a note on this tab", "remind me where I left off", wants to install this tab-note tool, or asks what the tab-note keybinding is. Requires kitty with remote control enabled.
---

# kitty-tab-note

A tiny pure-stdlib tool that draws a large coloured note over a "parked" kitty tab (the tab's
text stays visible, slightly dimmed, behind it). `tab-note.py` lives next to this file.

## Default keybinding

**`ctrl+shift+p`** (mnemonic: "**p**ark this tab") → type a note → it appears over the tab.
Press any key to dismiss. If the user forgets the key, the answer is `ctrl+shift+p` (unless they
rebound it — check `grep tab-note ~/.config/kitty/kitty.conf`).

## Tag the current tab on request

If the user (working inside a kitty tab) asks you to tag/park THIS tab with a note, run the
script as an overlay in their tab — it covers the tab with the note:

```sh
kitty @ launch --type=overlay python3 <path>/tab-note.py "their note text"
```

`<path>` is wherever `tab-note.py` is installed (usually `~/.config/kitty/tab-note.py`). The
overlay closes when they press a key.

## Install it for a new user

1. Confirm kitty has remote control on (`grep allow_remote_control ~/.config/kitty/kitty.conf`;
   if missing, add `allow_remote_control yes` and `listen_on unix:/tmp/kitty-{kitty_pid}`).
2. Copy `tab-note.py` to `~/.config/kitty/tab-note.py`.
3. Add a keybinding to `~/.config/kitty/kitty.conf`:
   ```
   map ctrl+shift+p launch --type=overlay --title "📌 note" python3 ~/.config/kitty/tab-note.py
   ```
4. Reload: `kitty @ load-config`.

`./install.sh` in this repo does steps 2–4.

## Customise

Environment variables (set on the `launch` line with `--env NAME=VALUE`): `TABNOTE_COLOR`
(ANSI SGR, default `1;94` bold blue), `TABNOTE_DIM` (default `0;2`; `0`=none), `TABNOTE_SIZE`
(1–4, default 2), `TABNOTE_POS` (`bottom`/`middle`/`top`). See README.md for details.

## Troubleshooting

- Nothing happens on the key → kitty config not reloaded, or `allow_remote_control` is off.
- Note shows but no background text → the tab has only one window, or `kitty @ get-text` failed.
