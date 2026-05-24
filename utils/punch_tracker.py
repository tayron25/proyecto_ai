"""
Arm punch state machine and evasion detection.

ArmPunchState tracks elbow-extension angle through three states:
  GUARD     - elbow angle < _GUARD_THRESH   (arm bent / at rest)
  EXTENDING - angle rising toward full extension
  IMPACT    - angle exceeded _IMPACT_THRESH -> punch fires once

A complete GUARD -> EXTENDING -> IMPACT cycle is required.
A target that spawns under an already-extended arm cannot auto-register.

DodgeDetector tracks nose position with EMA to detect lateral/down
evasion relative to a snapshotted neutral baseline.
"""

from typing import Optional, Tuple

# ── Punch state machine tunables ─────────────────────────────────────────────
_GUARD_THRESH  = 90.0    # (°) arm must drop below this to enter GUARD
_IMPACT_THRESH = 165.0   # (°) arm must reach this to fire the punch
_RETURN_THRESH = 130.0   # (°) arm must retract below this to reset after IMPACT

# ── Dodge tunables ───────────────────────────────────────────────────────────
_EMA_ALPHA       = 0.05
_DODGE_THRESHOLD = 0.08


class ArmPunchState:
    """
    Three-state machine per arm.
    Call update() once per frame with the current elbow angle (degrees).
    Returns True on the single frame the punch fires.
    Thresholds are injected so boxing.py can define them as tuning constants.
    """
    _GUARD     = 0
    _EXTENDING = 1
    _IMPACT    = 2
    _NAMES     = ["GUARD", "EXTENDING", "IMPACT"]

    def __init__(self,
                 guard_thresh:  float = _GUARD_THRESH,
                 impact_thresh: float = _IMPACT_THRESH,
                 return_thresh: float = _RETURN_THRESH) -> None:
        self._gt = guard_thresh
        self._it = impact_thresh
        self._rt = return_thresh
        self._state = self._GUARD

    def update(self, elbow_angle: float) -> bool:
        if self._state == self._GUARD:
            if elbow_angle > self._gt:
                self._state = self._EXTENDING
        elif self._state == self._EXTENDING:
            if elbow_angle >= self._it:
                self._state = self._IMPACT
                return True                      # punch fires here, exactly once
            elif elbow_angle < self._gt:
                self._state = self._GUARD        # aborted extension
        elif self._state == self._IMPACT:
            if elbow_angle < self._rt:
                self._state = self._GUARD        # retracted, ready for next
        return False

    @property
    def state_name(self) -> str:
        return self._NAMES[self._state]

    def reset(self) -> None:
        self._state = self._GUARD


class DodgeDetector:
    """
    Detects evasion moves (lean left/right, duck) relative to a neutral
    nose position tracked with EMA.
    Call track() every frame, arm() when a dodge event begins,
    detect() each frame of the event.
    """

    def __init__(self) -> None:
        self._ema_x: Optional[float] = None
        self._ema_y: Optional[float] = None
        self._neutral: Optional[Tuple[float, float]] = None

    def track(self, nose_x: float, nose_y: float) -> None:
        if self._ema_x is None:
            self._ema_x, self._ema_y = nose_x, nose_y
        else:
            self._ema_x += _EMA_ALPHA * (nose_x - self._ema_x)
            self._ema_y += _EMA_ALPHA * (nose_y - self._ema_y)

    def arm(self) -> None:
        if self._ema_x is not None:
            self._neutral = (self._ema_x, self._ema_y)

    def detect(self, nose_x: float, nose_y: float, direction: str) -> bool:
        if self._neutral is None:
            return False
        nx, ny = self._neutral
        if direction == "IZQUIERDA":
            return nose_x < nx - _DODGE_THRESHOLD
        if direction == "DERECHA":
            return nose_x > nx + _DODGE_THRESHOLD
        if direction == "AGACHA":
            return nose_y > ny + _DODGE_THRESHOLD
        return False
