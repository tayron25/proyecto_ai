# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run the app

```bash
# Activate venv first
venv\Scripts\activate          # Windows
python main.py
```

Dependencies: `pip install mediapipe opencv-python cvzone numpy`

Keyboard shortcuts while running:
- `ESC` — quit
- `m`   — return to menu from any game

## Architecture

The app is a Python/OpenCV fitness game console that uses MediaPipe pose detection to track body movements in real time.

**Display layout (1920×1080)**
- Left panel (540px): instructional video (480×480, 1:1, centered) + mode chip
- Right canvas (1380×1080): scaled camera feed + skeleton overlay + game HUD

**Core loop** (`main.py`):
1. Capture frame at 640×480 from webcam
2. Submit to background `PoseEngine` thread (non-blocking)
3. Scale frame to 1380×1080 → `game_panel`
4. Call `game.update(game_panel, landmarks, GAME_W, GAME_H)`
5. Draw skeleton overlay with `draw_skeleton(..., GAME_W, GAME_H)`
6. Call `game.render(game_panel)`
7. Composite: dark BG + video panel (left) + game_panel (right)

**Game state machine** (`games/`): `menu → boxing | pose_challenge | aerobics → menu`  
Each game implements `BaseGame`: `update()`, `render()`, `reset()`, `next_state`, `get_video_frame()`.

**Pose coordinates**: MediaPipe landmarks are normalized (0–1). Convert to pixels with `landmark_to_px(lm, frame_w, frame_h)` from `utils/math_utils.py`. Always pass `GAME_W`/`GAME_H` (1380×1080), not the camera resolution.

**Hardcoded positions in games**: all games use `self._w` / `self._h` for layout. Never hardcode pixel values — always express as fractions: `int(0.25 * self._w)`.

**Video player** (`core/video_player.py`): preloads all frames to RAM on `load()`. Default size is 480×480 (1:1). `read_frame()` does zero disk I/O.

## Visual design system (`core/renderer.py`)

Cyberpunk arcade palette (BGR):

| Token      | Use                      |
|------------|--------------------------|
| `BG`       | Near-black background    |
| `BOX_CLR`  | Magenta — boxing mode    |
| `YOGA_CLR` | Cyan — yoga mode         |
| `AERO_CLR` | Lime — aerobics mode     |
| `INK`      | Warm white text          |
| `INK_DIM`  | Muted text               |
| `LINE`     | Subtle borders           |

Key drawing functions:
- `draw_chip(frame, pos, text, color)` — neon badge
- `draw_stepper(frame, pos, total, current, color)` — module progress dots
- `draw_hold_ring(frame, center, radius, ratio, color)` — yoga arc timer
- `draw_background(frame)` — fills with BG + radial vignette (cached)

## Adding a new game

1. Create `games/my_game.py` implementing `BaseGame`
2. Register in `main.py`: add to `games` dict and `_MODE_COLOR`/`_MODE_LABEL`
3. Instantiate with `MyGame(GAME_W, GAME_H)` — never hardcode resolution
4. Load video with `VideoPlayer(path)` (defaults to 480×480)
