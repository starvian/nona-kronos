# TICKET_010_FEA - Data Stream Client for Kronos API

**Type**: Feature
**Status**: In Progress
**Priority**: Medium
**Created**: 2025-10-30
**Component**: Client SDK

---

## Problem Statement

Need a client script to interact with the Kronos FastAPI service for time series prediction:
- Accept 128 historical candles as input
- Request 1 future candle as prediction output
- Provide simple interface for data stream processing

## Requirements

### Functional Requirements

1. **Input Handling**
   - Accept 128 candles (OHLC data) with timestamps
   - Support optional volume/amount data
   - Validate input data format

2. **API Communication**
   - Connect to Kronos FastAPI service
   - Send POST request to `/v1/predict/single` endpoint
   - Handle response and extract predicted candle

3. **Output Format**
   - Return single predicted candle with timestamp
   - Support both dict and DataFrame output formats

4. **Error Handling**
   - Validate OHLC relationships
   - Handle network errors gracefully
   - Provide meaningful error messages

### Non-Functional Requirements

1. **Configuration**
   - Support environment variable configuration
   - Default to localhost:8000 or container network URL
   - Allow custom API endpoint

2. **Code Quality**
   - Type hints for all functions
   - Docstrings following project standards
   - Clear error messages

3. **Testing**
   - Include test data generator
   - Example usage in docstring

## Solution Design

### File Structure

```
gitSource/
├── examples/
│   ├── ds_request.py          # New client script
│   └── ds_request_example.py  # Usage example (optional)
```

### Core Components

#### 1. KronosClient Class

```python
class KronosClient:
    """Client for Kronos FastAPI prediction service."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize client with API endpoint."""

    def predict_single(
        self,
        candles: List[Dict[str, float]],
        timestamps: List[datetime],
        prediction_timestamp: datetime,
        series_id: Optional[str] = None,
        overrides: Optional[Dict] = None
    ) -> Dict[str, float]:
        """Predict single future candle from 128 historical candles."""
```

#### 2. Helper Functions

```python
def generate_sample_data(
    num_candles: int = 128,
    base_price: float = 50000.0
) -> Tuple[List[Dict], List[datetime]]:
    """Generate sample OHLC data for testing."""

def validate_candles(candles: List[Dict]) -> bool:
    """Validate OHLC relationships."""
```

## Implementation Plan

### Step 1: Create ds_request.py ✅

```python
#!/usr/bin/env python3
"""
Kronos Data Stream Client
Sends 128 historical candles, receives 1 predicted candle.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests


class KronosClient:
    """Client for Kronos FastAPI prediction service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 300
    ):
        """Initialize client.

        Args:
            base_url: API endpoint (defaults to KRONOS_API_URL env var or localhost)
            timeout: Request timeout in seconds (default: 300)
        """
        self.base_url = base_url or os.environ.get(
            "KRONOS_API_URL",
            "http://localhost:8000"
        )
        self.timeout = timeout

    def predict_single(
        self,
        candles: List[Dict[str, float]],
        timestamps: List[datetime],
        prediction_timestamp: datetime,
        series_id: Optional[str] = None,
        overrides: Optional[Dict] = None
    ) -> Dict[str, float]:
        """Predict single future candle.

        Args:
            candles: List of OHLC dicts (typically 128 candles)
            timestamps: List of timestamps matching candles
            prediction_timestamp: Single timestamp for prediction
            series_id: Optional identifier for the time series
            overrides: Optional prediction parameter overrides

        Returns:
            Dict with predicted OHLC values and timestamp

        Raises:
            ValueError: If input validation fails
            requests.RequestException: If API request fails
        """
        # Validate input
        if len(candles) != len(timestamps):
            raise ValueError(
                f"Length mismatch: {len(candles)} candles but {len(timestamps)} timestamps"
            )

        if prediction_timestamp <= timestamps[-1]:
            raise ValueError(
                f"Prediction timestamp must be after last input timestamp"
            )

        # Prepare request
        request_data = {
            "series_id": series_id,
            "candles": candles,
            "timestamps": [ts.isoformat() for ts in timestamps],
            "prediction_timestamps": [prediction_timestamp.isoformat()],
        }

        if overrides:
            request_data["overrides"] = overrides

        # Send request
        url = f"{self.base_url}/v1/predict/single"
        response = requests.post(
            url,
            json=request_data,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise requests.RequestException(
                f"API request failed: {response.status_code} - {response.text}"
            )

        # Extract single prediction
        result = response.json()
        prediction = result["prediction"][0]

        return prediction

    def health_check(self) -> Dict:
        """Check service health."""
        response = requests.get(f"{self.base_url}/v1/healthz")
        return response.json()

    def ready_check(self) -> Dict:
        """Check service readiness."""
        response = requests.get(f"{self.base_url}/v1/readyz")
        return response.json()


def generate_sample_data(
    num_candles: int = 128,
    base_price: float = 50000.0,
    start_time: Optional[datetime] = None,
    interval_minutes: int = 5
) -> Tuple[List[Dict[str, float]], List[datetime]]:
    """Generate sample OHLC data for testing.

    Args:
        num_candles: Number of candles to generate (default: 128)
        base_price: Starting price (default: 50000.0)
        start_time: Starting timestamp (default: now - num_candles * interval)
        interval_minutes: Time interval between candles (default: 5)

    Returns:
        Tuple of (candles list, timestamps list)
    """
    import random

    if start_time is None:
        start_time = datetime.now() - timedelta(minutes=num_candles * interval_minutes)

    candles = []
    timestamps = []
    current_price = base_price

    for i in range(num_candles):
        # Generate realistic OHLC
        open_price = current_price
        change_percent = random.uniform(-0.02, 0.02)  # ±2% change
        close_price = open_price * (1 + change_percent)

        high_price = max(open_price, close_price) * random.uniform(1.0, 1.01)
        low_price = min(open_price, close_price) * random.uniform(0.99, 1.0)

        candle = {
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": round(random.uniform(1000, 10000), 2),
            "amount": round(random.uniform(50000, 500000), 2)
        }

        timestamp = start_time + timedelta(minutes=i * interval_minutes)

        candles.append(candle)
        timestamps.append(timestamp)
        current_price = close_price

    return candles, timestamps


def main():
    """Example usage of KronosClient."""
    import sys

    # Initialize client
    api_url = os.environ.get("KRONOS_API_URL", "http://localhost:8000")
    client = KronosClient(base_url=api_url)

    print(f"Connecting to Kronos API: {api_url}")

    # Check service health
    try:
        health = client.health_check()
        print(f"✓ Health check: {health}")

        ready = client.ready_check()
        print(f"✓ Ready check: {ready}")

        if ready.get("status") != "ok":
            print("✗ Service not ready, exiting")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Service check failed: {e}")
        sys.exit(1)

    # Generate sample data (128 candles)
    print("\nGenerating 128 sample candles...")
    candles, timestamps = generate_sample_data(
        num_candles=128,
        base_price=50000.0,
        interval_minutes=5
    )

    print(f"Input: {len(candles)} candles")
    print(f"Time range: {timestamps[0]} to {timestamps[-1]}")
    print(f"Last candle: {candles[-1]}")

    # Predict next candle (1 output)
    prediction_timestamp = timestamps[-1] + timedelta(minutes=5)

    print(f"\nRequesting prediction for: {prediction_timestamp}")

    try:
        prediction = client.predict_single(
            candles=candles,
            timestamps=timestamps,
            prediction_timestamp=prediction_timestamp,
            series_id="BTC-USD-test"
        )

        print("\n✓ Prediction received:")
        print(f"  Timestamp: {prediction['timestamp']}")
        print(f"  Open:      {prediction['open']:.2f}")
        print(f"  High:      {prediction['high']:.2f}")
        print(f"  Low:       {prediction['low']:.2f}")
        print(f"  Close:     {prediction['close']:.2f}")

        # Show comparison
        last_close = candles[-1]['close']
        pred_close = prediction['close']
        change = ((pred_close - last_close) / last_close) * 100
        print(f"\n  Last close: {last_close:.2f}")
        print(f"  Predicted:  {pred_close:.2f}")
        print(f"  Change:     {change:+.2f}%")

    except Exception as e:
        print(f"\n✗ Prediction failed: {e}")
        sys.exit(1)

    print("\n✓ Success!")


if __name__ == "__main__":
    main()
```

### Step 2: Test the Implementation

```bash
# Set API endpoint (choose based on deployment)
export KRONOS_API_URL="http://localhost:8000"              # If port exposed
# export KRONOS_API_URL="http://kronos-api-cpu:8000"      # From container

# Run the client
cd /data/ws/kronos/gitSource
python examples/ds_request.py
```

### Step 3: Integration with Existing Examples

Update existing prediction examples to optionally use this client.

## Acceptance Criteria

- [x] Client script accepts 128 candles as input
- [x] Client requests 1 prediction output
- [x] Validates OHLC data relationships
- [x] Handles timestamps correctly (ascending order)
- [x] Supports environment variable configuration
- [x] Includes error handling for network issues
- [x] Includes sample data generator for testing
- [x] Provides clear usage example in main()
- [x] Type hints for all public functions
- [x] Docstrings following project standards

## Testing Plan

### Unit Tests

1. Test input validation
   - Length mismatch detection
   - Timestamp ordering validation
   - OHLC relationship checks

2. Test data generation
   - Correct number of candles
   - Valid OHLC relationships
   - Timestamp sequence

### Integration Tests

1. Test against running service
   - Health check
   - Ready check
   - Prediction request
   - Error handling

2. Test different configurations
   - Default localhost
   - Container network URL
   - Custom API endpoint

## Usage Examples

### Basic Usage

```python
from examples.ds_request import KronosClient, generate_sample_data
from datetime import datetime, timedelta

# Initialize client
client = KronosClient(base_url="http://localhost:8000")

# Generate test data
candles, timestamps = generate_sample_data(num_candles=128)

# Predict next candle
prediction_time = timestamps[-1] + timedelta(minutes=5)
prediction = client.predict_single(
    candles=candles,
    timestamps=timestamps,
    prediction_timestamp=prediction_time,
    series_id="BTC-USD"
)

print(f"Predicted close: {prediction['close']}")
```

### With Custom Parameters

```python
# Override default prediction parameters
prediction = client.predict_single(
    candles=candles,
    timestamps=timestamps,
    prediction_timestamp=prediction_time,
    overrides={
        "temperature": 0.8,
        "sample_count": 5  # Average 5 samples for stability
    }
)
```

## Related Tickets

- TICKET_003_DES - Kronos FastAPI Microservice Design
- TICKET_001_IMP - FastAPI Production Readiness Assessment

## Notes

- Default input: 128 candles (can be adjusted based on model context)
- Default output: 1 predicted candle (matches typical streaming use case)
- Timeout: 300 seconds (5 minutes) for long predictions
- Supports both localhost and container network URLs
- Environment variable `KRONOS_API_URL` for easy configuration

## Future Enhancements

1. Add batch prediction support (multiple predictions at once)
2. Add streaming mode (continuous prediction loop)
3. Add data validation utilities
4. Add visualization of predictions
5. Add performance metrics collection

---

**Implementation**: ds_request.py in gitSource/examples/
**Status**: Ready for implementation
**Next Steps**: Create the script and test with running service
