import time
import cv2
import numpy as np
from typing import Optional, Dict, List, Tuple

from games.base_game import BaseGame
from core.renderer import (
    draw_text, draw_progress_bar, draw_panel, draw_chip, draw_hold_ring,
    BG, YOGA_CLR, INK, INK_DIM, LINE,
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

HOLD_SECS      = 10.0
SUCCESS_LINGER = 1.8


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


YOGA_POSES: List[Dict] = [
    {
        "name":              "Saludo hacia Arriba",
        "description":       "Brazos rectos sobre la cabeza, cuerpo erguido",
        "video":             "assets/videos/yoga/yoga1.mp4",
        "option_timestamps": [0.0],
        "options": [
            [
                ("angle", "left_elbow",      ">", 120, "Codo izq recto"),
                ("angle", "right_elbow",     ">", 120, "Codo der recto"),
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
            [
                ("y_cmp", "rw_y", "<", "nose_y",  "Mano der sobre cabeza"),
                ("angle", "right_elbow", ">", 150, "Codo der recto"),
                ("y_cmp", "lw_y", ">", "lh_y",    "Mano izq bajo cadera"),
                ("angle", "left_knee",   ">", 160, "Rodilla izq recta"),
                ("angle", "right_knee",  ">", 160, "Rodilla der recta"),
            ],
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
            [
                ("angle", "stance_ratio",   ">", 1.3,  "Piernas separadas"),
                ("near",  "rw_y", "rk_y",   0.13,      "Muneca der a altura rodilla"),
                ("near",  "rw_x", "rk_x",   0.12,      "Muneca sobre rodilla der"),
                ("y_cmp", "lw_y", "<", "nose_y",        "Mano izq sobre cabeza"),
                ("angle", "left_elbow",     ">", 145,  "Brazo izq recto"),
            ],
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
            [
                ("angle", "right_hip_angle", "<", 130, "Cadera der elevada"),
                ("angle", "right_knee",      "<", 110, "Rodilla der doblada"),
            ],
            [
                ("angle", "left_hip_angle", "<", 120, "Cadera izq elevada"),
                ("angle", "left_knee",      "<", 110, "Rodilla izq doblada"),
            ],
        ],
    },
]


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
            "left_elbow":      calc_angle(pt(LEFT_SHOULDER),  pt(LEFT_ELBOW),   pt(LEFT_WRIST)),
            "right_elbow":     calc_angle(pt(RIGHT_SHOULDER), pt(RIGHT_ELBOW),  pt(RIGHT_WRIST)),
            "left_knee":       calc_angle(pt(LEFT_HIP),       pt(LEFT_KNEE),    pt(LEFT_ANKLE)),
            "right_knee":      calc_angle(pt(RIGHT_HIP),      pt(RIGHT_KNEE),   pt(RIGHT_ANKLE)),
            "left_hip_angle":  calc_angle(pt(LEFT_SHOULDER),  pt(LEFT_HIP),     pt(LEFT_KNEE)),
            "right_hip_angle": calc_angle(pt(RIGHT_SHOULDER), pt(RIGHT_HIP),    pt(RIGHT_KNEE)),
            "nose_y": landmarks[NOSE].y,
            "lw_y":   landmarks[LEFT_WRIST].y,
            "rw_y":   landmarks[RIGHT_WRIST].y,
            "lh_y":   landmarks[LEFT_HIP].y,
            "rh_y":   landmarks[RIGHT_HIP].y,
            "lk_y":   landmarks[LEFT_KNEE].y,
            "rk_y":   landmarks[RIGHT_KNEE].y,
            "lw_x":   landmarks[LEFT_WRIST].x,
            "rw_x":   landmarks[RIGHT_WRIST].x,
            "lk_x":   landmarks[LEFT_KNEE].x,
            "rk_x":   landmarks[RIGHT_KNEE].x,
            "stance_ratio": stance_ratio,
        }
    except Exception:
        return {}


class PoseChallenge(BaseGame):
    def __init__(self, frame_w: int = 1380, frame_h: int = 1080):
        self._w = frame_w
        self._h = frame_h
        self._video: Optional[VideoPlayer] = None
        self._next: Optional[str] = None
        self.reset()

    def reset(self) -> None:
        self._next             = None
        self._idx              = 0
        self._active_option    = 0
        self._score            = 0
        self._hold_accumulated = 0.0
        self._last_met_t: Optional[float] = None
        self._hold_ratio       = 0.0
        self._data:       dict = {}
        self._best_conds: list = []
        self._n_met            = 0
        self._all_met          = False
        self._success          = False
        self._success_t        = 0.0
        self._success_pts      = 0
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
        self._active_option    = 0
        self._hold_accumulated = 0.0
        self._last_met_t       = None
        self._hold_ratio       = 0.0
        self._best_conds       = []
        self._n_met            = 0
        self._all_met          = False

    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        now = time.perf_counter()

        if self._idx >= len(YOGA_POSES):
            self._next = "menu"
            return

        if self._success:
            if now - self._success_t >= SUCCESS_LINGER:
                self._success = False
                pose = YOGA_POSES[self._idx]
                if self._active_option < len(pose["options"]) - 1:
                    pass
                else:
                    self._idx += 1
                    if self._idx >= len(YOGA_POSES):
                        self._next = "menu"
                    else:
                        self._load_pose(self._idx)
            return

        vt = self._video.current_time if self._video else 0.0
        timestamps = YOGA_POSES[self._idx]["option_timestamps"]
        new_opt = sum(1 for t in timestamps if vt >= t) - 1
        new_opt = max(0, min(new_opt, len(YOGA_POSES[self._idx]["options"]) - 1))
        if new_opt != self._active_option:
            self._active_option    = new_opt
            self._hold_accumulated = 0.0
            self._last_met_t       = None
            self._hold_ratio       = 0.0

        if self._video and self._video.is_done:
            if self._hold_ratio > 0:
                pts = int(self._hold_ratio * len(self._best_conds) * 10)
                self._score      += pts
                self._success     = True
                self._success_t   = now
                self._success_pts = pts
            else:
                self._idx += 1
                if self._idx >= len(YOGA_POSES):
                    self._next = "menu"
                else:
                    self._load_pose(self._idx)
            return

        if landmarks:
            self._data = _extract_pose_data(landmarks, frame_w, frame_h)
        else:
            self._data = {}

        if self._data:
            pose    = YOGA_POSES[self._idx]
            conds   = pose["options"][self._active_option]
            n_met   = sum(_check(self._data, c) for c in conds)
            self._best_conds = conds
            self._n_met      = n_met
            self._all_met    = (n_met == len(conds) and len(conds) > 0)
        else:
            self._n_met, self._best_conds, self._all_met = 0, [], False

        if self._all_met:
            if self._last_met_t is not None:
                self._hold_accumulated = min(
                    self._hold_accumulated + (now - self._last_met_t), HOLD_SECS
                )
            self._last_met_t = now
            self._hold_ratio = self._hold_accumulated / HOLD_SECS
            if self._hold_ratio >= 1.0:
                pts = len(self._best_conds) * 10
                self._score           += pts
                self._success          = True
                self._success_t        = now
                self._success_pts      = pts
                self._hold_accumulated = 0.0
                self._last_met_t       = None
                self._hold_ratio       = 0.0
        else:
            self._last_met_t = None

    def render(self, frame: np.ndarray) -> None:
        if self._idx >= len(YOGA_POSES):
            return

        if self._success:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (self._w, self._h), (40, 100, 40), -1)
            cv2.addWeighted(overlay, 0.30, frame, 0.70, 0, frame)
            (tw, _), _ = cv2.getTextSize("EXCELENTE!", cv2.FONT_HERSHEY_SIMPLEX, 2.2, 4)
            draw_text(frame, "EXCELENTE!",
                      (self._w // 2 - tw // 2, self._h // 2 - 20),
                      scale=2.2, color=YOGA_CLR, thickness=4)
            (pw, _), _ = cv2.getTextSize(f"+{self._success_pts} pts",
                                         cv2.FONT_HERSHEY_SIMPLEX, 1.2, 2)
            draw_text(frame, f"+{self._success_pts} pts",
                      (self._w // 2 - pw // 2, self._h // 2 + 60),
                      scale=1.2, color=YELLOW, thickness=2)
            return

        pose    = YOGA_POSES[self._idx]
        panel_w = int(280 * self._w / 640)

        draw_panel(frame, (0, 0, panel_w, self._h), color=BG, alpha=0.75)
        cv2.line(frame, (panel_w, 0), (panel_w, self._h), LINE, 1, cv2.LINE_AA)

        # Mode chip + pose name
        draw_chip(frame, (12, 42), "YOGA", color=YOGA_CLR, scale=0.65)
        draw_text(frame, pose["name"], (12, 78),  scale=0.7,  color=INK,     thickness=2)

        desc = pose["description"]
        draw_text(frame, desc[:28], (12, 104), scale=0.48, color=INK_DIM, thickness=1)
        if len(desc) > 28:
            draw_text(frame, desc[28:], (12, 124), scale=0.48, color=INK_DIM, thickness=1)

        # Option indicator (A/B/C)
        if len(pose["options"]) > 1:
            opt_lbl = chr(65 + self._active_option)
            draw_chip(frame, (12, 152), f"OPCION {opt_lbl}", color=YOGA_CLR, scale=0.52)

        # Per-condition checklist
        y_off   = 172 if len(pose["options"]) > 1 else 156
        n_total = len(self._best_conds)
        for cond in self._best_conds:
            met    = _check(self._data, cond) if self._data else False
            label  = cond[-1]
            symbol = "OK" if met else "--"
            color  = YOGA_CLR if met else LINE
            draw_text(frame, f"{symbol} {label}", (12, y_off),
                      scale=0.45, color=color, thickness=1)
            y_off += 22

        # Condition count chip
        count_color = YOGA_CLR if self._all_met else ORANGE if self._n_met >= n_total // 2 else RED
        draw_text(frame, f"{self._n_met}/{n_total} condiciones",
                  (12, self._h - 120),
                  scale=0.65, color=count_color, thickness=2)

        # Hold ring — centered on the frame (right side), above HUD
        if self._hold_ratio > 0:
            ring_cx = self._w // 2
            ring_cy = self._h // 2
            ring_r  = int(90 * self._w / 640)
            draw_hold_ring(frame, (ring_cx, ring_cy), ring_r, self._hold_ratio, YOGA_CLR)
            hold_secs_done = self._hold_ratio * HOLD_SECS
            (tw, _), _ = cv2.getTextSize(f"{hold_secs_done:.1f}s",
                                         cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
            draw_text(frame, f"{hold_secs_done:.1f}s",
                      (ring_cx - tw // 2, ring_cy + 12),
                      scale=1.0, color=YOGA_CLR, thickness=2)

        # Hold bar (panel)
        if self._hold_ratio > 0:
            hold_secs_done = self._hold_ratio * HOLD_SECS
            draw_text(frame, f"MANTEN! {hold_secs_done:.1f}/{HOLD_SECS:.0f}s",
                      (12, self._h - 90), scale=0.52, color=YOGA_CLR, thickness=1)
            draw_progress_bar(frame, (12, self._h - 68), (panel_w - 24, 16),
                              self._hold_ratio, 1.0, fg_color=YOGA_CLR)

        # Top-right: pose counter + score
        counter_txt = f"POSE {self._idx + 1}/{len(YOGA_POSES)}"
        (cw, _), _  = cv2.getTextSize(counter_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 1)
        draw_chip(frame, (self._w - cw - 36, 50), counter_txt, color=YOGA_CLR, scale=0.65)
        draw_chip(frame, (self._w - cw - 36, 96), f"PTS: {self._score}", color=YOGA_CLR, scale=0.65)

    def get_video_frame(self) -> Optional[np.ndarray]:
        return self._video.read_frame() if self._video else None

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "pose_challenge"
