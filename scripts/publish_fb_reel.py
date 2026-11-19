"""Publish pending Reel jobs to the Fanart Designs MX Facebook Page.

Each job is jobs/<id>.json:
  {"id": "...", "video_url": "https://... (public mp4, 9:16)", "description": "..."}
A result is written next to it as jobs/<id>.result.json (never contains the token).

Uses the Facebook Reels Publishing API (Graph API v26.0):
  1. POST /{page-id}/video_reels upload_phase=start  -> video_id
  2. POST rupload.facebook.com/video-upload/v26.0/{video_id} with header file_url (hosted file)
  3. POST /{page-id}/video_reels upload_phase=finish video_state=PUBLISHED description=...
  4. GET /{video_id}?fields=status,permalink_url until published
"""
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

V = "v26.0"
TOKEN = os.environ.get("FB_PAGE_TOKEN", "").strip()
PAGE = os.environ.get("FB_PAGE_ID", "").strip()


def call(method, url, params=None, headers=None):
    data = None
    if params is not None:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body).get("error", {})
            msg = f"{err.get('type')} {err.get('code')}: {err.get('message')}"
        except Exception:
            msg = body[:300]
        raise RuntimeError(f"HTTP {e.code} on {url.split('?')[0]} -> {msg}") from None


GRAPH = f"https://graph.facebook.com/{V}"
PAGE_NAME_HINT = "fanart designs"


def resolve_page():
    """Works with either a Page token or a (long-lived) user token.
    Returns (page_id, page_token, info) — info never contains a token."""
    me = call("GET", f"{GRAPH}/me?" + urllib.parse.urlencode({"fields": "id,name", "access_token": TOKEN}))
    try:
        acc = call("GET", f"{GRAPH}/me/accounts?" + urllib.parse.urlencode(
            {"fields": "id,name,access_token", "limit": 100, "access_token": TOKEN}))
        pages = acc.get("data", [])
    except RuntimeError:
        pages = None  # a Page token has no /accounts edge
    if pages is None:
        return me["id"], TOKEN, {"token_kind": "page", "page_id": me["id"], "page_name": me.get("name")}
    for p in pages:
        if p.get("id") == PAGE or PAGE_NAME_HINT in (p.get("name") or "").lower():
            return p["id"], p["access_token"], {"token_kind": "user", "page_id": p["id"], "page_name": p.get("name"),
                                                  "user_name": me.get("name")}
    names = [p.get("name") for p in pages]
    raise RuntimeError(f"token belongs to '{me.get('name')}' but no matching Page in /me/accounts (pages seen: {names})")


def publish(job, page, token):
    graph = GRAPH
    PAGE, TOKEN = page, token  # local overrides: page id/token resolved at runtime
    start = call("POST", f"{graph}/{PAGE}/video_reels", {"upload_phase": "start", "access_token": TOKEN})
    vid = start["video_id"]
    up = call("POST", f"https://rupload.facebook.com/video-upload/{V}/{vid}",
              params={}, headers={"Authorization": f"OAuth {TOKEN}", "file_url": job["video_url"]})
    if not up.get("success"):
        raise RuntimeError(f"upload not accepted: {up}")
    fin = call("POST", f"{graph}/{PAGE}/video_reels", {
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": job.get("description", ""), "access_token": TOKEN})
    if not fin.get("success"):
        raise RuntimeError(f"finish not accepted: {fin}")
    status, permalink = {}, None
    for _ in range(60):
        info = call("GET", f"{graph}/{vid}?" + urllib.parse.urlencode(
            {"fields": "status,permalink_url", "access_token": TOKEN}))
        status = info.get("status", {})
        permalink = info.get("permalink_url")
        vs = status.get("video_status")
        pub = (status.get("publishing_phase") or {}).get("status")
        if vs in ("error", "upload_failed", "expired"):
            raise RuntimeError(f"video failed: {json.dumps(status)}")
        if pub == "complete" or vs == "ready" and pub in (None, "complete"):
            break
        time.sleep(15)
    if permalink and permalink.startswith("/"):
        permalink = "https://www.facebook.com" + permalink
    return {"ok": True, "video_id": vid, "permalink": permalink, "status": status}


def main():
    jobs = sorted(j for j in glob.glob("jobs/*.json") if not j.endswith(".result.json"))
    if not jobs:
        print("No jobs.")
        return 0
    failed = 0
    for path in jobs:
        res_path = path[:-5] + ".result.json"
        if os.path.exists(res_path):
            print(f"{path}: already processed")
            continue
        job = json.load(open(path))
        if not TOKEN:
            res = {"ok": False, "error": "FB_PAGE_TOKEN secret is missing"}
        else:
            info = {}
            try:
                page_id, page_token, info = resolve_page()
                res = publish(job, page_id, page_token)
                res.update(info)
            except Exception as e:  # message never includes the token
                res = {"ok": False, "error": str(e).replace(TOKEN, "***"), **info}
        res["job"] = job.get("id")
        res["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(res, open(res_path, "w"), indent=1, ensure_ascii=False)
        print(f"{path}: {'OK ' + str(res.get('permalink')) if res.get('ok') else 'FAILED ' + res.get('error', '')}")
        failed += 0 if res.get("ok") else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
