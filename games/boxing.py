import time
import random
import cv2
import numpy as np
from typing import Optional, List, Tuple

from games.base_game import BaseGame
from core.renderer import (
    draw_target, draw_text, draw_panel, draw_wrist_cursor,
    WHITE, RED, YELLOW, CYAN,
)
from utils.landmarks import (LEFT_WRIST, RIGHT_WRIST,
                              LEFT_SHOULDER, LEFT_ELBOW,
                              RIGHT_SHOULDER, RIGHT_ELBOW)
from utils.math_utils import landmark_to_px, distance_2d, calc_angle
from utils.punch_tracker import ArmPunchState

# ═══════════════════════════════════════════════════════════════════════════════
# PARÁMETROS DE CALIBRACIÓN — ajusta estos valores para afinar la detección
# ═══════════════════════════════════════════════════════════════════════════════
TARGET_RADIUS   = 80      # px   – radio del círculo objetivo
HIT_SLOP        = 30      # px   – margen extra alrededor del radio que cuenta como hit

GUARD_ANGLE     = 90.0    # °    – codo DEBE bajar de este valor para entrar en GUARD
IMPACT_ANGLE    = 150.0   # °    – codo DEBE llegar aquí para disparar el golpe
RETURN_ANGLE    = 130.0   # °    – tras IMPACT, baja de aquí para resetear a GUARD
MIN_VISIBILITY  = 0.5     # 0–1  – visibilidad mínima del landmark para usarlo

HIT_LINGER      = 0.5     # s    – tiempo que se muestra el hit antes de spawnar siguiente
CENTER_GAP      = 60      # px   – zona muerta a cada lado del centro (evita el medio)
BOTTOM_MARGIN   = 160     # px   – margen desde abajo donde NO aparecen círculos

# ── Uppercut parameters ───────────────────────────────────────────────────────
UPPER_GUARD_ANGLE  = 60.0   # °    – ángulo de elevación muñeca para entrar en GUARD
UPPER_IMPACT_ANGLE = 120.0  # °    – ángulo de elevación para disparar uppercut
UPPER_RETURN_ANGLE =  90.0  # °    – baja de aquí para resetear tras IMPACT
UPPER_BOTTOM_MAX   = 0.55   # 0–1  – UPPER aparece en la mitad superior de pantalla

# ── Hook / Gancho parameters ─────────────────────────────────────────────────
HOOK_GUARD_ANGLE  =  45.0   # °    – abducción de hombro: arm abajo < este valor → GUARD
HOOK_IMPACT_ANGLE =  60.0   # °    – abducción de hombro para disparar el gancho
HOOK_RETURN_ANGLE =  58.0   # °    – baja de aquí para resetear tras IMPACT
GANCHO_TOP_MIN    =  0.35   # 0–1  – GANCHO no aparece por encima de este % de pantalla
GANCHO_ELBOW_MAX  = 153.0   # °    – codo DEBE estar doblado < este valor para registrar gancho
GANCHO_WINDOW     =   0.3   # s    – ventana tras disparo del gancho para registrar hit
UPPER_WINDOW      =   0.3   # s    – ventana tras disparo del uppercut para registrar hit
JAB_WINDOW        =   0.3   # s    – ventana tras disparo del JAB para registrar hit
CROSS_WINDOW      =   0.3   # s    – ventana tras disparo del CROSS para registrar hit
TARGET_REACTION_DELAY = 0.35  # s  – grace period tras spawn: ignora golpes residuales

# ═══════════════════════════════════════════════════════════════════════════════

PUNCH_COLOR = {
    "JAB":      ( 50, 210,  50),
    "CROSS":    (  0, 140, 255),
    "UPPER_L":  (180,  50, 255),
    "UPPER_R":  (180,  50, 255),
    "GANCHO_L": (  0,  80, 255),
    "GANCHO_R": (  0,  80, 255),
}

# Grupos de detección (Option B):
# JAB y CROSS son independientes. UPPER y GANCHO del mismo brazo comparten grupo —
# cualquier movimiento dinámico de ese brazo (hacia arriba O lateral) cuenta.
_PUNCH_GROUP = {
    "JAB":      "rw",   # muñeca derecha MediaPipe
    "UPPER_L":  "rw",
    "GANCHO_L": "rw",
    "CROSS":    "lw",   # muñeca izquierda MediaPipe
    "UPPER_R":  "lw",
    "GANCHO_R": "lw",
}


# ── Target ───────────────────────────────────────────────────────────────────
class _Target:
    def __init__(self, cx: int, cy: int, radius: int, punch_type: str):
        self.center      = (cx, cy)
        self.radius      = radius
        self.punch_type  = punch_type
        self.color       = PUNCH_COLOR[punch_type]
        self.hit         = False
        self.hit_time:   Optional[float] = None
        self.hit_correct: bool = False
        self.spawn_time: float = time.perf_counter()


# ── Floating text popup ───────────────────────────────────────────────────────
class _Popup:
    DURATION = 2.0

    def __init__(self, x: int, y: int, text: str, color: Tuple):
        self.x, self.y = x, y
        self.text  = text
        self.color = color
        self._born = time.perf_counter()

    @property
    def alive(self) -> bool:
        return time.perf_counter() - self._born < self.DURATION

    @property
    def render_y(self) -> int:
        return int(self.y - (time.perf_counter() - self._born) * 80)

    @property
    def alpha(self) -> float:
        return max(0.0, 1.0 - (time.perf_counter() - self._born) / self.DURATION)


# ── Main game class ───────────────────────────────────────────────────────────
class BoxingGame(BaseGame):
    def __init__(self, frame_w: int = 640, frame_h: int = 480):
        self._w = frame_w
        self._h = frame_h
        self._left_arm   = ArmPunchState(GUARD_ANGLE,       IMPACT_ANGLE,       RETURN_ANGLE)
        self._right_arm  = ArmPunchState(GUARD_ANGLE,       IMPACT_ANGLE,       RETURN_ANGLE)
        self._left_upper   = ArmPunchState(UPPER_GUARD_ANGLE, UPPER_IMPACT_ANGLE, UPPER_RETURN_ANGLE)
        self._right_upper  = ArmPunchState(UPPER_GUARD_ANGLE, UPPER_IMPACT_ANGLE, UPPER_RETURN_ANGLE)
        self._left_gancho  = ArmPunchState(HOOK_GUARD_ANGLE,  HOOK_IMPACT_ANGLE,  HOOK_RETURN_ANGLE)
        self._right_gancho = ArmPunchState(HOOK_GUARD_ANGLE,  HOOK_IMPACT_ANGLE,  HOOK_RETURN_ANGLE)
        self._next: Optional[str] = None
        self.reset()

    def reset(self) -> None:
        self._next         = None
        self._score        = 0
        self._target: Optional[_Target] = None
        self._spawn_after  = 0.0
        self._popups:  List[_Popup] = []
        self._ripples: List[Tuple]  = []
        self._wrists   = [None, None]
        self._last_la  = 0.0
        self._last_ra  = 0.0
        self._lg_fire_time = -1.0
        self._rg_fire_time = -1.0
        self._lu_fire_time = -1.0
        self._ru_fire_time = -1.0
        self._rj_fire_time = -1.0
        self._lc_fire_time = -1.0
        self._left_arm.reset()
        self._right_arm.reset()
        self._left_upper.reset()
        self._right_upper.reset()
        self._left_gancho.reset()
        self._right_gancho.reset()

    # ── Spawn ─────────────────────────────────────────────────────────────────
    def _spawn(self) -> None:
        margin    = TARGET_RADIUS + 20
        playfield = self._w
        mid       = playfield // 2
        punch_type = random.choice(["JAB", "CROSS", "UPPER_L", "UPPER_R", "GANCHO_L", "GANCHO_R"])
        cy_upper = random.randint(margin + 30, int(self._h * UPPER_BOTTOM_MAX))
        if punch_type == "JAB":
            cx = random.randint(margin, mid - CENTER_GAP)
            cy = random.randint(margin + 30, self._h - BOTTOM_MARGIN)
        elif punch_type == "CROSS":
            cx = random.randint(mid + CENTER_GAP, playfield - margin)
            cy = random.randint(margin + 30, self._h - BOTTOM_MARGIN)
        elif punch_type == "UPPER_L":  # MediaPipe DER → lado derecho
            cx = random.randint(mid + CENTER_GAP, playfield - margin)
            cy = cy_upper
        elif punch_type == "UPPER_R":  # MediaPipe IZQ → lado izquierdo
            cx = random.randint(margin, mid - CENTER_GAP)
            cy = cy_upper
        elif punch_type == "GANCHO_L":  # MediaPipe DER → lado derecho
            cx = random.randint(mid + CENTER_GAP, playfield - margin)
            cy = random.randint(int(self._h * GANCHO_TOP_MIN), self._h - BOTTOM_MARGIN)
        else:  # GANCHO_R – MediaPipe IZQ → lado izquierdo
            cx = random.randint(margin, mid - CENTER_GAP)
            cy = random.randint(int(self._h * GANCHO_TOP_MIN), self._h - BOTTOM_MARGIN)
        self._target = _Target(cx, cy, TARGET_RADIUS, punch_type)

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        now = time.perf_counter()

        # Spawn first target, or next one after hit animation finishes
        if self._target is None or (self._target.hit and now >= self._spawn_after):
            self._spawn()

        # Landmark extraction
        self._wrists = [None, None]
        lw = rw = None

        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST],  frame_w, frame_h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], frame_w, frame_h)
            self._wrists = [lw, rw]

        # Elbow angle → state machine → punch event
        punch_events: List[Tuple] = []
        if landmarks:
            def _arm_angle(sh: int, el: int, wr: int) -> Optional[float]:
                s, e, w = landmarks[sh], landmarks[el], landmarks[wr]
                if min(s.visibility, e.visibility, w.visibility) < MIN_VISIBILITY:
                    return None
                return calc_angle((s.x, s.y, s.z), (e.x, e.y, e.z), (w.x, w.y, w.z))

            la = _arm_angle(LEFT_SHOULDER,  LEFT_ELBOW,  LEFT_WRIST)
            ra = _arm_angle(RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST)

            if la is not None:
                self._last_la = la
                if self._left_arm.update(la) and lw is not None:
                    punch_events.append((lw, "CROSS"))
                    self._lc_fire_time = now
                    self._lg_fire_time = -1.0   # CROSS cancela ventana GANCHO_R (mismo brazo)
            if ra is not None:
                self._last_ra = ra
                if self._right_arm.update(ra) and rw is not None:
                    punch_events.append((rw, "JAB"))
                    self._rj_fire_time = now
                    self._rg_fire_time = -1.0   # JAB cancela ventana GANCHO_L (mismo brazo)

            # Uppercut: angle of wrist elevation relative to elbow
            # Uses a synthetic point below the elbow as reference (y+0.5 in norm coords)
            def _upper_angle(el: int, wr: int) -> Optional[float]:
                e, w = landmarks[el], landmarks[wr]
                if min(e.visibility, w.visibility) < MIN_VISIBILITY:
                    return None
                below = (e.x, e.y + 0.5, e.z)   # below elbow → arm hanging ≈ 0°, raised ≈ 160°
                return calc_angle(below, (e.x, e.y, e.z), (w.x, w.y, w.z))

            lu = _upper_angle(LEFT_ELBOW,  LEFT_WRIST)
            ru = _upper_angle(RIGHT_ELBOW, RIGHT_WRIST)

            if lu is not None:
                if self._left_upper.update(lu) and lw is not None:
                    punch_events.append((lw, "UPPER_R"))
                    self._lu_fire_time = now
            if ru is not None:
                if self._right_upper.update(ru) and rw is not None:
                    punch_events.append((rw, "UPPER_L"))
                    self._ru_fire_time = now

            # Hook: shoulder abduction angle using synthetic point below shoulder
            # Avoids hip landmark (often low visibility). At rest ≈ 0-30°, hook ≈ 90°
            def _gancho_angle(sh: int, el: int) -> Optional[float]:
                s, e = landmarks[sh], landmarks[el]
                if min(s.visibility, e.visibility) < MIN_VISIBILITY:
                    return None
                below_sh = (s.x, s.y + 0.5, s.z)
                return calc_angle(below_sh, (s.x, s.y, s.z), (e.x, e.y, e.z))

            lg = _gancho_angle(LEFT_SHOULDER,  LEFT_ELBOW)
            rg = _gancho_angle(RIGHT_SHOULDER, RIGHT_ELBOW)

            if lg is not None:
                if self._left_gancho.update(lg) and lw is not None:
                    if self._last_la < GANCHO_ELBOW_MAX:
                        punch_events.append((lw, "GANCHO_R"))
                        self._lg_fire_time = now
            if rg is not None:
                if self._right_gancho.update(rg) and rw is not None:
                    if self._last_ra < GANCHO_ELBOW_MAX:
                        punch_events.append((rw, "GANCHO_L"))
                        self._rg_fire_time = now

            # Ventanas activas: si el golpe disparó hace <WINDOW s y la muñeca todavía
            # no llegó al target, el hit sigue contando como ese tipo de golpe.
            if lw is not None and now - self._lu_fire_time < UPPER_WINDOW:
                punch_events.append((lw, "UPPER_R"))
            if rw is not None and now - self._ru_fire_time < UPPER_WINDOW:
                punch_events.append((rw, "UPPER_L"))
            if lw is not None and now - self._lg_fire_time < GANCHO_WINDOW:
                punch_events.append((lw, "GANCHO_R"))
            if rw is not None and now - self._rg_fire_time < GANCHO_WINDOW:
                punch_events.append((rw, "GANCHO_L"))
            if rw is not None and now - self._rj_fire_time < JAB_WINDOW:
                punch_events.append((rw, "JAB"))
            if lw is not None and now - self._lc_fire_time < CROSS_WINDOW:
                punch_events.append((lw, "CROSS"))

        # Hit detection — only active target, no timeout
        # Grace period: ignore all punch events for TARGET_REACTION_DELAY s after spawn
        # to prevent arms already in motion from instantly registering a hit.
        t = self._target
        if t and not t.hit and now - t.spawn_time >= TARGET_REACTION_DELAY:
            in_range = [(wp, det) for wp, det in punch_events
                        if distance_2d(wp, t.center) <= t.radius + HIT_SLOP]
            if in_range:
                target_group = _PUNCH_GROUP[t.punch_type]
                # Prefer same-group event; fall back to first in range
                chosen = next(
                    (e for e in in_range if _PUNCH_GROUP[e[1]] == target_group),
                    in_range[0]
                )
                _, detected = chosen
                t.hit         = True
                t.hit_time    = now
                t.hit_correct = (_PUNCH_GROUP[detected] == target_group)
                self._spawn_after  = now + HIT_LINGER
                if t.hit_correct:
                    self._score += 10
                    self._ripples.append((*t.center, now, True))
                    self._popups.append(_Popup(t.center[0], t.center[1] - t.radius,
                                               "+10", YELLOW))
                else:
                    self._ripples.append((*t.center, now, False))
                    self._popups.append(_Popup(t.center[0], t.center[1] - t.radius,
                                               "MAL", RED))

        # Prune effects
        self._ripples = [(x, y, b, ok) for x, y, b, ok in self._ripples
                         if now - b < 0.45]
        self._popups  = [p for p in self._popups if p.alive]

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, frame: np.ndarray) -> None:
        now = time.perf_counter()

        # Target
        if self._target:
            t = self._target
            draw_target(frame, t.center, t.radius, t.color, hit=t.hit)
            if not t.hit:
                self._draw_punch_label(frame, t)

        # Ripple effects
        for x, y, born, ok in self._ripples:
            age   = now - born
            r     = int(26 + age * 120)
            color = CYAN if ok else RED
            alpha = max(0.0, 1.0 - age / 0.45)
            if alpha > 0.05:
                ov = frame.copy()
                cv2.circle(ov, (x, y), r, color, 2, cv2.LINE_AA)
                cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)

        # Floating popups
        for p in self._popups:
            if p.alpha > 0.05:
                ov = frame.copy()
                draw_text(ov, p.text, (p.x - 30, p.render_y),
                          scale=0.65, color=p.color, thickness=2)
                cv2.addWeighted(ov, p.alpha, frame, 1 - p.alpha, 0, frame)

        # Wrist cursors
        for pt in self._wrists:
            draw_wrist_cursor(frame, pt, color=YELLOW)

        # Score (top-left)
        draw_panel(frame, (0, 0, 175, 50), color=(10, 10, 40), alpha=0.65)
        draw_text(frame, f"SCORE: {self._score}", (10, 35), scale=0.85, color=YELLOW)

    @staticmethod
    def _draw_punch_label(frame: np.ndarray, t: "_Target") -> None:
        label = t.punch_type
        scale = 0.6
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
        tx = t.center[0] - tw // 2
        ty = t.center[1] + th // 2
        cv2.putText(frame, label, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, label, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, WHITE, 1, cv2.LINE_AA)

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "boxing"
