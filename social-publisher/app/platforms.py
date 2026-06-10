"""平台规范注册表与内容-平台匹配引擎。

每个平台定义其内容规范（字数限制、支持的媒体类型、媒体规格等），
匹配引擎根据分析出的内容类型推荐合适的平台，并逐项校验是否符合规范。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlatformSpec:
    id: str
    name: str
    icon: str                          # 前端展示用 emoji
    content_types: list[str]           # 支持的内容形态: text / image / video / audio / link
    text_limit: int = 0                # 正文字数上限, 0 表示不支持纯文字
    title_limit: int = 0               # 标题字数上限, 0 表示无标题概念
    max_images: int = 0
    max_video_seconds: int = 0
    max_video_mb: int = 0
    video_formats: list[str] = field(default_factory=lambda: ["mp4"])
    image_formats: list[str] = field(default_factory=lambda: ["jpg", "jpeg", "png", "webp"])
    hashtag_style: str = "#tag"        # 话题标签风格
    api_available: bool = False        # 是否有可编程的公开发布 API
    api_note: str = ""                 # API 接入说明
    notes: str = ""                    # 其他规范说明


PLATFORMS: dict[str, PlatformSpec] = {p.id: p for p in [
    PlatformSpec(
        id="x", name="X (Twitter)", icon="𝕏",
        content_types=["text", "image", "video", "link"],
        text_limit=280, max_images=4,
        max_video_seconds=140, max_video_mb=512,
        api_available=True,
        api_note="X API v2，需要在 developer.x.com 创建应用获取 OAuth 密钥",
        notes="文字 280 字符（中文按 2 字符计），最多 4 张图，视频 ≤ 2分20秒",
    ),
    PlatformSpec(
        id="xiaohongshu", name="小红书", icon="📕",
        content_types=["text", "image", "video"],
        text_limit=1000, title_limit=20, max_images=18,
        max_video_seconds=900, max_video_mb=4096,
        api_available=False,
        api_note="无公开个人发布 API，将保存为草稿包供手动发布（或接入第三方聚合工具）",
        notes="标题 ≤ 20 字，正文 ≤ 1000 字，最多 18 张图，视频 ≤ 15 分钟；图文笔记必须有图",
    ),
    PlatformSpec(
        id="weibo", name="微博", icon="🅦",
        content_types=["text", "image", "video", "link"],
        text_limit=2000, max_images=9,
        max_video_seconds=900, max_video_mb=2048,
        api_available=True,
        api_note="微博开放平台 API（需企业/开发者审核），未配置时保存为草稿",
        notes="普通微博 2000 字内，最多 9 张图，视频 ≤ 15 分钟",
    ),
    PlatformSpec(
        id="wechat_channels", name="微信视频号", icon="📹",
        content_types=["video", "image"],
        text_limit=1000, title_limit=22,
        max_video_seconds=3600, max_video_mb=4096,
        api_available=False,
        api_note="无公开个人发布 API，将保存为草稿包供视频号助手手动上传",
        notes="视频为主，描述 ≤ 1000 字，建议竖屏 9:16 或横屏 16:9",
    ),
    PlatformSpec(
        id="youtube", name="YouTube", icon="▶️",
        content_types=["video"],
        text_limit=5000, title_limit=100,
        max_video_seconds=43200, max_video_mb=262144,
        video_formats=["mp4", "mov", "avi", "webm", "mkv"],
        api_available=True,
        api_note="YouTube Data API v3，需要 Google Cloud 项目 OAuth 凭据",
        notes="标题 ≤ 100 字符，描述 ≤ 5000 字符，标签总长 ≤ 500 字符",
    ),
    PlatformSpec(
        id="bilibili", name="哔哩哔哩", icon="📺",
        content_types=["video", "text", "image"],
        text_limit=2000, title_limit=80, max_images=9,
        max_video_seconds=36000, max_video_mb=8192,
        api_available=False,
        api_note="官方投稿 API 仅对认证机构开放，可配置 cookie 走创作中心接口或保存草稿",
        notes="视频标题 ≤ 80 字，简介 ≤ 2000 字；动态（图文）最多 9 图",
    ),
    PlatformSpec(
        id="douyin", name="抖音", icon="🎵",
        content_types=["video", "image"],
        text_limit=1000, max_images=35,
        max_video_seconds=900, max_video_mb=4096,
        api_available=False,
        api_note="开放平台发布 API 需企业认证，个人内容将保存为草稿包",
        notes="标题/描述 ≤ 1000 字，竖屏 9:16 最佳，视频 ≤ 15 分钟",
    ),
    PlatformSpec(
        id="tiktok", name="TikTok", icon="♪",
        content_types=["video", "image"],
        text_limit=2200, max_images=35,
        max_video_seconds=600, max_video_mb=4096,
        api_available=True,
        api_note="TikTok Content Posting API，需在 developers.tiktok.com 申请",
        notes="文案 ≤ 2200 字符，视频 ≤ 10 分钟，竖屏 9:16 最佳",
    ),
    PlatformSpec(
        id="instagram", name="Instagram", icon="📷",
        content_types=["image", "video"],
        text_limit=2200, max_images=10,
        max_video_seconds=900, max_video_mb=4096,
        api_available=True,
        api_note="Instagram Graph API（需 Facebook 开发者账号 + 专业账号）",
        notes="文案 ≤ 2200 字符，最多 30 个标签，轮播最多 10 张图，Reels ≤ 15 分钟",
    ),
]}


# 各内容形态的平台推荐优先级（出现在前面的优先勾选）
RECOMMENDATION = {
    "text":        ["x", "weibo", "xiaohongshu", "bilibili"],
    "text+image":  ["xiaohongshu", "x", "weibo", "instagram"],
    "image":       ["instagram", "xiaohongshu", "x", "weibo"],
    "video":       ["youtube", "bilibili", "douyin", "tiktok", "wechat_channels", "x", "weibo", "instagram", "xiaohongshu"],
    "audio":       ["x", "weibo"],   # 音频建议转视频后发视频平台
    "link":        ["x", "weibo"],
}


def text_weight_len(text: str) -> int:
    """X 风格计数: CJK 等宽字符按 2 计。其他平台直接用 len()。"""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in text)


def validate_for_platform(spec: PlatformSpec, content: dict) -> dict:
    """校验一份内容是否符合某平台规范，返回 {ok, issues:[...]}。"""
    issues: list[str] = []
    hard: bool = False   # 无法自动修正的超限（视频时长/大小/格式），不参与自动勾选
    text = content.get("text") or ""
    title = content.get("title") or ""
    images = content.get("images") or []
    video = content.get("video")
    audio = content.get("audio")

    has_media = bool(images or video)
    if not has_media and not text:
        issues.append("内容为空")

    if text:
        n = text_weight_len(text) if spec.id == "x" else len(text)
        if spec.text_limit and n > spec.text_limit:
            issues.append(f"正文 {n} 字超过上限 {spec.text_limit}，发布时将自动截断")

    if title and spec.title_limit and len(title) > spec.title_limit:
        issues.append(f"标题 {len(title)} 字超过上限 {spec.title_limit}")

    if images:
        if "image" not in spec.content_types:
            issues.append("该平台不支持图片")
        elif spec.max_images and len(images) > spec.max_images:
            issues.append(f"图片 {len(images)} 张超过上限 {spec.max_images}，多余的将被忽略")

    if video:
        if "video" not in spec.content_types:
            issues.append("该平台不支持视频")
        else:
            dur = video.get("duration") or 0
            if spec.max_video_seconds and dur > spec.max_video_seconds:
                issues.append(f"视频时长 {int(dur)}s 超过上限 {spec.max_video_seconds}s")
                hard = True
            size_mb = (video.get("size") or 0) / 1024 / 1024
            if spec.max_video_mb and size_mb > spec.max_video_mb:
                issues.append(f"视频 {size_mb:.0f}MB 超过上限 {spec.max_video_mb}MB")
                hard = True
            fmt = (video.get("format") or "").lower()
            if fmt and fmt not in spec.video_formats:
                issues.append(f"视频格式 {fmt} 不受支持（支持: {','.join(spec.video_formats)}）")
                hard = True

    if audio and not video and "video" in spec.content_types and "audio" not in spec.content_types:
        issues.append("该平台不直接支持音频，建议先转换为视频")

    # 平台不支持当前内容主形态时直接判不适配
    ctype = content.get("content_type") or "text"
    base = ctype.split("+")[0]
    fatal = any("不支持" in i for i in issues)
    supported = base in spec.content_types or (base == "link" and "link" in spec.content_types) \
        or (ctype == "text+image" and "image" in spec.content_types)

    return {"ok": supported and not fatal, "issues": issues, "hard": hard}


def match_platforms(content: dict) -> list[dict]:
    """根据内容类型返回所有平台的匹配结果，推荐的排前面并标记 recommended。"""
    ctype = content.get("content_type") or "text"
    rec_order = RECOMMENDATION.get(ctype, RECOMMENDATION["text"])
    results = []
    for pid in list(rec_order) + [p for p in PLATFORMS if p not in rec_order]:
        spec = PLATFORMS[pid]
        v = validate_for_platform(spec, content)
        results.append({
            "id": spec.id,
            "name": spec.name,
            "icon": spec.icon,
            "recommended": pid in rec_order and v["ok"] and not v["hard"],
            "ok": v["ok"],
            "issues": v["issues"],
            "api_available": spec.api_available,
            "notes": spec.notes,
        })
    return results
