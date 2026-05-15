"""
auditerm visualizer

Each column = loudness of a frequency band humans can hear (20 Hz – 10 kHz),
spread logarithmically so bass takes up as much visual space as treble.

Styles: bars | mirror | wave | dots | off
All parameters read from config [visualizer] section.
"""

from __future__ import annotations

import curses
import numpy as np

from auditerm.config import Config
from auditerm.player import Player
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2, PAIR_MUTED, PAIR_ACCENT

# Sub-character vertical resolution — eighth-block chars
BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg    = cfg

        # Physics — all read live from config each draw so config changes take effect
        self._bars:  np.ndarray = np.zeros(1)
        self._peaks: np.ndarray = np.zeros(1)
        self._n_last: int = 0

    # ── helpers ───────────────────────────────────────────────────

    def _params(self):
        """Read physics params fresh from config every frame."""
        return (
            float(self.cfg.get("visualizer", "gravity",    "0.035")),
            float(self.cfg.get("visualizer", "smoothing",  "0.75")),
            float(self.cfg.get("visualizer", "monstercat", "1.8")),
            float(self.cfg.get("visualizer", "gain",       "14.0")),
        )

    # ── FFT ───────────────────────────────────────────────────────

    def _fft_bands(self, n: int) -> np.ndarray:
        """
        Slice 2048 samples at current playback position, FFT them,
        and bucket into n log-spaced bands covering 20 Hz – 10 kHz.
        Returns zeros if nothing is playing or samples aren't ready yet.
        """
        if not (self.player.is_playing or self.player.is_paused):
            return np.zeros(n, dtype=np.float32)

        samples = self.player.raw_samples
        if samples is None or len(samples) < 2048:
            return np.zeros(n, dtype=np.float32)

        sr     = 44100
        winsz  = 2048
        pos    = int(self.player.elapsed * sr)
        chunk  = samples[pos: pos + winsz]

        if len(chunk) < winsz:
            # near end of track — zero-pad rather than skip
            chunk = np.pad(chunk, (0, winsz - len(chunk)))

        # Hanning window reduces spectral leakage
        win = np.hanning(winsz).astype(np.float32)
        mag = np.abs(np.fft.rfft(chunk * win))

        n_fft = len(mag)
        # frequency of bin k = k * sr / winsz
        lo_bin = max(1,        int(20    * winsz / sr))
        hi_bin = min(n_fft-1,  int(10000 * winsz / sr))

        # n+1 logarithmically spaced bin edges
        edges = np.geomspace(lo_bin, hi_bin, n + 1).astype(int)
        edges = np.clip(edges, 0, n_fft - 1)

        bands = np.empty(n, dtype=np.float32)
        for i in range(n):
            a = edges[i]
            b = max(a + 1, edges[i + 1])
            bands[i] = float(np.mean(mag[a:b]))

        # Normalize against spectrum RMS so quiet tracks still have visible bars
        rms = float(np.sqrt(np.mean(mag ** 2))) + 1e-9
        _, _, _, gain = self._params()
        bands = (bands / rms) * (gain / 100.0)

        return np.clip(bands, 0.0, 1.0)

    # ── Physics ───────────────────────────────────────────────────

    def _physics(self, raw: np.ndarray) -> np.ndarray:
        gravity, smoothing, monstercat, _ = self._params()
        n = len(raw)

        # Resize state arrays when band count changes (e.g. terminal resize)
        if n != self._n_last:
            self._bars  = np.zeros(n, dtype=np.float32)
            self._peaks = np.zeros(n, dtype=np.float32)
            self._n_last = n

        # Drain to zero when stopped — bars fall off screen cleanly
        if not (self.player.is_playing or self.player.is_paused):
            self._bars  = np.maximum(0.0, self._bars  - gravity * 3)
            self._peaks = np.maximum(0.0, self._peaks - gravity * 1.5)
            return self._bars.copy()

        # Monstercat smoothing: each bar pulls up its neighbours
        s = raw.copy()
        for i in range(1, n):
            if s[i - 1] / monstercat > s[i]:
                s[i] = s[i - 1] / monstercat
        for i in range(n - 2, -1, -1):
            if s[i + 1] / monstercat > s[i]:
                s[i] = s[i + 1] / monstercat

        # Rise/fall per bar
        rising  = s > self._bars
        falling = ~rising

        self._bars[rising]  += (s[rising]  - self._bars[rising])  * (1.0 - smoothing)
        self._bars[falling]  = np.maximum(0.0, self._bars[falling] - gravity)

        # Peak: instant rise, slow fall
        new_peak = self._bars > self._peaks
        self._peaks[new_peak]  = self._bars[new_peak]
        self._peaks[~new_peak] = np.maximum(0.0, self._peaks[~new_peak] - gravity * 0.4)

        return self._bars.copy()

    # ── Draw dispatch ─────────────────────────────────────────────

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        if h < 2 or w < 4:
            return

        style = self.cfg.get("visualizer", "style", "bars")
        if style == "off":
            return

        n = (w - 2) // 2 if style == "mirror" else w - 2
        n = max(1, n)

        raw   = self._fft_bands(n)
        bands = self._physics(raw)

        if style in ("bars", "mirror"):
            self._draw_bars(win, bands, h, w, mirror=(style == "mirror"))
        elif style == "wave":
            self._draw_wave(win, bands, h, w)
        elif style == "dots":
            self._draw_dots(win, bands, h, w)
        # unknown style → nothing drawn (no crash)

    # ── Bar renderer ──────────────────────────────────────────────

    def _draw_bars(self, win, bands: np.ndarray, h: int, w: int, mirror: bool):
        peaks = self._peaks[:len(bands)]

        def draw_col(x: int, val: float, peak: float):
            if x < 1 or x >= w - 1:
                return
            fh      = val * (h - 1)
            full    = int(fh)
            partial = int((fh - full) * 8)

            for off in range(full):
                row = h - 1 - off
                if 0 <= row < h:
                    try:
                        win.addch(row, x, ord("█"), cp(PAIR_BAR_FILLED))
                    except curses.error:
                        pass

            top = h - 1 - full
            if 0 <= top < h and partial > 0:
                try:
                    win.addch(top, x, ord(BLOCKS[partial]), cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass

            if peak > 0.015:
                pr = h - 1 - int(peak * (h - 1))
                pr = max(0, min(h - 1, pr))
                try:
                    win.addch(pr, x, ord("─"), cp(PAIR_ACCENT2) | curses.A_BOLD)
                except curses.error:
                    pass

        if mirror:
            cx = w // 2
            for i, (v, p) in enumerate(zip(bands, peaks)):
                draw_col(cx - 1 - i, v, p)
                draw_col(cx + i,     v, p)
        else:
            for i, (v, p) in enumerate(zip(bands, peaks)):
                draw_col(i + 1, v, p)

    # ── Wave renderer ─────────────────────────────────────────────

    def _draw_wave(self, win, bands: np.ndarray, h: int, w: int):
        mid  = h // 2
        cols = w - 2
        n    = len(bands)
        if n == 0:
            return
        exp = np.interp(np.linspace(0, n - 1, cols), np.arange(n), bands)

        for i, v in enumerate(exp):
            x   = i + 1
            amp = int(v * max(1, h // 2 - 1))
            top = max(0,   mid - amp)
            bot = min(h-1, mid + amp)
            for row in range(top, bot + 1):
                if row == mid:
                    ch   = ord("─")
                    attr = cp(PAIR_BAR_FILLED)
                elif row in (top, bot):
                    ch   = ord("█")
                    attr = cp(PAIR_ACCENT) | curses.A_BOLD
                else:
                    ch   = ord("│")
                    attr = cp(PAIR_BAR_FILLED)
                try:
                    win.addch(row, x, ch, attr)
                except curses.error:
                    pass

    # ── Dots renderer ─────────────────────────────────────────────

    def _draw_dots(self, win, bands: np.ndarray, h: int, w: int):
        cols  = w - 2
        n     = len(bands)
        if n == 0:
            return
        peaks = self._peaks[:n]
        exp   = np.interp(np.linspace(0, n-1, cols), np.arange(n), bands)
        expp  = np.interp(np.linspace(0, n-1, cols), np.arange(n), peaks)

        for i, (v, p) in enumerate(zip(exp, expp)):
            x  = i + 1
            r  = max(0, min(h-1, h - 1 - int(v * (h - 1))))
            pr = max(0, min(h-1, h - 1 - int(p * (h - 1))))
            try:
                if pr != r and p > 0.015:
                    win.addch(pr, x, ord("·"), cp(PAIR_MUTED))
                win.addch(r, x, ord("◆"), cp(PAIR_ACCENT) | curses.A_BOLD)
            except curses.error:
                pass
