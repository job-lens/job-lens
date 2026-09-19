# 融职境系统架构

[系统架构](architecture.md) · [接口契约](api-contract.md) · [OpenAPI](openapi.yaml) · [验证记录](verification.md)

![总体架构](figures/01-containers.svg)

| 视图 | 内容 |
| --- | --- |
| [总体架构](figures/01-containers.svg) | Web、后续客户端、业务 API、worker 与数据存储 |
| [后端组件](figures/02-components.svg) | 五个业务模块、用例事务与基础设施适配 |
| [数据关系](figures/03-data.svg) | 个案授权、SOP 版本、训练任务、提交与反馈 |
| [任务状态机](figures/04-states.svg) | 执行、暂停、提交、返工、完成与取消 |
| [发布时序](figures/05-sequence.svg) | 原子发布、幂等结果与学员通知 |
| [部署拓扑](figures/06-deployment.svg) | HTTPS 入口、私有运行区与独立备份 |

接口包含 44 个路径、55 个操作和 64 个数据模型。`CaseProfile` 同时返回档案与只读界面偏好，两者保留独立版本。

## 契约检查

Python 3.11+，安装 PyYAML 与 jsonschema 后运行：

```bash
python docs/proposals/architecture-v0.1/validate_contract.py
```

安装 FastAPI 时会额外执行 OpenAPI 模型检查。脚本覆盖引用、操作标识、路径参数、请求头约定、Schema 正负例与图文件链接。

## 开发入口

四人职责、M0–M4 阶段和 T01–T10 任务依赖见[架构第八章](architecture.md#八分工与开发路径)。讨论在 [Issue #5](https://github.com/job-lens/job-lens/issues/5)，逐行评审在 [PR #6](https://github.com/job-lens/job-lens/pull/6)。依仓库流程，设计评审后另提空骨架 PR。
