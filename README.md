# 融职境 · Job Lens

面向岗位训练学员与辅导员的双端支持系统。单仓库、React / TypeScript Web、Python / FastAPI 模块化单体和 PostgreSQL；后续小程序、App 复用业务 API 与数据。

## 启动

```bash
git clone --branch feat/architecture-foundation https://github.com/job-lens/job-lens.git
cd job-lens
cp .env.example .env
docker compose up -d --build --wait --wait-timeout 180
```

打开 **http://localhost:8080** 查看真实 API 与数据库连接状态。启动包含 Web 构建、数据库迁移、API、独立 worker 和 Caddy 网关。

```bash
python tools/smoke.py
docker compose exec -T api python tools/worker_smoke.py
```

## 工程入口

| 路径 | 内容 |
| --- | --- |
| `apps/web` | 应用壳、七个功能模块、生成式路由、会话与角色边界、类型化请求、设备适配 |
| `apps/api` | 五个业务模块、公共接口、数据库模型、迁移、事务与异步作业基础设施 |
| `contracts` | 55 个产品操作的 OpenAPI、已接入操作登记、运行时 OpenAPI |
| `architecture.toml` | 模块依赖、前端路由与职责清单 |
| `tools`、`tests` | 架构与契约检查、生成工具、基础设施及浏览器测试 |
| `infra`、`compose.yaml` | 构建、网络、启动顺序、TLS 入口与环境配置 |

[架构图](docs/architecture.md) · [开发说明](docs/development.md) · [部署与恢复](docs/deployment.md) · [贡献规范](CONTRIBUTING.md)

## 当前可执行范围

工程基线已接入健康检查和持久化系统作业，提供可验证的权限、状态、存储与事务基础设施。产品契约为 **44 个路径、55 个操作、64 个模型**；HTTP 当前接入 `health_live`、`health_ready`。登录、SOP 编辑、训练与辅导页面是后续功能开发入口，未使用假成功接口代替业务实现。

## 检查

```bash
uv sync --locked
pnpm install --frozen-lockfile
make check
make test
```

CI 在真实 PostgreSQL 上验证迁移、数据库约束与并发，另执行 React 构建、生成产物差异检查、Docker 启动和 Playwright 烟测。

Apache-2.0 · [License](LICENSE)
