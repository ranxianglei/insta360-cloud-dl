#!/usr/bin/env python3
"""Insta360 云视频 Linux 批量下载器(纯标准库)。

用法:
  python3 i360dl.py login                # 首次登录: 带教程, 粘贴浏览器 token
  python3 i360dl.py list                 # 列出云端全部素材(只读)
  python3 i360dl.py list --csv out.csv   # 导出清单
  python3 i360dl.py dl <mediaId> ...     # 下载指定素材(原始文件, 含 .lrv)
  python3 i360dl.py dl --all             # 下载全部(自动跳过已完成)
  python3 i360dl.py dl <id> --no-lrv     # 跳过 LRV 代理文件(省空间)

token 读取 ./token.txt (网页 cookie insta_access_token), 失效时自动尝试续期。
"""
import csv
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# 用户要求直连、不走系统代理
urllib.request.install_opener(
    urllib.request.build_opener(urllib.request.ProxyHandler({})))
from datetime import datetime

API_BASE = os.environ.get("I360_API", "https://service-hz.insta360.com")
REFRESH_URL = os.environ.get(
    "I360_REFRESH", "https://openapi-c.insta360.com/account/v2/refreshToken")
CHECK_URL = os.environ.get(
    "I360_CHECK", "https://openapi-c.insta360.com/account/v1/checkToken")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
DL_ROOT = os.environ.get("I360_DL_ROOT", "./downloads")
CHUNK = 1 * 1024 * 1024          # 1MB 分块, 便于限速
RATE_MBPS = float(os.environ.get("I360_RATE", "8"))   # 全局限速 MB/s(所有并发合计)
_print_lock = threading.Lock()
_pace_lock = threading.Lock()
_pace_time = time.monotonic()
_pace_bytes = 0.0


def log(msg):
    with _print_lock:
        print(time.strftime("%H:%M:%S ") + msg, flush=True)


def load_token():
    with open(TOKEN_FILE) as f:
        t = f.read().strip()
    if not t:
        sys.exit("token.txt 为空")
    return t


def save_token(t):
    with open(TOKEN_FILE, "w") as f:
        f.write(t + "\n")
    os.chmod(TOKEN_FILE, 0o600)


def headers(token):
    return {
        "authentication": token,
        "x-user-token": token,
        "x-country": "CN",
        "x-insta360-platform": "pc/mac",
        "x-equipment-code": "02:00:00:00:00:01",
        "x-insta360-trace-id": "pc" + uuid.uuid4().hex,
        "app_traffic": "release",
        "app_version": "6.0.2",
        "user-agent": "insta360/studio",
        "referer": "https://cloud.insta360.com/",
        "accept-language": "zh-CN,zh;q=0.9",
        "cookie": f"insta_access_token={token}",
    }


class Api:
    def __init__(self, token=None):
        self.token = token or load_token()

    def _get(self, url, params=None, token=None):
        tok = token or self.token
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers(tok))
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                body = e.read()
                if e.code == 401 and attempt == 0:
                    if self._refresh():
                        continue
                try:
                    return json.loads(body)
                except Exception:
                    return {"code": -999, "msg": f"HTTP {e.code}: {body[:200]!r}"}
            except Exception as e:
                if attempt == 2:
                    return {"code": -999, "msg": str(e)}
                time.sleep(2 * (attempt + 1))
        return {"code": -999, "msg": "unexpected"}

    def _refresh(self):
        try:
            r = self._get(REFRESH_URL, token=self.token)
        except Exception:
            return False
        data = r.get("data") or r
        new = None
        if isinstance(data, dict):
            new = data.get("access_token") or data.get("token")
        if new and r.get("code") in (0, None):
            # 验证新 token
            chk = self._get(API_BASE + "/cloud/service/media/view/searchList",
                            {"lastUpdatePosition": "0"}, token=new)
            if chk.get("code") == 0:
                self.token = new
                save_token(new)
                log("token 已自动续期")
                return True
        return False

    def list_all(self):
        """游标翻页拉全量清单, 返回 [{...item}]"""
        items, seen = [], set()
        cursor = "0"
        while True:
            r = self._get(API_BASE + "/cloud/service/media/view/searchList",
                          {"lastUpdatePosition": cursor})
            if r.get("code") != 0:
                sys.exit(f"拉清单失败: {r}")
            data = r.get("data") or {}
            lst = data.get("list") or []
            items.extend(lst)
            log(f"  清单 +{len(lst)} 条, 累计 {len(items)}")
            nxt = data.get("lastUpdatePosition")
            if not lst or not nxt or str(nxt) in seen or str(nxt) == cursor:
                break
            seen.add(str(cursor))
            cursor = str(nxt)
        return items

    def download_urls(self, media_id):
        r = self._get(API_BASE + "/cloud/service/media/download",
                      {"mediaId": media_id})
        if r.get("code") != 0:
            return None, r.get("msg")
        paths = (r.get("data") or {}).get("paths") or []
        return [p for p in paths if p.get("url")], None


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f}{u}" if u != "B" else f"{n}B"
        n /= 1024


def fmt_ts(ms):
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")


def _mask_phone(p):
    p = str(p or "")
    return p[:3] + "****" + p[-4:] if len(p) >= 7 else "***"


def cmd_login(args):
    print("""
== Get your token from the browser (一次性, 之后自动续期) ==
  1. Open https://www.insta360.com/cn/account/login in Chrome/Edge and log in
  2. Press F12 → Application → Cookies → .insta360.com
  3. Copy the VALUE of the cookie named  insta_access_token

== 从浏览器获取 token(一次性, 之后脚本自动续期) ==
  1. 用 Chrome/Edge 打开 https://www.insta360.com/cn/account/login 并登录
  2. 按 F12 → Application(应用) → Cookies → .insta360.com
  3. 复制名为  insta_access_token  的 cookie 的值
""")
    try:
        tok = input("Paste token (粘贴后回车): ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit(1)
    if not tok:
        sys.exit("empty token")
    r = Api(token=tok)._get(CHECK_URL)
    acct = (((r.get("data") or {}).get("account")) or {})
    if r.get("code") != 0 or not acct:
        sys.exit(f"token 校验失败: {r}")
    save_token(tok)
    phone = acct.get("phone") or acct.get("phoneNumber") or ""
    log(f"登录成功: account id={acct.get('id')} phone={_mask_phone(phone)} "
        f"country={acct.get('country')} | token 已保存到 {TOKEN_FILE}")


def cmd_list(args):
    api = Api()
    log("拉取云端清单...")
    items = api.list_all()
    rows = []
    total = 0
    for it in items:
        size = int(it.get("size") or it.get("uploadSize") or 0)
        total += size
        rows.append({
            "mediaId": it.get("mediaId"),
            "name": it.get("mediaName"),
            "type": it.get("mediaType"),
            "size": size,
            "size_h": human(size),
            "files": it.get("fileItems") or [],
            "shoot": fmt_ts(it.get("shootTime")),
            "camera": it.get("cameraType"),
        })
    rows.sort(key=lambda x: x["shoot"])
    print(f"\n共 {len(rows)} 个素材, 总大小 {human(total)}\n")
    hdr = f"{'mediaId':<21} {'拍摄时间':<17} {'类型':<12} {'大小':>8}  文件名"
    print(hdr)
    print("-" * 100)
    for r in rows:
        print(f"{r['mediaId']:<21} {r['shoot']:<17} {r['type']:<12} {r['size_h']:>8}  {r['name']}")
    if "--csv" in args:
        i = args.index("--csv") + 1
        out = args[i] if i < len(args) else "i360_list.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["mediaId", "name", "type", "size",
                                              "size_h", "files", "shoot", "camera"])
            w.writeheader()
            for r in rows:
                rr = dict(r)
                rr["files"] = "|".join(r["files"])
                w.writerow(rr)
        log(f"清单已导出: {out}")


def _pace(nbytes):
    """全局令牌桶限速: 所有并发线程合计不超过 RATE_MBPS MB/s。"""
    global _pace_time, _pace_bytes
    limit = RATE_MBPS * 1024 * 1024
    while True:
        with _pace_lock:
            now = time.monotonic()
            # 按经过时间补充令牌
            _pace_bytes = min(nbytes, _pace_bytes + (now - _pace_time) * limit)
            _pace_time = now
            if _pace_bytes >= nbytes:
                _pace_bytes -= nbytes
                return
            need = (nbytes - _pace_bytes) / limit
        time.sleep(need)


def download_one_file(url, part, expected):
    resume = os.path.getsize(part) if os.path.exists(part) else 0
    if expected and resume >= expected:
        os.replace(part, part[:-5])
        return True
    req = urllib.request.Request(url)
    if resume:
        req.add_header("Range", f"bytes={resume}-")
    with urllib.request.urlopen(req, timeout=60) as r:
        if resume and r.status == 206:
            mode = "ab"
        else:
            resume, mode = 0, "wb"
        clen = int(r.headers.get("content-length") or 0)
        todo = clen if clen else max(expected - resume, 0) if expected else 0
        got, last = resume, time.monotonic()
        with open(part, mode) as f:
            while True:
                b = r.read(CHUNK)
                if not b:
                    break
                f.write(b)
                _pace(len(b))
                got += len(b)
                now = time.monotonic()
                if now - last > 5:
                    last = now
                    pct = f"{got / expected * 100:.0f}%" if expected else ""
                    log(f"    {os.path.basename(part)} {human(got)}/{human(expected) if expected else '?'} {pct}")
    os.replace(part, part[:-5])
    return True


def cmd_dl(args):
    api = Api()
    all_mode = "--all" in args
    no_lrv = "--no-lrv" in args
    ids = [a for a in args if a not in ("--all", "--no-lrv")
           and not a.startswith("--")]
    if not all_mode and not ids:
        sys.exit("用法: i360dl.py dl <mediaId>... | i360dl.py dl --all [--no-lrv]")
    log("拉取云端清单...")
    items = api.list_all()
    by_id = {str(it.get("mediaId")): it for it in items}
    targets = items if all_mode else [by_id[i] for i in ids if i in by_id]
    missing = [i for i in ids if i not in by_id]
    if missing:
        log(f"警告: 未找到 mediaId: {missing}")
    os.makedirs(DL_ROOT, exist_ok=True)

    tasks = []  # (dest_dir, name, url, size)
    for it in targets:
        mid = str(it.get("mediaId"))
        name = it.get("mediaName") or mid
        d = os.path.join(DL_ROOT, name)
        urls, err = api.download_urls(mid)
        if not urls:
            log(f"[{name}] 获取下载地址失败: {err}")
            continue
        log(f"[{name}] {len(urls)} 个文件, 合计 {human(sum(int(u.get('size') or 0) for u in urls))}")
        for u in urls:
            fn = os.path.basename(urllib.parse.urlparse(u["url"]).path) or u.get("name")
            if no_lrv and fn.lower().endswith(".lrv"):
                continue
            tasks.append((d, fn, u["url"], int(u.get("size") or 0)))

    total_bytes = sum(t[3] for t in tasks)
    log(f"待下载 {len(tasks)} 个文件, 共 {human(total_bytes)} -> {DL_ROOT}")
    done = fail = 0

    def work(t):
        nonlocal done, fail
        d, fn, url, size = t
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, fn)
        part = dest + ".part"
        if os.path.exists(dest) and os.path.getsize(dest) == size and size:
            log(f"  跳过已完成: {fn}")
            done += 1
            return
        log(f"  开始: {fn} ({human(size)})")
        try:
            download_one_file(url, part, size)
            done += 1
            log(f"  完成: {fn}")
        except Exception as e:
            fail += 1
            log(f"  失败: {fn}: {e} (已下载 {human(os.path.getsize(part) if os.path.exists(part) else 0)}, 重跑可续传)")

    with ThreadPoolExecutor(max_workers=2) as ex:  # 2 路并发, 慢速防限流
        futs = [ex.submit(work, t) for t in tasks]
        for _ in as_completed(futs):
            pass
    log(f"全部结束: 成功/跳过 {done}, 失败 {fail}, 总 {len(tasks)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "list":
        cmd_list(a[1:])
    elif a[0] == "login":
        cmd_login(a[1:])
    elif a[0] == "dl":
        cmd_dl(a[1:])
    else:
        sys.exit(__doc__)
