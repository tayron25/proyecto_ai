import time
import cv2
import numpy as np
from typing import Optional, List, Tuple

from games.base_game import BaseGame
from core.renderer import (
    draw_button, draw_text, draw_panel, draw_wrist_cursor,
    BG, BOX_CLR, YOGA_CLR, AERO_CLR, INK, INK_DIM, LINE, GREEN,
)
from utils.landmarks import LEFT_WRIST, RIGHT_WRIST
from utils.math_utils import landmark_to_px

CLAP_DIST      = 0.18
CLAP_HOLD_SECS = 0.4


class _Button:
    def __init__(self, label: str, action: str, rect: Tuple[int, int, int, int],
                 color: Tuple = LINE):
        self.label   = label
        self.action  = action
        self.rect    = rect
        self.color   = color
        self.hovered = False

    def update(self, wrist_positions: List[Tuple[int, int]]) -> bool:
        x, y, w, h = self.rect
        self.hovered = any(x <= p[0] <= x + w and y <= p[1] <= y + h
                           for p in wrist_positions)
        return self.hovered

    def reset(self) -> None:
        self.hovered = False


class MainMenu(BaseGame):
    def __init__(self, frame_w: int = 820, frame_h: int = 820):
        self._w = frame_w
        self._h = frame_h
        self._next: Optional[str] = None
        self._buttons: List[_Button] = []
        self._wrists: List[Optional[Tuple[int, int]]] = [None, None]
        self._hovered_idx: int = -1
        self._clap_t: Optional[float] = None
        self._clap_ratio: float = 0.0
        self._build()

    def _build(self) -> None:
        # Proportional card sizing for any square canvas
        cw      = int(self._w * 0.24)   # ~197 px
        ch      = int(self._h * 0.24)   # ~197 px
        spacing = (self._w - 3 * cw) // 4
        card_y  = (self._h - ch) // 2

        specs = [
            ("BOXEO",     "boxing",        spacing,                BOX_CLR),
            ("YOGA",      "pose_challenge", spacing * 2 + cw,      YOGA_CLR),
            ("AEROBICOS", "aerobics",       spacing * 3 + cw * 2,  AERO_CLR),
        ]
        for label, action, x, color in specs:
            self._buttons.append(_Button(label, action, (x, card_y, cw, ch), color))

        # Exit — small button, bottom center
        self._buttons.append(
            _Button("SALIR", "exit",
                    (self._w // 2 - 80, self._h - 70, 160, 44), LINE)
        )

    def _clapping(self, landmarks) -> bool:
        if landmarks is None:
            return False
        lw = landmarks[LEFT_WRIST]
        rw = landmarks[RIGHT_WRIST]
        return abs(lw.x - rw.x) < CLAP_DIST

    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        self._wrists  = [None, None]
        wrist_pts: List[Tuple[int, int]] = []
        now = time.perf_counter()

        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST],  frame_w, frame_h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], frame_w, frame_h)
            self._wrists = [lw, rw]
            wrist_pts    = [lw, rw]

        self._hovered_idx = -1
        for i, btn in enumerate(self._buttons):
            if btn.update(wrist_pts):
                self._hovered_idx = i

        if self._clapping(landmarks) and self._hovered_idx >= 0:
            if self._clap_t is None:
                self._clap_t = now
            self._clap_ratio = min((now - self._clap_t) / CLAP_HOLD_SECS, 1.0)
            if self._clap_ratio >= 1.0:
                self._next = self._buttons[self._hovered_idx].action
        else:
            self._clap_t     = None
            self._clap_ratio = 0.0

        if not landmarks:
            for btn in self._buttons:
                btn.reset()

    def render(self, frame: np.ndarray) -> None:
        draw_panel(frame, (0, 0, self._w, self._h), color=BG, alpha=0.55)

        # Title
        title = "FLOWBOX"
        (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
        draw_text(frame, title, (self._w // 2 - tw // 2, int(self._h * 0.11)),
                  scale=1.5, color=INK, thickness=3)

        hint = "Muneca + aplaude para seleccionar"
        (hw, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        draw_text(frame, hint, (self._w // 2 - hw // 2, int(self._h * 0.19)),
                  scale=0.5, color=INK_DIM, thickness=1)

        # Mode cards (first 3 buttons)
        subtitles = ["PUNETAZOS", "POSES", "MOVIMIENTO"]
        for i, btn in enumerate(self._buttons[:3]):
            ratio = self._clap_ratio if i == self._hovered_idx and self._clap_ratio > 0 else 0.0
            draw_button(frame, btn.rect, btn.label,
                        hover_ratio=ratio,
                        base_color=btn.color,
                        hover_color=btn.color)
            x, y, w, h = btn.rect
            (sw, _), _ = cv2.getTextSize(subtitles[i], cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            draw_text(frame, subtitles[i],
                      (x + (w - sw) // 2, y + h - 28),
                      scale=0.42, color=btn.color, thickness=1)

        # Exit button
        exit_btn = self._buttons[3]
        ratio = self._clap_ratio if self._hovered_idx == 3 and self._clap_ratio > 0 else 0.0
        draw_button(frame, exit_btn.rect, exit_btn.label,
                    hover_ratio=ratio, base_color=LINE, hover_color=LINE)

        # Wrist cursors
        for pt in self._wrists:
            draw_wrist_cursor(frame, pt)

        # Clap progress bar
        if self._clap_ratio > 0:
            bar_w = int(240 * self._clap_ratio)
            cx    = self._w // 2
            cv2.rectangle(frame, (cx - 120, self._h - 28),
                          (cx - 120 + bar_w, self._h - 14), GREEN, -1)
            cv2.rectangle(frame, (cx - 120, self._h - 28),
                          (cx + 120, self._h - 14), LINE, 2)
            draw_text(frame, "APLAUDE!", (cx - 44, self._h - 32),
                      scale=0.44, color=GREEN, thickness=1)

    def reset(self) -> None:
        self._next        = None
        self._hovered_idx = -1
        self._clap_t      = None
        self._clap_ratio  = 0.0
        for btn in self._buttons:
            btn.reset()
        self._wrists = [None, None]

    def get_video_frame(self):
        return None

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "menu"
