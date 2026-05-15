import curses
import math
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2
from auditerm.config import Config
from auditerm.player import Player


class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg = cfg
        self._current_bands = []
        self._peaks = []
        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # CAVA Physics
        self.gravity = 0.05
        self.integral = 0.85
        self.monstercat = 1.5 # Higher = smoother transitions between bars
        self.silence_threshold = 0.01

    def _get_audio_bands(self, n_bands):
        if not self.player.is_playing or not hasattr(self.player, 'raw_samples'):
            return [0.0] * n_bands

        # 1. Sync: Figure out where we are in the sample array
        sample_rate = 44100
        buffer_size = 2048
        current_sample = int(self.player.elapsed * sample_rate)

        # Pull a chunk of data
        data_chunk = self.player.raw_samples[current_sample : current_sample + buffer_size]

        if len(data_chunk) < buffer_size:
            return [0.0] * n_bands

        # 2. FFT: Convert time domain to frequency domain
        # Apply Hanning window to smooth the edges of the buffer
        window = np.hanning(len(data_chunk))
        fft_data = np.abs(np.fft.rfft(data_chunk * window))

        # 3. Logarithmic Scaling: Humans hear frequencies logarithmically
        # We group FFT bins into 'n_bands'
        bands = np.zeros(n_bands)
        # Calculate indices for frequency bands (log scale)
        # This ensures bass gets more detail than high-pitch
        nodes = np.geomspace(1, len(fft_data), n_bands + 1).astype(int)

        for i in range(n_bands):
            start, end = nodes[i], nodes[i+1]
            if start == end: end += 1
            # Take the average magnitude in this band
            val = np.mean(fft_data[start:end])
            # Normalize and apply a simple gain boost for visualization
            bands[i] = (val / 5000.0)

        return bands.tolist()

    def _apply_physics(self, raw):
        n = len(raw)
        if not self._current_bands or len(self._current_bands) != n:
            self._current_bands = [0.0] * n
            self._peaks = [0.0] * n

        # Monstercat smoothing (Adjacent bar influence)
        for i in range(1, n):
            raw[i] = max(raw[i], raw[i-1] / self.monstercat)
        for i in range(n-2, -1, -1):
            raw[i] = max(raw[i], raw[i+1] / self.monstercat)

        for i in range(n):
            # Slow down the fall (Gravity)
            if raw[i] > self._current_bands[i]:
                self._current_bands[i] = raw[i]
            else:
                self._current_bands[i] -= self.gravity

            self._current_bands[i] = max(0, self._current_bands[i])

            # Peak logic
            if self._current_bands[i] > self._peaks[i]:
                self._peaks[i] = self._current_bands[i]
            else:
                self._peaks[i] = max(0, self._peaks[i] - (self.gravity * 0.5))

        return self._current_bands

    def draw(self, win):
        win.erase()
        h_win, w_win = win.getmaxyx()
        if h_win < 2 or w_win < 4: return

        n_bands = w_win - 2
        h = h_win - 2 # Leave space for the floor

        # Get real data
        raw = self._get_audio_bands(n_bands)
        bands = self._apply_physics(raw)

        for i, val in enumerate(bands):
            x = i + 1
            # Scale value to window height
            total = min(1.0, val) * h
            full = int(total)
            partial = int((total - full) * 8)

            # Draw the solid bars
            for y in range(full):
                try: win.addch(h - y, x, "█", cp(PAIR_BAR_FILLED))
                except: pass

            # Draw the smooth top transition
            if full < h:
                try: win.addch(h - full, x, self.smooth_blocks[partial], cp(PAIR_BAR_FILLED))
                except: pass

            # Draw the falling peak
            py = h - int(self._peaks[i] * h)
            if 0 <= py <= h:
                try: win.addch(py, x, "─", cp(PAIR_ACCENT2))
                except: pass
