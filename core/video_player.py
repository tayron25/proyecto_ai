import time
from typing import Optional

import cv2
import numpy as np


class VideoPlayer:
    """Preloads all video frames into RAM on load(); read_frame() is a pure list index."""

    def __init__(self, path: str, panel_w: int = 270, panel_h: int = 480) -> None:
        self._path    = path
        self._pw      = panel_w
        self._ph      = panel_h
        self._frames: list[np.ndarray] = []
        self._fps     = 30.0
        self._total   = 0
        self._start_t = 0.0
        self._started = False
        self._done    = False

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> bool:
        """Decode every frame into RAM. Returns True if at least one frame loaded."""
        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        self._fps = fps if fps > 0 else 30.0

        frames: list[np.ndarray] = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame.shape[0] != self._ph or frame.shape[1] != self._pw:
                frame = cv2.resize(frame, (self._pw, self._ph))
            frames.append(frame)
        cap.release()

        self._frames = frames
        self._total  = len(frames)
        self._done   = False
        return self._total > 0

    def start(self) -> None:
        """Mark playback start time. Call once after load()."""
        self._start_t = time.perf_counter()
        self._started = True
        self._done    = False

    def stop(self) -> None:
        """Free preloaded frames from RAM."""
        self._frames  = []
        self._total   = 0
        self._started = False
        self._done    = False

    @property
    def current_time(self) -> float:
        """Seconds elapsed since start()."""
        if not self._started:
            return 0.0
        return time.perf_counter() - self._start_t

    @property
    def is_done(self) -> bool:
        return self._done

    def read_frame(self) -> Optional[np.ndarray]:
        """Return the frame matching current wall-clock time. Zero disk I/O."""
        if not self._frames or self._done:
            return None

        idx = int(self.current_time * self._fps)
        if idx >= self._total:
            self._done = True
            return None

        return self._frames[idx]
