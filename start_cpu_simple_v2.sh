#!/bin/bash
# Kronos CPU 模式简化启动脚本 - 增强版（显式设置超时）
# 开发模式：不依赖 .env 文件，完全通过环境变量控制

set -e

echo "=========================================="
echo "Kronos FastAPI - CPU 模式启动"
echo "=========================================="

# 获取项目根目录
SERVICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SERVICES_DIR")"
GIT_SOURCE_DIR="$PROJECT_ROOT/gitSource"
ENV_FILE="$PROJECT_ROOT/services/kronos_fastapi/.env"

# 检查并临时重命名 .env 文件，避免配置冲突
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  检测到 .env 文件，临时禁用以避免配置冲突"
    mv "$ENV_FILE" "$ENV_FILE.disabled"
    ENV_DISABLED=true
else
    ENV_DISABLED=false
fi

# 配置 CPU 模式
export KRONOS_DEVICE=cpu
export KRONOS_LOG_LEVEL=INFO
export KRONOS_SECURITY_ENABLED=false
export KRONOS_RATE_LIMIT_ENABLED=false

# 显式设置超时（覆盖默认值）
export KRONOS_INFERENCE_TIMEOUT=240
export KRONOS_REQUEST_TIMEOUT=300
export KRONOS_STARTUP_TIMEOUT=300

# 设置 PYTHONPATH（包含 gitSource 以便导入 model 模块）
export PYTHONPATH="$GIT_SOURCE_DIR:$PROJECT_ROOT"

PORT=${1:-8000}

echo "项目根目录: $PROJECT_ROOT"
echo "工作目录: $PROJECT_ROOT"
echo "PYTHONPATH: $PYTHONPATH"
echo ""
echo "配置:"
echo "  端口: $PORT"
echo "  设备: $KRONOS_DEVICE"
echo "  推理超时: ${KRONOS_INFERENCE_TIMEOUT}秒"
echo "  请求超时: ${KRONOS_REQUEST_TIMEOUT}秒"
echo ""
echo "模型加载需要 1-2 分钟，请耐心等待..."
echo "按 Ctrl+C 停止服务"
echo ""

# 从项目根目录启动
cd "$PROJECT_ROOT"

# 清理函数：恢复 .env 文件
cleanup() {
    if [ "$ENV_DISABLED" = true ]; then
        echo ""
        echo "恢复 .env 文件..."
        if [ -f "$ENV_FILE.disabled" ]; then
            mv "$ENV_FILE.disabled" "$ENV_FILE"
        fi
    fi
}

# 注册退出时的清理函数
trap cleanup EXIT INT TERM

python -m uvicorn services.kronos_fastapi.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --log-level info
