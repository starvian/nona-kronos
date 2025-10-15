# DESIGN TICKET 004 - Kronos 设备无关化支持（CPU/GPU）

**日期**: 2025-10-15  
**状态**: Draft  
**类型**: Design (DES)

---

## 1. 背景与目标

- 现有 Kronos 推理与微服务实现默认依赖 NVIDIA CUDA 环境：`requirements.txt` 强制安装 `nvidia-*` 组件、推理逻辑中直接调用 `torch.cuda.*`，导致在无 GPU 的环境下无法运行。
- Finetune 脚本也通过 DDP 固定使用 `torch.device(f"cuda:{local_rank}")`，在仅有 CPU 的研发/测试环境中无法复用流程。
- 目标：定义一套统一的设备抽象方案，使 Kronos 在“纯 CPU”与“纯 GPU”两种部署形态下均可无改代码运行，同时保留未来扩展到 MPS/多 GPU 的能力。

---

## 2. 问题分析

1. **依赖层面：** `requirements.txt` 强制拉取 CUDA 12 运行时包，安装在 CPU-only 主机上会失败或造成冗余。
2. **推理层面：** `model/kronos.py` 的 `auto_regressive_inference` 与 `KronosPredictor` 默认调用 `.to(device)` 并在循环中执行 `torch.cuda.empty_cache()`；当 device=cpu 时调用会抛错。
3. **服务层面：** FastAPI 以及 Flask WebUI 通过请求参数选择 `device`，但缺乏对可用性的检测与回退逻辑，且未暴露配置默认值的统一入口。
4. **训练层面：** `finetune/train_*.py` 工作流使用 `torchrun` + DDP 并固定 `cuda:{local_rank}`；未提供单机 CPU 训练模式。
5. **测试覆盖：** 当前没有集成测试覆盖 CPU-only 场景，CI 上亦未验证。

---

## 3. 设计方案

### 3.1 设备抽象与配置

- 在共享配置层（如 `services/kronos_fastapi/config.py`、WebUI 配置、CLI 脚本）引入统一的 `device` 选择逻辑：
  - 优先使用显式输入（API 参数、CLI flag、环境变量 `KRONOS_DEVICE`）。
  - 若请求 GPU 但 `torch.cuda.is_available()` 返回 False，则自动降级到 CPU 并记录警告。
- 为未来支持 MPS / 多 GPU，设计设备解析函数 `resolve_device(requested: str | None) -> torch.device`，负责：
  - 校验格式（`cpu`、`cuda`, `cuda:0`, `mps`）。
  - 返回 `torch.device` 实例。
  - 负责降级逻辑（如请求 `cuda:1` 但不可用）。

### 3.2 推理代码调整

- 修改 `model/kronos.py`：
  - 在 `auto_regressive_inference` 中，将 `torch.cuda.empty_cache()` 改为按需调用（仅当当前设备属于 CUDA）。
  - 确保所有张量创建、索引操作使用 `device` 上下文，而不是硬编码 GPU。
- 调整 `KronosPredictor`：
  - 初始化时存储 `self.device = torch.device(device)`。
  - 在 `.generate()`/`.predict()` 中通过 `to(self.device)` 放置张量；创建中间张量时复用 `device`。
  - 增加设备可用性校验与日志提示。

### 3.3 服务与 CLI 层改造

- **FastAPI 微服务**：
  - 在模型加载入口调用新的 `resolve_device`，并在 `/v1/predict/*` 路由中复用。
  - 如果传入设备不可用，返回 400 或自动回退并在响应中标注。
  - 增加健康检查项（`/v1/readyz`）以显式报告当前设备。
- **Flask WebUI**：
  - UI 中保留设备下拉框；调用后端时传递用户选择。
  - 若回退到 CPU，在前端提示。
- **示例脚本与 CLI**：
  - 为 `examples/*.py` 提供 `--device` CLI 选项，默认自动解析。

### 3.4 训练脚本兼容

- 为 `finetune/train_tokenizer.py` 与 `finetune/train_predictor.py` 增加单机 CPU 模式：
  - 若 `torch.cuda.is_available()` 为 False 或命令行显式指定 `--device cpu`，则使用单进程训练（禁用 DDP，使用标准优化循环）。
  - 在配置中增加 `training.device` 字段，统一读取。
  - DDP 相关逻辑包裹在条件判断内，避免在 CPU 上初始化 NCCL。

### 3.5 依赖与分发

- 调整 `requirements.txt`：
  - 将 CUDA 相关依赖移动至 `extras` 或单独文档说明；基础安装仅包含 `torch`（由用户选择 CPU/GPU 版本）。
  - 或者提供 `requirements-cuda.txt` 与 `requirements-cpu.txt`，在 README/Ticket 中描述安装指引。
- 确保 Dockerfile / 启动脚本根据目标设备选择合适的 requirements。

---

## 4. 测试计划

1. **单元测试**：
   - 覆盖 `resolve_device` 的各种输入（有效、降级、错误）。
   - 验证 `auto_regressive_inference` 在 CPU 模式下不触发 CUDA 调用。
2. **集成测试**：
   - 在 CPU-only 环境跑通预测示例与 FastAPI `/v1/predict/single` 调用。
   - 在 GPU 环境确认仍能使用 CUDA 并维持性能。
3. **训练验证**：
   - CPU 模式下运行最小化 finetune epoch，确认不会触发 DDP / NCCL 错误。
4. **CI/CD**：
   - 增加 GitHub Actions / Pipeline job，使用 CPU runner 执行核心预测测试。

---

## 5. 风险与缓解

| 风险 | 描述 | 缓解措施 |
| --- | --- | --- |
| 性能退化 | CPU 模式推理速度显著下降 | 文档中提示性能差异，提供批量推理建议；评估是否需要量化/优化 | 
| 依赖冲突 | 拆分 CUDA 依赖后用户安装 GPU 版本 torch 需手动选择 | 在安装指引中提供 `pip install torch --index-url https://download.pytorch.org/whl/cu121` 示例 |
| 训练复杂性 | 在 CPU 上恢复 DDP 逻辑较复杂 | CPU 模式仅支持单进程训练，文档中明确限制 |

---

## 6. 交付物与验收标准

1. 设备解析与降级模块实现，并在 FastAPI/WebUI/CLI 中统一使用。
2. Kronos 推理代码在 CPU-only 环境运行成功（示例脚本与 FastAPI 请求）。
3. CUDA 专属调用与依赖均具备条件判断或替代实现。
4. Finetune 脚本可在 CPU-only 环境执行最小训练流程。
5. 新增自动化测试覆盖 CPU 场景，CI 通过。

---

## 7. 后续任务与跟踪

- 编写对应实现任务票（TSK/FEA），拆分为：依赖调整、推理改造、服务层支持、训练脚本兼容、测试补充。
- 如需支持 Apple Silicon (MPS) 或多 GPU，更进一步在该设计基础上扩展。
