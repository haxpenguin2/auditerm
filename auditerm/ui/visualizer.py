import curses
import math
import random
from auditerm.ui.colors import cp, PAIR_BAR_FILLED, PAIR_ACCENT, PAIR_ACCENT2, PAIR_MUTED
from auditerm.config import Config
from auditerm.player import Player

class Visualizer:
    def __init__(self, player: Player, cfg: Config):
        self.player = player
        self.cfg = cfg
        self._peaks: list[float] = []
        # Smooth block characters for CAVA-style rendering
        self.smooth_blocks = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def _generate_bands(self, n: int) -> list[float]:
    p = self.player
    if not (p.is_playing):
        return [max(0, b - 0.1) for b in self._bands] # Fade out

    # We use a mix of the current timestamp and random seeds
    # to create "peaks" that feel intentional.
    t = p.elapsed * 10
    bands = []
    for i in range(n):
        # Create a "pseudo-frequency" by combining waves
        # This makes different bands react at different speeds
        sig = math.sin(t * (i * 0.1 + 1)) * math.cos(t * 0.5)
        sig = abs(sig) # Only positive bars

        # Add a "kick" every second to simulate a beat
        beat = 0.4 if (int(p.elapsed * 2) % 2 == 0) else 0.0

        val = (sig * 0.6) + beat + (random.random() * 0.1)
        bands.append(min(1.0, val))

    self._bands = bands
    return bands

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        if h < 2 or w < 10:
            return

        # 1. Split window into 3 sections: [Smooth Bars] [Mirrored Peak] [Dot Spectrum]
        sec_w = w // 3
        bands = self._generate_bands(sec_w)

        # Sync peaks
        if len(self._peaks) != len(bands):
            self._peaks = list(bands)
        for i, v in enumerate(bands):
            self._peaks[i] = max(v, self._peaks[i] - 0.05)

        # 2. Draw Sections
        self._draw_section(win, bands, 0, sec_w, h, mode="smooth")
        self._draw_section(win, bands, sec_w, sec_w, h, mode="mirror")
        self._draw_section(win, bands, sec_w * 2, w - (sec_w * 2), h, mode="dots")

    def _draw_section(self, win, bands, start_x, width, max_h, mode):
        """Draws a specific visualizer style in a horizontal slice of the window."""
        h = max_h - 1 # Leave room for window borders if necessary

        for i in range(width):
            x = start_x + i
            if i >= len(bands): break

            val = bands[i]
            pk = self._peaks[i]

            # Calculate high-res height
            # Each 'cell' is 8 units high thanks to Unicode blocks
            total_units = val * h
            full_cells = int(total_units)
            partial_unit = int((total_units - full_cells) * 8)

            if mode == "smooth":
                # Draw full blocks
                for y in range(full_cells):
                    win.addch(h - y, x, "█", cp(PAIR_BAR_FILLED))
                # Draw smooth tip
                if h - full_cells > 0:
                    win.addch(h - full_cells, x, self.smooth_blocks[partial_unit], cp(PAIR_BAR_FILLED))

            elif mode == "mirror":
                # Mirrored grows from the middle of the section height
                mid_y = h // 2
                offset = int(val * (h // 2))
                for y in range(mid_y - offset, mid_y + offset):
                    if 0 < y < max_h:
                        win.addch(y, x, "┃", cp(PAIR_ACCENT))

            elif mode == "dots":
                # Peak dots only
                pk_y = h - int(pk * (h - 1))
                if 0 < pk_y < max_h:
                    win.addch(pk_y, x, "◆", cp(PAIR_ACCENT2))

### Key Fixes Made:
#* **Vertical Inversion**: Curses `(0,0)` is top-left. To make bars grow **up**, I used `h - y`.
#* **Smooth Blocks**: Instead of just using `bar_char`, I calculate the remainder of the height and pick the corresponding Unicode block from `self.smooth_blocks`. This makes the movement look fluid rather than stepping #cell-by-cell.
#* **The "Highlight" Fix**: Notice I am using `win.addch(y, x, char, attr)`. By passing the attribute (color pair) directly into the `addch` call, it prevents the terminal from falling back to a white-background default.
#* **Modular Sections**: The `draw` function now acts as a coordinator, allowing you to mix and match styles (Smooth, Mirror, Dots) in the same view.
