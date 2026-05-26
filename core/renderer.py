import cv2
import numpy as np
from typing import Tuple, List, Optional

# ── Cyberpunk arcade palette (BGR) ───────────────────────────────────────────
BG       = (11,  7,   7)    # #07070b — near-black
BOX_CLR  = (111, 45,  255)  # #ff2d6f — magenta  (boxing)
YOGA_CLR = (255, 229, 0)    # #00e5ff — cyan      (yoga)
AERO_CLR = (18,  255, 163)  # #a3ff12 — lime      (aerobics)
INK      = (255, 244, 244)  # #f4f4ff — warm white
INK_DIM  = (170, 158, 158)  # muted text
LINE     = (50,  40,  40)   # subtle borders/separators

# ── Legacy palette (kept for game-logic compatibility) ───────────────────────
WHITE  = (255, 255, 255)
BLACK  = (0,   0,   0)
RED    = (0,   0,   255)
GREEN  = (0,   255, 0)
BLUE   = (255, 0,   0)
YELLOW = (0,   255, 255)
CYAN   = (255, 255, 0)
ORANGE = (0,   165, 255)
PURPLE = (255, 0,   255)

_vig_cache: Optional[np.ndarray] = None
_vig_shape: Tuple[int, int] = (0, 0)


def draw_background(frame: np.ndarray) -> None:
    """Fill frame with BG color and a subtle radial vignette."""
    global _vig_cache, _vig_shape
    frame[:] = BG
    h, w = frame.shape[:2]
    if _vig_shape != (h, w):
        cx, cy = w // 2, h // 2
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt(((X - cx) / max(cx, 1)) ** 2 + ((Y - cy) / max(cy, 1)) ** 2)
        _vig_cache = np.clip(1.0 - dist * 0.4, 0.6, 1.0).astype(np.float32)
        _vig_shape = (h, w)
    for c in range(3):
        frame[:, :, c] = (frame[:, :, c] * _vig_cache).astype(np.uint8)


def draw_skeleton(
    frame: np.ndarray,
    landmarks: list,
    connections: List[Tuple[int, int]],
    frame_w: int,
    frame_h: int,
    joint_color: Tuple = YOGA_CLR,
    bone_color: Tuple = LINE,
    joint_radius: int = 5,
    thickness: int = 1,
) -> None:
    pts = [(int(lm.x * frame_w), int(lm.y * frame_h)) for lm in landmarks]
    vis = [(getattr(lm, "visibility", None) or 1.0) > 0.3 for lm in landmarks]
    for a, b in connections:
        if vis[a] and vis[b]:
            cv2.line(frame, pts[a], pts[b], bone_color, thickness, cv2.LINE_AA)
    for i, (px, py) in enumerate(pts):
        if vis[i]:
            cv2.circle(frame, (px, py), joint_radius,     joint_color, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), joint_radius + 2, joint_color,  1, cv2.LINE_AA)


def draw_text(
    frame: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    scale: float = 0.7,
    color: Tuple = INK,
    thickness: int = 2,
) -> None:
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, BLACK,
                thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thickness, cv2.LINE_AA)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    draw_text(frame, f"FPS:{fps:.0f}", (10, 30), scale=0.55, color=INK_DIM, thickness=1)


def draw_panel(
    frame: np.ndarray,
    rect: Tuple[int, int, int, int],
    color: Tuple = BG,
    alpha: float = 0.82,
) -> None:
    x, y, w, h = rect
    x1 = max(0, x);                  y1 = max(0, y)
    x2 = min(frame.shape[1], x + w); y2 = min(frame.shape[0], y + h)
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    bg  = np.full_like(roi, color)
    frame[y1:y2, x1:x2] = cv2.addWeighted(bg, alpha, roi, 1 - alpha, 0)


def draw_progress_bar(
    frame: np.ndarray,
    pos: Tuple[int, int],
    size: Tuple[int, int],
    value: float,
    max_value: float,
    bg_color: Tuple = LINE,
    fg_color: Tuple = AERO_CLR,
) -> None:
    x, y = pos
    w, h = size
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg_color, -1)
    fill_w = int(w * min(max(value / (max_value or 1), 0.0), 1.0))
    if fill_w > 0:
        cv2.rectangle(frame, (x, y), (x + fill_w, y + h), fg_color, -1)


def draw_button(
    frame: np.ndarray,
    rect: Tuple[int, int, int, int],
    label: str,
    hover_ratio: float = 0.0,
    base_color: Tuple = LINE,
    hover_color: Tuple = BOX_CLR,
) -> None:
    x, y, w, h = rect
    draw_panel(frame, rect, color=(20, 15, 15), alpha=0.88)
    border = hover_color if hover_ratio > 0 else base_color
    cv2.rectangle(frame, (x, y), (x + w, y + h), border, 2, cv2.LINE_AA)

    if hover_ratio > 0:
        cx, cy    = x + w // 2, y + h // 2
        r         = min(w, h) // 2 - 6
        end_angle = int(hover_ratio * 360)
        cv2.ellipse(frame, (cx, cy), (r, r), -90, 0, end_angle, hover_color, 3, cv2.LINE_AA)

    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
    draw_text(frame, label,
              (x + (w - tw) // 2, y + (h + th) // 2),
              scale=0.85, color=INK, thickness=2)


def draw_target(
    frame: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    color: Tuple,
    hit: bool = False,
) -> None:
    cv2.circle(frame, center, radius + 20, color,  1, cv2.LINE_AA)   # outer pulse ring
    if hit:
        cv2.circle(frame, center, radius + 10, YELLOW, -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius,            color,  -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius,            WHITE,   2, cv2.LINE_AA)
    cv2.circle(frame, center, max(4, radius // 3), WHITE, 2, cv2.LINE_AA)


def draw_wrist_cursor(
    frame: np.ndarray,
    pos: Optional[Tuple[int, int]],
    color: Tuple = YOGA_CLR,
) -> None:
    if pos is None:
        return
    cv2.circle(frame, pos, 18, color, 2, cv2.LINE_AA)
    cv2.circle(frame, pos,  4, WHITE, -1, cv2.LINE_AA)


def draw_hold_ring(
    frame: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    ratio: float,
    color: Tuple = YOGA_CLR,
) -> None:
    """Circular arc progress indicator for yoga hold timer. ratio: 0.0–1.0."""
    cv2.circle(frame, center, radius, LINE, 6, cv2.LINE_AA)
    end_angle = int(ratio * 360)
    if end_angle > 0:
        cv2.ellipse(frame, center, (radius, radius),
                    -90, 0, end_angle, color, 8, cv2.LINE_AA)
    cv2.circle(frame, center, radius - 16, LINE, 1, cv2.LINE_AA)


def draw_chip(
    frame: np.ndarray,
    pos: Tuple[int, int],
    text: str,
    color: Tuple = INK_DIM,
    scale: float = 0.55,
) -> None:
    """Neon badge: dark fill + colored 1px border + text."""
    x, y = pos
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    px, py = 10, 6
    rx1, ry1 = x,                y - th - py
    rx2, ry2 = x + tw + px * 2,  y + py
    draw_panel(frame, (rx1, ry1, rx2 - rx1, ry2 - ry1), color=(20, 15, 15), alpha=0.92)
    cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), color, 1, cv2.LINE_AA)
    draw_text(frame, text, (x + px, y), scale=scale, color=color, thickness=1)


def _draw_gradient_icon(frame: np.ndarray, x: int, y: int, size: int) -> None:
    """Ícono cuadrado redondeado con degradado teal→purple (AERO_CLR→BOX_CLR)."""
    t = np.linspace(0, 1, size, dtype=np.float32)
    grad = np.zeros((size, size, 3), dtype=np.uint8)
    for c in range(3):
        col = (AERO_CLR[c] * (1 - t) + BOX_CLR[c] * t).astype(np.uint8)
        grad[:, :, c] = col[:, np.newaxis]
    mask = np.zeros((size, size), dtype=np.uint8)
    r = 9
    cv2.rectangle(mask, (r, 0), (size - r, size), 255, -1)
    cv2.rectangle(mask, (0, r), (size, size - r), 255, -1)
    for cx, cy in [(r, r), (size - r, r), (r, size - r), (size - r, size - r)]:
        cv2.circle(mask, (cx, cy), r, 255, -1)
    roi = frame[y:y + size, x:x + size]
    roi[mask > 0] = grad[mask > 0]
    frame[y:y + size, x:x + size] = roi


def draw_navbar(frame: np.ndarray, height: int = 70) -> None:
    """FLOWBOX top navbar: barra oscura con ícono degradado + texto de marca."""
    w = frame.shape[1]
    frame[0:height, 0:w] = BG
    cv2.line(frame, (0, height - 1), (w, height - 1), LINE, 1, cv2.LINE_AA)
    icon_size = 44
    icon_x = 24
    icon_y = (height - icon_size) // 2
    _draw_gradient_icon(frame, icon_x, icon_y, icon_size)
    text_x = icon_x + icon_size + 12
    (_, th), _ = cv2.getTextSize("FLOWBOX", cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    text_y = (height + th) // 2
    draw_text(frame, "FLOWBOX", (text_x, text_y), scale=0.9, color=INK, thickness=2)


def draw_stepper(
    frame: np.ndarray,
    pos: Tuple[int, int],
    total: int,
    current: int,
    color: Tuple = BOX_CLR,
    dot_r: int = 8,
    spacing: int = 30,
) -> None:
    """Row of dots showing module progress. current is 0-indexed active module."""
    x, y = pos
    for i in range(total):
        cx = x + i * spacing
        if i < current:
            cv2.circle(frame, (cx, y), dot_r,     color,   -1, cv2.LINE_AA)
        elif i == current:
            cv2.circle(frame, (cx, y), dot_r,     color,   -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, y), dot_r + 5, color,    2, cv2.LINE_AA)
        else:
            cv2.circle(frame, (cx, y), dot_r,     LINE,    -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, y), dot_r,     INK_DIM,  1, cv2.LINE_AA)
