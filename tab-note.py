#!/usr/bin/env python3
"""
tab-note — leave a big bold note over a "parked" kitty terminal tab.

Press the bound key (see README), type a short note, and a large coloured label appears
low on the screen as an overlay over that tab, so you remember where you left off or why
the tab is open. The tab's existing content stays visible (slightly dimmed) behind the
note. Press any key to dismiss.

Pure Python standard library — no dependencies. Renders text with a tiny built-in 3x5
block font, upscaled and drawn with █ blocks, over a snapshot of the tab's window.

Usage:
    tab-note.py                 # prompt for the note (used by the keybinding)
    tab-note.py "waiting on CI" # set the note directly (non-interactive)

Customise with environment variables:
    TABNOTE_COLOR  ANSI SGR for the note text   (default "1;94" = bold bright blue)
    TABNOTE_DIM    ANSI SGR for the background   (default "0;2" = slight dim; "0" = none)
    TABNOTE_SIZE   block scale, 1-4              (default 2)
    TABNOTE_POS    bottom | middle | top         (default bottom)
"""
import json
import os
import shutil
import subprocess
import sys

# 3-wide x 5-tall bitmap font ('#' = on pixel). Notes are upper-cased before rendering.
F = {
    'A': [" # ", "# #", "###", "# #", "# #"], 'B': ["## ", "# #", "## ", "# #", "## "],
    'C': [" ##", "#  ", "#  ", "#  ", " ##"], 'D': ["## ", "# #", "# #", "# #", "## "],
    'E': ["###", "#  ", "## ", "#  ", "###"], 'F': ["###", "#  ", "## ", "#  ", "#  "],
    'G': [" ##", "#  ", "# #", "# #", " ##"], 'H': ["# #", "# #", "###", "# #", "# #"],
    'I': ["###", " # ", " # ", " # ", "###"], 'J': ["  #", "  #", "  #", "# #", " # "],
    'K': ["# #", "# #", "## ", "# #", "# #"], 'L': ["#  ", "#  ", "#  ", "#  ", "###"],
    'M': ["# #", "###", "###", "# #", "# #"], 'N': ["# #", "## ", "###", " ##", "# #"],
    'O': [" # ", "# #", "# #", "# #", " # "], 'P': ["## ", "# #", "## ", "#  ", "#  "],
    'Q': [" # ", "# #", "# #", " # ", "  #"], 'R': ["## ", "# #", "## ", "# #", "# #"],
    'S': [" ##", "#  ", " # ", "  #", "## "], 'T': ["###", " # ", " # ", " # ", " # "],
    'U': ["# #", "# #", "# #", "# #", "###"], 'V': ["# #", "# #", "# #", "# #", " # "],
    'W': ["# #", "# #", "###", "###", "# #"], 'X': ["# #", "# #", " # ", "# #", "# #"],
    'Y': ["# #", "# #", " # ", " # ", " # "], 'Z': ["###", "  #", " # ", "#  ", "###"],
    '0': ["###", "# #", "# #", "# #", "###"], '1': [" # ", "## ", " # ", " # ", "###"],
    '2': ["## ", "  #", " # ", "#  ", "###"], '3': ["###", "  #", " ##", "  #", "###"],
    '4': ["# #", "# #", "###", "  #", "  #"], '5': ["###", "#  ", "## ", "  #", "## "],
    '6': [" ##", "#  ", "## ", "# #", " # "], '7': ["###", "  #", " # ", " # ", " # "],
    '8': [" # ", "# #", " # ", "# #", " # "], '9': [" # ", "# #", " ##", "  #", "## "],
    ' ': ["   ", "   ", "   ", "   ", "   "], '.': ["   ", "   ", "   ", "   ", " # "],
    ',': ["   ", "   ", "   ", " # ", " # "], '!': [" # ", " # ", " # ", "   ", " # "],
    '?': ["## ", "  #", " # ", "   ", " # "], ':': ["   ", " # ", "   ", " # ", "   "],
    '-': ["   ", "   ", "###", "   ", "   "], "'": [" # ", " # ", "   ", "   ", "   "],
    '/': ["  #", "  #", " # ", "#  ", "#  "], '(': [" ##", "#  ", "#  ", "#  ", " ##"],
    ')': ["## ", "  #", "  #", "  #", "## "], '#': ["# #", "###", "# #", "###", "# #"],
}

NOTE_SGR = os.environ.get("TABNOTE_COLOR", "1;94")          # bold bright blue
BG_SGR = os.environ.get("TABNOTE_DIM", "0;2")               # slight dim
SIZE = max(1, min(4, int(os.environ.get("TABNOTE_SIZE", "2"))))
POS = os.environ.get("TABNOTE_POS", "bottom")
NOTE = f"\033[{NOTE_SGR}m"
HINT = "\033[2;37m"
RESET = "\033[0m"
BLOCK = "█"


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


def render_word(word, scale):
    """Render one word into a list of text rows at the given block scale."""
    rows = [""] * (5 * scale)
    for ch in word:
        g = F.get(ch.upper(), F[' '])
        for r in range(5):
            line = "".join((BLOCK if px == "#" else " ") * scale for px in g[r])
            for s in range(scale):
                rows[r * scale + s] += line + " " * scale   # gap between letters
    return rows


def wrap_lines(text, scale, max_cols):
    """Greedy word-wrap so each rendered line fits the terminal width."""
    out, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if len(render_word(trial, scale)[0]) > max_cols and cur:
            out.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        out.append(cur)
    return out or [""]


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
            note = input(f"{NOTE}📌 Tag this tab — type a note:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            return
    if not note:
        return

    bg = sibling_screen()
    cols, lines = shutil.get_terminal_size((80, 24))

    scale = SIZE
    first = note.split()[0] if note.split() else note
    while scale > 1 and (len(render_word(first, scale)[0]) > cols or 5 * scale > lines // 2):
        scale -= 1

    rendered = []
    blocks = wrap_lines(note, scale, cols - 2)
    for i, ln in enumerate(blocks):
        rendered.extend(render_word(ln, scale))
        if i < len(blocks) - 1:
            rendered.append("")                              # blank row between wrapped lines

    height = len(rendered)
    if POS == "top":
        top = max(1, 2)
    elif POS == "middle":
        top = max(1, (lines - height) // 2)
    else:
        top = max(1, lines - height - 2)                     # bottom (default)

    out = ["\033[2J\033[H"]
    for r, line in enumerate(bg[:lines]):                    # the tab's text, behind the note
        if line.strip():
            out.append(f"\033[{r + 1};1H\033[{BG_SGR}m{line[:cols]}{RESET}")
    for i, row in enumerate(rendered):                       # the note, on top
        col = max(0, (cols - len(row)) // 2) + 1
        for ch in row:
            if ch == BLOCK:                                  # paint only blocks; gaps show the bg
                out.append(f"\033[{top + i};{col}H{NOTE}{BLOCK}{RESET}")
            col += 1
    out.append(f"\033[{lines};1H{HINT}  press any key to dismiss{RESET}")
    out.append("\033[?25l")
    sys.stdout.write("".join(out))
    sys.stdout.flush()

    wait_for_key()
    sys.stdout.write("\033[?25h\033[0m")


if __name__ == "__main__":
    main()
