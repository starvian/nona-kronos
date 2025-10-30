# Data API Service - Quick Start Guide

快速开始使用 Data API 服务

---

## 🚀 5分钟快速启动

### 1. 启动服务

```bash
cd /data/ws/kronos/services/data_api
./start.sh
```

### 2. 检查健康状态

```bash
curl http://localhost:8001/v1/healthz
```

### 3. 查看 API 文档

浏览器打开: http://localhost:8001/docs

### 4. 测试 K-line 查询

```bash
curl "http://localhost:8001/v1/kline/EURUSD?limit=10&timeframe=1h"
```

### 5. 运行完整预测流程

```bash
cd /data/ws/kronos/gitSource/examples
python ds_request_clickhouse.py EURUSD 128 1h
```

---

## 📖 详细使用

### 服务管理

```bash
# 启动
cd /data/ws/kronos/services/data_api
./start.sh

# 停止
./stop.sh

# 查看日志
docker-compose logs -f

# 重启
docker-compose restart
```

### API 调用示例

#### 1. 健康检查

```bash
curl http://localhost:8001/v1/healthz
```

**响应**:
```json
{
  "status": "ok",
  "timestamp": "2025-10-30T12:00:00",
  "database_connected": true,
  "version": "1.0.0"
}
```

#### 2. 获取 K 线数据 (POST)

```bash
curl -X POST http://localhost:8001/v1/kline \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "limit": 128,
    "timeframe": "1h"
  }'
```

#### 3. 获取 K 线数据 (GET)

```bash
# 小时数据
curl "http://localhost:8001/v1/kline/EURUSD?limit=128&timeframe=1h"

# 日数据
curl "http://localhost:8001/v1/kline/EURUSD?limit=30&timeframe=1d"
```

### Python 集成

#### 方式1: 使用集成客户端

```python
from examples.ds_request_clickhouse import predict_with_real_data

# 一键预测
prediction = predict_with_real_data(
    symbol="EURUSD",
    limit=128,
    timeframe="1h",
    verbose=True
)

print(f"预测价格: {prediction['close']:.5f}")
```

#### 方式2: 手动集成

```python
import requests
from datetime import datetime, timedelta
from examples.ds_request import KronosClient

# 1. 获取数据
response = requests.post(
    "http://localhost:8001/v1/kline",
    json={"symbol": "EURUSD", "limit": 128, "timeframe": "1h"}
)
data = response.json()

# 2. 转换格式
candles = [
    {
        'open': c['open'],
        'high': c['high'],
        'low': c['low'],
        'close': c['close'],
        'volume': c['volume'],
        'amount': c['amount']
    }
    for c in data['candles']
]

timestamps = [
    datetime.fromisoformat(c['timestamp'].replace('+00:00', ''))
    for c in data['candles']
]

# 3. 预测
client = KronosClient(base_url="http://localhost:8000")
prediction = client.predict_single(
    candles=candles,
    timestamps=timestamps,
    prediction_timestamp=timestamps[-1] + timedelta(hours=1),
    series_id="EURUSD",
    verbose=True
)

print(f"预测结果: {prediction}")
```

---

## 🔧 配置

### 环境变量 (.env)

```bash
# ClickHouse 连接
DATA_API_CLICKHOUSE_HOST=111.220.88.138
DATA_API_CLICKHOUSE_PORT=19999
DATA_API_CLICKHOUSE_USER=webss
DATA_API_CLICKHOUSE_PASSWORD=your_password
DATA_API_CLICKHOUSE_DATABASE=default

# 服务配置
DATA_API_LOG_LEVEL=INFO
DATA_API_API_PORT=8001
```

### 修改配置

1. 编辑 `.env` 文件
2. 重启服务: `docker-compose restart`

---

## 🐛 故障排查

### 问题1: 服务无法启动

```bash
# 检查端口占用
lsof -i :8001

# 查看日志
docker-compose logs

# 重新构建
docker-compose down
docker-compose up -d --build
```

### 问题2: 数据库连接失败

```bash
# 检查健康状态
curl http://localhost:8001/v1/healthz

# 测试 ClickHouse 连接
telnet 111.220.88.138 19999

# 验证凭据
# 更新 .env 文件后重启
docker-compose restart
```

### 问题3: API 返回错误

```bash
# 查看详细日志
docker-compose logs -f

# 检查请求格式
curl -v "http://localhost:8001/v1/kline/EURUSD?limit=10&timeframe=1h"
```

---

## 📚 更多文档

- **完整文档**: `README.md`
- **实施状态**: `IMPLEMENTATION_COMPLETE.md`
- **部署状态**: `DEPLOYMENT_STATUS.md`
- **API 文档**: http://localhost:8001/docs

---

## 💡 常用命令

```bash
# 服务管理
./start.sh                          # 启动服务
./stop.sh                           # 停止服务
docker-compose logs -f              # 查看日志
docker-compose restart              # 重启服务
docker-compose ps                   # 查看状态

# 测试
curl http://localhost:8001/v1/healthz              # 健康检查
curl http://localhost:8001/v1/kline/EURUSD?limit=10  # 获取数据

# 客户端
python ds_request_clickhouse.py                    # 完整流程
python ds_request_clickhouse.py EURUSD 128 1h     # 自定义参数
```

---

## 🎯 快速测试流程

### 完整测试（5步）

```bash
# 1. 启动服务
cd /data/ws/kronos/services/data_api && ./start.sh

# 2. 健康检查
curl http://localhost:8001/v1/healthz

# 3. 获取 10 根 K 线
curl "http://localhost:8001/v1/kline/EURUSD?limit=10&timeframe=1h" | python3 -m json.tool

# 4. 运行完整预测
cd /data/ws/kronos/gitSource/examples
python ds_request_clickhouse.py

# 5. 查看日志
cd /data/ws/kronos/services/data_api
docker-compose logs --tail=50
```

---

## ✅ 成功标志

服务正常运行时，你会看到：

1. ✅ `./start.sh` 显示 "✓ Data API service is ready!"
2. ✅ Health check 返回 `"database_connected": true`
3. ✅ K-line 查询返回 JSON 数据
4. ✅ 完整预测流程成功输出预测结果

---

**准备好了吗？开始使用吧！** 🚀
