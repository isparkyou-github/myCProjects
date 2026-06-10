from .base import BaseAdapter
from .misc import (
    BilibiliAdapter,
    DouyinAdapter,
    InstagramAdapter,
    TikTokAdapter,
    WechatChannelsAdapter,
    WeiboAdapter,
    XiaohongshuAdapter,
)
from .twitter_x import XAdapter
from .youtube import YouTubeAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "x": XAdapter,
    "weibo": WeiboAdapter,
    "xiaohongshu": XiaohongshuAdapter,
    "wechat_channels": WechatChannelsAdapter,
    "youtube": YouTubeAdapter,
    "bilibili": BilibiliAdapter,
    "douyin": DouyinAdapter,
    "tiktok": TikTokAdapter,
    "instagram": InstagramAdapter,
}


def get_adapter(platform_id: str, config: dict) -> BaseAdapter:
    cls = ADAPTERS[platform_id]
    return cls(config.get(platform_id, {}))
