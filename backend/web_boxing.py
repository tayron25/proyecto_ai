import time
from dataclasses import dataclass, field
from typing import Optional

from games.boxing import (
    BOXING_MODULES,
    CROSS_WINDOW,
    DODGE_HINT,
    DODGE_RESULT_T,
    DODGE_WINDOW,
    ENTRY_DURATION,
    GANCHO_ELBOW_MAX,
    GANCHO_WINDOW,
    GUARD_ANGLE,
    HIT_LINGER,
    HIT_SLOP,
    IMPACT_ANGLE,
    JAB_WINDOW,
    MIN_VISIBILITY,
    PUNCH_COLOR,
    PUNCH_LABEL_ES,
    PUNCH_POS,
    RETURN_ANGLE,
    TARGET_RADIUS,
    TARGET_LIFE_SECS,
    TARGET_REACTION_DELAY,
    UPPER_GUARD_ANGLE,
    UPPER_IMPACT_ANGLE,
    UPPER_RETURN_ANGLE,
    UPPER_WINDOW,
    HOOK_GUARD_ANGLE,
    HOOK_IMPACT_ANGLE,
    HOOK_RETURN_ANGLE,
)
from utils.landmarks import (
    LEFT_ELBOW,
    LEFT_SHOULDER,
    LEFT_WRIST,
    NOSE,
    RIGHT_ELBOW,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)
from utils.math_utils import calc_angle, distance_2d, landmark_to_px
from utils.punch_tracker import ArmPunchState, DodgeDetector

_PUNCH_GROUP = {
    "JAB": "rw",
    "UPPER_L": "rw",
    "GANCHO_L": "rw",
    "CROSS": "lw",
    "UPPER_R": "lw",
    "GANCHO_R": "lw",
}


@dataclass
class Target:
    id: int
    center: tuple[int, int]
    radius: int
    punch_type: str
    life_secs: float
    color: tuple[int, int, int]
    spawn_time: float = field(default_factory=time.perf_counter)
    hit: bool = False
    hit_time: Optional[float] = None
    hit_correct: bool = False
    expired: bool = False


@dataclass
class Popup:
    text: str
    x: int
    y: int
    color: str
    born: float = field(default_factory=time.perf_counter)

    @property
    def alive(self) -> bool:
        return time.perf_counter() - self.born < 0.5

    def to_json(self) -> dict:
        age = time.perf_counter() - self.born
        return {
            "text": self.text,
            "x": self.x,
            "y": int(self.y - age * 80),
            "kind": self.color,
            "alpha": max(0.0, 1.0 - age / 0.5),
        }


@dataclass
class Ripple:
    x: int
    y: int
    born: float
    ok: bool

    def to_json(self) -> dict:
        age = time.perf_counter() - self.born
        return {
            "x": self.x,
            "y": self.y,
            "radius": int(26 + age * 120),
            "ok": self.ok,
            "alpha": max(0.0, 1.0 - age / 0.45),
        }


class WebBoxingGame:
    def __init__(self, frame_w: int = 640, frame_h: int = 480) -> None:
        self._w = frame_w
        self._h = frame_h
        self._target_id = 0
        self._left_arm = ArmPunchState(GUARD_ANGLE, IMPACT_ANGLE, RETURN_ANGLE)
        self._right_arm = ArmPunchState(GUARD_ANGLE, IMPACT_ANGLE, RETURN_ANGLE)
        self._left_upper = ArmPunchState(UPPER_GUARD_ANGLE, UPPER_IMPACT_ANGLE, UPPER_RETURN_ANGLE)
        self._right_upper = ArmPunchState(UPPER_GUARD_ANGLE, UPPER_IMPACT_ANGLE, UPPER_RETURN_ANGLE)
        self._left_gancho = ArmPunchState(HOOK_GUARD_ANGLE, HOOK_IMPACT_ANGLE, HOOK_RETURN_ANGLE)
        self._right_gancho = ArmPunchState(HOOK_GUARD_ANGLE, HOOK_IMPACT_ANGLE, HOOK_RETURN_ANGLE)
        self._dodge_det = DodgeDetector()
        self.reset()

    def reset(self) -> None:
        self._next: Optional[str] = None
        self._score = 0
        self._target_id = 0
        self._targets: list[Target] = []
        self._popups: list[Popup] = []
        self._ripples: list[Ripple] = []
        self._wrists: list[Optional[tuple[int, int]]] = [None, None]
        self._last_la = 0.0
        self._last_ra = 0.0
        self._lg_fire_time = -1.0
        self._rg_fire_time = -1.0
        self._lu_fire_time = -1.0
        self._ru_fire_time = -1.0
        self._rj_fire_time = -1.0
        self._lc_fire_time = -1.0
        self._mod_idx = 0
        self._sched_idx = 0
        self._dodge_was_armed = False
        self._dodge_resolved = True
        self._dodge_active = False
        self._dodge_dir = ""
        self._dodge_armed_t = 0.0
        self._dodge_result: Optional[bool] = None
        self._dodge_result_t = 0.0
        self._module_correct = 0
        self._module_failed = 0
        self._combo = 0
        self._best_combo = 0
        self._module_results: list[dict] = []
        self._last_result: Optional[dict] = None
        for tracker in (
            self._left_arm,
            self._right_arm,
            self._left_upper,
            self._right_upper,
            self._left_gancho,
            self._right_gancho,
        ):
            tracker.reset()

    def advance_module(self) -> None:
        self._last_result = self._finish_module_result()
        self._mod_idx += 1
        if self._mod_idx >= len(BOXING_MODULES):
            self._next = "summary"
            self._targets = []
            self._popups = []
            self._ripples = []
            return
        self._sched_idx = 0
        self._targets = []
        self._popups = []
        self._ripples = []
        self._module_correct = 0
        self._module_failed = 0
        self._combo = 0
        self._best_combo = 0
        self._dodge_was_armed = False
        self._dodge_resolved = True
        self._dodge_active = False
        self._dodge_result = None

    def update(self, landmarks: Optional[list], video_time: float) -> None:
        now = time.perf_counter()
        if self._next:
            return

        if landmarks:
            nose = landmarks[NOSE]
            self._dodge_det.track(nose.x, nose.y)

        if self._dodge_active:
            detected = False
            if landmarks:
                nose = landmarks[NOSE]
                detected = self._dodge_det.detect(nose.x, nose.y, self._dodge_dir)
            if detected:
                self._score += 25
                self._register_success()
                self._dodge_result = True
                self._dodge_result_t = now
                self._dodge_active = False
                self._dodge_resolved = True
            elif now - self._dodge_armed_t > DODGE_WINDOW:
                self._register_failure()
                self._dodge_result = False
                self._dodge_result_t = now
                self._dodge_active = False
                self._dodge_resolved = True

        for target in self._targets:
            if not target.hit and not target.expired and now - target.spawn_time > target.life_secs:
                target.expired = True
                self._register_failure()
                self._popups.append(Popup("MISS", target.center[0], target.center[1], "bad"))
                self._ripples.append(Ripple(target.center[0], target.center[1], now, False))

        self._targets = [
            target
            for target in self._targets
            if not target.expired
            and not (target.hit and target.hit_time is not None and now - target.hit_time >= HIT_LINGER)
        ]

        sched = BOXING_MODULES[self._mod_idx]["schedule"]
        while self._sched_idx < len(sched) and video_time >= sched[self._sched_idx][0]:
            entry = sched[self._sched_idx]
            steps = entry[1]
            life_secs = entry[2] if len(entry) > 2 else TARGET_LIFE_SECS
            self._sched_idx += 1
            for punch_type in steps:
                if punch_type in PUNCH_POS:
                    self._targets.append(self._new_target(punch_type, life_secs))
            if "DODGE" in steps:
                self._arm_dodge(now)

        self._wrists = [None, None]
        punch_events: list[tuple[tuple[int, int], str]] = []
        if landmarks:
            lw = landmark_to_px(landmarks[LEFT_WRIST], self._w, self._h)
            rw = landmark_to_px(landmarks[RIGHT_WRIST], self._w, self._h)
            self._wrists = [lw, rw]
            punch_events = self._detect_punches(landmarks, lw, rw, now)

        for target in self._targets:
            if target.hit or target.expired or now - target.spawn_time < TARGET_REACTION_DELAY:
                continue
            in_range = [
                (wp, detected)
                for wp, detected in punch_events
                if distance_2d(wp, target.center) <= target.radius + HIT_SLOP
            ]
            if not in_range:
                continue
            target_group = _PUNCH_GROUP[target.punch_type]
            chosen = next((event for event in in_range if _PUNCH_GROUP[event[1]] == target_group), in_range[0])
            detected = chosen[1]
            target.hit = True
            target.hit_time = now
            target.hit_correct = _PUNCH_GROUP[detected] == target_group
            if target.hit_correct:
                self._score += 10
                self._register_success()
                self._popups.append(Popup("+10", target.center[0], target.center[1], "good"))
                self._ripples.append(Ripple(target.center[0], target.center[1], now, True))
            else:
                self._register_failure()
                self._popups.append(Popup("MAL", target.center[0], target.center[1], "bad"))
                self._ripples.append(Ripple(target.center[0], target.center[1], now, False))

        self._ripples = [ripple for ripple in self._ripples if now - ripple.born < 0.45]
        self._popups = [popup for popup in self._popups if popup.alive]
        if self._dodge_result is not None and now - self._dodge_result_t >= DODGE_RESULT_T:
            self._dodge_result = None

    def _detect_punches(
        self,
        landmarks: list,
        lw: tuple[int, int],
        rw: tuple[int, int],
        now: float,
    ) -> list[tuple[tuple[int, int], str]]:
        events: list[tuple[tuple[int, int], str]] = []

        def arm_angle(sh: int, el: int, wr: int) -> Optional[float]:
            s, e, w = landmarks[sh], landmarks[el], landmarks[wr]
            if min(s.visibility, e.visibility, w.visibility) < MIN_VISIBILITY:
                return None
            return calc_angle((s.x, s.y, s.z), (e.x, e.y, e.z), (w.x, w.y, w.z))

        la = arm_angle(LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST)
        ra = arm_angle(RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST)

        if la is not None:
            self._last_la = la
            if self._left_arm.update(la):
                events.append((lw, "CROSS"))
                self._lc_fire_time = now
                self._lg_fire_time = -1.0
        if ra is not None:
            self._last_ra = ra
            if self._right_arm.update(ra):
                events.append((rw, "JAB"))
                self._rj_fire_time = now
                self._rg_fire_time = -1.0

        def upper_angle(el: int, wr: int) -> Optional[float]:
            e, w = landmarks[el], landmarks[wr]
            if min(e.visibility, w.visibility) < MIN_VISIBILITY:
                return None
            below = (e.x, e.y + 0.5, e.z)
            return calc_angle(below, (e.x, e.y, e.z), (w.x, w.y, w.z))

        lu = upper_angle(LEFT_ELBOW, LEFT_WRIST)
        ru = upper_angle(RIGHT_ELBOW, RIGHT_WRIST)
        if lu is not None and self._left_upper.update(lu):
            events.append((lw, "UPPER_R"))
            self._lu_fire_time = now
        if ru is not None and self._right_upper.update(ru):
            events.append((rw, "UPPER_L"))
            self._ru_fire_time = now

        def gancho_angle(sh: int, el: int) -> Optional[float]:
            s, e = landmarks[sh], landmarks[el]
            if min(s.visibility, e.visibility) < MIN_VISIBILITY:
                return None
            below_sh = (s.x, s.y + 0.5, s.z)
            return calc_angle(below_sh, (s.x, s.y, s.z), (e.x, e.y, e.z))

        lg = gancho_angle(LEFT_SHOULDER, LEFT_ELBOW)
        rg = gancho_angle(RIGHT_SHOULDER, RIGHT_ELBOW)
        if lg is not None and self._left_gancho.update(lg) and self._last_la < GANCHO_ELBOW_MAX:
            events.append((lw, "GANCHO_R"))
            self._lg_fire_time = now
        if rg is not None and self._right_gancho.update(rg) and self._last_ra < GANCHO_ELBOW_MAX:
            events.append((rw, "GANCHO_L"))
            self._rg_fire_time = now

        recent = (
            (self._lu_fire_time, lw, "UPPER_R", UPPER_WINDOW),
            (self._ru_fire_time, rw, "UPPER_L", UPPER_WINDOW),
            (self._lg_fire_time, lw, "GANCHO_R", GANCHO_WINDOW),
            (self._rg_fire_time, rw, "GANCHO_L", GANCHO_WINDOW),
            (self._rj_fire_time, rw, "JAB", JAB_WINDOW),
            (self._lc_fire_time, lw, "CROSS", CROSS_WINDOW),
        )
        for fired_at, wrist, punch_type, window in recent:
            if now - fired_at < window:
                events.append((wrist, punch_type))
        return events

    def _new_target(self, punch_type: str, life_secs: float) -> Target:
        self._target_id += 1
        return Target(
            id=self._target_id,
            center=PUNCH_POS[punch_type],
            radius=TARGET_RADIUS,
            punch_type=punch_type,
            life_secs=life_secs,
            color=PUNCH_COLOR[punch_type],
        )

    def _arm_dodge(self, now: float) -> None:
        self._dodge_det.arm()
        self._dodge_dir = "AGACHA"
        self._dodge_armed_t = now
        self._dodge_active = True
        self._dodge_was_armed = True
        self._dodge_resolved = False

    def _register_success(self) -> None:
        self._module_correct += 1
        self._combo += 1
        self._best_combo = max(self._best_combo, self._combo)

    def _register_failure(self) -> None:
        self._module_failed += 1
        self._combo = 0

    def _expected_actions(self, idx: Optional[int] = None) -> int:
        module_idx = self._mod_idx if idx is None else idx
        if module_idx < 0 or module_idx >= len(BOXING_MODULES):
            return 0
        total = 0
        for entry in BOXING_MODULES[module_idx]["schedule"]:
            total += sum(1 for step in entry[1] if step in PUNCH_POS or step == "DODGE")
        return total

    def _module_percent(self) -> int:
        expected = self._expected_actions()
        if expected <= 0:
            return 0
        return round(min(1.0, self._module_correct / expected) * 100)

    @staticmethod
    def _rating(percent: int) -> str:
        if percent >= 90:
            return "EXCELENTE"
        if percent >= 75:
            return "MUY BIEN"
        if percent >= 60:
            return "BIEN"
        return "PUEDES HACERLO MEJOR"

    @staticmethod
    def _summary_message(percent: int) -> str:
        return WebBoxingGame._rating(percent)

    def _finish_module_result(self) -> dict:
        percent = self._module_percent()
        result = {
            "id": f"{self._mod_idx}-{len(self._module_results)}",
            "index": self._mod_idx,
            "name": BOXING_MODULES[self._mod_idx]["name"],
            "percent": percent,
            "rating": self._rating(percent),
            "correct": self._module_correct,
            "failed": self._module_failed,
            "expected": self._expected_actions(),
            "bestCombo": self._best_combo,
        }
        self._module_results.append(result)
        return result

    def _summary(self) -> dict:
        count = len(self._module_results)
        average = round(sum(result["percent"] for result in self._module_results) / count) if count else 0
        return {
            "average": average,
            "message": self._summary_message(average),
            "results": self._module_results,
        }

    def to_json(self) -> dict:
        module_idx = min(self._mod_idx, len(BOXING_MODULES) - 1)
        module = BOXING_MODULES[module_idx] if 0 <= module_idx < len(BOXING_MODULES) else None
        messages = [popup.to_json() for popup in self._popups]
        if self._dodge_active:
            messages.append({"text": DODGE_HINT.get(self._dodge_dir, "ESQUIVA!"), "x": 320, "y": 240, "kind": "dodge"})
        elif self._dodge_result is not None and time.perf_counter() - self._dodge_result_t < DODGE_RESULT_T:
            messages.append({
                "text": "BIEN ESQUIVADO!" if self._dodge_result else "GOLPEADO!",
                "x": 320,
                "y": 300,
                "kind": "good" if self._dodge_result else "bad",
            })
        now = time.perf_counter()
        return {
            "score": self._score,
            "nextState": self._next,
            "module": {
                "index": module_idx,
                "total": len(BOXING_MODULES),
                "name": module["name"] if module else "",
            },
            "video": None if self._next == "summary" else f"/assets/{module['video'][len('assets/'):]}" if module else None,
            "boxing": {
                "percent": self._module_percent(),
                "combo": self._combo,
                "bestCombo": self._best_combo,
                "correct": self._module_correct,
                "failed": self._module_failed,
                "expected": self._expected_actions(),
                "lastResult": self._last_result,
                "summary": self._summary() if self._next == "summary" else None,
                "ripples": [ripple.to_json() for ripple in self._ripples],
                "dodge": self._dodge_json(now),
            },
            "targets": [
                {
                    "id": target.id,
                    "x": target.center[0],
                    "y": target.center[1],
                    "radius": target.radius,
                    "type": target.punch_type,
                    "label": PUNCH_LABEL_ES.get(target.punch_type, target.punch_type),
                    "color": target.color,
                    "hit": target.hit,
                    "hitCorrect": target.hit_correct,
                    "lifeRatio": max(0.0, 1.0 - (now - target.spawn_time) / target.life_secs),
                    "entryScale": self._entry_scale(now - target.spawn_time),
                }
                for target in self._targets
            ],
            "messages": messages,
        }

    @staticmethod
    def _entry_scale(age: float) -> float:
        if age < 0.18:
            return age / 0.18 * 1.1
        if age < ENTRY_DURATION:
            return 1.1 - 0.1 * ((age - 0.18) / (ENTRY_DURATION - 0.18))
        return 1.0

    def _dodge_json(self, now: float) -> dict:
        result_visible = self._dodge_result is not None and now - self._dodge_result_t < DODGE_RESULT_T
        return {
            "active": self._dodge_active,
            "hint": DODGE_HINT.get(self._dodge_dir, "ESQUIVA!"),
            "progress": max(0.0, 1.0 - (now - self._dodge_armed_t) / DODGE_WINDOW) if self._dodge_active else 0.0,
            "result": self._dodge_result if result_visible else None,
            "resultAlpha": max(0.0, 1.0 - (now - self._dodge_result_t) / DODGE_RESULT_T) if result_visible else 0.0,
        }

    @property
    def next_state(self) -> Optional[str]:
        return self._next
