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
        self._bands: list[float] = []
        self._peaks: list[float] = []
        # Unicode characters for sub-cell vertical resolution (CAVA style)
        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def _generate_bands(self, n: int) -> list[float]:
        p = self.player
        # Fade out if nothing is playing
        if not p.is_playing:
            return [max(0.0, b - 0.08) for b in (self._bands or [0.0] * n)]

        t = p.elapsed * 10
        bands = []
        for i in range(n):
            # Complex wave combination for organic movement
            sig = math.sin(t * (i * 0.05 + 1)) * math.cos(t * 0.3 + i * 0.1)
            sig = abs(sig)

            # Simple kick simulation
            kick = 0.3 if (int(p.elapsed * 4) % 4 == 0 and i < n//4) else 0.0

            val = (sig * 0.7) + kick + (random.random() * 0.05)
            bands.append(min(1.0, val))

        self._bands = bands
        return bands

    def draw(self, win):
        win.erase()
        h_win, w_win = win.getmaxyx()

        # Guard for small windows
        if h_win < 2 or w_win < 4:
            return

        # CAVA uses the full width (minus potential padding)
        n_bands = w_win - 2
        bands = self._generate_bands(n_bands)

        # Initialize/Update peaks
        if len(self._peaks) != n_bands:
            self._peaks = list(bands)

        for i, v in enumerate(bands):
            if v > self._peaks[i]:
                self._peaks[i] = v
            else:
                self._peaks[i] = max(0.0, self._peaks[i] - 0.02) # Slow peak drop

        # Draw the single massive CAVA wall
        self._draw_cava_style(win, bands, h_win, w_win)

    def _draw_cava_style(self, win, bands, max_h, max_w):
        # We draw from the bottom (h-1) up to the top (0)
        h = max_h - 1

        for i, val in enumerate(bands):
            x = i + 1 # Horizontal padding of 1
            if x >= max_w - 1:
                break

            # 1. Calculate how many full terminal cells to fill
            total_units = val * h
            full_cells = int(total_units)

            # 2. Calculate which partial block to use for the very top
            # (8 steps of resolution per cell)
            partial_idx = int((total_units - full_cells) * 8)

            # 3. Draw the solid pillars
            for y_off in range(full_cells):
                try:
                    # Drawing from bottom up
                    win.addch(h - y_off, x, "█", cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass

            # 4. Draw the smooth cap
            if h - full_cells >= 0:
                try:
                    char = self.smooth_blocks[partial_idx]
                    win.addch(h - full_cells, x, char, cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass

            # 5. Draw the floating peak (Optional but classic CAVA)
            pk_val = self._peaks[i]
            pk_y = h - int(pk_val * h)
            if pk_y >= 0:
                try:
                    # Using a secondary accent color for the peaks
                    win.addch(pk_y, x, "-", cp(PAIR_ACCENT2))
                except curses.error:
                    pass
