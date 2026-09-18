# 融职境 API 契约

## A. 通用规则

所有业务路径相对于 `/api/v1`。JSON 字段使用 snake_case，资源 ID 使用 UUID，时间使用 UTC/RFC 3339，日期使用 `YYYY-MM-DD`。成功返回对象或分页对象，错误返回 `application/problem+json`。字段类型见 [openapi.yaml](openapi.yaml)。

L 表示资源所属学员，C 表示拥有该个案有效授权的辅导员。请求中的个案、任务、步骤、提交和附件须逐级验证归属。所有写请求检查 CSRF 和 Origin；请求模型拒绝额外字段。

### A.1 请求头与版本

| 请求头 | 规则 |
| --- | --- |
| `X-CSRF-Token` | 所有 Cookie 写请求必需，包括登录、退出。 |
| `Idempotency-Key` | 业务 POST 必需，登录、退出除外；16–128 个可打印 ASCII 字符，同一次操作重试复用原键。 |
| `If-Match` | 更新已有可变聚合和执行状态命令必需，格式如 `"7"`；缺失返回 428，过期返回 412。 |
| `ETag` | 返回当前聚合版本；任务子资源写入使用任务版本。Submission 视图携带 `task_version/task_status`，其 ETag 用于反馈。 |
| `X-Request-ID` | 可选追踪标识，服务端校验并返回 `trace_id`。 |
| `Retry-After` | 用于 429、暂时性 503 和同键操作处理中，客户端按值退避。 |

幂等作用域为主体、方法、规范路径与 key；请求指纹包含语义请求体、附件校验和及版本条件。同键同请求重放原结果，同键不同请求返回 409；重放前重新授权。已成功请求先重放，再判断原 If-Match 是否过期。记录保留 24 小时，发布和提交另受业务唯一约束保护。

PUT 替换该模型定义的可编辑字段。所有权、角色、作者及审核结果由服务端确定。普通列表使用 `limit`（默认 20，最大 100）和不透明 `cursor`，返回 `items / next_cursor / has_more`；以 `created_at + id` 稳定排序，游标绑定筛选条件。授权过滤在分页前执行。

### A.2 错误与处理

| HTTP | code 或条件 | 客户端处理 |
| --- | --- | --- |
| 400 / 422 | 请求语义或字段校验失败。 | 保留输入，定位错误字段。 |
| 401 | 未登录或会话失效。 | 重新登录。 |
| 403 / 404 | 禁止操作 / 不存在或无读取权。 | 关闭操作入口或显示资源不可访问。 |
| 409 | 状态、业务唯一性、幂等冲突。 | 按 code 处理，禁止盲重试。 |
| 410 | `CURSOR_EXPIRED`。 | 重置通知游标并读取当前业务对象。 |
| 412 / 428 | `VERSION_CONFLICT` / 缺少前置版本。 | 获取新版本，确认后重新提交。 |
| 413 / 415 | 文件过大 / 类型不支持。 | 更换符合要求的文件。 |
| 429 / 503 | 限流 / 临时依赖失败。 | 按 Retry-After 退避。 |

```json
{
  "type": "urn:job-lens:problem:version-conflict",
  "title": "资源已更新",
  "status": 412,
  "code": "VERSION_CONFLICT",
  "detail": "请刷新任务，确认最新反馈后再操作。",
  "trace_id": "req_example_001",
  "errors": [{"field": "If-Match", "reason": "expected_current_version"}]
}
```

客户端按稳定 `code` 分支，`detail` 用于展示。错误不返回 SQL、令牌、存储路径或内部堆栈。

## B. 接口目录

“版本”表示携带 If-Match；业务 POST 同时携带幂等键。M1 为工程骨架，M2 为业务闭环，M3 为辅导与试用功能。
### B.1 公共、登录与本人资料

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| GET `/health/live` | — → 200 Health | 匿名 / M1 |
| GET `/health/ready` | — → 200 Health | 匿名 / M1 |
| GET `/auth/csrf` | — → 200 CsrfToken | 匿名 / M2 |
| POST `/auth/login` | LoginRequest → 200 LoginResult | 匿名 / M2 |
| POST `/auth/logout` | — → 204 | 本人 / M2 |
| GET `/me` | — → 200 User | 本人 / M2 |
| GET `/me/preferences` | — → 200 Preferences | 本人 / M2 |
| PUT `/me/preferences` | PreferencesWrite → 200 Preferences | 本人；版本 / M2 |
| GET `/me/profile` | — → 200 Profile | 本人 / M2 |
| PUT `/me/profile` | ProfileWrite → 200 Profile | 本人；版本 / M2 |
| GET `/capabilities` | — → 200 Capabilities | 本人 / M2 |
| GET `/dashboard` | — → 200 Dashboard | L/C / M2 |

`GET /dashboard` 的 view 为 learner/counselor，只允许当前主体已有角色；计数按权限和业务状态派生。`GET /capabilities` 返回服务端功能开关，客户端仍需检测本机能力。`/health/ready` 依赖未就绪时返回 503。

登录流程为 GET `/auth/csrf` → POST `/auth/login` → 轮换会话；CSRF 响应禁止缓存，HttpOnly 会话令牌不返回 JavaScript。

### B.2 个案、匹配与记录

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| GET `/cases` | — → 200 CasePage | L/C / M2 |
| GET `/cases/{case_id}` | — → 200 Case | L/C / M2 |
| GET `/cases/{case_id}/profile` | — → 200 Profile | L/C / M2 |
| GET `/cases/{case_id}/materials` | — → 200 FilePage | L/C / M2 |
| GET `/cases/{case_id}/match` | — → 200 SupportMatch | L/C / M2 |
| PUT `/cases/{case_id}/match` | MatchWrite → 200 SupportMatch | C；版本 / M2 |
| POST `/cases/{case_id}/match/confirm` | — → 200 SupportMatch | C；版本 / M2 |
| GET `/cases/{case_id}/records` | — → 200 RecordPage | L/C / M3 |

`GET /cases` 支持 state、limit、cursor；资料和记录列表支持分页。受控开户初始化个案与匹配草稿。确认匹配前 direction、focus、basis 非空，周期合法且辅导员授权有效；确认后的内容不直接覆盖。

**资料响应待补：**`GET /cases/{case_id}/profile` 增加只读 `preferences: Preferences` 投影，供辅导员查看字号、音量和提示方式；现有 OpenAPI 尚未包含该字段，由贺凡恩与 A/B 在接口联评时同步。

### B.3 私有文件

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| POST `/files` | FileUpload → 202 FileAsset | L/C / M2 |
| GET `/files/{file_id}` | — → 200 FileAsset | L/C / M2 |
| DELETE `/files/{file_id}` | — → 204 | 上传者；未引用；版本 / M2 |
| GET `/files/{file_id}/content` | — → 200 二进制文件 | L/C / M2 |

上传采用 multipart：purpose、case_id、file 必填，task_id 按用途关联。purpose 为 profile_material、task_evidence、sop_media、support_message。202 返回隔离文件记录；GET 状态为 ready 后方可读取和关联。待扫描返回 `FILE_NOT_READY`，已引用文件删除返回 `FILE_IN_USE`。

图片上限 10 MiB，PDF/DOCX 上限 20 MiB；读取返回实际 MIME 和安全 disposition，不暴露存储键。PDF/DOCX 标注使用独立截图。

### B.4 SOP 与不可变发布

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| GET `/cases/{case_id}/sop-plans` | — → 200 PlanPage | L/C / M2 |
| POST `/cases/{case_id}/sop-plans` | PlanCreate → 201 SopPlan | C / M2 |
| GET `/sop-plans/{plan_id}` | — → 200 SopPlan | L/C / M2 |
| POST `/sop-plans/{plan_id}/revisions` | RevisionCreate → 201 SopRevision | C / M2 |
| GET `/sop-revisions/{revision_id}` | — → 200 SopRevision | L/C / M2 |
| PUT `/sop-revisions/{revision_id}` | RevisionWrite → 200 SopRevision | C；版本 / M2 |
| POST `/sop-revisions/{revision_id}/publish` | PublishRequest → 200 Publication | C；版本 / M2 |

创建计划同时建立初始草稿；新增版本可从同计划已发布版本复制，最多一份当前草稿。学员只能读取发布版和历史任务引用版，不返回 `draft_revision_id`。

草稿允许未完成的目标和步骤；发布要求目标非空、1–100 个完整步骤、步骤 ID/顺序唯一、提醒配置有效、素材 ready。发布原子冻结版本并创建任务；重复发布返回原任务，存在非终态任务返回 `ACTIVE_TASK_EXISTS`。`due_on=null` 表示未设截止日期。

### B.5 训练、提交与反馈

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| GET `/tasks` | — → 200 TaskPage | L/C / M2 |
| GET `/tasks/{task_id}` | — → 200 Task | L/C / M2 |
| POST `/tasks/{task_id}/actions` | TaskAction → 200 Task | L 开始/暂停/继续；C 取消；版本 / M2 |
| PUT `/tasks/{task_id}/steps/{step_id}` | ProgressWrite → 200 Task | L；版本 / M2 |
| POST `/tasks/{task_id}/events` | EventBatch → 200 EventReceipt | L / M3 |
| GET `/tasks/{task_id}/submissions` | — → 200 SubmissionPage | L/C / M2 |
| POST `/tasks/{task_id}/submissions` | SubmissionCreate → 201 Submission | L；版本 / M2 |
| GET `/submissions/{submission_id}` | — → 200 Submission | L/C / M2 |
| POST `/submissions/{submission_id}/feedback` | FeedbackCreate → 201 FeedbackResult | C；版本 / M2 |
| PUT `/tasks/{task_id}/prompt-override` | PromptOverrideWrite → 200 Task | C；版本 / M3 |

任务列表支持 status、case_id、limit、cursor。学员可 start/pause/resume，辅导员可 cancel 且必须填写 reason。步骤写入检查当前可执行步骤、任务版本和附件归属。完成所有必需步骤后，后端从已保存进度生成提交快照。

反馈仅审核最新未审提交。`changes_requested` 必须给出本版本返工步骤；`passed` 的 `redo_step_ids` 必须为空。主反馈 message 为 1–500 字符，快捷标签作为补充。提交保留原附件与进度，返工只重置指定步骤。

事件每批最多 100 条，按 event_id 去重，同 ID 不同内容返回冲突。time_sample 为会话内步骤累计毫秒，取最高有效 sequence 的值再跨会话汇总；求助次数取服务端求助记录。提示覆盖只调整当前任务文字提示等级，个人安静设置优先。

### B.6 标注与上下文求助

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| GET `/tasks/{task_id}/annotations` | — → 200 AnnotationPage | L/C / M3 |
| POST `/tasks/{task_id}/annotations` | AnnotationCreate → 201 Annotation | L 提问 / C 指引 / M3 |
| GET `/annotations/{annotation_id}` | — → 200 Annotation | L/C / M3 |
| PUT `/annotations/{annotation_id}` | AnnotationWrite → 200 Annotation | 标注作者；草稿；版本 / M3 |
| POST `/annotations/{annotation_id}/publish` | — → 200 Annotation | 标注作者；草稿；版本 / M3 |
| GET `/assistance-requests` | — → 200 AssistancePage | L/C / M3 |
| POST `/assistance-requests` | AssistanceCreate → 201 Assistance | L / M3 |
| GET `/assistance-requests/{request_id}` | — → 200 Assistance | L/C / M3 |
| POST `/assistance-requests/{request_id}/actions` | AssistanceAction → 200 Assistance | C 接单/解决；L 取消；版本 / M3 |
| GET `/assistance-requests/{request_id}/messages` | — → 200 MessagePage | L/C / M3 |
| POST `/assistance-requests/{request_id}/messages` | MessageCreate → 201 SupportMessage | L/C / M3 |

标注素材必须为 ready 图片且属于同一任务/提交；学员创建 question，辅导员创建 guidance。草稿仅作者可见和编辑，发布后参与者可读且内容不可变；修改草稿不得换图或更换上下文。

求助列表支持 state、case_id、limit、cursor。同个案/任务已有 queued 或 accepted 请求时返回 `ASSISTANCE_ALREADY_OPEN` 与可读取的 request_id。C 可 accept/resolve；L 可 cancel 未解决请求。消息须有非空白正文或有效附件，已结束请求禁止追加。

### B.7 通知

| 方法与路径 | 请求 → 响应 | 权限 / 阶段 |
| --- | --- | --- |
| GET `/notifications` | — → 200 NotificationPage | 本人 / M3 |
| GET `/notifications/stream` | — → 200 SSE | 本人 / M3 |
| POST `/notifications/{notification_id}/read` | — → 204 | 本人 / M3 |

`GET /notifications` 使用 after_seq（默认字符串 `"0"`）与 limit；响应为 items、next_seq、has_more。非零游标过期返回 410；next_seq 为最后已返回序号，无新项时保持原序号。

SSE 同时收到 after_seq 与 Last-Event-ID 时，后者优先。订阅前鉴权失败返回 HTTP 错误；连接建立后会话失效发送 session_expired 并关闭。EventSource 无法读取具体 HTTP 错误时，通过普通通知接口检查会话/游标后重连。

```text
id: 42
event: notification
data: {"id":"00000000-0000-4000-8000-000000000042","seq":"42","type":"feedback.created","resource_type":"submission","resource_id":"00000000-0000-4000-8000-000000000008","created_at":"2026-09-19T01:00:00Z","read_at":null}

: heartbeat
```

客户端按通知 ID 去重，再按资源引用读取对象。通知已读不改变任务状态；连接失败不触发业务写入重试。

## C. 请求模型

以下字段除注明外均必填；允许 null 的字段仍须显式传入。数组元素 ID 均为 UUID，请求拒绝额外字段。

### C.1 个人界面偏好（PreferencesWrite）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| font_scale | 是 | 数值；枚举：1, 1.25, 1.5 |
| volume | 是 | 数值；最小 0，最大 1 |
| quiet_mode | 是 | 布尔 |
| speech_enabled | 是 | 布尔 |
| vibration_enabled | 是 | 布尔 |

### C.2 个人资料（ProfileWrite）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| display_name | 是 | 字符串；最短 1，最长 80 |
| sensory_preferences | 是 | 数组；元素 字符串；最短 1，最长 40；最多 10 |
| communication_preference | 是 | 字符串；最长 200 |
| work_notes | 是 | 字符串；最长 1000 |

### C.3 支持匹配草稿（MatchWrite）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| direction | 是 | 字符串；最长 80 |
| focus | 是 | 字符串；最长 500 |
| cycle_weeks | 是 | 整数；最小 1，最大 52 |
| basis | 是 | 字符串；最长 1000 |

### C.4 SOP 草稿（RevisionWrite）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| goal | 是 | 字符串；最长 1000 |
| steps | 是 | 数组；元素 SopStep；最多 100 |
| reminder | 是 | Reminder |

### C.5 单个步骤（SopStep）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| id | 是 | 字符串（uuid） |
| position | 是 | 整数；最小 1，最大 100 |
| instruction | 是 | 字符串；最长 2000 |
| media_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |
| estimated_seconds | 是 | 整数；最小 0，最大 86400 |
| evidence_required | 是 | 布尔 |

### C.6 任务状态命令（TaskAction）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| action | 是 | 字符串；枚举：start, pause, resume, cancel |
| reason | 否 | 字符串；最长 500 |

### C.7 步骤进度（ProgressWrite）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| status | 是 | 字符串；枚举：in_progress, completed |
| attachment_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |

### C.8 提交结果（SubmissionCreate）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| note | 是 | 字符串；最长 500 |

### C.9 主反馈（FeedbackCreate）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| outcome | 是 | 字符串；枚举：passed, changes_requested |
| message | 是 | 字符串；最短 1，最长 500 |
| tags | 是 | 数组；元素 字符串；枚举：title_correct, naming_adjustment, retake_required, other；最多 5 |
| redo_step_ids | 是 | 数组；元素 字符串（uuid）；最多 100 |
| annotation_ids | 是 | 数组；元素 字符串（uuid）；最多 20 |

### C.10 创建二维标注（AnnotationCreate）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| asset_id | 是 | 字符串（uuid） |
| submission_id | 是 | string / null（uuid） |
| kind | 是 | 字符串；枚举：question, guidance |
| markers | 是 | 数组；元素 Marker；至少 1，最多 100 |

### C.11 创建求助（AssistanceCreate）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| case_id | 是 | 字符串（uuid） |
| task_id | 是 | string / null（uuid） |
| step_id | 是 | string / null（uuid） |
| message | 是 | 字符串；最短 1，最长 500 |
| attachment_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |
| preferred_mode | 是 | 字符串；枚举：text, annotation |

### C.12 追加消息（MessageCreate）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| body | 是 | 字符串；最长 2000 |
| attachment_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |

### C.13 观测事件（TaskEvent）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| event_id | 是 | 字符串（uuid） |
| session_id | 是 | 字符串（uuid） |
| sequence | 是 | 整数；最小 1，最大 2147483647 |
| step_id | 是 | 字符串（uuid） |
| kind | 是 | 字符串；枚举：hint_requested, self_reported_error, time_sample |
| value | 是 | 整数；最小 0，最大 86400000 |
| observed_at | 是 | 字符串（date-time） |

### C.14 任务提示覆盖（PromptOverrideWrite）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| prompt_level | 是 | 整数；最小 1，最大 3 |
| reason | 是 | 字符串；最短 1，最长 500 |

### C.15 标注几何与核心响应

| 对象 | 字段与约束 |
| --- | --- |
| PointMarker | id、shape=point、x、y、text。坐标 0–1，text 长度 1–200；不能混入 width/height。 |
| RectMarker | 上述字段加 width、height；两者 >0 且 ≤1；还要验证 x+width≤1、y+height≤1。 |
| Task | id、case_id、learner_id、title、固定 revision、status、due_on、current_step_id、progress、prompt_override、version。 |
| Submission | id、task_id、attempt_no、revision_id、note、不可变 snapshot、submitted_at，以及当前父任务 task_version/task_status 和对应 feedback。 |
| FileAsset | id、归属、purpose、filename、mime_type、size_bytes、扫描 state/reason、图像 width/height、version、created_at；不返回私有 storage_key。 |
| Notification | id、字符串 seq、type、resource_type/id、created_at、read_at；事件只带资源引用，再按权限读取对象。 |

## D. 请求示例

### D.1 发布 SOP

```http
POST /api/v1/sop-revisions/00000000-0000-4000-8000-000000000201/publish
Content-Type: application/json
X-CSRF-Token: <csrf>
Idempotency-Key: publish-example-0001
If-Match: "7"

{"due_on":"2026-09-20"}
```

```json
{
  "revision_id":"00000000-0000-4000-8000-000000000201",
  "task_id":"00000000-0000-4000-8000-000000000301",
  "published_at":"2026-09-19T01:00:00Z"
}
```

### D.2 反馈返工

```json
{
  "outcome":"changes_requested",
  "message":"请补充文件名中的日期，然后重新提交截图。",
  "tags":["naming_adjustment"],
  "redo_step_ids":["00000000-0000-4000-8000-000000000101"],
  "annotation_ids":[]
}
```

### D.3 创建标注

```json
{
  "asset_id":"00000000-0000-4000-8000-000000000401",
  "submission_id":"00000000-0000-4000-8000-000000000501",
  "kind":"guidance",
  "markers":[{
    "id":"00000000-0000-4000-8000-000000000601",
    "shape":"rect",
    "x":0.12,"y":0.7,"width":0.65,"height":0.12,
    "text":"在文件名末尾补上日期。"
  }]
}
```

## E. 扩展接口

以下接口在对应能力立项时补充到 OpenAPI。

| 能力 | 接口 | 关键约束 |
| --- | --- | --- |
| 平台身份 | POST `/auth/exchanges/{provider}` | 一次性 code、防重放、应用标识与回调校验；绑定同一内部 user_id。 |
| 通话 | POST `/assistance-requests/{id}/calls`；GET `/calls/{id}`；POST `/calls/{id}/actions` | 参与者由支持关系确定；独立维护邀请、接听、连接、结束和失败状态；HTTP 接受与媒体连接分开。 |
| 入会与回调 | POST `/calls/{id}/join-token`；POST `/integrations/rtc/events` | 单房间短期凭据；回调验签、去重、防重放与乱序处理；媒体不经过业务 API。 |
| 辅导纪要 | POST/GET `/calls/{id}/notes` | 记录作者、内容与修订；默认不录制。 |
| SOP 转换 | POST `/sop-plans/{id}/conversion-jobs`；GET `/conversion-jobs/{id}` | 授权输入、固定输出 Schema、超时与费用控制；仅产生待确认草稿，复用原发布流程。 |
| 企业报告 | POST `/cases/{id}/report-exports`；GET `/report-exports/{id}` | 接收者与字段白名单、授权、有效期、撤回及下载审计。 |
| 重复训练 | POST `/tasks/{id}/repetitions` | 新任务实例、排期、并行限制与统计口径。 |
| GPS / 实时 AR | 独立位置与空间锚点契约。 | 用途、保留、授权失败、世界坐标、跟踪丢失及设备兼容。 |
