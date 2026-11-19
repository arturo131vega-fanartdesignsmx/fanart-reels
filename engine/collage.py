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


FAN_MARGIN = 84  # minimum distance between any card and the frame edge


def _card_rgba(card, h, angle, has_wm=False):
    """Watermarked rounded card of height h, rotated by angle -> (BGR uint8, alpha float 0..1).
    Shop mockups already carry the shop watermark: never stack a second one."""
    w = int(h * card.shape[1] / card.shape[0])
    c = cv2.resize(card, (w, h), interpolation=cv2.INTER_AREA)
    if not has_wm:
        c = watermark(c, w, h)
    a = _rounded(c, max(6, w // 26))
    pad = int(0.12 * h)
    big = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
    big[pad:pad + h, pad:pad + w, :3] = c
    big[pad:pad + h, pad:pad + w, 3] = a
    if angle:
        M = cv2.getRotationMatrix2D((big.shape[1] / 2, big.shape[0] / 2), angle, 1.0)
        big = cv2.warpAffine(big, M, (big.shape[1], big.shape[0]), flags=cv2.INTER_LINEAR)
    return big[..., :3], big[..., 3].astype(np.float32) / 255


def _fan(cards):
    """Lay out 1-3 cards as a fan (back cards first) on a transparent layer, then scale/centre it so the
    whole group sits in the middle of the frame with FAN_MARGIN px of free space around it."""
    n = len(cards)
    # (index into cards, x offset, y offset, height, angle) - the main card goes last (on top)
    spec = {1: [(0, 0, 0, 900, 0)],
            2: [(1, 170, 16, 560, -6), (0, -170, 0, 580, 5)],
            3: [(1, -272, 26, 540, 6), (2, 272, 26, 540, -6), (0, 0, 0, 640, 0)]}[n]
    big = 2600
    rgb = np.zeros((big, big, 3), np.float32)
    al = np.zeros((big, big), np.float32)
    for i, dx, dy, h, ang in spec:
        c, a = _card_rgba(cards[i][0], h, ang, cards[i][1])
        y0, x0 = big // 2 + dy - c.shape[0] // 2, big // 2 + dx - c.shape[1] // 2
        sl = (slice(y0, y0 + c.shape[0]), slice(x0, x0 + c.shape[1]))
        # shadow of this card falls on the cards behind it
        sh = cv2.GaussianBlur(a, (0, 0), 16) * 0.55
        rgb[sl] = rgb[sl] * (1 - sh[..., None])
        al[sl] = np.maximum(al[sl], sh)
        A = a[..., None]
        rgb[sl] = rgb[sl] * (1 - A) + c.astype(np.float32) * A
        al[sl] = al[sl] * (1 - a) + a
    ys, xs = np.where(al > 0.02)
    y1, y2, x1, x2 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb, al = rgb[y1:y2, x1:x2], al[y1:y2, x1:x2]
    avail = SIZE - 2 * FAN_MARGIN
    s = min(avail / rgb.shape[1], avail / rgb.shape[0])
    rgb = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    al = cv2.resize(al, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return rgb, al


def build(card_paths, out_path):
    """Slide 3: the other designs of the Pokémon as a centred fan of three (two or one if that's all)."""
    cards = [load_card(p) for p in card_paths[:3]]  # [(card, already_watermarked)]
    bg = cv2.resize(cards[0][0], (SIZE, SIZE))
    bg = (cv2.GaussianBlur(bg, (0, 0), 40).astype(np.float32) * 0.35)
    rgb, al = _fan(cards)
    h, w = al.shape
    y0, x0 = (SIZE - h) // 2, (SIZE - w) // 2
    A = al[..., None]
    roi = bg[y0:y0 + h, x0:x0 + w]
    bg[y0:y0 + h, x0:x0 + w] = roi * (1 - A) + rgb * A
    cv2.imwrite(out_path, np.clip(bg, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
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
    card, has_wm = load_card(mockup_path)
    ch = 742
    cw = int(ch * card.shape[1] / card.shape[0])
    card = cv2.resize(card, (cw, ch), interpolation=cv2.INTER_AREA)
    if not has_wm:
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
