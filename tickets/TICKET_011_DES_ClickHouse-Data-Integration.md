# TICKET_011_DES - ClickHouse Data Integration Design

**Type**: Design
**Status**: Discussion
**Priority**: Medium
**Created**: 2025-10-30
**Component**: Data Integration

---

## Problem Statement

当前 `ds_request.py` 使用随机生成的测试数据。需要设计一个方案从 ClickHouse 读取真实的历史 K 线数据，然后发送给 Kronos 预测服务。

## Core Question

**是否应该实现一个 API 来读取 ClickHouse 数据？**

---

## Architecture Options

### Option 1: Direct Client Access (No API) ⭐ **推荐开始**

```
┌─────────────┐
│  Client     │
│  Script     │
└──────┬──────┘
       │ 1. Read data
       ↓
┌─────────────┐
│ ClickHouse  │
│  Database   │
└──────┬──────┘
       │ 2. Predict
       ↓
┌─────────────┐
│   Kronos    │
│   FastAPI   │
└─────────────┘
```

**实现方式：**
```python
# ds_request_clickhouse.py
from clickhouse_driver import Client
from ds_request import KronosClient

# 1. 从 ClickHouse 读取数据
ch_client = Client(host='localhost')
candles = ch_client.execute("""
    SELECT timestamp, open, high, low, close, volume
    FROM kline_data
    WHERE symbol = 'BTC-USD'
    ORDER BY timestamp DESC
    LIMIT 128
""")

# 2. 发送给 Kronos 预测
kronos_client = KronosClient()
prediction = kronos_client.predict_single(candles, timestamps, next_time)
```

**优点：**
- ✅ 简单直接，快速实现
- ✅ 无额外服务，减少运维复杂度
- ✅ 适合单个客户端或小规模使用
- ✅ 低延迟（无中间层）

**缺点：**
- ❌ 需要直接暴露 ClickHouse 访问权限
- ❌ 数据访问逻辑分散在客户端
- ❌ 难以统一管理查询优化
- ❌ 不适合多客户端场景

**适用场景：**
- 个人研究项目
- 原型开发
- 单一应用集成

---

### Option 2: Data API Microservice 🏗️ **生产推荐**

```
┌─────────────┐
│  Client     │
│  Script     │
└──────┬──────┘
       │ 1. Get data
       ↓
┌─────────────┐
│  Data API   │ ← 新增服务
│  (FastAPI)  │
└──────┬──────┘
       │ 2. Query
       ↓
┌─────────────┐
│ ClickHouse  │
│  Database   │
└─────────────┘
       │ 3. Predict
       ↓
┌─────────────┐
│   Kronos    │
│   FastAPI   │
└─────────────┘
```

**实现方式：**
```python
# services/data_api/main.py
from fastapi import FastAPI
from clickhouse_driver import Client

app = FastAPI()
ch = Client(host='clickhouse-server')

@app.get("/v1/kline/{symbol}")
def get_kline_data(
    symbol: str,
    limit: int = 128,
    end_time: Optional[datetime] = None
):
    """Get historical K-line data from ClickHouse."""
    query = """
        SELECT timestamp, open, high, low, close, volume, amount
        FROM kline_data
        WHERE symbol = %(symbol)s
        AND timestamp <= %(end_time)s
        ORDER BY timestamp DESC
        LIMIT %(limit)s
    """
    data = ch.execute(query, {
        'symbol': symbol,
        'end_time': end_time or datetime.now(),
        'limit': limit
    })
    return {"symbol": symbol, "candles": data}

# Client usage
data_client = requests.get(
    "http://data-api:8001/v1/kline/BTC-USD?limit=128"
).json()

kronos_client.predict_single(data_client['candles'], ...)
```

**优点：**
- ✅ 统一的数据访问层
- ✅ 可以添加缓存、权限控制、限流
- ✅ 易于监控和日志记录
- ✅ 支持多个客户端
- ✅ 可以做数据预处理、验证
- ✅ ClickHouse 不直接暴露

**缺点：**
- ❌ 增加了系统复杂度
- ❌ 多一层网络调用（额外延迟 ~10-50ms）
- ❌ 需要维护额外的服务

**适用场景：**
- 生产环境
- 多客户端访问
- 需要数据治理
- 团队协作

---

### Option 3: Unified Prediction API (All-in-One) 🎯

```
┌─────────────┐
│  Client     │
│  Script     │
└──────┬──────┘
       │ Request: symbol + time
       ↓
┌─────────────────────────┐
│   Enhanced Kronos API   │ ← 扩展现有服务
│  - Data fetching        │
│  - Prediction           │
└──────┬──────────────────┘
       │ Query data
       ↓
┌─────────────┐
│ ClickHouse  │
└─────────────┘
```

**实现方式：**
```python
# services/kronos_fastapi/routes.py 新增端点
@router.post("/v1/predict/from_db")
async def predict_from_database(
    symbol: str,
    predict_timestamp: datetime,
    lookback_candles: int = 128
):
    """Fetch data from ClickHouse and predict."""
    # 1. 从 ClickHouse 获取数据
    candles = fetch_from_clickhouse(symbol, lookback_candles)

    # 2. 直接预测
    prediction = manager.predict_single(candles, ...)

    return prediction

# Client usage (极简)
response = requests.post(
    "http://kronos-api:8000/v1/predict/from_db",
    json={
        "symbol": "BTC-USD",
        "predict_timestamp": "2025-10-30T12:00:00"
    }
)
```

**优点：**
- ✅ 客户端极简，一次调用完成
- ✅ 最少的网络往返
- ✅ 数据和预测逻辑紧密集成
- ✅ 易于实现端到端优化

**缺点：**
- ❌ Kronos 服务职责过重（违反单一职责原则）
- ❌ Kronos 服务依赖 ClickHouse（增加耦合）
- ❌ 难以独立扩展数据层和预测层
- ❌ 如果有多个数据源（MySQL, PostgreSQL），会变得复杂

**适用场景：**
- 快速原型
- 数据源单一且稳定
- 不需要数据层独立扩展

---

### Option 4: Hybrid Approach (灵活混合) 🔀

```
┌─────────────┐     ┌─────────────┐
│  Client A   │     │  Client B   │
│  (Direct)   │     │  (API)      │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │ Direct            │ Via API
       ↓                   ↓
┌─────────────┐     ┌─────────────┐
│ ClickHouse  │←────│  Data API   │
└──────┬──────┘     └─────────────┘
       │
       └─────────┬─────────┘
                 ↓
          ┌─────────────┐
          │   Kronos    │
          │   FastAPI   │
          └─────────────┘
```

**实现方式：**
- 提供 Data API 作为可选服务
- 客户端可以选择直接访问或通过 API
- Kronos 保持纯粹的预测功能

**优点：**
- ✅ 灵活性最高
- ✅ 渐进式演进（先直连，后加 API）
- ✅ 满足不同场景需求

**缺点：**
- ❌ 架构复杂度较高
- ❌ 需要维护多种访问方式

---

## Detailed Design: Option 2 (Data API Microservice)

### API Specification

#### 1. Get K-line Data

```
GET /v1/kline/{symbol}
```

**Query Parameters:**
```json
{
  "limit": 128,               // 获取K线数量
  "end_time": "2025-10-30T12:00:00",  // 结束时间（可选）
  "interval": "5m"            // K线周期（可选）
}
```

**Response:**
```json
{
  "symbol": "BTC-USD",
  "interval": "5m",
  "count": 128,
  "candles": [
    {
      "timestamp": "2025-10-30T11:55:00",
      "open": 50000.0,
      "high": 51000.0,
      "low": 49500.0,
      "close": 50800.0,
      "volume": 1000.0,
      "amount": 50000000.0
    }
    // ... 127 more
  ]
}
```

#### 2. Get Multiple Symbols (Batch)

```
POST /v1/kline/batch
```

**Request:**
```json
{
  "symbols": ["BTC-USD", "ETH-USD"],
  "limit": 128,
  "end_time": "2025-10-30T12:00:00"
}
```

#### 3. Data Validation Endpoint

```
POST /v1/kline/validate
```

检查数据完整性、是否有缺失时间点等。

### ClickHouse Schema Example

```sql
CREATE TABLE kline_data (
    symbol String,
    timestamp DateTime64(3),
    interval String,         -- '1m', '5m', '15m', '1h', etc.
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    amount Float64,
    trade_count UInt64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, interval, timestamp);
```

### Service Configuration

```yaml
# docker-compose.data-api.yml
version: '3.8'

services:
  data-api:
    build:
      context: ../..
      dockerfile: services/data_api/Dockerfile
    image: kronos-data-api:latest
    container_name: kronos-data-api
    ports:
      - "8001:8001"
    environment:
      - CLICKHOUSE_HOST=clickhouse-server
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_DATABASE=market_data
      - CACHE_ENABLED=true
      - CACHE_TTL_SECONDS=60
    networks:
      - kronos-internal
    depends_on:
      - clickhouse

  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: clickhouse-server
    ports:
      - "9000:9000"  # Native protocol
      - "8123:8123"  # HTTP interface
    volumes:
      - clickhouse-data:/var/lib/clickhouse
    networks:
      - kronos-internal

networks:
  kronos-internal:
    external: true

volumes:
  clickhouse-data:
```

---

## Performance Considerations

### Option 1 (Direct): ~0.1s
```
ClickHouse Query: 0.05s
Kronos Predict:   0.05s
Total:            0.10s
```

### Option 2 (Data API): ~0.12s
```
Data API Request: 0.02s
ClickHouse Query: 0.05s
Kronos Predict:   0.05s
Total:            0.12s
```

### Option 3 (Unified): ~0.11s
```
API Request:      0.01s
ClickHouse Query: 0.05s
Kronos Predict:   0.05s
Total:            0.11s
```

**额外开销：**
- Data API 增加 ~10-20ms
- 但换来了架构清晰和可维护性

---

## Implementation Phases

### Phase 1: Quick Start (1 day)
**使用 Option 1: Direct Access**

```bash
# 安装 ClickHouse 驱动
pip install clickhouse-driver

# 创建 ds_request_clickhouse.py
# 直接读取 ClickHouse + 调用 Kronos
```

**目标：** 快速验证整个流程

---

### Phase 2: Production API (3-5 days)
**实现 Option 2: Data API Microservice**

Day 1-2: 实现 Data API 基础功能
- FastAPI 服务框架
- ClickHouse 连接和查询
- 基础的 K 线数据端点

Day 3: 添加功能增强
- 数据验证
- 缓存机制
- 错误处理

Day 4: Docker 化和部署
- Dockerfile
- docker-compose
- 与 Kronos 服务集成

Day 5: 测试和文档
- 集成测试
- API 文档
- 性能测试

---

### Phase 3: Advanced Features (Optional)
- 实时数据流订阅
- 数据预处理管道
- 多数据源聚合
- 数据质量监控

---

## Recommendation Matrix

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 个人研究/原型 | Option 1 | 简单快速 |
| 小团队项目 | Option 2 | 平衡架构和复杂度 |
| 生产环境 | Option 2 | 可维护性和扩展性 |
| 快速演示 | Option 3 | 用户体验最佳 |
| 复杂系统 | Option 2 + 4 | 灵活性最高 |

---

## Open Questions

1. **ClickHouse 数据库是否已经存在？**
   - 如果没有，需要先建立数据采集管道

2. **数据更新频率？**
   - 实时？分钟级？小时级？
   - 影响缓存策略

3. **并发量预期？**
   - 单用户？多用户？
   - 影响是否需要 API 层

4. **数据量级？**
   - 影响查询优化策略
   - 影响是否需要分页

5. **是否需要数据回填（backtesting）？**
   - 批量历史数据查询
   - 可能需要专门的批处理端点

6. **安全性要求？**
   - 是否需要认证授权？
   - 数据访问审计？

---

## Next Steps

### 建议的决策流程：

1. **第一步：回答 Open Questions**
   - 明确需求和约束

2. **第二步：选择初始方案**
   - 如果是快速验证 → Option 1
   - 如果是生产准备 → Option 2
   - 如果不确定 → 先 Option 1，保留演进到 Option 2 的路径

3. **第三步：实现 PoC**
   - 用最简单的方案验证整体流程
   - 测量性能基准

4. **第四步：迭代优化**
   - 根据实际使用情况调整架构

---

## Related Tickets

- TICKET_010_FEA - Data Stream Client (客户端已实现)
- TICKET_003_DES - Kronos FastAPI Microservice Design (预测服务)

---

## Decision Log

**Date**: 2025-10-30
**Status**: Awaiting Discussion
**Decision Maker**: TBD

**Discussion Points:**
- [ ] 确认 ClickHouse 现状
- [ ] 确认使用场景（研究 vs 生产）
- [ ] 确认性能要求
- [ ] 确认团队资源
- [ ] 选择实现方案

---

**下一步行动：讨论并回答 Open Questions，然后选择实现方案。**
