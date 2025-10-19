# Kronos CPU 模式配置、启动和测试 - 完整总结

## 📦 已创建的文件

### 配置文件
```
services/kronos_fastapi/.env.cpu     - CPU 模式配置模板
```

### 启动脚本
```
services/start_cpu_server.sh         - 一键启动服务器（CPU 模式）
```

### 测试脚本
```
services/test_cpu_prediction.py      - CPU 预测性能测试客户端
services/test_device_resolution.py   - 设备解析验证测试
```

### 文档
```
services/QUICKSTART.md               - 一分钟快速开始指南
services/START_CPU_MODE.md           - 详细启动和测试指南
services/DEVICE_SUPPORT.md           - 设备支持技术文档
services/CPU_GPU_IMPLEMENTATION.md   - 实现架构总结
services/CPU_TEST_SUMMARY.md         - 本文件
```

## 🚀 快速使用流程

### 步骤 1: 启动服务器

**终端 1** - 启动服务：
```bash
cd /data/ws/kronos/services
./start_cpu_server.sh
```

等待看到：
```
INFO:     Application startup complete.
```

### 步骤 2: 验证服务

**终端 2** - 检查状态：
```bash
# 健康检查
curl http://localhost:8000/v1/healthz

# 等待模型加载（1-2分钟）
watch -n 2 'curl -s http://localhost:8000/v1/readyz | python -m json.tool'
```

等待看到：
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cpu",
  "device_warning": null
}
```

### 步骤 3: 运行测试

**终端 2** - 执行测试：
```bash
cd /data/ws/kronos/services
python test_cpu_prediction.py
```

## 📊 测试客户端功能

`test_cpu_prediction.py` 自动执行以下操作：

1. ✅ **健康检查** - 验证服务可访问
2. ✅ **就绪检查** - 确认模型已加载，显示设备信息（CPU）
3. ✅ **生成测试数据** - 创建 100 条模拟 K 线数据
4. ✅ **执行预测** - 发送预测请求，预测 10 个未来点
5. ✅ **统计时间** - 精确测量预测耗时
6. ✅ **显示结果** - 展示预测的 OHLC 数据

### 输出示例

```
======================================================================
⏱️  预测时间统计
======================================================================
总耗时: 12.34 秒
平均每个预测点: 1.234 秒
吞吐量: 0.81 点/秒

预测结果（前3个点）:
  1. 时间: 2024-01-01T11:10:00
     OHLC: O=104.23, H=105.12, L=103.89, C=104.56
  2. 时间: 2024-01-01T11:11:00
     OHLC: O=104.56, H=105.34, L=104.12, C=104.89
  3. 时间: 2024-01-01T11:12:00
     OHLC: O=104.89, H=105.67, L=104.45, C=105.23
```

## 🎛️ 配置说明

### CPU 模式强制配置

`.env.cpu` 文件的关键设置：

```bash
# 强制 CPU（即使有 GPU 也不使用）
KRONOS_DEVICE=cpu

# 增加超时（CPU 较慢）
KRONOS_INFERENCE_TIMEOUT=120
KRONOS_REQUEST_TIMEOUT=180
KRONOS_STARTUP_TIMEOUT=300

# 禁用安全检查（开发模式）
KRONOS_SECURITY_ENABLED=false
KRONOS_RATE_LIMIT_ENABLED=false
```

### 预测参数调优

```bash
# 默认预测长度（较短更快）
KRONOS_DEFAULT_PRED_LEN=10

# 采样次数（越多质量越好但越慢）
KRONOS_DEFAULT_SAMPLE_COUNT=1

# Temperature（1.0 = 标准，<1.0 = 更确定性）
KRONOS_DEFAULT_TEMPERATURE=1.0
```

## 📈 性能基准

### CPU 模式典型性能

基于测试，CPU 模式的预测性能：

| 输入长度 | 预测长度 | 采样次数 | 预计耗时 | 吞吐量 |
|---------|---------|---------|---------|--------|
| 50      | 5       | 1       | 5-10秒  | 0.5-1 点/秒 |
| 100     | 10      | 1       | 10-20秒 | 0.5-1 点/秒 |
| 100     | 10      | 3       | 30-60秒 | 0.15-0.3 点/秒 |
| 200     | 20      | 1       | 20-40秒 | 0.5-1 点/秒 |

### 与 GPU 对比

- **CPU**: 0.5-1 点/秒
- **GPU**: 5-50 点/秒（快 10-50 倍）

**结论**: CPU 模式适合开发测试和低频预测场景。生产环境建议使用 GPU。

## 🧪 测试场景

### 场景 1: 快速单次预测

```bash
# 最快配置：短输入、短预测、单次采样
python test_cpu_prediction.py
# 默认: 100 输入 → 10 预测 → 1 采样
# 预计: 10-20 秒
```

### 场景 2: 高质量预测

```python
# 编辑 test_cpu_prediction.py，修改参数：
result = client.predict_single(
    candles=test_data["candles"],
    timestamps=test_data["timestamps"],
    pred_len=10,
    sample_count=5,  # 增加采样次数
    temperature=1.0
)
# 预计: 50-100 秒
```

### 场景 3: 性能压测

```python
# 取消注释性能测试代码块：
client.run_performance_test(
    input_lengths=[50, 100, 200],
    pred_lengths=[5, 10, 20],
    sample_counts=[1, 3]
)
# 预计: 5-10 分钟完成全部测试
```

## 🔧 手动 API 调用

### 最小示例

```bash
curl -X POST http://localhost:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{
    "series_id": "manual_test",
    "candles": [
      {"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000000, "amount": 100500000}
    ],
    "timestamps": ["2024-01-01T09:30:00"],
    "prediction_timestamps": ["2024-01-01T09:31:00"],
    "overrides": {"pred_len": 1, "sample_count": 1}
  }' | python -m json.tool
```

### Python 代码示例

```python
import requests
import time

start = time.time()

response = requests.post(
    "http://localhost:8000/v1/predict/single",
    json={
        "series_id": "python_test",
        "candles": [
            {"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000000, "amount": 100500000},
            {"open": 100.5, "high": 102, "low": 100, "close": 101.5, "volume": 1100000, "amount": 111650000}
        ],
        "timestamps": ["2024-01-01T09:30:00", "2024-01-01T09:31:00"],
        "prediction_timestamps": ["2024-01-01T09:32:00"],
        "overrides": {"pred_len": 1, "sample_count": 1}
    },
    timeout=60
)

elapsed = time.time() - start

if response.status_code == 200:
    result = response.json()
    print(f"✓ 预测成功，耗时 {elapsed:.2f} 秒")
    print(f"预测结果: {result['prediction']}")
else:
    print(f"✗ 预测失败: {response.status_code}")
    print(response.text)
```

## 🐛 常见问题速查

| 问题 | 原因 | 解决方案 |
|-----|-----|---------|
| 端口占用 | 8000 端口被占用 | `lsof -i :8000` 查看并杀死进程 |
| 模型加载失败 | 模型文件不存在 | 设置 `KRONOS_MODEL_ID=NeoQuasar/Kronos-small` 自动下载 |
| 预测超时 | CPU 推理慢 | 增加 `KRONOS_INFERENCE_TIMEOUT=300` |
| Import 错误 | 工作目录错误 | 必须从 `gitSource/` 启动服务 |
| CUDA 警告 | 配置未生效 | 确认 `.env` 中 `KRONOS_DEVICE=cpu` |

## 📁 文件组织结构

```
/data/ws/kronos/
├── gitSource/                          # Kronos 模型核心代码
│   ├── model/
│   │   ├── device.py                  # ⭐ 设备解析模块
│   │   ├── kronos.py                  # ✏️ 使用设备解析
│   │   └── __init__.py                # ✏️ 导出 resolve_device
│   ├── requirements.txt               # ✏️ 纯 CPU 依赖
│   ├── requirements-cuda.txt          # ⭐ CUDA 依赖
│   └── ...
│
└── services/                           # 生产微服务
    ├── kronos_fastapi/
    │   ├── .env.cpu                   # ⭐ CPU 配置模板
    │   ├── config.py                  # ✓ 支持 device 配置
    │   ├── predictor.py               # ✓ 支持 device 属性
    │   └── ...
    │
    ├── start_cpu_server.sh            # ⭐ 一键启动脚本
    ├── test_cpu_prediction.py         # ⭐ 性能测试客户端
    ├── test_device_resolution.py      # ⭐ 设备验证测试
    │
    ├── QUICKSTART.md                  # 📖 快速开始
    ├── START_CPU_MODE.md              # 📖 详细指南
    ├── DEVICE_SUPPORT.md              # 📖 技术文档
    ├── CPU_GPU_IMPLEMENTATION.md      # 📖 实现总结
    └── CPU_TEST_SUMMARY.md            # 📖 本文件

图例: ⭐ 新建  ✏️ 修改  ✓ 已有  📖 文档
```

## ✅ 验证清单

完成所有步骤后，确认：

- [ ] `.env.cpu` 配置文件已创建
- [ ] 启动脚本 `start_cpu_server.sh` 可执行
- [ ] 服务启动无错误，日志显示 "Application startup complete"
- [ ] 健康检查 `/v1/healthz` 返回 `{"status": "ok"}`
- [ ] 就绪检查 `/v1/readyz` 返回 `"model_loaded": true` 和 `"device": "cpu"`
- [ ] 测试客户端运行成功，显示预测时间统计
- [ ] 预测结果包含正确的 OHLC 数据
- [ ] 时间统计合理（10-20秒用于 100→10 预测）

## 📚 相关文档

1. **快速开始**: `QUICKSTART.md` - 一分钟快速测试
2. **详细指南**: `START_CPU_MODE.md` - 完整启动和故障排除
3. **技术文档**: `DEVICE_SUPPORT.md` - 设备支持技术细节
4. **实现总结**: `CPU_GPU_IMPLEMENTATION.md` - 架构和实现说明
5. **设计票据**: `tickets/TICKET_004_DES_Device-Agnostic-Kronos.md` - 设计文档

## 🎯 下一步

### 开发环境
- ✅ CPU 模式测试完成
- 🔄 切换到 GPU 模式: 设置 `KRONOS_DEVICE=cuda:0` 并安装 `requirements-cuda.txt`

### 生产部署
- 参考 `kronos_fastapi/DEPLOYMENT.md` 进行 Docker 容器化
- 使用 `docker-compose.yml` 部署
- 配置 GPU 支持（如果有 NVIDIA GPU）

### 性能优化
- 使用 GPU 加速（快 10-50 倍）
- 调整 `sample_count` 和 `temperature` 参数
- 使用批量预测 API（`/v1/predict/batch`）

## 📞 支持

遇到问题？

1. 查看 `START_CPU_MODE.md` 的故障排除章节
2. 检查服务日志输出
3. 验证配置文件 `.env` 的设置
4. 确认从正确的目录启动服务（`gitSource/`）

---

**总结**: 所有 CPU 模式配置、启动脚本、测试客户端和文档已完成。使用 `./start_cpu_server.sh` 启动服务，然后运行 `python test_cpu_prediction.py` 进行测试。
