import curses
import math
import random
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT2
from auditerm.config import Config
from auditerm.player import Player

class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg = cfg
        self._target_bands = []  # Where the audio wants to be
        self._current_bands = [] # Where the bars actually are (smoothed)
        self._prev_bands = []    # History for integral smoothing
        self._peaks = []         # Falling peak logic

        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # CAVA Physics Constants
        self.gravity = 0.04      # How fast bars fall
        self.integral = 0.85     # Smoothing factor (0.0 to 1.0)
        self.monstercat = 0.7    # Neighbor influence (0.0 to 1.0)

    def _apply_physics(self, raw_bands):
        n = len(raw_bands)
        if not self._current_bands or len(self._current_bands) != n:
            self._current_bands = [0.0] * n
            self._prev_bands = [0.0] * n
            self._peaks = [0.0] * n

        # 1. Neighbor Smoothing (Monstercat style)
        # Higher frequencies are influenced by their lower neighbors
        for i in range(1, n):
            raw_bands[i] = max(raw_bands[i], raw_bands[i-1] * self.monstercat)
        for i in range(n-2, -1, -1):
            raw_bands[i] = max(raw_bands[i], raw_bands[i+1] * self.monstercat)

        # 2. Integral Smoothing & Gravity
        for i in range(n):
            # Target is the raw "audio" value
            target = raw_bands[i]

            # If the audio is higher than the bar, "ooze" up
            if target > self._current_bands[i]:
                self._current_bands[i] = target * (1 - self.integral) + self._current_bands[i] * self.integral
            else:
                # If audio is lower, let gravity pull the bar down
                self._current_bands[i] = max(0, self._current_bands[i] - self.gravity)

            # 3. Peak logic (falling slower than bars)
            if self._current_bands[i] > self._peaks[i]:
                self._peaks[i] = self._current_bands[i]
            else:
                self._peaks[i] = max(0, self._peaks[i] - (self.gravity * 0.5))

        return self._current_bands

    def draw(self, win):
        win.erase()
        h_win, w_win = win.getmaxyx()
        if h_win < 2 or w_win < 4: return

        # CAVA Setup
        n_bands = w_win - 2

        # Simulated raw input (replace this with FFT data if you switch backends)
        t = self.player.elapsed * 12
        raw = []
        for i in range(n_bands):
            # Base logic: lower bands are busier, higher bands have spikes
            freq_mod = (i / n_bands)
            sig = abs(math.sin(t * (0.2 + freq_mod)) * math.cos(t * 0.5))
            raw.append(sig * math.exp(-freq_mod * 2))

        # Apply the CAVA physics engine
        bands = self._apply_physics(raw)

        # Rendering
        h = h_win - 1
        for i, val in enumerate(bands):
            x = i + 1
            total_units = val * h
            full_cells = int(total_units)
            partial_idx = int((total_units - full_cells) * 8)

            # Draw Pillar
            for y_off in range(full_cells):
                try: win.addch(h - y_off, x, "█", cp(PAIR_BAR_FILLED))
                except curses.error: pass

            # Draw Smooth Cap
            if h - full_cells >= 0:
                try: win.addch(h - full_cells, x, self.smooth_blocks[partial_idx], cp(PAIR_BAR_FILLED))
                except curses.error: pass

            # Draw Peak
            pk_y = h - int(self._peaks[i] * h)
            if pk_y >= 0:
                try: win.addch(pk_y, x, "-", cp(PAIR_ACCENT2))
                except curses.error: pass
