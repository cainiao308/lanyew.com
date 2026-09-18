#!/usr/bin/env python3
"""Generate sitemap/robots, retry failed pages, audit local assets."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "src" / "data" / "pages.json"
PUBLIC = ROOT / "public"
META = ROOT / "raw" / "crawl-meta.json"
ASSET_LOG = ROOT / "raw" / "asset-log.json"

spec = importlib.util.spec_from_file_location("crawl", ROOT / "scripts" / "crawl_live.py")
crawl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crawl)


def write_sitemap(pages: dict) -> None:
    urls = []
    for path in sorted(pages.keys(), key=lambda p: (p != "/", p)):
        loc = f"https://lanyew.com{path if path != '/' else '/'}"
        # encode path properly for XML
        parts = urllib.parse.urlsplit(loc)
        enc_path = urllib.parse.quote(parts.path, safe="/")
        loc = urllib.parse.urlunsplit((parts.scheme, parts.netloc, enc_path, "", ""))
        urls.append(loc)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for i, loc in enumerate(urls):
        pri = "1.0" if i == 0 else "0.8"
        lines.append("<url>")
        lines.append(f"<loc>{loc}</loc>")
        lines.append("<changefreq>weekly</changefreq>")
        lines.append(f"<priority>{pri}</priority>")
        lines.append("</url>")
    lines.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("sitemap", len(urls))


def write_robots() -> None:
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: https://lanyew.com/sitemap.xml\n",
        encoding="utf-8",
    )


def audit_assets(pages: dict) -> dict:
    refs = set()
    pat = re.compile(r"""(?:src|href)=["'](/[^"']+)["']""")
    css_url = re.compile(r"""url\((['"]?)(/[^)'"]+)\1\)""")
    for page in pages.values():
        for m in pat.finditer(page.get("html", "")):
            refs.add(m.group(1).split("?")[0])
        for m in css_url.finditer(page.get("html", "")):
            refs.add(m.group(2).split("?")[0])
        for c in page.get("css") or []:
            refs.add(c.split("?")[0])
        for j in page.get("js") or []:
            refs.add(j.split("?")[0])
        for m in css_url.finditer(page.get("inlineStyle") or ""):
            refs.add(m.group(2).split("?")[0])

    # also scan local css files
    for css in PUBLIC.rglob("*.css"):
        try:
            text = css.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in css_url.finditer(text):
            refs.add(m.group(2).split("?")[0])
        # relative urls in css
        for m in re.finditer(r"""url\((['"]?)(?!data:|/|https?:)([^)'"]+)\1\)""", text):
            rel = m.group(2)
            abs_path = "/" + str((css.parent / rel).resolve().relative_to(PUBLIC.resolve())).replace("\\", "/")
            refs.add(abs_path)

    missing = []
    ok = []
    for ref in sorted(refs):
        if not ref.startswith("/"):
            continue
        # skip page routes
        if ref.endswith(".html") or ref.startswith("/sort/") or ref.startswith("/tag/") or ref.startswith("/page/"):
            continue
        if ref == "/":
            continue
        dest = PUBLIC / ref.lstrip("/")
        if dest.is_file() and dest.stat().st_size > 0:
            ok.append(ref)
        else:
            # might be a page path without extension
            if ref in pages:
                continue
            missing.append(ref)
    return {"ok": len(ok), "missing": missing, "refs": len(refs)}


def retry_fails() -> None:
    if not META.exists():
        return
    meta = json.loads(META.read_text())
    fails = meta.get("fail") or []
    if not fails:
        print("no fails to retry")
        return
    pages = json.loads(PAGES.read_text()) if PAGES.exists() else {}
    asset_status = {}
    if ASSET_LOG.exists():
        asset_status = {k: v for k, v in json.loads(ASSET_LOG.read_text()).items() if v.get("ok")}
    still = []
    for item in fails:
        url = item.get("url") if isinstance(item, dict) else item
        if not url:
            continue
        path = crawl.path_from_url(url)
        key = crawl.page_key(path)
        if key in pages and len(pages[key].get("html", "")) > 200:
            continue
        time.sleep(0.3)
        code, data, _ = crawl.fetch(url)
        if code != 200 or not data:
            print("retry fail", code, url)
            still.append({"url": url, "code": code})
            continue
        try:
            html = data.decode("utf-8")
        except Exception:
            html = data.decode("gbk", errors="replace")
        if "<html" not in html.lower():
            still.append({"url": url, "code": code, "reason": "not-html"})
            continue
        meta_p = crawl.extract_meta(html)
        body, css_list, js_list, inline = crawl.extract_body_and_head_assets(html)
        body2, assets = crawl.rewrite_html(body, url)
        inline2, _ = crawl.rewrite_html(inline, url) if inline else ("", set())
        local_css, local_js = [], []
        for c in css_list:
            absu = urllib.parse.urljoin(url, c)
            lp = crawl.safe_public_path(absu)
            if lp:
                local_css.append(lp.split("?")[0])
                assets.add(absu)
        for j in js_list:
            absu = urllib.parse.urljoin(url, j)
            lp = crawl.safe_public_path(absu)
            if lp:
                local_js.append(lp.split("?")[0])
                assets.add(absu)
        for a in sorted(assets):
            lp = crawl.safe_public_path(a)
            if lp:
                crawl.download_asset(a, lp, asset_status)
        pages[key] = {
            "title": meta_p["title"] or "蓝叶网",
            "description": meta_p["description"],
            "robots": "index,follow",
            "canonical": f"https://lanyew.com{key if key != '/' else '/'}",
            "ogTitle": meta_p["title"] or "蓝叶网",
            "ogDescription": meta_p["description"],
            "ogType": "website",
            "ogUrl": f"https://lanyew.com{key if key != '/' else '/'}",
            "css": local_css,
            "js": local_js,
            "inlineStyle": inline2 or inline,
            "html": body2,
            "source": url,
        }
        print("retry OK", key)
    meta["fail"] = still
    meta["page_count"] = len(pages)
    PAGES.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    ASSET_LOG.write_text(json.dumps(asset_status, ensure_ascii=False, indent=2))
    print("after retry pages", len(pages), "still fail", len(still))


def main():
    retry_fails()
    pages = json.loads(PAGES.read_text())
    write_sitemap(pages)
    write_robots()
    audit = audit_assets(pages)
    (ROOT / "raw" / "asset-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    print("audit ok", audit["ok"], "missing", len(audit["missing"]))
    for m in audit["missing"][:40]:
        print("  missing", m)


if __name__ == "__main__":
    main()
