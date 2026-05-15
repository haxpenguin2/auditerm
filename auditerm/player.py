"""
Audio playback engine using pygame.mixer with raw sample exposure for FFT.
"""

import threading
import time
from pathlib import Path
import numpy as np

try:
    import pygame
    # Initialize with specific buffer for lower latency
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
    """Helper to format seconds into M:SS or H:MM:SS."""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class Track:
    """Metadata for a single audio file."""
    def __init__(self, path: str):
        self.path = str(path)
        self.filename = Path(path).name
        self.title = self.filename
        self.artist = "Unknown"
        self.album = "Unknown"
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
        """Returns the track duration as a formatted string."""
        return _fmt_time(self.duration)


class Player:
    """
    Stateful audio player.
    Exposes raw_samples for the visualizer and full state for the UI.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._track: Track | None = None
        self._queue: list[Track] = []
        self._queue_index: int = -1
        self._playing = False
        self._paused = False
        self._volume = 0.8
        self._start_time = 0.0
        self._elapsed_at_pause = 0.0
        self._on_track_end = None

        # Buffer for the FFT visualizer
        self.raw_samples = np.array([], dtype=np.float32)

        self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self._monitor_thread.start()

    # ── Queue Management ──────────────────────────────────────────

    def set_queue(self, tracks: list[Track], index: int = 0):
        with self._lock:
            self._queue = tracks
            self._queue_index = index

    # ── Playback Controls ─────────────────────────────────────────

    def play(self, track: Track | None = None):
        if not PYGAME_OK:
            return
        with self._lock:
            if track:
                self._track = track
            if self._track is None:
                return
            try:
                # Load and play
                pygame.mixer.music.load(self._track.path)
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play()

                # Extract raw samples for FFT analysis in visualizer.py
                sound = pygame.mixer.Sound(self._track.path)
                samples = pygame.sndarray.array(sound)
                # Average stereo to mono for visualizer processing
                if len(samples.shape) > 1:
                    self.raw_samples = samples.mean(axis=1)
                else:
                    self.raw_samples = samples

                self._playing = True
                self._paused = False
                self._start_time = time.time()
                self._elapsed_at_pause = 0.0
            except Exception:
                self._playing = False

    def pause(self):
        if not PYGAME_OK or not self._playing:
            return
        with self._lock:
            if self._paused:
                pygame.mixer.music.unpause()
                self._start_time = time.time()
                self._paused = False
            else:
                pygame.mixer.music.pause()
                self._elapsed_at_pause += time.time() - self._start_time
                self._paused = True

    def stop(self):
        if not PYGAME_OK:
            return
        with self._lock:
            pygame.mixer.music.stop()
            self._playing = False
            self._paused = False
            self._elapsed_at_pause = 0.0

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

    # ── Getters / Properties for UI (layout.py, controls.py) ───────

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
        """Percentage of track played (0.0 to 1.0)."""
        if self._track and self._track.duration > 0:
            return min(1.0, self.elapsed / self._track.duration)
        return 0.0

    def elapsed_str(self) -> str:
        return _fmt_time(self.elapsed)

    def on_track_end(self, cb):
        self._on_track_end = cb

    # ── Background Thread ─────────────────────────────────────────

    def _monitor(self):
        """Monitors pygame events to auto-advance the queue."""
        while True:
            time.sleep(0.25)
            if not PYGAME_OK:
                continue
            with self._lock:
                playing = self._playing
                paused = self._paused
            if playing and not paused:
                if not pygame.mixer.music.get_busy():
                    # Track ended naturally
                    with self._lock:
                        self._playing = False
                        self._elapsed_at_pause = 0.0
                    if self._on_track_end:
                        self._on_track_end()
                    else:
                        self.next_track()
