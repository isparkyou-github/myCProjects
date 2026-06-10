"""内容自动识别：判断输入是纯文字、图文、视频、音频还是链接。"""

import re
from pathlib import Path

URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}


def classify_file(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "other"


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


def analyze(text: str, files: list[dict]) -> dict:
    """综合文字与上传文件，得出内容主形态。

    files: [{"name":..., "kind": image/video/audio, ...}]
    返回 content_type: text / image / text+image / video / audio / link
    """
    text = (text or "").strip()
    urls = extract_urls(text)
    kinds = {f["kind"] for f in files}

    if "video" in kinds:
        ctype = "video"
    elif "audio" in kinds:
        ctype = "audio"
    elif "image" in kinds:
        ctype = "text+image" if _text_without_urls(text, urls) else "image"
    elif urls and not _text_without_urls(text, urls):
        ctype = "link"
    else:
        ctype = "text"

    return {
        "content_type": ctype,
        "urls": urls,
        "has_text": bool(text),
        "is_pure_link": ctype == "link",
    }


def _text_without_urls(text: str, urls: list[str]) -> str:
    for u in urls:
        text = text.replace(u, "")
    return text.strip()
