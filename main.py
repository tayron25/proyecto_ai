import sys
import numpy as np
import cv2

from core.camera      import CameraCapture
from core.pose_engine import PoseEngine
from core.renderer    import draw_fps, draw_skeleton, draw_text, draw_panel, RED, CYAN, WHITE
from games.menu       import MainMenu
from games.boxing     import BoxingGame
from games.pose_challenge import PoseChallenge
from games.aerobics   import AerobicsGame
from utils.landmarks  import POSE_CONNECTIONS

FRAME_W   = 640
FRAME_H   = 480
VIDEO_W   = 270                 # panel izquierdo (video vertical 9:16)
DISPLAY_W = VIDEO_W + FRAME_W  # 910

MODEL_PATH = "assets/models/pose_landmarker_lite.task"


def _draw_video_panel(display: np.ndarray, game) -> None:
    vid = game.get_video_frame()
    if vid is not None:
        display[:, :VIDEO_W] = vid
    else:
        draw_panel(display, (0, 0, VIDEO_W, FRAME_H), color=(5, 5, 30), alpha=1.0)
        draw_text(display, "CONSOLA",     (12, 210), scale=0.75, color=CYAN,  thickness=2)
        draw_text(display, "MULTIJUEGOS", (12, 242), scale=0.52, color=WHITE, thickness=1)


def main() -> None:
    cam = CameraCapture(cam_id=0, width=FRAME_W, height=FRAME_H)
    if not cam.cap.isOpened():
        print("ERROR: No se pudo abrir la camara.", file=sys.stderr)
        return

    engine = PoseEngine(model_path=MODEL_PATH)

    games = {
        "menu":           MainMenu(FRAME_W, FRAME_H),
        "boxing":         BoxingGame(FRAME_W, FRAME_H),
        "pose_challenge": PoseChallenge(FRAME_W, FRAME_H),
        "aerobics":       AerobicsGame(FRAME_W, FRAME_H),
    }
    state = "menu"

    cv2.namedWindow("Consola Multijuegos", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Consola Multijuegos", DISPLAY_W, FRAME_H)

    while True:
        cam_frame = cam.read()
        if cam_frame is None:
            break

        # Submit to background inference thread — never blocks
        engine.submit(cam_frame)
        landmarks = engine.landmarks

        game = games[state]

        # Build game panel (640×480) — games still use original coords
        game_panel = cam_frame.copy()
        game.update(game_panel, landmarks, FRAME_W, FRAME_H)

        if landmarks:
            draw_skeleton(game_panel, landmarks, POSE_CONNECTIONS, FRAME_W, FRAME_H)

        game.render(game_panel)

        # Composite display (910×480)
        display = np.zeros((FRAME_H, DISPLAY_W, 3), dtype=np.uint8)
        _draw_video_panel(display, game)
        display[:, VIDEO_W:] = game_panel

        draw_fps(display, cam.fps)

        # State transition
        nxt = game.next_state
        if nxt == "exit":
            break
        if nxt and nxt in games:
            game.reset()
            state = nxt
            games[state].reset()

        cv2.imshow("Consola Multijuegos", display)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        elif key == ord("m"):
            games[state].reset()
            state = "menu"
            games["menu"].reset()

    cam.release()
    engine.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
