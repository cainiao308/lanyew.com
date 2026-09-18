# lanyew.com mirror report

- **Project path:** `/workspace/lanyew.com`
- **Source:** live `https://lanyew.com` (www → apex 301; `lanyew.cc` serves same content; cert CN=`lanyew.cc`)
- **Stack:** Next.js 16 App Router, Vercel-ready (`vercel.json` framework nextjs)
- **Built at:** 2026-09-18 09:51:18 Asia/Shanghai
- **Pages mirrored:** 1155
- **Categories:** {"home": 1, "liuyanben.html": 1, "links.html": 1, "about.html": 1, "sort": 6, "youxixiazai": 12, "zuopin": 103, "wangzhanmuban": 46, "web": 318, "rizhi": 458, "greensoft": 87, "dabaobo.html": 1, "wenda.html": 1, "tag": 68, "pagination": 51}
- **Build:** `npm run build` succeeded (SSG ~1159 routes including home, catch-all, ads.txt, icons)
- **AdSense env:** `NEXT_PUBLIC_ADSENSE_ENABLED`, `NEXT_PUBLIC_ADSENSE_CLIENT`, `ADS_TXT_CONTENT` (seeded in `.env.example` from public live values; default enabled=false)
- **SEO files:** `public/sitemap.xml`, `public/robots.txt` → `https://lanyew.com`
- **GitHub push:** not done (parent handles after smoke)

## Local smoke (verified)

- Dev server running: **http://localhost:3000** (bind `0.0.0.0:3000`)
- HTTP 200: `/`, `/zuopin/lanyebadge.html`, `/sort/wangzhanmuban`, `/page/2`, `/liuyanben.html`
- Assets 200: logo JPG, theme `style.css`, `favicon.ico`
- `/ads.txt` returns empty until `ADS_TXT_CONTENT` is set in env (pattern OK; value in `.env.example`)

## Completeness
- Nav routes: home, sorts, guestbook, links, about, tags (from sitemap), pagination `/page/2`–`/page/52`
- Article HTML from live sitemap (~1100 URLs) + retries
- Visual chrome (header/menu/footer/tags/comments/friend links/kefu) preserved from live HTML/CSS/JS
- Gaps: some old upload images 404 on origin; dynamic uptime badge placeholder; comment posting / search are static (no PHP backend); Baidu analytics stripped; AdSense off until env enabled

## How to open locally
```bash
cd /workspace/lanyew.com
npm install
npm run dev
# → http://localhost:3000
```
