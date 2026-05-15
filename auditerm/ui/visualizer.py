"""
auditerm visualizer

Each column = loudness of one frequency band (20 Hz to 10 kHz, log spaced).
Stops immediately when audio stops. Config is read every frame so changes
to ~/.config/auditerm/config take effect without restarting.
"""

from __future__ import annotations
import curses
import numpy as np
from auditerm.config import Config
from auditerm.player import Player
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2, PAIR_MUTED, PAIR_ACCENT

BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg = cfg
        self._bars: np.ndarray = np.zeros(1, dtype=np.float32)
        self._peaks: np.ndarray = np.zeros(1, dtype=np.float32)
        self._n: int = 0

    def _stopped(self) -> bool:
        return not self.player.is_playing and not self.player.is_paused

    def _fft_bands(self, n: int) -> np.ndarray:
        if self._stopped():
            return np.zeros(n, dtype=np.float32)

        samples = self.player.raw_samples
        if samples is None or len(samples) < 2048:
            return np.zeros(n, dtype=np.float32)

        sr = 44100
        pos = int(self.player.elapsed * sr)
        chunk = samples[pos: pos + 2048]
        if len(chunk) < 2048:
            chunk = np.pad(chunk, (0, 2048 - len(chunk)))

        mag = np.abs(np.fft.rfft(chunk * np.hanning(2048).astype(np.float32)))
        n_fft = len(mag)

        lo = max(1, int(20 * 2048 / sr))
        hi = min(n_fft - 1, int(10000 * 2048 / sr))
        edges = np.geomspace(lo, hi, n + 1).astype(int)
        edges = np.clip(edges, 0, n_fft - 1)

        bands = np.empty(n, dtype=np.float32)
        for i in range(n):
            a = edges[i]
            b = max(a + 1, edges[i + 1])
            bands[i] = float(np.mean(mag[a:b]))

        rms = float(np.sqrt(np.mean(mag ** 2))) + 1e-9
        gain = float(self.cfg.get("visualizer", "gain", "14.0"))
        bands = (bands / rms) * (gain / 100.0)
        return np.clip(bands, 0.0, 1.0)

    def _physics(self, raw: np.ndarray) -> np.ndarray:
        # Read config every frame so edits take effect immediately
        gravity = float(self.cfg.get("visualizer", "gravity", "0.035"))
        smoothing = float(self.cfg.get("visualizer", "smoothing", "0.75"))
        monstercat = float(self.cfg.get("visualizer", "monstercat", "1.8"))

        n = len(raw)
        if n != self._n:
            self._bars = np.zeros(n, dtype=np.float32)
            self._peaks = np.zeros(n, dtype=np.float32)
            self._n = n

        # When stopped: drain everything to zero then stop touching state
        if self._stopped():
            if np.any(self._bars > 0) or np.any(self._peaks > 0):
                self._bars = np.maximum(0.0, self._bars - gravity * 4)
                self._peaks = np.maximum(0.0, self._peaks - gravity * 2)
            return self._bars.copy()

        # Monstercat lateral smoothing
        s = raw.copy()
        for i in range(1, n):
            if s[i - 1] / monstercat > s[i]:
                s[i] = s[i - 1] / monstercat
        for i in range(n - 2, -1, -1):
            if s[i + 1] / monstercat > s[i]:
                s[i] = s[i + 1] / monstercat

        # Rise / fall
        for i in range(n):
            if s[i] > self._bars[i]:
                self._bars[i] += (s[i] - self._bars[i]) * (1.0 - smoothing)
            else:
                self._bars[i] = max(0.0, self._bars[i] - gravity)
            if self._bars[i] >= self._peaks[i]:
                self._peaks[i] = self._bars[i]
            else:
                self._peaks[i] = max(0.0, self._peaks[i] - gravity * 0.4)

        return self._bars.copy()

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        if h < 2 or w < 4:
            return

        style = self.cfg.get("visualizer", "style", "bars")
        if style == "off":
            return

        n = max(1, (w - 2) // 2 if style == "mirror" else w - 2)
        raw = self._fft_bands(n)
        bands = self._physics(raw)

        if style in ("bars", "mirror"):
            self._draw_bars(win, bands, h, w, mirror=(style == "mirror"))
        elif style == "wave":
            self._draw_wave(win, bands, h, w)
        elif style == "dots":
            self._draw_dots(win, bands, h, w)

    def _draw_bars(self, win, bands, h, w, mirror=False):
        peaks = self._peaks[:len(bands)]

        def draw_col(x, val, peak):
            if not (1 <= x < w - 1):
                return
            fh = val * (h - 1)
            full = int(fh)
            partial = int((fh - full) * 8)
            for off in range(full):
                row = h - 1 - off
                if 0 <= row < h:
                    try:
                        win.addch(row, x, "█", cp(PAIR_BAR_FILLED))
                    except curses.error:
                        pass
            top = h - 1 - full
            if 0 <= top < h and partial > 0:
                try:
                    win.addch(top, x, BLOCKS[partial], cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass
            if peak > 0.015:
                pr = max(0, min(h - 1, h - 1 - int(peak * (h - 1))))
                try:
                    win.addch(pr, x, "─", cp(PAIR_ACCENT2) | curses.A_BOLD)
                except curses.error:
                    pass

        if mirror:
            cx = w // 2
            for i, (v, p) in enumerate(zip(bands, peaks)):
                draw_col(cx - 1 - i, v, p)
                draw_col(cx + i, v, p)
        else:
            for i, (v, p) in enumerate(zip(bands, peaks)):
                draw_col(i + 1, v, p)

    def _draw_wave(self, win, bands, h, w):
        cols = w - 2
        n = len(bands)
        if n == 0:
            return
        exp = np.interp(np.linspace(0, n - 1, cols), np.arange(n), bands)
        mid = h // 2
        for i, v in enumerate(exp):
            x = i + 1
            amp = int(v * max(1, h // 2 - 1))
            for row in range(max(0, mid - amp), min(h, mid + amp + 1)):
                ch = "─" if row == mid else ("█" if row in (mid - amp, mid + amp) else "│")
                attr = cp(PAIR_ACCENT) | curses.A_BOLD if row in (mid - amp, mid + amp) else cp(PAIR_BAR_FILLED)
                try:
                    win.addch(row, x, ch, attr)
                except curses.error:
                    pass

    def _draw_dots(self, win, bands, h, w):
        cols = w - 2
        n = len(bands)
        if n == 0:
            return
        peaks = self._peaks[:n]
        exp = np.interp(np.linspace(0, n - 1, cols), np.arange(n), bands)
        expp = np.interp(np.linspace(0, n - 1, cols), np.arange(n), peaks)
        for i, (v, p) in enumerate(zip(exp, expp)):
            x = i + 1
            r = max(0, min(h - 1, h - 1 - int(v * (h - 1))))
            pr = max(0, min(h - 1, h - 1 - int(p * (h - 1))))
            try:
                if pr != r and p > 0.015:
                    win.addch(pr, x, "·", cp(PAIR_MUTED))
                win.addch(r, x, "◆", cp(PAIR_ACCENT) | curses.A_BOLD)
            except curses.error:
                pass
