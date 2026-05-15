"""
auditerm — terminal audio player
Entry point. Initializes curses, config, player, and runs the layout.
"""

import curses
import sys
import os
from pathlib import Path


def main():
    # Ensure config dir exists and write default config
    from auditerm.config import Config
    cfg = Config()
    cfg.write_default()

    from auditerm.player import Player, PYGAME_OK, MUTAGEN_OK
    from auditerm.library import Library
    from auditerm.ui.layout import Layout

    if not PYGAME_OK:
        print("Error: pygame is required. Install with: pip install pygame", file=sys.stderr)
        sys.exit(1)

    player = Player()
    library = Library()

    def _run(stdscr):
        layout = Layout(stdscr, player, library, cfg)
        layout.run()

    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()


if __name__ == "__main__":
    main()
