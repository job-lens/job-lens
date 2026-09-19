# API 契约

基础路径为 `/api/v1`。L 表示所属学员，C 表示已获该个案访问权的辅导员。M1 为工程骨架，M2 为业务闭环，M3 为辅导支持。所有列表先授权后分页；UUID、步骤和附件同时校验所属个案、任务及版本。

## 通用规则

业务 POST 需要 `Idempotency-Key`，登录、退出除外。写请求需要 `X-CSRF-Token`；表中“版本”表示还需要 `If-Match`。PUT/DELETE 修改使用目标聚合版本，任务下的步骤、提交和反馈使用任务版本。错误、分页、幂等及会话规则见[系统架构第四至六章](architecture.md)。

`GET /cases/{case_id}/profile` 返回 `CaseProfile {profile, preferences}`，用于辅导员画像。两部分各自带 version；组合响应不提供写入 ETag。本人资料与偏好仍分别通过 `/me/profile`、`/me/preferences` 修改。

## 一、接口目录

### A.1 公共、登录与本人资料
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `GET /health/live`<br>存活检查 | — → 200 Health | 匿名；M1 |
| `GET /health/ready`<br>就绪检查 | — → 200 Health | 匿名；M1 |
| `GET /auth/csrf`<br>获取预登录或当前会话CSRF凭据 | — → 200 CsrfToken | 匿名/预登录会话；M2 |
| `POST /auth/login`<br>账号登录并轮换会话 | LoginRequest → 200 LoginResult | 匿名/预登录会话；M2 |
| `POST /auth/logout`<br>撤销当前会话 | — → 204 无响应体 | 本人；M2 |
| `GET /me`<br>读取本人身份 | — → 200 User | 本人；M2 |
| `GET /me/preferences`<br>读取本人偏好 | — → 200 Preferences | 本人；M2 |
| `PUT /me/preferences`<br>更新本人偏好 | PreferencesWrite → 200 Preferences | 本人；版本；M2 |
| `GET /me/profile`<br>读取本人档案 | — → 200 Profile | 本人；M2 |
| `PUT /me/profile`<br>更新本人档案 | ProfileWrite → 200 Profile | 本人；版本；M2 |
| `GET /capabilities`<br>查询服务端已开启能力 | — → 200 Capabilities | 本人；M2 |
| `GET /dashboard`<br>读取角色工作台摘要 | view（必填） → 200 Dashboard | L/C；M2 |

### A.2 个案、匹配与记录
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `GET /cases`<br>列出已授权个案 | state/limit/cursor → 200 CasePage | L/C；M2 |
| `GET /cases/{case_id}`<br>读取授权个案 | — → 200 Case | L/C；M2 |
| `GET /cases/{case_id}/profile`<br>读取授权个案档案 | — → 200 CaseProfile | L/C；M2 |
| `GET /cases/{case_id}/materials`<br>读取授权资料文件 | limit/cursor → 200 FilePage | L/C；M2 |
| `GET /cases/{case_id}/match`<br>读取支持匹配 | — → 200 SupportMatch | L/C；M2 |
| `PUT /cases/{case_id}/match`<br>保存匹配草稿 | MatchWrite → 200 SupportMatch | C；版本；M2 |
| `POST /cases/{case_id}/match/confirm`<br>确认支持匹配 | — → 200 SupportMatch | C；版本；M2 |
| `GET /cases/{case_id}/records`<br>读取描述性训练记录 | limit/cursor → 200 RecordPage | L/C；M3 |

### A.3 私有文件
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `POST /files`<br>上传至私有隔离区 | FileUpload（multipart） → 202 FileAsset | L/C；M2 |
| `GET /files/{file_id}`<br>读取文件状态 | — → 200 FileAsset | L/C；M2 |
| `DELETE /files/{file_id}`<br>删除本人未被引用文件 | — → 204 无响应体 | 上传者；未引用；版本；M2 |
| `GET /files/{file_id}/content`<br>鉴权读取就绪文件 | — → 200 二进制文件 | L/C；M2 |

### A.4 SOP 与不可变发布
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `GET /cases/{case_id}/sop-plans`<br>列出授权SOP计划 | limit/cursor → 200 PlanPage | L/C；M2 |
| `POST /cases/{case_id}/sop-plans`<br>创建计划和初始草稿 | PlanCreate → 201 SopPlan | C；M2 |
| `GET /sop-plans/{plan_id}`<br>读取授权SOP计划 | — → 200 SopPlan | L/C；M2 |
| `POST /sop-plans/{plan_id}/revisions`<br>创建新草稿版本 | RevisionCreate → 201 SopRevision | C；M2 |
| `GET /sop-revisions/{revision_id}`<br>读取授权SOP版本 | — → 200 SopRevision | L/C；M2 |
| `PUT /sop-revisions/{revision_id}`<br>整体保存草稿版本 | RevisionWrite → 200 SopRevision | C；版本；M2 |
| `POST /sop-revisions/{revision_id}/publish`<br>冻结SOP并原子创建唯一任务 | PublishRequest → 200 Publication | C；版本；M2 |

### A.5 训练、提交与反馈
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `GET /tasks`<br>列出授权训练任务 | status/case_id/limit/cursor → 200 TaskPage | L/C；M2 |
| `GET /tasks/{task_id}`<br>读取固定训练内容与进度 | — → 200 Task | L/C；M2 |
| `POST /tasks/{task_id}/actions`<br>开始暂停继续或取消任务 | TaskAction → 200 Task | L 开始/暂停/继续；C 取消；版本；M2 |
| `PUT /tasks/{task_id}/steps/{step_id}`<br>保存可执行步骤进度 | ProgressWrite → 200 Task | L；版本；M2 |
| `POST /tasks/{task_id}/events`<br>批量写入去重观测事件 | EventBatch → 200 EventReceipt | L；M3 |
| `GET /tasks/{task_id}/submissions`<br>读取全部历史提交 | limit/cursor → 200 SubmissionPage | L/C；M2 |
| `POST /tasks/{task_id}/submissions`<br>锁定本次训练提交 | SubmissionCreate → 201 Submission | L；版本；M2 |
| `GET /submissions/{submission_id}`<br>读取快照与父任务当前版本 | — → 200 Submission | L/C；M2 |
| `POST /submissions/{submission_id}/feedback`<br>审核当前提交并更新任务 | FeedbackCreate → 201 FeedbackResult | C；版本；M2 |
| `PUT /tasks/{task_id}/prompt-override`<br>调整当前任务文字提示等级 | PromptOverrideWrite → 200 Task | C；版本；M3 |

### A.6 标注与上下文求助
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `GET /tasks/{task_id}/annotations`<br>列出授权标注 | limit/cursor → 200 AnnotationPage | L/C；M3 |
| `POST /tasks/{task_id}/annotations`<br>创建问题或指引标注草稿 | AnnotationCreate → 201 Annotation | L 提问 / C 指引；M3 |
| `GET /annotations/{annotation_id}`<br>读取授权标注 | — → 200 Annotation | L/C；M3 |
| `PUT /annotations/{annotation_id}`<br>修改本人标注草稿 | AnnotationWrite → 200 Annotation | 标注作者；草稿；版本；M3 |
| `POST /annotations/{annotation_id}/publish`<br>发布不可变二维标注 | — → 200 Annotation | 标注作者；草稿；版本；M3 |
| `GET /assistance-requests`<br>列出授权求助 | state/case_id/limit/cursor → 200 AssistancePage | L/C；M3 |
| `POST /assistance-requests`<br>创建文字或标注求助 | AssistanceCreate → 201 Assistance | L；M3 |
| `GET /assistance-requests/{request_id}`<br>读取求助状态 | — → 200 Assistance | L/C；M3 |
| `POST /assistance-requests/{request_id}/actions`<br>接单解决或取消求助 | AssistanceAction → 200 Assistance | C 接单/解决；L 取消；版本；M3 |
| `GET /assistance-requests/{request_id}/messages`<br>读取求助上下文消息 | limit/cursor → 200 MessagePage | L/C；M3 |
| `POST /assistance-requests/{request_id}/messages`<br>追加求助上下文消息 | MessageCreate → 201 SupportMessage | L/C；M3 |

### A.7 通知
| 接口与用途 | 请求 → 成功响应 | 权限与阶段 |
| --- | --- | --- |
| `GET /notifications`<br>补拉本人持久化通知 | after_seq/limit → 200 NotificationPage | 通知接收者；M3 |
| `GET /notifications/stream`<br>订阅可恢复通知流 | after_seq/Last-Event-ID → 200 SSE 事件流 | 通知接收者；M3 |
| `POST /notifications/{notification_id}/read`<br>标记本人通知已读 | — → 204 无响应体 | 通知接收者；M3 |

## 二、业务校验

| 操作 | 前置条件与结果 |
| --- | --- |
| 匹配确认 | 仅授权辅导员；方向、重点、依据非空且周期合法；确认后锁定匹配内容 |
| 草稿与发布 | 草稿可不完整；发布要求 1–100 个完整步骤、唯一步骤 ID/顺序、非空目标、就绪素材及已确认匹配；冻结版本并原子创建任务 |
| 重复发布 | 同发布版本返回同一任务；已有非终态任务返回 ACTIVE_TASK_EXISTS；修订不替换历史任务内容 |
| 任务动作 | L 可 start/pause/resume，C 可 cancel 且原因必填；仅允许状态机定义的转移 |
| 步骤进度 | 仅所属学员；步骤属于任务固定版本，按当前可执行步骤保存，附件 ready；已提交内容锁定 |
| 提交 | 后端从持久化进度构建 snapshot；增加 attempt_no；任务转 submitted；不接受客户端提供作者或审核快照 |
| 反馈 | 仅最新未审核提交；主反馈唯一；passed 不含返工步骤，changes_requested 至少指定一个本版本步骤；只重置指定步骤 |
| 文件 | purpose 与关联上下文一致；辅导员只读 ready 资料；下载重新授权；删除仅限本人未被引用文件 |
| 标注 | question 由 L 创建，guidance 由 C 创建；草稿仅作者可见；发布不可变；原图、任务和提交归属一致 |
| 求助 | 支持关系有效；同上下文已有 queued/accepted 返回 409 ASSISTANCE_ALREADY_OPEN 与现有 ID；C 可 accept/resolve，L 可 cancel |
| 消息 | 当前线程参与者；正文或附件至少有一项；仅开放线程可追加；客户端不能指定第三方接收者 |
| 通知 | 仅接收者；已读不改变业务状态；资源引用仍需通过对应 GET 授权 |

观测事件 `hint_requested / self_reported_error / time_sample` 按 event_id 去重，同 ID 不同内容返回 409。time_sample 为同一 session_id、step_id 的累计毫秒，取最大有效 sequence 后跨会话汇总；不叠加同会话累计值。观测事件不完成任务，求助次数从服务端求助记录统计。

`CaseProfile` 的只读偏好是最新界面设置；训练指引内容取固定 SOP 版本。辅导员的提示调整仅作用于当前任务，学员安静模式优先。

## 三、字段定义

请求拒绝额外字段。表中可空字段仍遵循“必填”列；允许 null 不等于可以省略。

### B.1 个人界面偏好（PreferencesWrite）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| font_scale | 是 | 数值；枚举：1, 1.25, 1.5 |
| volume | 是 | 数值；最小 0，最大 1 |
| quiet_mode | 是 | 布尔 |
| speech_enabled | 是 | 布尔 |
| vibration_enabled | 是 | 布尔 |

### B.2 个人资料（ProfileWrite）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| display_name | 是 | 字符串；最短 1，最长 80 |
| sensory_preferences | 是 | 数组；元素 字符串；最短 1，最长 40；最多 10 |
| communication_preference | 是 | 字符串；最长 200 |
| work_notes | 是 | 字符串；最长 1000 |

### B.3 支持匹配草稿（MatchWrite）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| direction | 是 | 字符串；最长 80 |
| focus | 是 | 字符串；最长 500 |
| cycle_weeks | 是 | 整数；最小 1，最大 52 |
| basis | 是 | 字符串；最长 1000 |

草稿允许空文本；确认时 direction、focus、basis 必须非空，case_id 和辅导员身份取自上下文。

### B.4 SOP 草稿（RevisionWrite）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| goal | 是 | 字符串；最长 1000 |
| steps | 是 | 数组；元素 SopStep；最多 100 |
| reminder | 是 | Reminder |

发布时至少一个完整步骤，步骤 ID/顺序唯一、素材 ready；草稿允许不完整。

### B.5 单个步骤（SopStep）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| id | 是 | 字符串（uuid） |
| position | 是 | 整数；最小 1，最大 100 |
| instruction | 是 | 字符串；最长 2000 |
| media_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |
| estimated_seconds | 是 | 整数；最小 0，最大 86400 |
| evidence_required | 是 | 布尔 |

estimated_seconds 为建议时长，不表示超时处罚。该步骤必须属于任务固定引用的发布版本。

### B.6 任务状态命令（TaskAction）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| action | 是 | 字符串；枚举：start, pause, resume, cancel |
| reason | 否 | 字符串；最长 500 |

学员仅能 start/pause/resume，辅导员 cancel 必须给 reason；服务端依当前状态限制转移。

### B.7 步骤进度（ProgressWrite）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| status | 是 | 字符串；枚举：in_progress, completed |
| attachment_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |

### B.8 提交结果（SubmissionCreate）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| note | 是 | 字符串；最长 500 |

### B.9 主反馈（FeedbackCreate）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| outcome | 是 | 字符串；枚举：passed, changes_requested |
| message | 是 | 字符串；最短 1，最长 500 |
| tags | 是 | 数组；元素 字符串；枚举：title_correct, naming_adjustment, retake_required, other；最多 5 |
| redo_step_ids | 是 | 数组；元素 字符串（uuid）；最多 100 |
| annotation_ids | 是 | 数组；元素 字符串（uuid）；最多 20 |

changes_requested 必须列出返工步骤；passed 的 redo_step_ids 必须为空。所有引用必须属于当前待审提交。

### B.10 创建二维标注（AnnotationCreate）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| asset_id | 是 | 字符串（uuid） |
| submission_id | 是 | string / null（uuid） |
| kind | 是 | 字符串；枚举：question, guidance |
| markers | 是 | 数组；元素 Marker；至少 1，最多 100 |

 guidance 由辅导员创建，question 由学员创建；图片必须 ready 且归属相同任务/提交。

### B.11 创建求助（AssistanceCreate）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| case_id | 是 | 字符串（uuid） |
| task_id | 是 | string / null（uuid） |
| step_id | 是 | string / null（uuid） |
| message | 是 | 字符串；最短 1，最长 500 |
| attachment_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |
| preferred_mode | 是 | 字符串；枚举：text, annotation |

 task_id、step_id 可为 null，但若给出须逐级匹配；关系有效且不接受任意接收者或 GPS 字段。

### B.12 追加消息（MessageCreate）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| body | 是 | 字符串；最长 2000 |
| attachment_ids | 是 | 数组；元素 字符串（uuid）；最多 5 |

非空白文字或有效附件至少一项；请求结束后不允许追加。

### B.13 观测事件（TaskEvent）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| event_id | 是 | 字符串（uuid） |
| session_id | 是 | 字符串（uuid） |
| sequence | 是 | 整数；最小 1，最大 2147483647 |
| step_id | 是 | 字符串（uuid） |
| kind | 是 | 字符串；枚举：hint_requested, self_reported_error, time_sample |
| value | 是 | 整数；最小 0，最大 86400000 |
| observed_at | 是 | 字符串（date-time） |

 time_sample 是会话与步骤的累计值，按最高有效 sequence 取值后跨会话汇总；不累加每个累计采样。

### B.14 任务提示覆盖（PromptOverrideWrite）
| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| prompt_level | 是 | 整数；最小 1，最大 3 |
| reason | 是 | 字符串；最短 1，最长 500 |

仅调整任务文字提示等级，不能强制改变个人声音、震动或安静偏好。

### B.15 标注几何与核心响应
| 对象 | 主要字段 / 附加规则 |
| --- | --- |
| PointMarker | id、shape=point、x、y、text。坐标 0–1，text 长度 1–200；不能混入 width/height。 |
| RectMarker | 上述字段加 width、height；两者 >0 且 ≤1；还要验证 x+width≤1、y+height≤1。 |
| Task | id、case_id、learner_id、title、固定 revision、status、due_on、current_step_id、progress、prompt_override、version。 |
| Submission | id、task_id、attempt_no、revision_id、note、不可变 snapshot、submitted_at，以及当前父任务 task_version/task_status 和对应 feedback。 |
| FileAsset | id、归属、purpose、filename、mime_type、size_bytes、扫描 state/reason、图像 width/height、version、created_at；不返回私有 storage_key。 |
| Notification | id、字符串 seq、type、resource_type/id、created_at、read_at；事件只带资源引用，再按权限读取对象。 |

### B.16 辅导员画像（CaseProfile）

| 字段 | 必填 | 类型与约束 |
| --- | --- | --- |
| profile | 是 | Profile；资料及其独立 version |
| preferences | 是 | Preferences；字号、音量、提示偏好及其独立 version |

## 四、请求与响应示例

### 4.1 SOP 发布

```http
POST /api/v1/sop-revisions/00000000-0000-4000-8000-000000000201/publish
Content-Type: application/json
X-CSRF-Token: <current-session-csrf>
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

### 4.2 返工反馈

```json
{
  "outcome": "changes_requested",
  "message": "请补充文件名中的日期，再提交这一张截图。",
  "tags": ["naming_adjustment"],
  "redo_step_ids": ["00000000-0000-4000-8000-000000000101"],
  "annotation_ids": []
}
```

### 4.3 图片框标注

```json
{
  "asset_id": "00000000-0000-4000-8000-000000000401",
  "submission_id": "00000000-0000-4000-8000-000000000501",
  "kind": "guidance",
  "markers": [{
    "id": "00000000-0000-4000-8000-000000000601",
    "shape": "rect",
    "x": 0.12, "y": 0.70,
    "width": 0.65, "height": 0.12,
    "text": "在文件名末尾补上日期。"
  }]
}
```

### 4.4 通知恢复

`GET /notifications?after_seq=41&limit=20` 补拉通知；`next_seq` 为最后返回序号。非零游标已过期时返回 410，重新从 0 同步保留窗口，再刷新业务对象。

```text
id: 42
event: notification
data: {"id":"00000000-0000-4000-8000-000000000042", "seq":"42", "type":"feedback.created", "resource_type":"submission", "resource_id":"00000000-0000-4000-8000-000000000501", "created_at":"2026-09-19T01:00:00Z", "read_at":null}

: heartbeat
```

Last-Event-ID 优先于查询参数 after_seq；同一通知可重投，客户端按 ID 去重。EventSource 无法读取连接错误详情时，用通知列表接口检查会话与游标。
