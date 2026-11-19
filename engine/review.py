"""Real-card check helper (GitHub Actions).

review/request.json: {"candidates": [{"key": "...", "name": "Mega Mewtwo Y ex", "pokemon": "Mewtwo",
                                       "image": "https://..."}]}
Writes for every candidate:
  review/out/<key>_design.jpg   our design (card crop, readable size)
  review/out/<key>_real.jpg     contact sheet of printed / Pocket cards of the same Pokémon (numbered)
  review/out/<key>.json         those cards: id, set, hp, attacks, abilities, rarity, pocket flag
The daily planner (Claude) compares them and decides; nothing is decided here.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "review", "out")
API = "https://api.tcgdex.net/v2/en"
UA = {"User-Agent": "Mozilla/5.0 fanart-reels-review"}
POCKET = re.compile(r"^(A\d|B\d|P-A)", re.I)


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else json.loads(data.decode())


def img_from(url):
    data = get(url, binary=True)
    arr = np.frombuffer(data, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if im is None:  # webp fallback through PIL
        from PIL import Image
        import io
        im = cv2.cvtColor(np.array(Image.open(io.BytesIO(data)).convert("RGB")), cv2.COLOR_RGB2BGR)
    return im


def crop_card(im):
    h, w = im.shape[:2]
    if abs(w / h - 1) < 0.02:
        s = w / 2000.0
        return im[int(140 * s):int(1860 * s), int(384 * s):int(1616 * s)]
    return im


def detail(cid):
    try:
        c = get(f"{API}/cards/{urllib.parse.quote(cid)}")
    except Exception as e:
        return {"id": cid, "error": str(e)[:80]}
    return {
        "id": c.get("id"), "name": c.get("name"), "set": (c.get("set") or {}).get("name"),
        "hp": c.get("hp"), "rarity": c.get("rarity"), "illustrator": c.get("illustrator"),
        "attacks": [a.get("name") for a in (c.get("attacks") or [])],
        "abilities": [a.get("name") for a in (c.get("abilities") or [])],
        "pocket": bool(POCKET.match(c.get("id") or "")),
        "image": (c.get("image") + "/low.png") if c.get("image") else None,
    }


def sheet(cards, path, cols=8, tw=150, th=210):
    rows = max(1, (len(cards) + cols - 1) // cols)
    canvas = np.full((rows * (th + 26), cols * tw, 3), 30, np.uint8)

    def fetch(c):
        try:
            return cv2.resize(img_from(c["image"]), (tw - 6, th - 6)) if c.get("image") else None
        except Exception:
            return None

    with ThreadPoolExecutor(8) as ex:
        thumbs = list(ex.map(fetch, cards))
    for i, (c, t) in enumerate(zip(cards, thumbs)):
        r, k = divmod(i, cols)
        y, x = r * (th + 26), k * tw
        if t is not None:
            canvas[y + 3:y + th - 3, x + 3:x + tw - 3] = t
        label = f"{i + 1}{' P' if c.get('pocket') else ''}"
        cv2.putText(canvas, label, (x + 6, y + th + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(path, canvas, [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    req = json.load(open(os.path.join(ROOT, "review", "request.json")))
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    summary = {}
    for cand in req.get("candidates", []):
        key = re.sub(r"[^A-Za-z0-9_-]", "_", cand["key"])
        try:
            d = crop_card(img_from(cand["image"]))
            d = cv2.resize(d, (int(d.shape[1] * 1100 / d.shape[0]), 1100))
            cv2.imwrite(os.path.join(OUT, f"{key}_design.jpg"), d, [cv2.IMWRITE_JPEG_QUALITY, 88])
        except Exception as e:
            summary[key] = {"error": f"design image: {e}"}
            continue
        poke = cand.get("pokemon") or cand["name"].split()[0]
        try:
            brief = get(f"{API}/cards?name={urllib.parse.quote(poke)}")
        except Exception as e:
            brief = []
            summary[key] = {"error": f"tcgdex: {e}"}
        ids = [b["id"] for b in brief][:96]
        with ThreadPoolExecutor(8) as ex:
            cards = [c for c in ex.map(detail, ids) if c.get("name")]
        json.dump({"candidate": cand, "real_cards": cards}, open(os.path.join(OUT, f"{key}.json"), "w"), indent=1)
        sheet(cards, os.path.join(OUT, f"{key}_real.jpg"))
        summary[key] = {"name": cand["name"], "real_cards_found": len(cards)}
    json.dump(summary, open(os.path.join(OUT, "_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
