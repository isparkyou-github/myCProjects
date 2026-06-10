#!/bin/bash
# 停止后台运行的 OnePost 服务
pkill -f "uvicorn app.main:app" && echo "✅ OnePost 已停止" || echo "OnePost 未在运行"
sleep 1
