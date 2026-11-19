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


def _place(bg, card, cx, cy, h, angle=0.0):
    """Draw a watermarked, rounded card of height h centred at (cx, cy), rotated by angle, with shadow."""
    w = int(h * card.shape[1] / card.shape[0])
    c = cv2.resize(card, (w, h), interpolation=cv2.INTER_AREA)
    c = watermark(c, w, h)
    a = _rounded(c, max(6, w // 26))
    pad = int(0.12 * h)
    big = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
    big[pad:pad + h, pad:pad + w, :3] = c
    big[pad:pad + h, pad:pad + w, 3] = a
    M = cv2.getRotationMatrix2D((big.shape[1] / 2, big.shape[0] / 2), angle, 1.0)
    big = cv2.warpAffine(big, M, (big.shape[1], big.shape[0]), flags=cv2.INTER_LINEAR)
    al = big[..., 3].astype(np.float32) / 255
    sh = cv2.GaussianBlur(al, (0, 0), 14) * 0.6
    x0, y0 = int(cx - big.shape[1] / 2), int(cy - big.shape[0] / 2)
    for layer, color, alpha, dx, dy in ((None, 0, sh, 6, 14), (big[..., :3], None, al, 0, 0)):
        xa, ya = max(0, x0 + dx), max(0, y0 + dy)
        xb, yb = min(SIZE, x0 + dx + big.shape[1]), min(SIZE, y0 + dy + big.shape[0])
        sl = (slice(ya - y0 - dy, yb - y0 - dy), slice(xa - x0 - dx, xb - x0 - dx))
        A = alpha[sl][..., None]
        roi = bg[ya:yb, xa:xb].astype(np.float32)
        src = np.zeros_like(roi) if layer is None else layer[sl].astype(np.float32)
        bg[ya:yb, xa:xb] = (roi * (1 - A) + src * A).astype(np.uint8)


def build(card_paths, out_path):
    cards = [load_card(p) for p in card_paths]
    n = len(cards)
    if n in (1, 3):  # one big card, or a fan of three (bigger than a row of three)
        bg = cv2.resize(cards[0], (SIZE, SIZE))
        bg = (cv2.GaussianBlur(bg, (0, 0), 40).astype(np.float32) * 0.35).astype(np.uint8)
        if n == 1:
            _place(bg, cards[0], SIZE / 2, SIZE / 2, 940)
        else:
            # symmetric fan, every card at least ~48 px inside the frame
            _place(bg, cards[1], SIZE / 2 - 284, SIZE / 2 + 20, 520, 5)
            _place(bg, cards[2], SIZE / 2 + 284, SIZE / 2 + 20, 520, -5)
            _place(bg, cards[0], SIZE / 2, SIZE / 2, 580)
        cv2.imwrite(out_path, bg, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return out_path
    cols, rows = _layout(n)
    # background: blurred, darkened first card
    bg = cv2.resize(cards[0], (SIZE, SIZE))
    bg = cv2.GaussianBlur(bg, (0, 0), 40)
    bg = (bg.astype(np.float32) * 0.35).astype(np.uint8)
    gap = 24 if n > 4 else 36
    margin = 56  # keep every card well inside the frame
    ar = cards[0].shape[1] / cards[0].shape[0]  # ~0.716
    cell_w = (SIZE - 2 * margin - gap * (cols - 1)) / cols
    cell_h = (SIZE - 2 * margin - gap * (rows - 1)) / rows
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


# ------------------------------------------------------------------ carousel main image (slide 1)
def _over(dst, rgba, cx, cy):
    """Alpha-composite an RGBA float image (0..1, BGR order) centred at (cx, cy) on a uint8 BGR canvas."""
    h, w = rgba.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    sub = rgba[ya - y0:yb - y0, xa - x0:xb - x0]
    a = sub[..., 3:4]
    roi = dst[ya:yb, xa:xb].astype(np.float32) / 255
    dst[ya:yb, xa:xb] = np.clip((roi * (1 - a) + sub[..., :3] * a) * 255, 0, 255).astype(np.uint8)


def hero(mockup_path, out_path):
    """Main carousel image: the design mockup look (its own background), the card, the
    "Handmade Proxy Cards" title and the "ETSY Link in Bio" button of the approved Reel template."""
    from PIL import Image, ImageDraw, ImageFont
    from render_reel import text_img, FB, YEL, ORG, WHITE
    src = cv2.imread(mockup_path)
    bg = cv2.resize(src, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    bg = cv2.GaussianBlur(bg, (0, 0), 22)
    bg = (bg.astype(np.float32) * 0.70).astype(np.uint8)
    card = load_card(mockup_path)
    ch = 742
    cw = int(ch * card.shape[1] / card.shape[0])
    card = cv2.resize(card, (cw, ch), interpolation=cv2.INTER_AREA)
    card = watermark(card, cw, ch)
    cy = 528
    x, y = (SIZE - cw) // 2, cy - ch // 2
    sh = np.zeros((SIZE, SIZE), np.float32)
    sh[y + 14:y + ch + 14, x + 6:x + cw + 6] = 1
    sh = cv2.GaussianBlur(sh, (0, 0), 16)[..., None] * 0.6
    bg = (bg.astype(np.float32) * (1 - sh)).astype(np.uint8)
    m = _rounded(card, max(8, cw // 24)).astype(np.float32)[..., None] / 255
    roi = bg[y:y + ch, x:x + cw].astype(np.float32)
    bg[y:y + ch, x:x + cw] = (roi * (1 - m) + card.astype(np.float32) * m).astype(np.uint8)
    # title (same words/colours as the Reels)
    words = [("Handmade", YEL), ("Proxy", WHITE), ("Cards", WHITE)]
    ts = 80
    while True:
        f = ImageFont.truetype(FB, ts)
        tot = sum(f.getbbox(w, stroke_width=3)[2] for w, _ in words) + int(ts * 0.28) * 2
        if tot <= 900:
            break
        ts -= 2
    _over(bg, text_img(words, ts, FB, stroke=3), SIZE / 2, 82)
    # ETSY Link in Bio button (outline style of the Reels)
    txt = text_img([("ETSY", ORG), ("Link in Bio", WHITE)], 54, FB, stroke=0, shadow=False, pad=0)
    ph, pw = txt.shape[:2]
    PW, PH = pw + 80, ph + 22
    pim = Image.new("RGBA", (PW + 20, PH + 20), (0, 0, 0, 0))
    ImageDraw.Draw(pim).rounded_rectangle((10, 10, 10 + PW, 10 + PH), radius=PH // 2,
                                          fill=(15, 15, 20, 220), outline=(241, 100, 30, 255), width=5)
    pa = np.array(pim).astype(np.float32) / 255
    pill = np.dstack([pa[..., 2], pa[..., 1], pa[..., 0], pa[..., 3]])
    oy, ox = (pill.shape[0] - ph) // 2 + 2, (pill.shape[1] - pw) // 2
    reg = pill[oy:oy + ph, ox:ox + pw]
    a = txt[..., 3:4]
    reg[..., :3] = reg[..., :3] * (1 - a) + txt[..., :3] * a
    reg[..., 3:4] = np.maximum(reg[..., 3:4], a)
    _over(bg, pill, SIZE / 2, 990)
    cv2.imwrite(out_path, bg, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return out_path
