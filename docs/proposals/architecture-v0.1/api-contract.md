# 融职境 API 契约说明 v0.1

> 状态：Proposed；关联 #5；配套 [系统架构](architecture.md) 与 [OpenAPI](openapi.yaml)。
> M2/M3 是建议实施工作包，不表示接口已经存在。本文件与 OpenAPI 描述的是提案；上线前须经过后端和两名前端的联合评审。

## A. 通用协议

### A.1 命名、身份与返回值

下列路径均相对于 `/api/v1`。资源 ID 为 UUID；用户可读编号不作为授权凭据。JSON 字段用 snake_case；时间用 UTC/RFC 3339，业务日期用 YYYY-MM-DD。成功返回对象或分页对象，错误返回 `application/problem+json`；不得用 HTTP 200 伪装失败。

角色缩写 L=学员，C=辅导员。表中的 C 始终表示“拥有该个案有效授权的辅导员”，不表示全部辅导员。表中的 L 始终表示“该对象所属学员”。业务对象 ID、文件 ID、步骤 ID 必须交叉验证所属个案和任务；列表查询、消息和通知也执行授权。

OpenAPI 使用 Web Cookie security scheme。未来 Bearer/平台身份兑换不列为当前实现端点；扩展时仍解析为同一内部主体与资源授权，不复制业务表。

### A.2 请求头与错误

| 项目 | 契约 |
| --- | --- |
| `X-CSRF-Token` | 除获取 CSRF、GET 查询和健康检查外，所有 Cookie 写请求必需，包括登录/退出。服务端另检查 Origin。 |
| `Idempotency-Key` | 业务 POST 必需，16–128 个可打印 ASCII 字符；登录/退出除外。键由客户端为一次用户操作生成，失败重试复用，不按重试次数更换。 |
| `If-Match` | 修改已有可变聚合及执行有状态命令必需，格式如 `"7"`；无前置条件返回 428，版本过期返回 412。 |
| `ETag` | 返回对应聚合版本。任务子资源命令使用最近 Task/Submission 视图返回的任务 ETag；反馈读取视图包含 task_version，因此其表示版本可随父任务改变。 |
| `X-Request-ID` | 可选诊断相关 ID；服务端不盲信其值，验证后生成/回传 trace_id；不可用作幂等键或用户身份。 |
| `Retry-After` | 429、暂时性 503 和同键操作正在处理时使用。客户端退避重试，不无限循环。 |

标准失败状态：400 请求语义错误；401 未认证/会话失效；403 已知对象但禁止该操作；404 不存在或无读取权限；409 状态冲突/业务唯一约束/同幂等键不同请求；410 通知游标过期；412 版本不匹配；413 文件过大；415 不支持的文件类型；422 字段/跨字段校验失败；428 缺少版本前置条件；429 限流；503 依赖暂不可用。[架构参考 R6、R19]

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

客户端展示稳定中文说明与可执行下一步，不暴露 SQL、令牌、完整文件路径或内部堆栈。`detail` 可本地化，业务分支必须依据 `code`。

### A.3 幂等、并发和分页

幂等记录以当前主体、方法、规范路径和 key 为作用域；指纹包含语义请求体、附件校验和及关联版本条件。同键同请求重放原结果，同键不同请求返回 409；授权必须在每次重放前重新验证。已完成同键操作先重放，再考虑原 If-Match 已过期，避免成功提交在网络重试时被误报失败。建议保留 24 小时；即使过期，发布和提交仍由数据库业务唯一约束兜底。

全量 PUT 只替换其定义的可编辑字段，不允许通过额外字段写入 user_id、role、status 或 author_id。请求模型拒绝未声明字段；响应模型按契约过滤敏感字段。一个业务用例内的状态、通知与审计同事务提交。

普通列表参数为 `limit`（默认 20，1–100）和不透明 `cursor`；响应为 `items / next_cursor / has_more`。排序以 created_at、id 稳定排序；游标绑定筛选条件，变更筛选需从头获取。通知采用独立的 after_seq/next_seq 机制。服务端先按授权过滤再分页，不能先取全量再在前端隐藏。

### A.4 安全启动流程

受控发放账号时创建 user、profile、preferences；学员同时建立 case 和空 draft support_match，并由授权流程配置待匹配 case_grant。这个引导流程解释为什么辅导员在匹配确认前就有权看被分配个案。首版不提供公共自助注册、任意用户列表或任意个案认领 API；以后增加时另行设计资格与授权规则。

浏览器先 GET `/auth/csrf`，取得短时预登录会话和 CSRF 值，再 POST `/auth/login`。登录成功轮换会话，返回 User 与新的 CSRF 值，不把 HttpOnly 会话令牌返回给 JavaScript。登录限流按账号和来源组合，错误不区分“账号不存在/密码错误”。这些时限与限流阈值是工程建议，试用前测试并定案。

## B. 核心与支持接口目录

表中的输入/输出名称与 OpenAPI components/schemas 对应；“—”表示无请求体或无成功响应体。`版本`表示需要 If-Match；业务 POST 同时需要幂等键。

### B.1 公共、登录与本人资料

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| GET `/health/live` | — → 200 Health | 匿名；不暴露版本、配置和依赖凭据。 | M1 |
| GET `/health/ready` | — → 200 Health / 503 Problem | 匿名最小状态；数据库未就绪返回 503。 | M1 |
| GET `/auth/csrf` | — → 200 CsrfToken | 匿名/当前会话；Cache-Control:no-store。 | M2 |
| POST `/auth/login` | LoginRequest → 200 LoginResult | 匿名 + CSRF；服务端授予角色，请求无 role 字段。 | M2 |
| POST `/auth/logout` | — → 204 | 当前会话 + CSRF；撤销会话并清 Cookie。 | M2 |
| GET `/me` | — → 200 User | 当前主体；不接受 user_id 替身参数。 | M2 |
| GET `/me/preferences` | — → 200 Preferences | 本人；返回 ETag。 | M2 |
| PUT `/me/preferences` | PreferencesWrite → 200 Preferences | 本人 + 版本；辅导员不得代写学员安静模式。 | M2 |
| GET `/me/profile` | — → 200 Profile | 本人；返回 ETag。 | M2 |
| PUT `/me/profile` | ProfileWrite → 200 Profile | 本人 + 版本；不含临床评分和身份证明。 | M2 |
| GET `/capabilities` | — → 200 Capabilities | 已登录；返回服务端功能开关，不代替本机能力检测。 | M2 |
| GET `/dashboard` | view → 200 Dashboard | view=learner/counselor；只允许主体已有角色，计数按权限实时派生。 | M2 |

### B.2 个案、匹配、资料与记录

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| GET `/cases` | limit/cursor/state → 200 CasePage | L 仅本人；C 仅已分配个案。 | M2 |
| GET `/cases/{case_id}` | — → 200 Case | L/C；显示状态派生，不提供任意 status PATCH。 | M2 |
| GET `/cases/{case_id}/profile` | — → 200 Profile | L/C；仅支持所需字段，C 只读。 | M2 |
| GET `/cases/{case_id}/materials` | limit/cursor → 200 FilePage | L/C；本人可见上传状态，C 仅可读 ready 资料。 | M2 |
| GET `/cases/{case_id}/match` | — → 200 SupportMatch | L/C；匹配草稿由受控个案建立流程初始化。 | M2 |
| PUT `/cases/{case_id}/match` | MatchWrite → 200 SupportMatch | C + 版本；仅 draft，confirmed 不可静默改。 | M2 |
| POST `/cases/{case_id}/match/confirm` | — → 200 SupportMatch | C + 版本；方向/依据非空、周期合法、资格有效。 | M2 |
| GET `/cases/{case_id}/records` | limit/cursor → 200 RecordPage | L/C；记录为任务/提交事实，不返回未定义能力评分。 | M3 |

### B.3 私有文件

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| POST `/files` | multipart FileUpload → 202 FileAsset | L/C；purpose、case_id、可选 task_id、file；任务材料必须同个案。 | M2 |
| GET `/files/{file_id}` | — → 200 FileAsset | 上传者或可读所属上下文的 L/C；返回状态，不暴露 storage_key。 | M2 |
| GET `/files/{file_id}/content` | — → 200 binary | L/C 且文件 ready；按文件实际 MIME、安全 disposition 返回；不是公开链接。 | M2 |
| DELETE `/files/{file_id}` | — → 204 | 上传者 + 版本；仅未被业务引用文件可删，否则 409 FILE_IN_USE。 | M2 |

文件用途枚举：profile_material、task_evidence、sop_media、support_message。类型、体积和安全规则见架构第 7.3 节。隔离文件不得通过 content 下载；待扫描返回 409 FILE_NOT_READY，拒绝文件返回可理解的 reason。客户端不得凭一个 file_id 将其他学员的文件挂到自己的任务上。

首版文件下载采用授权后端流，不承诺 Range/视频在线播放/文档解析；后续视频接入时补充 Range 与受控媒体能力。图片用已归一化的展示文件；PDF/DOCX 可下载，但标注需要另外上传截图。孤立文件按批准策略清理。

### B.4 SOP 与不可变发布

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| GET `/cases/{case_id}/sop-plans` | limit/cursor → 200 PlanPage | C 可见草稿元数据；L 仅已发布计划。 | M2 |
| POST `/cases/{case_id}/sop-plans` | PlanCreate → 201 SopPlan | C；创建计划及初始空草稿版本。 | M2 |
| GET `/sop-plans/{plan_id}` | — → 200 SopPlan | L/C；学员响应不暴露 draft_revision_id。 | M2 |
| POST `/sop-plans/{plan_id}/revisions` | RevisionCreate → 201 SopRevision | C；可从本计划已发布版复制；至多一份当前草稿。 | M2 |
| GET `/sop-revisions/{revision_id}` | — → 200 SopRevision | C 可读本个案草稿；L 仅已发布/关联历史任务版本。 | M2 |
| PUT `/sop-revisions/{revision_id}` | RevisionWrite → 200 SopRevision | C + 版本；整体保存草稿，校验步骤 ID/顺序唯一。 | M2 |
| POST `/sop-revisions/{revision_id}/publish` | PublishRequest → 200 Publication | C + 版本；原子冻结版本并产生唯一任务。 | M2 |

计划是内容的组织对象，版本是实际训练内容。RevisionWrite 允许空步骤/空目标以保存未完成草稿，但 publish 必须校验 1–100 个完整步骤、非空目标、提示配置和 ready 素材。estimated_seconds 是建议时长，不是超时处罚或自动失败阈值。

同一发布版本重复请求必须返回同一任务引用；与原发布请求内容冲突时返回 409。若个案已有非终态任务，返回 ACTIVE_TASK_EXISTS；旧任务不会被后台“升级”。多任务并行与重复训练另待 Q03 定案。

### B.5 训练、事件、提交与反馈

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| GET `/tasks` | limit/cursor/status/case_id → 200 TaskPage | L/C；按授权过滤。 | M2 |
| GET `/tasks/{task_id}` | — → 200 Task | L/C；包含固定 revision、进度和任务 ETag。 | M2 |
| POST `/tasks/{task_id}/actions` | TaskAction → 200 Task | L 可 start/pause/resume；C 可 cancel 且必填 reason；版本必需。 | M2 |
| PUT `/tasks/{task_id}/steps/{step_id}` | ProgressWrite → 200 Task | L + 任务版本；只能更新该任务可执行步骤，附件必须 ready。 | M2 |
| POST `/tasks/{task_id}/events` | EventBatch → 200 EventReceipt | L；最多 100 条；event_id 去重，同 ID 不同内容冲突。 | M3 |
| GET `/tasks/{task_id}/submissions` | limit/cursor → 200 SubmissionPage | L/C；全部历史尝试。 | M2 |
| POST `/tasks/{task_id}/submissions` | SubmissionCreate → 201 Submission | L + 任务版本；所有必需步骤完成、附件合规；锁定提交。 | M2 |
| GET `/submissions/{submission_id}` | — → 200 Submission | L/C；不可变快照 + 当前 task_version/task_status + 对应反馈。 | M2 |
| POST `/submissions/{submission_id}/feedback` | FeedbackCreate → 201 FeedbackResult | C + 最近 Submission 视图 ETag；仅当前待审提交，禁止双重审核。 | M2 |
| PUT `/tasks/{task_id}/prompt-override` | PromptOverrideWrite → 200 Task | C + 任务版本；只调整当前任务文本提示等级，安静偏好优先。 | M3 |

TaskAction 不是通用状态设置器。服务端根据 actor、当前状态和 action 校验转移。不能通过跳过步骤或随意设置 current_step_id 完成任务。提交时后端读取已保存进度组装快照；请求不接受客户端伪造完整审核快照。

FeedbackCreate.outcome 为 passed 或 changes_requested。后者必须包含至少一个本版本 redo_step_id；前者 redo_step_ids 必须为空。changes_requested 只重置指定步骤，旧提交保留原附件与进度。主反馈 message 必填且不超过 500 字符，快捷标签是补充，不替代可操作说明。

事件仅为观测，不直接改变任务完成状态。kind 为 hint_requested、self_reported_error、time_sample；time_sample.value 为同一 session_id、step_id 的累计毫秒，按最大有效 sequence 的样本取值后跨会话汇总，不把每个累计值相加。缺失、重复、晚到与不可信客户端时间须标注；不将其作为精确考核或临床评价。求助次数从服务端成功创建的求助记录派生，避免与客户端事件重复计数。

### B.6 二维标注与上下文求助

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| GET `/tasks/{task_id}/annotations` | limit/cursor → 200 AnnotationPage | L/C；L 只能看到已发布指引及自己草稿。 | M3 |
| POST `/tasks/{task_id}/annotations` | AnnotationCreate → 201 Annotation | C 创建 guidance；L 创建 question；素材及提交必须同上下文。 | M3 |
| GET `/annotations/{annotation_id}` | — → 200 Annotation | 作者可读草稿，参与者可读 published；返回 ETag。 | M3 |
| PUT `/annotations/{annotation_id}` | AnnotationWrite → 200 Annotation | 作者 + 版本；仅 draft，不能换原图或上下文。 | M3 |
| POST `/annotations/{annotation_id}/publish` | — → 200 Annotation | 作者 + 版本；坐标有效、文字非空；发布后不可变。 | M3 |
| GET `/assistance-requests` | limit/cursor/state/case_id → 200 AssistancePage | L/C；仅授权个案。 | M3 |
| POST `/assistance-requests` | AssistanceCreate → 201 Assistance | L；支持关系有效；task/step 可选但出现时必须逐级匹配。 | M3 |
| GET `/assistance-requests/{request_id}` | — → 200 Assistance | L/C；明确 queued/accepted/resolved/cancelled。 | M3 |
| POST `/assistance-requests/{request_id}/actions` | AssistanceAction → 200 Assistance | C 可 accept/resolve；L 可 cancel 未解决请求；版本必需。 | M3 |
| GET `/assistance-requests/{request_id}/messages` | limit/cursor → 200 MessagePage | L/C；不允许加入任意第三方。 | M3 |
| POST `/assistance-requests/{request_id}/messages` | MessageCreate → 201 SupportMessage | L/C；内容或附件至少一项；已关闭请求禁止追加。 | M3 |

Marker 支持 point 与 rect。point 为 x/y；rect 增加 width/height，均针对归一化展示图片；marker.id 为 UUID，text 长度 1–200。矩形边界校验、同图校验及角色区分由后端执行，JSON Schema 的基本数值范围校验不能替代 x+width≤1 等跨字段规则。

求助 preferred_mode 当前为 text/annotation；call 在通话能力批准并开启后才加入。相同个案/任务已存在 queued 或 accepted 求助时，后端返回 409 ASSISTANCE_ALREADY_OPEN，并给出可授权读取的现有 request_id，前端引导进入已有线程。没有照片、拒绝相机和弱网都不应让文字求助入口失效。

### B.7 通知

| 端点 | 输入 → 成功输出 | 权限与不变量 | 阶段 |
| --- | --- | --- | --- |
| GET `/notifications` | after_seq/limit → 200 NotificationPage | 仅本人；序号字符串，按接收者隔离。 | M3 |
| GET `/notifications/stream` | after_seq 或 Last-Event-ID → 200 SSE | 仅本人，定期重验会话；只有一条活跃主连接。 | M3 |
| POST `/notifications/{notification_id}/read` | — → 204 | 仅接收者；天然幂等，不产生业务完成。 | M3 |

after_seq 默认 `0` 表示从最早仍保留的通知开始分页；非零且超出保留窗口的游标返回 410 CURSOR_EXPIRED，前端从 0 同步保留窗口并重新读取当前任务/求助对象。`next_seq` 是已返回的最后一项序号，没有新项时保持请求序号；不是当前数据库最大序号，否则可能跳过尚未分页的事件。has_more 表示当前仍有更多保留通知。

同一连接参数 after_seq 与 Last-Event-ID 同时存在时，优先 Last-Event-ID。订阅前鉴权失败用普通 HTTP 错误；已经开始 SSE 后会话失效发送最小 session_expired 控制事件并关闭，不继续推送。客户端 EventSource 无法读取具体 HTTP 错误时，改用 `/notifications` 检查会话/游标后再重连。

```text
id: 42
event: notification
data: {"id":"00000000-0000-4000-8000-000000000042","seq":"42","type":"feedback.created","resource_type":"submission","resource_id":"00000000-0000-4000-8000-000000000008","created_at":"2026-09-19T01:00:00Z","read_at":null}

: heartbeat
```

事件至少可能重复一次，客户端按通知 ID 去重；收到 resource_ref 后再鉴权读取对象。业务已成功但通知连接失败，不得让前端重复执行业务写操作。

## C. 关键数据结构与完整示例

### C.1 结构约束速查

| 模型 | 关键字段与约束 |
| --- | --- |
| PreferencesWrite | font_scale=1/1.25/1.5；volume=0–1；quiet_mode、speech_enabled、vibration_enabled 为布尔。quiet_mode 优先，不自动消除用户原有偏好。 |
| ProfileWrite | display_name 1–80；sensory_preferences 最多 10 个短标签；communication_preference≤200；work_notes≤1000。不包含匹配评分或诊断字段。 |
| MatchWrite | direction≤80；focus≤500；basis≤1000；cycle_weeks=1–52。草稿允许空文本，确认前非空校验。 |
| RevisionWrite | goal≤1000；steps≤100；reminder 为结构化对象。步骤 ID、position、instruction、media_ids、evidence_required、estimated_seconds 明确。 |
| ProgressWrite | status=in_progress/completed；attachment_ids≤5。状态由服务端转移规则限制，不能退回已锁定提交。 |
| SubmissionCreate | note≤500；后端依据当前任务形成 snapshot，不接受 outcome、author 或任意 revision_id。 |
| FeedbackCreate | outcome、message、tags、redo_step_ids、annotation_ids；引用均须属于当前提交/任务。 |
| AnnotationCreate | asset_id、可选 submission_id、kind、markers；asset 必须为 ready 图片。 |
| AssistanceCreate | case_id、可选 task_id/step_id、message≤500、attachment_ids≤5、preferred_mode。无 GPS 和任意 recipient_id。 |
| MessageCreate | body≤2000、attachment_ids≤5，至少有一项有效内容。 |

### C.2 SOP 草稿

```json
{
  "goal": "按固定步骤完成文档标题格式核验",
  "steps": [
    {
      "id": "00000000-0000-4000-8000-000000000101",
      "position": 1,
      "instruction": "找到文档最上方的标题，并与给定示例比较。",
      "media_ids": [],
      "estimated_seconds": 720,
      "evidence_required": true
    }
  ],
  "reminder": {"speech_enabled": false, "vibration_enabled": false, "prompt_level": 1}
}
```

12 分钟来自辅导员 PRD 的示例提示配置，不是所有步骤必须采用的固定时长。媒体 ID 空列表在本例仅表示文字步骤；需要图示时必须先上传并等待 ready。

### C.3 发布请求与结果

```http
POST /api/v1/sop-revisions/00000000-0000-4000-8000-000000000201/publish
Content-Type: application/json
X-CSRF-Token: <csrf-from-current-session>
Idempotency-Key: publish-example-0001
If-Match: "7"

{"due_on":"2026-09-20"}
```

```json
{
  "revision_id": "00000000-0000-4000-8000-000000000201",
  "task_id": "00000000-0000-4000-8000-000000000301",
  "published_at": "2026-09-19T01:00:00Z"
}
```

due_on 可为 null，表示未设截止日期，不表示“今天必须完成”。本请求不接收任意 learner_id，任务所属学员由版本→计划→个案关系确定。

### C.4 反馈与返工

```json
{
  "outcome": "changes_requested",
  "message": "请补充文件名中的日期，然后重新提交这一张截图。",
  "tags": ["naming_adjustment"],
  "redo_step_ids": ["00000000-0000-4000-8000-000000000101"],
  "annotation_ids": []
}
```

此命令只针对 URL 对应提交。服务端确认它是该任务最新未审核提交，再生成 FeedbackResult；旧请求或第二位审核者竞态应返回明确冲突，不创建第二份主结论。

### C.5 标注草稿

```json
{
  "asset_id": "00000000-0000-4000-8000-000000000401",
  "submission_id": "00000000-0000-4000-8000-000000000501",
  "kind": "guidance",
  "markers": [
    {
      "id": "00000000-0000-4000-8000-000000000601",
      "shape": "rect",
      "x": 0.12,
      "y": 0.7,
      "width": 0.65,
      "height": 0.12,
      "text": "在文件名末尾补上日期。"
    }
  ]
}
```

更换图片需新建标注，不允许只替换 asset_id 后继续沿用旧坐标。shape=point 时不应携带 width/height；rect 要求两者都存在且大于 0。

## D. 扩展接口草案：不计入当前核心 OpenAPI

这些端点有明确业务边界，但产品/平台条件未定。不得为“接口齐全”提前实现空壳并对用户显示可用。

| 扩展 | 建议接口边界 | 进入开发前必须补齐 |
| --- | --- | --- |
| 平台登录 | POST `/auth/exchanges/{provider}`：一次性平台 code → 同一内部 user/session | 平台、应用 ID、回调校验、防重放、会话存储与账号绑定/解绑。 |
| 通话 | POST `/assistance-requests/{id}/calls`；GET `/calls/{id}`；POST `/calls/{id}/actions` | SDK/区域、参与者授权、邀请超时、接听/拒接/挂断、计费和媒体权限。 |
| RTC 凭据 | POST `/calls/{id}/join-token` | 短时、单房间、参与者绑定；接口限流；不得把管理密钥交客户端。 |
| RTC 回调 | POST `/integrations/rtc/events` | 验签、防重放、事件 ID 去重、乱序处理；不能以未验证回调标记 connected。 |
| 通话纪要 | POST `/calls/{id}/notes`；GET `/calls/{id}/notes` | 内容范围、作者、修订留痕、默认不录制；纪要不等于转写。 |
| SOP 转换 | POST `/sop-plans/{id}/conversion-jobs`；GET `/conversion-jobs/{id}` | 输入资料授权、输出 JSON Schema、模型/费用/超时、人工确认；只产生 draft。 |
| 企业报告 | POST `/cases/{id}/report-exports`；GET `/report-exports/{id}` | 接收者、字段白名单、授权依据、有效期、撤回及下载审计。 |
| 任务重训/并行 | POST `/tasks/{id}/repetitions` 或新的任务创建规格 | Q03：重复实例身份、排期、同一学员并发、统计口径。 |
| 精确位置/实时 AR | 独立位置授权与空间锚点契约，不能复用二维 x/y 伪装 | Q06：用途、保留、设备坐标、跟踪丢失、授权失败与隐私。 |

## E. 后续实现的契约验收清单

- [ ] 每个目录端点的 operationId 唯一；所有 `$ref` 可解析；请求、成功和错误响应都有模型。
- [ ] 文档示例通过相应 Schema；Marker、Feedback、Message 等跨字段规则有服务端测试。
- [ ] 受控账号可登录；伪造角色、user_id、file_id、case_id、step_id 均有负例。
- [ ] 同幂等键并发发布/提交不会产生两条业务记录；24 小时后仍有自然唯一约束兜底。
- [ ] GET/PUT/POST 版本对应关系真实验证；成功后重试不会因原 ETag 过期而误报失败。
- [ ] 已发布 SOP 与提交快照不可变；反馈只审核当前提交；返工不擦除旧结果。
- [ ] 上传隔离、扫描失败、未关联清理、引用文件删除冲突与越权下载均有测试。
- [ ] SSE 心跳、断线重连、过期游标、会话撤销和轮询降级都能恢复到业务事实。
- [ ] 前端类型/Mock 与批准契约生成结果一致，后端运行时契约无未说明漂移。

本清单是实现验收要求，勾选需真实执行证据；当前资料校验结果另见 verification.md。
