import time
from typing import Optional

from games.aerobics import (
    AEROBIC_MODULES,
    AEROBICS_VIDEO,
    MODULE_TARGET_REPS,
    MODULE_TIMESTAMPS,
    SUCCESS_FLASH,
    TRANSITION_SECS,
    _extract_data,
)


class WebAerobics:
    def __init__(self, frame_w: int = 640, frame_h: int = 480) -> None:
        self._w = frame_w
        self._h = frame_h
        self.reset()

    def reset(self) -> None:
        self._next: Optional[str] = None
        self._mod_idx = 0
        self._reps = 0
        self._score = 0
        self._module_results: list[dict] = []
        self._last_cp: Optional[str] = None
        self._last_cp_t = 0.0
        self._cur_cp: Optional[str] = None
        self._flash_t = 0.0
        self._data: dict = {}

    def update(self, landmarks: Optional[list], video_time: float, video_ended: bool = False) -> None:
        if self._next:
            return
        if video_ended:
            self._finish_module()
            self._next = "summary"
            return

        new_mod = sum(1 for t in MODULE_TIMESTAMPS if video_time >= t) - 1
        new_mod = max(0, min(new_mod, len(AEROBIC_MODULES) - 1))
        if new_mod != self._mod_idx:
            self._finish_module()
            self._mod_idx = new_mod
            self._reps = 0
            self._last_cp = None
            self._cur_cp = None

        now = time.perf_counter()
        self._data = _extract_data(landmarks, self._w, self._h) if landmarks else {}
        mod = AEROBIC_MODULES[self._mod_idx]
        cp_now = mod["check"](self._data)
        self._cur_cp = cp_now

        if cp_now is not None and cp_now == self._last_cp:
            self._last_cp_t = now
        elif cp_now is not None:
            if (
                self._last_cp is not None
                and now - self._last_cp_t <= TRANSITION_SECS
                and cp_now in mod["transitions"].get(self._last_cp, set())
                and cp_now in mod["score_on"]
                and video_time <= mod.get("count_until", float("inf"))
            ):
                self._reps += 1
                self._score += 10
                self._flash_t = now
            self._last_cp = cp_now
            self._last_cp_t = now
        elif self._last_cp is not None and now - self._last_cp_t > TRANSITION_SECS:
            self._last_cp = None
            self._last_cp_t = 0.0

    def finish_now(self) -> None:
        if self._next == "summary":
            return
        self._finish_module()
        self._next = "summary"

    def _finish_module(self) -> Optional[dict]:
        if self._mod_idx >= len(AEROBIC_MODULES):
            return None
        if any(result["index"] == self._mod_idx for result in self._module_results):
            return None
        target = MODULE_TARGET_REPS[self._mod_idx]
        percent = round(min(self._reps / target, 1.0) * 100) if target else 0
        result = {
            "id": f"{self._mod_idx}-{len(self._module_results)}",
            "index": self._mod_idx,
            "name": AEROBIC_MODULES[self._mod_idx]["name"],
            "reps": self._reps,
            "target": target,
            "percent": percent,
            "rating": self._rating(percent),
        }
        self._module_results.append(result)
        return result

    def _summary(self) -> dict:
        total_reps = sum(result["reps"] for result in self._module_results)
        total_target = sum(result["target"] for result in self._module_results)
        percent = round(min(total_reps / total_target, 1.0) * 100) if total_target else 0
        return {
            "reps": total_reps,
            "target": total_target,
            "percent": percent,
            "message": self._rating(percent),
            "results": self._module_results,
        }

    @staticmethod
    def _rating(percent: int) -> str:
        if percent >= 90:
            return "EXCELENTE"
        if percent >= 75:
            return "MUY BIEN"
        if percent >= 60:
            return "BIEN"
        return "SIGUE A TU RITMO"

    def to_json(self) -> dict:
        if self._next == "summary":
            return {
                "score": self._score,
                "nextState": self._next,
                "video": None,
                "module": {
                    "index": self._mod_idx,
                    "total": len(AEROBIC_MODULES),
                    "name": AEROBIC_MODULES[self._mod_idx]["name"],
                },
                "aerobics": {
                    "summary": self._summary(),
                },
            }

        mod = AEROBIC_MODULES[self._mod_idx]
        target = MODULE_TARGET_REPS[self._mod_idx]
        labels = [
            {"label": label, "active": cp == self._cur_cp}
            for cp, label in mod["labels"].items()
        ]
        form_ok = mod["form_check"](self._data) if mod["form_check"] is not None else None
        return {
            "score": self._score,
            "nextState": self._next,
            "video": f"/assets/{AEROBICS_VIDEO[len('assets/'):]}" ,
            "module": {"index": self._mod_idx, "total": len(AEROBIC_MODULES), "name": mod["name"]},
            "activity": {
                "kind": "aerobics",
                "title": mod["name"],
                "description": mod["description"],
                "labels": labels,
                "reps": self._reps,
                "target": target,
                "progress": min(self._reps / target, 1.0),
                "formOk": form_ok,
                "flash": time.perf_counter() - self._flash_t < SUCCESS_FLASH,
            },
        }

    @property
    def next_state(self) -> Optional[str]:
        return self._next
