"""
Color pair registry for curses.
Call init_colors(config) once after curses.start_color().
Then use PAIRS["accent"] etc.
"""

import curses
from auditerm.config import Config, _name_to_curses

# Pair IDs — reserve 0 for curses default
PAIR_DEFAULT    = 1
PAIR_ACCENT     = 2
PAIR_ACCENT2    = 3
PAIR_SELECTED   = 4
PAIR_PLAYING    = 5
PAIR_MUTED      = 6
PAIR_ERROR      = 7
PAIR_TITLE      = 8
PAIR_STATUS     = 9
PAIR_BORDER     = 10
PAIR_BAR_FILLED = 11
PAIR_BAR_EMPTY  = 12
PAIR_HEADER     = 13


def init_colors(cfg: Config):
    curses.start_color()
    curses.use_default_colors()

    bg  = cfg.color("bg")
    fg  = cfg.color("fg")
    acc = cfg.color("accent")
    ac2 = cfg.color("accent2")
    sel_bg = cfg.color("selected_bg")
    sel_fg = cfg.color("selected_fg")
    play   = cfg.color("playing_fg")
    muted  = cfg.color("muted")
    err    = cfg.color("error")
    title  = cfg.color("title_fg")
    stat   = cfg.color("status_fg")
    bord   = cfg.color("border")
    barf   = cfg.color("bar_filled")
    bare   = cfg.color("bar_empty")

    curses.init_pair(PAIR_DEFAULT,    fg,     bg)
    curses.init_pair(PAIR_ACCENT,     acc,    bg)
    curses.init_pair(PAIR_ACCENT2,    ac2,    bg)
    curses.init_pair(PAIR_SELECTED,   sel_fg, sel_bg)
    curses.init_pair(PAIR_PLAYING,    play,   bg)
    curses.init_pair(PAIR_MUTED,      muted,  bg)
    curses.init_pair(PAIR_ERROR,      err,    bg)
    curses.init_pair(PAIR_TITLE,      title,  bg)
    curses.init_pair(PAIR_STATUS,     stat,   bg)
    curses.init_pair(PAIR_BORDER,     bord,   bg)
    curses.init_pair(PAIR_BAR_FILLED, barf,   bg)
    curses.init_pair(PAIR_BAR_EMPTY,  bare,   bg)
    curses.init_pair(PAIR_HEADER,     bg,     acc)


def cp(pair_id: int) -> int:
    return curses.color_pair(pair_id)
