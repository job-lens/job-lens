# 开发说明

## 本地运行

运行时为 Python 3.13、Node.js 24、pnpm 10.11.0；Python 与前端依赖分别由 `uv.lock`、`pnpm-lock.yaml` 锁定。

```bash
cp .env.example .env
uv sync --locked
pnpm install --frozen-lockfile
# 只启动供本机开发使用的数据库，端口仅绑定 loopback。
docker compose -f compose.yaml -f infra/compose.dev.yaml up -d db
export JOB_LENS_DATABASE_URL='postgresql+psycopg://job_lens:local_only@127.0.0.1:5432/job_lens'
export JOB_LENS_PUBLIC_ORIGIN='http://localhost:5173'
make migrate
make api
```

第二个终端运行 `pnpm dev`；worker 使用同样的数据库环境变量后运行 `make worker`。Web 为 `http://localhost:5173`，Vite 将 `/api` 转发到本机 8000 端口。PowerShell 使用 `$env:JOB_LENS_DATABASE_URL="..."` 设置变量；Makefile 的各项可直接替换为文件内对应命令。

## 代码边界

`app/main.py`、`app/bootstrap.py`、`app/worker.py` 是装配入口。后端业务模块包含内部模型、用例服务与 `public.py`；跨模块只允许导入 `architecture.toml` 声明依赖的 `public.py`。路由只调用服务，不直接查询 ORM；服务在最外层 `Database.transaction()` 中统一提交。禁止内部函数独立 commit 和基础设施反向引用业务模块。

前端 `app` 组合页面与 Provider，`features` 保存业务功能，`shared` 保存实际共用组件、请求与设备能力。功能模块通过 `public.tsx` 暴露页面。当前模块间不直接互相依赖；新增依赖必须登记并通过边界检查。

`architecture.toml` 驱动三个产物：路由 `routes.generated.ts`、前端边界清单 `architecture.generated.json`、`docs/architecture.md`。数据关系来自 ORM 外键，状态图来自训练状态表，部署依赖来自 Compose。CI 检查生成差异，不能只改图而不改模型。

## 接口接入流程

产品 HTTP 契约维护在 `contracts/openapi.yaml`，前端调用类型自动生成，禁止手改 `schema.d.ts`。`contracts/implemented.json` 只登记已接入 HTTP 的操作；`runtime.openapi.json` 从 FastAPI 导出，不把未实现操作加入 Swagger。

新增用例依次完成契约、服务及权限测试、路由装配、实现登记和前端联调，再执行：

```bash
make generate
make check
make test
```

契约检查比较方法与路径、必填参数、请求体、认证声明、成功响应及错误媒体类型；负例测试故意修改这些内容，确认检查能够阻断漂移。接口统一 `/api/v1`、snake_case、UUID、UTC/RFC 3339；错误返回 `application/problem+json`。

Cookie 写操作必须校验 CSRF 和 Origin。业务 POST 使用 `Idempotency-Key`，修改已有聚合使用 `If-Match`。幂等缓存读取前重新授权；成功重放先于旧版本检查。一次业务写入、通知、审计与幂等结果放在同一事务，远程副作用不能放进可重放事务回调。

## 数据与运行机制

数据库包含 **27 张关系表、两次冻结迁移**。`0001_foundation` 创建基础结构；`0002_integrity` 增加任务身份保护、持久化字段与事件不可变规则。迁移不导入实时 ORM；API 启动不执行 `create_all`。就绪检查要求数据库已到当前 schema revision。

SOP 发布后内容及步骤不可改写；任务只能从同个案的已发布版本创建，任务的个案和版本引用不能重指派；提交、反馈、消息、审计和观测事件追加保存。组合外键与部分唯一索引约束步骤上下文、当前草稿、活动任务及重复求助。

API 展示对象不直接等于数据库行：`CaseProfile` 组合档案与偏好，各自保留版本；任务内嵌 SOP、当前进度由服务查询组装；提示覆盖投影为 `{prompt_level, reason}`，存储列为 `prompt_override` 与 `prompt_reason`。`estimated_seconds` 的历史空值投影为 0（无预计时长）。`observed_at` 为空的历史事件表示缺失客户端观测时间，不能用接收时间冒充；新事件接口要求客户端提供观测时间。提交说明保存为 `submissions.note`。

通知在事务内锁定接收者计数器并分配顺序号，直到提交才释放；多接收者按 ID 排序加锁。分页游标指向本页最后一项，过期游标返回 410。首版通知由客户端轮询 `GET /notifications` 补拉，不提供服务端推送：同步请求栈上的长连接会占住线程与数据库连接，且多实例后需要额外的跨实例唤醒通道。改回推送需先有实测数据，见 #13。worker 使用 `FOR UPDATE SKIP LOCKED`、自动续租与 lease token，过期 worker 无法回写结果。处理器必须可重试且幂等；失去租约不等于外部副作用自动撤销。当前注册 `system.ping`，文件扫描等处理器随业务用例接入。

文件通过私有 Local / S3 适配器读写，存储键与用户文件名分离。ClamAV 适配器提供真实流式扫描协议；未通过扫描的文件不得转为 ready。现阶段未接入上传 HTTP 与扫描 worker 流程。

## 测试与构建

```bash
make check
make test
# 专用空数据库：名称必须以 _test 结尾；测试会清空其业务表。
JOB_LENS_TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/job_lens_ci_test' uv run pytest -m postgres
pnpm build
# 对已启动的容器栈运行浏览器测试：
E2E_BASE_URL=http://127.0.0.1:8080 pnpm test:e2e
```

PostgreSQL 集成测试包含迁移往返、元数据差异、事务回滚、权限撤销、不可变历史、并发幂等、通知顺序和作业租约。未配置专用库时本地显示 skipped，CI 必须配置并执行。浏览器烟测覆盖真实基础设施连接，身份成功/过期分支使用明确标记的 Mock，不代表账号服务已完成。

## 四人接续开发

| 成员 | 主责 | 入口 |
| --- | --- | --- |
| 刘峥岩 | 总体架构、模块边界与接口变更评审、进度统筹 | 架构清单、契约、代码 PR |
| 贺凡恩 | 业务用例、数据库、后端安全与部署 | `apps/api`、迁移、`infra` |
| 前端 A | 学员端与公共前端 | `features/learner`、`profile`、`shared`、`app` |
| 前端 B | 辅导员端及公共组件共建 | `features/counselor`、`sop`、反馈与辅导页面 |

接续顺序：账号与个案授权 → 资料与匹配 → SOP 发布与训练提交 → 反馈返工 → 求助、文件扫描与通知。每个业务 PR 同时交付权限负例、契约回归和相应页面联调。
