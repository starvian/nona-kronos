#!/bin/bash
# 测试开发脚本的 .env 自动处理功能

echo "=========================================="
echo "测试开发脚本的 .env 处理机制"
echo "=========================================="

ENV_FILE="/data/ws/kronos/services/kronos_fastapi/.env"

echo ""
echo "1. 检查 .env 文件状态"
echo "-------------------------------------------"
if [ -f "$ENV_FILE" ]; then
    echo "✓ .env 文件存在"
    echo "  内容预览："
    grep "KRONOS_DEVICE" "$ENV_FILE" | head -1
else
    echo "✗ .env 文件不存在"
fi

echo ""
echo "2. 模拟脚本启动流程（不实际启动服务）"
echo "-------------------------------------------"

# 模拟脚本的 .env 处理逻辑
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  检测到 .env 文件，临时禁用以避免配置冲突"
    echo "  执行：mv $ENV_FILE ${ENV_FILE}.disabled"
    mv "$ENV_FILE" "${ENV_FILE}.disabled"
    ENV_DISABLED=true
else
    ENV_DISABLED=false
fi

echo ""
echo "3. 检查禁用后的状态"
echo "-------------------------------------------"
if [ -f "${ENV_FILE}.disabled" ]; then
    echo "✓ .env 已重命名为 .env.disabled"
else
    echo "✗ .env.disabled 不存在"
fi

if [ -f "$ENV_FILE" ]; then
    echo "✗ .env 仍然存在（不应该）"
else
    echo "✓ .env 已不存在（正确）"
fi

echo ""
echo "4. 模拟退出时的清理"
echo "-------------------------------------------"
cleanup() {
    if [ "$ENV_DISABLED" = true ]; then
        echo "恢复 .env 文件..."
        if [ -f "${ENV_FILE}.disabled" ]; then
            mv "${ENV_FILE}.disabled" "$ENV_FILE"
            echo "✓ .env 文件已恢复"
        fi
    fi
}

cleanup

echo ""
echo "5. 验证最终状态"
echo "-------------------------------------------"
if [ -f "$ENV_FILE" ]; then
    echo "✓ .env 文件已恢复"
else
    echo "✗ .env 文件未恢复"
fi

if [ -f "${ENV_FILE}.disabled" ]; then
    echo "✗ .env.disabled 仍存在（不应该）"
else
    echo "✓ .env.disabled 已清理"
fi

echo ""
echo "=========================================="
echo "✓ 测试完成"
echo "=========================================="
