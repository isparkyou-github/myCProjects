"""YouTube OAuth 授权辅助脚本。

1. 在 Google Cloud Console 创建项目，启用 YouTube Data API v3
2. 创建 OAuth 客户端（桌面应用），下载为 client_secret.json 放到本目录
3. 运行: python youtube_auth.py
4. 浏览器完成授权后生成 youtube_token.json，即可在平台中直发 YouTube
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)
with open("youtube_token.json", "w") as f:
    f.write(creds.to_json())
print("✅ 已生成 youtube_token.json")
