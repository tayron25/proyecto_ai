import cv2
import numpy as np
from typing import Tuple, List, Optional

# BGR color palette
WHITE  = (255, 255, 255)
BLACK  = (0,   0,   0)
RED    = (0,   0,   255)
GREEN  = (0,   255, 0)
BLUE   = (255, 0,   0)
YELLOW = (0,   255, 255)
CYAN   = (255, 255, 0)
ORANGE = (0,   165, 255)
PURPLE = (255, 0,   255)


def draw_skeleton(
    frame: np.ndarray,
    landmarks: list,
    connections: List[Tuple[int, int]],
    frame_w: int,
    frame_h: int,
    joint_color: Tuple = GREEN,
    bone_color: Tuple = WHITE,
    joint_radius: int = 5,
    thickness: int = 2,
) -> None:
    pts = [(int(lm.x * frame_w), int(lm.y * frame_h)) for lm in landmarks]
    vis = [
        (getattr(lm, 'visibility', None) or 1.0) > 0.3
        for lm in landmarks
    ]
    for a, b in connections:
        if vis[a] and vis[b]:
            cv2.line(frame, pts[a], pts[b], bone_color, thickness, cv2.LINE_AA)
    for i, (px, py) in enumerate(pts):
        if vis[i]:
            cv2.circle(frame, (px, py), joint_radius, joint_color, -1, cv2.LINE_AA)


def draw_text(
    frame: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    scale: float = 0.7,
    color: Tuple = WHITE,
    thickness: int = 2,
) -> None:
    """Draw text with a black outline for readability on any background."""
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, BLACK,
                thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thickness, cv2.LINE_AA)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    draw_text(frame, f"FPS: {fps:.0f}", (10, 28), scale=0.6, color=YELLOW, thickness=1)


def draw_panel(
    frame: np.ndarray,
    rect: Tuple[int, int, int, int],
    color: Tuple = (15, 15, 50),
    alpha: float = 0.72,
) -> None:
    """Semi-transparent filled rectangle."""
    x, y, w, h = rect
    x1 = max(0, x);  y1 = max(0, y)
    x2 = min(frame.shape[1], x + w);  y2 = min(frame.shape[0], y + h)
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    bg  = np.full_like(roi, color)
    frame[y1:y2, x1:x2] = cv2.addWeighted(bg, alpha, roi, 1 - alpha, 0)
    cv2.rectangle(frame, (x, y), (x + w, y + h), WHITE, 1, cv2.LINE_AA)


def draw_progress_bar(
    frame: np.ndarray,
    pos: Tuple[int, int],
    size: Tuple[int, int],
    value: float,
    max_value: float,
    bg_color: Tuple = (50, 50, 50),
    fg_color: Tuple = GREEN,
) -> None:
    x, y = pos
    w, h = size
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg_color, -1)
    fill_w = int(w * min(max(value / (max_value or 1), 0.0), 1.0))
    if fill_w > 0:
        cv2.rectangle(frame, (x, y), (x + fill_w, y + h), fg_color, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), WHITE, 1)


def draw_button(
    frame: np.ndarray,
    rect: Tuple[int, int, int, int],
    label: str,
    hover_ratio: float = 0.0,
    base_color: Tuple = (30, 30, 110),
    hover_color: Tuple = (60, 60, 200),
) -> None:
    x, y, w, h = rect
    color = hover_color if hover_ratio > 0 else base_color
    draw_panel(frame, rect, color=color, alpha=0.75)

    if hover_ratio > 0:
        cx, cy = x + w // 2, y + h // 2
        r = min(w, h) // 2 - 4
        end_angle = int(360 * hover_ratio)
        cv2.ellipse(frame, (cx, cy), (r, r), -90, 0, end_angle, CYAN, 3, cv2.LINE_AA)

    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
    tx = x + (w - tw) // 2
    ty = y + (h + th) // 2
    draw_text(frame, label, (tx, ty), scale=0.85, color=WHITE, thickness=2)


def draw_target(
    frame: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    color: Tuple,
    hit: bool = False,
) -> None:
    if hit:
        cv2.circle(frame, center, radius + 12, YELLOW, -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius, color, -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius, WHITE, 2, cv2.LINE_AA)
    cv2.circle(frame, center, max(4, radius // 2), WHITE, 2, cv2.LINE_AA)


def draw_wrist_cursor(frame: np.ndarray, pos: Optional[Tuple[int, int]], color: Tuple = CYAN) -> None:
    if pos is None:
        return
    cv2.circle(frame, pos, 14, color, 2, cv2.LINE_AA)
    cv2.circle(frame, pos, 3, WHITE, -1, cv2.LINE_AA)
