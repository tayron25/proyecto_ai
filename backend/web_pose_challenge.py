import time
from pathlib import Path
from typing import Optional

from games.pose_challenge import HOLD_SECS, SUCCESS_LINGER, YOGA_POSES, _check, _extract_pose_data

POSE_MAX_POINTS = [10, 20, 20, 40]
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _asset_url(path: str) -> str:
    url = f"/assets/{path[len('assets/'):]}"
    file_path = PROJECT_ROOT / path
    try:
        stat = file_path.stat()
    except OSError:
        return url
    return f"{url}?v={int(stat.st_mtime)}-{stat.st_size}"


class WebPoseChallenge:
    def __init__(self, frame_w: int = 640, frame_h: int = 480) -> None:
        self._w = frame_w
        self._h = frame_h
        self.reset()

    def reset(self) -> None:
        self._next: Optional[str] = None
        self._idx = 0
        self._active_option = 0
        self._score = 0
        self._hold_accumulated = 0.0
        self._last_met_t: Optional[float] = None
        self._hold_ratio = 0.0
        self._data: dict = {}
        self._best_conds: list = []
        self._n_met = 0
        self._all_met = False
        self._success = False
        self._success_t = 0.0
        self._success_pts = 0
        self._option_results: list[dict] = []
        self._pose_results: list[dict] = []
        self._last_result: Optional[dict] = None
        self._last_pose_result: Optional[dict] = None
        self._finished_options: set[tuple[int, int]] = set()

    def update(self, landmarks: Optional[list], video_time: float, video_ended: bool = False) -> None:
        now = time.perf_counter()
        if self._idx >= len(YOGA_POSES):
            self._next = "summary"
            return

        pose = YOGA_POSES[self._idx]
        timestamps = pose["option_timestamps"]
        new_opt = sum(1 for t in timestamps if video_time >= t) - 1
        new_opt = max(0, min(new_opt, len(pose["options"]) - 1))

        if video_ended:
            if new_opt != self._active_option:
                self._finish_option()
                self._active_option = new_opt
                self._hold_accumulated = 0.0
                self._last_met_t = None
                self._hold_ratio = 0.0
            self._finish_option()
            self._success = False
            self._advance_pose()
            return

        if self._success:
            if now - self._success_t >= SUCCESS_LINGER:
                self._success = False
            return

        if new_opt != self._active_option:
            self._finish_option()
            self._active_option = new_opt
            self._hold_accumulated = 0.0
            self._last_met_t = None
            self._hold_ratio = 0.0

        self._data = _extract_pose_data(landmarks, self._w, self._h) if landmarks else {}

        if self._data:
            conds = pose["options"][self._active_option]
            self._best_conds = conds
            self._n_met = sum(_check(self._data, cond) for cond in conds)
            self._all_met = self._n_met == len(conds) and len(conds) > 0
        else:
            self._n_met = 0
            self._best_conds = []
            self._all_met = False

        if self._all_met:
            if self._last_met_t is not None:
                self._hold_accumulated = min(self._hold_accumulated + (now - self._last_met_t), HOLD_SECS)
            self._last_met_t = now
            self._hold_ratio = self._hold_accumulated / HOLD_SECS
            if self._hold_ratio >= 1.0:
                result = self._finish_option(force_full=True)
                self._success = True
                self._success_t = now
                self._success_pts = result["points"] if result else self._option_max_points(self._idx)
                self._hold_accumulated = 0.0
                self._last_met_t = None
                self._hold_ratio = 0.0
        else:
            self._last_met_t = None

    def _advance_pose(self) -> None:
        self._finish_pose_if_needed()
        self._idx += 1
        self._active_option = 0
        self._hold_accumulated = 0.0
        self._last_met_t = None
        self._hold_ratio = 0.0
        if self._idx >= len(YOGA_POSES):
            self._next = "summary"

    def _finish_option(self, force_full: bool = False) -> Optional[dict]:
        if self._idx >= len(YOGA_POSES):
            return None
        key = (self._idx, self._active_option)
        if key in self._finished_options:
            return None
        pose = YOGA_POSES[self._idx]
        max_points = self._option_max_points(self._idx)
        held_seconds = HOLD_SECS if force_full else self._hold_accumulated
        progress = 1.0 if force_full else min(max(held_seconds / HOLD_SECS, 0.0), 1.0)
        points = int(round(progress * max_points))
        result = {
            "id": f"{self._idx}-{self._active_option}-{len(self._option_results)}",
            "poseIndex": self._idx,
            "optionIndex": self._active_option,
            "poseName": pose["name"],
            "option": chr(65 + self._active_option),
            "heldSeconds": round(held_seconds, 1),
            "targetSeconds": HOLD_SECS,
            "points": points,
            "maxPoints": max_points,
            "percent": round(progress * 100),
            "message": self._result_message(progress),
            "breath": self._breath_message(progress),
        }
        self._score += points
        self._option_results.append(result)
        self._last_result = result
        self._finished_options.add(key)
        return result

    @staticmethod
    def _option_max_points(pose_idx: int) -> int:
        pose_points = POSE_MAX_POINTS[pose_idx] if pose_idx < len(POSE_MAX_POINTS) else 10
        option_count = len(YOGA_POSES[pose_idx]["options"])
        return pose_points // option_count if option_count else pose_points

    def _finish_pose_if_needed(self) -> Optional[dict]:
        if self._idx >= len(YOGA_POSES):
            return None
        pose_results = [result for result in self._option_results if result["poseIndex"] == self._idx]
        pose_results = self._with_missing_option_results(self._idx, pose_results)
        if not pose_results:
            return None
        if any(result["index"] == self._idx for result in self._pose_results):
            return self._last_pose_result
        points = sum(result["points"] for result in pose_results)
        max_points = sum(result["maxPoints"] for result in pose_results)
        percent = round(points / max_points * 100) if max_points else 0
        result = {
            "id": f"pose-{self._idx}",
            "index": self._idx,
            "name": YOGA_POSES[self._idx]["name"],
            "points": points,
            "maxPoints": max_points,
            "percent": percent,
            "message": self._result_message(percent / 100),
            "options": pose_results,
        }
        self._pose_results.append(result)
        self._last_pose_result = result
        return result

    def _current_pose_points(self) -> int:
        return sum(result["points"] for result in self._option_results if result["poseIndex"] == self._idx)

    def _with_missing_option_results(self, pose_idx: int, results: list[dict]) -> list[dict]:
        existing = {result["optionIndex"]: result for result in results}
        complete = []
        pose = YOGA_POSES[pose_idx]
        max_points = self._option_max_points(pose_idx)
        for option_idx in range(len(pose["options"])):
            if option_idx in existing:
                complete.append(existing[option_idx])
                continue
            complete.append({
                "id": f"{pose_idx}-{option_idx}-missing",
                "poseIndex": pose_idx,
                "optionIndex": option_idx,
                "poseName": pose["name"],
                "option": chr(65 + option_idx),
                "heldSeconds": 0.0,
                "targetSeconds": HOLD_SECS,
                "points": 0,
                "maxPoints": max_points,
                "percent": 0,
                "message": self._result_message(0.0),
                "breath": self._breath_message(0.0),
            })
        return complete

    @staticmethod
    def _result_message(progress: float) -> str:
        if progress >= 0.9:
            return "RESPIRACION EN CALMA"
        if progress >= 0.7:
            return "MUY BUENA ESTABILIDAD"
        if progress >= 0.45:
            return "SIGUE RESPIRANDO"
        return "VUELVE A TU CENTRO"

    @staticmethod
    def _breath_message(progress: float) -> str:
        if progress >= 0.9:
            return "Inhala, exhala, tu cuerpo encontro quietud."
        if progress >= 0.7:
            return "Respira profundo, sostuviste con buena presencia."
        if progress >= 0.45:
            return "Inhala lento, exhala suave, vuelve a intentarlo."
        return "Pausa, respira y regresa con calma."

    def _summary(self) -> dict:
        total_points = sum(result["points"] for result in self._pose_results)
        max_points = sum(result["maxPoints"] for result in self._pose_results)
        percent = round(total_points / max_points * 100) if max_points else 0
        return {
            "points": total_points,
            "maxPoints": max_points,
            "percent": percent,
            "message": self._summary_message(percent),
            "results": self._pose_results,
        }

    @staticmethod
    def _summary_message(percent: int) -> str:
        if percent >= 90:
            return "TU RESPIRACION FLORECE EN EQUILIBRIO"
        if percent >= 75:
            return "CALMA FIRME, ENERGIA PRESENTE"
        if percent >= 60:
            return "SIGUE INHALANDO, SIGUE CRECIENDO"
        return "CADA RESPIRACION ES UN NUEVO COMIENZO"

    def to_json(self) -> dict:
        if self._idx >= len(YOGA_POSES):
            return {
                "nextState": self._next,
                "score": self._score,
                "yoga": {
                    "lastResult": self._last_result,
                    "poseResult": self._last_pose_result,
                    "summary": self._summary(),
                },
            }
        pose = YOGA_POSES[self._idx]
        conditions = [
            {"label": cond[-1], "met": bool(_check(self._data, cond) if self._data else False)}
            for cond in self._best_conds
        ]
        return {
            "score": self._score,
            "nextState": self._next,
            "video": _asset_url(pose["video"]),
            "module": {"index": self._idx, "total": len(YOGA_POSES), "name": pose["name"]},
            "activity": {
                "kind": "yoga",
                "title": pose["name"],
                "description": pose["description"],
                "option": chr(65 + self._active_option),
                "conditions": conditions,
                "met": self._n_met,
                "total": len(self._best_conds),
                "progress": self._hold_ratio,
                "success": self._success,
                "successPoints": self._success_pts,
            },
            "yoga": {
                "heldSeconds": round(self._hold_ratio * HOLD_SECS, 1),
                "targetSeconds": HOLD_SECS,
                "points": self._current_pose_points(),
                "lastResult": self._last_result,
                "poseResult": self._last_pose_result,
                "summary": self._summary() if self._next == "summary" else None,
            },
        }

    @property
    def next_state(self) -> Optional[str]:
        return self._next
