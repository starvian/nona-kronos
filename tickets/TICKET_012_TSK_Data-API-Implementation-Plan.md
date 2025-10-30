# TICKET_012_TSK - Data API Implementation Plan

**Type**: Task
**Status**: Planning
**Priority**: High
**Created**: 2025-10-30
**Component**: Data Integration
**Related**: TICKET_011_DES

---

## Objective

实现 **Option 2 (Data API Microservice)** - 将 ClickHouse K-line 数据聚合功能封装为独立的 FastAPI 微服务。

---

## Background

### 现有基础设施

1. **ClickHouse 数据库**
   - Host: `111.220.88.138` (可通过 `192.168.1.110` 访问)
   - Port: `19999`
   - User: `webss`
   - Password: `webss`
   - Database: `default` (或通过环境变量配置)

2. **已有的聚合函数**
   - Location: nona_server_06 容器
   - Function: `ForexDataProcessor._get_aggregated_data()`
   - Features: 支持 hourly/daily 聚合，OHLC 计算
   - Source: `/data/ws/kronos/services/tickets/CLICKHOUSE_AGGREGATE_IMPLEMENTATION.md`

3. **现有客户端**
   - `ds_request.py`: Kronos 预测客户端
   - 当前使用随机测试数据
   - 需要替换为真实 ClickHouse 数据

---

## Implementation Plan

### Phase 1: Service Structure (Day 1) ✅

#### 1.1 创建服务目录结构

```bash
/data/ws/kronos/services/data_api/
├── __init__.py
├── main.py                    # FastAPI 应用入口
├── routes.py                  # API 路由定义
├── config.py                  # 配置管理
├── schemas.py                 # Pydantic 数据模型
├── database.py                # ClickHouse 连接管理
├── aggregator.py              # 数据聚合核心逻辑
├── middleware.py              # 中间件（日志、请求ID等）
├── logging_utils.py           # 日志配置
├── requirements.txt           # Python 依赖
├── Dockerfile                 # Docker 镜像
├── docker-compose.yml         # 容器编排
├── start.sh                   # 启动脚本
├── stop.sh                    # 停止脚本
└── README.md                  # 服务文档
```

#### 1.2 目录结构说明

```
services/
├── kronos_fastapi/           # 预测服务 (现有)
│   ├── Port: 8000
│   └── Function: 时间序列预测
│
└── data_api/                 # 数据 API 服务 (新增)
    ├── Port: 8001
    └── Function: ClickHouse 数据查询和聚合
```

---

### Phase 2: Core Implementation (Day 2-3) 🔨

#### 2.1 配置管理 (`config.py`)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Data API Service Configuration"""

    # Service info
    app_name: str = "Kronos Data API Service"
    log_level: str = "INFO"

    # ClickHouse connection
    clickhouse_host: str = "111.220.88.138"  # 192.168.1.110 本机
    clickhouse_port: int = 19999
    clickhouse_user: str = "webss"
    clickhouse_password: str = "webss"
    clickhouse_database: str = "default"

    # Connection pool
    clickhouse_pool_size: int = 10
    clickhouse_max_retries: int = 3
    clickhouse_retry_delay: float = 1.0
    clickhouse_timeout: int = 30

    # API settings
    api_port: int = 8001
    api_host: str = "0.0.0.0"

    # Data limits
    max_candles_per_request: int = 10000
    default_candles_limit: int = 128

    # Cache settings (Phase 3)
    cache_enabled: bool = False
    cache_ttl_seconds: int = 60

    model_config = SettingsConfigDict(
        env_prefix="DATA_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

def get_settings() -> Settings:
    return Settings()
```

#### 2.2 数据库连接 (`database.py`)

```python
from clickhouse_driver import Client
from typing import Optional, List, Dict, Any
import logging
from .config import get_settings

logger = logging.getLogger(__name__)

class ClickHouseConnection:
    """ClickHouse connection manager with pooling"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client: Optional[Client] = None

    def connect(self) -> Client:
        """Create and return ClickHouse client"""
        if self._client is None:
            try:
                self._client = Client(
                    host=self.settings.clickhouse_host,
                    port=self.settings.clickhouse_port,
                    user=self.settings.clickhouse_user,
                    password=self.settings.clickhouse_password,
                    database=self.settings.clickhouse_database,
                    settings={
                        'max_execution_time': self.settings.clickhouse_timeout,
                    }
                )
                logger.info(
                    f"Connected to ClickHouse at "
                    f"{self.settings.clickhouse_host}:{self.settings.clickhouse_port}"
                )
            except Exception as e:
                logger.error(f"Failed to connect to ClickHouse: {e}")
                raise

        return self._client

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """Execute query with retry logic"""
        client = self.connect()
        retries = 0

        while retries < self.settings.clickhouse_max_retries:
            try:
                result = client.execute(query, params or {})
                return result
            except Exception as e:
                retries += 1
                logger.warning(
                    f"Query failed (attempt {retries}/{self.settings.clickhouse_max_retries}): {e}"
                )
                if retries >= self.settings.clickhouse_max_retries:
                    raise
                import time
                time.sleep(self.settings.clickhouse_retry_delay)

    def disconnect(self):
        """Close connection"""
        if self._client:
            self._client.disconnect()
            self._client = None
            logger.info("Disconnected from ClickHouse")

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
```

#### 2.3 数据聚合器 (`aggregator.py`)

```python
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
import logging
from .database import ClickHouseConnection

logger = logging.getLogger(__name__)

class KlineAggregator:
    """K-line data aggregation from ClickHouse"""

    def __init__(self, db_connection: ClickHouseConnection):
        self.db = db_connection

    def get_kline_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        timeframe: str = '1h',
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get K-line (OHLC) data from ClickHouse.

        Args:
            symbol: Currency pair (e.g., 'EURUSD', 'BTC-USD')
            start_time: Query start time
            end_time: Query end time
            timeframe: '1h' (hourly) or '1d' (daily)
            limit: Maximum number of candles to return

        Returns:
            DataFrame with OHLC data and timestamp index
        """
        logger.info(
            f"Fetching K-line data: symbol={symbol}, "
            f"timeframe={timeframe}, start={start_time}, end={end_time}, limit={limit}"
        )

        try:
            if timeframe == '1d':
                query = self._build_daily_query(limit)
            else:
                query = self._build_hourly_query(limit)

            results = self.db.execute_query(
                query,
                {
                    'currency_pair': symbol,
                    'start_time': start_time,
                    'end_time': end_time
                }
            )

            if not results:
                logger.warning(f"No data found for {symbol} in timeframe {timeframe}")
                return pd.DataFrame()

            df = self._parse_results(results, timeframe)
            logger.info(f"Retrieved {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching K-line data: {e}")
            raise

    def _build_hourly_query(self, limit: Optional[int]) -> str:
        """Build hourly aggregation query"""
        return f"""
            WITH
            raw_data AS (
                SELECT
                    timestamp,
                    bid_price,
                    ask_price,
                    volume,
                    toDate(if(toHour(timestamp) >= 17, addDays(timestamp, 1), timestamp)) as trading_date,
                    if(toHour(timestamp) < 17,
                        toHour(timestamp) + 7,
                        toHour(timestamp) - 17) as trading_hour
                FROM forex
                WHERE
                    currency_pair = %(currency_pair)s
                    AND timestamp BETWEEN %(start_time)s AND %(end_time)s
                ORDER BY timestamp ASC
            ),
            hourly_data AS (
                SELECT
                    trading_date,
                    trading_hour as hour,
                    argMin(bid_price, timestamp) as open,
                    max(bid_price) as high,
                    min(bid_price) as low,
                    argMax(bid_price, timestamp) as close,
                    avg(bid_price) as avg_bid_price,
                    avg(ask_price) as avg_ask_price,
                    sum(volume) as volume,
                    count() as tick_count
                FROM raw_data
                GROUP BY trading_date, trading_hour
                ORDER BY trading_date ASC, trading_hour ASC
            )
            SELECT
                trading_date,
                hour,
                open,
                high,
                low,
                close,
                avg_bid_price,
                avg_ask_price,
                volume,
                tick_count
            FROM hourly_data
            {f'LIMIT {limit}' if limit else ''}
        """

    def _build_daily_query(self, limit: Optional[int]) -> str:
        """Build daily aggregation query"""
        return f"""
            WITH
            raw_data AS (
                SELECT
                    timestamp,
                    bid_price,
                    ask_price,
                    volume,
                    toDate(if(toHour(timestamp) >= 17, addDays(timestamp, 1), timestamp)) as trading_date
                FROM forex
                WHERE
                    currency_pair = %(currency_pair)s
                    AND timestamp BETWEEN %(start_time)s AND %(end_time)s
                ORDER BY timestamp ASC
            ),
            daily_data AS (
                SELECT
                    trading_date,
                    0 as hour,
                    argMin(bid_price, timestamp) as open,
                    max(bid_price) as high,
                    min(bid_price) as low,
                    argMax(bid_price, timestamp) as close,
                    avg(bid_price) as avg_bid_price,
                    avg(ask_price) as avg_ask_price,
                    sum(volume) as volume,
                    count() as tick_count
                FROM raw_data
                GROUP BY trading_date
                ORDER BY trading_date ASC
            )
            SELECT
                trading_date,
                hour,
                open,
                high,
                low,
                close,
                avg_bid_price,
                avg_ask_price,
                volume,
                tick_count
            FROM daily_data
            {f'LIMIT {limit}' if limit else ''}
        """

    def _parse_results(self, results: List[tuple], timeframe: str) -> pd.DataFrame:
        """Parse query results into DataFrame"""
        df = pd.DataFrame(
            results,
            columns=[
                'trading_date', 'hour', 'open', 'high', 'low', 'close',
                'avg_bid_price', 'avg_ask_price', 'volume', 'tick_count'
            ]
        )

        # Create timestamp index
        temp_timestamp_col = pd.to_datetime(df['trading_date'])

        if timeframe == '1d':
            df.set_index(temp_timestamp_col, inplace=True)
            df.index = df.index.tz_localize('UTC')
        else:
            df['timestamp'] = temp_timestamp_col + pd.to_timedelta(df['hour'], unit='h')
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
            df.set_index('timestamp', inplace=True)

        df.index.name = 'timestamp'
        return df
```

#### 2.4 API 数据模型 (`schemas.py`)

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

class CandleResponse(BaseModel):
    """Single K-line candle"""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None  # Calculated field

class KlineDataResponse(BaseModel):
    """K-line data response"""
    symbol: str
    timeframe: str
    start_time: str
    end_time: str
    count: int
    candles: List[CandleResponse]

class KlineRequest(BaseModel):
    """K-line data request"""
    symbol: str = Field(..., description="Currency pair (e.g., 'EURUSD', 'BTC-USD')")
    limit: int = Field(128, ge=1, le=10000, description="Number of candles")
    end_time: Optional[datetime] = Field(None, description="End time (default: now)")
    timeframe: str = Field('1h', pattern='^(1h|1d)$', description="Timeframe: '1h' or '1d'")

    @field_validator('end_time')
    @classmethod
    def set_default_end_time(cls, v):
        return v or datetime.now()

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    database_connected: bool
    version: str = "1.0.0"
```

#### 2.5 API 路由 (`routes.py`)

```python
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from typing import Optional
import logging

from .schemas import KlineDataResponse, KlineRequest, HealthResponse, CandleResponse
from .aggregator import KlineAggregator
from .database import ClickHouseConnection
from .config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency injection
def get_db_connection():
    """Dependency: Database connection"""
    settings = get_settings()
    return ClickHouseConnection(settings)

def get_aggregator(db: ClickHouseConnection = Depends(get_db_connection)):
    """Dependency: K-line aggregator"""
    return KlineAggregator(db)

@router.get("/v1/healthz", response_model=HealthResponse)
async def health_check(db: ClickHouseConnection = Depends(get_db_connection)):
    """Health check endpoint"""
    try:
        # Test database connection
        client = db.connect()
        result = client.execute("SELECT 1")
        db_connected = result == [(1,)]
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_connected = False

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        timestamp=datetime.now().isoformat(),
        database_connected=db_connected
    )

@router.post("/v1/kline", response_model=KlineDataResponse)
async def get_kline_data(
    request: KlineRequest,
    aggregator: KlineAggregator = Depends(get_aggregator)
):
    """
    Get K-line (OHLC) data from ClickHouse.

    **Example request:**
    ```json
    {
        "symbol": "EURUSD",
        "limit": 128,
        "end_time": "2025-10-30T12:00:00",
        "timeframe": "1h"
    }
    ```

    **Returns:**
    - List of OHLC candles
    - Timestamps in ISO format
    - Trading volume and derived amount
    """
    try:
        # Calculate start time based on limit
        if request.timeframe == '1h':
            start_time = request.end_time - timedelta(hours=request.limit + 24)  # Buffer
        else:  # 1d
            start_time = request.end_time - timedelta(days=request.limit + 7)   # Buffer

        # Fetch data
        df = aggregator.get_kline_data(
            symbol=request.symbol,
            start_time=start_time,
            end_time=request.end_time,
            timeframe=request.timeframe,
            limit=request.limit
        )

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {request.symbol} in timeframe {request.timeframe}"
            )

        # Convert to response format
        candles = []
        for idx, row in df.iterrows():
            candle = CandleResponse(
                timestamp=idx.isoformat(),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                amount=float(row['volume']) * float(row['close'])  # Approximate
            )
            candles.append(candle)

        return KlineDataResponse(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_time=df.index.min().isoformat(),
            end_time=df.index.max().isoformat(),
            count=len(candles),
            candles=candles
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing K-line request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/v1/kline/{symbol}", response_model=KlineDataResponse)
async def get_kline_by_path(
    symbol: str,
    limit: int = 128,
    end_time: Optional[str] = None,
    timeframe: str = '1h',
    aggregator: KlineAggregator = Depends(get_aggregator)
):
    """
    Get K-line data via GET request.

    **Example:** `GET /v1/kline/EURUSD?limit=128&timeframe=1h`
    """
    # Convert to KlineRequest and reuse POST handler logic
    request = KlineRequest(
        symbol=symbol,
        limit=limit,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
        timeframe=timeframe
    )
    return await get_kline_data(request, aggregator)
```

---

### Phase 3: Docker Deployment (Day 3-4) 🐳

#### 3.1 Requirements (`requirements.txt`)

```txt
# FastAPI and server
fastapi>=0.111.0
uvicorn[standard]>=0.30.0

# Data processing
pandas>=2.0.0
numpy>=1.24.0

# ClickHouse
clickhouse-driver>=0.2.6

# Configuration
pydantic>=2.0.0
pydantic-settings>=2.0.0

# Logging and monitoring
python-json-logger>=2.0.7
prometheus-client>=0.20.0

# Utilities
python-dateutil>=2.8.2
pytz>=2023.3
```

#### 3.2 Dockerfile

```dockerfile
# Multi-stage build for Data API service
FROM python:3.10-slim as builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /tmp
COPY services/data_api/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Runtime stage
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r dataapi && \
    useradd -r -g dataapi -u 1001 -m -s /bin/bash dataapi

RUN mkdir -p /app /logs && \
    chown -R dataapi:dataapi /app /logs

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=dataapi:dataapi services/data_api ./services/data_api

USER dataapi

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/v1/healthz || exit 1

CMD ["uvicorn", "services.data_api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
```

#### 3.3 Docker Compose (`docker-compose.yml`)

```yaml
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
      - DATA_API_LOG_LEVEL=INFO
      - DATA_API_CLICKHOUSE_HOST=192.168.1.110
      - DATA_API_CLICKHOUSE_PORT=19999
      - DATA_API_CLICKHOUSE_USER=webss
      - DATA_API_CLICKHOUSE_PASSWORD=webss
      - DATA_API_CLICKHOUSE_DATABASE=default
      - DATA_API_API_PORT=8001
      - DATA_API_API_HOST=0.0.0.0
    networks:
      - kronos-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/v1/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

networks:
  kronos-network:
    external: true
```

#### 3.4 启动/停止脚本

**`start.sh`**
```bash
#!/bin/bash
# Start Data API service

echo "Starting Kronos Data API service..."

# Check if network exists
if ! docker network inspect kronos-network &>/dev/null; then
    echo "Creating kronos-network..."
    docker network create kronos-network
fi

# Build and start
docker-compose up -d --build

# Wait for service to be ready
echo "Waiting for service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8001/v1/healthz > /dev/null; then
        echo "✓ Data API service is ready!"
        echo "✓ API docs: http://localhost:8001/docs"
        exit 0
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo "✗ Service failed to start"
exit 1
```

**`stop.sh`**
```bash
#!/bin/bash
# Stop Data API service

echo "Stopping Kronos Data API service..."
docker-compose down

echo "✓ Service stopped"
```

---

### Phase 4: Client Integration (Day 4-5) 🔌

#### 4.1 更新 `ds_request.py`

在 `/data/ws/kronos/gitSource/examples/` 创建新的客户端：

**`ds_request_clickhouse.py`**

```python
#!/usr/bin/env python3
"""
Kronos Data Stream Client with ClickHouse Integration
Fetches real K-line data from Data API instead of random test data.

Usage:
    # Default (localhost Data API)
    python ds_request_clickhouse.py

    # Custom endpoints
    export DATA_API_URL="http://192.168.1.110:8001"
    export KRONOS_API_URL="http://192.168.1.110:8000"
    python ds_request_clickhouse.py
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from ds_request import KronosClient

class DataAPIClient:
    """Client for Data API service"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get(
            "DATA_API_URL",
            "http://localhost:8001"
        )

    def fetch_kline_data(
        self,
        symbol: str,
        limit: int = 128,
        timeframe: str = '1h',
        end_time: datetime = None
    ) -> Tuple[List[Dict], List[datetime]]:
        """
        Fetch K-line data from Data API.

        Returns:
            Tuple of (candles, timestamps)
        """
        if end_time is None:
            end_time = datetime.now()

        request_data = {
            "symbol": symbol,
            "limit": limit,
            "timeframe": timeframe,
            "end_time": end_time.isoformat()
        }

        url = f"{self.base_url}/v1/kline"
        response = requests.post(url, json=request_data, timeout=30)

        if response.status_code != 200:
            raise requests.RequestException(
                f"Data API request failed: {response.status_code} - {response.text}"
            )

        result = response.json()

        # Convert to format expected by Kronos
        candles = []
        timestamps = []

        for candle_data in result['candles']:
            candle = {
                'open': candle_data['open'],
                'high': candle_data['high'],
                'low': candle_data['low'],
                'close': candle_data['close'],
                'volume': candle_data['volume'],
                'amount': candle_data.get('amount', 0.0)
            }
            candles.append(candle)
            timestamps.append(datetime.fromisoformat(candle_data['timestamp']))

        return candles, timestamps


def main():
    """Main execution with real ClickHouse data"""
    import sys

    # Initialize clients
    data_api_url = os.environ.get("DATA_API_URL", "http://localhost:8001")
    kronos_api_url = os.environ.get("KRONOS_API_URL", "http://localhost:8000")

    data_client = DataAPIClient(base_url=data_api_url)
    kronos_client = KronosClient(base_url=kronos_api_url)

    print(f"Data API: {data_api_url}")
    print(f"Kronos API: {kronos_api_url}")

    # Check Data API health
    try:
        health_response = requests.get(f"{data_api_url}/v1/healthz")
        health = health_response.json()
        print(f"✓ Data API health: {health}")

        if not health.get('database_connected'):
            print("✗ Database not connected!")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Data API check failed: {e}")
        sys.exit(1)

    # Check Kronos API health
    try:
        kronos_health = kronos_client.health_check()
        print(f"✓ Kronos health: {kronos_health}")
    except Exception as e:
        print(f"✗ Kronos API check failed: {e}")
        sys.exit(1)

    # Fetch real data from ClickHouse via Data API
    print("\nFetching real K-line data from ClickHouse...")
    symbol = "EURUSD"  # Change to your actual symbol

    try:
        candles, timestamps = data_client.fetch_kline_data(
            symbol=symbol,
            limit=128,
            timeframe='1h'
        )

        print(f"✓ Fetched {len(candles)} candles")
        print(f"Time range: {timestamps[0]} to {timestamps[-1]}")
        print(f"Last candle: {candles[-1]}")

    except Exception as e:
        print(f"✗ Failed to fetch data: {e}")
        sys.exit(1)

    # Predict next candle
    prediction_timestamp = timestamps[-1] + timedelta(hours=1)

    print(f"\nRequesting prediction for: {prediction_timestamp}")

    try:
        prediction = kronos_client.predict_single(
            candles=candles,
            timestamps=timestamps,
            prediction_timestamp=prediction_timestamp,
            series_id=symbol,
            verbose=True
        )

        print("\n✓ Prediction received:")
        print(f"  Timestamp: {prediction['timestamp']}")
        print(f"  Open:      {prediction['open']:.5f}")
        print(f"  High:      {prediction['high']:.5f}")
        print(f"  Low:       {prediction['low']:.5f}")
        print(f"  Close:     {prediction['close']:.5f}")

        # Show comparison
        last_close = candles[-1]['close']
        pred_close = prediction['close']
        change = ((pred_close - last_close) / last_close) * 100

        print(f"\n  Last close: {last_close:.5f}")
        print(f"  Predicted:  {pred_close:.5f}")
        print(f"  Change:     {change:+.2f}%")

        # Show timing
        if '_request_time_seconds' in prediction:
            print(f"\n⏱️  Kronos request time: {prediction['_request_time_seconds']:.2f}s")

    except Exception as e:
        print(f"\n✗ Prediction failed: {e}")
        sys.exit(1)

    print("\n✓ Complete workflow successful!")


if __name__ == "__main__":
    main()
```

---

### Phase 5: Testing & Documentation (Day 5) ✅

#### 5.1 测试清单

**单元测试：**
- [ ] ClickHouse 连接测试
- [ ] 数据聚合查询测试（hourly/daily）
- [ ] 数据格式转换测试
- [ ] 错误处理测试

**集成测试：**
- [ ] Health check 端点
- [ ] K-line 数据查询端点（GET/POST）
- [ ] 与 Kronos API 的完整流程测试

**性能测试：**
- [ ] 查询延迟测试（目标: <100ms for 128 candles）
- [ ] 并发请求测试
- [ ] 大数据量测试（1000+ candles）

#### 5.2 文档

**`README.md`** - 服务文档包括：
- 服务概述
- API 端点文档
- 配置说明
- 部署指南
- 使用示例
- 故障排查

---

## Timeline Summary

| Phase | Tasks | Days | Status |
|-------|-------|------|--------|
| 1 | Directory structure | 0.5 | Pending |
| 2 | Core implementation (config, DB, aggregator, API) | 2.5 | Pending |
| 3 | Docker deployment (Dockerfile, compose, scripts) | 1.0 | Pending |
| 4 | Client integration (ds_request_clickhouse.py) | 1.0 | Pending |
| 5 | Testing & documentation | 1.0 | Pending |
| **Total** | | **6 days** | |

---

## Success Criteria

### Functional Requirements ✅

- [ ] Data API 服务成功启动并响应健康检查
- [ ] 成功连接到 ClickHouse (`192.168.1.110:19999`)
- [ ] 支持 hourly 和 daily K-line 数据查询
- [ ] 返回标准 OHLC 格式数据
- [ ] 客户端成功从 Data API 获取数据
- [ ] Kronos 成功使用真实数据进行预测

### Performance Requirements 📊

- [ ] K-line 查询延迟 < 100ms (128 candles)
- [ ] 支持并发请求（至少 10 QPS）
- [ ] 99% 请求成功率

### Operational Requirements 🔧

- [ ] Docker 容器成功部署
- [ ] 健康检查正常工作
- [ ] 日志记录完整
- [ ] 错误处理健壮

---

## Configuration Reference

### Environment Variables

```bash
# Data API Service
DATA_API_LOG_LEVEL=INFO
DATA_API_CLICKHOUSE_HOST=192.168.1.110
DATA_API_CLICKHOUSE_PORT=19999
DATA_API_CLICKHOUSE_USER=webss
DATA_API_CLICKHOUSE_PASSWORD=webss
DATA_API_CLICKHOUSE_DATABASE=default
DATA_API_API_PORT=8001
DATA_API_API_HOST=0.0.0.0
DATA_API_MAX_CANDLES_PER_REQUEST=10000
DATA_API_DEFAULT_CANDLES_LIMIT=128
```

### Network Topology

```
192.168.1.110 (本机)
├── Port 19999: ClickHouse Database
├── Port 8000:  Kronos FastAPI (Prediction Service)
└── Port 8001:  Data API (K-line Data Service) [新增]

Data Flow:
Client → Data API (8001) → ClickHouse (19999)
Client → Kronos API (8000) [with data from Data API]
```

---

## Next Steps

1. **Review and approve this plan**
2. **Start Phase 1**: Create directory structure
3. **Implement Phase 2**: Core functionality
4. **Deploy Phase 3**: Docker containerization
5. **Test Phase 4**: Integration with Kronos
6. **Document Phase 5**: Complete documentation

---

## Related Tickets

- **TICKET_011_DES** - ClickHouse Data Integration Design (Architecture)
- **TICKET_010_FEA** - Data Stream Client (Client implementation)
- **CLICKHOUSE_AGGREGATE_IMPLEMENTATION.md** - Existing aggregation function reference

---

**准备开始实施吗？**
