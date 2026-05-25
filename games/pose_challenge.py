import time
import cv2
import numpy as np
from typing import Optional, Dict, List, Tuple

from games.base_game import BaseGame
from core.renderer import (
    draw_text, draw_progress_bar, draw_panel,
    WHITE, GREEN, RED, YELLOW, CYAN, ORANGE,
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

HOLD_SECS      = 10.0   # seconds user must hold the pose
SUCCESS_LINGER = 1.8    # flash duration after completing a pose section

# ── Condition types ──────────────────────────────────────────────────────────
# ("angle",  data_key,  ">"|"<",  threshold_degrees,  "label")
# ("y_cmp",  key_a,     "<"|">",  key_b,               "label")
#   y_cmp: smaller Y = higher on screen (MediaPipe normalized Y, 0=top)
# ("near",   key_a,     key_b,    threshold,            "label")
#   near: abs(data[key_a] - data[key_b]) < threshold

def _check(data: dict, cond: tuple) -> bool:
    kind = cond[0]
    if kind == "angle":
        v = data.get(cond[1])
        return v is not None and (v > cond[3] if cond[2] == ">" else v < cond[3])
    elif kind == "y_cmp":
        a, b = data.get(cond[1]), data.get(cond[3])
        return a is not None and b is not None and (a < b if cond[2] == "<" else a > b)
    elif kind == "near":
        a, b = data.get(cond[1]), data.get(cond[2])
        return a is not None and b is not None and abs(a - b) < cond[3]
    return False


# ── Yoga pose definitions ────────────────────────────────────────────────────
# Each pose: name, description, video, option_timestamps, options (list of condition lists).
# option_timestamps[i] = video time (seconds) when option i becomes active.
# Timer starts when ALL conditions of the currently active option are met simultaneously.
YOGA_POSES: List[Dict] = [
    {
        "name":              "Saludo hacia Arriba",
        "description":       "Brazos rectos sobre la cabeza, cuerpo erguido",
        "video":             "assets/videos/yoga/yoga1.mp4",
        "option_timestamps": [0.0],
        "options": [
            [
                ("angle", "left_elbow",      ">", 150, "Codo izq recto"),
                ("angle", "right_elbow",     ">", 150, "Codo der recto"),
                ("y_cmp", "lw_y", "<", "nose_y",       "Mano izq sobre cabeza"),
                ("y_cmp", "rw_y", "<", "nose_y",       "Mano der sobre cabeza"),
                ("angle", "left_hip_angle",  ">", 160, "Cadera izq recta"),
                ("angle", "right_hip_angle", ">", 160, "Cadera der recta"),
                ("angle", "left_knee",       ">", 160, "Rodilla izq recta"),
                ("angle", "right_knee",      ">", 160, "Rodilla der recta"),
            ]
        ],
    },
    {
        "name":              "Inclinacion Lateral",
        "description":       "Inclina hacia un lado, brazo opuesto arriba",
        "video":             "assets/videos/yoga/yoga2.mp4",
        "option_timestamps": [0.0, 13.0],
        "options": [
            # Option A: lean left — right arm up, left hand rests on leg
            [
                ("y_cmp", "rw_y", "<", "nose_y",  "Mano der sobre cabeza"),
                ("angle", "right_elbow", ">", 150, "Codo der recto"),
                ("y_cmp", "lw_y", ">", "lh_y",    "Mano izq bajo cadera"),
                ("angle", "left_knee",   ">", 160, "Rodilla izq recta"),
                ("angle", "right_knee",  ">", 160, "Rodilla der recta"),
            ],
            # Option B: lean right — left arm up, right hand rests on leg
            [
                ("y_cmp", "lw_y", "<", "nose_y",  "Mano izq sobre cabeza"),
                ("angle", "left_elbow",  ">", 150, "Codo izq recto"),
                ("y_cmp", "rw_y", ">", "rh_y",    "Mano der bajo cadera"),
                ("angle", "left_knee",   ">", 160, "Rodilla izq recta"),
                ("angle", "right_knee",  ">", 160, "Rodilla der recta"),
            ],
        ],
    },
    {
        "name":              "Apertura con Toque",
        "description":       "Piernas abiertas, toca rodilla, otro brazo arriba",
        "video":             "assets/videos/yoga/yoga3.mp4",
        "option_timestamps": [0.0, 13.0],
        "options": [
            # Option A: lean right — right wrist near right knee, left arm up
            [
                ("angle", "stance_ratio",   ">", 1.3,  "Piernas separadas"),
                ("near",  "rw_y", "rk_y",   0.13,      "Muneca der a altura rodilla"),
                ("near",  "rw_x", "rk_x",   0.12,      "Muneca sobre rodilla der"),
                ("y_cmp", "lw_y", "<", "nose_y",        "Mano izq sobre cabeza"),
                ("angle", "left_elbow",     ">", 145,  "Brazo izq recto"),
            ],
            # Option B: lean left — left wrist near left knee, right arm up
            [
                ("angle", "stance_ratio",   ">", 1.3,  "Piernas separadas"),
                ("near",  "lw_y", "lk_y",   0.13,      "Muneca izq a altura rodilla"),
                ("near",  "lw_x", "lk_x",   0.12,      "Muneca sobre rodilla izq"),
                ("y_cmp", "rw_y", "<", "nose_y",        "Mano der sobre cabeza"),
                ("angle", "right_elbow",    ">", 145,  "Brazo der recto"),
            ],
        ],
    },
    {
        "name":              "Rodilla Elevada",
        "description":       "Equilibrio en una pierna, rodilla contraria arriba",
        "video":             "assets/videos/yoga/yoga4.mp4",
        "option_timestamps": [0.0, 16.0],
        "options": [
            # Option A: balance on left leg, right knee raised
            [
                ("angle", "left_knee",       ">", 160, "Pierna izq recta"),
                ("angle", "right_hip_angle", "<", 130, "Cadera der elevada"),
                ("angle", "right_knee",      "<", 110, "Rodilla der doblada"),
            ],
            # Option B: balance on right leg, left knee raised
            [
                ("angle", "right_knee",     ">", 160, "Pierna der recta"),
                ("angle", "left_hip_angle", "<", 120, "Cadera izq elevada"),
                ("angle", "left_knee",      "<", 110, "Rodilla izq doblada"),
            ],
        ],
    },
]


# ── Data extraction ──────────────────────────────────────────────────────────
def _extract_pose_data(landmarks: list, fw: int, fh: int) -> dict:
    if not landmarks or len(landmarks) < 33:
        return {}

    def pt(idx: int) -> Tuple[float, float]:
        lm = landmarks[idx]
        return (lm.x * fw, lm.y * fh)

    try:
        lh_x = landmarks[LEFT_HIP].x
        rh_x = landmarks[RIGHT_HIP].x
        la_x = landmarks[LEFT_ANKLE].x
        ra_x = landmarks[RIGHT_ANKLE].x
        hip_span    = abs(lh_x - rh_x)
        ankle_span  = abs(la_x - ra_x)
        stance_ratio = ankle_span / max(hip_span, 0.01)

        return {
            # Angles
            "left_elbow":      calc_angle(pt(LEFT_SHOULDER),  pt(LEFT_ELBOW),   pt(LEFT_WRIST)),
            "right_elbow":     calc_angle(pt(RIGHT_SHOULDER), pt(RIGHT_ELBOW),  pt(RIGHT_WRIST)),
            "left_knee":       calc_angle(pt(LEFT_HIP),       pt(LEFT_KNEE),    pt(LEFT_ANKLE)),
            "right_knee":      calc_angle(pt(RIGHT_HIP),      pt(RIGHT_KNEE),   pt(RIGHT_ANKLE)),
            "left_hip_angle":  calc_angle(pt(LEFT_SHOULDER),  pt(LEFT_HIP),     pt(LEFT_KNEE)),
            "right_hip_angle": calc_angle(pt(RIGHT_SHOULDER), pt(RIGHT_HIP),    pt(RIGHT_KNEE)),
            # Y coords (normalized)
            "nose_y": landmarks[NOSE].y,
            "lw_y":   landmarks[LEFT_WRIST].y,
            "rw_y":   landmarks[RIGHT_WRIST].y,
            "lh_y":   landmarks[LEFT_HIP].y,
            "rh_y":   landmarks[RIGHT_HIP].y,
            "lk_y":   landmarks[LEFT_KNEE].y,
            "rk_y":   landmarks[RIGHT_KNEE].y,
            # X coords (normalized) — for "near" conditions
            "lw_x":   landmarks[LEFT_WRIST].x,
            "rw_x":   landmarks[RIGHT_WRIST].x,
            "lk_x":   landmarks[LEFT_KNEE].x,
            "rk_x":   landmarks[RIGHT_KNEE].x,
            # Computed
            "stance_ratio": stance_ratio,
        }
    except Exception:
        return {}


# ── Game class ────────────────────────────────────────────────────────────────
class PoseChallenge(BaseGame):
    def __init__(self, frame_w: int = 640, frame_h: int = 480):
        self._w = frame_w
        self._h = frame_h
        self._video: Optional[VideoPlayer] = None
        self._next: Optional[str] = None
        self.reset()

    def reset(self) -> None:
        self._next           = None
        self._idx            = 0
        self._active_option  = 0
        self._score          = 0
        self._hold_start: Optional[float] = None
        self._hold_ratio     = 0.0
        self._data:       dict = {}
        self._best_conds: list = []
        self._n_met          = 0
        self._all_met        = False
        self._success        = False
        self._success_t      = 0.0
        self._success_pts    = 0
        if self._video:
            self._video.stop()
        self._video = None
        self._load_pose(0)

    def _load_pose(self, idx: int) -> None:
        if self._video:
            self._video.stop()
        if idx >= len(YOGA_POSES):
            return
        pose = YOGA_POSES[idx]
        self._video = VideoPlayer(pose["video"])
        if not self._video.load():
            self._video = None
        else:
            self._video.start()
        self._active_option = 0
        self._hold_start    = None
        self._hold_ratio    = 0.0
        self._best_conds    = []
        self._n_met         = 0
        self._all_met       = False

    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        now = time.perf_counter()

        if self._idx >= len(YOGA_POSES):
            self._next = "menu"
            return

        # Success linger before advancing to next pose
        if self._success:
            if now - self._success_t >= SUCCESS_LINGER:
                self._success = False
                self._idx    += 1
                if self._idx >= len(YOGA_POSES):
                    self._next = "menu"
                else:
                    self._load_pose(self._idx)
            return

        # Video-driven option switching
        vt = self._video.current_time if self._video else 0.0
        timestamps = YOGA_POSES[self._idx]["option_timestamps"]
        new_opt = sum(1 for t in timestamps if vt >= t) - 1
        new_opt = max(0, min(new_opt, len(YOGA_POSES[self._idx]["options"]) - 1))
        if new_opt != self._active_option:
            self._active_option = new_opt
            self._hold_start    = None
            self._hold_ratio    = 0.0

        # Advance to next pose when video ends
        if self._video and self._video.is_done:
            # Grant score for whatever hold was accumulated
            if self._hold_ratio > 0:
                pts = int(self._hold_ratio * len(self._best_conds) * 10)
                self._score     += pts
                self._success    = True
                self._success_t  = now
                self._success_pts = pts
            else:
                self._idx += 1
                if self._idx >= len(YOGA_POSES):
                    self._next = "menu"
                else:
                    self._load_pose(self._idx)
            return

        # Landmark extraction
        if landmarks:
            self._data = _extract_pose_data(landmarks, frame_w, frame_h)
        else:
            self._data = {}

        # Evaluate the currently active option
        if self._data:
            pose    = YOGA_POSES[self._idx]
            options = pose["options"]
            conds   = options[self._active_option]
            n_met   = sum(_check(self._data, c) for c in conds)
            self._best_conds = conds
            self._n_met      = n_met
            self._all_met    = (n_met == len(conds) and len(conds) > 0)
        else:
            self._n_met, self._best_conds, self._all_met = 0, [], False

        # Hold timer
        if self._all_met:
            if self._hold_start is None:
                self._hold_start = now
            self._hold_ratio = min((now - self._hold_start) / HOLD_SECS, 1.0)
            if self._hold_ratio >= 1.0:
                pts = len(self._best_conds) * 10
                self._score      += pts
                self._success     = True
                self._success_t   = now
                self._success_pts = pts
                self._hold_start  = None
                self._hold_ratio  = 0.0
        else:
            self._hold_start = None
            self._hold_ratio = 0.0

    def render(self, frame: np.ndarray) -> None:
        if self._idx >= len(YOGA_POSES):
            return

        if self._success:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (self._w, self._h), (0, 180, 0), -1)
            cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
            draw_text(frame, "EXCELENTE!",
                      (self._w // 2 - 115, self._h // 2 - 10),
                      scale=1.6, color=(0, 255, 0), thickness=4)
            draw_text(frame, f"+{self._success_pts} pts",
                      (self._w // 2 - 60, self._h // 2 + 50),
                      scale=1.0, color=YELLOW, thickness=2)
            return

        pose    = YOGA_POSES[self._idx]
        panel_w = 220
        draw_panel(frame, (0, 0, panel_w, self._h), color=(10, 10, 40), alpha=0.70)

        draw_text(frame, "YOGA",        (8, 28),  scale=0.65, color=CYAN,   thickness=2)
        draw_text(frame, pose["name"],  (8, 52),  scale=0.55, color=WHITE,  thickness=2)

        desc = pose["description"]
        draw_text(frame, desc[:28], (8, 74), scale=0.40, color=(200, 200, 200), thickness=1)
        if len(desc) > 28:
            draw_text(frame, desc[28:], (8, 89), scale=0.40, color=(200, 200, 200), thickness=1)

        # Option indicator (A/B) when pose has multiple options
        if len(pose["options"]) > 1:
            opt_lbl = chr(65 + self._active_option)  # A, B, C...
            draw_text(frame, f"Opcion {opt_lbl}", (8, 104),
                      scale=0.42, color=ORANGE, thickness=1)

        # Per-condition feedback
        y_off   = 118 if len(pose["options"]) > 1 else 108
        n_total = len(self._best_conds)
        for cond in self._best_conds:
            met    = _check(self._data, cond) if self._data else False
            label  = cond[-1]
            symbol = "OK" if met else "--"
            color  = GREEN if met else RED
            draw_text(frame, f"{symbol} {label}", (8, y_off),
                      scale=0.38, color=color, thickness=1)
            y_off += 18

        # Condition count
        count_color = GREEN if self._all_met else ORANGE if self._n_met >= n_total // 2 else RED
        draw_text(frame, f"{self._n_met}/{n_total} condiciones", (8, self._h - 90),
                  scale=0.55, color=count_color, thickness=2)

        # Hold bar
        if self._hold_ratio > 0:
            hold_secs_done = self._hold_ratio * HOLD_SECS
            draw_text(frame, f"MANTEN! {hold_secs_done:.1f}/{HOLD_SECS:.0f}s",
                      (8, self._h - 68), scale=0.48, color=CYAN, thickness=1)
            draw_progress_bar(frame, (8, self._h - 50), (panel_w - 16, 14),
                              self._hold_ratio, 1.0, fg_color=CYAN)

        # Top-right: pose counter + score
        counter_txt = f"Pose {self._idx + 1}/{len(YOGA_POSES)}"
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
        return "pose_challenge"
