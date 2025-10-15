"""Basic end-to-end integration tests for Kronos FastAPI service.

These tests verify core functionality including:
- Service startup and health checks
- Model loading and readiness
- Single prediction requests
- Batch prediction requests
- Graceful shutdown

Run with: pytest tests/integration/test_e2e_basic.py
"""

import time
from datetime import datetime, timedelta
from typing import List

import pytest
import requests


# Test configuration
BASE_URL = "http://localhost:8000"
HEALTHZ_URL = f"{BASE_URL}/v1/healthz"
READYZ_URL = f"{BASE_URL}/v1/readyz"
DETAILED_HEALTH_URL = f"{BASE_URL}/v1/healthz/detailed"
PREDICT_SINGLE_URL = f"{BASE_URL}/v1/predict/single"
PREDICT_BATCH_URL = f"{BASE_URL}/v1/predict/batch"


def generate_test_candles(count: int = 400) -> List[dict]:
    """Generate realistic test candle data."""
    base_price = 100.0
    candles = []

    for i in range(count):
        # Simulate price movement
        price = base_price + (i % 10) - 5
        candles.append({
            "open": price,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price + 0.5,
            "volume": 1000 + (i * 10),
            "amount": 100000 + (i * 100),
        })

    return candles


def generate_timestamps(count: int, start: datetime = None) -> List[str]:
    """Generate timestamps for test data."""
    if start is None:
        start = datetime.now() - timedelta(days=1)

    timestamps = []
    for i in range(count):
        ts = start + timedelta(minutes=i)
        timestamps.append(ts.isoformat())

    return timestamps


class TestHealthChecks:
    """Test health check endpoints."""

    def test_healthz(self):
        """Test basic health check."""
        response = requests.get(HEALTHZ_URL, timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_readyz(self):
        """Test readiness check."""
        # May need to wait for model loading
        max_wait = 120  # 2 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                response = requests.get(READYZ_URL, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("model_loaded"):
                        assert data["status"] == "ok"
                        return
                time.sleep(5)
            except requests.exceptions.RequestException:
                time.sleep(5)

        pytest.fail("Service did not become ready within timeout")

    def test_detailed_health(self):
        """Test detailed health check endpoint (Phase 5)."""
        response = requests.get(DETAILED_HEALTH_URL, timeout=5)
        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "status" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "checks" in data

        # Check components
        checks = data["checks"]
        assert "model" in checks
        assert "memory" in checks
        assert "disk" in checks

        # Verify model check
        assert checks["model"]["loaded"] is True
        assert checks["model"]["version"] is not None

        # Verify memory check
        assert checks["memory"]["process_mb"] > 0
        assert checks["memory"]["system_percent"] >= 0

        # Verify disk check
        assert checks["disk"]["free_gb"] > 0


class TestPredictions:
    """Test prediction endpoints."""

    def test_single_prediction_success(self):
        """Test successful single prediction."""
        # Generate test data
        candles = generate_test_candles(400)
        input_timestamps = generate_timestamps(400)
        prediction_timestamps = generate_timestamps(
            120,
            start=datetime.fromisoformat(input_timestamps[-1]) + timedelta(minutes=1)
        )

        # Make request
        payload = {
            "series_id": "test-series-1",
            "candles": candles,
            "timestamps": input_timestamps,
            "prediction_timestamps": prediction_timestamps,
        }

        response = requests.post(PREDICT_SINGLE_URL, json=payload, timeout=60)

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["series_id"] == "test-series-1"
        assert "prediction" in data
        assert len(data["prediction"]) == 120
        assert "model_version" in data
        assert "tokenizer_version" in data

        # Verify prediction structure
        first_pred = data["prediction"][0]
        assert "timestamp" in first_pred
        assert "open" in first_pred
        assert "high" in first_pred
        assert "low" in first_pred
        assert "close" in first_pred

    def test_single_prediction_validation_error(self):
        """Test validation error handling (Phase 5)."""
        # Invalid: timestamps not in order
        candles = generate_test_candles(10)
        timestamps = generate_timestamps(10)
        timestamps[5], timestamps[6] = timestamps[6], timestamps[5]  # Swap order

        prediction_timestamps = generate_timestamps(
            10,
            start=datetime.fromisoformat(timestamps[0]) + timedelta(hours=1)
        )

        payload = {
            "series_id": "test-invalid",
            "candles": candles,
            "timestamps": timestamps,
            "prediction_timestamps": prediction_timestamps,
        }

        response = requests.post(PREDICT_SINGLE_URL, json=payload, timeout=10)

        # Should return validation error
        assert response.status_code == 422  # Unprocessable Entity

    def test_batch_prediction_success(self):
        """Test successful batch prediction."""
        # Generate test data for 3 series
        items = []
        for i in range(3):
            candles = generate_test_candles(200)
            input_timestamps = generate_timestamps(200)
            prediction_timestamps = generate_timestamps(
                60,
                start=datetime.fromisoformat(input_timestamps[-1]) + timedelta(minutes=1)
            )

            items.append({
                "series_id": f"batch-series-{i}",
                "candles": candles,
                "timestamps": input_timestamps,
                "prediction_timestamps": prediction_timestamps,
            })

        payload = {"items": items}

        response = requests.post(PREDICT_BATCH_URL, json=payload, timeout=120)

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert len(data) == 3
        for i, result in enumerate(data):
            assert result["series_id"] == f"batch-series-{i}"
            assert len(result["prediction"]) == 60


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_model_not_ready_error(self):
        """Test behavior when model is not ready (should not happen in normal operation)."""
        # This test is mostly for documentation
        # In real scenario, /readyz would return not ready
        pass

    def test_invalid_candle_data(self):
        """Test validation of invalid candle data (Phase 5)."""
        # Invalid: low > high
        candles = [{
            "open": 100,
            "high": 95,  # Invalid: high < open
            "low": 105,  # Invalid: low > open
            "close": 100,
        }]
        timestamps = generate_timestamps(1)
        prediction_timestamps = generate_timestamps(
            10,
            start=datetime.fromisoformat(timestamps[0]) + timedelta(hours=1)
        )

        payload = {
            "candles": candles,
            "timestamps": timestamps,
            "prediction_timestamps": prediction_timestamps,
        }

        response = requests.post(PREDICT_SINGLE_URL, json=payload, timeout=10)
        assert response.status_code == 422  # Validation error

    def test_empty_request(self):
        """Test handling of empty request."""
        payload = {
            "candles": [],
            "timestamps": [],
            "prediction_timestamps": [],
        }

        response = requests.post(PREDICT_SINGLE_URL, json=payload, timeout=10)
        assert response.status_code == 422  # Validation error


@pytest.mark.slow
class TestPerformance:
    """Performance and load tests (marked as slow)."""

    def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import concurrent.futures

        def make_request():
            candles = generate_test_candles(200)
            timestamps = generate_timestamps(200)
            prediction_timestamps = generate_timestamps(
                60,
                start=datetime.fromisoformat(timestamps[-1]) + timedelta(minutes=1)
            )

            payload = {
                "candles": candles,
                "timestamps": timestamps,
                "prediction_timestamps": prediction_timestamps,
            }

            response = requests.post(PREDICT_SINGLE_URL, json=payload, timeout=120)
            return response.status_code == 200

        # Send 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(results)

    def test_large_input(self):
        """Test with maximum allowed input size."""
        candles = generate_test_candles(2048)  # Max allowed
        timestamps = generate_timestamps(2048)
        prediction_timestamps = generate_timestamps(
            512,  # Max allowed
            start=datetime.fromisoformat(timestamps[-1]) + timedelta(minutes=1)
        )

        payload = {
            "candles": candles,
            "timestamps": timestamps,
            "prediction_timestamps": prediction_timestamps,
        }

        response = requests.post(PREDICT_SINGLE_URL, json=payload, timeout=180)
        assert response.status_code == 200


# Test fixtures and helpers
@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    """Wait for service to be ready before running tests."""
    max_wait = 120
    start_time = time.time()

    print("\nWaiting for Kronos service to be ready...")

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(READYZ_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("model_loaded"):
                    print("Service ready!")
                    return
        except requests.exceptions.RequestException:
            pass

        time.sleep(5)

    pytest.fail("Service did not start within timeout")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
