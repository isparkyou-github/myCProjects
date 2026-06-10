"""YouTube 适配器：YouTube Data API v3 上传视频。

需要 Google Cloud OAuth 客户端凭据，首次使用前运行
`python -m app.adapters.youtube_auth` 完成授权生成 token 文件。
"""

from pathlib import Path

from .base import ROOT, UPLOAD_DIR, BaseAdapter


class YouTubeAdapter(BaseAdapter):
    platform_id = "youtube"
    platform_name = "YouTube"

    def token_path(self) -> Path:
        return ROOT / self.config.get("token_file", "youtube_token.json")

    def is_configured(self) -> bool:
        return self.token_path().exists()

    def publish_api(self, content: dict) -> dict:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        video = content.get("video")
        if not video or not video.get("path"):
            raise ValueError("YouTube 仅支持视频内容")
        path = UPLOAD_DIR / video["path"]

        creds = Credentials.from_authorized_user_file(
            str(self.token_path()),
            ["https://www.googleapis.com/auth/youtube.upload"],
        )
        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": (content.get("title") or content.get("text") or "Untitled")[:100],
                "description": (content.get("text") or "")[:5000],
            },
            "status": {"privacyStatus": self.config.get("privacy", "public")},
        }
        media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp["id"]
        return {"ok": True, "mode": "api", "message": "已上传到 YouTube",
                "url": f"https://youtu.be/{vid}"}

    def fetch_stats(self) -> dict | None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(
            str(self.token_path()),
            ["https://www.googleapis.com/auth/youtube.readonly"],
        )
        yt = build("youtube", "v3", credentials=creds)
        ch = yt.channels().list(
            part="statistics,contentDetails", mine=True).execute()
        if not ch.get("items"):
            return None
        info = ch["items"][0]
        st = info["statistics"]
        uploads = info["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=20
        ).execute().get("items", [])
        ids = [i["contentDetails"]["videoId"] for i in items]
        posts, likes, comments = [], 0, 0
        if ids:
            videos = yt.videos().list(
                part="statistics,snippet", id=",".join(ids)).execute()
            for v in videos.get("items", []):
                vs = v["statistics"]
                likes += int(vs.get("likeCount", 0))
                comments += int(vs.get("commentCount", 0))
                posts.append({
                    "title": v["snippet"]["title"][:40],
                    "views": int(vs.get("viewCount", 0)),
                    "likes": int(vs.get("likeCount", 0)),
                    "comments": int(vs.get("commentCount", 0)),
                    "favorites": int(vs.get("favoriteCount", 0)),
                })
        return {"metrics": {"followers": int(st.get("subscriberCount", 0)),
                            "likes": likes, "comments": comments,
                            "favorites": 0},
                "posts": posts}
