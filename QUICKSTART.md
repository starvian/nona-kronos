# Kronos CPU 模式 - 快速开始

## 🚀 一分钟快速测试

### 1. 启动服务器（终端 1）

```bash
cd /data/ws/kronos/services
./start_cpu_server.sh
```

等待看到：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### 2. 运行测试客户端（终端 2）

打开新终端：

```bash
cd /data/ws/kronos/services

# 等待模型加载（1-2 分钟）
watch -n 2 'curl -s http://localhost:8000/v1/readyz | python -m json.tool'

# 当看到 "model_loaded": true 后，按 Ctrl+C 退出 watch

# 运行测试
python test_cpu_prediction.py
```

## 📋 详细步骤

### 准备工作

**检查依赖是否已安装**：
```bash
# 基础依赖（必须）
pip list | grep -E "torch|pandas|numpy|fastapi|uvicorn"

# 如果缺少，安装：
pip install -r /data/ws/kronos/gitSource/requirements.txt
pip install -r /data/ws/kronos/services/kronos_fastapi/requirements.txt
```

### 方式 1: 使用一键启动脚本（推荐）

```bash
cd /data/ws/kronos/services

# 启动服务（默认端口 8000）
./start_cpu_server.sh

# 或指定端口
./start_cpu_server.sh 8080
```

### 方式 2: 手动启动

```bash
cd /data/ws/kronos/gitSource

export KRONOS_DEVICE=cpu
export KRONOS_LOG_LEVEL=INFO

uvicorn services.kronos_fastapi.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info
```

### 验证服务

**健康检查**：
```bash
curl http://localhost:8000/v1/healthz
# 预期: {"status":"ok"}
```

**就绪检查**：
```bash
curl http://localhost:8000/v1/readyz
# 预期: {"status":"ok","model_loaded":true,"device":"cpu","device_warning":null}
```

如果 `model_loaded` 是 `false`，等待 1-2 分钟后重试。

### 运行测试客户端

```bash
cd /data/ws/kronos/services
python test_cpu_prediction.py
```

### 预期输出

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
  ...
```

## 🎯 手动 API 测试

### 使用 curl

```bash
# 生成测试数据并发送请求
curl -X POST http://localhost:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{
    "series_id": "test",
    "candles": [
      {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000, "amount": 100500000},
      {"open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1100000, "amount": 111650000}
    ],
    "timestamps": [
      "2024-01-01T09:30:00",
      "2024-01-01T09:31:00"
    ],
    "prediction_timestamps": [
      "2024-01-01T09:32:00",
      "2024-01-01T09:33:00"
    ],
    "overrides": {
      "pred_len": 2,
      "temperature": 1.0,
      "sample_count": 1
    }
  }'
```

### 使用 Python 脚本

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/predict/single",
    json={
        "series_id": "test",
        "candles": [
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000, "amount": 100500000},
            {"open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1100000, "amount": 111650000}
        ],
        "timestamps": ["2024-01-01T09:30:00", "2024-01-01T09:31:00"],
        "prediction_timestamps": ["2024-01-01T09:32:00", "2024-01-01T09:33:00"],
        "overrides": {"pred_len": 2, "temperature": 1.0, "sample_count": 1}
    },
    timeout=60
)

print(response.json())
```

## ⚙️ 配置选项

### 环境变量

在启动前设置：

```bash
# 强制 CPU 模式（即使有 GPU）
export KRONOS_DEVICE=cpu

# 使用 GPU（如果可用）
export KRONOS_DEVICE=cuda:0

# 自动检测
export KRONOS_DEVICE=auto

# 增加超时时间（秒）
export KRONOS_INFERENCE_TIMEOUT=180
export KRONOS_REQUEST_TIMEOUT=300

# 禁用安全检查（开发模式）
export KRONOS_SECURITY_ENABLED=false
export KRONOS_RATE_LIMIT_ENABLED=false
```

### 配置文件

编辑 `services/kronos_fastapi/.env`：

```bash
cd /data/ws/kronos/services/kronos_fastapi
cp .env.cpu .env
nano .env
```

## 🐛 常见问题

### Q1: 端口被占用

**错误**: `Address already in use`

**解决**:
```bash
# 查看占用进程
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或使用其他端口
./start_cpu_server.sh 8080
```

### Q2: 模型加载失败

**错误**: `No such file or directory: '/data/ws/kronos/models'`

**解决**:

选项 1 - 使用 Hugging Face（自动下载）:
```bash
export KRONOS_MODEL_ID=NeoQuasar/Kronos-small
export KRONOS_TOKENIZER_ID=NeoQuasar/Kronos-Tokenizer-base
unset KRONOS_MODEL_PATH
```

选项 2 - 下载模型到本地:
```bash
mkdir -p /data/ws/kronos/models
# 手动下载模型文件到该目录
```

### Q3: 预测超时

**错误**: `requests.exceptions.Timeout`

**原因**: CPU 推理较慢

**解决**:
1. 减少预测长度
2. 增加超时时间：
```bash
export KRONOS_INFERENCE_TIMEOUT=300
export KRONOS_REQUEST_TIMEOUT=600
```

### Q4: Import 错误

**错误**: `ModuleNotFoundError: No module named 'model'`

**原因**: 工作目录错误

**解决**: 必须从 `gitSource/` 目录启动:
```bash
cd /data/ws/kronos/gitSource
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

## 📚 更多文档

- **详细启动指南**: `START_CPU_MODE.md`
- **设备支持文档**: `DEVICE_SUPPORT.md`
- **实现总结**: `CPU_GPU_IMPLEMENTATION.md`
- **FastAPI 文档**: `kronos_fastapi/README.md`

## 🛑 停止服务

按 `Ctrl+C` 停止前台运行的服务。

如果后台运行：
```bash
pkill -f "uvicorn services.kronos_fastapi.main:app"
```

## 📊 性能参考

CPU 模式典型性能（Intel i7/Xeon，仅供参考）：

| 配置 | 预计时间 |
|------|---------|
| 输入100点 + 预测10点 + 采样1次 | 10-20秒 |
| 输入100点 + 预测10点 + 采样3次 | 30-60秒 |
| 输入200点 + 预测20点 + 采样1次 | 20-40秒 |

**注意**: CPU 比 GPU 慢 10-50 倍。生产环境建议使用 GPU。

## ✅ 验证清单

- [ ] 服务启动成功（无错误日志）
- [ ] 健康检查返回 `"status": "ok"`
- [ ] 就绪检查返回 `"model_loaded": true`
- [ ] 设备显示为 `"device": "cpu"`
- [ ] 测试客户端运行成功
- [ ] 预测时间在合理范围内
- [ ] 预测结果包含 OHLC 数据
