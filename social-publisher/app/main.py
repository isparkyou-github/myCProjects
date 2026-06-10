"""一键多平台发布 — FastAPI 入口。

启动: uvicorn app.main:app --reload
访问: http://localhost:8000
"""

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analyzer, auth, extractor, platforms, settings, stats
from .adapters import get_adapter

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "uploads"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="OnePost 多平台发布")
UPLOAD_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    """读取配置，已过期的平台凭据自动剔除（降级为草稿模式）。"""
    return settings.effective_config()


# ---------- 登录保护（设置访问密码后启用） ----------

AUTH_EXEMPT = ("/login", "/api/login", "/style.css", "/favicon.png",
               "/icon.png", "/manifest.json", "/sw.js")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if auth.enabled() and path not in AUTH_EXEMPT:
        token = request.cookies.get("onepost_session", "")
        if not auth.verify_token(token):
            if path.startswith("/api/"):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return RedirectResponse("/login")
    return await call_next(request)


class LoginReq(BaseModel):
    password: str
    keep_days: int = 30    # 0 = 永久


@app.get("/login")
async def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/api/login")
async def login(req: LoginReq):
    if not auth.check_password(req.password):
        return JSONResponse({"ok": False, "message": "密码错误"}, status_code=401)
    resp = JSONResponse({"ok": True})
    max_age = 10 * 365 * 86400 if req.keep_days == 0 else req.keep_days * 86400
    resp.set_cookie("onepost_session", auth.make_token(req.keep_days),
                    max_age=max_age, httponly=True, samesite="lax")
    return resp


class PasswordReq(BaseModel):
    password: str


@app.get("/api/auth/status")
async def auth_status():
    return {"enabled": auth.enabled()}


@app.post("/api/auth/password")
async def set_auth_password(req: PasswordReq):
    if len(req.password) < 4:
        return {"ok": False, "message": "密码至少 4 位"}
    auth.set_password(req.password)
    # 当前设备直接保持登录（永久），其他设备需用密码登录
    resp = JSONResponse({"ok": True, "message": "访问密码已开启，手机访问时需登录"})
    resp.set_cookie("onepost_session", auth.make_token(0),
                    max_age=10 * 365 * 86400, httponly=True, samesite="lax")
    return resp


@app.delete("/api/auth/password")
async def clear_auth_password():
    auth.clear_password()
    return {"ok": True, "message": "已关闭登录保护"}


# ---------- 上传 ----------

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """保存上传文件，返回服务器端文件名与识别出的媒体类型。"""
    ext = Path(file.filename or "file").suffix.lower()
    name = f"{uuid.uuid4().hex[:12]}{ext}"
    dest = UPLOAD_DIR / name
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    kind = analyzer.classify_file(file.filename or name)
    info = {"name": name, "original": file.filename, "kind": kind,
            "size": dest.stat().st_size}
    if kind == "video":
        info["duration"] = _video_duration(dest)
        info["format"] = ext.lstrip(".")
    return info


def _video_duration(path: Path) -> float:
    import json
    import subprocess
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return 0.0


# ---------- 分析与平台匹配 ----------

class AnalyzeReq(BaseModel):
    text: str = ""
    title: str = ""
    files: list[dict] = []


@app.post("/api/analyze")
async def analyze(req: AnalyzeReq):
    """识别内容形态并返回各平台匹配结果（推荐项前端自动勾选）。"""
    result = analyzer.analyze(req.text, req.files)
    content = _build_content(req.title, req.text, req.files,
                             result["content_type"])
    matches = platforms.match_platforms(content)
    return {"analysis": result, "platforms": matches}


class ExtractReq(BaseModel):
    url: str
    download_video: bool = True


@app.post("/api/extract")
async def extract_link(req: ExtractReq):
    """解析链接：文章抓取标题/摘要/首图，视频链接经 yt-dlp 下载供转发。"""
    info = await extractor.extract(req.url, download_video=req.download_video)
    files = []
    if info.get("video"):
        files.append({**info["video"], "kind": "video",
                      "name": info["video"]["path"]})
    ctype = "video" if info["kind"] == "video" else (
        "text+image" if info.get("images") else "text")
    content = _build_content(info.get("title", ""), info.get("text", ""),
                             files, ctype)
    content["source"] = req.url
    return {"extracted": info, "platforms": platforms.match_platforms(content)}


# ---------- 发布 ----------

class PublishReq(BaseModel):
    title: str = ""
    text: str = ""
    files: list[dict] = []
    source: str = ""           # 转载来源链接
    platforms: list[str]       # 用户勾选的平台 id


@app.post("/api/publish")
async def publish(req: PublishReq):
    config = load_config()
    ctype = analyzer.analyze(req.text, req.files)["content_type"]
    content = _build_content(req.title, req.text, req.files, ctype)
    if req.source:
        content["source"] = req.source
        attribution = f"\n\n转自: {req.source}"
        content["text"] = (content["text"] or "") + attribution

    async def run_one(pid: str) -> dict:
        spec = platforms.PLATFORMS.get(pid)
        if not spec:
            return {"platform": pid, "ok": False, "message": "未知平台"}
        v = platforms.validate_for_platform(spec, content)
        adapter = get_adapter(pid, config)
        res = await asyncio.to_thread(adapter.publish, content)
        return {"platform": pid, "name": spec.name, "icon": spec.icon,
                "warnings": v["issues"], **res}

    results = await asyncio.gather(*(run_one(p) for p in req.platforms))
    return {"results": list(results)}


@app.get("/api/platforms")
async def list_platforms():
    config = load_config()
    out = []
    for spec in platforms.PLATFORMS.values():
        adapter = get_adapter(spec.id, config)
        out.append({
            "id": spec.id, "name": spec.name, "icon": spec.icon,
            "configured": adapter.is_configured(),
            "api_available": spec.api_available,
            "api_note": spec.api_note, "notes": spec.notes,
        })
    return out


# ---------- 账号设置 ----------

class SettingsReq(BaseModel):
    values: dict = {}
    keep_days: int = 0     # 0 = 永久；1/7/30 = 保持天数


@app.get("/api/settings")
async def get_settings():
    config = load_config()
    configured = {pid: get_adapter(pid, config).is_configured()
                  for pid in platforms.PLATFORMS}
    return {
        "platforms": settings.settings_view(platforms.PLATFORMS, configured),
        "keep_choices": settings.KEEP_CHOICES,
    }


@app.post("/api/settings/{pid}")
async def save_settings(pid: str, req: SettingsReq):
    if pid not in platforms.PLATFORMS:
        return {"ok": False, "message": "未知平台"}
    settings.save_platform(pid, req.values, req.keep_days)
    configured = get_adapter(pid, load_config()).is_configured()
    return {"ok": True, "configured": configured,
            "message": "已保存" + ("，凭据已生效" if configured else "，凭据不完整，仍为草稿模式")}


@app.delete("/api/settings/{pid}")
async def delete_settings(pid: str):
    settings.clear_platform(pid)
    return {"ok": True, "message": "已退出登录"}


# ---------- 数据看板 ----------

class ManualStatsReq(BaseModel):
    followers: int = 0
    likes: int = 0
    comments: int = 0
    favorites: int = 0


@app.get("/api/stats")
async def get_stats():
    config = load_config()
    refreshable = [pid for pid in platforms.PLATFORMS
                   if get_adapter(pid, config).is_configured()]
    return {"platforms": stats.overview(platforms.PLATFORMS),
            "refreshable": refreshable}


@app.post("/api/stats/manual/{pid}")
async def manual_stats(pid: str, req: ManualStatsReq):
    if pid not in platforms.PLATFORMS:
        return {"ok": False, "message": "未知平台"}
    stats.record(pid, req.model_dump(), source="manual")
    return {"ok": True, "message": "已记录"}


@app.post("/api/stats/refresh")
async def refresh_stats():
    """从已配置凭据的平台 API 拉取最新数据。"""
    config = load_config()

    async def fetch_one(pid: str) -> dict:
        adapter = get_adapter(pid, config)
        if not adapter.is_configured():
            return {"platform": pid, "ok": False, "message": "未配置凭据"}
        try:
            data = await asyncio.to_thread(adapter.fetch_stats)
        except Exception as e:
            return {"platform": pid, "ok": False, "message": f"拉取失败: {e}"}
        if not data:
            return {"platform": pid, "ok": False, "message": "该平台暂不支持数据拉取"}
        stats.record(pid, data["metrics"], data.get("posts"), source="api")
        return {"platform": pid, "ok": True, "message": "已更新"}

    results = await asyncio.gather(*(fetch_one(p) for p in platforms.PLATFORMS))
    return {"results": [r for r in results if r["ok"] or "未配置" not in r["message"]]}


def _build_content(title: str, text: str, files: list[dict], ctype: str) -> dict:
    images = [f["name"] for f in files if f.get("kind") == "image"]
    videos = [f for f in files if f.get("kind") == "video"]
    audios = [f for f in files if f.get("kind") == "audio"]
    return {
        "title": title, "text": text, "content_type": ctype,
        "images": images,
        "video": videos[0] if videos else None,
        "audio": audios[0] if audios else None,
    }


@app.get("/uploads/{name}")
async def serve_upload(name: str):
    path = (UPLOAD_DIR / name).resolve()
    if UPLOAD_DIR.resolve() not in path.parents or not path.exists():
        return {"error": "not found"}
    return FileResponse(path)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
