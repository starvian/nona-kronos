#!/bin/bash
# 修复超时配置

cd /data/ws/kronos/services/kronos_fastapi

echo "当前 .env 超时设置:"
grep TIMEOUT .env

echo ""
echo "修改为长序列配置..."

# 备份
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 更新超时设置
sed -i 's/KRONOS_INFERENCE_TIMEOUT=.*/KRONOS_INFERENCE_TIMEOUT=240/' .env
sed -i 's/KRONOS_REQUEST_TIMEOUT=.*/KRONOS_REQUEST_TIMEOUT=300/' .env

echo ""
echo "新的超时设置:"
grep TIMEOUT .env

echo ""
echo "✓ 配置已更新！请重启服务生效。"
