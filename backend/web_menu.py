import time
from dataclasses import dataclass
from typing import Optional

from games.menu import CLAP_DIST, CLAP_HOLD_SECS
from utils.landmarks import LEFT_WRIST, RIGHT_WRIST
from utils.math_utils import landmark_to_px


@dataclass
class MenuButton:
    label: str
    action: str
    rect: tuple[int, int, int, int]
    hovered: bool = False

    def update(self, wrist_positions: list[tuple[int, int]]) -> bool:
        x, y, w, h = self.rect
        self.hovered = any(x <= px <= x + w and y <= py <= y + h for px, py in wrist_positions)
        return self.hovered

    def reset(self) -> None:
        self.hovered = False


class WebMenu:
    def __init__(self, frame_w: int = 640, frame_h: int = 480) -> None:
        self._w = frame_w
        self._h = frame_h
        self._buttons: list[MenuButton] = []
        self._wrists: list[Optional[tuple[int, int]]] = [None, None]
        self._hovered_idx = -1
        self._clap_t: Optional[float] = None
        self._clap_ratio = 0.0
        self._next: Optional[str] = None
        self._build()

    def _build(self) -> None:
        bw, bh = 180, 130
        y = 326
        specs = [
            ("BOX", "boxing", 28, y),
            ("YOGA", "pose_challenge", 230, y),
            ("AEROBICO", "aerobics", 432, y),
        ]
        self._buttons = [MenuButton(label, action, (left_x, top_y, bw, bh)) for label, action, left_x, top_y in specs]

    def _clapping(self, landmarks: Optional[list]) -> bool:
        if landmarks is None:
            return False
        lw = landmarks[LEFT_WRIST]
        rw = landmarks[RIGHT_WRIST]
        dx = lw.x - rw.x
        dy = lw.y - rw.y
        return (dx * dx + dy * dy) < (CLAP_DIST * CLAP_DIST)

    def update(self, landmarks: Optional[list]) -> None:
        self._wrists = [None, None]
        wrist_pts: list[tuple[int, int]] = []
        now = time.perf_counter()

        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST], self._w, self._h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], self._w, self._h)
            self._wrists = [lw, rw]
            wrist_pts = [lw, rw]

        previous_hovered_idx = self._hovered_idx
        self._hovered_idx = -1
        for idx, button in enumerate(self._buttons):
            if button.update(wrist_pts):
                self._hovered_idx = idx

        if self._hovered_idx != previous_hovered_idx:
            self._clap_t = None
            self._clap_ratio = 0.0

        if self._clapping(landmarks) and self._hovered_idx >= 0:
            if self._clap_t is None:
                self._clap_t = now
            self._clap_ratio = min((now - self._clap_t) / CLAP_HOLD_SECS, 1.0)
            if self._clap_ratio >= 1.0:
                self._next = self._buttons[self._hovered_idx].action
        else:
            self._clap_t = None
            self._clap_ratio = 0.0

        if not landmarks:
            for button in self._buttons:
                button.reset()

    def reset(self) -> None:
        self._next = None
        self._hovered_idx = -1
        self._clap_t = None
        self._clap_ratio = 0.0
        self._wrists = [None, None]
        for button in self._buttons:
            button.reset()

    def consume_next_state(self) -> Optional[str]:
        next_state = self._next
        if next_state is not None:
            self.reset()
        return next_state

    def to_json(self) -> dict:
        return {
            "title": "CONSOLA MULTIJUEGOS",
            "hint": "Apunta con la muneca y aplaude para seleccionar",
            "clapRatio": self._clap_ratio,
            "hoveredIndex": self._hovered_idx,
            "buttons": [
                {
                    "label": button.label,
                    "action": button.action,
                    "rect": button.rect,
                    "hovered": button.hovered,
                }
                for button in self._buttons
            ],
            "wrists": [
                {"x": wrist[0], "y": wrist[1]}
                for wrist in self._wrists
                if wrist is not None
            ],
        }
