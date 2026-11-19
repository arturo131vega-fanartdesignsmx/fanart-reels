"""Real-card check (GitHub Actions): is this DESIGN (the artwork) an official card?

Arturo's rule: never post a design that exists as an official Pokémon card. We compare the artwork
of each design against the official card images (TCGdex: every official English card incl. TCG Pocket,
plus Japanese cards) with SIFT feature matching + RANSAC. Same artwork -> many geometric inliers.

review/request.json:
  {"candidates": [{"key": "...", "name": "Pikachu 27", "pokemon": "Pikachu", "dex": 25, "image": "https://..."}]}
Writes:
  review/out/<key>_design.jpg   the design (card crop)
  review/out/<key>_match.jpg    the design next to the 4 most similar official cards (inliers on top)
  review/out/<key>.json         top matches: id, name, set, pocket flag, inliers
  review/out/_summary.json      verdict per key: ART_MATCH (official design) / POSSIBLE (look at it) / NO_ART_MATCH
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "review", "out")
API = "https://api.tcgdex.net/v2"
UA = {"User-Agent": "Mozilla/5.0 fanart-reels-review"}
POCKET = re.compile(r"^(A\d|B\d|P-A)", re.I)
MATCH, POSSIBLE = 25, 12


def get(url, binary=False, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data.decode())
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 + 3 * i)


def decode(data):
    im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        from PIL import Image
        import io
        im = cv2.cvtColor(np.array(Image.open(io.BytesIO(data)).convert("RGB")), cv2.COLOR_RGB2BGR)
    return im


def crop_card(im):
    h, w = im.shape[:2]
    if abs(w / h - 1) < 0.02:  # 2000x2000 mockup
        s = w / 2000.0
        return im[int(140 * s):int(1860 * s), int(384 * s):int(1616 * s)]
    return im


SIFT = cv2.SIFT_create(nfeatures=2500)


def feats(img, art_only=False):
    h, w = img.shape[:2]
    if art_only:  # artwork zone only, so card-frame/template elements can't create false matches
        img = img[int(0.14 * h):int(0.54 * h), int(0.08 * w):int(0.92 * w)]
    s = 800 / max(img.shape[:2])
    img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kp, des = SIFT.detectAndCompute(g, None)
    return np.float32([k.pt for k in kp]) if kp else None, des


BF = cv2.BFMatcher(cv2.NORM_L2)


def inliers(fa, fb):
    pa, da = fa
    pb, db = fb
    if da is None or db is None or len(da) < 8 or len(db) < 8:
        return 0
    good = [m for m, n in (x for x in BF.knnMatch(da, db, k=2) if len(x) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return len(good) // 3
    A = pa[[m.queryIdx for m in good]]
    B = pb[[m.trainIdx for m in good]]
    H, mask = cv2.findHomography(A, B, cv2.RANSAC, 6.0)
    return int(mask.sum()) if mask is not None else 0


def ja_name(dex):
    try:
        sp = get(f"https://pokeapi.co/api/v2/pokemon-species/{dex}")
        for n in sp.get("names", []):
            if n["language"]["name"] in ("ja-Hrkt", "ja"):
                return n["name"]
    except Exception:
        pass
    return None


def official_cards(pokemon, dex):
    found, log = {}, {}
    queries = [("en", f"{API}/en/cards?name={urllib.parse.quote(pokemon)}")]
    jn = ja_name(dex) if dex else None
    if jn:
        queries.append(("ja", f"{API}/ja/cards?name={urllib.parse.quote(jn)}"))
    for lang, q in queries:
        try:
            res = get(q)
            log[lang] = len(res)
            for c in res:
                if c.get("image"):
                    found[f"{lang}:{c['id']}"] = {"id": c["id"], "lang": lang, "name": c.get("name"),
                                                  "image": c["image"], "pocket": bool(POCKET.match(c["id"]))}
        except Exception as e:
            log[lang] = f"error {str(e)[:60]}"
    return list(found.values()), log


def load_official(cards):
    def one(c):
        for ext in ("/high.webp", "/high.png", "/low.webp"):
            try:
                im = decode(get(c["image"] + ext, binary=True, tries=2))
                return c, im, feats(im)
            except Exception:
                continue
        return c, None, (None, None)
    with ThreadPoolExecutor(16) as ex:
        return [r for r in ex.map(one, cards) if r[1] is not None]


def detail(c):
    try:
        d = get(f"{API}/{c['lang']}/cards/{urllib.parse.quote(c['id'])}")
        return {"set": (d.get("set") or {}).get("name"), "illustrator": d.get("illustrator"), "hp": d.get("hp"),
                "attacks": [a.get("name") for a in (d.get("attacks") or [])]}
    except Exception:
        return {}


def match_sheet(design, top, path, th=520):
    tiles = [cv2.resize(design, (int(design.shape[1] * th / design.shape[0]), th))]
    for m, im in top:
        t = cv2.resize(im, (int(im.shape[1] * th / im.shape[0]), th))
        col = (0, 0, 255) if m["inliers"] >= MATCH else ((0, 200, 255) if m["inliers"] >= POSSIBLE else (255, 255, 255))
        cv2.rectangle(t, (0, 0), (t.shape[1], 46), (0, 0, 0), -1)
        cv2.putText(t, f"{m['inliers']} {m['id']}{' P' if m['pocket'] else ''}", (6, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, 2)
        tiles.append(t)
    cv2.imwrite(path, np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    req = json.load(open(os.path.join(ROOT, "review", "request.json")))
    os.makedirs(OUT, exist_ok=True)
    cache, summary = {}, {}
    for cand in req["candidates"]:
        key = cand["key"]
        try:
            d = crop_card(decode(get(cand["image"], binary=True)))
        except Exception as e:
            summary[key] = {"name": cand.get("name"), "verdict": "ERROR", "error": f"design image: {e}"}
            continue
        cv2.imwrite(os.path.join(OUT, f"{key}_design.jpg"),
                    cv2.resize(d, (int(d.shape[1] * 1100 / d.shape[0]), 1100)), [cv2.IMWRITE_JPEG_QUALITY, 88])
        pk = cand["pokemon"]
        if pk not in cache:
            cards, log = official_cards(pk, cand.get("dex"))
            cache[pk] = (load_official(cards), log)
        official, log = cache[pk]
        fd = feats(d, art_only=True)
        scored = sorted(((inliers(fd, f), c, im) for c, im, f in official), key=lambda x: -x[0])
        top = []
        for n, c, im in scored[:4]:
            m = dict(c, inliers=n)
            m.pop("image", None)
            if n >= POSSIBLE:
                m.update(detail(c))
            top.append((m, im))
        match_sheet(d, top, os.path.join(OUT, f"{key}_match.jpg"))
        best = top[0][0] if top else {"inliers": 0}
        verdict = ("ART_MATCH" if best["inliers"] >= MATCH else "POSSIBLE" if best["inliers"] >= POSSIBLE
                   else "NO_ART_MATCH")
        if not official:
            verdict = "NO_OFFICIAL_DATA"  # lookup failed: never treat as clean
        json.dump({"candidate": cand, "official_cards_checked": len(official), "lookup": log,
                   "top": [m for m, _ in top]}, open(os.path.join(OUT, f"{key}.json"), "w"), indent=1,
                  ensure_ascii=False)
        summary[key] = {"name": cand.get("name"), "verdict": verdict, "best": best,
                        "official_cards_checked": len(official), "lookup": log}
        print(key, verdict, best.get("inliers"), best.get("id"), len(official))
    json.dump(summary, open(os.path.join(OUT, "_summary.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
