"""
auditerm visualizer — CAVA-style FFT visualizer.

Styles: bars | mirror | wave | spectrum | dots | off

Physics mirrors CAVA:
  - Hanning-windowed FFT
  - Logarithmic frequency bins (geomspace, 20Hz–10kHz range)
  - Monstercat lateral smoothing
  - Per-band gravity fall + peak dot with slow decay
  - Time-domain integral smoothing on rise

All tunables are read from config [visualizer] section.
"""

import curses
import numpy as np

from auditerm.ui.colors import (
    cp,
    PAIR_BAR_FILLED, PAIR_BAR_EMPTY,
    PAIR_ACCENT, PAIR_ACCENT2, PAIR_MUTED,
)
from auditerm.config import Config
from auditerm.player import Player

# Sub-character vertical resolution (braille-style eighth blocks)
EIGHTH_BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg    = cfg

        # Physics params — read from config, fall back to CAVA defaults
        self.gravity     = float(cfg.get("visualizer", "gravity",     "0.04"))
        self.monstercat  = float(cfg.get("visualizer", "monstercat",  "1.6"))
        self.integral    = float(cfg.get("visualizer", "integral",    "0.82"))
        self.gain        = float(cfg.get("visualizer", "gain",        "12.0"))
        self.sample_rate = 44100
        self.buffer_size = 2048

        # State
        self._bands:  np.ndarray = np.array([])
        self._peaks:  np.ndarray = np.array([])
        self._prev_raw: np.ndarray = np.array([])

    # ── FFT ──────────────────────────────────────────────────────

    def _get_fft_bands(self, n_bands: int) -> np.ndarray:
        """
        1. Slice a buffer_size chunk from raw_samples at current playback pos.
        2. Apply Hanning window → FFT.
        3. Map FFT bins onto n_bands logarithmic frequency buckets.
        4. Normalize and apply gain.
        """
        samples = self.player.raw_samples

        if not (self.player.is_playing or self.player.is_paused) \
                or samples is None or len(samples) == 0:
            return np.zeros(n_bands)

        start = int(self.player.elapsed * self.sample_rate)
        end   = start + self.buffer_size
        chunk = samples[start:end]

        if len(chunk) < self.buffer_size:
            # end of track — zero pad
            chunk = np.pad(chunk, (0, self.buffer_size - len(chunk)))

        # Normalize int16 → float [-1, 1]
        if chunk.dtype != np.float32 and chunk.dtype != np.float64:
            chunk = chunk.astype(np.float32) / 32768.0

        window  = np.hanning(len(chunk))
        fft_mag = np.abs(np.fft.rfft(chunk * window))
        n_fft   = len(fft_mag)

        # Logarithmic bin edges: map to 20 Hz – 10 kHz
        low_bin  = max(1, int(20   / (self.sample_rate / 2) * n_fft))
        high_bin = min(n_fft - 1, int(10000 / (self.sample_rate / 2) * n_fft))
        edges    = np.geomspace(low_bin, high_bin, n_bands + 1).astype(int)
        edges    = np.clip(edges, 0, n_fft - 1)

        bands = np.zeros(n_bands)
        for i in range(n_bands):
            lo, hi = edges[i], edges[i + 1]
            if hi <= lo:
                hi = lo + 1
            bands[i] = np.mean(fft_mag[lo:hi])

        # Normalize: divide by RMS of the whole FFT, then apply gain
        rms = np.sqrt(np.mean(fft_mag ** 2)) + 1e-9
        bands = (bands / rms) * (self.gain / 100.0)
        bands = np.clip(bands, 0.0, 1.0)

        return bands

    # ── Physics ──────────────────────────────────────────────────

    def _apply_physics(self, raw: np.ndarray) -> np.ndarray:
        n = len(raw)

        if len(self._bands) != n:
            self._bands    = np.zeros(n)
            self._peaks    = np.zeros(n)
            self._prev_raw = np.zeros(n)

        # ── Monstercat lateral smoothing ──────────────────────────
        # Forward pass: each bar pulls up from the left
        smoothed = raw.copy()
        for i in range(1, n):
            smoothed[i] = max(smoothed[i], smoothed[i - 1] / self.monstercat)
        # Backward pass: and from the right
        for i in range(n - 2, -1, -1):
            smoothed[i] = max(smoothed[i], smoothed[i + 1] / self.monstercat)

        # ── Per-band rise/fall physics ─────────────────────────────
        for i in range(n):
            target = smoothed[i]
            if target > self._bands[i]:
                # Rise: exponential smoothing toward target
                self._bands[i] += (target - self._bands[i]) * (1.0 - self.integral)
            else:
                # Fall: constant gravity
                self._bands[i] -= self.gravity
            self._bands[i] = max(0.0, min(1.0, self._bands[i]))

            # Peak: rises instantly, falls at half gravity
            if self._bands[i] > self._peaks[i]:
                self._peaks[i] = self._bands[i]
            else:
                self._peaks[i] -= self.gravity * 0.5
            self._peaks[i] = max(0.0, min(1.0, self._peaks[i]))

        self._prev_raw = smoothed
        return self._bands.copy()

    # ── Draw dispatch ─────────────────────────────────────────────

    def draw(self, win):
        win.erase()
        h_win, w_win = win.getmaxyx()
        if h_win < 2 or w_win < 4:
            return

        style  = self.cfg.get("visualizer", "style", "bars")
        mirror = self.cfg.getbool("visualizer", "mirror", True)

        if style == "off":
            return

        # Content area (leave 1-char border on left/right)
        content_w = w_win - 2
        h         = h_win          # use full height for the vis window

        if style == "mirror":
            n_bands = content_w // 2
        else:
            n_bands = content_w

        raw   = self._get_fft_bands(n_bands)
        bands = self._apply_physics(raw)

        if style in ("bars", "mirror"):
            self._draw_bars(win, bands, h, w_win, style == "mirror")
        elif style == "wave":
            self._draw_wave(win, bands, h, w_win)
        elif style == "spectrum":
            self._draw_spectrum(win, bands, h, w_win)
        elif style == "dots":
            self._draw_dots(win, bands, h, w_win)

    # ── Bar renderer (bars + mirror) ─────────────────────────────

    def _draw_bars(self, win, bands: np.ndarray, h: int, w: int, mirror: bool):
        n = len(bands)
        peaks = self._peaks[:n]

        def draw_column(col: int, val: float, peak: float):
            """Draw one bar column with eighth-block smooth top and peak dot."""
            total_h  = val * (h - 1)          # float height in chars
            full     = int(total_h)            # solid blocks
            partial  = int((total_h - full) * 8)  # 0–7 for smooth top

            # solid fill from bottom
            for row_off in range(full):
                row = h - 1 - row_off
                if 0 <= row < h:
                    try:
                        win.addch(row, col, "█", cp(PAIR_BAR_FILLED))
                    except curses.error:
                        pass

            # smooth partial block on top
            top_row = h - 1 - full
            if 0 <= top_row < h and partial > 0:
                try:
                    win.addch(top_row, col, EIGHTH_BLOCKS[partial], cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass

            # falling peak dot
            if peak > 0.01:
                peak_row = h - 1 - int(peak * (h - 1))
                peak_row = max(0, min(h - 1, peak_row))
                try:
                    win.addch(peak_row, col, "─", cp(PAIR_ACCENT2) | curses.A_BOLD)
                except curses.error:
                    pass

        if mirror:
            # Left half: bands reversed; right half: bands forward
            half_w = w // 2
            for i, (val, peak) in enumerate(zip(bands, peaks)):
                left_col  = half_w - 1 - i
                right_col = half_w + i
                if 1 <= left_col < w - 1:
                    draw_column(left_col, val, peak)
                if 1 <= right_col < w - 1:
                    draw_column(right_col, val, peak)
        else:
            for i, (val, peak) in enumerate(zip(bands, peaks)):
                col = i + 1
                if col < w - 1:
                    draw_column(col, val, peak)

    # ── Wave renderer ─────────────────────────────────────────────

    def _draw_wave(self, win, bands: np.ndarray, h: int, w: int):
        """Oscilloscope-style center wave."""
        mid  = h // 2
        cols = w - 2
        n    = len(bands)

        # Expand bands to fill width
        expanded = np.interp(np.linspace(0, n - 1, cols), np.arange(n), bands)

        prev_row = None
        for i, val in enumerate(expanded):
            col = i + 1
            # val drives amplitude above/below center
            offset = int(val * (h // 2 - 1))
            row_hi = max(0, mid - offset)
            row_lo = min(h - 1, mid + offset)

            # vertical line connecting hi and lo for filled look
            for row in range(row_hi, row_lo + 1):
                attr = cp(PAIR_ACCENT) | curses.A_BOLD if row == row_hi or row == row_lo \
                       else cp(PAIR_BAR_FILLED)
                try:
                    win.addch(row, col, "│" if row != mid else "─", attr)
                except curses.error:
                    pass

    # ── Spectrum (filled area) ────────────────────────────────────

    def _draw_spectrum(self, win, bands: np.ndarray, h: int, w: int):
        """Filled area under the curve, gradient-style."""
        cols = w - 2
        n    = len(bands)
        expanded = np.interp(np.linspace(0, n - 1, cols), np.arange(n), bands)

        for i, val in enumerate(expanded):
            col      = i + 1
            fill_h   = int(val * (h - 1))
            total_h  = val * (h - 1)
            partial  = int((total_h - fill_h) * 8)

            for row_off in range(fill_h):
                row = h - 1 - row_off
                # Gradient: top rows use accent color
                attr = cp(PAIR_ACCENT2) if row_off >= fill_h - 2 else cp(PAIR_BAR_FILLED)
                try:
                    win.addch(row, col, "█", attr)
                except curses.error:
                    pass

            top_row = h - 1 - fill_h
            if 0 <= top_row < h and partial > 0:
                try:
                    win.addch(top_row, col, EIGHTH_BLOCKS[partial], cp(PAIR_ACCENT2))
                except curses.error:
                    pass

    # ── Dots ─────────────────────────────────────────────────────

    def _draw_dots(self, win, bands: np.ndarray, h: int, w: int):
        """Single dot per band at its current height, with peak trail."""
        cols   = w - 2
        n      = len(bands)
        peaks  = self._peaks[:n]
        expanded       = np.interp(np.linspace(0, n - 1, cols), np.arange(n), bands)
        expanded_peaks = np.interp(np.linspace(0, n - 1, cols), np.arange(n), peaks)

        for i, (val, pk) in enumerate(zip(expanded, expanded_peaks)):
            col  = i + 1
            row  = h - 1 - int(val * (h - 1))
            prow = h - 1 - int(pk  * (h - 1))
            row  = max(0, min(h - 1, row))
            prow = max(0, min(h - 1, prow))
            try:
                if prow != row:
                    win.addch(prow, col, "·", cp(PAIR_MUTED))
                win.addch(row, col, "◆", cp(PAIR_ACCENT) | curses.A_BOLD)
            except curses.error:
                pass
