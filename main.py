import sys
import numpy as np
import cv2

from core.camera      import CameraCapture
from core.pose_engine import PoseEngine
from core.renderer    import (
    draw_fps, draw_skeleton, draw_text, draw_panel, draw_chip, draw_navbar,
    BG, BOX_CLR, YOGA_CLR, AERO_CLR, INK_DIM, LINE, RED,
)
from games.menu           import MainMenu
from games.boxing         import BoxingGame
from games.pose_challenge import PoseChallenge
from games.aerobics       import AerobicsGame
from utils.landmarks      import POSE_CONNECTIONS

# ── Display constants ─────────────────────────────────────────────────────────
FRAME_W  = 640
FRAME_H  = 480
CAM_SIZE = 820           # coach and player panels are equal 1:1 squares: 820×820
GAP      = 20
MARGIN   = (1920 - 2 * CAM_SIZE - GAP) // 2   # 130 px
PANEL_Y  = (1080 - CAM_SIZE) // 2              # 130 px
COACH_X  = MARGIN                              # 130
PLAYER_X = MARGIN + CAM_SIZE + GAP             # 970

# Center-crop the 640×480 camera feed to 480×480
CROP_X1 = (FRAME_W - FRAME_H) // 2            # 80
CROP_X2 = FRAME_W - CROP_X1                   # 560

DISPLAY_W = 1920
DISPLAY_H = 1080

MODEL_PATH = "assets/models/pose_landmarker_lite.task"

_MODE_COLOR = {
    "boxing":         BOX_CLR,
    "pose_challenge": YOGA_CLR,
    "aerobics":       AERO_CLR,
}
_MODE_LABEL = {
    "boxing":         "BOX",
    "pose_challenge": "YOGA",
    "aerobics":       "AERO",
}


def main() -> None:
    cam = CameraCapture(cam_id=0, width=FRAME_W, height=FRAME_H)
    if not cam.cap.isOpened():
        print("ERROR: No se pudo abrir la camara.", file=sys.stderr)
        return

    engine = PoseEngine(model_path=MODEL_PATH)

    games = {
        "menu":           MainMenu(CAM_SIZE, CAM_SIZE),
        "boxing":         BoxingGame(CAM_SIZE, CAM_SIZE),
        "pose_challenge": PoseChallenge(CAM_SIZE, CAM_SIZE),
        "aerobics":       AerobicsGame(CAM_SIZE, CAM_SIZE),
    }
    state = "menu"

    cv2.namedWindow("FLOWBOX", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("FLOWBOX", DISPLAY_W, DISPLAY_H)

    while True:
        cam_frame = cam.read()
        if cam_frame is None:
            break

        # Center-crop 640×480 → 480×480 for 1:1 panels
        cam_crop = cam_frame[:, CROP_X1:CROP_X2]

        engine.submit(cam_crop)
        landmarks = engine.landmarks

        game = games[state]

        # Scale crop to 820×820 game canvas
        game_panel = cv2.resize(cam_crop, (CAM_SIZE, CAM_SIZE))

        game.update(game_panel, landmarks, CAM_SIZE, CAM_SIZE)

        if landmarks:
            draw_skeleton(game_panel, landmarks, POSE_CONNECTIONS, CAM_SIZE, CAM_SIZE)

        game.render(game_panel)

        # ── Composite ─────────────────────────────────────────────────────────
        display = np.full((DISPLAY_H, DISPLAY_W, 3), BG, dtype=np.uint8)
        if state == "menu":
            draw_navbar(display)

        # Coach panel (left) — instructional video resized to 820×820
        coach_frame = game.get_video_frame()
        if coach_frame is not None:
            display[PANEL_Y:PANEL_Y + CAM_SIZE, COACH_X:COACH_X + CAM_SIZE] = \
                cv2.resize(coach_frame, (CAM_SIZE, CAM_SIZE))
        else:
            draw_panel(display,
                       (COACH_X, PANEL_Y, CAM_SIZE, CAM_SIZE),
                       color=(20, 15, 15), alpha=0.95)
            draw_text(display, "FLOWBOX",
                      (COACH_X + CAM_SIZE // 4, PANEL_Y + CAM_SIZE // 2),
                      scale=1.4, color=INK_DIM, thickness=2)

        # Mode chip above coach panel
        if state in _MODE_LABEL:
            draw_chip(display, (COACH_X, PANEL_Y - 36), _MODE_LABEL[state],
                      color=_MODE_COLOR[state], scale=0.65)

        # Recording dot (decorative)
        cv2.circle(display,
                   (COACH_X + CAM_SIZE - 14, PANEL_Y + 14),
                   5, RED, -1, cv2.LINE_AA)

        # Player panel (right) — game canvas with skeleton + HUD
        display[PANEL_Y:PANEL_Y + CAM_SIZE, PLAYER_X:PLAYER_X + CAM_SIZE] = game_panel

        draw_fps(display, cam.fps)

        nxt = game.next_state
        if nxt == "exit":
            break
        if nxt and nxt in games:
            game.reset()
            state = nxt
            games[state].reset()

        cv2.imshow("FLOWBOX", display)
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
