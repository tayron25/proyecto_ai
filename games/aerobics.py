import time
import cv2
import numpy as np
from typing import Optional, Tuple

from games.base_game import BaseGame
from core.renderer import (
    draw_text, draw_progress_bar, draw_panel,
    WHITE, GREEN, RED, YELLOW, CYAN,
)
from core.video_player import VideoPlayer
from utils.landmarks import (
    NOSE,
    LEFT_SHOULDER,  RIGHT_SHOULDER,
    LEFT_ELBOW,     RIGHT_ELBOW,
    LEFT_WRIST,     RIGHT_WRIST,
    LEFT_HIP,       RIGHT_HIP,
    LEFT_KNEE,      RIGHT_KNEE,
    LEFT_ANKLE,     RIGHT_ANKLE,
)
from utils.math_utils import calc_angle

# ── Video and module timing ───────────────────────────────────────────────────
AEROBICS_VIDEO    = "assets/videos/aerobicos/aerobicos1.mp4"
MODULE_TIMESTAMPS = [8.0, 23.0, 38.0, 53.0]   # video time when each module activates
MODULE_TARGET_REPS = [15, 8, 16, 15]           # goal reps per module (display only)

TRANSITION_SECS = 2.0
SUCCESS_FLASH   = 0.6


# ── Data extraction ───────────────────────────────────────────────────────────
def _extract_data(landmarks: list, fw: int, fh: int) -> dict:
    if not landmarks or len(landmarks) < 33:
        return {}

    def pt(idx: int) -> Tuple[float, float]:
        lm = landmarks[idx]
        return (lm.x * fw, lm.y * fh)

    try:
        return {
            "left_elbow":      calc_angle(pt(LEFT_SHOULDER),  pt(LEFT_ELBOW),   pt(LEFT_WRIST)),
            "right_elbow":     calc_angle(pt(RIGHT_SHOULDER), pt(RIGHT_ELBOW),  pt(RIGHT_WRIST)),
            "left_hip_angle":  calc_angle(pt(LEFT_SHOULDER),  pt(LEFT_HIP),     pt(LEFT_KNEE)),
            "right_hip_angle": calc_angle(pt(RIGHT_SHOULDER), pt(RIGHT_HIP),    pt(RIGHT_KNEE)),
            "nose_y":  landmarks[NOSE].y,
            "ls_y":    landmarks[LEFT_SHOULDER].y,
            "rs_y":    landmarks[RIGHT_SHOULDER].y,
            "lw_y":    landmarks[LEFT_WRIST].y,
            "rw_y":    landmarks[RIGHT_WRIST].y,
            "ls_x":    landmarks[LEFT_SHOULDER].x,
            "rs_x":    landmarks[RIGHT_SHOULDER].x,
            "lw_x":    landmarks[LEFT_WRIST].x,
            "rw_x":    landmarks[RIGHT_WRIST].x,
            "la_x":    landmarks[LEFT_ANKLE].x,
            "ra_x":    landmarks[RIGHT_ANKLE].x,
            "lh_x":    landmarks[LEFT_HIP].x,
            "rh_x":    landmarks[RIGHT_HIP].x,
        }
    except Exception:
        return {}


# ── Checkpoint functions ──────────────────────────────────────────────────────
def _check_mod1(data: dict) -> Optional[str]:
    if not data:
        return None
    d_wr = abs(data["lw_x"] - data["rw_x"])
    d_sh = abs(data["ls_x"] - data["rs_x"])
    if d_wr < d_sh:
        return "CLOSED"
    if d_wr > d_sh:
        return "OPEN"
    return None


def _form_ok_mod1(data: dict) -> bool:
    if not data:
        return False
    return (70 <= data.get("left_elbow",  0) <= 110
            and 70 <= data.get("right_elbow", 0) <= 110)


def _check_mod2(data: dict) -> Optional[str]:
    if not data:
        return None
    if data["lw_y"] > data["ls_y"] and data["rw_y"] < data["nose_y"]:
        return "RIGHT_HIGH"
    if data["lw_y"] < data["nose_y"] and data["rw_y"] > data["rs_y"]:
        return "LEFT_HIGH"
    return None


def _check_mod3(data: dict) -> Optional[str]:
    if not data:
        return None
    if data["lw_y"] < data["nose_y"] and data["rw_y"] < data["nose_y"]:
        return "ARMS_UP"
    if (data["lw_y"] > data["ls_y"] and data["rw_y"] > data["rs_y"]
            and data.get("left_hip_angle", 180) < 130):
        return "PULL_L"
    if (data["lw_y"] > data["ls_y"] and data["rw_y"] > data["rs_y"]
            and data.get("right_hip_angle", 180) < 130):
        return "PULL_R"
    return None


def _check_mod4(data: dict) -> Optional[str]:
    if not data:
        return None
    d_wr = abs(data["lw_x"] - data["rw_x"])
    d_sh = abs(data["ls_x"] - data["rs_x"])
    d_an = abs(data["la_x"] - data["ra_x"])
    d_hp = abs(data["lh_x"] - data["rh_x"])
    if d_wr < d_sh and d_an <= d_hp:
        return "CLOSED"
    if d_wr > d_sh * 1.5 and d_an > d_hp * 1.2:
        return "OPEN"
    return None


# ── Module definitions ────────────────────────────────────────────────────────
AEROBIC_MODULES = [
    {
        "name":        "Bombeo L",
        "description": "Codos a 90, abre y cierra brazos",
        "check":       _check_mod1,
        "form_check":  _form_ok_mod1,
        "transitions": {"CLOSED": {"OPEN"}, "OPEN": {"CLOSED"}},
        "score_on":    {"OPEN", "CLOSED"},
        "labels":      {"CLOSED": "Brazos Cerrados", "OPEN": "Brazos Abiertos"},
    },
    {
        "name":        "Alcance Overhead",
        "description": "Alterna brazo der/izq arriba",
        "check":       _check_mod2,
        "form_check":  None,
        "transitions": {"RIGHT_HIGH": {"LEFT_HIGH"}, "LEFT_HIGH": {"RIGHT_HIGH"}},
        "score_on":    {"RIGHT_HIGH", "LEFT_HIGH"},
        "labels":      {"RIGHT_HIGH": "Der Arriba", "LEFT_HIGH": "Izq Arriba"},
    },
    {
        "name":        "Jalon con Rodilla",
        "description": "Brazos arriba, baja con rodilla",
        "check":       _check_mod3,
        "form_check":  None,
        "transitions": {
            "ARMS_UP": {"PULL_L", "PULL_R"},
            "PULL_L":  {"ARMS_UP"},
            "PULL_R":  {"ARMS_UP"},
        },
        "score_on": {"PULL_L", "PULL_R"},
        "labels":   {"ARMS_UP": "Brazos Arriba", "PULL_L": "Jalon Izq", "PULL_R": "Jalon Der"},
    },
    {
        "name":        "Paso Lateral",
        "description": "Cierra y abre brazos y piernas",
        "check":       _check_mod4,
        "form_check":  None,
        "transitions": {"CLOSED": {"OPEN"}, "OPEN": {"CLOSED"}},
        "score_on":    {"OPEN", "CLOSED"},
        "labels":      {"CLOSED": "Cerrado", "OPEN": "Abierto"},
    },
]


# ── Game class ────────────────────────────────────────────────────────────────
class AerobicsGame(BaseGame):
    def __init__(self, frame_w: int = 640, frame_h: int = 480):
        self._w    = frame_w
        self._h    = frame_h
        self._video: Optional[VideoPlayer] = None
        self._next: Optional[str] = None
        self.reset()

    def reset(self) -> None:
        self._next       = None
        self._mod_idx    = 0
        self._reps       = 0
        self._score      = 0
        self._last_cp:   Optional[str] = None
        self._last_cp_t: float = 0.0
        self._cur_cp:    Optional[str] = None
        self._flash_t:   float = 0.0
        self._data:      dict  = {}
        if self._video:
            self._video.stop()
        self._video = VideoPlayer(AEROBICS_VIDEO)
        if not self._video.load():
            self._video = None
        else:
            self._video.start()

    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        if self._next:
            return

        # Video-driven module activation
        vt = self._video.current_time if self._video else 0.0
        new_mod = sum(1 for t in MODULE_TIMESTAMPS if vt >= t) - 1
        new_mod = max(0, min(new_mod, len(AEROBIC_MODULES) - 1))
        if new_mod != self._mod_idx:
            self._mod_idx  = new_mod
            self._reps     = 0
            self._last_cp  = None
            self._cur_cp   = None

        # End of video → back to menu
        if self._video and self._video.is_done:
            self._next = "menu"
            return

        now        = time.perf_counter()
        self._data = _extract_data(landmarks, frame_w, frame_h) if landmarks else {}

        mod    = AEROBIC_MODULES[self._mod_idx]
        cp_now = mod["check"](self._data)
        self._cur_cp = cp_now

        if cp_now is not None and cp_now == self._last_cp:
            self._last_cp_t = now
        elif cp_now is not None:
            if (self._last_cp is not None
                    and now - self._last_cp_t <= TRANSITION_SECS
                    and cp_now in mod["transitions"].get(self._last_cp, set())):
                if cp_now in mod["score_on"]:
                    self._reps  += 1
                    self._score += 10
                    self._flash_t = now
            self._last_cp   = cp_now
            self._last_cp_t = now
        else:
            if self._last_cp is not None and now - self._last_cp_t > TRANSITION_SECS:
                self._last_cp   = None
                self._last_cp_t = 0.0

    def render(self, frame: np.ndarray) -> None:
        if self._mod_idx >= len(AEROBIC_MODULES):
            return

        now      = time.perf_counter()
        mod      = AEROBIC_MODULES[self._mod_idx]
        panel_w  = 220
        target   = MODULE_TARGET_REPS[self._mod_idx]
        draw_panel(frame, (0, 0, panel_w, self._h), color=(10, 10, 40), alpha=0.70)

        draw_text(frame, "AEROBICOS", (8, 28), scale=0.65, color=CYAN,  thickness=2)
        draw_text(frame, mod["name"], (8, 52), scale=0.55, color=WHITE, thickness=2)

        desc = mod["description"]
        draw_text(frame, desc[:28], (8, 72), scale=0.38, color=(200, 200, 200), thickness=1)
        if len(desc) > 28:
            draw_text(frame, desc[28:], (8, 87), scale=0.38, color=(200, 200, 200), thickness=1)

        # Checkpoint indicators
        y_off = 108
        for cp, label in mod["labels"].items():
            active = (self._cur_cp == cp)
            color  = GREEN if active else (100, 100, 100)
            marker = ">" if active else "-"
            draw_text(frame, f"{marker} {label}", (8, y_off),
                      scale=0.42, color=color, thickness=1)
            y_off += 18

        # Form feedback (module 1 only)
        if mod["form_check"] is not None:
            form_ok = mod["form_check"](self._data)
            draw_text(frame,
                      "FORMA OK" if form_ok else "AJUSTA CODOS",
                      (8, y_off + 4),
                      scale=0.42,
                      color=GREEN if form_ok else RED,
                      thickness=1)

        # Rep progress — goal is per-module target (visual only, not gating)
        rep_display = min(self._reps, target)
        rep_color   = GREEN if self._reps >= target else CYAN
        draw_text(frame, f"Reps: {self._reps}/{target}",
                  (8, self._h - 72), scale=0.55, color=rep_color, thickness=2)
        draw_progress_bar(frame, (8, self._h - 52), (panel_w - 16, 14),
                          rep_display, target, fg_color=rep_color)

        if now - self._flash_t < SUCCESS_FLASH:
            draw_text(frame, "+10 pts", (8, self._h - 22),
                      scale=0.55, color=YELLOW, thickness=2)

        # Top-right: module counter + score
        counter_txt = f"Modulo {self._mod_idx + 1}/{len(AEROBIC_MODULES)}"
        (cw, _), _ = cv2.getTextSize(counter_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        draw_panel(frame, (self._w - cw - 20, 0, cw + 20, 65), color=(10, 10, 40), alpha=0.65)
        draw_text(frame, counter_txt,           (self._w - cw - 10, 28), scale=0.6,  color=WHITE)
        draw_text(frame, f"Pts: {self._score}", (self._w - cw - 10, 55), scale=0.55, color=YELLOW)

    def get_video_frame(self) -> Optional[np.ndarray]:
        return self._video.read_frame() if self._video else None

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "aerobics"
