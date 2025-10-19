# Kronos FastAPI 服务访问指南

## 当前状态

✅ **CPU 服务运行中**
- 容器名：`kronos-api-cpu`
- 镜像：`kronos-fastapi:cpu` (1.2GB)
- 状态：健康 (healthy)
- 内部端口：8000
- 设备：CPU

---

## 方式 1：从容器内部访问（当前可用）✅

适用于：调试、测试、容器间通信

### 健康检查

```bash
docker exec kronos-api-cpu curl -s http://localhost:8000/v1/healthz | jq .
```

**响应：**
```json
{"status": "ok"}
```

### 就绪检查

```bash
docker exec kronos-api-cpu curl -s http://localhost:8000/v1/readyz | jq .
```

**响应：**
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cpu",
  "device_warning": null
}
```

### 服务信息

```bash
docker exec kronos-api-cpu curl -s http://localhost:8000/ | jq .
```

**响应：**
```json
{"message": "Kronos FastAPI Service"}
```

### 预测请求示例

```bash
# 1. 创建测试数据（在宿主机）
cat > /tmp/predict_request.json << 'EOF'
{
  "series_id": "BTC-USD",
  "candles": [
    {"open": 50000.0, "high": 51000.0, "low": 49500.0, "close": 50800.0},
    {"open": 50800.0, "high": 51500.0, "low": 50500.0, "close": 51200.0},
    {"open": 51200.0, "high": 52000.0, "low": 51000.0, "close": 51800.0}
  ],
  "timestamps": [
    "2025-01-01T09:00:00",
    "2025-01-01T09:05:00",
    "2025-01-01T09:10:00"
  ],
  "prediction_timestamps": [
    "2025-01-01T09:15:00",
    "2025-01-01T09:20:00"
  ]
}
EOF

# 2. 复制到容器
docker cp /tmp/predict_request.json kronos-api-cpu:/tmp/

# 3. 发起预测请求
docker exec kronos-api-cpu curl -s -X POST \
  http://localhost:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d @/tmp/predict_request.json | jq .
```

---

## 方式 2：从宿主机访问（需要暴露端口）

### 步骤 1：修改 docker-compose.cpu.yml

打开文件并**取消注释**端口映射（第 44-45 行）：

```yaml
# 修改前（当前配置）：
# No external port mapping for security (internal access only)
# To access from host for testing, temporarily uncomment below:
# ports:
#   - "8000:8000"

# 修改后：
ports:
  - "8000:8000"
```

### 步骤 2：重新部署

```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-cpu.sh --stop
./deploy-cpu.sh
```

### 步骤 3：从宿主机访问

```bash
# 健康检查
curl http://localhost:8000/v1/healthz | jq .

# 就绪检查
curl http://localhost:8000/v1/readyz | jq .

# 预测请求
curl -X POST http://localhost:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d @/tmp/predict_request.json | jq .
```

---

## 方式 3：从其他 Docker 容器访问（推荐生产环境）

适用于：微服务架构、容器间通信

### 连接到同一网络

```bash
# 查看 Kronos 网络
docker network ls | grep kronos
# 输出：kronos_fastapi_kronos-internal

# 启动客户端容器并连接到同一网络
docker run --rm -it --network kronos_fastapi_kronos-internal curlimages/curl \
  curl http://kronos-api-cpu:8000/v1/healthz
```

### 在 docker-compose.yml 中配置

```yaml
version: '3.8'

services:
  your-app:
    image: your-app:latest
    networks:
      - kronos_fastapi_kronos-internal
    environment:
      - KRONOS_API_URL=http://kronos-api-cpu:8000

networks:
  kronos_fastapi_kronos-internal:
    external: true
```

---

## API 端点详解

### 1. GET /v1/healthz
**用途**：存活检查（Kubernetes liveness probe）

**响应**：
```json
{"status": "ok"}
```

---

### 2. GET /v1/readyz
**用途**：就绪检查（Kubernetes readiness probe）

**响应**：
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cpu",
  "device_warning": null
}
```

---

### 3. POST /v1/predict/single
**用途**：单个时间序列预测

**请求格式**：
```json
{
  "series_id": "可选的序列标识符",
  "candles": [
    {
      "open": 100.0,
      "high": 105.0,
      "low": 99.0,
      "close": 103.0,
      "volume": 1000000.0,  // 可选
      "amount": 100000.0    // 可选
    }
  ],
  "timestamps": ["2025-01-01T09:00:00"],
  "prediction_timestamps": ["2025-01-01T09:05:00"],
  "overrides": {  // 可选
    "pred_len": 120,
    "temperature": 1.0,
    "top_k": 0,
    "top_p": 0.9,
    "sample_count": 1
  }
}
```

**字段说明**：
- `candles`：1-2048 个历史蜡烛（OHLC 数据）
- `timestamps`：与 candles 长度一致的时间戳（必须递增）
- `prediction_timestamps`：1-512 个预测时间点（必须在 timestamps 之后）
- `overrides`：可选的预测参数覆盖

**OHLC 验证**：
- `low <= open, close <= high`
- `low <= high`
- 所有价格必须 > 0

**响应格式**：
```json
{
  "series_id": "BTC-USD",
  "prediction": [
    {
      "timestamp": "2025-01-01T09:15:00",
      "open": 108.5,
      "high": 112.3,
      "low": 107.2,
      "close": 110.8,
      "volume": 0.0,
      "amount": 0.0
    }
  ],
  "model_version": "NeoQuasar/Kronos-small",
  "tokenizer_version": "NeoQuasar/Kronos-Tokenizer-base"
}
```

---

### 4. POST /v1/predict/batch
**用途**：批量预测多个时间序列

**请求格式**：
```json
{
  "items": [
    {
      "series_id": "BTC-USD",
      "candles": [...],
      "timestamps": [...],
      "prediction_timestamps": [...]
    },
    {
      "series_id": "ETH-USD",
      "candles": [...],
      "timestamps": [...],
      "prediction_timestamps": [...]
    }
  ]
}
```

**响应**：返回多个预测结果数组

---

### 5. GET /v1/metrics
**用途**：Prometheus 指标

**响应**：
```
# HELP prediction_requests_total Total prediction requests
# TYPE prediction_requests_total counter
prediction_requests_total{status="success"} 42.0
prediction_requests_total{status="error"} 2.0

# HELP prediction_latency_seconds Prediction latency
# TYPE prediction_latency_seconds histogram
prediction_latency_seconds_bucket{le="0.1"} 10.0
...
```

---

## 完整测试示例

### Python 客户端

```python
import requests
from datetime import datetime, timedelta

# API 端点
# 方式 1：容器内部（需要在容器内运行）
# base_url = "http://localhost:8000"

# 方式 2：宿主机（需要暴露端口）
base_url = "http://localhost:8000"

# 方式 3：容器间（从其他容器访问）
# base_url = "http://kronos-api-cpu:8000"

# 健康检查
health = requests.get(f"{base_url}/v1/healthz").json()
print("Health:", health)

readiness = requests.get(f"{base_url}/v1/readyz").json()
print("Ready:", readiness)

# 预测请求
base_time = datetime(2025, 1, 1, 9, 0, 0)
request_data = {
    "series_id": "BTC-USD",
    "candles": [
        {"open": 50000.0, "high": 51000.0, "low": 49500.0, "close": 50800.0},
        {"open": 50800.0, "high": 51500.0, "low": 50500.0, "close": 51200.0},
        {"open": 51200.0, "high": 52000.0, "low": 51000.0, "close": 51800.0}
    ],
    "timestamps": [
        (base_time + timedelta(minutes=i*5)).isoformat()
        for i in range(3)
    ],
    "prediction_timestamps": [
        (base_time + timedelta(minutes=15)).isoformat(),
        (base_time + timedelta(minutes=20)).isoformat()
    ]
}

response = requests.post(
    f"{base_url}/v1/predict/single",
    json=request_data
)

if response.status_code == 200:
    prediction = response.json()
    print("Prediction:", prediction)
else:
    print("Error:", response.status_code, response.text)
```

### curl 示例（完整）

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"  # 根据访问方式修改

# 1. 健康检查
echo "=== Health Check ==="
curl -s "${BASE_URL}/v1/healthz" | jq .

# 2. 就绪检查
echo -e "\n=== Readiness Check ==="
curl -s "${BASE_URL}/v1/readyz" | jq .

# 3. 预测请求
echo -e "\n=== Prediction Request ==="
curl -s -X POST "${BASE_URL}/v1/predict/single" \
  -H "Content-Type: application/json" \
  -d '{
    "series_id": "BTC-USD",
    "candles": [
      {"open": 50000.0, "high": 51000.0, "low": 49500.0, "close": 50800.0},
      {"open": 50800.0, "high": 51500.0, "low": 50500.0, "close": 51200.0},
      {"open": 51200.0, "high": 52000.0, "low": 51000.0, "close": 51800.0}
    ],
    "timestamps": [
      "2025-01-01T09:00:00",
      "2025-01-01T09:05:00",
      "2025-01-01T09:10:00"
    ],
    "prediction_timestamps": [
      "2025-01-01T09:15:00",
      "2025-01-01T09:20:00"
    ]
  }' | jq .

# 4. Prometheus 指标
echo -e "\n=== Metrics ==="
curl -s "${BASE_URL}/v1/metrics" | head -20
```

---

## 常见错误

### 1. "Field required" 错误

**原因**：缺少必需字段

**解决**：检查请求格式，确保包含 `candles`、`timestamps`、`prediction_timestamps`

---

### 2. "candles and timestamps length mismatch"

**原因**：蜡烛数量和时间戳数量不一致

**解决**：确保 `len(candles) == len(timestamps)`

---

### 3. "timestamps must be in ascending order"

**原因**：时间戳未按升序排列

**解决**：确保时间戳递增

---

### 4. "prediction_timestamps must be after input timestamps"

**原因**：预测时间早于最后一个历史时间

**解决**：确保 `prediction_timestamps[0] > timestamps[-1]`

---

### 5. "Low cannot be greater than high"

**原因**：OHLC 数据不合理

**解决**：确保 `low <= open, close <= high` 且 `low <= high`

---

## 性能建议

### 历史数据长度
- **最小**：至少 10-20 个蜡烛获得合理预测
- **推荐**：50-100 个蜡烛用于更准确的预测
- **最大**：512 个蜡烛（模型上下文限制）

### 预测长度
- **短期**：1-10 个时间点（更准确）
- **中期**：10-50 个时间点
- **长期**：50-120 个时间点（准确性下降）

### 采样参数
- `temperature=1.0`：标准随机性
- `top_p=0.9`：保留 90% 概率质量
- `sample_count=1`：单次采样（快速）
- `sample_count=5-10`：多次采样平均（更稳定但慢）

---

## 安全注意事项

### 生产环境
1. ✅ **不要暴露端口到公网**（默认配置已禁用）
2. ✅ **使用容器间网络通信**（推荐方式 3）
3. ✅ **启用容器白名单**（已配置）
4. ✅ **启用速率限制**（已配置：100 req/min）
5. ✅ **限制请求大小**（已配置：10MB）

### 开发/测试环境
- 可临时暴露端口到 localhost（方式 2）
- **不要**在生产环境使用端口映射

---

## 监控和日志

### 查看实时日志

```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-cpu.sh --logs

# 或直接使用 docker
docker logs -f kronos-api-cpu
```

### 查看 Prometheus 指标

```bash
# 从容器内
docker exec kronos-api-cpu curl http://localhost:8000/v1/metrics

# 如果暴露了端口
curl http://localhost:8000/v1/metrics
```

---

## 快速参考

| 访问方式 | URL | 适用场景 | 当前可用 |
|---------|-----|---------|---------|
| 容器内部 | `http://localhost:8000` | 调试、测试 | ✅ |
| 宿主机 | `http://localhost:8000` | 本地开发 | ❌（需暴露端口） |
| 容器间 | `http://kronos-api-cpu:8000` | 生产微服务 | ✅ |

---

**更新时间**：2025-10-16
**服务版本**：kronos-fastapi:cpu (1.2GB)
**状态**：✅ 健康运行中
