# Kronos CPU 模式启动和测试指南

## 快速开始

### 步骤 1: 配置 CPU 模式

```bash
cd /data/ws/kronos/services/kronos_fastapi

# 复制 CPU 配置文件
cp .env.cpu .env

# 查看配置（确认 KRONOS_DEVICE=cpu）
cat .env | grep KRONOS_DEVICE
```

### 步骤 2: 确保依赖已安装

**CPU 模式只需要基础依赖**：
```bash
cd /data/ws/kronos

# 检查是否已安装
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import pandas; print(f'Pandas: {pandas.__version__}')"

# 如果未安装，执行：
pip install -r gitSource/requirements.txt
pip install -r services/kronos_fastapi/requirements.txt
```

### 步骤 3: 启动服务器

**方式 1: 直接启动（推荐用于测试）**

```bash
cd /data/ws/kronos/gitSource

# 使用 CPU 配置启动
export KRONOS_DEVICE=cpu
export KRONOS_LOG_LEVEL=INFO
export KRONOS_SECURITY_ENABLED=false
export KRONOS_RATE_LIMIT_ENABLED=false

# 启动服务（带自动重载）
uvicorn services.kronos_fastapi.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
```

**方式 2: 使用启动脚本**

```bash
cd /data/ws/kronos/services/kronos_fastapi

# 使用脚本启动（需要先 cp .env.cpu .env）
./start.sh 8000
```

**方式 3: 后台运行**

```bash
cd /data/ws/kronos/gitSource

export KRONOS_DEVICE=cpu
nohup uvicorn services.kronos_fastapi.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    > /tmp/kronos_cpu.log 2>&1 &

echo $! > /tmp/kronos_cpu.pid
echo "服务已启动，PID: $(cat /tmp/kronos_cpu.pid)"
echo "查看日志: tail -f /tmp/kronos_cpu.log"
```

### 步骤 4: 验证服务启动

**等待模型加载**（CPU 模式较慢，可能需要 1-2 分钟）：

```bash
# 检查健康状态
curl http://localhost:8000/v1/healthz

# 检查模型就绪（等待 model_loaded: true）
curl http://localhost:8000/v1/readyz

# 持续监控直到就绪
watch -n 2 'curl -s http://localhost:8000/v1/readyz | jq'
```

预期输出：
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cpu",
  "device_warning": null
}
```

### 步骤 5: 运行测试客户端

**单次测试**：
```bash
cd /data/ws/kronos/services

# 运行测试客户端
python test_cpu_prediction.py
```

**完整性能测试**：
```bash
# 编辑 test_cpu_prediction.py，取消注释性能测试部分
# 或直接运行 Python 脚本并在提示时输入 'yes'
```

## 测试客户端功能

`test_cpu_prediction.py` 提供以下功能：

1. **健康检查** - 验证服务可访问
2. **就绪检查** - 确认模型已加载，显示设备信息
3. **生成测试数据** - 创建模拟的 OHLCV K线数据
4. **执行预测** - 发送预测请求并统计时间
5. **性能测试** - 多种配置的性能基准测试

### 预期输出示例

```
======================================================================
Kronos CPU 模式预测测试
======================================================================

======================================================================
1. 检查服务健康状态
======================================================================
✓ 服务健康: {'status': 'ok'}

======================================================================
2. 检查模型就绪状态
======================================================================
状态: ok
模型已加载: True
设备: cpu
✓ 模型就绪

======================================================================
3. 生成测试数据
======================================================================
✓ 生成 100 条 K 线数据
  时间范围: 2024-01-01T09:30:00 到 2024-01-01T11:09:00
  价格范围: 95.23 - 105.67

======================================================================
4. 执行 CPU 预测
======================================================================
请求参数:
  输入数据点: 100
  预测长度: 10
  Temperature: 1.0
  采样次数: 1

开始预测...

✓ 预测完成!

======================================================================
⏱️  预测时间统计
======================================================================
总耗时: 12.34 秒
平均每个预测点: 1.234 秒
吞吐量: 0.81 点/秒

预测结果（前3个点）:
  1. 时间: 2024-01-01T11:10:00
     OHLC: O=104.23, H=105.12, L=103.89, C=104.56
  2. 时间: 2024-01-01T11:11:00
     OHLC: O=104.56, H=105.34, L=104.12, C=104.89
  3. 时间: 2024-01-01T11:12:00
     OHLC: O=104.89, H=105.67, L=104.45, C=105.23
```

## 性能基准参考

**CPU 模式典型性能**（仅供参考，实际性能取决于 CPU）：

| 输入长度 | 预测长度 | 采样次数 | 预计耗时 |
|---------|---------|---------|----------|
| 50      | 5       | 1       | 5-10秒   |
| 100     | 10      | 1       | 10-20秒  |
| 100     | 10      | 3       | 30-60秒  |
| 200     | 20      | 1       | 20-40秒  |

**注意**: CPU 模式比 GPU 慢 10-50 倍，但无需 GPU 硬件。

## 停止服务

**如果使用前台运行**：
- 按 `Ctrl+C`

**如果使用后台运行**：
```bash
# 使用 PID 文件
kill $(cat /tmp/kronos_cpu.pid)
rm /tmp/kronos_cpu.pid

# 或查找并杀死进程
pkill -f "uvicorn services.kronos_fastapi.main:app"

# 或使用停止脚本
cd /data/ws/kronos/services/kronos_fastapi
./stop.sh 8000
```

## 故障排除

### 问题 1: 服务启动失败

**检查端口占用**：
```bash
lsof -i :8000
# 如果被占用，杀死进程或换端口
```

**查看错误日志**：
```bash
# 如果前台运行，直接查看终端输出
# 如果后台运行，查看日志文件
tail -f /tmp/kronos_cpu.log
```

### 问题 2: 模型加载超时

CPU 模式下模型加载较慢，特别是首次加载或从 Hugging Face 下载时。

**解决方案**：
1. 增加启动超时时间（在 .env 中设置 `KRONOS_STARTUP_TIMEOUT=600`）
2. 预先下载模型到本地
3. 使用更小的模型（如 Kronos-mini）

### 问题 3: 预测超时

**症状**: 客户端报 `requests.exceptions.Timeout`

**解决方案**：
1. 减少预测长度 (`pred_len`)
2. 减少采样次数 (`sample_count`)
3. 增加客户端超时时间（修改 `test_cpu_prediction.py` 中的 `timeout=180`）
4. 增加服务器超时（`.env` 中 `KRONOS_INFERENCE_TIMEOUT`）

### 问题 4: 导入错误

**症状**: `ModuleNotFoundError: No module named 'model'`

**原因**: 工作目录不正确

**解决方案**: 确保从 `gitSource/` 目录启动服务：
```bash
cd /data/ws/kronos/gitSource
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

### 问题 5: CUDA 警告（即使设置了 CPU）

**症状**: 日志中出现 "CUDA device requested but CUDA not available"

**原因**: 环境变量未正确设置或配置文件未生效

**解决方案**：
```bash
# 显式设置环境变量
export KRONOS_DEVICE=cpu

# 或检查 .env 文件
cd /data/ws/kronos/services/kronos_fastapi
grep KRONOS_DEVICE .env
```

## 进阶使用

### 使用 Hugging Face 模型

如果本地没有模型文件，可以从 Hugging Face 自动下载：

编辑 `.env`:
```bash
# 注释掉本地路径
# KRONOS_MODEL_PATH=/data/ws/kronos/models

# 启用 Hugging Face
KRONOS_MODEL_ID=NeoQuasar/Kronos-small
KRONOS_TOKENIZER_ID=NeoQuasar/Kronos-Tokenizer-base
```

首次启动会自动下载模型（需要网络连接）。

### 调整预测参数

编辑 `.env` 中的默认参数：
```bash
# 更快的预测（但质量可能下降）
KRONOS_DEFAULT_SAMPLE_COUNT=1
KRONOS_DEFAULT_TEMPERATURE=0.8

# 更好的质量（但更慢）
KRONOS_DEFAULT_SAMPLE_COUNT=5
KRONOS_DEFAULT_TEMPERATURE=1.0
```

### 监控性能

```bash
# 查看 Prometheus 指标
curl http://localhost:8000/v1/metrics

# 或在浏览器访问
firefox http://localhost:8000/v1/metrics
```

## 相关文档

- 设备支持详情: `services/DEVICE_SUPPORT.md`
- 实现总结: `services/CPU_GPU_IMPLEMENTATION.md`
- FastAPI 服务文档: `services/kronos_fastapi/README.md`
- 设计票据: `services/tickets/TICKET_004_DES_Device-Agnostic-Kronos.md`
