"""适配器基类：统一 publish 接口，未配置 API 时回退为本地草稿包。

草稿包 = drafts/<平台>/<时间戳>/ 目录，内含 content.json + 媒体文件，
方便手动上传或后续接入自动化工具。
"""

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DRAFT_DIR = ROOT / "drafts"
UPLOAD_DIR = ROOT / "uploads"


class BaseAdapter:
    platform_id = "base"
    platform_name = "Base"

    def __init__(self, config: dict):
        # config 为 config.yaml 中该平台的小节, 可能为空 dict
        self.config = config or {}

    def is_configured(self) -> bool:
        return False

    def publish(self, content: dict) -> dict:
        """content: {title, text, images:[文件名], video:{path,...}, source}
        返回 {ok, mode: api|draft, message, url?}
        """
        if self.is_configured():
            try:
                return self.publish_api(content)
            except Exception as e:
                return {"ok": False, "mode": "api",
                        "message": f"API 发布失败: {e}，已转存草稿: {self.save_draft(content)}"}
        path = self.save_draft(content)
        return {
            "ok": True, "mode": "draft",
            "message": f"未配置 {self.platform_name} API，已保存草稿包: {path}",
        }

    def publish_api(self, content: dict) -> dict:
        raise NotImplementedError

    def fetch_stats(self) -> dict | None:
        """拉取账号数据。返回 {metrics: {followers,likes,comments,favorites},
        posts: [{title, views, likes, comments, favorites}]}，无 API 返回 None。"""
        return None

    def save_draft(self, content: dict) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S")
        d = DRAFT_DIR / self.platform_id / ts
        d.mkdir(parents=True, exist_ok=True)
        media = []
        for name in content.get("images") or []:
            src = UPLOAD_DIR / name
            if src.exists():
                shutil.copy(src, d / src.name)
                media.append(src.name)
        video = content.get("video")
        if video and video.get("path"):
            src = UPLOAD_DIR / video["path"]
            if src.exists():
                shutil.copy(src, d / src.name)
                media.append(src.name)
        (d / "content.json").write_text(json.dumps({
            "platform": self.platform_id,
            "title": content.get("title", ""),
            "text": content.get("text", ""),
            "media": media,
            "source": content.get("source", ""),
            "created": ts,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(d.relative_to(ROOT))


class DraftOnlyAdapter(BaseAdapter):
    """没有公开发布 API 的平台（小红书、视频号、抖音个人号、B站个人号）。"""

    def is_configured(self) -> bool:
        return False
