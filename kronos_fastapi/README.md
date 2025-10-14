# Kronos FastAPI Service

Production-ready FastAPI microservice for Kronos financial time series prediction.

## Quick Start

### Start the service

```bash
# From the kronos_fastapi directory
./start.sh [PORT] [HOST] [WORKERS]

# Examples:
./start.sh                    # Default: port 8000, host 0.0.0.0, 1 worker (dev mode with reload)
./start.sh 28888              # Custom port with auto-reload
./start.sh 8000 0.0.0.0 4     # Production mode with 4 workers (no reload)
```

### Stop the service

```bash
# From the kronos_fastapi directory
./stop.sh [PORT]

# Examples:
./stop.sh           # Stop service on default port 8000
./stop.sh 28888     # Stop service on port 28888
```

### Manual start (alternative)

```bash
# From gitSource/ directory (IMPORTANT!)
cd /path/to/gitSource
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

## Configuration

Set environment variables to customize the service:

```bash
export KRONOS_MODEL_ID="NeoQuasar/Kronos-small"           # Hugging Face model ID
export KRONOS_TOKENIZER_ID="NeoQuasar/Kronos-Tokenizer-base"  # HF tokenizer ID
export KRONOS_MODEL_PATH="/data/ws/kronos/models"        # Local model path
export KRONOS_DEVICE="cuda:0"                             # Device: cpu, cuda:0, mps
export KRONOS_LOG_LEVEL="INFO"                            # Logging level
export KRONOS_MAX_CONTEXT=512                             # Max context length
export KRONOS_DEFAULT_PRED_LEN=120                        # Default prediction length
export KRONOS_DEFAULT_TEMPERATURE=1.0                     # Default temperature
export KRONOS_DEFAULT_TOP_P=0.9                           # Default nucleus sampling
```

See `config.py` for all available configuration options.

## API Endpoints

Once running, the service provides:

- **`GET /`** - Service information
- **`GET /v1/healthz`** - Health check (liveness probe)
- **`GET /v1/readyz`** - Readiness check (includes model loaded status)
- **`POST /v1/predict/single`** - Single time series prediction
- **`POST /v1/predict/batch`** - Batch predictions for multiple time series
- **`GET /v1/metrics`** - Prometheus metrics
- **`GET /docs`** - Interactive API documentation (Swagger UI)
- **`GET /redoc`** - Alternative API documentation (ReDoc)

## Testing the service

```bash
# Health check
curl http://localhost:8000/v1/healthz

# Readiness check
curl http://localhost:8000/v1/readyz

# Example prediction request (replace with your data)
curl -X POST "http://localhost:8000/v1/predict/single" \
  -H "Content-Type: application/json" \
  -d '{
    "series_id": "test-001",
    "candles": [
      {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000.0}
    ],
    "timestamps": ["2024-01-01T00:00:00"],
    "prediction_timestamps": ["2024-01-01T01:00:00"]
  }'
```

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Required packages:
- fastapi>=0.111.0
- uvicorn[standard]>=0.30.0
- pydantic>=2.0.0
- pydantic-settings>=2.0.0
- prometheus-client>=0.20.0

Also requires the core Kronos dependencies from `gitSource/requirements.txt`.

## Architecture

- **`main.py`** - FastAPI app initialization and startup logic
- **`routes.py`** - API endpoint definitions
- **`predictor.py`** - Model management and prediction logic
- **`config.py`** - Configuration management via Pydantic Settings
- **`schemas.py`** - Request/response models
- **`middleware.py`** - Request ID tracking middleware
- **`metrics.py`** - Prometheus metrics integration
- **`logging_utils.py`** - Structured logging configuration

## Production Deployment

For production deployments:

1. **Use multiple workers** for better performance:
   ```bash
   ./start.sh 8000 0.0.0.0 4  # 4 workers
   ```

2. **Set appropriate environment variables**:
   ```bash
   export KRONOS_DEVICE="cuda:0"  # Use GPU
   export KRONOS_LOG_LEVEL="WARNING"  # Reduce logging
   ```

3. **Use a process manager** like systemd or supervisord

4. **Put behind a reverse proxy** (nginx, traefik) for:
   - SSL/TLS termination
   - Load balancing
   - Rate limiting

5. **Monitor metrics** via the `/v1/metrics` endpoint

## Troubleshooting

### Port already in use
```bash
./stop.sh 8000  # Stop service on port 8000
# Or manually find and kill:
lsof -ti:8000 | xargs kill -9
```

### Module not found errors
Make sure to run from the `gitSource/` directory, not from `services/kronos_fastapi/`.

### Model loading issues
- Verify `KRONOS_MODEL_PATH` points to valid model directory
- Or set `KRONOS_MODEL_ID` to use Hugging Face models
- Check that tokenizer is available at the specified path

### Out of memory
- Use CPU instead of GPU: `export KRONOS_DEVICE="cpu"`
- Reduce batch size in prediction requests
- Use a smaller model variant (Kronos-mini or Kronos-small)

## Development

Run with auto-reload for development:
```bash
./start.sh 8000  # Single worker with reload enabled
```

Access interactive API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

This service follows the same MIT License as the main Kronos project.
