import time
from typing import Optional, List, Tuple

import cv2
import numpy as np

from games.base_game import BaseGame
from core.renderer import (
    draw_target, draw_text, draw_panel, draw_wrist_cursor, draw_progress_bar,
    WHITE, RED, GREEN, YELLOW, CYAN, ORANGE,
)
from core.video_player import VideoPlayer
from utils.landmarks import (
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_SHOULDER, LEFT_ELBOW,
    RIGHT_SHOULDER, RIGHT_ELBOW,
    NOSE,
)
from utils.math_utils import landmark_to_px, distance_2d, calc_angle
from utils.punch_tracker import ArmPunchState, DodgeDetector

# ═══════════════════════════════════════════════════════════════════════════════
# CALIBRACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
TARGET_RADIUS    = 80
HIT_SLOP         = 30
TARGET_LIFE_SECS = 2.0   # duración por defecto; sobreescribible por entrada del schedule
HIT_LINGER       = 0.45
DODGE_WINDOW     = 1.8
DODGE_RESULT_T   = 1.2

GUARD_ANGLE    = 90.0
IMPACT_ANGLE   = 150.0
RETURN_ANGLE   = 130.0
MIN_VISIBILITY = 0.5

UPPER_GUARD_ANGLE  = 60.0
UPPER_IMPACT_ANGLE = 120.0
UPPER_RETURN_ANGLE =  90.0

HOOK_GUARD_ANGLE  =  45.0
HOOK_IMPACT_ANGLE =  60.0
HOOK_RETURN_ANGLE =  58.0
GANCHO_ELBOW_MAX  = 153.0

GANCHO_WINDOW  = 0.3
UPPER_WINDOW   = 0.3
JAB_WINDOW     = 0.3
CROSS_WINDOW   = 0.3
TARGET_REACTION_DELAY = 0.35
ENTRY_DURATION        = 0.25   # segundos que tarda el círculo en escalar de 0 a tamaño completo

# ── Posiciones fijas por tipo de golpe (frame 640×480) ──────────────────────
PUNCH_POS = {
    "JAB":      (160, 240),   # lado izquierdo, altura media  (puño der en espejo)
    "CROSS":    (480, 240),   # lado derecho,   altura media  (puño izq en espejo)
    "UPPER_R":  (480, 140),   # lado derecho,   zona alta
    "UPPER_L":  (160, 140),   # lado izquierdo, zona alta
    "GANCHO_L": (535, 255),   # lado derecho extremo, altura media
    "GANCHO_R": (105, 255),   # lado izquierdo extremo, altura media
}

# ═══════════════════════════════════════════════════════════════════════════════

PUNCH_COLOR = {
    "JAB":      ( 50, 210,  50),
    "CROSS":    (  0, 140, 255),
    "UPPER_L":  (180,  50, 255),
    "UPPER_R":  (180,  50, 255),
    "GANCHO_L": (  0,  80, 255),
    "GANCHO_R": (  0,  80, 255),
}

PUNCH_LABEL_ES = {
    "JAB":      "JAB",
    "CROSS":    "CROSS",
    "UPPER_L":  "UPPER IZQ",
    "UPPER_R":  "UPPER DER",
    "GANCHO_L": "GANCHO IZQ",
    "GANCHO_R": "GANCHO DER",
}

_PUNCH_GROUP = {
    "JAB":      "rw",
    "UPPER_L":  "rw",
    "GANCHO_L": "rw",
    "CROSS":    "lw",
    "UPPER_R":  "lw",
    "GANCHO_R": "lw",
}

DODGE_HINT = {
    "IZQUIERDA": "ESQUIVA IZQ!",
    "DERECHA":   "ESQUIVA DER!",
    "AGACHA":    "AGACHA!",
}

# ── Module definitions ─────────────────────────────────────────────────────────
# Cada entrada del schedule: (segundos_video, [golpes_simultáneos, ...])
# Todos los golpes de una entrada aparecen a la vez. DODGE aparece al final.
BOXING_MODULES = [
    {
        "video": "assets/videos/box/box1.mp4",
        "name":  "Modulo 1 - Jab y Cross",
        "schedule": [
            (1.8,  ["JAB"]),
            (3.3,  ["CROSS"]),
            (4.5,  ["JAB"]),
            (5.8,  ["CROSS"]),
            (7.2,  ["JAB"]),
            (8.5,  ["CROSS"]),
            (10.0, ["JAB"], 2.0),
            (11.0, ["CROSS"],2.0),
        ],
    },
    {
        "video": "assets/videos/box/box2.mp4",
        "name":  "Modulo 2 - Ganchos",
        "schedule": [
            (1.5,  ["GANCHO_L"]),
            (3.1,  ["GANCHO_R"]),
            (4.4,  ["GANCHO_L"]),
            (5.8,  ["GANCHO_R"]),
            (7.3,  ["GANCHO_L"]),
            (8.8,  ["GANCHO_R"]),
            (10.3, ["GANCHO_L"], 2.0),
            (11.2, ["GANCHO_R"], 1.7),
        ],
    },
    {
        "video": "assets/videos/box/box3.mp4",
        "name":  "Modulo 3 - Uppercuts",
        "schedule": [
            (1.2,  ["UPPER_L"]),
            (2.8,  ["UPPER_R"]),
            (4.3,  ["UPPER_L"]),
            (5.7,  ["UPPER_R"]),
            (7.2,  ["UPPER_L"]),
            (8.8,  ["UPPER_R"]),
        ],
    },
    {
        "video": "assets/videos/box/box4.mp4",
        "name":  "Modulo 4 - Jab+Cross+Esquive",
        "schedule": [
            (1.8,  ["JAB", "CROSS", "DODGE"],2.1),
            (3.9,  ["JAB", "CROSS", "DODGE"],2.5),
            (6.4,  ["JAB", "CROSS", "DODGE"],2.3),
            (8.7,  ["JAB", "CROSS", "DODGE"],2.4),
            (11.2, ["JAB", "CROSS", "DODGE"],1.8),
        ],
    },
    {
        "video": "assets/videos/box/box5.mp4",
        "name":  "Modulo 5 - Combos Mixtos",
        "schedule": [
            (2.0,  ["JAB", "CROSS", "DODGE"]),
            (4.8,  ["UPPER_R"]),
            (5.8, ["UPPER_L", "DODGE"], 1.8),
            
            (7.6,  ["JAB", "CROSS", "DODGE"], 2.0),
            (9.6,  ["UPPER_R"]),
            (11.7, ["UPPER_L", "DODGE"],2.3),
        ],
    },
]


# ── Support classes ────────────────────────────────────────────────────────────
class _Target:
    def __init__(self, cx: int, cy: int, radius: int, punch_type: str,
                 life_secs: float = TARGET_LIFE_SECS):
        self.center      = (cx, cy)
        self.radius      = radius
        self.punch_type  = punch_type
        self.color       = PUNCH_COLOR[punch_type]
        self.life_secs   = life_secs
        self.hit         = False
        self.hit_time:   Optional[float] = None
        self.hit_correct = False
        self.spawn_time  = time.perf_counter()
        self.expired     = False


class _Popup:
    DURATION = 0.5

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


# ── Game class ─────────────────────────────────────────────────────────────────
class BoxingGame(BaseGame):
    def __init__(self, frame_w: int = 640, frame_h: int = 480):
        self._w = frame_w
        self._h = frame_h
        self._left_arm     = ArmPunchState(GUARD_ANGLE,       IMPACT_ANGLE,       RETURN_ANGLE)
        self._right_arm    = ArmPunchState(GUARD_ANGLE,       IMPACT_ANGLE,       RETURN_ANGLE)
        self._left_upper   = ArmPunchState(UPPER_GUARD_ANGLE, UPPER_IMPACT_ANGLE, UPPER_RETURN_ANGLE)
        self._right_upper  = ArmPunchState(UPPER_GUARD_ANGLE, UPPER_IMPACT_ANGLE, UPPER_RETURN_ANGLE)
        self._left_gancho  = ArmPunchState(HOOK_GUARD_ANGLE,  HOOK_IMPACT_ANGLE,  HOOK_RETURN_ANGLE)
        self._right_gancho = ArmPunchState(HOOK_GUARD_ANGLE,  HOOK_IMPACT_ANGLE,  HOOK_RETURN_ANGLE)
        self._dodge_det    = DodgeDetector()
        self._video: Optional[VideoPlayer] = None
        self._dodge_was_armed = False
        self._dodge_resolved  = True
        self._next: Optional[str] = None
        self.reset()

    # ── State management ──────────────────────────────────────────────────────
    def reset(self) -> None:
        self._next           = None
        self._score          = 0
        self._targets: List[_Target] = []
        self._popups:  List[_Popup]  = []
        self._ripples: List[Tuple]   = []
        self._wrists         = [None, None]
        self._last_la        = 0.0
        self._last_ra        = 0.0
        self._lg_fire_time   = -1.0
        self._rg_fire_time   = -1.0
        self._lu_fire_time   = -1.0
        self._ru_fire_time   = -1.0
        self._rj_fire_time   = -1.0
        self._lc_fire_time   = -1.0
        self._mod_idx         = 0
        self._sched_idx       = 0
        self._dodge_was_armed = False
        self._dodge_resolved  = True
        self._dodge_active    = False
        self._dodge_dir      = ""
        self._dodge_armed_t  = 0.0
        self._dodge_result: Optional[bool] = None
        self._dodge_result_t = 0.0
        self._left_arm.reset()
        self._right_arm.reset()
        self._left_upper.reset()
        self._right_upper.reset()
        self._left_gancho.reset()
        self._right_gancho.reset()
        if self._video:
            self._video.stop()
        self._video = None
        self._load_module(0)

    def _load_module(self, idx: int) -> None:
        if self._video:
            self._video.stop()
        mod = BOXING_MODULES[idx]
        self._video = VideoPlayer(mod["video"])
        if not self._video.load():
            self._video = None
        else:
            self._video.start()
        self._sched_idx       = 0
        self._targets         = []
        self._dodge_was_armed = False
        self._dodge_resolved  = True
        self._dodge_active    = False

    def _advance_module(self) -> None:
        self._mod_idx += 1
        if self._mod_idx >= len(BOXING_MODULES):
            if self._video:
                self._video.stop()
            self._video = None
            self._next  = "menu"
        else:
            self._load_module(self._mod_idx)

    # ── Spawn ─────────────────────────────────────────────────────────────────
    def _spawn_targets(self, punch_types: list) -> None:
        """Spawn all punch types simultaneously at their fixed positions."""
        self._targets = [
            _Target(*PUNCH_POS[pt], TARGET_RADIUS, pt)
            for pt in punch_types
            if pt in PUNCH_POS
        ]

    def _all_targets_done(self, now: float) -> bool:
        if not self._targets:
            return True
        return all(
            t.expired or (t.hit and t.hit_time is not None and now - t.hit_time >= HIT_LINGER)
            for t in self._targets
        )

    def _all_wave_done(self, now: float) -> bool:
        """Targets AND dodge (if any) must both be resolved before next wave."""
        return self._all_targets_done(now) and (not self._dodge_was_armed or self._dodge_resolved)

    def _arm_dodge(self, now: float) -> None:
        self._dodge_det.arm()
        self._dodge_dir      = "AGACHA"
        self._dodge_armed_t  = now
        self._dodge_active   = True
        self._dodge_was_armed = True
        self._dodge_resolved  = False

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self, frame: np.ndarray, landmarks: Optional[list],
               frame_w: int, frame_h: int) -> None:
        now = time.perf_counter()

        if self._next:
            return

        if self._video and self._video.is_done:
            self._advance_module()
            return

        vt = self._video.current_time if self._video else 0.0

        # Nose tracking for dodge detector (always, so EMA stays warm)
        if landmarks:
            nose = landmarks[NOSE]
            self._dodge_det.track(nose.x, nose.y)

        # ── Active dodge window (coexiste con los círculos activos) ──────────
        if self._dodge_active:
            detected = False
            if landmarks:
                nose = landmarks[NOSE]
                detected = self._dodge_det.detect(nose.x, nose.y, self._dodge_dir)
            if detected:
                self._score          += 25
                self._dodge_result    = True
                self._dodge_result_t  = now
                self._dodge_active    = False
                self._dodge_resolved  = True
            elif now - self._dodge_armed_t > DODGE_WINDOW:
                self._dodge_result    = False
                self._dodge_result_t  = now
                self._dodge_active    = False
                self._dodge_resolved  = True
            # sin return — continúa a detección de golpes y targets

        # ── Target expiry ─────────────────────────────────────────────────────
        for t in self._targets:
            if not t.hit and not t.expired and now - t.spawn_time > t.life_secs:
                t.expired = True
                cx, cy = t.center
                self._popups.append(_Popup(cx, cy, "MISS", RED))
                self._ripples.append((cx, cy, now, False))

        # ── Limpiar targets resueltos (hit+linger o expirados) ───────────────
        self._targets = [
            t for t in self._targets
            if not t.expired and
               not (t.hit and t.hit_time is not None and now - t.hit_time >= HIT_LINGER)
        ]

        # ── Schedule: cada entrada dispara en cuanto pasa su timestamp ────────
        # No depende del estado de los targets actuales — el video manda.
        sched = BOXING_MODULES[self._mod_idx]["schedule"]
        while (self._sched_idx < len(sched) and
               vt >= sched[self._sched_idx][0]):
            entry = sched[self._sched_idx]
            steps     = entry[1]
            life_secs = entry[2] if len(entry) > 2 else TARGET_LIFE_SECS
            self._sched_idx += 1
            self._targets.extend(
                _Target(*PUNCH_POS[pt], TARGET_RADIUS, pt, life_secs)
                for pt in steps
                if pt in PUNCH_POS
            )
            if "DODGE" in steps:
                self._arm_dodge(now)

        # ── Landmark extraction ───────────────────────────────────────────────
        self._wrists = [None, None]
        lw = rw = None
        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST],  frame_w, frame_h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], frame_w, frame_h)
            self._wrists = [lw, rw]

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
                    self._lg_fire_time = -1.0
            if ra is not None:
                self._last_ra = ra
                if self._right_arm.update(ra) and rw is not None:
                    punch_events.append((rw, "JAB"))
                    self._rj_fire_time = now
                    self._rg_fire_time = -1.0

            def _upper_angle(el: int, wr: int) -> Optional[float]:
                e, w = landmarks[el], landmarks[wr]
                if min(e.visibility, w.visibility) < MIN_VISIBILITY:
                    return None
                below = (e.x, e.y + 0.5, e.z)
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

        # ── Hit detection — todos los targets activos ─────────────────────────
        for t in self._targets:
            if t.hit or t.expired:
                continue
            if now - t.spawn_time < TARGET_REACTION_DELAY:
                continue
            in_range = [(wp, det) for wp, det in punch_events
                        if distance_2d(wp, t.center) <= t.radius + HIT_SLOP]
            if in_range:
                target_group = _PUNCH_GROUP[t.punch_type]
                chosen = next(
                    (e for e in in_range if _PUNCH_GROUP[e[1]] == target_group),
                    in_range[0],
                )
                _, detected = chosen
                t.hit         = True
                t.hit_time    = now
                t.hit_correct = (_PUNCH_GROUP[detected] == target_group)
                cx, cy = t.center
                if t.hit_correct:
                    self._score += 10
                    self._ripples.append((cx, cy, now, True))
                    self._popups.append(_Popup(cx, cy, "+10", YELLOW))
                else:
                    self._ripples.append((cx, cy, now, False))
                    self._popups.append(_Popup(cx, cy, "MAL", RED))

        self._ripples = [(x, y, b, ok) for x, y, b, ok in self._ripples if now - b < 0.45]
        self._popups  = [p for p in self._popups if p.alive]

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, frame: np.ndarray) -> None:
        now = time.perf_counter()

        # Todos los targets activos
        for t in self._targets:
            age = now - t.spawn_time

            # Entrada spring: 0 → 110% en 0.18s → settle 100% en 0.25s
            if age < 0.18:
                entry_scale = age / 0.18 * 1.1
            elif age < ENTRY_DURATION:
                entry_scale = 1.1 - 0.1 * ((age - 0.18) / (ENTRY_DURATION - 0.18))
            else:
                entry_scale = 1.0
            draw_radius = max(1, int(t.radius * entry_scale))

            # Color vira a rojo en el último 30% de vida (aprox. último segundo)
            if not t.hit and not t.expired and age >= t.life_secs * 0.70:
                u = min(1.0, (age - t.life_secs * 0.70) / (t.life_secs * 0.30))
                draw_color = (
                    int(t.color[0] * (1 - u)),                   # B → 0
                    int(t.color[1] * (1 - u)),                   # G → 0
                    int(t.color[2] + (255 - t.color[2]) * u),    # R → 255
                )
            else:
                draw_color = t.color

            draw_target(frame, t.center, draw_radius, draw_color, hit=t.hit)
            if not t.hit and not t.expired and entry_scale >= 1.0:
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

        # Active dodge overlay
        if self._dodge_active:
            elapsed  = now - self._dodge_armed_t
            ratio    = max(0.0, 1.0 - elapsed / DODGE_WINDOW)
            hint_txt = DODGE_HINT.get(self._dodge_dir, "ESQUIVA!")
            ov = frame.copy()
            cv2.rectangle(ov, (0, 0), (self._w, self._h), (0, 0, 180), -1)
            cv2.addWeighted(ov, 0.18, frame, 0.82, 0, frame)
            (tw, _), _ = cv2.getTextSize(hint_txt, cv2.FONT_HERSHEY_SIMPLEX, 1.3, 3)
            draw_text(frame, hint_txt,
                      (self._w // 2 - tw // 2, self._h // 2),
                      scale=1.3, color=RED, thickness=3)
            draw_progress_bar(frame,
                              (self._w // 2 - 100, self._h // 2 + 20),
                              (200, 12), ratio, 1.0, fg_color=RED)

        # Dodge result flash
        if self._dodge_result is not None:
            age = now - self._dodge_result_t
            if age < DODGE_RESULT_T:
                alpha = max(0.0, 1.0 - age / DODGE_RESULT_T)
                color = GREEN if self._dodge_result else RED
                txt   = "BIEN ESQUIVADO!" if self._dodge_result else "GOLPEADO!"
                ov = frame.copy()
                (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)
                draw_text(ov, txt,
                          (self._w // 2 - tw // 2, self._h // 2 + 60),
                          scale=1.1, color=color, thickness=3)
                cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)
            else:
                self._dodge_result = None

        # Wrist cursors
        for pt in self._wrists:
            draw_wrist_cursor(frame, pt, color=YELLOW)

        # HUD — score
        draw_panel(frame, (0, 0, 190, 50), color=(10, 10, 40), alpha=0.65)
        draw_text(frame, f"SCORE: {self._score}", (10, 35), scale=0.85, color=YELLOW)

        # HUD — module name
        mod_name = BOXING_MODULES[self._mod_idx]["name"] if self._mod_idx < len(BOXING_MODULES) else ""
        (cw, _), _ = cv2.getTextSize(mod_name, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
        draw_panel(frame, (self._w - cw - 20, 0, cw + 20, 40), color=(10, 10, 40), alpha=0.65)
        draw_text(frame, mod_name, (self._w - cw - 10, 28), scale=0.52, color=CYAN, thickness=1)

    @staticmethod
    def _draw_punch_label(frame: np.ndarray, t: "_Target") -> None:
        label = PUNCH_LABEL_ES.get(t.punch_type, t.punch_type)
        scale = 0.55
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
        tx = t.center[0] - tw // 2
        ty = t.center[1] + th // 2
        cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    (255, 255, 255), 1, cv2.LINE_AA)

    def get_video_frame(self) -> Optional[np.ndarray]:
        return self._video.read_frame() if self._video else None

    @property
    def next_state(self) -> Optional[str]:
        return self._next

    @property
    def name(self) -> str:
        return "boxing"
