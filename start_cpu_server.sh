#!/bin/bash
# Kronos CPU 模式一键启动脚本

set -e

echo "=========================================="
echo "Kronos FastAPI 服务 - CPU 模式启动"
echo "=========================================="

# 检查工作目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GIT_SOURCE_DIR="$PROJECT_ROOT/gitSource"
SERVICES_DIR="$SCRIPT_DIR"

echo "项目根目录: $PROJECT_ROOT"
echo "gitSource 目录: $GIT_SOURCE_DIR"
echo "services 目录: $SERVICES_DIR"

# 检查目录存在
if [ ! -d "$GIT_SOURCE_DIR" ]; then
    echo "错误: gitSource 目录不存在: $GIT_SOURCE_DIR"
    exit 1
fi

if [ ! -d "$SERVICES_DIR/kronos_fastapi" ]; then
    echo "错误: kronos_fastapi 目录不存在: $SERVICES_DIR/kronos_fastapi"
    exit 1
fi

# 检查配置文件
ENV_FILE="$SCRIPT_DIR/kronos_fastapi/.env"
ENV_CPU_FILE="$SCRIPT_DIR/kronos_fastapi/.env.cpu"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_CPU_FILE" ]; then
        echo "复制 CPU 配置文件..."
        cp "$ENV_CPU_FILE" "$ENV_FILE"
        echo "✓ 已创建 .env 文件"
    else
        echo "警告: 未找到 .env 或 .env.cpu 文件"
        echo "将使用默认配置（环境变量）"
    fi
fi

# 设置环境变量（强制 CPU 模式）
export KRONOS_DEVICE=cpu
export KRONOS_LOG_LEVEL=INFO
export KRONOS_SECURITY_ENABLED=false
export KRONOS_RATE_LIMIT_ENABLED=false
export KRONOS_INFERENCE_TIMEOUT=120
export KRONOS_REQUEST_TIMEOUT=180

echo ""
echo "环境配置:"
echo "  KRONOS_DEVICE: $KRONOS_DEVICE"
echo "  KRONOS_LOG_LEVEL: $KRONOS_LOG_LEVEL"
echo "  KRONOS_SECURITY_ENABLED: $KRONOS_SECURITY_ENABLED"

# 检查 Python 和依赖
echo ""
echo "检查依赖..."

if ! command -v python &> /dev/null; then
    echo "错误: Python 未安装"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1)
echo "✓ $PYTHON_VERSION"

# 检查关键包
python -c "import torch" 2>/dev/null || { echo "错误: PyTorch 未安装。请运行: pip install -r $GIT_SOURCE_DIR/requirements.txt"; exit 1; }
python -c "import fastapi" 2>/dev/null || { echo "错误: FastAPI 未安装。请运行: pip install -r $SCRIPT_DIR/kronos_fastapi/requirements.txt"; exit 1; }

echo "✓ 依赖检查通过"

# 检查端口
PORT=${1:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo ""
    echo "警告: 端口 $PORT 已被占用"
    echo "请停止占用进程或使用其他端口: $0 <port>"
    echo ""
    echo "占用进程:"
    lsof -Pi :$PORT -sTCP:LISTEN
    exit 1
fi

# 启动服务
echo ""
echo "=========================================="
echo "启动服务 (端口: $PORT)"
echo "=========================================="
echo ""
echo "服务将在 CPU 模式下运行"
echo "模型加载可能需要 1-2 分钟，请耐心等待..."
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 设置 PYTHONPATH 包含 gitSource 和 services
export PYTHONPATH="$GIT_SOURCE_DIR:$PROJECT_ROOT:$PYTHONPATH"

# 从 PROJECT_ROOT 启动以便能找到 services 和 model
cd "$PROJECT_ROOT"

echo "工作目录: $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"
echo ""

# 启动 uvicorn
python -m uvicorn services.kronos_fastapi.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --log-level info \
    --timeout-keep-alive 300

echo ""
echo "服务已停止"
