# insta360-cloud-dl

Insta360 云空间(Library)素材的 **Linux 批量下载器**。纯 Python 标准库,零依赖。

官方只有 Android / Windows 客户端,本工具直接调用其网页播放器使用的私有 REST API,
把云空间里的原始文件(`.insv` / `.insp` / `.mp4` / `.lrv`)整批拉到本地 Linux 机器。

English version: [README.md](./README.md)

## 功能

- `list` — 拉取云空间全量素材清单(游标翻页,不限数量),可导出 CSV
- `dl` — 按 `mediaId` 下载,或 `--all` 全量下载
  - 多路并发 + **全局限速**(默认 8MB/s,防限流)
  - 断点续传(`.part` 文件):中断后重跑同一条命令即可,已完成的自动跳过
  - token 过期时自动调 `refreshToken` 续期并回写本地
  - 默认直连,显式禁用系统代理
- `login` — 首次登录:交互式打印教程,从浏览器拿 token、校验、保存为 `token.txt`

## 快速开始

```bash
# 1) 一次性登录:按屏幕提示操作,粘贴 token
python3 i360dl.py login

# 2) 看看云端有什么
python3 i360dl.py list
python3 i360dl.py list --csv i360_list.csv

# 3) 下载
python3 i360dl.py dl 323671545639604224        # 单个素材(mediaId 来自 list)
nohup python3 i360dl.py dl --all > dl_all.log 2>&1 &   # 全量,慢速,后台
python3 i360dl.py dl --all --no-lrv            # 跳过低清 .lrv 代理(省 20~30%)
```

### login 登录教程说明

官方 API 没有纯账号密码登录(网页登录有滑块验证码),所以工具复用浏览器会话:

1. 用 Chrome/Edge 登录 <https://www.insta360.com/cn/account/login>
2. F12 → **Application(应用)** → **Cookies** → `.insta360.com`
3. 复制 cookie `insta_access_token` 的值,粘贴给 `login` 命令

token 有效期约 30 天,脚本会自动续期并回写,只有续期本身失败时才需要重新登录一次。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `I360_DL_ROOT` | `./downloads` | 下载目标目录 |
| `I360_RATE` | `8` | 全局限速,MB/s(所有并发合计) |
| `I360_API` | `https://service-hz.insta360.com` | 区域专属云 API 主机。如与你账号不符,用 `GET https://service-c.insta360.com/cloud-subscription-service/user/v2/cloudBenefitInfo`(带 `X-User-Token` 头)返回的 `data.endpoint` |
| `I360_REFRESH` | `https://openapi-c.insta360.com/account/v2/refreshToken` | token 续期端点 |
| `I360_CHECK` | `https://openapi-c.insta360.com/account/v1/checkToken` | token 校验端点 |

## 文件格式

| 后缀 | 内容 |
|---|---|
| `.insv` | 全景视频原始文件。本质是 MP4 容器,含**两路 HEVC 鱼眼视频流**(前/后镜头)+ AAC 音轨,`mpv`/VLC/ffmpeg 直接可放(`,`/`.` 切镜头) |
| `.insp` | 全景照片,JPEG(等距柱状 + Insta360 EXIF) |
| `.mp4` | App 里平视模式导出的普通视频 |
| `.lrv` | 低清代理文件(预览用),`--no-lrv` 可跳过 |

注意:原始 `.insv` 是双鱼眼,**不是**拼好的 360° 投影——App 里的全景画面是导出时拼的。

## 免责声明

本工具仅供备份**自己账号**内的个人数据。使用私有、未公开的接口,官方可能随时变更导致失效。
使用者自行承担使用后果,请遵守 Insta360 服务条款与当地法律。

## 许可

MIT — 见 [LICENSE](./LICENSE)。
