import base64
import time
from typing import Any, Optional

import cv2
import numpy as np

from backend.web_boxing import WebBoxingGame
from backend.web_aerobics import WebAerobics
from backend.web_menu import WebMenu
from backend.web_pose_challenge import WebPoseChallenge
from core.pose_engine import PoseEngine
from games.menu import CLAP_DIST
from utils.landmarks import LEFT_WRIST, POSE_CONNECTIONS, RIGHT_WRIST

FRAME_W = 640
FRAME_H = 480
MODEL_PATH = "assets/models/pose_landmarker_lite.task"
SUMMARY_CLAP_HOLD_SECS = 3.5


def _decode_frame(data_url: str) -> Optional[np.ndarray]:
    if not data_url:
        return None
    encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        raw = base64.b64decode(encoded)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None
    if frame is None:
        return None
    return cv2.resize(frame, (FRAME_W, FRAME_H))


def _landmarks_to_json(landmarks: Optional[list]) -> list[dict[str, float]]:
    if not landmarks:
        return []
    return [
        {
            "x": float(lm.x),
            "y": float(lm.y),
            "z": float(getattr(lm, "z", 0.0)),
            "visibility": float(getattr(lm, "visibility", 1.0) or 1.0),
        }
        for lm in landmarks
    ]


def _wrist_json(landmarks: Optional[list]) -> list[dict[str, float]]:
    if not landmarks:
        return []
    wrists = []
    for idx, hand in ((LEFT_WRIST, "left"), (RIGHT_WRIST, "right")):
        lm = landmarks[idx]
        wrists.append({"hand": hand, "x": float(lm.x), "y": float(lm.y)})
    return wrists


class GameSession:
    def __init__(self) -> None:
        self._engine = PoseEngine(MODEL_PATH)
        self._boxing = WebBoxingGame(FRAME_W, FRAME_H)
        self._pose_challenge = WebPoseChallenge(FRAME_W, FRAME_H)
        self._aerobics = WebAerobics(FRAME_W, FRAME_H)
        self._menu = WebMenu(FRAME_W, FRAME_H)
        self._state = "menu"
        self._last_message: Optional[dict[str, str]] = None
        self._last_t = time.perf_counter()
        self._fps = 0.0
        self._frames = 0
        self._summary_clap_t: Optional[float] = None
        self._summary_clap_ratio = 0.0

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        command = payload.get("command")
        selected_game = payload.get("selectedGame")
        video_time = float(payload.get("videoTime") or 0.0)
        paused = bool(payload.get("paused"))

        if command == "menu":
            self._state = "menu"
            self._boxing.reset()
            self._pose_challenge.reset()
            self._aerobics.reset()
            self._menu.reset()
        elif command == "reset":
            if self._state == "menu":
                self._menu.reset()
            elif self._state == "boxing":
                self._boxing.reset()
            elif self._state == "pose_challenge":
                self._pose_challenge.reset()
            elif self._state == "aerobics":
                self._aerobics.reset()
        elif command == "videoEnded":
            if self._state == "boxing":
                self._boxing.advance_module()
            elif self._state == "pose_challenge":
                self._pose_challenge.update(None, video_time=video_time, video_ended=True)
            elif self._state == "aerobics":
                self._aerobics.update(None, video_time=video_time, video_ended=True)
            return self._state_json(self._engine.landmarks)
        elif selected_game:
            self._apply_menu_action(str(selected_game))

        frame = _decode_frame(str(payload.get("frame", "")))
        if frame is not None:
            self._engine.submit(frame)
            self._tick_fps()

        landmarks = self._engine.landmarks
        if self._summary_active():
            self._update_summary_clap(landmarks)
            if self._state == "menu":
                return self._state_json(landmarks)
        else:
            self._reset_summary_clap()

        if paused:
            return self._state_json(landmarks)

        if self._state == "menu":
            self._menu.update(landmarks)
            self._handle_menu_next_state()
        elif self._state == "boxing":
            self._boxing.update(landmarks, video_time)
            if self._boxing.next_state == "menu":
                self._state = "menu"
                self._boxing.reset()
                self._menu.reset()
        elif self._state == "pose_challenge":
            self._pose_challenge.update(landmarks, video_time)
            if self._pose_challenge.next_state == "menu":
                self._state = "menu"
                self._pose_challenge.reset()
                self._menu.reset()
        elif self._state == "aerobics":
            self._aerobics.update(landmarks, video_time)
            if self._aerobics.next_state == "menu":
                self._state = "menu"
                self._aerobics.reset()
                self._menu.reset()

        return self._state_json(landmarks)

    def _summary_active(self) -> bool:
        if self._state == "boxing":
            return self._boxing.next_state == "summary"
        if self._state == "pose_challenge":
            return self._pose_challenge.next_state == "summary"
        if self._state == "aerobics":
            return self._aerobics.next_state == "summary"
        return False

    def _clapping(self, landmarks: Optional[list]) -> bool:
        if not landmarks:
            return False
        lw = landmarks[LEFT_WRIST]
        rw = landmarks[RIGHT_WRIST]
        return abs(lw.x - rw.x) < CLAP_DIST

    def _update_summary_clap(self, landmarks: Optional[list]) -> None:
        now = time.perf_counter()
        if self._clapping(landmarks):
            if self._summary_clap_t is None:
                self._summary_clap_t = now
            self._summary_clap_ratio = min((now - self._summary_clap_t) / SUMMARY_CLAP_HOLD_SECS, 1.0)
            if self._summary_clap_ratio >= 1.0:
                self._return_to_menu()
        else:
            self._reset_summary_clap()

    def _reset_summary_clap(self) -> None:
        self._summary_clap_t = None
        self._summary_clap_ratio = 0.0

    def _return_to_menu(self) -> None:
        self._state = "menu"
        self._boxing.reset()
        self._pose_challenge.reset()
        self._aerobics.reset()
        self._menu.reset()
        self._last_message = None
        self._reset_summary_clap()

    def _handle_menu_next_state(self) -> None:
        next_state = self._menu.consume_next_state()
        if next_state is None:
            return
        self._apply_menu_action(next_state)

    def _apply_menu_action(self, next_state: str) -> None:
        if next_state == "boxing":
            self._state = "boxing"
            self._boxing.reset()
            self._menu.reset()
            self._last_message = None
        elif next_state == "pose_challenge":
            self._state = "pose_challenge"
            self._pose_challenge.reset()
            self._menu.reset()
            self._last_message = None
        elif next_state == "aerobics":
            self._state = "aerobics"
            self._aerobics.reset()
            self._menu.reset()
            self._last_message = None
        elif next_state == "exit":
            self._last_message = {"text": "SALIR seleccionado", "kind": "info", "x": 320, "y": 430}
        else:
            self._last_message = {
                "text": f"{next_state} aun no esta migrado a web",
                "kind": "info",
                "x": 320,
                "y": 430,
            }

    def _state_json(self, landmarks: Optional[list]) -> dict[str, Any]:
        game_state: dict[str, Any] = {}
        if self._state == "boxing":
            game_state = self._boxing.to_json()
        elif self._state == "pose_challenge":
            game_state = self._pose_challenge.to_json()
        elif self._state == "aerobics":
            game_state = self._aerobics.to_json()

        messages = game_state.get("messages", [])
        if self._last_message:
            messages = [*messages, self._last_message]
        return {
            "state": self._state,
            "landmarks": _landmarks_to_json(landmarks),
            "connections": POSE_CONNECTIONS,
            "fps": round(self._fps, 1),
            "score": game_state.get("score", 0),
            "targets": game_state.get("targets", []),
            "wrists": _wrist_json(landmarks),
            "video": game_state.get("video"),
            "messages": messages,
            "nextState": game_state.get("nextState"),
            "module": game_state.get("module"),
            "activity": game_state.get("activity"),
            "boxing": game_state.get("boxing"),
            "yoga": game_state.get("yoga"),
            "aerobics": game_state.get("aerobics"),
            "summaryClap": self._summary_clap_json(),
            "menu": self._menu.to_json() if self._state == "menu" else None,
        }

    def _summary_clap_json(self) -> Optional[dict[str, float | bool]]:
        if not self._summary_active():
            return None
        return {
            "active": True,
            "ratio": self._summary_clap_ratio,
            "holdSeconds": SUMMARY_CLAP_HOLD_SECS,
        }

    def _tick_fps(self) -> None:
        self._frames += 1
        now = time.perf_counter()
        elapsed = now - self._last_t
        if elapsed >= 0.5:
            self._fps = self._frames / elapsed
            self._frames = 0
            self._last_t = now

    def close(self) -> None:
        self._engine.close()
