import time
import random
import cv2
import numpy as np
from typing import Optional, List, Tuple

from games.base_game import BaseGame
from core.renderer import (
    draw_target, draw_text, draw_progress_bar, draw_panel, draw_wrist_cursor,
    WHITE, RED, GREEN, YELLOW, CYAN, ORANGE,
)
from utils.landmarks import LEFT_WRIST, RIGHT_WRIST
from utils.math_utils import landmark_to_px, distance_2d

GAME_DURATION   = 60.0
TARGET_LIFETIME = 3.0
HIT_SLOP        = 22          # extra pixels around target radius that count as hit
COMBO_WINDOW    = 1.5         # seconds between hits to keep combo alive
GAMEOV_LINGER   = 2.5         # seconds to show game-over screen before returning


class _Target:
    COLORS = [
        (0,   0,   220),   # red
        (0,   130, 255),   # orange
        (200, 0,   160),   # magenta
        (0,   80,  200),   # dark-orange
    ]

    def __init__(self, cx: int, cy: int, radius: int):
        self.center    = (cx, cy)
        self.radius    = radius
        self.color     = random.choice(self.COLORS)
        self._born     = time.perf_counter()
        self.hit       = False
        self.hit_time: Optional[float] = None

    @property
    def alive(self) -> bool:
        return not self.hit and (time.perf_counter() - self._born) < TARGET_LIFETIME

    @property
    def age_ratio(self) -> float:
        return min((time.perf_counter() - self._born) / TARGET_LIFETIME, 1.0)


class BoxingGame(BaseGame):
    def __init__(self, frame_w: int = 640, frame_h: int = 480):
        self._w = frame_w
        self._h = frame_h
        self._next: Optional[str] = None
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._next        = None
        self._score       = 0
        self._lives       = 3
        self._combo       = 0
        self._targets:    List[_Target] = []
        self._effects:    List[Tuple[int, int, float]] = []   # (x, y, born)
        self._start       = time.perf_counter()
        self._last_spawn  = 0.0
        self._last_hit    = 0.0
        self._wrists: List[Optional[Tuple[int, int]]] = [None, None]
        self._game_over   = False
        self._over_time   = 0.0

    # ------------------------------------------------------------------
    def _spawn_interval(self) -> float:
        elapsed = time.perf_counter() - self._start
        return max(0.75, 2.2 - elapsed * 0.018)

    def _spawn(self) -> None:
        margin = 80
        cx = random.randint(margin, self._w - margin)
        cy = random.randint(margin, self._h - margin)
        r  = random.randint(28, 52)
        self._targets.append(_Target(cx, cy, r))

    # ------------------------------------------------------------------
    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        now = time.perf_counter()

        if self._game_over:
            if now - self._over_time >= GAMEOV_LINGER:
                self._next = "menu"
            return

        elapsed = now - self._start
        if elapsed >= GAME_DURATION or self._lives <= 0:
            self._game_over = True
            self._over_time = now
            return

        # spawn
        if now - self._last_spawn >= self._spawn_interval():
            self._spawn()
            self._last_spawn = now

        # wrists
        self._wrists = [None, None]
        wrist_pts: List[Tuple[int, int]] = []
        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST],  frame_w, frame_h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], frame_w, frame_h)
            self._wrists = [lw, rw]
            wrist_pts    = [lw, rw]

        # hit detection & expiry
        alive: List[_Target] = []
        for t in self._targets:
            if t.hit:
                if now - t.hit_time < 0.25:
                    alive.append(t)
                continue
            if not t.alive:
                self._lives = max(0, self._lives - 1)
                self._combo = 0
                continue
            for wp in wrist_pts:
                if distance_2d(wp, t.center) <= t.radius + HIT_SLOP:
                    t.hit      = True
                    t.hit_time = now
                    self._combo = self._combo + 1 if now - self._last_hit < COMBO_WINDOW else 1
                    self._last_hit = now
                    self._score   += 10 * self._combo
                    self._effects.append((*t.center, now))
                    break
            alive.append(t)
        self._targets = alive

        self._effects = [(x, y, bt) for x, y, bt in self._effects if now - bt < 0.4]

    # ------------------------------------------------------------------
    def render(self, frame: np.ndarray) -> None:
        now = time.perf_counter()

        # targets
        for t in self._targets:
            ratio  = t.age_ratio
            factor = max(0.45, 1.0 - ratio * 0.55)
            faded  = tuple(int(c * factor) for c in t.color)
            draw_target(frame, t.center, t.radius, faded, hit=t.hit)

        # hit ripples
        for x, y, born in self._effects:
            age = now - born
            r   = int(28 + age * 110)
            alpha_val = max(0, int(255 * (1.0 - age / 0.4)))
            overlay = frame.copy()
            cv2.circle(overlay, (x, y), r, CYAN, 2, cv2.LINE_AA)
            cv2.addWeighted(overlay, alpha_val / 255, frame, 1 - alpha_val / 255, 0, frame)

        # wrist cursors
        for pt in self._wrists:
            draw_wrist_cursor(frame, pt, color=YELLOW)

        # HUD panel
        draw_panel(frame, (0, 0, 220, 115), color=(10, 10, 40), alpha=0.65)
        draw_text(frame, f"SCORE: {self._score}", (10, 35),  scale=0.85, color=YELLOW)
        combo_color = CYAN if self._combo > 1 else WHITE
        draw_text(frame, f"COMBO x{self._combo}",  (10, 65),  scale=0.65, color=combo_color)

        # lives (circles)
        for i in range(3):
            c = RED if i < self._lives else (70, 70, 70)
            cv2.circle(frame, (self._w - 30 - i * 38, 28), 13, c, -1, cv2.LINE_AA)
            cv2.circle(frame, (self._w - 30 - i * 38, 28), 13, WHITE, 1, cv2.LINE_AA)

        # timer bar
        elapsed   = now - self._start
        remaining = max(0.0, GAME_DURATION - elapsed)
        bar_color = GREEN if remaining > 20 else ORANGE if remaining > 10 else RED
        draw_progress_bar(frame, (10, self._h - 22), (self._w - 20, 14),
                          remaining, GAME_DURATION, fg_color=bar_color)
        draw_text(frame, f"{remaining:.0f}s",
                  (self._w // 2 - 18, self._h - 26), scale=0.55, color=WHITE, thickness=1)

        # game-over overlay
        if self._game_over:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (self._w, self._h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
            draw_text(frame, "GAME OVER",
                      (self._w // 2 - 130, self._h // 2 - 20),
                      scale=1.8, color=RED, thickness=4)
            draw_text(frame, f"Puntuacion final: {self._score}",
                      (self._w // 2 - 145, self._h // 2 + 40),
                      scale=0.9, color=YELLOW, thickness=2)

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "boxing"
