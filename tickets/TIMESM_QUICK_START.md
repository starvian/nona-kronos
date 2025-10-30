# TimesFM 金融应用 - 快速参考

## 核心问题回答

### ❓ TimesFM 能否直接用于金融预测？

**❌ 不能**

- 预训练的 TimesFM 是通用时间序列模型
- Google Research 实验发现：**"在金融预测上表现很差"**
- 原因：预训练数据不是金融专门数据

### ✅ 如何正确使用 TimesFM 进行金融预测？

**需要微调**

1. **关键技术**：对损失函数应用对数变换
   ```python
   # 标准方法失败了
   loss = MSE(predicted, actual)

   # 金融正确方法
   loss = MSE(log(predicted), log(actual))
   ```

2. **微调配方**（已验证）
   - 数据：79,153 个时间序列 (股票/加密/外汇)
   - 硬件：8 个 V100 GPU，~1 小时
   - 优化器：SGD, LR=5e-4, 100 epochs
   - 上下文：512 points，预测：128 points

3. **实际性能**（Market-neutral strategy）
   - S&P 500: **1.68 Sharpe ratio**, 3.6% annual return ✅
   - TOPIX 500: 1.06 Sharpe ratio
   - 加密/外汇: 表现差，需要特殊处理 ⚠️

---

## TimesFM vs Kronos - 速查表

| 维度 | Kronos | TimesFM |
|------|--------|---------|
| **参数** | 4.1M-102.3M (小) | 200M (大) |
| **架构** | 分层tokens (s1/s2) | 解码器-only transformer |
| **金融特化** | ✅ 原生 | 通过微调 |
| **不确定性** | ❌ 无 | ✅ 分位数 |
| **K线适配** | ✅ OHLCV | 需对数变换 |
| **速度** | 快 | 中等 |
| **最佳用途** | 短期精准预测 | 风险量化/中期 |

---

## 为什么值得集成？

### ✅ 集成的好处

```
Kronos (短期K线优化)
    ↓
  集成器 ← TimesFM (风险量化 + 多资产)
    ↓
最终预测 + 置信度 + 分位数
```

**具体优势**：
1. 不同架构降低预测方差
2. TimesFM 的分位数支持风险管理
3. 覆盖短期和中期预测
4. 提高整体鲁棒性

### ⚠️ 集成的成本

1. **计算**: 200M 参数，内存+延迟增加
2. **微调**: 需要大量金融数据和 GPU
3. **维护**: 两个模型要管理和监控

---

## 快速开始流程

### Phase 1: 评估 (2-3 周)

```bash
# 步骤 1: 安装 TimesFM
pip install timesfm torch

# 步骤 2: 在 Kronos 数据上测试
python evaluate_timesfm_on_kronos_data.py

# 步骤 3: 对比性能
# - 同一数据集上比较准确度
# - 测量延迟差异
# - 评估计算成本
```

**决策点**: TimesFM 的性能改进值得额外成本吗？

### Phase 2: 设计 (1-2 周)

```
设计集成架构
├─ 选择聚合策略 (平均/加权/置信度)
├─ 定义置信度阈值
├─ 规划 API 版本 (/v2/predict/ensemble)
└─ 确保向后兼容性
```

### Phase 3: 实现 (2-3 周)

```
实现集成服务
├─ TimesFMPredictor 包装类
├─ 集成端点 (/v2/predict/ensemble)
├─ 模型管理 (启动/加载)
├─ 测试 + 性能基准
└─ 部署
```

---

## 决策树

```
你的应用需要什么?
│
├─ 只要点预测 (O, H, L, C 的预测值)
│  └─ 使用 Kronos ✅ (已充分)
│
├─ 需要不确定性估计 (风险分位数)
│  └─ 集成 TimesFM ✅ (推荐)
│
├─ 处理加密/外汇交易
│  └─ 需谨慎 ⚠️ (TimesFM 在这些资产上表现一般)
│
└─ 计算资源受限
   └─ 只用 Kronos ✅ (TimesFM 很重)
```

---

## 实际代码示例

### 最小化集成示例

```python
from kronos_predictor import KronosPredictor  # 现有
from timesfm_predictor import TimesFMPredictor  # 新增

# 初始化两个模型
kronos = KronosPredictor(device="cuda:0")
timesfm = TimesFMPredictor(device="cuda:0")

# 输入数据 (OHLC)
ohlc = np.array([
    [100, 102, 99, 101],
    [101, 103, 100, 102],
    # ... 512 个历史数据点
])

# 两个模型的预测
kronos_pred = kronos.predict(ohlc, horizon=128)
timesfm_pred = timesfm.predict(ohlc, horizon=128)

# 简单平均集成
ensemble_pred = (kronos_pred + timesfm_pred) / 2

print("Kronos:    ", kronos_pred[:5])
print("TimesFM:   ", timesfm_pred[:5])
print("Ensemble:  ", ensemble_pred[:5])
```

---

## 关键数字速查

### 微调成本
- **时间**: 1 小时 (8 V100 GPU)
- **数据**: 79,153 个时间序列
- **成本**: ~$50-100 (云 GPU)

### 部署成本
- **内存**: Kronos 500MB + TimesFM 1GB + 缓冲 = ~2GB
- **延迟**: 150-350ms (预测 128 步)
- **吞吐量**: ~10-20 请求/秒 (单 GPU)

### 性能指标 (金融)
- **S&P 500 Sharpe**: 1.68 (好)
- **加密交易 Sharpe**: 低 (需改进)
- **最大交易成本**: 0.60% (S&P 500)

---

## 关键参考

| 资源 | 链接 |
|------|------|
| 论文 | arxiv.org/html/2412.09880v1 |
| GitHub | github.com/google-research/timesfm |
| Preferred Networks | tech.preferred.jp/en/blog/timesfm/ |
| 模型权重 | huggingface.co (已发布) |

---

## 常见问题

**Q: TimesFM 能替代 Kronos 吗?**
A: 不能。Kronos 针对 K线数据深度优化，TimesFM 是通用时间序列。集成 > 替换。

**Q: 微调很复杂吗?**
A: 不复杂。关键是对数变换 + SGD 优化。Preferred Networks 已发布代码。

**Q: 能用预训练权重吗?**
A: 不行。研究表明"表现很差"。必须在金融数据上微调。

**Q: 加密交易能用吗?**
A: 可以，但性能一般。需要额外的加密特定调整。

**Q: 多长时间才能集成?**
A: 评估 2-3 周 + 设计 1-2 周 + 实现 2-3 周 = 5-8 周

---

## 推荐行动

### 立即 (本周)
- [ ] 阅读论文: arxiv.org/html/2412.09880v1
- [ ] 浏览 GitHub: github.com/google-research/timesfm
- [ ] 评估集成收益

### 短期 (2-4 周)
- [ ] Phase 1 评估
  - 在 Kronos 数据上运行 TimesFM
  - 对比结果
  - 计算性能提升

### 中期 (5-8 周)
- [ ] 决定是否集成
- [ ] 如果是，执行 Phase 2+3

---

**结论**: TimesFM 是**高质量的金融时间序列模型**，但**不能开箱即用**。经过适当的微调和集成，它可以为 Kronos 系统增加**风险量化和多资产支持**，但需要**显著的计算投资**。
