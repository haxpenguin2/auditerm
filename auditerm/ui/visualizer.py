import numpy as np
import curses
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2

class Visualizer:
    def __init__(self, player, cfg):
        self.player = player
        self._current_bands = []
        self._peaks = []
        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # CAVA Physics
        self.gravity = 0.05
        self.monstercat = 1.5  # Higher = smoother lateral transitions
        self.integral = 0.85   # Time smoothing (0.0 = instant, 1.0 = heavy)

    def _get_audio_bands(self, n_bands):
        if not self.player.is_playing or len(self.player.raw_samples) == 0:
            return [0.0] * n_bands

        # 1. Grab a chunk of samples based on current time
        sample_rate = 44100
        buffer_size = 2048
        start_idx = int(self.player.elapsed * sample_rate)
        end_idx = start_idx + buffer_size

        chunk = self.player.raw_samples[start_idx:end_idx]
        if len(chunk) < buffer_size:
            return [0.0] * n_bands

        # 2. FFT with Hanning Window (prevents "clicking" in data)
        window = np.hanning(len(chunk))
        fft = np.abs(np.fft.rfft(chunk * window))

        # 3. Logarithmic Scaling (CAVA Style)
        # Humans hear 20Hz-20kHz, but 90% of visual action is < 10kHz
        bands = np.zeros(n_bands)
        # Create bins that grow wider as frequency increases
        nodes = np.geomspace(2, len(fft)-1, n_bands + 1).astype(int)

        for i in range(n_bands):
            val = np.mean(fft[nodes[i]:nodes[i+1]])
            # Simple gain scaling - adjust 10.0 to change sensitivity
            bands[i] = val * 15.0

        return bands

    def _apply_physics(self, raw):
        n = len(raw)
        if len(self._current_bands) != n:
            self._current_bands = np.zeros(n)
            self._peaks = np.zeros(n)

        # Monstercat Smoothing (Lateral)
        # Bars "pull up" their neighbors for a wave-like look
        for i in range(1, n):
            raw[i] = max(raw[i], raw[i-1] / self.monstercat)
        for i in range(n-2, -1, -1):
            raw[i] = max(raw[i], raw[i+1] / self.monstercat)

        # Falling/Rising Physics
        for i in range(n):
            target = raw[i]
            if target > self._current_bands[i]:
                # Rise quickly but smooth
                self._current_bands[i] = (target * (1 - self.integral)) + (self._current_bands[i] * self.integral)
            else:
                # Fall by gravity
                self._current_bands[i] -= self.gravity

            self._current_bands[i] = max(0, self._current_bands[i])

            # Peak tracking
            if self._current_bands[i] > self._peaks[i]:
                self._peaks[i] = self._current_bands[i]
            else:
                self._peaks[i] -= (self.gravity * 0.5)
            self._peaks[i] = max(0, self._peaks[i])

        return self._current_bands

    def draw(self, win):
        win.erase()
        h_win, w_win = win.getmaxyx()
        if h_win < 3: return

        n_bands = w_win - 2
        h = h_win - 2

        raw = self._get_audio_bands(n_bands)
        bands = self._apply_physics(raw)

        for i, val in enumerate(bands):
            x = i + 1
            # Scale value to window height
            total = min(1.0, val) * h
            full = int(total)
            # Use smooth_blocks for sub-character resolution
            partial = int((total - full) * 8)

            # Draw the solid part
            for y in range(full):
                try: win.addch(h - y, x, "█", cp(PAIR_BAR_FILLED))
                except: pass

            # Draw the smooth top
            if full < h:
                try: win.addch(h - full, x, self.smooth_blocks[partial], cp(PAIR_BAR_FILLED))
                except: pass

            # Draw the falling peak
            py = h - int(self._peaks[i] * h)
            if 0 <= py <= h:
                try: win.addch(py, x, "─", cp(PAIR_ACCENT2))
                except: pass
