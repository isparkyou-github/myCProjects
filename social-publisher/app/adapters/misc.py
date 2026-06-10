"""其余平台适配器。

- 微博: 开放平台分享接口（需 access_token）
- TikTok: Content Posting API（需 access_token）
- Instagram: Graph API（需 access_token + ig_user_id，媒体需公网 URL，
  本地文件场景默认转草稿）
- 小红书 / 微信视频号 / 抖音 / B站: 无公开个人发布 API，草稿包模式
"""

import httpx

from .base import BaseAdapter, DraftOnlyAdapter, UPLOAD_DIR


class WeiboAdapter(BaseAdapter):
    platform_id = "weibo"
    platform_name = "微博"

    def is_configured(self) -> bool:
        return bool(self.config.get("access_token"))

    def publish_api(self, content: dict) -> dict:
        token = self.config["access_token"]
        text = (content.get("text") or content.get("title") or "")[:2000]
        images = content.get("images") or []
        if images:
            # share/share.json 仅支持单图，多图取第一张，其余转草稿包附带
            path = UPLOAD_DIR / images[0]
            with open(path, "rb") as f:
                r = httpx.post(
                    "https://api.weibo.com/2/statuses/share.json",
                    data={"access_token": token, "status": text},
                    files={"pic": f}, timeout=60,
                )
        else:
            r = httpx.post(
                "https://api.weibo.com/2/statuses/share.json",
                data={"access_token": token, "status": text}, timeout=30,
            )
        r.raise_for_status()
        return {"ok": True, "mode": "api", "message": "已发布到微博"}


class TikTokAdapter(BaseAdapter):
    platform_id = "tiktok"
    platform_name = "TikTok"

    def is_configured(self) -> bool:
        return bool(self.config.get("access_token"))

    def publish_api(self, content: dict) -> dict:
        video = content.get("video")
        if not video or not video.get("path"):
            raise ValueError("TikTok 适配器当前仅支持视频")
        path = UPLOAD_DIR / video["path"]
        size = path.stat().st_size
        headers = {"Authorization": f"Bearer {self.config['access_token']}"}

        init = httpx.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": (content.get("text") or content.get("title") or "")[:2200],
                    "privacy_level": self.config.get("privacy", "SELF_ONLY"),
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": size,
                    "total_chunk_count": 1,
                },
            }, timeout=30,
        )
        init.raise_for_status()
        data = init.json()["data"]
        with open(path, "rb") as f:
            up = httpx.put(
                data["upload_url"],
                content=f.read(),
                headers={"Content-Type": "video/mp4",
                         "Content-Range": f"bytes 0-{size - 1}/{size}"},
                timeout=600,
            )
        up.raise_for_status()
        return {"ok": True, "mode": "api",
                "message": "已提交到 TikTok（审核后可见）"}


class InstagramAdapter(BaseAdapter):
    platform_id = "instagram"
    platform_name = "Instagram"

    def is_configured(self) -> bool:
        # Graph API 要求媒体可经公网 URL 访问；需要额外配置 media_base_url
        # （把 uploads/ 暴露到公网的地址），否则走草稿。
        return bool(self.config.get("access_token")
                    and self.config.get("ig_user_id")
                    and self.config.get("media_base_url"))

    def publish_api(self, content: dict) -> dict:
        token = self.config["access_token"]
        uid = self.config["ig_user_id"]
        base = self.config["media_base_url"].rstrip("/")
        caption = (content.get("text") or content.get("title") or "")[:2200]
        api = f"https://graph.facebook.com/v21.0/{uid}"

        video = content.get("video")
        images = content.get("images") or []
        if video and video.get("path"):
            params = {"media_type": "REELS",
                      "video_url": f"{base}/{video['path']}",
                      "caption": caption, "access_token": token}
        elif images:
            params = {"image_url": f"{base}/{images[0]}",
                      "caption": caption, "access_token": token}
        else:
            raise ValueError("Instagram 需要图片或视频")

        r = httpx.post(f"{api}/media", data=params, timeout=60)
        r.raise_for_status()
        creation_id = r.json()["id"]
        r2 = httpx.post(f"{api}/media_publish",
                        data={"creation_id": creation_id, "access_token": token},
                        timeout=60)
        r2.raise_for_status()
        return {"ok": True, "mode": "api", "message": "已发布到 Instagram"}


class XiaohongshuAdapter(DraftOnlyAdapter):
    platform_id = "xiaohongshu"
    platform_name = "小红书"


class WechatChannelsAdapter(DraftOnlyAdapter):
    platform_id = "wechat_channels"
    platform_name = "微信视频号"


class DouyinAdapter(DraftOnlyAdapter):
    platform_id = "douyin"
    platform_name = "抖音"


class BilibiliAdapter(DraftOnlyAdapter):
    platform_id = "bilibili"
    platform_name = "哔哩哔哩"
