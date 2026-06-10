#!/bin/bash
# OnePost 启动器（macOS 双击运行版，带日志窗口）
cd "$(dirname "$0")"

# 已在运行则直接打开浏览器
if curl -s http://127.0.0.1:8000/api/platforms >/dev/null 2>&1; then
  echo "OnePost 已在运行，正在打开浏览器…"
  open "http://127.0.0.1:8000"
  exit 0
fi

# 首次运行：创建虚拟环境并安装依赖（约 1-2 分钟，只需一次）
if [ ! -d .venv ]; then
  echo "首次运行，正在安装依赖（只需一次，请稍候）…"
  python3 -m venv .venv || { echo "❌ 需要先安装 Python3"; read -r; exit 1; }
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt || { echo "❌ 依赖安装失败"; read -r; exit 1; }
  echo "✅ 依赖安装完成"
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️ 未检测到 ffmpeg（视频时长检测与链接视频下载需要）"
  echo "   安装方法: brew install ffmpeg"
fi

echo "正在启动 OnePost… 关闭本窗口即停止服务"
( sleep 2 && open "http://127.0.0.1:8000" ) &
exec ./.venv/bin/uvicorn app.main:app --port 8000
