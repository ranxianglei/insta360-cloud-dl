# insta360-cloud-dl

Insta360 云空间(Library)素材的 Linux 批量下载工具。纯 Python 标准库,零依赖。

官方只有 Android / Windows 客户端,本工具直接调用其网页端(Studio 网页)使用的私有 REST API,
把云空间里的原始素材(.insv / .insp / .mp4 / .lrv)整批拉到本地 Linux 机器。

## 功能

- `list` 拉取云空间全量素材清单(游标翻页,不限数量),可导出 CSV
- `dl` 按 mediaId 下载,或 `--all` 全量下载
  - 多路并发,全局限速(默认 8MB/s,防限流)
  - 断点续传(`.part` 文件),中断后重跑同一条命令即可,已完成的自动跳过
  - token 过期时自动调用 refreshToken 续期并回写本地
  - 默认直连,不使用系统代理

## 准备工作

1. 在浏览器(Chrome/Edge)登录 https://www.insta360.com/cn/account/login
2. F12 → Application → Cookies → `insta_access_token`(域名 `.insta360.com`)
3. 复制其值,保存为脚本同目录的 `token.txt`(一行,无引号)

token 有效期约 30 天,脚本会在过期时自动续期;续期失败时重新从浏览器取一次即可。

## 用法

```bash
# 列出云端全部素材
python3 i360dl.py list
python3 i360dl.py list --csv i360_list.csv

# 下载指定素材(参数是清单里的 mediaId)
python3 i360dl.py dl 323671545639604224

# 全量下载(慢速,后台跑)
nohup python3 i360dl.py dl --all > dl_all.log 2>&1 &

# 跳过 .lrv 低清代理文件(省 20~30% 空间)
python3 i360dl.py dl --all --no-lrv
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `I360_DL_ROOT` | `./downloads` | 下载根目录 |
| `I360_RATE` | `8` | 全局限速,MB/s(所有并发合计) |
| `I360_API` | `https://service-hz.insta360.com` | 区域专属云 API 主机。若你的账号区域不同,以 `GET https://service-c.insta360.com/cloud-subscription-service/user/v2/cloudBenefitInfo`(带 `X-User-Token` 头)返回的 `data.endpoint` 为准 |
| `I360_REFRESH` | `https://openapi-c.insta360.com/account/v2/refreshToken` | token 续期端点 |

## 文件格式说明

| 后缀 | 内容 |
|---|---|
| `.insv` | 全景视频原始文件。本质是 MP4 容器,含两路 HEVC 鱼眼视频流(前后镜头各一路)+ AAC 音轨,`mpv`/`ffmpeg` 可直接播放 |
| `.insp` | 全景照片,JPEG(等距柱状全景 + Insta360 EXIF) |
| `.mp4` | App 里"平视模式"导出的普通视频 |
| `.lrv` | 低清代理文件(预览用),`--no-lrv` 可跳过 |

## 免责声明

本工具仅供备份自己账号内的个人数据,使用私有接口,官方接口随时可能变更。
使用者需自行承担使用本工具的后果,请遵守 Insta360 服务条款与当地法律。
