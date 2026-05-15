"""
Bottom controls bar: track info, progress, volume, playback state.
"""

import curses
from auditerm.player import Player, _fmt_time
from auditerm.ui.colors import cp, PAIR_ACCENT, PAIR_MUTED, PAIR_PLAYING, PAIR_DEFAULT, PAIR_STATUS, PAIR_BAR_FILLED, PAIR_BAR_EMPTY
from auditerm.config import Config

ICONS_UNICODE = {"play": "▶", "pause": "⏸", "stop": "■", "prev": "◀◀", "next": "▶▶", "vol": "♪"}
ICONS_ASCII   = {"play": ">", "pause": "||", "stop": "[]", "prev": "<<", "next": ">>", "vol": "V"}


class ControlsBar:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg = cfg
        self.icons = ICONS_UNICODE if cfg.getbool("ui", "unicode_icons", True) else ICONS_ASCII

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        p = self.player

        # ── top divider ──────────────────────────────────────────
        try:
            win.attron(cp(PAIR_ACCENT))
            win.hline(0, 0, "─", w)
            win.attroff(cp(PAIR_ACCENT))
        except curses.error:
            pass

        if h < 2:
            return

        # ── row 1: track info ────────────────────────────────────
        track = p.current_track
        if track:
            name = track.display_name()
            dur  = track.duration_str()
            ela  = p.elapsed_str()
            time_str = f" {ela} / {dur} "
            max_name = w - len(time_str) - 4
            if len(name) > max_name:
                name = name[:max_name - 1] + "…"
            try:
                win.addstr(1, 2, name, cp(PAIR_PLAYING) | curses.A_BOLD)
                win.addstr(1, w - len(time_str) - 1, time_str, cp(PAIR_MUTED))
            except curses.error:
                pass
        else:
            try:
                win.addstr(1, 2, "No track loaded", cp(PAIR_MUTED))
            except curses.error:
                pass

        if h < 3:
            return

        # ── row 2: progress bar ──────────────────────────────────
        prog = p.progress
        bar_w = w - 4
        filled = int(prog * bar_w)
        style = self.cfg.get("ui", "progress_style", "bar")
        try:
            if style == "bar":
                bar = "█" * filled + "░" * (bar_w - filled)
                win.addstr(2, 2, bar[:bar_w], cp(PAIR_BAR_FILLED))
            elif style == "dots":
                bar = "●" * filled + "·" * (bar_w - filled)
                win.addstr(2, 2, bar[:bar_w], cp(PAIR_ACCENT))
            else:
                bar = "=" * filled + "-" * (bar_w - filled)
                win.addstr(2, 2, bar[:bar_w], cp(PAIR_MUTED))
        except curses.error:
            pass

        if h < 4:
            return

        # ── row 3: state + volume ────────────────────────────────
        if p.is_playing:
            state = f" {self.icons['pause']} PLAYING "
            attr = cp(PAIR_PLAYING) | curses.A_BOLD
        elif p.is_paused:
            state = f" {self.icons['play']} PAUSED  "
            attr = cp(PAIR_ACCENT) | curses.A_BOLD
        else:
            state = f" {self.icons['stop']} STOPPED "
            attr = cp(PAIR_MUTED)

        vol_pct = int(p.volume * 100)
        vol_bar_w = 10
        vol_filled = int(p.volume * vol_bar_w)
        vol_bar = "█" * vol_filled + "░" * (vol_bar_w - vol_filled)
        vol_str = f" {self.icons['vol']} {vol_pct:3d}%  {vol_bar} "

        help_str = " [SPC]pause [>/<]next/prev [+/-]vol [b]browse [l]lib [q]quit "
        show_help = self.cfg.getbool("ui", "show_help_bar", True)

        try:
            win.addstr(3, 2, state, attr)
            win.addstr(3, 12, vol_str, cp(PAIR_ACCENT2))
            if show_help and len(help_str) + 24 < w:
                win.addstr(3, w - len(help_str) - 1, help_str, cp(PAIR_MUTED))
        except curses.error:
            pass
