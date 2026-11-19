# insta360-cloud-dl

Bulk downloader for your Insta360 cloud library (Library/云空间) on **Linux**.
Pure Python standard library, zero dependencies.

Insta360 ships no Linux client (only Android / Windows). This tool talks
directly to the private REST API used by their web player, so you can pull
all original files (`.insv` / `.insp` / `.mp4` / `.lrv`) off the cloud in bulk.

中文版: [README.zh.md](./README.zh.md)

## Features

- `list` — fetch the full cloud asset list (cursor pagination, no size cap), exportable to CSV
- `dl` — download by `mediaId`, or `--all` for everything
  - parallel downloads with a **global rate limit** (default 8 MB/s, avoid throttling)
  - resumable (`.part` files): interrupt it and re-run the same command later;
    finished files are skipped automatically
  - expired tokens are refreshed automatically (`refreshToken`) and saved back
  - direct connection by default; system proxy is explicitly disabled
- `login` — interactive first-run: prints a step-by-step tutorial for grabbing
  your token from the browser, validates it, saves it as `token.txt`

## Getting started

```bash
# 1) one-time login: follow the on-screen tutorial, paste your token
python3 i360dl.py login

# 2) see what's in your cloud
python3 i360dl.py list
python3 i360dl.py list --csv i360_list.csv

# 3) download
python3 i360dl.py dl 323671545639604224        # one asset (mediaId from list)
nohup python3 i360dl.py dl --all > dl_all.log 2>&1 &   # everything, slow, in background
python3 i360dl.py dl --all --no-lrv            # skip low-res .lrv proxies (~20-30% less)
```

### How `login` works

The API has no plain username/password login (web login is protected by a
slider captcha), so the tool reuses your browser session:

1. Log in at <https://www.insta360.com/cn/account/login> in Chrome/Edge
2. F12 → **Application** → **Cookies** → `.insta360.com`
3. Copy the value of the cookie `insta_access_token`, paste it into `login`

The token lasts ~30 days; the tool auto-refreshes it and re-saves it, so you
only have to log in again when the refresh itself fails.

## Environment variables

| Var | Default | Meaning |
|---|---|---|
| `I360_DL_ROOT` | `./downloads` | download destination directory |
| `I360_RATE` | `8` | global speed cap, MB/s (all workers combined) |
| `I360_API` | `https://service-hz.insta360.com` | region-specific cloud API host. If yours differs, read `data.endpoint` from `GET https://service-c.insta360.com/cloud-subscription-service/user/v2/cloudBenefitInfo` (with `X-User-Token` header) |
| `I360_REFRESH` | `https://openapi-c.insta360.com/account/v2/refreshToken` | token refresh endpoint |
| `I360_CHECK` | `https://openapi-c.insta360.com/account/v1/checkToken` | token validation endpoint |

## File formats

| Ext | Content |
|---|---|
| `.insv` | raw 360° video. It is a plain MP4 container with **two HEVC fisheye video streams** (front + back lens) + AAC audio. Plays directly in `mpv` / VLC / ffmpeg (`,` / `.` switch lens) |
| `.insp` | 360° photo, JPEG (equirectangular + Insta360 EXIF) |
| `.mp4` | flat (rectilinear) export from the app |
| `.lrv` | low-resolution proxy for previews; skip with `--no-lrv` |

Note: raw `.insv` is dual-fisheye, **not** a stitched 360° projection — the
stitched look you see in the app is produced at export time.

## Disclaimer

This tool is meant for backing up **your own** data inside **your own** account.
It uses private, undocumented APIs that may change or break at any time.
Use at your own risk; comply with Insta360's terms of service and applicable law.

## License

MIT — see [LICENSE](./LICENSE).
