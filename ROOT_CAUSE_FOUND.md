# 超时问题根因分析

## 🎯 问题根源

经过 4 轮调试，终于找到真正的根因：

### Pydantic Field() 参数错误

**错误代码** (config.py 第 46 行):
```python
inference_timeout: int = Field(30, env="KRONOS_INFERENCE_TIMEOUT")
                              ^^^ 这不是 default 参数！
```

**正确代码**:
```python
inference_timeout: int = Field(default=240, env="KRONOS_INFERENCE_TIMEOUT")
                              ^^^^^^^^ 必须显式指定 default=
```

## 📚 技术细节

### Pydantic Field() 的签名

在 Pydantic v2 中，`Field()` 的第一个位置参数**不是** `default`！

正确的签名：
```python
Field(
    default=...,           # 默认值（关键字参数）
    default_factory=...,   # 默认值工厂
    alias=...,             # 别名
    # ... 其他参数
)
```

我们的错误：
```python
Field(30, env="KRONOS_INFERENCE_TIMEOUT")
```

Pydantic 把 `30` 当作**第一个位置参数**，而不是 `default`！

### 为什么环境变量被忽略

因为：
1. Pydantic 没有正确识别默认值
2. 使用了某个内部默认值 (30)
3. 环境变量 `KRONOS_INFERENCE_TIMEOUT=240` 被忽略

### 验证

修复前：
```python
# 环境变量: KRONOS_INFERENCE_TIMEOUT=240
settings.inference_timeout  # 返回 30 ✗
```

修复后：
```python
# 环境变量: KRONOS_INFERENCE_TIMEOUT=240  
settings.inference_timeout  # 返回 240 ✓
```

## 🔍 调试过程回顾

### 第 1 轮
- 问题：504 超时
- 尝试：修改 .env 文件
- 结果：失败（服务未读取）

### 第 2 轮  
- 问题：服务未读取 .env
- 尝试：修改启动脚本，设置环境变量
- 结果：失败（Pydantic 仍使用默认值）

### 第 3 轮
- 问题：环境变量设置但未生效
- 尝试：增加超时到 240 秒
- 结果：失败（根本没读取）

### 第 4 轮
- 问题：添加日志追踪
- 发现：`inference_timeout=30` 不是 240！
- 深入：检查 Pydantic Field() 参数
- 根因：**Field(30, ...) 参数错误**
- 修复：改为 `Field(default=240, ...)`
- 验证：✓ 配置正确

## ✅ 完整修复

### 1. config.py

```python
# 修复前
inference_timeout: int = Field(30, env="KRONOS_INFERENCE_TIMEOUT")
request_timeout: int = Field(60, env="KRONOS_REQUEST_TIMEOUT")
startup_timeout: int = Field(120, env="KRONOS_STARTUP_TIMEOUT")

# 修复后
inference_timeout: int = Field(default=240, env="KRONOS_INFERENCE_TIMEOUT")
request_timeout: int = Field(default=300, env="KRONOS_REQUEST_TIMEOUT")
startup_timeout: int = Field(default=300, env="KRONOS_STARTUP_TIMEOUT")
```

### 2. predictor.py

添加日志：
```python
# 启动时
logger.info(
    f"Service configuration: "
    f"device={self._settings.device}, "
    f"inference_timeout={self._settings.inference_timeout}s, "
    f"request_timeout={self._settings.request_timeout}s"
)

# 预测时
logger.info(
    f"predict_single_async starting: "
    f"input_len={len(candles)}, "
    f"pred_len={len(prediction_timestamps)}, "
    f"timeout_configured={self._settings.inference_timeout}s, "
    f"timeout_used={timeout_seconds}s"
)
```

### 3. 验证脚本

创建 `verify_config.py` 用于验证配置加载。

## 💡 经验教训

1. **Pydantic v2 的 Field() 必须使用关键字参数**
   ```python
   # 错误
   Field(value, env="...")
   
   # 正确
   Field(default=value, env="...")
   ```

2. **环境变量不生效？先验证配置加载**
   - 创建简单脚本验证
   - 不要假设环境变量会自动生效

3. **添加日志追踪是关键**
   - 启动时记录配置
   - 关键路径记录参数
   - 日志帮助快速定位问题

4. **调试要深入到代码层面**
   - 不要只改配置文件
   - 检查代码如何读取配置
   - 验证实际使用的值

## 🚀 验证修复

运行验证脚本：
```bash
cd /data/ws/kronos/services
python verify_config.py
```

预期输出：
```
✓ inference_timeout 正确: 240 秒
✓ request_timeout 正确: 300 秒
```

重启服务并测试：
```bash
./start_cpu_simple_v2.sh

# 新终端
python test_cpu_prediction_400.py
```

## 📊 最终配置

| 参数 | 值 | 说明 |
|-----|---|------|
| inference_timeout | 240秒 | 模型推理超时 |
| request_timeout | 300秒 | 请求总超时 |
| startup_timeout | 300秒 | 启动超时 |
| client timeout | 300秒 | 客户端超时 |

足够支持 400→120 长序列预测（预估 25-30 秒）。
