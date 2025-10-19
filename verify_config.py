#!/usr/bin/env python3
"""验证配置是否正确加载"""

import sys
import os

# 添加路径
sys.path.insert(0, '/data/ws/kronos')

# 设置环境变量（模拟启动脚本）
os.environ['KRONOS_DEVICE'] = 'cpu'
os.environ['KRONOS_INFERENCE_TIMEOUT'] = '240'
os.environ['KRONOS_REQUEST_TIMEOUT'] = '300'

from services.kronos_fastapi.config import get_settings

settings = get_settings()

print("=" * 70)
print("配置验证")
print("=" * 70)
print(f"device: {settings.device}")
print(f"inference_timeout: {settings.inference_timeout}")
print(f"request_timeout: {settings.request_timeout}")
print(f"startup_timeout: {settings.startup_timeout}")
print(f"max_context: {settings.max_context}")
print()
print("环境变量:")
print(f"  KRONOS_DEVICE: {os.environ.get('KRONOS_DEVICE')}")
print(f"  KRONOS_INFERENCE_TIMEOUT: {os.environ.get('KRONOS_INFERENCE_TIMEOUT')}")
print(f"  KRONOS_REQUEST_TIMEOUT: {os.environ.get('KRONOS_REQUEST_TIMEOUT')}")
print("=" * 70)

if settings.inference_timeout == 240:
    print("✓ inference_timeout 正确: 240 秒")
else:
    print(f"✗ inference_timeout 错误: {settings.inference_timeout} 秒 (应该是 240)")

if settings.request_timeout == 300:
    print("✓ request_timeout 正确: 300 秒")
else:
    print(f"✗ request_timeout 错误: {settings.request_timeout} 秒 (应该是 300)")
