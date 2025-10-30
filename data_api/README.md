# Kronos Data API Service

RESTful API for querying K-line (OHLC) data from ClickHouse database.

---

## Overview

This service provides a clean API layer for accessing historical candlestick data stored in ClickHouse. It implements the aggregation logic from `nona_server_06` and exposes it through FastAPI endpoints.

### Key Features

- ✅ **ClickHouse Integration**: Direct connection to ClickHouse database
- ✅ **OHLC Aggregation**: Hourly and daily candlestick data
- ✅ **Trading Day Logic**: Proper 17:00 UTC trading day boundaries
- ✅ **RESTful API**: FastAPI with automatic OpenAPI documentation
- ✅ **Docker Deployment**: Containerized with health checks
- ✅ **Production Ready**: Retry logic, connection pooling, structured logging

---

## Quick Start

### 1. Start the Service

```bash
cd /data/ws/kronos/services/data_api
./start.sh
```

### 2. Check Health

```bash
curl http://localhost:8001/v1/healthz
```

### 3. View API Documentation

Open in browser: http://localhost:8001/docs

---

## API Endpoints

### Health Check

```http
GET /v1/healthz
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-10-30T12:00:00",
  "database_connected": true,
  "version": "1.0.0"
}
```

### Get K-line Data (POST)

```http
POST /v1/kline
Content-Type: application/json

{
  "symbol": "EURUSD",
  "limit": 128,
  "end_time": "2025-10-30T12:00:00",
  "timeframe": "1h"
}
```

**Response:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_time": "2025-10-24T12:00:00+00:00",
  "end_time": "2025-10-30T11:00:00+00:00",
  "count": 128,
  "candles": [
    {
      "timestamp": "2025-10-30T10:00:00+00:00",
      "open": 1.0850,
      "high": 1.0860,
      "low": 1.0845,
      "close": 1.0855,
      "volume": 1500.0,
      "amount": 1628.25
    }
  ]
}
```

### Get K-line Data (GET)

```http
GET /v1/kline/EURUSD?limit=128&timeframe=1h
```

---

## Configuration

### Environment Variables

All configuration can be set via environment variables with `DATA_API_` prefix:

```bash
# ClickHouse Connection
DATA_API_CLICKHOUSE_HOST=192.168.1.110
DATA_API_CLICKHOUSE_PORT=19999
DATA_API_CLICKHOUSE_USER=webss
DATA_API_CLICKHOUSE_PASSWORD=webss
DATA_API_CLICKHOUSE_DATABASE=default

# API Settings
DATA_API_API_PORT=8001
DATA_API_LOG_LEVEL=INFO

# Data Limits
DATA_API_MAX_CANDLES_PER_REQUEST=10000
DATA_API_DEFAULT_CANDLES_LIMIT=128
```

### Configuration File

Create `.env` file in `services/data_api/`:

```bash
DATA_API_CLICKHOUSE_HOST=192.168.1.110
DATA_API_CLICKHOUSE_PORT=19999
DATA_API_LOG_LEVEL=DEBUG
```

---

## Docker Deployment

### Build and Run

```bash
# Start service
./start.sh

# Stop service
./stop.sh

# View logs
docker-compose logs -f

# Restart service
docker-compose restart
```

### Manual Docker Commands

```bash
# Build image
docker-compose build

# Start in foreground
docker-compose up

# Start in background
docker-compose up -d

# Check status
docker-compose ps

# Stop and remove
docker-compose down
```

---

## Development

### Local Development (Without Docker)

```bash
# Install dependencies
cd /data/ws/kronos
pip install -r services/data_api/requirements.txt

# Set environment variables
export DATA_API_CLICKHOUSE_HOST=192.168.1.110
export DATA_API_CLICKHOUSE_PORT=19999
export DATA_API_LOG_LEVEL=DEBUG

# Run service
cd /data/ws/kronos
uvicorn services.data_api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Project Structure

```
services/data_api/
├── __init__.py           # Package initialization
├── main.py               # FastAPI app entry point
├── routes.py             # API route definitions
├── config.py             # Configuration management
├── schemas.py            # Pydantic request/response models
├── database.py           # ClickHouse connection manager
├── aggregator.py         # K-line data aggregation logic
├── logging_utils.py      # Logging configuration
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker orchestration
├── start.sh              # Start script
├── stop.sh               # Stop script
└── README.md             # This file
```

---

## Usage Examples

### Python Client

```python
import requests
from datetime import datetime

# Fetch K-line data
response = requests.post(
    "http://localhost:8001/v1/kline",
    json={
        "symbol": "EURUSD",
        "limit": 128,
        "timeframe": "1h"
    }
)

data = response.json()
print(f"Retrieved {data['count']} candles")

# Convert to format for Kronos
candles = []
timestamps = []

for candle in data['candles']:
    candles.append({
        'open': candle['open'],
        'high': candle['high'],
        'low': candle['low'],
        'close': candle['close'],
        'volume': candle['volume'],
        'amount': candle['amount']
    })
    timestamps.append(datetime.fromisoformat(candle['timestamp']))
```

### cURL Examples

```bash
# Health check
curl http://localhost:8001/v1/healthz

# Get hourly data
curl -X POST http://localhost:8001/v1/kline \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "limit": 128,
    "timeframe": "1h"
  }'

# Get daily data via GET
curl "http://localhost:8001/v1/kline/EURUSD?limit=30&timeframe=1d"
```

---

## Integration with Kronos

### Complete Workflow

```python
from datetime import datetime, timedelta
import requests
from examples.ds_request import KronosClient

# 1. Fetch data from Data API
data_response = requests.post(
    "http://localhost:8001/v1/kline",
    json={
        "symbol": "EURUSD",
        "limit": 128,
        "timeframe": "1h"
    }
)

data = data_response.json()

# 2. Convert to Kronos format
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
    datetime.fromisoformat(c['timestamp'])
    for c in data['candles']
]

# 3. Predict with Kronos
kronos_client = KronosClient(base_url="http://localhost:8000")
prediction_timestamp = timestamps[-1] + timedelta(hours=1)

prediction = kronos_client.predict_single(
    candles=candles,
    timestamps=timestamps,
    prediction_timestamp=prediction_timestamp,
    series_id="EURUSD",
    verbose=True
)

print(f"Predicted close: {prediction['close']:.5f}")
```

---

## Performance

### Typical Latency

- **128 candles (hourly)**: ~50-100ms
- **365 candles (daily)**: ~30-80ms
- **Network overhead**: ~10-20ms

### Optimization

- ClickHouse queries use CTEs for optimization
- Data is partitioned by month
- Primary key on (currency_pair, timestamp)
- Connection pooling reduces overhead

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs

# Check if port 8001 is in use
lsof -i :8001

# Check network
docker network inspect kronos-network
```

### Database Connection Failed

```bash
# Test ClickHouse connection
docker exec -it kronos-data-api curl http://192.168.1.110:19999

# Check environment variables
docker exec -it kronos-data-api env | grep DATA_API

# Restart with fresh logs
docker-compose down && docker-compose up
```

### No Data Returned

```bash
# Check if data exists in ClickHouse
# (requires ClickHouse client)

# Verify symbol name matches database
# Check timeframe parameter ('1h' or '1d')
# Adjust start/end time range
```

---

## Related Documentation

- **TICKET_011_DES**: ClickHouse Data Integration Design
- **TICKET_012_TSK**: Data API Implementation Plan
- **CLICKHOUSE_AGGREGATE_IMPLEMENTATION.md**: Aggregation function reference
- **TICKET_010_FEA**: Data Stream Client documentation

---

## API Schema

Full API schema available at:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **OpenAPI JSON**: http://localhost:8001/openapi.json

---

## Version

**Current Version**: 1.0.0

## License

Part of the Kronos project.
