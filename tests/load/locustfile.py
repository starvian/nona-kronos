"""Load testing for Kronos FastAPI service using Locust.

Usage:
    # Install locust
    pip install locust

    # Run with web UI
    locust -f locustfile.py --host=http://localhost:8000

    # Run headless
    locust -f locustfile.py --host=http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 5m --headless

Test Scenarios:
    - Steady state: 10 users, 5 minutes
    - Stress test: Ramp up to 100 users
    - Spike test: 10 → 100 → 10 users
"""

import random
import json
from datetime import datetime, timedelta
from typing import List

from locust import HttpUser, task, between, events


class KronosLoadTest(HttpUser):
    """Load test for Kronos prediction endpoints."""

    wait_time = between(0.5, 2.0)  # Wait 0.5-2s between requests

    def on_start(self):
        """Setup test data when user starts."""
        # Generate realistic test data
        self.candles = self._generate_candles(400)
        self.timestamps = [c['timestamp'] for c in self.candles]
        self.pred_timestamps = self._generate_pred_timestamps(120)

        # Test with different series IDs
        self.series_counter = 0

    @task(3)  # 3x weight - most common endpoint
    def predict_single(self):
        """Test single prediction endpoint."""
        self.series_counter += 1

        payload = {
            "series_id": f"test-series-{self.series_counter}",
            "candles": self.candles,
            "timestamps": self.timestamps,
            "prediction_timestamps": self.pred_timestamps,
        }

        with self.client.post(
            "/v1/predict/single",
            json=payload,
            catch_response=True,
            name="/v1/predict/single"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 504:
                response.failure("Timeout - prediction took too long")
            elif response.status_code == 503:
                response.failure("Service unavailable - model not ready")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(1)  # 1x weight - less common
    def predict_batch(self):
        """Test batch prediction endpoint."""
        batch_size = random.randint(2, 5)  # 2-5 series per batch

        payload = {
            "items": [
                {
                    "series_id": f"batch-{self.series_counter}-{i}",
                    "candles": self.candles,
                    "timestamps": self.timestamps,
                    "prediction_timestamps": self.pred_timestamps,
                }
                for i in range(batch_size)
            ]
        }

        with self.client.post(
            "/v1/predict/batch",
            json=payload,
            catch_response=True,
            name="/v1/predict/batch"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 504:
                response.failure("Timeout")
            elif response.status_code == 503:
                response.failure("Service unavailable")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(0.5)  # 0.5x weight - occasional health checks
    def health_check(self):
        """Test health check endpoint."""
        with self.client.get(
            "/v1/healthz",
            catch_response=True,
            name="/v1/healthz"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(0.5)  # 0.5x weight - occasional readiness checks
    def ready_check(self):
        """Test readiness check endpoint."""
        with self.client.get(
            "/v1/readyz",
            catch_response=True,
            name="/v1/readyz"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("model_loaded"):
                    response.success()
                else:
                    response.failure("Model not loaded")
            else:
                response.failure(f"Readiness check failed: {response.status_code}")

    def _generate_candles(self, count: int) -> List[dict]:
        """Generate realistic fake candle data.

        Args:
            count: Number of candles to generate

        Returns:
            List of candle dictionaries
        """
        base_time = datetime.now() - timedelta(minutes=count)
        candles = []
        price = 100.0 + random.uniform(-10, 10)  # Starting price around 100

        for i in range(count):
            # Simulate price movement with random walk
            price_change = random.uniform(-2, 2)
            price += price_change

            # Ensure realistic OHLC relationships
            open_price = price
            high_price = price + random.uniform(0, abs(price_change) + 0.5)
            low_price = price - random.uniform(0, abs(price_change) + 0.5)
            close_price = price + price_change

            candles.append({
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": random.randint(1000, 50000),
                "amount": random.randint(100000, 5000000),
            })

        return candles

    def _generate_pred_timestamps(self, count: int) -> List[str]:
        """Generate prediction timestamps.

        Args:
            count: Number of prediction timestamps

        Returns:
            List of ISO format timestamp strings
        """
        base_time = datetime.now()
        return [
            (base_time + timedelta(minutes=i)).isoformat()
            for i in range(count)
        ]


# Event hooks for custom logging
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print test configuration when test starts."""
    print("\n" + "="*60)
    print("Starting Kronos FastAPI Load Test")
    print("="*60)
    print(f"Host: {environment.host}")
    print(f"Users: {environment.parsed_options.num_users if hasattr(environment, 'parsed_options') else 'N/A'}")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary when test stops."""
    print("\n" + "="*60)
    print("Load Test Complete")
    print("="*60)
    print("Check Locust web UI for detailed results")
    print("="*60 + "\n")


# Custom user class for specific scenarios
class SteadyStateUser(HttpUser):
    """User for steady state testing - consistent load."""
    wait_time = between(1.0, 2.0)  # Consistent 1-2s wait
    tasks = [KronosLoadTest.predict_single]


class SpikeUser(HttpUser):
    """User for spike testing - burst traffic."""
    wait_time = between(0.1, 0.5)  # Very short wait - aggressive
    tasks = [KronosLoadTest.predict_single]


class EnduranceUser(HttpUser):
    """User for endurance testing - long duration."""
    wait_time = between(2.0, 5.0)  # Longer wait - sustained load
    tasks = [KronosLoadTest.predict_single, KronosLoadTest.predict_batch]
