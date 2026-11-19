"""Minimal Meta Graph API client for the Fanart Designs MX Page and @fanartdesignsmx.

The secret FB_PAGE_TOKEN may be a Page token or a long-lived user token; the Page token
and Instagram account id are resolved at runtime. Errors never include token values.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

V = "v26.0"
GRAPH = f"https://graph.facebook.com/{V}"
PAGE_HINT = os.environ.get("FB_PAGE_ID", "1199826319888363")
IG_HINT = os.environ.get("IG_USER_ID", "17841439102137781")


class GraphError(RuntimeError):
    pass


def _mask(s, *secrets):
    for x in secrets:
        if x:
            s = s.replace(x, "***")
    return s


def call(method, path, params=None, headers=None, token=None, base=GRAPH):
    params = dict(params or {})
    if token:
        params["access_token"] = token
    url = path if path.startswith("http") else f"{base}/{path.lstrip('/')}"
    data = None
    if method == "GET":
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body).get("error", {})
            msg = f"{err.get('type')} {err.get('code')}/{err.get('error_subcode')}: {err.get('message')}"
        except Exception:
            msg = body[:300]
        raise GraphError(_mask(f"HTTP {e.code} on {url.split('?')[0]} -> {msg}", token)) from None


class Meta:
    def __init__(self, token):
        self.user_token = token
        me = call("GET", "me", {"fields": "id,name"}, token=token)
        self.page_id, self.page_token = None, None
        try:
            pages = call("GET", "me/accounts", {"fields": "id,name,access_token", "limit": 100}, token=token).get("data", [])
        except GraphError:
            pages = None
        if pages is None:  # already a Page token
            self.page_id, self.page_token = me["id"], token
        else:
            for p in pages:
                if p["id"] == PAGE_HINT or "fanart designs" in (p.get("name") or "").lower():
                    self.page_id, self.page_token = p["id"], p["access_token"]
                    break
        if not self.page_id:
            raise GraphError("no Fanart Designs MX Page reachable with FB_PAGE_TOKEN")
        ig = call("GET", self.page_id, {"fields": "instagram_business_account"}, token=self.page_token)
        self.ig_id = (ig.get("instagram_business_account") or {}).get("id") or IG_HINT

    # ------------------------------------------------------------- Instagram
    def _ig_wait(self, cid, timeout=600):
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = call("GET", cid, {"fields": "status_code,status"}, token=self.page_token)
            code = st.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise GraphError(f"IG container {code}: {st.get('status')}")
            time.sleep(10)
        raise GraphError("IG container processing timed out")

    def _ig_publish(self, cid):
        mid = call("POST", f"{self.ig_id}/media_publish", {"creation_id": cid}, token=self.page_token)["id"]
        info = call("GET", mid, {"fields": "permalink"}, token=self.page_token)
        return {"media_id": mid, "permalink": info.get("permalink")}

    def ig_reel(self, video_url, caption, cover_url=None):
        p = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}
        if cover_url:
            p["cover_url"] = cover_url
        cid = call("POST", f"{self.ig_id}/media", p, token=self.page_token)["id"]
        self._ig_wait(cid)
        return self._ig_publish(cid)

    def ig_carousel(self, slides, caption):
        kids = []
        for s in slides:
            if s.get("video"):
                cid = call("POST", f"{self.ig_id}/media", {"media_type": "VIDEO", "video_url": s["video"],
                                                             "is_carousel_item": "true"}, token=self.page_token)["id"]
                self._ig_wait(cid)
            else:
                cid = call("POST", f"{self.ig_id}/media", {"image_url": s["image"], "is_carousel_item": "true"},
                           token=self.page_token)["id"]
            kids.append(cid)
        parent = call("POST", f"{self.ig_id}/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                                       "caption": caption}, token=self.page_token)["id"]
        self._ig_wait(parent)
        return self._ig_publish(parent)

    # ------------------------------------------------------------- Facebook
    def fb_reel(self, video_url, description):
        start = call("POST", f"{self.page_id}/video_reels", {"upload_phase": "start"}, token=self.page_token)
        vid = start["video_id"]
        up = call("POST", f"https://rupload.facebook.com/video-upload/{V}/{vid}", {},
                  headers={"Authorization": f"OAuth {self.page_token}", "file_url": video_url})
        if not up.get("success"):
            raise GraphError(f"FB upload not accepted: {up}")
        fin = call("POST", f"{self.page_id}/video_reels", {"upload_phase": "finish", "video_id": vid,
                                                            "video_state": "PUBLISHED", "description": description},
                   token=self.page_token)
        if not fin.get("success"):
            raise GraphError(f"FB finish not accepted: {fin}")
        permalink = None
        for _ in range(40):
            info = call("GET", vid, {"fields": "status,permalink_url"}, token=self.page_token)
            st = info.get("status", {})
            permalink = info.get("permalink_url")
            if st.get("video_status") in ("error", "upload_failed", "expired"):
                raise GraphError(f"FB video failed: {json.dumps(st)}")
            if (st.get("publishing_phase") or {}).get("status") == "complete":
                break
            time.sleep(15)
        if permalink and permalink.startswith("/"):
            permalink = "https://www.facebook.com" + permalink
        return {"video_id": vid, "permalink": permalink}

    def fb_album(self, image_urls, message):
        ids = []
        for u in image_urls:
            r = call("POST", f"{self.page_id}/photos", {"url": u, "published": "false"}, token=self.page_token)
            ids.append(r["id"])
        params = {"message": message}
        for i, x in enumerate(ids):
            params[f"attached_media[{i}]"] = json.dumps({"media_fbid": x})
        post = call("POST", f"{self.page_id}/feed", params, token=self.page_token)
        pid = post.get("id", "")
        return {"post_id": pid, "permalink": f"https://www.facebook.com/{pid}" if pid else None}

    def check(self):
        perms = call("GET", "me/permissions", token=self.user_token).get("data", [])
        ig = call("GET", self.ig_id, {"fields": "username"}, token=self.page_token)
        return {"page_id": self.page_id, "ig_id": self.ig_id, "ig_username": ig.get("username"),
                "granted": sorted(p["permission"] for p in perms if p.get("status") == "granted")}
