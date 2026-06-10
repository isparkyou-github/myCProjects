# OnePost · 一键多平台内容发布

一次创作，按各社交平台规范自动适配并发布到：
**X (Twitter) · 小红书 · 微博 · 微信视频号 · YouTube · 哔哩哔哩 · 抖音 · TikTok · Instagram**

![架构](#) <!-- 内容分析 → 平台规则匹配 → 适配器发布 -->

## 功能

- **内容自动识别**：输入文字 / 上传图片、视频、音乐，自动判断内容形态
  （纯文字 / 图文 / 视频 / 音频 / 链接），并推荐适合的平台
  - 文字 + 图片 → 自动勾选 小红书、X、微博、Instagram
  - 视频 → 自动勾选 YouTube、B站、抖音、TikTok、视频号 等
- **平台规范校验**：按各平台的字数上限、图片数量、视频时长/大小逐项校验，
  超限会提示并自动截断
- **链接转载**：粘贴网页链接自动抓取标题、摘要、首图；粘贴视频链接
  （YouTube / B站 / 抖音 / X 等）自动通过 yt-dlp 下载视频，确认后转发到其他平台，
  并自动附上「转自: 原链接」
- **发布前平台勾选**：所有平台以可选框列出，推荐项自动勾选，可手动调整
- **草稿包回退**：没有开放 API 的平台（小红书、视频号、抖音、B站个人号）
  或未配置密钥的平台，内容 + 媒体自动保存到 `drafts/<平台>/`，方便手动发布

## 快速开始（macOS 双击启动，无需终端）

在 Finder 中打开 `social-publisher` 目录：

- **双击 `OnePost.app`** —— 后台静默启动并自动打开浏览器（首次会自动安装依赖，
  约 1-2 分钟，注意右上角通知）。停止服务双击 `停止OnePost.command`
- 或 **双击 `启动OnePost.command`** —— 弹出终端窗口显示运行日志，关窗即停，
  排查问题时用这个

> 首次双击如果提示「无法验证开发者」，右键文件 → 打开 → 再点打开，之后就不会再问。
> 想放到 Dock：把 OnePost.app 拖到 Dock 即可。

## 手机使用（PWA）

1. 电脑上启动 OnePost（手机与电脑连同一 Wi-Fi）
2. 在「⚙️ 账号设置 → 📱 手机访问」中**开启访问密码**
3. 手机浏览器打开 `http://电脑IP:8000`（启动OnePost.command 窗口里会显示该地址），
   输入密码登录（可选保持登录 1/7/30 天或永久）
4. Safari 分享菜单 →「添加到主屏幕」，即可像 App 一样从主屏幕图标全屏打开

想在任何网络下用手机访问：用 Docker 部署到云服务器（见下方部署），同样受密码保护，
但更推荐再加一层 HTTPS 反向代理或 VPN（如 Tailscale）。

首次启动时 macOS 若弹出「是否允许接受传入网络连接」，选「允许」手机才能连上。

## 快速开始（命令行）

```bash
cd social-publisher
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 可选：配置平台 API 密钥（不配置则全部走草稿包模式）
cp config.example.yaml config.yaml

uvicorn app.main:app --reload
# 打开 http://localhost:8000
```

建议同时安装 `ffmpeg`（视频时长检测与 yt-dlp 合流需要）：
`apt install ffmpeg` 或 `brew install ffmpeg`。

## 平台接入状态

| 平台 | 直发方式 | 说明 |
|---|---|---|
| X (Twitter) | ✅ API v2 | config.yaml 填入 4 个 OAuth 密钥 |
| YouTube | ✅ Data API v3 | 运行 `python youtube_auth.py` 完成授权 |
| 微博 | ✅ 开放平台 | 填入 access_token（share 接口支持文字+单图） |
| TikTok | ✅ Content Posting API | 填入 access_token |
| Instagram | ✅ Graph API | 需专业账号 + 媒体公网 URL（media_base_url） |
| 小红书 | 📦 草稿包 | 无公开个人发布 API |
| 微信视频号 | 📦 草稿包 | 无公开个人发布 API |
| 抖音 | 📦 草稿包 | 发布 API 仅企业认证可用 |
| 哔哩哔哩 | 📦 草稿包 | 投稿 API 仅认证机构可用 |

草稿包内含 `content.json`（标题/正文/来源）和全部媒体文件，
打开对应平台的创作中心直接复制粘贴即可。

## 项目结构

```
social-publisher/
├── app/
│   ├── main.py          # FastAPI 入口与 API 路由
│   ├── analyzer.py      # 内容形态自动识别
│   ├── platforms.py     # 各平台规范注册表 + 匹配/校验引擎
│   ├── extractor.py     # 链接抓取 / yt-dlp 视频下载
│   ├── adapters/        # 各平台发布适配器
│   └── static/          # 前端单页（HTML/CSS/JS）
├── config.example.yaml  # 平台密钥配置模板
├── uploads/             # 上传与下载的媒体
└── drafts/              # 草稿包输出
```

## API

| 接口 | 说明 |
|---|---|
| `POST /api/upload` | 上传媒体文件，返回识别出的类型 |
| `POST /api/analyze` | 分析内容形态并返回平台匹配结果 |
| `POST /api/extract` | 解析链接（文章抓取 / 视频下载） |
| `POST /api/publish` | 向勾选的平台并行发布 |
| `GET /api/platforms` | 各平台规范与配置状态 |

## 部署

**本地运行（推荐日常使用）**：见上方快速开始，凭据保存在本机最安全。

**Docker 部署**（云服务器 / Railway / Fly.io 等支持持久磁盘的平台）：

```bash
cd social-publisher
cp config.example.yaml config.yaml && touch stats_history.json
docker compose up -d        # 打开 http://服务器IP:8000
```

部署到公网时务必加访问控制（反向代理 + Basic Auth，或仅绑定内网/VPN），
config.yaml 中保存着你的平台凭据。

> ⚠️ 不建议 Vercel/Netlify 等无服务器平台：无持久磁盘（凭据/草稿/数据丢失）、
> 请求体上限小（视频传不上去）、函数超时（视频下载/上传会被掐断）、无法安装 ffmpeg。

## 注意事项

- 转载他人内容请确保已获得授权，遵守各平台的转载与版权规则
- 各平台 API 的权限申请与审核要求以官方文档为准
- `config.yaml`、`uploads/`、`drafts/` 已加入 .gitignore，不会提交密钥与媒体
