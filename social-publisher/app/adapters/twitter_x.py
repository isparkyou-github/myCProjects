"""X (Twitter) 适配器：X API v2 + v1.1 媒体上传，依赖 tweepy。"""

from .base import BaseAdapter, UPLOAD_DIR


class XAdapter(BaseAdapter):
    platform_id = "x"
    platform_name = "X (Twitter)"

    REQUIRED = ("api_key", "api_secret", "access_token", "access_token_secret")

    def is_configured(self) -> bool:
        return all(self.config.get(k) for k in self.REQUIRED)

    def publish_api(self, content: dict) -> dict:
        import tweepy

        auth = tweepy.OAuth1UserHandler(
            self.config["api_key"], self.config["api_secret"],
            self.config["access_token"], self.config["access_token_secret"],
        )
        api_v1 = tweepy.API(auth)  # 媒体上传仍走 v1.1
        client = tweepy.Client(
            consumer_key=self.config["api_key"],
            consumer_secret=self.config["api_secret"],
            access_token=self.config["access_token"],
            access_token_secret=self.config["access_token_secret"],
        )

        media_ids = []
        for name in (content.get("images") or [])[:4]:
            path = UPLOAD_DIR / name
            if path.exists():
                media_ids.append(api_v1.media_upload(str(path)).media_id)
        video = content.get("video")
        if video and video.get("path"):
            path = UPLOAD_DIR / video["path"]
            if path.exists():
                m = api_v1.media_upload(str(path), media_category="tweet_video",
                                        chunked=True)
                media_ids = [m.media_id]

        text = self._fit(content.get("text") or content.get("title") or "")
        resp = client.create_tweet(text=text, media_ids=media_ids or None)
        tid = resp.data["id"]
        return {"ok": True, "mode": "api", "message": "已发布到 X",
                "url": f"https://x.com/i/status/{tid}"}

    def fetch_stats(self) -> dict | None:
        import tweepy

        client = tweepy.Client(
            consumer_key=self.config["api_key"],
            consumer_secret=self.config["api_secret"],
            access_token=self.config["access_token"],
            access_token_secret=self.config["access_token_secret"],
        )
        me = client.get_me(user_fields=["public_metrics"]).data
        followers = me.public_metrics["followers_count"]
        tweets = client.get_users_tweets(
            me.id, max_results=20,
            tweet_fields=["public_metrics", "text"],
        ).data or []
        posts, likes, comments, favorites = [], 0, 0, 0
        for t in tweets:
            m = t.public_metrics
            likes += m.get("like_count", 0)
            comments += m.get("reply_count", 0)
            favorites += m.get("bookmark_count", 0)
            posts.append({
                "title": t.text[:40],
                "views": m.get("impression_count", 0),
                "likes": m.get("like_count", 0),
                "comments": m.get("reply_count", 0),
                "favorites": m.get("bookmark_count", 0),
            })
        return {"metrics": {"followers": followers, "likes": likes,
                            "comments": comments, "favorites": favorites},
                "posts": posts}

    @staticmethod
    def _fit(text: str, limit: int = 280) -> str:
        """按 X 加权字数截断（CJK 计 2）。"""
        total, out = 0, []
        for c in text:
            total += 2 if ord(c) > 0x2E7F else 1
            if total > limit - 1:
                return "".join(out) + "…"
            out.append(c)
        return text
