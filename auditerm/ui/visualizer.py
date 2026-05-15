import curses
import math
import numpy as np
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2

class Visualizer:
    def __init__(self, player, cfg):
        self.player = player
        self.cfg = cfg

        self._current_bands = []
        self._peaks = []
        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # CAVA Tuning
        self.gravity = 0.04
        self.integral = 0.85
        self.monstercat = 1.5

        # Gain control to handle different song volumes
        self.max_history = 1.0
        self.agc_speed = 0.005

    def _get_audio_bands(self, n_bands):
        # Handle silence or missing samples
        if not self.player.is_playing or len(self.player.raw_samples) == 0:
            return [0.0] * n_bands

        sample_rate = 44100
        buffer_size = 2048

        # Syncing with current playback position
        current_idx = int(self.player.elapsed * sample_rate)
        data_chunk = self.player.raw_samples[current_idx : current_idx + buffer_size]

        if len(data_chunk) < buffer_size:
            return [0.0] * n_bands

        # Windowing and FFT
        window = np.hanning(len(data_chunk))
        fft_data = np.abs(np.fft.rfft(data_chunk * window))

        # Filter: Keep frequencies between ~20Hz and 15kHz
        fft_data = fft_data[2:int(len(fft_data) * 0.7)]

        # Logarithmic binning (more focus on bass/mids)
        bands = np.zeros(n_bands)
        nodes = np.geomspace(1, len(fft_data), n_bands + 1).astype(int)

        for i in range(n_bands):
            val = np.mean(fft_data[nodes[i]:nodes[i+1]])
            bands[i] = val

        # Simple Automatic Gain Control
        curr_max = np.max(bands) if np.max(bands) > 0 else 1.0
        if curr_max > self.max_history:
            self.max_history = curr_max
        else:
            self.max_history = (self.max_history * (1 - self.agc_speed) + curr_max * self.agc_speed)

        return (bands / self.max_history).tolist()

    def _apply_physics(self, raw):
        n = len(raw)
        if not self._current_bands or len(self._current_bands) != n:
            self._current_bands = [0.0] * n
            self._peaks = [0.0] * n

        # Monstercat (Lateral) Smoothing
        for i in range(1, n):
            raw[i] = max(raw[i], raw[i-1] / self.monstercat)
        for i in range(n-2, -1, -1):
            raw[i] = max(raw[i], raw[i+1] / self.monstercat)

        for i in range(n):
            target = raw[i]

            # Integral Smoothing
            if target > self._current_bands[i]:
                self._current_bands[i] = (target * (1 - self.integral) +
                                         self._current_bands[i] * self.integral)
            else:
                # Gravity fall
                self._current_bands[i] -= self.gravity

            self._current_bands[i] = max(0, self._current_bands[i])

            # Peak holding
            if self._current_bands[i] > self._peaks[i]:
                self._peaks[i] = self._current_bands[i]
            else:
                self._peaks[i] = max(0, self._peaks[i] - (self.gravity * 0.4))

        return self._current_bands

    def draw(self, win):
        win.erase()
        h_win, w_win = win.getmaxyx()
        if h_win < 3 or w_win < 4:
            return

        n_bands = w_win - 2
        h = h_win - 2

        raw = self._get_audio_bands(n_bands)
        bands = self._apply_physics(raw)

        for i, val in enumerate(bands):
            x = i + 1
            total = min(1.0, val) * h
            full = int(total)
            partial = int((total - full) * 8)

            # Bar core
            for y in range(full):
                try:
                    win.addch(h - y, x, "█", cp(PAIR_BAR_FILLED))
                except curses.error: pass

            # Smooth top
            if full < h:
                try:
                    win.addch(h - full, x, self.smooth_blocks[partial], cp(PAIR_BAR_FILLED))
                except curses.error: pass

            # Peak marker
            py = h - int(self._peaks[i] * h)
            if 0 <= py <= h:
                try:
                    win.addch(py, x, "─", cp(PAIR_ACCENT2))
                except curses.error: pass
