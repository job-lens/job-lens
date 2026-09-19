# 工程架构

## 运行边界

```mermaid
flowchart TB
  users["学员 / 辅导员 · 浏览器"] -->|HTTPS| gateway["Caddy · SPA / API 入口"]
  future["后续小程序 / App"] -.->|同一 API| gateway
  subgraph private["私有服务网络"]
    api["FastAPI · Python 模块化单体"]
    worker["Python worker · 作业租约 / 重试"]
    db[("PostgreSQL 17 · 业务 / 会话 / 通知 / 作业")]
    storage[("私有文件空间 · Local / S3 适配")]
  end
  gateway -->|HTTP /api/v1| api
  api -->|SQL / 事务| db
  worker -->|SKIP LOCKED / 租约| db
  api -->|受控文件 IO| storage
```

容器与存储适配边界；虚线为后续客户端。业务用例由 API 编排，worker 独立领取持久化作业。

## 允许的模块依赖

```mermaid
flowchart LR
  identity["identity"]
  cases["cases"]
  cases -->|public| identity
  sop["sop"]
  sop -->|public| cases
  training["training"]
  training -->|public| cases
  training -->|public| sop
  support["support"]
  support -->|public| cases
  support -->|public| training
```

跨模块只导入 public；core 不依赖基础设施，基础设施不导入业务模块。

## 核心数据关系

```mermaid
erDiagram
  ASSISTANCE_REQUESTS ||--o{ SUPPORT_MESSAGES : references
  CASES ||--o{ ANNOTATIONS : references
  CASES ||--o{ ASSISTANCE_REQUESTS : references
  CASES ||--o{ CASE_GRANTS : references
  CASES ||--o{ SOP_PLANS : references
  CASES ||--o{ TRAINING_TASKS : references
  SOP_PLANS ||--o{ SOP_REVISIONS : references
  SOP_REVISIONS ||--o{ SOP_STEPS : references
  SOP_REVISIONS ||--o| TRAINING_TASKS : references
  SOP_STEPS o|--o{ ASSISTANCE_REQUESTS : references
  SOP_STEPS ||--o{ STEP_PROGRESS : references
  SUBMISSIONS o|--o{ ANNOTATIONS : references
  SUBMISSIONS ||--o| FEEDBACK : references
  TRAINING_TASKS ||--o{ ANNOTATIONS : references
  TRAINING_TASKS o|--o{ ASSISTANCE_REQUESTS : references
  TRAINING_TASKS ||--o{ STEP_PROGRESS : references
  TRAINING_TASKS ||--o{ SUBMISSIONS : references
  USERS ||--o{ ANNOTATIONS : references
  USERS ||--o{ CASE_GRANTS : references
  USERS ||--o{ CASES : references
  USERS ||--o{ FEEDBACK : references
  USERS ||--o{ SOP_PLANS : references
  USERS ||--o{ SUPPORT_MESSAGES : references
```

图示主要外键关系；组合外键、唯一性、部分索引和不可变触发器见迁移。

## 训练状态

```mermaid
stateDiagram-v2
  [*] --> not_started
  not_started --> in_progress: start
  in_progress --> paused: pause
  paused --> in_progress: resume
  in_progress --> submitted: submit
  submitted --> changes_requested: request_changes
  changes_requested --> in_progress: resume
  submitted --> completed: pass
  not_started --> cancelled: cancel
  in_progress --> cancelled: cancel
  paused --> cancelled: cancel
  submitted --> cancelled: cancel
  changes_requested --> cancelled: cancel
  completed --> [*]
  cancelled --> [*]
```

## 部署依赖

```mermaid
flowchart LR
  db["db"]
  migrate["migrate"]
  migrate -->|service_healthy| db
  api["api"]
  api -->|service_completed_successfully| migrate
  worker["worker"]
  worker -->|service_completed_successfully| migrate
  gateway["gateway"]
  gateway -->|service_healthy| api
```

## 接口归属

| 模块 | 契约操作 | 已接入 HTTP |
| --- | ---: | ---: |
| cases | 8 | 0 |
| identity | 9 | 1 |
| infrastructure | 7 | 0 |
| platform | 2 | 2 |
| sop | 7 | 0 |
| support | 12 | 0 |
| training | 10 | 0 |

接口契约覆盖业务范围；健康检查接入 HTTP，业务路由在对应模块后续实现时登记。
