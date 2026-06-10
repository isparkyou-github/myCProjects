"""平台账号凭据管理：保存到本地 config.yaml，支持保持登录时长或永久。

- 凭据仅存本地（config.yaml 已被 .gitignore 排除），接口返回时打码
- _meta 记录每个平台的保存时间与保持时长，过期后该平台自动视为未配置
"""

import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"

# 各平台凭据表单定义；fields 为空表示无公开 API、无需配置
CREDENTIAL_FORMS: dict[str, dict] = {
    "x": {
        "help": "在 developer.x.com 创建应用（Free 层即可），开通 Read & Write 权限后，"
                "在 Keys and tokens 页面生成以下 4 个值",
        "fields": [
            {"key": "api_key", "label": "API Key", "secret": True},
            {"key": "api_secret", "label": "API Key Secret", "secret": True},
            {"key": "access_token", "label": "Access Token", "secret": True},
            {"key": "access_token_secret", "label": "Access Token Secret", "secret": True},
        ],
    },
    "weibo": {
        "help": "在 open.weibo.com 创建应用并完成 OAuth 授权后获得 access_token",
        "fields": [
            {"key": "access_token", "label": "Access Token", "secret": True},
        ],
    },
    "youtube": {
        "help": "在 Google Cloud 创建 OAuth 客户端并下载 client_secret.json 到项目目录，"
                "运行 python youtube_auth.py 完成浏览器授权后自动生成令牌文件",
        "fields": [
            {"key": "token_file", "label": "令牌文件路径", "secret": False,
             "placeholder": "youtube_token.json"},
            {"key": "privacy", "label": "默认可见性", "secret": False,
             "placeholder": "public / unlisted / private"},
        ],
    },
    "tiktok": {
        "help": "在 developers.tiktok.com 申请 Content Posting API 并完成 OAuth 后获得 access_token",
        "fields": [
            {"key": "access_token", "label": "Access Token", "secret": True},
            {"key": "privacy", "label": "默认可见性", "secret": False,
             "placeholder": "SELF_ONLY / PUBLIC_TO_EVERYONE"},
        ],
    },
    "instagram": {
        "help": "Facebook 开发者平台创建应用，绑定 Instagram 专业账号；"
                "media_base_url 为能从公网访问到本服务 uploads/ 的地址",
        "fields": [
            {"key": "access_token", "label": "Access Token", "secret": True},
            {"key": "ig_user_id", "label": "IG User ID", "secret": False},
            {"key": "media_base_url", "label": "媒体公网地址", "secret": False,
             "placeholder": "https://your-domain.com/uploads"},
        ],
    },
    "xiaohongshu": {"help": "小红书无公开个人发布 API，无需配置；发布时自动保存草稿包，"
                            "到创作中心 creator.xiaohongshu.com 粘贴即可", "fields": []},
    "wechat_channels": {"help": "微信视频号无公开个人发布 API，无需配置；发布时自动保存草稿包，"
                                "用视频号助手 channels.weixin.qq.com 上传", "fields": []},
    "douyin": {"help": "抖音发布 API 仅对企业认证开放，个人无需配置；发布时自动保存草稿包，"
                       "到创作服务平台 creator.douyin.com 上传", "fields": []},
    "bilibili": {"help": "B站投稿 API 仅对认证机构开放，无需配置；发布时自动保存草稿包，"
                         "到创作中心 member.bilibili.com 上传", "fields": []},
}

KEEP_CHOICES = [
    {"days": 1, "label": "保持 1 天"},
    {"days": 7, "label": "保持 7 天"},
    {"days": 30, "label": "保持 30 天"},
    {"days": 0, "label": "永久"},
]


def raw_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {}


def _write_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _expired(meta: dict) -> bool:
    keep = meta.get("keep_days", 0)
    if not keep:
        return False
    return time.time() > meta.get("saved_at", 0) + keep * 86400


def effective_config() -> dict:
    """过滤掉已过期平台的凭据，供发布流程使用。"""
    cfg = raw_config()
    meta = cfg.get("_meta", {})
    return {pid: section for pid, section in cfg.items()
            if pid != "_meta" and not _expired(meta.get(pid, {}))}


def save_platform(pid: str, values: dict, keep_days: int) -> None:
    """保存某平台凭据。values 中空值/打码值不覆盖已有字段。"""
    cfg = raw_config()
    section = cfg.get(pid) or {}
    allowed = {f["key"] for f in CREDENTIAL_FORMS.get(pid, {}).get("fields", [])}
    for k, v in values.items():
        if k in allowed and v and not set(v) <= {"•"}:
            section[k] = v
    cfg[pid] = section
    meta = cfg.setdefault("_meta", {})
    meta[pid] = {"saved_at": int(time.time()), "keep_days": int(keep_days)}
    _write_config(cfg)


def clear_platform(pid: str) -> None:
    cfg = raw_config()
    cfg.pop(pid, None)
    cfg.get("_meta", {}).pop(pid, None)
    _write_config(cfg)


def _mask(value: str) -> str:
    tail = value[-4:] if len(value) > 4 else ""
    return "••••••••" + tail


def settings_view(platform_specs: dict, adapters_configured: dict) -> list[dict]:
    """生成设置面板数据：字段定义 + 打码后的当前值 + 登录保持状态。"""
    cfg = raw_config()
    meta_all = cfg.get("_meta", {})
    now = time.time()
    out = []
    for pid, spec in platform_specs.items():
        form = CREDENTIAL_FORMS.get(pid, {"help": "", "fields": []})
        section = cfg.get(pid) or {}
        meta = meta_all.get(pid, {})
        expired = _expired(meta)
        keep = meta.get("keep_days", 0)
        remaining = None
        if section and keep and not expired:
            remaining = max(0, int((meta["saved_at"] + keep * 86400 - now) / 86400))
        fields = []
        for f in form["fields"]:
            cur = section.get(f["key"], "")
            fields.append({**f, "value": _mask(cur) if (cur and f["secret"]) else cur})
        out.append({
            "id": pid, "name": spec.name, "icon": spec.icon,
            "has_api": bool(form["fields"]),
            "help": form["help"],
            "fields": fields,
            "configured": adapters_configured.get(pid, False) and not expired,
            "expired": bool(section) and expired,
            "keep_days": keep,
            "remaining_days": remaining,
        })
    return out
