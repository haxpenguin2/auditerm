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

        self._current_bands = []
        self._prev_bands = []
        self._peaks = []

        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # 🎛️ CAVA-ish tuning
        self.gravity = 0.08
        self.integral = 0.78
        self.monstercat = 0.6

    # ---------------------------
    # FAKE AUDIO ENGINE (CAVA STYLE)
    # ---------------------------
    def _generate_raw_bands(self, n_bands, t):
        raw = []

        for i in range(n_bands):
            freq_pos = i / max(1, n_bands - 1)

            # bass-heavy curve (real visualizers always bias low end)
            bass_boost = (1.0 - freq_pos) ** 2.2

            # chaotic noise energy (important for realism)
            noise = random.random() * 0.35

            # pseudo beat pulse (kick drum illusion)
            beat = max(0.0, math.sin(t * 2.8) * 0.55)

            # mid oscillation (keeps motion alive)
            wobble = math.sin(t * (1.2 + freq_pos * 3.0)) * 0.35

            val = (noise + beat + wobble) * bass_boost

            # compression so peaks feel sharper (CAVA-style punch)
            val = min(1.0, max(0.0, val)) ** 1.25

            raw.append(val)

        return raw

    # ---------------------------
    # PHYSICS LAYER (CAVA FEEL)
    # ---------------------------
    def _apply_physics(self, raw_bands):
        n = len(raw_bands)

        if not self._current_bands or len(self._current_bands) != n:
            self._current_bands = [0.0] * n
            self._prev_bands = [0.0] * n
            self._peaks = [0.0] * n

        # Monstercat-style neighbor bleed
        for i in range(1, n):
            raw_bands[i] = max(raw_bands[i], raw_bands[i - 1] * self.monstercat)

        for i in range(n - 2, -1, -1):
            raw_bands[i] = max(raw_bands[i], raw_bands[i + 1] * self.monstercat)

        # Integrate + gravity
        for i in range(n):
            target = raw_bands[i]

            if target > self._current_bands[i]:
                self._current_bands[i] = (
                    target * (1 - self.integral)
                    + self._current_bands[i] * self.integral
                )
            else:
                self._current_bands[i] = max(
                    0.0,
                    self._current_bands[i] - self.gravity
                )

            # peak hold
            if self._current_bands[i] > self._peaks[i]:
                self._peaks[i] = self._current_bands[i]
            else:
                self._peaks[i] = max(0.0, self._peaks[i] - self.gravity * 0.5)

        return self._current_bands

    # ---------------------------
    # RENDER
    # ---------------------------
    def draw(self, win):
        win.erase()

        h_win, w_win = win.getmaxyx()
        if h_win < 2 or w_win < 4:
            return

        n_bands = w_win - 2
        h = h_win - 1

        # time base
        t = self.player.elapsed * 8.0

        # generate + process audio
        raw = self._generate_raw_bands(n_bands, t)
        bands = self._apply_physics(raw)

        for i, val in enumerate(bands):
            x = i + 1

            total_units = val * h
            full_cells = int(total_units)
            partial_idx = int((total_units - full_cells) * 8)

            # main bar
            for y in range(full_cells):
                try:
                    win.addch(h - y, x, "█", cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass

            # partial top cap
            if full_cells < h:
                try:
                    win.addch(
                        h - full_cells,
                        x,
                        self.smooth_blocks[partial_idx],
                        cp(PAIR_BAR_FILLED),
                    )
                except curses.error:
                    pass

            # peak marker
            peak_y = h - int(self._peaks[i] * h)
            if 0 <= peak_y < h:
                try:
                    win.addch(peak_y, x, "─", cp(PAIR_ACCENT2))
                except curses.error:
                    pass
