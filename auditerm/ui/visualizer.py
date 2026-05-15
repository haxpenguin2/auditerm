"""
auditerm visualizer

Draws a bar visualizer driven by real FFT data from the player's raw_samples.
Stops cleanly when audio stops. Simple, reliable, good-looking.

Styles (set in config): bars | mirror | wave | dots | off
"""

import curses
import numpy as np

from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2, PAIR_MUTED, PAIR_ACCENT
from auditerm.config import Config
from auditerm.player import Player

# Eighth-block characters for smooth sub-character bar tops
BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg    = cfg

        self.gravity    = float(cfg.get("visualizer", "gravity",    "0.035"))
        self.smoothing  = float(cfg.get("visualizer", "smoothing",  "0.75"))
        self.monstercat = float(cfg.get("visualizer", "monstercat", "1.8"))
        self.gain       = float(cfg.get("visualizer", "gain",       "14.0"))

        self._bars:  np.ndarray = np.zeros(1)
        self._peaks: np.ndarray = np.zeros(1)

    # ─────────────────────────────────────────────────────────────
    # FFT
    # ─────────────────────────────────────────────────────────────

    def _compute_bands(self, n: int) -> np.ndarray:
        """
        Returns n float values in [0.0, 1.0].
        Returns zeros immediately if nothing is playing.
        """
        # Stop condition: return flat zero if not playing
        if not (self.player.is_playing or self.player.is_paused):
            return np.zeros(n)

        samples = self.player.raw_samples
        if samples is None or len(samples) == 0:
            return np.zeros(n)

        # Slice a 2048-sample window at current playback position
        sr      = 44100
        win_sz  = 2048
        pos     = int(self.player.elapsed * sr)
        chunk   = samples[pos : pos + win_sz]

        if len(chunk) < win_sz:
            return np.zeros(n)

        # Hanning window + FFT magnitude
        window  = np.hanning(win_sz).astype(np.float32)
        mag     = np.abs(np.fft.rfft(chunk * window))

        # Map FFT bins → n log-spaced frequency bands (20 Hz – 10 kHz)
        n_fft   = len(mag)
        lo      = max(1,        int(20    / (sr / 2) * n_fft))
        hi      = min(n_fft-1,  int(10000 / (sr / 2) * n_fft))
        edges   = np.geomspace(lo, hi, n + 1).astype(int)

        bands = np.zeros(n, dtype=np.float32)
        for i in range(n):
            a, b = edges[i], max(edges[i]+1, edges[i+1])
            bands[i] = np.mean(mag[a:b])

        # Normalize by spectrum RMS so quiet tracks still show bars
        rms = float(np.sqrt(np.mean(mag**2))) + 1e-9
        bands = (bands / rms) * (self.gain / 100.0)

        return np.clip(bands, 0.0, 1.0)

    # ─────────────────────────────────────────────────────────────
    # Physics
    # ─────────────────────────────────────────────────────────────

    def _physics(self, raw: np.ndarray) -> np.ndarray:
        n = len(raw)
        if len(self._bars) != n:
            self._bars  = np.zeros(n)
            self._peaks = np.zeros(n)

        # If audio stopped, drain bars to zero with gravity only
        if not (self.player.is_playing or self.player.is_paused):
            self._bars  = np.maximum(0.0, self._bars  - self.gravity * 3)
            self._peaks = np.maximum(0.0, self._peaks - self.gravity * 1.5)
            return self._bars.copy()

        # Monstercat: each bar pulls up neighbours so bands flow smoothly
        s = raw.copy()
        for i in range(1, n):
            s[i] = max(s[i], s[i-1] / self.monstercat)
        for i in range(n-2, -1, -1):
            s[i] = max(s[i], s[i+1] / self.monstercat)

        for i in range(n):
            if s[i] > self._bars[i]:
                # Rise: smooth lerp toward target
                self._bars[i] += (s[i] - self._bars[i]) * (1.0 - self.smoothing)
            else:
                # Fall: gravity
                self._bars[i] = max(0.0, self._bars[i] - self.gravity)

            # Peak dot: instant rise, slow fall
            if self._bars[i] >= self._peaks[i]:
                self._peaks[i] = self._bars[i]
            else:
                self._peaks[i] = max(0.0, self._peaks[i] - self.gravity * 0.4)

        return self._bars.copy()

    # ─────────────────────────────────────────────────────────────
    # Draw
    # ─────────────────────────────────────────────────────────────

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        if h < 2 or w < 4:
            return

        style = self.cfg.get("visualizer", "style", "bars")
        if style == "off":
            return

        # Number of bands = drawable columns
        if style == "mirror":
            n = (w - 2) // 2
        else:
            n = w - 2

        raw   = self._compute_bands(n)
        bands = self._physics(raw)

        if style in ("bars", "mirror"):
            self._draw_bars(win, bands, h, w, mirror=(style == "mirror"))
        elif style == "wave":
            self._draw_wave(win, bands, h, w)
        elif style == "dots":
            self._draw_dots(win, bands, h, w)

    # ─────────────────────────────────────────────────────────────
    # Styles
    # ─────────────────────────────────────────────────────────────

    def _draw_bars(self, win, bands, h, w, mirror=False):
        peaks = self._peaks[:len(bands)]

        def col(x, val, peak):
            # floating-point height → full blocks + smooth top eighth-block
            fh      = val * (h - 1)
            full    = int(fh)
            partial = int((fh - full) * 8)

            # solid fill upward from bottom row
            for off in range(full):
                row = h - 1 - off
                if 0 <= row < h:
                    try: win.addch(row, x, "█", cp(PAIR_BAR_FILLED))
                    except curses.error: pass

            # smooth partial block on top
            top = h - 1 - full
            if 0 <= top < h and partial > 0:
                try: win.addch(top, x, BLOCKS[partial], cp(PAIR_BAR_FILLED))
                except curses.error: pass

            # falling peak dash
            if peak > 0.015:
                pr = h - 1 - int(peak * (h - 1))
                pr = max(0, min(h - 1, pr))
                try: win.addch(pr, x, "─", cp(PAIR_ACCENT2) | curses.A_BOLD)
                except curses.error: pass

        if mirror:
            cx = w // 2
            for i, (v, p) in enumerate(zip(bands, peaks)):
                lx = cx - 1 - i
                rx = cx + i
                if 1 <= lx < w-1: col(lx, v, p)
                if 1 <= rx < w-1: col(rx, v, p)
        else:
            for i, (v, p) in enumerate(zip(bands, peaks)):
                x = i + 1
                if x < w - 1:
                    col(x, v, p)

    def _draw_wave(self, win, bands, h, w):
        mid  = h // 2
        cols = w - 2
        n    = len(bands)
        exp  = np.interp(np.linspace(0, n-1, cols), np.arange(n), bands)

        for i, v in enumerate(exp):
            x      = i + 1
            amp    = int(v * (h // 2 - 1))
            top    = max(0,   mid - amp)
            bottom = min(h-1, mid + amp)
            for row in range(top, bottom + 1):
                ch   = "┼" if row == mid else ("╷" if row < mid else "╵")
                attr = cp(PAIR_ACCENT) | curses.A_BOLD if row in (top, bottom) \
                       else cp(PAIR_BAR_FILLED)
                try: win.addch(row, x, ch, attr)
                except curses.error: pass

    def _draw_dots(self, win, bands, h, w):
        cols  = w - 2
        n     = len(bands)
        peaks = self._peaks[:n]
        exp   = np.interp(np.linspace(0, n-1, cols), np.arange(n), bands)
        expp  = np.interp(np.linspace(0, n-1, cols), np.arange(n), peaks)

        for i, (v, p) in enumerate(zip(exp, expp)):
            x  = i + 1
            r  = max(0, min(h-1, h - 1 - int(v * (h-1))))
            pr = max(0, min(h-1, h - 1 - int(p * (h-1))))
            try:
                if pr != r and p > 0.015:
                    win.addch(pr, x, "·", cp(PAIR_MUTED))
                win.addch(r, x, "◆", cp(PAIR_ACCENT) | curses.A_BOLD)
            except curses.error: passpass
