# TICKET_004_DES_Docker-HTTPS-Request-Handler

## Ticket Info
- **Type**: DES (Design)
- **Status**: Created
- **Phase**: Phase 2 - Security & Production Hardening
- **Created**: 2025-10-19
- **Related**: TICKET_001_IMP, TICKET_003_DES

---

## Problem Statement

当 Kronos FastAPI 微服务作为 Docker 容器运行时，需要以安全的方式处理来自其他容器或外部客户端的请求。当前实现存在以下问题：

1. **通信协议限制**: 当前服务仅支持 HTTP（非加密），不适合生产环境
2. **容器间通信**: Docker 容器间通常需要通过 HTTPS 进行通信以确保数据机密性
3. **证书管理**: 缺少 TLS/SSL 证书配置和管理机制
4. **请求验证**: 需要在 HTTPS 层面实现请求验证和身份认证

---

## Current Implementation Analysis

### 现有请求处理方式

**协议层**:
- 当前: HTTP 仅支持 (`uvicorn` 不配置 SSL/TLS)
- 启动方式: `./start.sh [PORT] [HOST] [WORKERS]`
  - 默认: `http://0.0.0.0:8000`
  - 无 SSL/TLS 选项

**请求类型** (`routes.py`):
- `POST /v1/predict/single` - 单条预测
- `POST /v1/predict/batch` - 批量预测
- `GET /v1/healthz` - 健康检查
- `GET /v1/readyz` - 就绪检查
- `GET /v1/metrics` - Prometheus 指标

**安全机制** (现有):
- 容器白名单中间件 (`security.py`)
- 按容器名称或 IP 进行访问控制
- 基于 HTTP 请求头 `X-Container-Name`
- 局限: 不支持 TLS 终端协商或证书验证

**配置** (`config.py`):
```python
security_enabled: bool = Field(True, env="KRONOS_SECURITY_ENABLED")
container_whitelist: str = Field(
    "localhost,frontend-app,worker-service,scheduler",
    env="KRONOS_CONTAINER_WHITELIST"
)
```

---

## Design Requirements

### 功能需求 (FR) - Apache2 反向代理方案

| ID | 需求 | 优先级 | 说明 |
|---|---|---|---|
| FR-1 | HTTP 容器服务 | P0 | Docker 容器内仅运行 HTTP (127.0.0.1:8000) |
| FR-2 | HTTPS 由 Apache 终止 | P0 | Apache 处理 TLS/SSL，容器无需配置证书 |
| FR-3 | Apache 反向代理配置 | P0 | 将 `/kronos/` 路径代理到 Docker 容器 |
| FR-4 | 证书自动续期 | P0 | Let's Encrypt 证书由 Apache 自动续期，无需重启 Docker |
| FR-5 | 可选 mTLS | P2 | 在 Apache 层可选配置客户端证书验证 |
| FR-6 | 后向兼容性 | P0 | HTTP localhost 访问支持用于开发/测试 |

### 非功能需求 (NFR)

| ID | 需求 | 说明 |
|---|---|---|
| NFR-1 | 容器简化 | Kronos 容器无需 SSL/TLS 配置，仅运行 HTTP |
| NFR-2 | 安全隔离 | Docker 不暴露到公网，仅通过 Apache 访问 |
| NFR-3 | Apache 配置 | 提供可复用的 Apache VirtualHost 配置 |
| NFR-4 | Docker Compose | docker-compose.yml 配置不需要卷挂载证书 |
| NFR-5 | 性能 | Apache SSL 终止性能高，后端 HTTP 无加密开销 |
| NFR-6 | 可扩展性 | 支持未来添加多个服务到同一 Apache 入口 |

---

## Solution Architecture

### ⭐ 推荐方案：Apache2 反向代理 (SSL 终止)

**架构**:
```
互联网 (HTTPS:443)
    ↓ (TLS 加密)
Apache2 (ai.silvonastream.com)
    ├─ SSL 证书管理 (Let's Encrypt)
    ├─ 证书自动续期 (certbot)
    └─ 反向代理配置
    ↓ (HTTP:127.0.0.1:8000 - 本机通信)
Kronos Docker (仅 HTTP)
    ├─ 无需证书配置
    ├─ 无需 SSL 支持
    └─ 简化的容器部署
```

**优点**:
- ✅ 无需在容器中配置 SSL
- ✅ 证书管理完全由 Apache 处理
- ✅ Let's Encrypt 自动续期，无需重启 Docker
- ✅ SSL 终止提高性能
- ✅ 容器完全隐藏于公网
- ✅ 易于扩展到多服务
- ✅ 业界标准架构

**缺点**:
- 需要在主机 Apache 中配置反向代理
- （相比容器独立管理证书）

**部署难度**: ⭐ 最简单

---

### 备选方案 1: Uvicorn 原生 HTTPS (不推荐)

如果 Apache 不可用，使用此方案。

**优点**:
- 无需额外代理
- 容器自包含

**缺点**:
- 容器需要配置证书
- 证书续期需要重启 Docker
- 性能较低
- 不支持高级特性

**部署难度**: ⭐⭐⭐

---

### 备选方案 2: Nginx 反向代理 (仅当 Apache 不可用)

**优点**:
- 专业级性能
- 支持高级特性

**缺点**:
- 需要额外容器或配置
- 维护复杂度高

**部署难度**: ⭐⭐⭐⭐

---

### 最终决策

✅ **采用 Apache2 反向代理方案** (本 Ticket 实施)

基于以下理由：
1. 用户已有 Apache2 + Let's Encrypt 证书 (ai.silvonastream.com)
2. Docker 与主机在同一机器
3. 无需修改 Kronos 容器代码
4. 最简单、最安全、最可维护

---

## Implementation Design

### 1. Kronos 容器配置（无需 SSL）

**Dockerfile** (简化):
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY gitSource /app

# 安装依赖
RUN pip install -r requirements.txt

# 暴露端口（本机内通信）
EXPOSE 8000

# 仅运行 HTTP（无需 SSL）
CMD ["uvicorn", "services.kronos_fastapi.main:app", \
     "--host", "127.0.0.1", \
     "--port", "8000"]
```

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  kronos:
    image: nona-kronos:latest

    # 不暴露到公网，仅本机通信
    # ports:
    #   - "8000:8000"

    environment:
      KRONOS_DEVICE: cuda:0  # 如果有 GPU
      KRONOS_LOG_LEVEL: INFO

    # 可选：挂载模型目录
    volumes:
      - /data/ws/kronos/models:/data/ws/kronos/models:ro

    networks:
      - local

networks:
  local:
    driver: bridge
```

### 2. Apache2 反向代理配置

**前置条件**:
- Apache2 已安装
- Let's Encrypt 证书已配置在 `/etc/letsencrypt/live/ai.silvonastream.com/`
- mod_proxy 和 mod_proxy_http 已启用

**启用必要模块**:
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod rewrite
```

**配置文件** (`/etc/apache2/sites-available/ai.silvonastream.com.conf`):

编辑现有的 HTTPS VirtualHost，添加以下内容：

```apache
<VirtualHost *:443>
    ServerName ai.silvonastream.com

    # 现有的 SSL 配置
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/ai.silvonastream.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/ai.silvonastream.com/privkey.pem
    SSLCertificateChainFile /etc/letsencrypt/live/ai.silvonastream.com/chain.pem

    # ... 现有网站配置 ...

    # ===== 新增：Kronos 反向代理 =====

    # 启用反向代理
    ProxyPreserveHost On
    ProxyRequests Off

    # Kronos 预测服务代理
    ProxyPass /kronos/ http://127.0.0.1:8000/
    ProxyPassReverse /kronos/ http://127.0.0.1:8000/

    # 设置超时（用于长时间预测）
    ProxyTimeout 300
    ProxyConnect Timeout 10

    # 设置代理连接参数
    <Proxy http://127.0.0.1:8000/*>
        Order allow,deny
        Allow all
    </Proxy>

    # 可选：启用 WebSocket（如果未来需要）
    # RewriteEngine On
    # RewriteCond %{HTTP:Upgrade} websocket [NC]
    # RewriteCond %{HTTP:Connection} upgrade [NC]
    # RewriteRule ^/kronos/(.*)$ "ws://127.0.0.1:8000/$1" [P,L]

</VirtualHost>
```

**测试 Apache 配置**:
```bash
# 验证配置语法
sudo apache2ctl configtest
# 应该输出: Syntax OK

# 重新加载 Apache（无需重启）
sudo systemctl reload apache2

# 查看状态
sudo systemctl status apache2
```

### 3. Docker 启动命令

```bash
# 构建镜像
docker build -t nona-kronos:latest .

# 启动容器
docker-compose up -d

# 验证状态
docker ps
docker logs -f kronos
```

---

## Request Flow

### 公网 HTTPS 请求示例（通过 Apache）

```bash
# 客户端通过 HTTPS 访问 Kronos（通过 Apache 反向代理）
curl -X POST https://ai.silvonastream.com/kronos/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{
    "series_id": "test",
    "candles": [
      {"open": 100, "high": 105, "low": 95, "close": 102},
      {"open": 102, "high": 107, "low": 100, "close": 105}
    ],
    "timestamps": ["2025-01-01T10:00:00Z", "2025-01-01T10:01:00Z"],
    "prediction_timestamps": ["2025-01-01T10:02:00Z"]
  }'
```

**流程**:
1. 客户端 → Apache (HTTPS:443 加密)
2. Apache 验证证书 ✅
3. Apache → Kronos (HTTP:127.0.0.1:8000 本机通信，不加密)
4. Kronos 返回预测结果
5. Apache → 客户端 (HTTPS 加密)

### 本机测试

```bash
# 测试健康检查
curl http://127.0.0.1:8000/v1/healthz
# 返回: {"status":"ok"}

# 通过 Apache 反向代理测试（需要本机访问）
curl https://ai.silvonastream.com/kronos/v1/healthz \
  -k  # --insecure 忽略自签名证书警告（如果需要）
```

### 网站后端集成示例

```python
# 在 ai.silvonastream.com 的网站后端中
import requests

def call_kronos_predict(payload):
    """调用 Kronos 预测服务"""
    try:
        response = requests.post(
            'https://ai.silvonastream.com/kronos/v1/predict/single',
            json=payload,
            verify=True,  # 验证 SSL 证书
            timeout=300  # 5 分钟超时
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Kronos request failed: {e}")
        raise
```

---

## Security Considerations

### Apache SSL 证书管理

1. **Let's Encrypt** (当前 ai.silvonastream.com 使用):
   ```bash
   # 证书路径
   /etc/letsencrypt/live/ai.silvonastream.com/
   ├─ fullchain.pem (完整证书链)
   ├─ privkey.pem (私钥)
   ├─ cert.pem
   └─ chain.pem

   # 自动续期（certbot 已配置）
   sudo certbot renew  # 通常每天自动运行
   ```

2. **证书续期和 Docker**:
   - Apache 证书续期 ✅ 无需重启 Kronos
   - Docker 容器完全不受影响
   - 完全自动化

### 容器网络隔离

**安全优势**:
- ✅ Kronos Docker 仅监听 127.0.0.1:8000（localhost）
- ✅ 不暴露到公网
- ✅ 不暴露到其他网络容器
- ✅ 私钥完全不在容器中

**配置确保**:
```yaml
# docker-compose.yml
services:
  kronos:
    # 不暴露端口到宿主机
    # ports:  ← 完全注释掉
    #   - "8000:8000"

    # 仅本机内通信
    networks:
      - local  # 内部 bridge 网络
```

### Apache 安全配置

在 Apache 配置中添加安全头（可选增强）:
```apache
<VirtualHost *:443>
    # ... 现有配置 ...

    # 安全头
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"

    # 反向代理配置
    ProxyPass /kronos/ http://127.0.0.1:8000/
    ProxyPassReverse /kronos/ http://127.0.0.1:8000/
</VirtualHost>
```

### 可选：mTLS（仅在需要时）

如果需要客户端证书验证：
```apache
# 在 <Proxy> 块中启用 mTLS
SSLVerifyClient require
SSLVerifyDepth 10
SSLCACertificateFile /path/to/client-ca.pem
```

### 防火墙建议

```bash
# 允许 Apache HTTPS
sudo ufw allow 443/tcp

# Docker 内部端口 8000 无需开放到公网
# 本机通信无需防火墙规则
```

---

## Testing Strategy

### 1. Docker 容器测试

- [ ] Docker 镜像成功构建
- [ ] Docker 容器成功启动
- [ ] 容器监听 127.0.0.1:8000
- [ ] 健康检查 `curl http://127.0.0.1:8000/v1/healthz` 成功
- [ ] 容器未暴露到公网端口

### 2. Apache 反向代理测试

- [ ] Apache 配置语法正确 (`apache2ctl configtest`)
- [ ] Apache 模块已启用 (`mod_proxy`, `mod_proxy_http`)
- [ ] Apache 成功重载

### 3. 集成测试

- [ ] **本机 HTTP 访问**: `curl http://127.0.0.1:8000/v1/healthz`
- [ ] **通过 Apache HTTPS**: `curl https://ai.silvonastream.com/kronos/v1/healthz`
- [ ] **预测请求**: 发送完整预测请求，验证正确响应
- [ ] **长时间预测**: 测试超时配置 (ProxyTimeout 300)
- [ ] **错误处理**: 测试异常情况下的代理行为

### 4. 性能测试

- [ ] HTTPS 吞吐量测试 (Apache → Kronos)
- [ ] 反向代理延迟测试 (网络往返时间)
- [ ] 证书续期期间的可用性 (Apache 无需重启)

### 5. 安全测试

- [ ] 防火墙验证: 127.0.0.1:8000 不可从外网访问
- [ ] 证书链验证正确
- [ ] HTTPS 强制 (可选)

---

## Acceptance Criteria

- [ ] **AC-1**: Docker 容器仅监听 127.0.0.1:8000 (HTTP)
  - 验证: `docker exec kronos lsof -i :8000` 显示 127.0.0.1

- [ ] **AC-2**: Apache 反向代理配置完成并生效
  - 验证: `apache2ctl configtest` 返回 "Syntax OK"
  - 验证: `curl https://ai.silvonastream.com/kronos/v1/healthz` 返回 200

- [ ] **AC-3**: HTTPS 预测请求正常工作
  - 验证: 完整的预测请求通过 Apache 返回正确结果
  - 验证: 预测结果与直接访问 HTTP 端口相同

- [ ] **AC-4**: 证书由 Apache 管理，自动续期
  - 验证: `/etc/letsencrypt/live/ai.silvonastream.com/` 证书存在
  - 验证: 证书续期时 Docker 无需重启

- [ ] **AC-5**: 容器网络隔离
  - 验证: 公网无法直接访问 127.0.0.1:8000
  - 验证: Docker 容器 ports 配置为空（无对外暴露）

- [ ] **AC-6**: 本机测试访问正常
  - 验证: `curl http://127.0.0.1:8000/v1/healthz` 返回 200
  - 验证: `curl https://ai.silvonastream.com/kronos/v1/healthz` 返回 200

- [ ] **AC-7**: 错误处理和超时配置
  - 验证: ProxyTimeout 设置为 300 秒
  - 验证: 异常情况下返回适当的 HTTP 错误码

- [ ] **AC-8**: 文档完整
  - 验证: Apache 配置示例清晰
  - 验证: docker-compose.yml 配置说明完整
  - 验证: 测试步骤文档齐全

---

## Dependencies & Risks

### 依赖

**已有 (不需新增)**:
- ✅ Apache2 (已运行)
- ✅ Let's Encrypt 证书 (已配置)
- ✅ Docker & docker-compose (已有)
- ✅ Kronos 代码库

**无需新增依赖**:
- ✅ Kronos 无需新增 Python 包
- ✅ Apache 标准模块即可

### 风险 & 缓解措施

| 风险 | 影响 | 概率 | 缓解 |
|---|---|---|---|
| Apache 配置错误 | 服务不可用 | 低 | 使用 `apache2ctl configtest` 验证 |
| Docker 监听外网 | 安全漏洞 | 低 | 配置清单中强制 127.0.0.1 |
| 证书续期中断 | 临时不可用 | 极低 | Let's Encrypt 已自动化，Apache 无需重启 |
| 反向代理延迟 | 性能下降 | 极低 | Apache 反向代理延迟通常 <1ms |
| Docker 网络隔离失败 | 容器暴露到公网 | 低 | 使用 firewall 规则验证 |

---

## Timeline & Estimation

| 任务 | 工作量 | 预计时间 |
|---|---|---|
| **设计审核** | 1h | Day 1 |
| **Apache 配置** | 1h | Day 1 |
| **Dockerfile 准备** | 0.5h | Day 1 |
| **docker-compose.yml** | 0.5h | Day 1 |
| **Docker 构建和测试** | 2h | Day 1-2 |
| **集成测试** | 2h | Day 2 |
| **文档编写** | 1h | Day 2 |
| **验证和优化** | 1h | Day 2 |
| **总计** | **9h** | **2 天** |

**相比原 Uvicorn SSL 方案节省**: 15h (减少 62%)

---

## Next Steps

### 立即行动

1. ✅ **获取批准** - 该设计文档
2. 📋 **创建 TICKET_005_TSK** - Apache2 反向代理实施任务
   - Apache 配置
   - Docker 镜像构建
   - 集成测试
3. 📋 **创建 TICKET_006_TSK** - 部署和文档任务
   - 部署验收
   - 文档完善
   - 监控配置

### 后续阶段

1. **Phase 3** - 性能优化
   - Apache 缓存配置
   - 连接池优化
   - 负载均衡

2. **Phase 4** - 可观测性
   - Apache 访问日志集成
   - Prometheus 指标暴露
   - 监控告警

3. **Phase 5** - 扩展性
   - 多 Kronos 实例支持
   - 负载均衡器配置
   - 自动扩展

---

## References

- [Uvicorn SSL Documentation](https://www.uvicorn.org/)
- [Python ssl Module](https://docs.python.org/3/library/ssl.html)
- [FastAPI HTTPS](https://fastapi.tiangolo.com/deployment/https/)
- [Docker Networking](https://docs.docker.com/network/)
- [mTLS Explained](https://www.cloudflare.com/learning/ssl/what-is-mtls/)

---

**Status**: Draft
**Owner**: TBD
**Last Updated**: 2025-10-19
