"""
Audio playback engine using pygame.mixer with raw sample exposure for FFT.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

try:
    import pygame
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.init()
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False

try:
    from mutagen import File as MutagenFile
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class Track:
    def __init__(self, path: str):
        self.path     = str(path)
        self.filename = Path(path).name
        self.title    = self.filename
        self.artist   = "Unknown"
        self.album    = "Unknown"
        self.duration = 0.0
        self._load_tags()

    def _load_tags(self):
        if not MUTAGEN_OK:
            return
        try:
            tags = MutagenFile(self.path, easy=True)
            if tags is None:
                return
            self.title  = str(tags.get("title",  [self.filename])[0])
            self.artist = str(tags.get("artist", ["Unknown"])[0])
            self.album  = str(tags.get("album",  ["Unknown"])[0])
            if hasattr(tags, "info") and hasattr(tags.info, "length"):
                self.duration = tags.info.length
        except Exception:
            pass

    def display_name(self) -> str:
        if self.title != self.filename:
            return f"{self.artist} — {self.title}"
        return self.filename

    def duration_str(self) -> str:
        return _fmt_time(self.duration)


class Player:
    def __init__(self):
        self._lock                    = threading.Lock()
        self._track: Track | None     = None
        self._queue: list[Track]      = []
        self._queue_index: int        = -1
        self._playing                 = False
        self._paused                  = False
        self._volume                  = 0.8
        self._start_time              = 0.0
        self._elapsed_at_pause        = 0.0
        self._on_track_end            = None

        # Raw mono float32 samples for the FFT visualizer.
        # None  = no track / not yet loaded
        # empty = load failed (visualizer shows nothing)
        self.raw_samples: np.ndarray | None = None

        # Generation counter: incremented on every play() call.
        # Background load thread checks its own generation against current;
        # if they differ, another track started — discard the result.
        self._load_gen: int = 0

        self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self._monitor_thread.start()

    # ── Queue ─────────────────────────────────────────────────────

    def set_queue(self, tracks: list[Track], index: int = 0):
        with self._lock:
            self._queue       = tracks
            self._queue_index = index

    def add_to_queue(self, track: Track):
        with self._lock:
            self._queue.append(track)

    def clear_queue(self):
        with self._lock:
            self._queue.clear()
            self._queue_index = -1

    # ── Playback ──────────────────────────────────────────────────

    def play(self, track: Track | None = None):
        if not PYGAME_OK:
            return
        with self._lock:
            if track:
                self._track = track
            if self._track is None:
                return
            try:
                pygame.mixer.music.load(self._track.path)
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play()
                self._playing          = True
                self._paused           = False
                self._start_time       = time.time()
                self._elapsed_at_pause = 0.0
            except Exception:
                self._playing = False
                return

            # Bump generation so any in-flight load thread for the previous
            # track knows to discard its result
            self._load_gen += 1
            my_gen = self._load_gen
            path   = self._track.path

        # Clear samples immediately so the visualizer shows nothing
        # until the new track's samples arrive
        self.raw_samples = None
        threading.Thread(
            target=self._load_samples,
            args=(path, my_gen),
            daemon=True,
        ).start()

    def _load_samples(self, path: str, gen: int):
        """
        Decode the audio file to raw PCM samples in a background thread.
        Discards the result if a newer track has started playing (gen check).
        """
        try:
            sound   = pygame.mixer.Sound(path)
            samples = pygame.sndarray.array(sound)

            # Stereo → mono
            mono = samples.mean(axis=1).astype(np.float32) \
                   if samples.ndim > 1 \
                   else samples.astype(np.float32)

            # Normalize integer types to [-1.0, 1.0]
            if np.issubdtype(samples.dtype, np.integer):
                mono /= float(np.iinfo(samples.dtype).max)

        except Exception:
            mono = np.array([], dtype=np.float32)

        # Only store if we're still on the same track
        with self._lock:
            if self._load_gen == gen:
                self.raw_samples = mono

    def pause(self):
        if not PYGAME_OK or not self._playing:
            return
        with self._lock:
            if self._paused:
                pygame.mixer.music.unpause()
                self._start_time = time.time()
                self._paused     = False
            else:
                pygame.mixer.music.pause()
                self._elapsed_at_pause += time.time() - self._start_time
                self._paused = True

    def stop(self):
        if not PYGAME_OK:
            return
        with self._lock:
            pygame.mixer.music.stop()
            self._playing          = False
            self._paused           = False
            self._elapsed_at_pause = 0.0
            self._load_gen        += 1   # cancel any pending load
        self.raw_samples = None

    def next_track(self) -> bool:
        with self._lock:
            if not self._queue:
                return False
            self._queue_index = (self._queue_index + 1) % len(self._queue)
            track = self._queue[self._queue_index]
        self.play(track)
        return True

    def prev_track(self) -> bool:
        with self._lock:
            if not self._queue:
                return False
            self._queue_index = (self._queue_index - 1) % len(self._queue)
            track = self._queue[self._queue_index]
        self.play(track)
        return True

    def set_volume(self, v: float):
        self._volume = max(0.0, min(1.0, v))
        if PYGAME_OK:
            pygame.mixer.music.set_volume(self._volume)

    def volume_up(self, step: float = 0.05):
        self.set_volume(self._volume + step)

    def volume_down(self, step: float = 0.05):
        self.set_volume(self._volume - step)

    # ── Properties ───────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_track(self) -> Track | None:
        return self._track

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def elapsed(self) -> float:
        if not self._playing:
            return 0.0
        if self._paused:
            return self._elapsed_at_pause
        return self._elapsed_at_pause + (time.time() - self._start_time)

    @property
    def progress(self) -> float:
        if self._track and self._track.duration > 0:
            return min(1.0, self.elapsed / self._track.duration)
        return 0.0

    def elapsed_str(self) -> str:
        return _fmt_time(self.elapsed)

    def on_track_end(self, cb):
        self._on_track_end = cb

    # ── Monitor thread ────────────────────────────────────────────

    def _monitor(self):
        """Detect natural track end and fire the callback."""
        while True:
            time.sleep(0.25)
            if not PYGAME_OK:
                continue
            with self._lock:
                playing = self._playing
                paused  = self._paused
            if playing and not paused:
                if not pygame.mixer.music.get_busy():
                    with self._lock:
                        self._playing          = False
                        self._elapsed_at_pause = 0.0
                    if self._on_track_end:
                        self._on_track_end()
