# Nona-Kronos: Production FastAPI Microservice for Kronos

Production-ready FastAPI microservice for Kronos financial time series prediction model, designed for Docker-based internal deployment.

## Overview

This service wraps the [Kronos](https://github.com/shiyu-coder/Kronos) foundation model in a production-ready API with:
- Docker containerization
- Internal network security
- Rate limiting and container whitelisting
- Prometheus metrics
- Health checks
- Graceful shutdown

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Kronos model files (local or from Hugging Face)

### Development Mode

```bash
cd kronos_fastapi
docker-compose -f docker-compose.dev.yml up
```

Service available at: http://localhost:8000

### Production Mode

```bash
cd kronos_fastapi
docker-compose up -d
```

Service accessible only from internal Docker network.

## Project Structure

```
services/
└── kronos_fastapi/          # FastAPI microservice
    ├── Dockerfile            # Multi-stage production build
    ├── docker-compose.yml    # Production configuration
    ├── docker-compose.dev.yml # Development with hot-reload
    ├── .dockerignore         # Build optimization
    ├── .env.example          # Configuration template
    ├── build.sh              # Build script
    ├── start.sh              # Start script
    ├── stop.sh               # Stop script
    ├── main.py               # FastAPI app
    ├── routes.py             # API endpoints
    ├── predictor.py          # Model manager
    ├── config.py             # Configuration
    ├── schemas.py            # Request/response models
    ├── middleware.py         # Request tracking
    ├── metrics.py            # Prometheus metrics
    ├── logging_utils.py      # Structured logging
    └── README.md             # Detailed documentation
```

## Features

### Security (Internal Docker Network)
- ✅ Network isolation (Docker internal network)
- ✅ Container whitelist middleware
- ✅ Rate limiting (per container)
- ✅ Request size limits
- ✅ Non-root container user
- ❌ No API key authentication (not needed for trusted internal network)

### Performance
- Async-ready architecture
- Batch prediction support
- Resource limits (CPU, memory)
- Health checks

### Observability
- Structured JSON logging
- Prometheus metrics
- Request ID tracking
- Health and readiness endpoints

## API Endpoints

- `GET /` - Service information
- `GET /v1/healthz` - Health check (liveness)
- `GET /v1/readyz` - Readiness check (model loaded)
- `POST /v1/predict/single` - Single time series prediction
- `POST /v1/predict/batch` - Batch predictions
- `GET /v1/metrics` - Prometheus metrics
- `GET /docs` - Interactive API documentation

## Configuration

Set environment variables in `.env` file (see `.env.example`):

```bash
# Model configuration
KRONOS_MODEL_PATH=/models
KRONOS_DEVICE=cpu

# Inference parameters
KRONOS_MAX_CONTEXT=512
KRONOS_DEFAULT_PRED_LEN=120
KRONOS_DEFAULT_TEMPERATURE=1.0
KRONOS_DEFAULT_TOP_P=0.9

# See .env.example for all options
```

## Development

### Building

```bash
cd kronos_fastapi
./build.sh
```

### Running Tests

```bash
# Start test environment
docker-compose -f docker-compose.dev.yml --profile testing up

# Run tests from test-consumer container
docker exec test-consumer curl http://kronos-api-dev:8000/v1/healthz
```

### Hot Reload

Development mode includes hot-reload:

```bash
docker-compose -f docker-compose.dev.yml up
# Edit code - service auto-reloads
```

## Deployment

See [kronos_fastapi/README.md](kronos_fastapi/README.md) for detailed deployment instructions.

### Production Deployment Checklist

- [ ] Set environment variables in `.env`
- [ ] Mount model files as volume
- [ ] Configure container whitelist
- [ ] Set up Prometheus monitoring
- [ ] Configure resource limits
- [ ] Test health checks
- [ ] Review security settings

## Architecture

```
Docker Host
├── kronos-internal (network)
│   ├── kronos-api (this service)
│   ├── frontend-app
│   ├── worker-service
│   └── scheduler
└── monitoring (separate network)
    ├── prometheus
    └── grafana
```

## Roadmap

See [tickets/TICKET_002_PLN_Productionization-Roadmap.md](tickets/TICKET_002_PLN_Productionization-Roadmap.md)

- [x] Phase 1: Dockerization
- [ ] Phase 2: Security middleware
- [ ] Phase 3: Performance optimization
- [ ] Phase 4: Enhanced observability
- [ ] Phase 5: Production hardening
- [ ] Phase 6: Documentation

## Contributing

This is a production service for internal use. For issues or improvements, please open an issue.

## License

MIT License - Same as original Kronos project

## Related Projects

- [Kronos](https://github.com/shiyu-coder/Kronos) - Original foundation model
- [starvian/Kronos](https://github.com/starvian/Kronos) - Fork with modifications

## Support

For questions or issues:
1. Check [kronos_fastapi/README.md](kronos_fastapi/README.md)
2. Review logs: `docker-compose logs kronos-api`
3. Check health: `curl http://localhost:8000/v1/healthz`
4. Open an issue on GitHub

---

**Status:** Phase 1 Complete (Dockerization) ✅
**Next:** Phase 2 - Security Implementation
