# auditerm

A modern, utilitarian terminal audio player for Linux with:

- **TUI file browser** — navigate your filesystem and play audio
- **Album library** — group MP3s/FLACs into albums *without* moving files
- **Live audio visualizer** — bars, wave, spectrum, dots, or off
- **Fully configurable** — colors, keybinds, UI layout, visualizer style
- **Zero bloat** — curses TUI, runs anywhere with a terminal

---

## Install (one command)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/auditerm/main/install.sh)
```

Then restart your terminal and run:

```bash
auditerm
```

---

## Manual install

```bash
git clone https://github.com/YOUR_USERNAME/auditerm
cd auditerm
pip install pygame mutagen numpy
pip install .
```

---

## Configuration

Config lives at `~/.config/auditerm/config` (created on first run).

```ini
[colors]
accent = cyan
playing_fg = green

[visualizer]
style = bars       # bars | wave | spectrum | dots | off
height = 8
mirror = true

[ui]
default_panel = split   # split | browser | library
border_style = rounded  # single | double | rounded | ascii
unicode_icons = true

[keybinds]
quit = q
play_pause = (space)
```

---

## Keybinds (defaults)

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `s` | Stop |
| `>` / `<` | Next / Prev track |
| `+` / `-` | Volume up/down |
| `b` | Toggle file browser |
| `l` | Toggle library |
| `Tab` | Switch focus (split mode) |
| `v` | Cycle visualizer style |
| `n` | New album |
| `a` | Add selected file to album |
| `q` | Quit |

---

## Supported formats

MP3, FLAC, OGG, WAV, M4A, AAC, OPUS, WMA, AIFF (anything pygame can load)

---

## Requirements

- Python 3.10+
- `pygame` — audio engine
- `mutagen` — tag reading
- `numpy` — visualizer math
- Linux terminal with UTF-8 support
