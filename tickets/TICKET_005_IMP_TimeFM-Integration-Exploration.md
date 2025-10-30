# TICKET_005_IMP - TimeFM Integration Exploration

**Status**: Created
**Created**: 2025-10-24
**Type**: Improvement (Analysis and Exploration)
**Priority**: Medium

---

## Problem Statement

Kronos is a specialized foundation model for financial K-line (candlestick) forecasting trained on 45+ global exchanges. However, exploring complementary time series forecasting approaches could enhance model diversity and provide:

1. **Alternative approaches**: TimeFM offers a different architectural paradigm (likely based on different tokenization/prediction mechanisms)
2. **Ensemble opportunities**: Combining Kronos and TimeFM predictions could improve robustness
3. **Performance benchmarking**: Comparative analysis of different SOTM approaches for financial forecasting
4. **Production flexibility**: Multiple models for different use cases (speed vs accuracy, different asset classes, etc.)

---

## Current State Analysis

### Kronos Architecture
- **Two-stage framework**: KronosTokenizer (OHLCV quantization) + Kronos (autoregressive prediction)
- **Hierarchical tokens**: s1 (coarse) and s2 (fine-grained) tokens with dependency-aware generation
- **Scope**: Candlestick data with temporal features (minute, hour, weekday, day, month)
- **Models available**: mini (4.1M), small (24.7M), base (102.3M)

### TimeFM Model - Financial Application Research

**Source**: Google Research TimesFM (github.com/google-research/timesfm)

#### Model Architecture & Characteristics
- **Base Architecture**: Decoder-only Transformer with 200M parameters (v2.5)
- **Context Window**: Up to 16k tokens (expanded from 2048 in v2.0)
- **Pre-training**: 100 billion real-world time series data points from diverse domains
- **Capabilities**:
  - Point forecasting (mean predictions)
  - Quantile forecasting (10th-90th percentile uncertainty estimates)
  - Variable input/output lengths
  - Batch processing support

#### Financial Application (Critical Findings)
**Research**: Preferred Networks & Google Research fine-tuned TimesFM for financial markets with key insights:

1. **Baseline TimesFM Fails**: Raw pre-trained model "fails drastically" on price prediction
   - Requires domain-specific fine-tuning on financial data

2. **Solution - Log Transformation**:
   ```
   Loss Function: MSE(log(y_pred), log(y_true))
   ```
   - Prevents high-price-bias (expensive stocks dominating)
   - Stabilizes training during market crashes (>99% drops)
   - Apply to each OHLC component separately

3. **Training Requirements**:
   - Data: 79,153+ hourly/daily time series (stocks, crypto, forex, commodities)
   - Context: 512 time points; Horizon: 128 points
   - Hardware: 8 V100 GPUs (~1 hour training)
   - Optimizer: SGD, LR 5e-4, 100 epochs with warmup + cosine decay

4. **Performance Results**:
   - **S&P 500**: 1.68 Sharpe ratio, 3.6% annual returns (market-neutral strategy)
   - **TOPIX 500**: 1.06 Sharpe ratio
   - **Max viable transaction cost**: 0.60% (S&P 500)
   - Outperforms baseline TimesFM on all horizons
   - Underperforms vs AR(1) on crypto/forex (domain-specific gap)

#### Integration Considerations with Kronos
- **Complementary Strengths**:
  - Kronos: Specialized for candlestick (OHLCV) with hierarchical tokens, 512 context window
  - TimesFM: General-purpose, larger context (512), simpler architecture, proven on multi-asset classes

- **Key Differences**:
  - Kronos uses hierarchical s1/s2 tokens; TimesFM uses raw/log-transformed values
  - Kronos includes temporal features (minute/hour/weekday); TimesFM doesn't require explicit features
  - Kronos optimized for short prediction (10-120 steps); TimesFM tested up to 128 steps

- **Potential Benefits of Ensemble**:
  - Different inductive biases could reduce prediction variance
  - TimesFM's quantile outputs enable uncertainty quantification
  - Ensemble could cover both short-term (Kronos) and medium-term (TimesFM) forecasting

#### Implementation Complexity
- **Moderate**: Both are transformer-based, require similar normalization/preprocessing
- **Code availability**: Google & Preferred Networks published reference implementations
- **Deployment**: Can be containerized similarly to Kronos FastAPI service

---

## Exploration Scope

### Phase 1: Research & Analysis
- [ ] Study TimeFM architecture and design philosophy
- [ ] Document model capabilities and limitations
- [ ] Analyze computational requirements (memory, inference time)
- [ ] Compare prediction accuracy on Kronos test datasets
- [ ] Identify complementary use cases

### Phase 2: Integration Design
- [ ] Design integration points in FastAPI microservice
- [ ] Plan model loading and caching strategy
- [ ] Define ensemble/comparison endpoints
- [ ] Identify shared components with Kronos pipeline

### Phase 3: Prototype (Conditional)
- [ ] Implement TimeFM predictor wrapper
- [ ] Create comparison API endpoints
- [ ] Benchmark against Kronos on standard datasets
- [ ] Document integration experience

---

## Acceptance Criteria

1. **Comprehensive documentation** of TimeFM capabilities, architecture, and fit with Kronos
2. **Comparison matrix** including:
   - Model size and inference latency
   - Accuracy metrics on Kronos test data
   - Integration complexity
   - Resource requirements
3. **Integration feasibility assessment** - clear go/no-go recommendation for Phase 2
4. **Prototype decision** - determine if prototype implementation is warranted

---

## Related Tickets

- TICKET_001_IMP - FastAPI Production Readiness Assessment (context)
- TICKET_003_DES - Kronos FastAPI Microservice Design (integration target)

---

## Practical Application Scenarios for Kronos + TimesFM

### Scenario 1: Multi-Model Ensemble (Recommended)
**Use Case**: Improve prediction robustness through model combination
```
User Request → Kronos (short-term, OHLCV-focused)
            → TimesFM (medium-term, uncertainty-aware)
            → Ensemble Aggregation → Final Prediction + Confidence
```
**Benefits**:
- Reduce individual model bias
- Quantify uncertainty via TimesFM's quantile outputs
- Diversify architectural approaches

### Scenario 2: Asset-Class Specific Routing
**Use Case**: Route predictions based on asset characteristics
```
High-frequency/Short-horizon (stocks) → Kronos (512 context, optimized)
Medium-horizon/Multi-asset (crypto, forex) → TimesFM (proven on multiple classes)
```

### Scenario 3: Fallback/Comparison Strategy
**Use Case**: Use TimesFM for validation and risk management
```
Primary: Kronos predictions
Backup: TimesFM if Kronos prediction confidence is low
Monitor: Compare predictions to detect model drift
```

## Critical Findings & Recommendations

### ✅ Why TimesFM Integration Makes Sense
1. **Proven financial track record**: 1.68 Sharpe ratio on S&P 500 with proper fine-tuning
2. **Uncertainty quantification**: Quantile forecasts enable risk-aware trading
3. **Architectural diversity**: Different tokenization/loss strategies reduce correlation
4. **Deployment ready**: Published code and model weights available

### ⚠️ Key Challenges
1. **Requires fine-tuning**: Can't use pre-trained model directly on new financial data
2. **Different data pipeline**: Log-transformation, different feature engineering vs Kronos
3. **Underperforms on crypto/forex**: Requires additional domain adaptation
4. **Training cost**: Needs significant GPU resources (8 V100s, ~1 hour)

### 🎯 Recommended Next Steps
1. **Phase 1**: Evaluate TimesFM on Kronos test data
   - Extract OHLCV data from Kronos evaluation sets
   - Apply proper fine-tuning pipeline (log transformation, training recipe)
   - Benchmark against Kronos on same data

2. **Phase 2**: Design ensemble architecture
   - Decide aggregation strategy (averaging, weighted, or conditional)
   - Define confidence/uncertainty thresholds
   - Plan API extensions for ensemble endpoints

3. **Phase 3**: Prototype integration
   - Add TimesFM predictor to FastAPI service
   - Implement ensemble endpoint
   - Conduct end-to-end testing

## Notes

- TimesFM requires **domain-specific fine-tuning** - baseline pre-trained model is insufficient for financial data
- Log-transformation of OHLC values is critical for stable training and performance
- Integration should be **non-disruptive** - add as parallel service/endpoint, keep Kronos unchanged
- Consider **API versioning strategy** early (e.g., `/v2/predict/ensemble`)
- Both models are transformer-based, deployment patterns will be similar
- Quantile outputs from TimesFM provide unique value for risk quantification that Kronos doesn't offer
