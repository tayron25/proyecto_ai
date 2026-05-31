import time
import cv2
import numpy as np
from typing import Optional, List, Tuple

from games.base_game import BaseGame
from core.renderer import draw_button, draw_text, draw_panel, draw_wrist_cursor, WHITE, YELLOW, CYAN, GREEN
from utils.landmarks import LEFT_WRIST, RIGHT_WRIST
from utils.math_utils import landmark_to_px

# Clap detection thresholds (normalized coords)
CLAP_DIST       = 0.18   # wrists must be closer than this (normalized) to count as clap
CLAP_HOLD_SECS  = 0.4    # must hold the clap gesture this long to confirm


class _Button:
    def __init__(self, label: str, action: str, rect: Tuple[int, int, int, int]):
        self.label  = label
        self.action = action
        self.rect   = rect
        self.hovered = False

    def update(self, wrist_positions: List[Tuple[int, int]]) -> bool:
        """Returns True if any wrist is hovering over this button."""
        x, y, w, h = self.rect
        self.hovered = any(x <= p[0] <= x + w and y <= p[1] <= y + h for p in wrist_positions)
        return self.hovered

    def reset(self) -> None:
        self.hovered = False


class MainMenu(BaseGame):
    def __init__(self, frame_w: int = 640, frame_h: int = 480):
        self._w = frame_w
        self._h = frame_h
        self._next: Optional[str] = None
        self._buttons: List[_Button] = []
        self._wrists: List[Optional[Tuple[int, int]]] = [None, None]
        self._hovered_idx: int = -1
        self._clap_t: Optional[float] = None   # when clap gesture started
        self._clap_ratio: float = 0.0
        self._build()

    def _build(self) -> None:
        bw, bh = 300, 67
        cx = self._w // 2 - bw // 2
        specs = [
            ("BOXEO",     "boxing",          self._h // 2 - 120),
            ("YOGA",      "pose_challenge",  self._h // 2 -  40),
            ("AEROBICOS", "aerobics",        self._h // 2 +  40),
            ("SALIR",     "exit",            self._h // 2 + 120),
        ]
        for label, action, top_y in specs:
            self._buttons.append(_Button(label, action, (cx, top_y, bw, bh)))

    def _clapping(self, landmarks) -> bool:
        """True when both wrists are close together (normalized coords)."""
        if landmarks is None:
            return False
        lw = landmarks[LEFT_WRIST]
        rw = landmarks[RIGHT_WRIST]
        dist = abs(lw.x - rw.x)
        return dist < CLAP_DIST

    # ------------------------------------------------------------------
    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        self._wrists = [None, None]
        wrist_pts: List[Tuple[int, int]] = []
        now = time.perf_counter()

        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST],  frame_w, frame_h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], frame_w, frame_h)
            self._wrists = [lw, rw]
            wrist_pts    = [lw, rw]

        # Update hover state for all buttons
        self._hovered_idx = -1
        for i, btn in enumerate(self._buttons):
            if btn.update(wrist_pts):
                self._hovered_idx = i

        # Clap detection
        if self._clapping(landmarks) and self._hovered_idx >= 0:
            if self._clap_t is None:
                self._clap_t = now
            self._clap_ratio = min((now - self._clap_t) / CLAP_HOLD_SECS, 1.0)
            if self._clap_ratio >= 1.0:
                self._next = self._buttons[self._hovered_idx].action
        else:
            self._clap_t    = None
            self._clap_ratio = 0.0

        if not landmarks:
            for btn in self._buttons:
                btn.reset()

    def render(self, frame: np.ndarray) -> None:
        draw_panel(frame, (0, 0, self._w, self._h), color=(5, 5, 30), alpha=0.45)

        title = "CONSOLA MULTIJUEGOS"
        (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)
        draw_text(frame, title, (self._w // 2 - tw // 2, 70),
                  scale=1.1, color=YELLOW, thickness=3)

        hint = "Apunta con la muneca y aplaude para seleccionar"
        (hw, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        draw_text(frame, hint, (self._w // 2 - hw // 2, 105),
                  scale=0.5, color=WHITE, thickness=1)

        for i, btn in enumerate(self._buttons):
            if i == self._hovered_idx:
                ratio = self._clap_ratio if self._clap_ratio > 0 else 0.01
            else:
                ratio = 0.0
            draw_button(frame, btn.rect, btn.label, hover_ratio=ratio)

        for pt in self._wrists:
            draw_wrist_cursor(frame, pt, color=CYAN)

        # Clap progress indicator
        if self._clap_ratio > 0:
            bar_w = int(200 * self._clap_ratio)
            cx = self._w // 2
            cv2.rectangle(frame, (cx - 100, self._h - 30), (cx - 100 + bar_w, self._h - 14),
                          (0, 220, 80), -1)
            cv2.rectangle(frame, (cx - 100, self._h - 30), (cx + 100, self._h - 14),
                          (0, 220, 80), 2)
            draw_text(frame, "APLAUDE!", (cx - 42, self._h - 34),
                      scale=0.45, color=GREEN, thickness=1)

    def reset(self) -> None:
        self._next       = None
        self._hovered_idx = -1
        self._clap_t     = None
        self._clap_ratio  = 0.0
        for btn in self._buttons:
            btn.reset()
        self._wrists = [None, None]

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "menu"
