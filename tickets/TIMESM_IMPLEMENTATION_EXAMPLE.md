# TimesFM 集成实现示例

本文档提供了如何在 Kronos FastAPI 服务中集成 TimesFM 的代码框架示例。

---

## 1. TimesFM 预测器包装类

```python
# services/kronos_fastapi/timesfm_predictor.py

import torch
import numpy as np
from typing import Tuple, Dict
import logging

logger = logging.getLogger(__name__)

class TimesFMPredictor:
    """TimesFM 预测器包装类"""

    def __init__(self, model_path: str = "google/timesfm-1.0-200m", device: str = "cuda:0"):
        """
        初始化 TimesFM 预测器

        Args:
            model_path: HuggingFace 模型路径
            device: 计算设备
        """
        self.device = device
        self.model_path = model_path

        try:
            # 从 HuggingFace 加载模型
            from timesfm import TimesFM
            self.model = TimesFM.from_pretrained(model_path)
            self.model.to(device)
            logger.info(f"TimesFM 模型加载成功: {model_path}")
        except ImportError:
            logger.error("TimesFM 库未安装，请运行: pip install timesfm")
            raise

    def apply_log_transform(self, data: np.ndarray) -> np.ndarray:
        """
        应用对数变换以稳定金融数据

        Args:
            data: 输入价格数据，形状为 (seq_len, features)

        Returns:
            对数变换后的数据
        """
        # 防止负数或零
        data_safe = np.where(data > 0, data, 1e-10)
        return np.log(data_safe)

    def reverse_log_transform(self, log_data: np.ndarray) -> np.ndarray:
        """反向对数变换"""
        return np.exp(log_data)

    def predict(
        self,
        history: np.ndarray,  # (seq_len, 4) for OHLC
        horizon: int = 128,
        quantiles: bool = True
    ) -> Dict:
        """
        单条时间序列预测

        Args:
            history: 历史OHLC数据，形状为 (seq_len, 4)
            horizon: 预测步数（推荐128）
            quantiles: 是否输出分位数

        Returns:
            预测结果字典
            {
                'point_forecast': (horizon, 4),  # OHLC 点预测
                'quantile_forecasts': (horizon, 4, num_quantiles),  # 可选
                'confidence': float  # 0-1 置信度
            }
        """
        with torch.no_grad():
            # 应用对数变换
            log_history = self.apply_log_transform(history)

            # TimesFM 预测
            # 输入形状: (batch_size, context_len)
            # 这里假设使用特定的TimesFM API
            config = {
                'context_length': min(len(history), 512),
                'forecast_length': horizon,
                'quantiles': quantiles
            }

            # 转换为模型输入格式
            input_tensor = torch.from_numpy(log_history).float().to(self.device)

            # 获取预测
            forecasts = self.model.forecast(
                input_tensor.unsqueeze(0),  # 添加batch维度
                forecast_length=horizon,
                quantiles=[0.1, 0.5, 0.9] if quantiles else None
            )

            # 反向对数变换
            point_forecast = self.reverse_log_transform(
                forecasts['mean'].cpu().numpy()[0]
            )

            result = {
                'point_forecast': point_forecast,
                'confidence': self._calculate_confidence(forecasts),
            }

            if quantiles and 'quantiles' in forecasts:
                result['quantile_forecasts'] = self.reverse_log_transform(
                    forecasts['quantiles'].cpu().numpy()[0]
                )

            return result

    def predict_batch(
        self,
        histories: np.ndarray,  # (batch_size, seq_len, 4)
        horizon: int = 128
    ) -> Dict:
        """
        批量预测

        Args:
            histories: 批量历史数据
            horizon: 预测步数

        Returns:
            批量预测结果
        """
        batch_size = len(histories)
        results = []

        with torch.no_grad():
            for history in histories:
                result = self.predict(history, horizon=horizon)
                results.append(result)

        return {
            'batch_forecasts': results,
            'batch_size': batch_size
        }

    def _calculate_confidence(self, forecasts: Dict) -> float:
        """
        计算预测置信度
        基于分位数宽度
        """
        if 'quantiles' not in forecasts:
            return 0.5

        quantiles = forecasts['quantiles'].cpu().numpy()
        # 使用10%-90%分位数宽度来估计置信度
        # 宽度越窄，置信度越高
        quantile_range = np.abs(quantiles[..., -1] - quantiles[..., 0]).mean()

        # 标准化到 [0, 1]
        confidence = 1.0 / (1.0 + quantile_range)
        return float(confidence)
```

---

## 2. 集成端点示例

```python
# services/kronos_fastapi/routes_ensemble.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import numpy as np
from typing import List, Optional
import logging

from .predictor import PredictorManager  # Kronos
from .timesfm_predictor import TimesFMPredictor  # TimesFM
from .schemas import PredictionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2", tags=["ensemble"])

# 模型管理器
timesfm_manager = None

async def init_timesfm():
    """初始化 TimesFM 模型"""
    global timesfm_manager
    try:
        timesfm_manager = TimesFMPredictor(device="cuda:0")
        logger.info("TimesFM 初始化成功")
    except Exception as e:
        logger.error(f"TimesFM 初始化失败: {e}")


class EnsemblePredictionRequest(BaseModel):
    """集成预测请求"""
    ohlc_data: List[List[float]]  # [[o,h,l,c], ...]
    horizon: int = 128
    use_kronos: bool = True
    use_timesfm: bool = True
    ensemble_method: str = "weighted"  # "averaged", "weighted", "max_confidence"


class EnsemblePredictionResponse(BaseModel):
    """集成预测响应"""
    ensemble_forecast: List[List[float]]  # 最终预测
    confidence: float  # 最终置信度
    kronos_forecast: Optional[List[List[float]]] = None
    timesfm_forecast: Optional[List[List[float]]] = None
    kronos_confidence: Optional[float] = None
    timesfm_confidence: Optional[float] = None
    details: dict = {}


@router.post("/predict/ensemble", response_model=EnsemblePredictionResponse)
async def predict_ensemble(request: EnsemblePredictionRequest):
    """
    多模型集成预测

    返回 Kronos 和 TimesFM 预测的集成结果
    """
    try:
        ohlc_array = np.array(request.ohlc_data)

        results = {
            'ensemble_forecast': None,
            'confidence': 0.0,
            'kronos_forecast': None,
            'timesfm_forecast': None,
            'kronos_confidence': None,
            'timesfm_confidence': None,
            'details': {}
        }

        # Kronos 预测
        if request.use_kronos:
            kronos_result = PredictorManager.get_predictor().predict(
                ohlc_array,
                horizon=request.horizon
            )
            results['kronos_forecast'] = kronos_result.get('forecast').tolist()
            results['kronos_confidence'] = kronos_result.get('confidence', 0.5)

        # TimesFM 预测
        if request.use_timesfm:
            if timesfm_manager is None:
                raise HTTPException(
                    status_code=500,
                    detail="TimesFM 模型未初始化"
                )

            timesfm_result = timesfm_manager.predict(
                ohlc_array,
                horizon=request.horizon
            )
            results['timesfm_forecast'] = timesfm_result['point_forecast'].tolist()
            results['timesfm_confidence'] = timesfm_result['confidence']

        # 集成聚合
        forecasts = []
        confidences = []

        if results['kronos_forecast']:
            forecasts.append(np.array(results['kronos_forecast']))
            confidences.append(results['kronos_confidence'])

        if results['timesfm_forecast']:
            forecasts.append(np.array(results['timesfm_forecast']))
            confidences.append(results['timesfm_confidence'])

        if not forecasts:
            raise HTTPException(
                status_code=400,
                detail="必须至少选择一个模型"
            )

        # 按聚合方法组合
        if request.ensemble_method == "averaged":
            ensemble = np.mean(forecasts, axis=0)
            ensemble_confidence = np.mean(confidences)

        elif request.ensemble_method == "weighted":
            # 按置信度加权
            weights = np.array(confidences) / sum(confidences)
            ensemble = np.average(
                forecasts, axis=0, weights=weights
            )
            ensemble_confidence = np.mean(confidences)

        elif request.ensemble_method == "max_confidence":
            # 选择置信度最高的预测
            max_idx = np.argmax(confidences)
            ensemble = forecasts[max_idx]
            ensemble_confidence = confidences[max_idx]

        else:
            raise HTTPException(
                status_code=400,
                detail=f"未知的聚合方法: {request.ensemble_method}"
            )

        results['ensemble_forecast'] = ensemble.tolist()
        results['confidence'] = float(ensemble_confidence)
        results['details']['ensemble_method'] = request.ensemble_method
        results['details']['num_models'] = len(forecasts)

        return EnsemblePredictionResponse(**results)

    except Exception as e:
        logger.error(f"集成预测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v2/models")
async def list_models():
    """列出可用模型"""
    return {
        'available_models': [
            {
                'name': 'kronos',
                'status': 'loaded',
                'parameters': '4.1M-102.3M',
                'context': 512,
            },
            {
                'name': 'timesfm',
                'status': 'loaded' if timesfm_manager else 'not_loaded',
                'parameters': '200M',
                'context': 512,
            }
        ]
    }
```

---

## 3. 在 main.py 中集成

```python
# services/kronos_fastapi/main.py (修改部分)

from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

# 导入集成路由
from .routes_ensemble import router as ensemble_router, init_timesfm

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动事件
    logger.info("启动事件: 初始化模型...")

    # 初始化 Kronos (现有)
    from .predictor import PredictorManager
    PredictorManager.initialize()

    # 初始化 TimesFM (新)
    await init_timesfm()

    logger.info("所有模型初始化完成")

    yield

    # 关闭事件
    logger.info("服务关闭...")


app = FastAPI(
    title="Kronos + TimesFM Ensemble",
    lifespan=lifespan
)

# 注册路由
from .routes import router as v1_router
app.include_router(v1_router)

# 注册集成路由
app.include_router(ensemble_router)
```

---

## 4. 使用示例

```bash
# 安装依赖
pip install timesfm torch numpy

# 启动服务
cd gitSource
uvicorn services.kronos_fastapi.main:app --reload --port 8000
```

```python
# 客户端使用示例
import requests
import json

url = "http://localhost:8000/v2/predict/ensemble"

# 示例 K线数据 (O, H, L, C)
ohlc_data = [
    [100.0, 102.0, 99.0, 101.0],
    [101.0, 103.0, 100.0, 102.0],
    # ... 更多数据
]

request_body = {
    "ohlc_data": ohlc_data,
    "horizon": 128,
    "use_kronos": True,
    "use_timesfm": True,
    "ensemble_method": "weighted"
}

response = requests.post(url, json=request_body)
result = response.json()

print("集成预测:")
print(json.dumps(result, indent=2))
```

---

## 5. 性能考虑

### 内存需求

```
Kronos (base):       ~300-500 MB
TimesFM (200M):      ~800 MB - 1.2 GB
集成服务:            ~2 GB (含缓冲)
```

### 延迟估计

```
Kronos 单条预测:     ~50-100 ms
TimesFM 单条预测:    ~100-200 ms
集成开销:           ~20-50 ms
总时间:             ~150-350 ms (预测128步)
```

### 优化建议

1. **模型缓存**: 在内存中缓存模型
2. **批处理**: 使用 `predict_batch` 端点
3. **异步处理**: 对长时间序列使用异步/队列
4. **GPU 选择**: 使用 NVIDIA A100/H100 加速

---

## 6. 下一步

- [ ] 实现模型权重的持久化
- [ ] 添加模型漂移检测
- [ ] 实现在线学习/增量微调
- [ ] 性能监控和指标收集
- [ ] A/B 测试框架
- [ ] 模型版本管理
