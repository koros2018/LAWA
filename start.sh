#!/bin/bash
# LAWA 一键启动脚本
# 用法: bash start.sh [seed|dev|docker]

set -e
cd "$(dirname "$0")"

case "${1:-dev}" in
  seed)
    echo "🌱 生成演示数据..."
    python3 scripts/seed.py
    echo "✅ 数据就绪: alice / bob / carol (密码: demo123)"
    ;;

  dev)
    echo "🚀 LAWA 开发模式启动"
    # 检查 .env
    if [ ! -f .env ]; then
      cp .env.example .env
      echo "⚠️  已创建 .env，请编辑填入 API Key: LLM_NVIDIA_KEY / LLM_OPENCODE_KEY"
    fi
    # 数据库迁移
    echo "📦 数据库迁移..."
    alembic upgrade head 2>/dev/null || echo "   (跳过，表可能已存在)"
    # 启动后端
    echo "🔧 后端: http://localhost:6288"
    python3 -m uvicorn src.main:app --host 0.0.0.0 --port 6288 --reload &
    BACKEND_PID=$!
    # 启动前端
    if [ -d frontend/node_modules ]; then
      echo "🎨 前端: http://localhost:6289"
      cd frontend && npm run dev -- --port 6289 &
      FRONTEND_PID=$!
    fi
    echo ""
    echo "═══════════════════════════════════════"
    echo "  API 文档: http://localhost:6288/docs"
    echo "  前端界面: http://localhost:6289"
    echo "  演示账户: alice / bob / carol"
    echo "  密码: demo123"
    echo "═══════════════════════════════════════"
    echo "按 Ctrl+C 停止所有服务"
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
    wait
    ;;

  docker)
    echo "🐳 Docker 部署"
    docker compose up -d
    echo "✅ 全栈已启动: http://localhost:6289"
    ;;

  demo)
    echo "🎬 快速演示模式（种子数据 + 启动）"
    bash "$0" seed
    bash "$0" dev
    ;;

  *)
    echo "用法: bash start.sh [seed|dev|docker|demo]"
    echo "  seed   - 生成演示数据"
    echo "  dev    - 开发模式（后端+前端）"
    echo "  docker - Docker 部署"
    echo "  demo   - 演示模式（种子+启动）"
    ;;
esac
