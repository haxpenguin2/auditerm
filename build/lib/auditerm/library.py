"""
Album/library management.
Albums are stored in ~/.config/auditerm/library.json
They are logical groupings — file paths are stored, not moved.
"""

import json
from pathlib import Path
from auditerm.player import Track

LIBRARY_FILE = Path.home() / ".config" / "auditerm" / "library.json"


class Album:
    def __init__(self, name: str, paths: list[str] | None = None):
        self.name = name
        self.paths: list[str] = paths or []

    def add(self, path: str):
        if path not in self.paths:
            self.paths.append(path)

    def remove(self, path: str):
        self.paths = [p for p in self.paths if p != path]

    def tracks(self) -> list[Track]:
        return [Track(p) for p in self.paths if Path(p).exists()]

    def to_dict(self):
        return {"name": self.name, "paths": self.paths}

    @staticmethod
    def from_dict(d: dict) -> "Album":
        return Album(d["name"], d.get("paths", []))


class Library:
    def __init__(self):
        self.albums: dict[str, Album] = {}
        self._load()

    def _load(self):
        if LIBRARY_FILE.exists():
            try:
                data = json.loads(LIBRARY_FILE.read_text())
                for entry in data.get("albums", []):
                    a = Album.from_dict(entry)
                    self.albums[a.name] = a
            except Exception:
                pass

    def save(self):
        LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"albums": [a.to_dict() for a in self.albums.values()]}
        LIBRARY_FILE.write_text(json.dumps(data, indent=2))

    def new_album(self, name: str) -> Album:
        a = Album(name)
        self.albums[name] = a
        self.save()
        return a

    def delete_album(self, name: str):
        self.albums.pop(name, None)
        self.save()

    def rename_album(self, old: str, new: str):
        if old in self.albums:
            a = self.albums.pop(old)
            a.name = new
            self.albums[new] = a
            self.save()

    def add_to_album(self, album_name: str, path: str):
        if album_name not in self.albums:
            self.new_album(album_name)
        self.albums[album_name].add(path)
        self.save()

    def album_names(self) -> list[str]:
        return sorted(self.albums.keys())
