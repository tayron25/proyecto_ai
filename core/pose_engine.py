import time
import threading
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Optional


class PoseEngine:
    def __init__(self, model_path: str = 'assets/models/pose_landmarker_lite.task'):
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_ts_ms = 0

        self._lock    = threading.Lock()
        self._pending: Optional[np.ndarray] = None
        self._result:  Optional[list]       = None
        self._event   = threading.Event()
        self._stopped = False
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ── Background inference loop ─────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stopped:
            self._event.wait()
            self._event.clear()
            if self._stopped:
                break
            with self._lock:
                frame = self._pending
            if frame is None:
                continue
            rgb      = np.ascontiguousarray(frame[:, :, ::-1])
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms    = int(time.perf_counter() * 1000)
            ts_ms    = max(ts_ms, self._last_ts_ms + 1)
            self._last_ts_ms = ts_ms
            result   = self._landmarker.detect_for_video(mp_image, ts_ms)
            lm       = result.pose_landmarks[0] if result.pose_landmarks else None
            with self._lock:
                self._result = lm

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(self, frame_bgr: np.ndarray) -> None:
        """Queue a frame for inference. Non-blocking — always returns immediately."""
        with self._lock:
            self._pending = frame_bgr
        self._event.set()

    @property
    def landmarks(self) -> Optional[list]:
        """Latest inference result (may be from a previous frame)."""
        with self._lock:
            return self._result

    def process(self, frame_bgr: np.ndarray) -> Optional[list]:
        """Backward-compatible: submit + return latest landmarks immediately."""
        self.submit(frame_bgr)
        return self.landmarks

    def close(self) -> None:
        self._stopped = True
        self._event.set()
        self._thread.join(timeout=2.0)
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
