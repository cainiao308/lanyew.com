#!/usr/bin/env python3
"""Crawl live https://lanyew.com (insecure SSL OK — cert is for lanyew.cc) and prepare mirrored content."""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
HTML_DIR = RAW / "html"
ASSET_RAW = RAW / "assets"
PUBLIC = ROOT / "public"
PAGES_OUT = ROOT / "src" / "data" / "pages.json"
META_OUT = ROOT / "raw" / "crawl-meta.json"
ASSET_LOG = ROOT / "raw" / "asset-log.json"

BASE = "https://lanyew.com"
SLEEP = 0.2
UA = "Mozilla/5.0 (compatible; LanyewMirror/1.0; +local-dev)"

CTX = ssl._create_unverified_context()

SKIP_EXT_HOSTS = {
    "pagead2.googlesyndication.com",
    "hm.baidu.com",
    "www.google-analytics.com",
    "www.googletagmanager.com",
    "cn.gravatar.com",
}

# Keep same-origin path structure under public/
LOCALIZE_HOSTS = {"lanyew.com", "www.lanyew.com", "lanyew.cc", "www.lanyew.cc"}


def fetch(url: str, timeout: float = 45) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, data, ctype
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", e.headers.get("Content-Type", "") if e.headers else ""
    except Exception as e:
        return 0, str(e).encode(), ""


def path_from_url(url: str) -> str:
    p = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(p.path or "/")
    if not path.startswith("/"):
        path = "/" + path
    return path



ASSET_EXT = {".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp3", ".mp4", ".webm", ".map", ".cur", ".bmp"}
ASSET_LIKE = __import__("re").compile(r"\.(css|js|mjs|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|eot|otf|mp3|mp4|webm|map|cur|bmp)(\?|$)", __import__("re").I)

def looks_like_asset(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    path = p.path or ""
    host = (p.hostname or "").lower()
    if host in SKIP_EXT_HOSTS:
        return False
    if "/api/label" in path or path.endswith(".php"):
        return True
    if host in ("images.weserv.nl", "cn.gravatar.com", "www.gravatar.com", "secure.gravatar.com"):
        return True
    if ASSET_LIKE.search(path):
        return True
    if any(x in host for x in ("image.baidu.com", "sinaimg.cn")):
        return True
    return False

def safe_public_path(url: str) -> str | None:
    """Map absolute/relative asset URL to a public/ relative path, or None to leave as-is."""
    absu = urllib.parse.urljoin(BASE + "/", url)
    p = urllib.parse.urlparse(absu)
    host = (p.hostname or "").lower()

    if host in SKIP_EXT_HOSTS:
        return None
    if not looks_like_asset(absu):
        return None

    # images.weserv.nl proxy → download and store under /assets/remote/
    if host == "images.weserv.nl":
        qs = urllib.parse.parse_qs(p.query)
        inner = qs.get("url", [None])[0]
        if inner:
            h = hashlib.sha1(inner.encode()).hexdigest()[:16]
            # guess ext
            ext = ".jpg"
            if "png" in inner.lower():
                ext = ".png"
            elif "gif" in inner.lower():
                ext = ".gif"
            elif "webp" in inner.lower():
                ext = ".webp"
            return f"/assets/remote/weserv-{h}{ext}"
        h = hashlib.sha1(absu.encode()).hexdigest()[:16]
        return f"/assets/remote/weserv-{h}.jpg"

    if host and host not in LOCALIZE_HOSTS and not absu.startswith(BASE):
        # other remote — localize under assets/remote
        h = hashlib.sha1(absu.encode()).hexdigest()[:20]
        path = p.path or ""
        ext = Path(path.split("?")[0]).suffix.lower()
        if "jpg" in path or "jpeg" in absu.lower():
            ext = ".jpg"
        elif "png" in absu.lower():
            ext = ".png"
        elif "gif" in absu.lower():
            ext = ".gif"
        elif "webp" in absu.lower():
            ext = ".webp"
        if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".css", ".js", ".woff", ".woff2", ".ttf", ".eot"}:
            ext = ".jpg"
        return f"/assets/remote/{h}{ext}"

    path = path_from_url(absu)
    # php / api endpoints that return assets → give file extensions
    if path.startswith("/api/label"):
        q = p.query
        h = hashlib.sha1((path + "?" + q).encode()).hexdigest()[:16]
        return f"/assets/api-label/{h}.png"
    if path.endswith(".php") or "lanyebdplayer_js.php" in path:
        h = hashlib.sha1((path + (("?" + p.query) if p.query else "")).encode()).hexdigest()[:12]
        name = Path(path).stem
        return f"/assets/php/{name}-{h}.js"

    # double slash in upload path
    path = path.replace("//", "/")
    return path


class AttrCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: set[str] = set()

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        for k in ("href", "src", "data-src", "poster"):
            if k in ad and ad[k]:
                self.refs.add(ad[k])
        if "style" in ad:
            for m in re.findall(r"url\((['\"]?)([^)'\"]+)\1\)", ad["style"]):
                self.refs.add(m[1])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


CSS_URL_RE = re.compile(r"url\((['\"]?)([^)'\"]+)\1\)", re.I)
IMPORT_RE = re.compile(r"@import\s+(?:url\()?['\"]?([^'\"\);]+)", re.I)


def extract_css_urls(css: str) -> list[str]:
    out = []
    for m in CSS_URL_RE.finditer(css):
        out.append(m.group(2))
    for m in IMPORT_RE.finditer(css):
        out.append(m.group(1))
    return out


def rewrite_html(html: str, page_url: str) -> tuple[str, set[str]]:
    """Rewrite asset URLs to local paths; same-origin page links become root-relative."""
    assets: set[str] = set()

    def repl_attr(m):
        attr, quote, ref = m.group(1), m.group(2), m.group(3)
        if not ref or ref.startswith(("data:", "javascript:", "mailto:", "#")):
            return m.group(0)
        absu = urllib.parse.urljoin(page_url, ref)
        host = (urllib.parse.urlparse(absu).hostname or "").lower()
        if looks_like_asset(absu):
            lp = safe_public_path(absu)
            if lp:
                assets.add(absu)
                return f"{attr}={quote}{lp}{quote}"
        if host in LOCALIZE_HOSTS or (not host and not ref.startswith("http")):
            path = urllib.parse.urlparse(absu).path or "/"
            if path in ("/index.html", "/index.htm"):
                path = "/"
            return f"{attr}={quote}{path}{quote}"
        return m.group(0)

    out = re.sub(
        r"(src|href|data-src|poster)\s*=\s*(['\"])([^'\"]+)\2",
        repl_attr,
        html,
        flags=re.I,
    )

    def repl_css(m):
        q, u = m.group(1), m.group(2)
        if not u or u.startswith("data:"):
            return m.group(0)
        absu = urllib.parse.urljoin(page_url, u)
        if looks_like_asset(absu):
            lp = safe_public_path(absu)
            if lp:
                assets.add(absu)
                return f"url({q}{lp}{q})"
        host = (urllib.parse.urlparse(absu).hostname or "").lower()
        if host in LOCALIZE_HOSTS:
            return f"url({q}{urllib.parse.urlparse(absu).path or '/'}{q})"
        return m.group(0)

    out = re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", repl_css, out)
    for h in ("https://www.lanyew.com", "http://www.lanyew.com", "https://lanyew.com", "http://lanyew.com", "https://lanyew.cc", "http://lanyew.cc"):
        out = out.replace(h, "")
    out = out.replace('href=""', 'href="/"').replace("href=''", "href='/'")
    out = out.replace('href="/index.html"', 'href="/"')
    return out, assets


def extract_meta(html: str) -> dict:
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    def meta_name(name):
        m = re.search(rf'''<meta[^>]+name=["']{re.escape(name)}["'][^>]+content=["']([^"']*)["']''', html, re.I)
        if not m:
            m = re.search(rf'''<meta[^>]+content=["']([^"']*)["'][^>]+name=["']{re.escape(name)}["']''', html, re.I)
        return m.group(1) if m else ""
    def meta_prop(prop):
        m = re.search(rf'''<meta[^>]+property=["']{re.escape(prop)}["'][^>]+content=["']([^"']*)["']''', html, re.I)
        if not m:
            m = re.search(rf'''<meta[^>]+content=["']([^"']*)["'][^>]+property=["']{re.escape(prop)}["']''', html, re.I)
        return m.group(1) if m else ""
    can = ""
    m = re.search(r'''<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']''', html, re.I)
    if not m:
        m = re.search(r'''<link[^>]+href=["']([^"']+)["'][^>]+rel=["']canonical["']''', html, re.I)
    if m:
        can = m.group(1)
    return {
        "title": title,
        "description": meta_name("description"),
        "keywords": meta_name("keywords"),
        "canonical": can,
        "ogTitle": meta_prop("og:title"),
        "ogDescription": meta_prop("og:description"),
        "ogType": meta_prop("og:type") or "website",
        "ogUrl": meta_prop("og:url"),
    }


def extract_body_and_head_assets(html: str) -> tuple[str, list[str], list[str], str]:
    """Return (body_inner_html, css_hrefs, js_srcs, inline_head_style)."""
    css, js = [], []
    for m in re.finditer(r'''<link[^>]+href=["']([^"']+)["'][^>]*>''', html, re.I):
        tag = m.group(0)
        if "stylesheet" in tag.lower() or tag.lower().endswith('.css">') or ".css" in m.group(1):
            css.append(m.group(1))
    for m in re.finditer(r'''<script[^>]+src=["']([^"']+)["'][^>]*>\s*</script>''', html, re.I):
        src = m.group(1)
        if "adsbygoogle" in src or "hm.baidu" in src or "googlesyndication" in src:
            continue
        js.append(src)
    inline_styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.I | re.S)
    # drop PHP warning after </html>
    html = re.split(r"</html>", html, flags=re.I)[0] + "</html>"
    bm = re.search(r"<body[^>]*>(.*)</body>", html, re.I | re.S)
    body = bm.group(1) if bm else html
    # remove baidu analytics leftover scripts in body
    body = re.sub(r"<script[^>]*>\s*var _hmt[\s\S]*?</script>", "", body, flags=re.I)
    return body, css, js, "\n".join(inline_styles)


def page_key(path: str) -> str:
    if not path or path == "/":
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    # keep .html paths as-is without forcing trailing slash
    return path


ASSET_EXT = {
    ".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp3", ".mp4", ".webm", ".map",
    ".cur", ".bmp",
}

def is_downloadable_asset(url: str, local_path: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    lp = local_path.lower()
    if lp.startswith("/assets/"):
        return True
    if path.endswith(".php") or "/api/label" in path:
        return True
    ext = Path(path).suffix
    if ext in ASSET_EXT:
        return True
    if Path(lp).suffix in ASSET_EXT:
        return True
    # fontawesome etc without clear ext already covered
    return False

def download_asset(url: str, local_path: str, asset_status: dict) -> bool:
    if not looks_like_asset(url):
        return False
    if local_path in asset_status and asset_status[local_path].get("ok"):
        return True
    dest = PUBLIC / local_path.lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        asset_status[local_path] = {"ok": True, "url": url, "bytes": dest.stat().st_size, "cached": True}
        return True
    time.sleep(SLEEP)
    code, data, ctype = fetch(url)
    if code != 200 or not data:
        asset_status[local_path] = {"ok": False, "url": url, "code": code, "ctype": ctype}
        print(f"  ASSET FAIL {code} {url} -> {local_path}")
        return False
    dest.write_bytes(data)
    asset_status[local_path] = {"ok": True, "url": url, "bytes": len(data), "ctype": ctype}
    print(f"  asset {len(data):6d} {local_path}")
    # if css, queue nested
    if local_path.endswith(".css") or "css" in (ctype or "").lower():
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        base = url
        for ref in extract_css_urls(text):
            if not ref or ref.startswith("data:"):
                continue
            absu = urllib.parse.urljoin(base, ref)
            lp = safe_public_path(absu)
            if lp and lp not in asset_status:
                download_asset(absu, lp, asset_status)
                # rewrite css file
        # rewrite css urls to local
        def css_repl(m):
            q, u = m.group(1), m.group(2)
            if u.startswith("data:"):
                return m.group(0)
            absu = urllib.parse.urljoin(base, u)
            lp = safe_public_path(absu)
            if not lp:
                return m.group(0)
            return f"url({q}{lp}{q})"
        new_css = CSS_URL_RE.sub(css_repl, text)
        # also rewrite absolute hosts
        for h in ("https://lanyew.com", "http://lanyew.com", "https://lanyew.cc"):
            new_css = new_css.replace(h, "")
        dest.write_text(new_css, encoding="utf-8")
    return True


def load_url_list() -> list[str]:
    urls = []
    f = ROOT / "raw" / "sitemap-urls.txt"
    if f.exists():
        urls = [u.strip() for u in f.read_text().splitlines() if u.strip()]
    # pagination not always in sitemap
    for i in range(2, 53):
        urls.append(f"{BASE}/page/{i}")
    # ensure nav
    extra = [
        f"{BASE}/",
        f"{BASE}/liuyanben.html",
        f"{BASE}/links.html",
        f"{BASE}/about.html",
        f"{BASE}/sort/wangzhanmuban",
        f"{BASE}/sort/zuopin",
        f"{BASE}/sort/youxixiazai",
        f"{BASE}/sort/greensoft",
        f"{BASE}/sort/rizhi",
        f"{BASE}/sort/web",
        f"{BASE}/tag/emlog插件",
        f"{BASE}/tag/zblog插件",
    ]
    seen = set()
    out = []
    for u in extra + urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main():
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_RAW.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    urls = load_url_list()
    print(f"Will crawl {len(urls)} URLs")

    asset_status: dict = {}
    if ASSET_LOG.exists():
        try:
            asset_status = json.loads(ASSET_LOG.read_text())
        except Exception:
            pass

    pages: dict[str, dict] = {}
    if PAGES_OUT.exists():
        try:
            pages = json.loads(PAGES_OUT.read_text())
        except Exception:
            pass

    crawl_meta = {"ok": [], "fail": [], "started": time.strftime("%Y-%m-%d %H:%M:%S")}

    # seed known chrome assets from homepage
    seed_assets = [
        f"{BASE}/favicon.ico",
        f"{BASE}/content/templates/lanyesimpleone/css/fontawesom/font-awesome.css",
        f"{BASE}/content/templates/lanyesimpleone/css/style.css?var=2.3.1.5",
        f"{BASE}/content/templates/lanyesimpleone/css/markdown.css?var=2.1",
        f"{BASE}/content/templates/lanyesimpleone/js/jquery.min.js",
        f"{BASE}/content/templates/lanyesimpleone/js/script.js?var=2.3.1",
        f"{BASE}/content/uploadfile/tpl_options/logoimg.jpg",
        f"{BASE}/content/templates/lanyesimpleone/images/avatar6.jpg",
        f"{BASE}/content/templates/lanyesimpleone/images/yxzz.gif",
        f"{BASE}/content/plugins/lanyekefu/static/uptop.png",
        f"{BASE}/content/plugins/lanyekefu/static/lanyekefu.js",
        f"{BASE}/content/templates/lanyesimpleone/lanye_music/lanye_music.js",
        f"{BASE}/content/plugins/lanyebdplayer/player/cyberplayer.js",
        f"{BASE}/content/plugins/lanyebdplayer/lanyebdplayer_js.php",
    ]
    for u in seed_assets:
        lp = safe_public_path(u)
        if lp:
            download_asset(u.split("?")[0] if "?" in u and not u.endswith(".php") and "style.css" not in u and "script.js" not in u and "markdown.css" not in u else u, lp, asset_status)
            # for versioned css/js, also try without query using same local path from safe_public_path which strips query via path_from_url
            # re-download with full URL if needed
            if "?" in u:
                lp2 = safe_public_path(u.split("?")[0])
                # safe_public_path uses path only so same; fetch with query
                download_asset(u, lp, asset_status)

    ASSET_LOG.write_text(json.dumps(asset_status, ensure_ascii=False, indent=2))

    shared_css: list[str] = []
    shared_js: list[str] = []
    shared_inline = ""

    for i, url in enumerate(urls):
        path = path_from_url(url)
        key = page_key(path)
        # skip if already have recent
        if key in pages and pages[key].get("html") and len(pages[key]["html"]) > 200:
            if i % 50 == 0:
                print(f"[{i}/{len(urls)}] skip cached {key}")
            continue

        time.sleep(SLEEP)
        code, data, ctype = fetch(url)
        if code != 200 or not data:
            print(f"[{i}/{len(urls)}] FAIL {code} {url}")
            crawl_meta["fail"].append({"url": url, "code": code})
            continue
        try:
            html = data.decode("utf-8")
        except Exception:
            html = data.decode("gbk", errors="replace")

        # strip php warnings after body
        if "<html" not in html.lower():
            print(f"[{i}/{len(urls)}] not html {url}")
            crawl_meta["fail"].append({"url": url, "code": code, "reason": "not-html"})
            continue

        meta = extract_meta(html)
        body, css_list, js_list, inline = extract_body_and_head_assets(html)
        if not shared_css and css_list:
            shared_css = css_list
            shared_js = js_list
            shared_inline = inline

        body2, assets = rewrite_html(body, url)
        # also rewrite css/js lists
        local_css = []
        for c in css_list:
            absu = urllib.parse.urljoin(url, c)
            lp = safe_public_path(absu)
            if lp:
                local_css.append(lp)
                assets.add(absu)
        local_js = []
        for j in js_list:
            absu = urllib.parse.urljoin(url, j)
            lp = safe_public_path(absu)
            if lp:
                local_js.append(lp)
                assets.add(absu)

        for a in sorted(assets):
            lp = safe_public_path(a)
            if lp:
                download_asset(a, lp, asset_status)

        # rewrite inline style urls already done in body via rewrite_html
        inline2, _ = rewrite_html(f"<style>{inline}</style>", url) if inline else ("", set())
        if inline2.startswith("<style>"):
            inline2 = inline2[7:-8]

        pages[key] = {
            "title": meta["title"] or "蓝叶网",
            "description": meta["description"],
            "robots": "index,follow",
            "canonical": f"https://lanyew.com{key if key != '/' else '/'}",
            "ogTitle": meta["ogTitle"] or meta["title"],
            "ogDescription": meta["ogDescription"] or meta["description"],
            "ogType": meta["ogType"],
            "ogUrl": meta["ogUrl"] or f"https://lanyew.com{key if key != '/' else '/'}",
            "css": local_css,
            "js": local_js,
            "inlineStyle": inline if not inline2 else inline2,
            "html": body2,
            "source": url,
        }
        crawl_meta["ok"].append(key)
        print(f"[{i}/{len(urls)}] OK {key} ({len(body2)} bytes)")

        if i % 25 == 0:
            PAGES_OUT.parent.mkdir(parents=True, exist_ok=True)
            PAGES_OUT.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
            ASSET_LOG.write_text(json.dumps(asset_status, ensure_ascii=False, indent=2))
            META_OUT.write_text(json.dumps(crawl_meta, ensure_ascii=False, indent=2))

    # save shared chrome note
    crawl_meta["shared_css"] = shared_css
    crawl_meta["shared_js"] = shared_js
    crawl_meta["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    crawl_meta["page_count"] = len(pages)
    crawl_meta["asset_ok"] = sum(1 for v in asset_status.values() if v.get("ok"))
    crawl_meta["asset_fail"] = sum(1 for v in asset_status.values() if not v.get("ok"))

    PAGES_OUT.parent.mkdir(parents=True, exist_ok=True)
    PAGES_OUT.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    ASSET_LOG.write_text(json.dumps(asset_status, ensure_ascii=False, indent=2))
    META_OUT.write_text(json.dumps(crawl_meta, ensure_ascii=False, indent=2))
    print(f"DONE pages={len(pages)} assets_ok={crawl_meta['asset_ok']} assets_fail={crawl_meta['asset_fail']}")


if __name__ == "__main__":
    main()
