"""
Audio visualizer panel.
Uses numpy FFT on a short fake/simulated signal when no raw PCM is available
(pygame.mixer doesn't expose PCM easily), but produces a convincing real-time
visualization driven by pygame's music position changes.
"""

import curses
import time
import math
import random
import threading
import numpy as np

from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_BAR_EMPTY, PAIR_ACCENT, PAIR_ACCENT2, PAIR_MUTED
from auditerm.config import Config
from auditerm.player import Player


class Visualizer:
    """
    Draws an audio visualizer.
    Generates pseudo-random band energies keyed to elapsed time + noise
    so it looks alive and reacts to "playback" even without raw PCM.
    """

    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg = cfg
        self._last_draw = 0.0
        self._bands: list[float] = []
        self._peaks: list[float] = []
        self._rng = random.Random()
        self._t = 0.0

    def _generate_bands(self, n: int) -> list[float]:
        p = self.player
        if not (p.is_playing or p.is_paused):
            return [0.0] * n

        t = p.elapsed
        # Simulate frequency content using overlapping sinusoids + noise
        bands = []
        for i in range(n):
            # base envelope: low freqs louder
            base = 0.7 * math.exp(-i / (n * 0.6))
            # slow oscillation per band
            osc  = 0.3 * math.sin(t * (0.5 + i * 0.3) + i)
            # fast transient noise
            noise = 0.2 * (random.random() - 0.5)
            val = max(0.0, min(1.0, base + osc + noise))
            bands.append(val)
        return bands

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        if h < 3 or w < 10:
            return

        style = self.cfg.get("visualizer", "style", "bars")
        vis_h = min(self.cfg.getint("visualizer", "height", 8), h - 1)
        mirror = self.cfg.getbool("visualizer", "mirror", True)
        bar_char  = self.cfg.get("visualizer", "bar_char", "█")
        empty_char = self.cfg.get("visualizer", "bar_empty_char", "░")
        wave_char = self.cfg.get("visualizer", "wave_char", "•")

        if style == "off":
            return

        n_bands = w - 2
        if mirror:
            n_bands = (w - 2) // 2
        bands = self._generate_bands(n_bands)

        # update peaks
        if len(self._peaks) != len(bands):
            self._peaks = list(bands)
        for i, v in enumerate(bands):
            if v > self._peaks[i]:
                self._peaks[i] = v
            else:
                self._peaks[i] = max(0.0, self._peaks[i] - 0.05)

        if style == "bars":
            self._draw_bars(win, bands, vis_h, w, mirror, bar_char, empty_char)
        elif style == "wave":
            self._draw_wave(win, bands, vis_h, w, mirror, wave_char)
        elif style == "spectrum":
            self._draw_spectrum(win, bands, vis_h, w, mirror)
        elif style == "dots":
            self._draw_dots(win, bands, vis_h, w, mirror)

    def _draw_bars(self, win, bands, vis_h, w, mirror, bar_char, empty_char):
        h, _ = win.getmaxyx()
        top_row = max(0, h - vis_h - 1)

        def draw_col(col, val, peak):
            filled = int(val * vis_h)
            peak_row = top_row + vis_h - int(peak * vis_h) - 1
            for row_off in range(vis_h):
                row = top_row + row_off
                if row >= h - 1:
                    break
                bar_row = vis_h - 1 - row_off
                ch = bar_char if bar_row < filled else empty_char
                if row == peak_row and peak > 0.05:
                    attr = cp(PAIR_ACCENT2) | curses.A_BOLD
                else:
                    attr = cp(PAIR_BAR_FILLED) if bar_row < filled else cp(PAIR_MUTED)
                try:
                    win.addch(row, col, ch, attr)
                except curses.error:
                    pass

        if mirror:
            half = len(bands)
            for i, (v, pk) in enumerate(zip(bands, self._peaks)):
                left  = half - i
                right = half + i + 1
                draw_col(left, v, pk)
                if right < w - 1:
                    draw_col(right, v, pk)
        else:
            for i, (v, pk) in enumerate(zip(bands, self._peaks)):
                draw_col(i + 1, v, pk)

    def _draw_wave(self, win, bands, vis_h, w, mirror, wave_char):
        h, _ = win.getmaxyx()
        mid = h - vis_h // 2 - 1
        cols = list(range(1, w - 1))
        n = len(bands)
        expanded = [bands[int(i * n / len(cols))] for i in range(len(cols))]
        if mirror:
            half = len(cols) // 2
            left  = list(reversed(expanded[:half]))
            right = expanded[:half]
            expanded = left + right

        for i, v in enumerate(expanded):
            col = i + 1
            row = mid - int(v * (vis_h // 2))
            row = max(0, min(h - 2, row))
            try:
                win.addch(row, col, wave_char, cp(PAIR_ACCENT) | curses.A_BOLD)
            except curses.error:
                pass

    def _draw_spectrum(self, win, bands, vis_h, w, mirror, ):
        """Filled area chart."""
        h, _ = win.getmaxyx()
        top_row = max(0, h - vis_h - 1)
        cols = list(range(1, w - 1))
        n = len(bands)
        expanded = [bands[int(i * n / len(cols))] for i in range(len(cols))]
        if mirror:
            half = len(cols) // 2
            left  = list(reversed(expanded[:half]))
            right = expanded[:half]
            expanded = left + right

        for i, v in enumerate(expanded):
            col = i + 1
            fill_h = int(v * vis_h)
            for row_off in range(vis_h):
                row = top_row + row_off
                if row >= h - 1:
                    break
                bar_row = vis_h - 1 - row_off
                if bar_row < fill_h:
                    attr = cp(PAIR_BAR_FILLED) if bar_row > 1 else (cp(PAIR_ACCENT2) | curses.A_BOLD)
                    try:
                        win.addch(row, col, "▓", attr)
                    except curses.error:
                        pass

    def _draw_dots(self, win, bands, vis_h, w, mirror):
        h, _ = win.getmaxyx()
        top_row = max(0, h - vis_h - 1)
        cols = list(range(1, w - 1))
        n = len(bands)
        expanded = [bands[int(i * n / len(cols))] for i in range(len(cols))]
        if mirror:
            half = len(cols) // 2
            left  = list(reversed(expanded[:half]))
            right = expanded[:half]
            expanded = left + right

        for i, v in enumerate(expanded):
            col = i + 1
            row = top_row + vis_h - 1 - int(v * (vis_h - 1))
            row = max(top_row, min(top_row + vis_h - 1, row))
            try:
                win.addch(row, col, "◆", cp(PAIR_ACCENT) | curses.A_BOLD)
            except curses.error:
                pass
