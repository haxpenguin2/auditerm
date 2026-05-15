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

        # CAVA-like tuning
        self.gravity = 0.10
        self.integral = 0.80
        self.monstercat = 0.6

        # 🔇 IMPORTANT: silence cutoff
        self.silence_threshold = 0.02

    # ---------------------------
    # REALISTIC "AUDIO INPUT" STUB
    # ---------------------------
    # THIS is where FFT would go in a real system
    def _get_audio_bands(self, n_bands, t):
        """
        IMPORTANT:
        Replace this with REAL FFT or system audio input.
        Right now we simulate BUT with silence capability.
        """

        # simulate "no audio playing"
        if self.player is None or getattr(self.player, "paused", False):
            return [0.0] * n_bands

        # fake but structured energy (only for demo mode)
        raw = []
        for i in range(n_bands):
            freq = i / max(1, n_bands - 1)

            # structured energy (not random noise anymore)
            bass = (1.0 - freq) ** 2.0

            # beat pulse
            beat = max(0.0, math.sin(t * 2.5)) * 0.6

            val = beat * bass

            raw.append(val)

        return raw

    # ---------------------------
    # PHYSICS (CAVA STYLE)
    # ---------------------------
    def _apply_physics(self, raw):
        n = len(raw)

        if not self._current_bands or len(self._current_bands) != n:
            self._current_bands = [0.0] * n
            self._peaks = [0.0] * n

        # 🧠 SILENCE GATE (KEY FIX)
        avg_energy = sum(raw) / n if n else 0.0
        if avg_energy < self.silence_threshold:
            raw = [0.0] * n

        # monstercat smoothing
        for i in range(1, n):
            raw[i] = max(raw[i], raw[i - 1] * self.monstercat)

        for i in range(n - 2, -1, -1):
            raw[i] = max(raw[i], raw[i + 1] * self.monstercat)

        # integrate + gravity
        for i in range(n):
            target = raw[i]

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
    # DRAW
    # ---------------------------
    def draw(self, win):
        win.erase()

        h_win, w_win = win.getmaxyx()
        if h_win < 2 or w_win < 4:
            return

        n_bands = w_win - 2
        h = h_win - 1

        t = self.player.elapsed * 8.0

        raw = self._get_audio_bands(n_bands, t)
        bands = self._apply_physics(raw)

        for i, val in enumerate(bands):
            x = i + 1

            total = val * h
            full = int(total)
            partial = int((total - full) * 8)

            # bar
            for y in range(full):
                try:
                    win.addch(h - y, x, "█", cp(PAIR_BAR_FILLED))
                except curses.error:
                    pass

            # cap
            if full < h:
                try:
                    win.addch(
                        h - full,
                        x,
                        self.smooth_blocks[partial],
                        cp(PAIR_BAR_FILLED),
                    )
                except curses.error:
                    pass

            # peak
            py = h - int(self._peaks[i] * h)
            if 0 <= py < h:
                try:
                    win.addch(py, x, "─", cp(PAIR_ACCENT2))
                except curses.error:
                    pass
