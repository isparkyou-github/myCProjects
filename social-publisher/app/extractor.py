"""链接内容识别与抓取。

- 普通网页: 抓取 OpenGraph / 标题 / 正文摘要 / 首图，用于转载图文
- 视频链接 (YouTube/B站/抖音/X 等): 通过 yt-dlp 获取元数据并可下载视频用于转发
"""

import re
import uuid
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

# 命中这些域名的链接优先按视频处理
VIDEO_HOSTS = re.compile(
    r"(youtube\.com|youtu\.be|bilibili\.com|b23\.tv|douyin\.com|tiktok\.com|"
    r"twitter\.com|x\.com|instagram\.com|weibo\.com|xiaohongshu\.com|xhslink\.com)",
    re.IGNORECASE,
)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def _ytdlp():
    try:
        import yt_dlp  # noqa: PLC0415
        return yt_dlp
    except ImportError:
        return None


async def extract(url: str, download_video: bool = False) -> dict:
    """识别链接内容。返回统一结构:
    {kind: video|article, title, text, images:[url], video:{...}|None, source}
    """
    if VIDEO_HOSTS.search(url):
        info = extract_video(url, download=download_video)
        if info:
            return info
    return await extract_article(url)


def extract_video(url: str, download: bool = False) -> dict | None:
    yt_dlp = _ytdlp()
    if yt_dlp is None:
        return {
            "kind": "video", "title": "", "text": "",
            "images": [], "video": None, "source": url,
            "error": "未安装 yt-dlp，无法解析视频链接。请运行: pip install yt-dlp",
        }
    out_id = uuid.uuid4().hex[:12]
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": not download,
        "outtmpl": str(UPLOAD_DIR / f"{out_id}.%(ext)s"),
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=download)
    except Exception as e:  # 链接失效/地区限制/需要登录等
        return {"kind": "video", "title": "", "text": "", "images": [],
                "video": None, "source": url, "error": f"视频解析失败: {e}"}

    video = None
    if download:
        files = list(UPLOAD_DIR.glob(f"{out_id}.*"))
        if files:
            f = files[0]
            video = {
                "path": f.name,
                "format": f.suffix.lstrip("."),
                "size": f.stat().st_size,
                "duration": info.get("duration") or 0,
            }
    return {
        "kind": "video",
        "title": info.get("title") or "",
        "text": (info.get("description") or "")[:2000],
        "images": [info.get("thumbnail")] if info.get("thumbnail") else [],
        "video": video,
        "duration": info.get("duration") or 0,
        "uploader": info.get("uploader") or "",
        "source": url,
    }


async def extract_article(url: str) -> dict:
    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, follow_redirects=True, timeout=20
    ) as client:
        resp = await client.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    def og(prop: str) -> str:
        tag = soup.find("meta", property=f"og:{prop}") or \
              soup.find("meta", attrs={"name": prop})
        return tag.get("content", "").strip() if tag else ""

    title = og("title") or (soup.title.get_text(strip=True) if soup.title else "")
    desc = og("description")
    image = og("image")

    # 正文摘要: 取最长的若干段落
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    paras = sorted(
        (p.get_text(" ", strip=True) for p in soup.find_all("p")),
        key=len, reverse=True,
    )
    body = "\n\n".join(x for x in paras[:5] if len(x) > 40)

    return {
        "kind": "article",
        "title": title,
        "text": desc or body[:1500],
        "body": body[:3000],
        "images": [image] if image else [],
        "video": None,
        "source": url,
    }
