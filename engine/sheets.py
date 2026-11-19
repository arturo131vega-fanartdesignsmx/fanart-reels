"""Contact sheets: existing Etsy listings of a Pokémon (row per listing) + the new designs (tests/sheets.json)."""
import json, os, urllib.request
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "fonts", "InterDisplay-Bold.otf")
TW, TH, LH = 230, 321, 34


def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return cv2.imdecode(np.frombuffer(urllib.request.urlopen(req, timeout=60).read(), np.uint8), cv2.IMREAD_COLOR)


def card(im):
    h, w = im.shape[:2]
    if abs(w / h - 1) < .02:
        s = w / 2000
        im = im[int(140 * s):int(1860 * s), int(384 * s):int(1616 * s)]
    return cv2.resize(im, (TW, TH), interpolation=cv2.INTER_AREA)


def text(img, xy, s, size, col):
    p = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(p)
    d.text(xy, s, font=ImageFont.truetype(F, size), fill=col)
    return cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR)


def main():
    cfg = json.load(open(os.path.join(ROOT, "tests", "sheets.json")))
    out = os.path.join(ROOT, "tests", "sheets"); os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))
    for gi, g in enumerate(cfg["groups"], 1):
        rows = []
        maxn = max(len(r["items"]) for r in g["rows"])
        W = 20 + maxn * (TW + 12)
        W = max(W, 900)
        for r in g["rows"]:
            col = (60, 200, 90) if r.get("new") else (60, 60, 70)
            head = np.full((46, W, 3), 22, np.uint8)
            head = text(head, (14, 10), r["title"], 24, (255, 220, 80) if r.get("new") else (255, 255, 255))
            band = np.full((TH + LH + 16, W, 3), 22, np.uint8)
            for i, it in enumerate(r["items"]):
                try:
                    c = card(get(it["url"]))
                except Exception as e:
                    c = np.full((TH, TW, 3), 80, np.uint8)
                x = 14 + i * (TW + 12)
                band[6:6 + TH, x:x + TW] = c
                cv2.rectangle(band, (x - 2, 4), (x + TW + 1, 7 + TH), col, 3)
                band = text(band, (x + 4, 10 + TH), it["label"][:22], 20, (230, 230, 230))
            rows += [head, band]
        title = text(np.full((60, W, 3), 12, np.uint8), (14, 12), g["name"], 32, (255, 255, 255))
        cv2.imwrite(os.path.join(out, f"{gi:02d}.jpg"), np.vstack([title] + rows), [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == "__main__":
    main()
