"""Arturo's 2000x2000 shop image format (folder "2000" / Cloudinary), rebuilt from a 1214x1695 card image:
blurred, darkened card as background, soft drop shadow, the card (rounded corners) at x 384..1616, y 140..1860,
and the diagonal "Fanart DesignsMX" watermark (Arial-like, white 41%, 48 degrees)."""
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts", "Arimo-Regular.ttf")
TXT = "Fanart DesignsMX"


def mockup(card_bgr, size=139, cxy=(567, 680), ang=48, alpha=0.41, shadow=(20, 12, 30, 0.85),
           sc=1.9, sig=80, k=0.85, rad=55):
    A = card_bgr
    w, h = int(A.shape[1] * sc), int(A.shape[0] * sc)
    big = cv2.resize(A, (w, h), interpolation=cv2.INTER_AREA)
    y, x = (h - 2000) // 2, (w - 2000) // 2
    bg = cv2.GaussianBlur(big[y:y + 2000, x:x + 2000].astype(np.float32), (0, 0), sig) * k
    m = np.zeros((2000, 2000), np.uint8)
    x0, y0, x1, y1 = 384, 140, 1616, 1860
    cv2.rectangle(m, (x0 + rad, y0), (x1 - rad, y1), 255, -1)
    cv2.rectangle(m, (x0, y0 + rad), (x1, y1 - rad), 255, -1)
    for cx, cy in [(x0 + rad, y0 + rad), (x1 - rad, y0 + rad), (x0 + rad, y1 - rad), (x1 - rad, y1 - rad)]:
        cv2.circle(m, (cx, cy), rad, 255, -1, cv2.LINE_AA)
    dx, dy, s, st = shadow
    sh = cv2.warpAffine(m, np.float32([[1, 0, dx], [0, 1, dy]]), (2000, 2000)).astype(np.float32) / 255
    sh = cv2.GaussianBlur(sh, (0, 0), s) * st
    bg = bg * (1 - sh[..., None])
    C = cv2.resize(A, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA).astype(np.float32)
    lay = Image.new("L", (3000, 3000), 0)
    d = ImageDraw.Draw(lay)
    fnt = ImageFont.truetype(FONT, size)
    tb = d.textbbox((0, 0), TXT, font=fnt)
    d.text((1500 - (tb[0] + tb[2]) / 2, 1500 - (tb[1] + tb[3]) / 2), TXT, font=fnt, fill=255)
    la = np.array(lay.rotate(-ang, resample=Image.BICUBIC)).astype(np.float32) / 255
    cx, cy = cxy
    wm = la[1500 - cy:1500 - cy + (y1 - y0), 1500 - cx:1500 - cx + (x1 - x0)] * alpha
    C = C * (1 - wm[..., None]) + 255 * wm[..., None]
    mm = (m.astype(np.float32) / 255)[..., None]
    out = bg.copy()
    out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - mm[y0:y1, x0:x1]) + C * mm[y0:y1, x0:x1]
    return np.clip(out, 0, 255).astype(np.uint8)
