# DESIGN TICKET 001 - Kronos FastAPI Microservice

**日期**: 2025-10-14  
**状态**: Draft  
**类型**: Service Design

---

## 1. 背景与目标

- 目前 Kronos 预测脚本需在本地或 SSH 环境下直接运行 Python，难以为多台机器提供统一的模型访问接口。
- 目标是设计一个基于 FastAPI 的微服务，封装 KronosTokenizer、Kronos 模型和预测流程，对外提供稳定、可观测、易扩展的推理能力。
- 服务需具备完备的日志与监控方案，支持多实例部署并与现有 DevOps 流程集成。

---

## 2. 功能范围

### 2.1 对外 API
- `POST /v1/predict/single`：接收单时间序列的历史数据与预测窗口，返回预测结果。
- `POST /v1/predict/batch`：接收多条时间序列，执行批量预测。
- `GET /v1/healthz`：基础健康检查，用于探针。
- `GET /v1/readyz`：模型与依赖加载完成后返回成功，避免冷启动期间误接入流量。

### 2.2 配置能力
- 支持通过环境变量或配置文件设置模型 ID、模型文件路径、设备 (CPU/GPU)、默认参数（lookback、pred_len、采样相关参数）。
- 允许在请求中覆盖默认预测参数，并提供输入验证与容错策略（缺失列、异常值）。

### 2.3 日志与可观测性
- 结构化 JSON 日志，包含请求 ID、调用时长、模型版本等关键字段。
- 与标准化日志收集（如 ELK / Loki）兼容，暴露 Prometheus metrics 或集成 OpenTelemetry。
- 支持追踪预测耗时、成功率、输入规模等指标。

---

## 3. 架构设计

### 3.1 模块划分
1. **API 层**：FastAPI 路由、请求体验证（Pydantic）。
2. **Service 层**：封装 KronosPredictor 调用、参数合并、错误处理。
3. **Model 管理**：负责加载并缓存 tokenizer 与模型实例，处理设备放置、并发访问。
4. **Observability 中间件**：日志、追踪、metrics 收集。

### 3.2 启动流程
1. 读取配置（env/config 文件）。
2. 初始化日志系统（结构化 JSON、Loguru 或 Python logging + `uvicorn.access` 统一格式）。
3. 加载 tokenizer 与模型（`from_pretrained`，优先使用本地挂载的 `/models` 目录，缺失时回落到 Hugging Face）。
4. 构建 KronosPredictor 并在 FastAPI `startup` 事件中注册。
5. 暴露健康检查，`readyz` 仅在模型加载完成后返回 200。

### 3.3 部署拓扑
- 推荐以容器方式部署（Docker + Kubernetes/Compose）。
- 单服务无状态，通过配置或 Secrets 提供模型凭据、Hugging Face Token 等。
- 模型权重可通过：
  - 预先打包在镜像内（适用于小模型）。
  - 启动时从对象存储/制品库同步到本地 volume。
- 若需 GPU，使用 NVIDIA CUDA 镜像并暴露必要驱动。

---

## 4. 日志与监控设计

### 4.1 日志
- 统一使用 JSON 格式，字段包括 `timestamp`、`level`、`request_id`、`path`、`latency_ms`、`model_version`、`device`、`result_status`。
- 在请求进入时生成/提取 `request_id`（支持 X-Request-ID），并向下游组件透传。
- 错误日志需记录异常栈、输入摘要（脱敏后的指标，如数据行数、时间范围）。

### 4.2 指标
- 请求计数：`kronos_requests_total{route,status}`。
- 请求耗时直方图：`kronos_request_duration_seconds`。
- 模型推理耗时、模型加载耗时。
- 内存 / GPU 利用率（可通过集成 Node Exporter / DCGM exporter 完成）。

### 4.3 追踪
- 若已有 OpenTelemetry 基础设施，接入 OTEL middleware，传递 trace/span，便于端到端追踪。

---

## 5. 安全与接口治理

- 认证：支持基于 API Key 或 JWT 的轻量认证，通过 FastAPI 依赖实现，可与外部网关对接。
- 限流：在基础层（API 网关 / Envoy / Nginx Ingress）实现 IP 或凭证限流，防止滥用。
- 输入校验：Pydantic 模型限制字段类型、范围（如 lookback 最大值、pred_len <= max_context）。
- 数据保护：日志中避免记录原始 OHLCV 数值，可仅打印统计特征。

---

## 6. 扩展与高可用

- **多实例扩容**：FastAPI 服务无状态，前置负载均衡器（如 Kubernetes Service、NGINX）。
- **并发控制**：根据模型耗时设置线程池 / 进程池大小，必要时引入工作队列（Celery / Dramatiq）。
- **缓存策略**：对重复预测请求可引入短期缓存（Redis），需评估时效性。
- **批处理优化**：在 `predict/batch` 中利用向量化计算，减少模型调用次数。

---

## 7. 未决问题

1. 是否需要支持异步预测（提交任务后返回任务 ID，后台处理）？
2. 生产环境硬件规格（GPU 型号、CPU 核心数、内存）及并发指标目标是什么？
3. 预测数据持久化策略：是否需要将预测结果和日志写入数据库以供审计？
4. 是否需要灰度/多模型版本并存（A/B 测试）？

---

## 8. 后续步骤

1. 明确硬件环境与部署平台，确定模型加载方式。
2. 与平台团队确认日志、监控栈对接方案。
3. 细化 API Contract（请求/响应 schema），输出 OpenAPI 规范草案。
4. 评估并选择日志/metrics/trace 库，实现 PoC。
5. 编写实施计划与里程碑，进入开发阶段。
