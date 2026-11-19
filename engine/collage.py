"""Carousel helper: one 1080x1080 image with several designs of the same Pokémon (slide 3).

Every card gets the diagonal "Fanart Designs MX" watermark, like the Reels.
"""
import math

import cv2
import numpy as np

from render_reel import load_card, watermark

SIZE = 1080


def _layout(n):
    if n <= 3:
        return n, 1
    if n == 4:
        return 2, 2
    if n <= 6:
        return 3, 2
    if n <= 8:
        return 4, 2
    return 3, math.ceil(n / 3)


def _rounded(card, r):
    h, w = card.shape[:2]
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1)
    cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for cx, cy in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)):
        cv2.circle(m, (cx, cy), r, 255, -1)
    return m


def build(card_paths, out_path):
    cards = [load_card(p) for p in card_paths]
    n = len(cards)
    cols, rows = _layout(n)
    # background: blurred, darkened first card
    bg = cv2.resize(cards[0], (SIZE, SIZE))
    bg = cv2.GaussianBlur(bg, (0, 0), 40)
    bg = (bg.astype(np.float32) * 0.35).astype(np.uint8)
    gap = 24 if n > 4 else 36
    ar = cards[0].shape[1] / cards[0].shape[0]  # ~0.716
    cell_w = (SIZE - gap * (cols + 1)) / cols
    cell_h = (SIZE - gap * (rows + 1)) / rows
    ch = int(min(cell_h, cell_w / ar))
    cw = int(ch * ar)
    total_w = cols * cw + (cols - 1) * gap
    total_h = rows * ch + (rows - 1) * gap
    x0, y0 = (SIZE - total_w) // 2, (SIZE - total_h) // 2
    for i, c in enumerate(cards):
        r, k = divmod(i, cols)
        in_row = min(cols, n - r * cols)  # center an incomplete last row
        xr = (SIZE - (in_row * cw + (in_row - 1) * gap)) // 2 if r == rows - 1 else x0
        x, y = xr + k * (cw + gap), y0 + r * (ch + gap)
        c = cv2.resize(c, (cw, ch), interpolation=cv2.INTER_AREA)
        c = watermark(c, cw, ch)
        m = _rounded(c, max(6, cw // 28)).astype(np.float32)[..., None] / 255
        # soft shadow
        sh = np.zeros((SIZE, SIZE), np.float32)
        sh[y + 8:y + ch + 8, x + 4:x + cw + 4] = 1
        sh = cv2.GaussianBlur(sh, (0, 0), 10)[..., None] * 0.55
        bg = (bg.astype(np.float32) * (1 - sh)).astype(np.uint8)
        roi = bg[y:y + ch, x:x + cw].astype(np.float32)
        bg[y:y + ch, x:x + cw] = (roi * (1 - m) + c.astype(np.float32) * m).astype(np.uint8)
    cv2.imwrite(out_path, bg, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return out_path
