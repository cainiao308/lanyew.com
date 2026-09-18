# Assets provenance

Source: **live site only** — `https://lanyew.com` (TLS cert currently issued for `lanyew.cc`; fetched with certificate verification disabled). No Wayback / archive.org.

## Theme / chrome
- Template: emlog `lanyesimpleone` under `/content/templates/lanyesimpleone/`
- CSS: `font-awesome.css`, `style.css`, `markdown.css` (+ nested webfonts)
- JS: `jquery.min.js`, `script.js`, `lanye_music.js`, kefu/player plugins
- Logo: `/content/uploadfile/tpl_options/logoimg.jpg`
- Favicon: live `/favicon.ico` → `public/favicon.ico`, `src/app/icon.png`, `src/app/apple-icon.png`

## Localized remote assets
- Gravatar avatars via `images.weserv.nl` → `public/assets/remote/weserv-*.jpg`
- Other hotlinked images → `public/assets/remote/*`
- Dynamic `/api/label/?…` badges snapshotted → `public/assets/api-label/*.png`
- One badge (`运行天数/runday`) failed to fetch (network); local placeholder PNG used

## Placeholders / gaps
- Theme CSS refs missing on origin (`plbg.png`, `seeking.gif`, `stop.gif`) → 1×1 transparent placeholders
- ~100 historical `/content/uploadfile/…` and third-party images returned 404/timeout on live origin → gray/empty placeholders so local `src` still 200
- Malformed historical post markup (JS fragments as `src`) left neutralized or as on live
- External nav targets (`blws.cc`, `laoge.pw`, `luobow.cc`) intentionally remain absolute outbound links

## AdSense (public on live page)
- Live page includes `ca-pub-6722799738440939`
- Live `/ads.txt`: `google.com, pub-6722799738440939, DIRECT, f08c47fec0942fa0`
- Wired via env only (see `.env.example`); ads script loads only when enabled+client set

## Counts
- Mirrored pages: **1155**
- Asset log OK: **2652** (plus placeholders for remaining referenced locals)
- Asset log FAIL (origin): **0** (see `raw/asset-log.json` / placeholders)
