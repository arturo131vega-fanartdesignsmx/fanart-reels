"""Scheduler run (GitHub Actions, every 15 min).

queue/<YYYY-MM-DD>.json  -> {"items": [ ...item... ]}  (written by the daily planner)
state/status.json        -> per-item progress (written here)

Reel item:
  {"id", "type": "reel", "publish_at": ISO8601 with offset,
   "card_image": URL (watermarked Etsy mockup or Cloudinary URL),
   "script": [...], "voice": "af_heart", "speed": 1.04, "variant_seed": int, "music_seed": int,
   "highlight": [...], "caption_ig": str, "caption_fb": str}
Carousel item:
  {"id", "type": "carousel", "publish_at",
   "slides": [{"hero": url} | {"image": url} | {"video": url} | {"collage": [url, url, ...]}, ...],
   "caption_ig": str, "caption_fb": str}
  "hero" = main image built here (design + "Handmade Proxy Cards" + "ETSY Link in Bio").
  "collage" = the other designs in one 1080x1080 image, each watermarked.
"""
import datetime as dt
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

REPO = os.environ.get("GITHUB_REPOSITORY", "arturo131vega-fanartdesignsmx/fanart-reels")
CLOUD = "rntnboij"
RENDER_AHEAD = dt.timedelta(hours=3)
GIVE_UP_AFTER = dt.timedelta(hours=10)
MAX_ATTEMPTS = 3
STATUS = os.path.join(ROOT, "state", "status.json")
MODEL_DIR = os.environ.get("KOKORO_DIR", os.path.join(ROOT, ".kokoro"))


def now():
    return dt.datetime.now(dt.timezone.utc)


def load_items():
    items = []
    today = now().date()
    for f in sorted(glob.glob(os.path.join(ROOT, "queue", "*.json"))):
        try:
            day = dt.date.fromisoformat(os.path.basename(f)[:10])
        except ValueError:
            continue
        if day < today - dt.timedelta(days=1) or day > today + dt.timedelta(days=2):
            continue
        for it in json.load(open(f)).get("items", []):
            it["_at"] = dt.datetime.fromisoformat(it["publish_at"])
            items.append(it)
    return sorted(items, key=lambda x: x["_at"])


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 fanart-reels"})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
        shutil.copyfileobj(r, f)
    return path


def push_cdn(files):
    """Publish files on the `cdn` branch (orphan commit, keeps ~2 days of files)."""
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://x-access-token:{token}@github.com/{REPO}.git"
    tmp = tempfile.mkdtemp()
    keep_from = (now() - dt.timedelta(days=2)).strftime("%Y-%m-%d")
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "cdn", url, tmp], capture_output=True)
    if r.returncode != 0:
        subprocess.run(["git", "init", "-q", "-b", "cdn", tmp], check=True)
    os.makedirs(os.path.join(tmp, "out"), exist_ok=True)
    for f in glob.glob(os.path.join(tmp, "out", "*")):
        if os.path.basename(f)[:10] < keep_from:
            os.remove(f)
    for name, path in files.items():
        shutil.copy(path, os.path.join(tmp, "out", name))
    shutil.rmtree(os.path.join(tmp, ".git"))
    subprocess.run(["git", "init", "-q", "-b", "cdn", tmp], check=True)
    g = ["git", "-C", tmp, "-c", "user.name=fanart-reels-bot", "-c",
         "user.email=41898282+github-actions[bot]@users.noreply.github.com"]
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["commit", "-qm", "cdn update"], check=True)
    subprocess.run(g + ["push", "-q", "-f", url, "cdn"], check=True)
    raw = f"https://raw.githubusercontent.com/{REPO}/cdn/out/"
    return {name: raw + name for name in files}


def cld_video(raw_url):
    return f"https://res.cloudinary.com/{CLOUD}/video/fetch/{raw_url}"


def cld_image(raw_url):
    return f"https://res.cloudinary.com/{CLOUD}/image/fetch/f_jpg,q_90/{raw_url}"


def warm(url):
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 fanart-reels"})
            with urllib.request.urlopen(req, timeout=180) as r:
                n = len(r.read())
            if n > 1000:
                return n
        except Exception:
            time.sleep(10)
    raise RuntimeError(f"media not reachable: {url}")


def fix_caption(text):
    """Arturo's rule: write EX in capitals (Pikachu EX, Mega Gengar EX)."""
    import re
    return re.sub(r"(?<![#\w])ex\b", "EX", text or "")


MORE_DESIGNS = ("https://res.cloudinary.com/rntnboij/image/fetch/f_jpg,q_90/"
                "https://raw.githubusercontent.com/arturo131vega-fanartdesignsmx/fanart-reels/main/design/more_designs_v2.jpg")
HOLO_SQUARE = ("https://res.cloudinary.com/rntnboij/video/upload/c_crop,w_720,h_720,x_0,y_185/c_scale,w_1080/q_auto/"
               "v1795034320/ig_holo_video.mp4")


def prepare_carousel(it, workdir):
    from collage import build, hero
    day = it["publish_at"][:10]
    slides, files = [], {}
    for i, sl in enumerate(it["slides"]):
        # keep Arturo's approved format even if a queue file still has an older slide
        if "ig_more_designs" in (sl.get("image") or ""):
            sl = {"image": MORE_DESIGNS}
        if "ig_holo_video" in (sl.get("video") or "") and "b_blurred" in sl["video"]:
            sl = {"video": HOLO_SQUARE}
        name = f"{day}_{it['id']}_slide{i + 1}.jpg"
        if sl.get("collage"):
            paths = [download(u, os.path.join(workdir, f"s{i}_{j}.jpg")) for j, u in enumerate(sl["collage"])]
            files[name] = build(paths, os.path.join(workdir, name))
            slides.append({"image": name, "_local": True})
        elif sl.get("hero"):
            files[name] = hero(download(sl["hero"], os.path.join(workdir, f"s{i}.jpg")), os.path.join(workdir, name))
            slides.append({"image": name, "_local": True})
        else:
            slides.append(dict(sl))
    if files:
        urls = push_cdn(files)
        for sl in slides:
            if sl.pop("_local", False):
                sl["image"] = cld_image(urls[sl["image"]])
    for sl in slides:
        warm(sl.get("image") or sl.get("video"))
    return {"slides": slides}


def render_item(it, workdir):
    import soundfile as sf
    from tts import synth
    from render_reel import render
    card = download(it["card_image"], os.path.join(workdir, "card.jpg"))
    y, sr, meta = synth(it["script"], it.get("voice", "af_heart"), float(it.get("speed", 1.04)), MODEL_DIR)
    wav = os.path.join(workdir, "voice.wav")
    sf.write(wav, y, sr)
    day = it["publish_at"][:10]
    mp4 = os.path.join(workdir, f"{day}_{it['id']}.mp4")
    cover = os.path.join(workdir, f"{day}_{it['id']}.jpg")
    info = render(card, meta, wav, mp4, int(it.get("variant_seed", 0)), int(it.get("music_seed", 0)),
                  it.get("highlight", []), cover_path=cover)
    urls = push_cdn({os.path.basename(mp4): mp4, os.path.basename(cover): cover})
    v = cld_video(urls[os.path.basename(mp4)])
    c = cld_image(urls[os.path.basename(cover)])
    warm(v)
    warm(c)
    return {"video_url": v, "cover_url": c, "render": info, "subs": meta["subs"]}


def main():
    mode = os.environ.get("MODE", "run")
    status = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    meta_api = None

    def api():
        nonlocal meta_api
        if meta_api is None:
            from meta import Meta
            meta_api = Meta(token)
        return meta_api

    if mode == "check":
        print(json.dumps(api().check(), indent=1))
        return 0

    if mode == "fbfix":  # delete / edit Page posts listed in tests/fbfix.json (requested by Arturo)
        from meta import call
        m, cfg, res = api(), json.load(open("tests/fbfix.json")), {}
        for pid in cfg.get("delete", []):
            try:
                res[pid] = call("DELETE", pid, token=m.page_token)
            except Exception as e:
                res[pid] = {"error": str(e)[:300]}
        for e in cfg.get("edit", []):
            try:
                res[e["post_id"]] = call("POST", e["post_id"], {"message": e["message"]}, token=m.page_token)
            except Exception as ex:
                res[e["post_id"]] = {"error": str(ex)[:300]}
        json.dump(res, open("tests/fbfix_result.json", "w"), indent=1)
        print(json.dumps(res, indent=1))
        return 0

    if mode == "igtest":  # build IG containers WITHOUT publishing (they expire on their own in 24 h)
        from meta import call
        m, cfg, res = api(), json.load(open("tests/igtest.json")), {}
        try:
            kids = []
            for s in cfg["slides"]:
                if s.get("video"):
                    cid = call("POST", f"{m.ig_id}/media", {"media_type": "VIDEO", "video_url": s["video"],
                               "is_carousel_item": "true"}, token=m.page_token)["id"]
                    m._ig_wait(cid)
                else:
                    cid = call("POST", f"{m.ig_id}/media", {"image_url": s["image"], "is_carousel_item": "true"},
                               token=m.page_token)["id"]
                kids.append(cid)
            parent = call("POST", f"{m.ig_id}/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                          "caption": "test (not published)"}, token=m.page_token)["id"]
            m._ig_wait(parent)
            res["carousel_container"] = "FINISHED"
            rc = call("POST", f"{m.ig_id}/media", {"media_type": "REELS", "video_url": cfg["reel"],
                      "caption": "test (not published)", "share_to_feed": "true", "cover_url": cfg["cover"]},
                      token=m.page_token)["id"]
            m._ig_wait(rc)
            res["reel_container"] = "FINISHED"
            res["ok"] = True
        except Exception as e:
            res["ok"], res["error"] = False, str(e)[:500]
        json.dump(res, open("tests/igtest_result.json", "w"), indent=1)
        print(json.dumps(res, indent=1))
        return 0

    if mode == "precheck":  # stdlib only: is there anything to render or publish now?
        work = False
        for it in load_items():
            st = status.get(it["id"], {})
            if st.get("done") or st.get("failed") or st.get("missed"):
                continue
            if it["_at"] - now() <= RENDER_AHEAD:
                work = True
                break
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            open(out, "a").write(f"work={'true' if work else 'false'}\n")
        print("work" if work else "nothing to do")
        return 0

    only = os.environ.get("ONLY_ID", "").strip()
    changed = False
    for it in load_items():
        if only and it["id"] != only:
            continue
        st = status.setdefault(it["id"], {"attempts": 0})
        if st.get("done") or st.get("failed") or st.get("missed"):
            continue
        at = it["_at"]
        due = now() >= at or (mode == "force" and only)
        if now() - at > GIVE_UP_AFTER and not st.get("ig"):
            st["missed"] = now().isoformat()
            changed = True
            continue
        try:
            if it["type"] == "reel" and not st.get("video_url") and (at - now() <= RENDER_AHEAD or due):
                wd = tempfile.mkdtemp()
                t0 = time.time()
                st.update(render_item(it, wd))
                st["rendered_at"] = now().isoformat()
                st["render_seconds"] = round(time.time() - t0)
                changed = True
                print(f"rendered {it['id']} -> {st['video_url']}")
            if it["type"] == "carousel" and not st.get("slides") and (at - now() <= RENDER_AHEAD or due):
                st.update(prepare_carousel(it, tempfile.mkdtemp()))
                changed = True
                print(f"prepared {it['id']} slides")
            if it.get("dry_run") and (st.get("video_url") or st.get("slides")):
                st["done"] = now().isoformat()
                st["dry_run"] = True
                changed = True
                continue
            if not due or mode == "render":
                continue
            if it["type"] == "reel" and st.get("video_url"):
                if not st.get("ig"):
                    st["ig"] = api().ig_reel(st["video_url"], fix_caption(it["caption_ig"]), st.get("cover_url"))
                    changed = True
                if not st.get("fb") and it.get("caption_fb"):
                    st["fb"] = api().fb_reel(st["video_url"], fix_caption(it["caption_fb"]))
                    changed = True
            elif it["type"] == "carousel":
                if not st.get("ig"):
                    st["ig"] = api().ig_carousel(st.get("slides") or it["slides"], fix_caption(it["caption_ig"]))
                    changed = True
                if not st.get("fb") and it.get("caption_fb"):
                    imgs = [x["image"] for x in (st.get("slides") or it["slides"]) if x.get("image")]
                    st["fb"] = api().fb_album(imgs, fix_caption(it["caption_fb"]))
                    changed = True
            if st.get("ig") and (st.get("fb") or not it.get("caption_fb")):
                st["done"] = now().isoformat()
                st.pop("error", None)
                changed = True
                print(f"published {it['id']}: IG {st['ig'].get('permalink')} | FB {(st.get('fb') or {}).get('permalink')}")
        except Exception as e:
            st["attempts"] = st.get("attempts", 0) + 1
            st["error"] = str(e)[:500].replace(token, "***") if token else str(e)[:500]
            st["error_at"] = now().isoformat()
            if st["attempts"] >= MAX_ATTEMPTS:
                st["failed"] = now().isoformat()
            changed = True
            print(f"ERROR {it['id']}: {st['error']}")
            traceback.print_exc()
    if changed:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        json.dump(status, open(STATUS, "w"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
