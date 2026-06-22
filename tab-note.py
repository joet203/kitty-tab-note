#!/usr/bin/env python3
"""
tab-note — leave a big bold note over a "parked" kitty terminal tab.

Press the bound key (see README), type a short note, and a large note appears low on the
screen as an overlay over that tab, so you remember where you left off or why the tab is
open. The tab's existing text stays visible (slightly dimmed) behind the note. Press any
key to dismiss.

The big text is drawn with kitty's native text-sizing protocol (real font, scaled up to 7x)
— no images, no extra fonts, no dependencies. Requires kitty >= 0.40.

Usage:
    tab-note.py                 # prompt for the note (used by the keybinding)
    tab-note.py "waiting on CI" # set the note directly (non-interactive)

Customise with environment variables:
    TABNOTE_COLOR  ANSI SGR for the note   (default "1;94" = bold bright blue)
    TABNOTE_DIM    ANSI SGR for the background (default "0;2" = slight dim; "0" = none)
    TABNOTE_SIZE   text scale, 1-7          (default 4)
    TABNOTE_POS    bottom | middle | top    (default bottom)
"""
import json
import os
import shutil
import subprocess
import sys

NOTE_SGR = os.environ.get("TABNOTE_COLOR", "1;94")          # bold bright blue
BG_SGR = os.environ.get("TABNOTE_DIM", "0;2")               # slight dim
MAX_SCALE = max(1, min(7, int(os.environ.get("TABNOTE_SIZE", "4"))))
POS = os.environ.get("TABNOTE_POS", "bottom")
HINT = "\033[2;37m"
RESET = "\033[0m"


def sized(text, scale):
    """kitty text-sizing protocol: draw `text` at `scale`x the cell size (real font)."""
    return f"\033]66;s={scale};{text}\033\\"


def sibling_screen():
    """Snapshot the window sharing this tab, so we can show its text behind the note."""
    try:
        me = int(os.environ.get("KITTY_WINDOW_ID", "0"))
        tree = json.loads(subprocess.check_output(["kitty", "@", "ls"], timeout=4))
        hint = os.environ.get("TABNOTE_SIBLING_HINT", "")
        target = None
        for ow in tree:
            for tab in ow["tabs"]:
                if me in [w["id"] for w in tab["windows"]]:
                    sibs = [w for w in tab["windows"] if w["id"] != me]
                    if hint:
                        target = next((w for w in sibs if any(
                            hint in " ".join(p.get("cmdline", [])) for p in w.get("foreground_processes", []))),
                            sibs[0] if sibs else None)
                    else:
                        target = sibs[0] if sibs else None
        if not target:
            return []
        txt = subprocess.check_output(
            ["kitty", "@", "get-text", "--match", f"id:{target['id']}", "--extent", "screen"],
            timeout=4).decode(errors="ignore")
        return txt.splitlines()
    except Exception:
        return []


def wrap(note, scale, cols):
    """Greedy word-wrap so each line fits the width once scaled."""
    out, cur = [], ""
    for w in note.split():
        trial = (cur + " " + w).strip()
        if len(trial) * scale > cols - 2 and cur:
            out.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        out.append(cur)
    return out or [note]


def wait_for_key():
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        try:
            input()
        except Exception:
            pass


def main():
    note = " ".join(a for a in sys.argv[1:] if not a.startswith("-")).strip()
    if not note:
        sys.stdout.write("\033[?25h")
        try:
            note = input(f"\033[{NOTE_SGR}m📌 Tag this tab — type a note:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            return
    if not note:
        return
    note = note.upper()

    bg = sibling_screen()
    cols, lines = shutil.get_terminal_size((80, 24))

    # pick the biggest scale where the longest word fits, and it isn't taller than ~half screen
    longest = max((len(w) for w in note.split()), default=len(note))
    scale = MAX_SCALE
    while scale > 1 and (longest * scale > cols - 2 or scale * 2 > lines - 4):
        scale -= 1
    rows = wrap(note, scale, cols)

    line_step = scale + 1                                  # one blank cell-row between lines
    block_h = len(rows) * line_step - 1
    if POS == "top":
        top = 2
    elif POS == "middle":
        top = max(1, (lines - block_h) // 2)
    else:
        top = max(1, lines - block_h - 2)                  # bottom (default)

    out = ["\033[2J\033[H"]
    for r, line in enumerate(bg[:lines]):                  # the tab's text, slightly dimmed, behind
        if line.strip():
            out.append(f"\033[{r + 1};1H\033[{BG_SGR}m{line[:cols]}{RESET}")
    row = top
    for ln in rows:                                        # the note, in the real font, scaled up
        pad = max(0, (cols - len(ln) * scale) // 2) + 1
        out.append(f"\033[{row};{pad}H\033[{NOTE_SGR}m{sized(ln, scale)}{RESET}")
        row += line_step
    out.append(f"\033[{lines};1H{HINT}  press any key to dismiss{RESET}")
    out.append("\033[?25l")
    sys.stdout.write("".join(out))
    sys.stdout.flush()

    wait_for_key()
    sys.stdout.write("\033[?25h\033[0m")


if __name__ == "__main__":
    main()
