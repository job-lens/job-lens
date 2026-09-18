# 融职境系统架构提案 v0.1

**状态：Proposed / 待人工评审。** [Proposal #5](https://github.com/job-lens/job-lens/issues/5) · [设计评审 PR #6](https://github.com/job-lens/job-lens/pull/6)

本提案确定 Web 首版、通用 Python 后端、领域数据与接口、四人职责和后续开发路径。它不表示应用已经开发完成，也不替代产品和各模块负责人的批准。

## 阅读顺序

| 文件 | 用途 |
| --- | --- |
| [architecture.md](architecture.md) | 总体架构：范围与需求追踪、技术选型与 ADR、架构视图、模块/数据/状态、权限/文件/通知、跨端、部署质量、四人分工、开发依赖、风险与待决策。 |
| [api-contract.md](api-contract.md) | HTTP 规则、资源授权、幂等与并发、55 个操作的输入输出和异常、完整示例、未批准增强能力的接口边界。 |
| [openapi.yaml](openapi.yaml) | 机器可读契约：44 个路径、55 个操作、63 个模型；用于后续 DTO、Mock 和实现一致性检查。 |
| [validate_contract.py](validate_contract.py) | 可重复运行的静态结构、引用、请求头及正负示例检查，不是应用测试。 |
| [verification.md](verification.md) | 本次实际执行结果、文档格式检查、校验边界和未执行的运行时测试。 |

Word 为单独交付给负责人的排版阅读版，汇总总体设计、5 张架构/流程图、四人分工及接口附录；仓库文件用于逐行评审和机器消费。没有把源 PRD、排版样例、真实学员资料或企业材料上传到公开仓库。

## 评审纪律

遵循基线 [CONTRIBUTING](https://github.com/job-lens/job-lens/blob/f1072e895d74a963740d46f82ab3e97034376306/CONTRIBUTING.md)：**本设计 PR 仅用于讨论，不直接合并**。定稿结论回写 #5；随后另开空骨架 Task/PR，人工 Review 合并后才按确认需求进入业务实现。

刘峥岩负责总体架构和统筹，贺凡恩复核后端/数据/权限，两位前端复核各自流程和公共契约；不把组长当作第四名全职实现者。两位前端姓名、各成员 GitHub 账号和投入时间待补，不猜测指派。

请优先评审架构文档 Q01–Q04：两端首版范围、账号/资格/个案分配、关系与任务并行数量，以及真实通话是否属于首版硬性要求。其余增强能力也有独立的范围与验证门槛。

## 复现静态契约检查

在 Python 3.11+ 的独立虚拟环境执行。以下依赖版本为本次实际验证环境，不是已批准的应用依赖锁文件：

```bash
python -m venv .venv-proposal
# Linux/macOS
source .venv-proposal/bin/activate
# Windows PowerShell 使用 .venv-proposal\Scripts\Activate.ps1
python -m pip install PyYAML==6.0.3 jsonschema==4.26.0 referencing==0.37.0
# 可选：启用与本次相同的 FastAPI OpenAPI 结构模型检查
python -m pip install fastapi==0.128.2 pydantic==2.13.4
python docs/proposals/architecture-v0.1/validate_contract.py
```

脚本默认读取同目录 `openapi.yaml`；也可传入文件路径及 `--json-out` 输出报告。脚本退出非零表示检查失败。没有安装 FastAPI 时，报告明确标为 skipped，而非假称通过。

YAML 使用锚点和合并键减少重复。需要不带 YAML 锚点的 JSON 输入时，可在仓库根目录执行：

```bash
python -c "import json,yaml; from pathlib import Path; p=Path('docs/proposals/architecture-v0.1/openapi.yaml'); print(json.dumps(yaml.safe_load(p.read_text(encoding='utf-8')),ensure_ascii=False,indent=2))" > /tmp/job-lens-openapi.json
```

输出文件只是展开后的本地衍生物，不是第二份独立维护的契约。Windows 可将输出路径改为当前目录的 `job-lens-openapi.json`。

## 契约理解与冻结门槛

HTTP 方法、字段、必填/可空及响应模型以 OpenAPI 的精确定义为准；资源关系、状态机与事务规则由接口说明共同定义。出现冲突时应停止对应实现并通过评审统一，不以选择其中一份作为规避方式。

“可空”不等于“可省略”：例如当前 `AssistanceCreate.task_id/step_id`、`AnnotationCreate.submission_id` 是必填但允许 null；没有该上下文时显式传 null。接口说明中“可选上下文”描述的是业务关联，不表示所有字段均可从 JSON 中删除。

**待接口会评补齐的明确事项：** 辅导员需要查看学员字号、音量等界面偏好，但当前 `Profile` 模型只包含资料字段。建议在 `GET /cases/{case_id}/profile` 的只读响应中增加 `preferences: Preferences`，沿用现有个案读取授权；不得通过调用别人的 `/me/preferences` 绕过身份。该字段尚未加入本版机器契约，必须在架构冻结前由贺凡恩与两名前端确认并同步 Schema、示例和检查结果。它不是当前 55 个操作已实现或已完全满足此项 PRD 的证明。

所有性能数字、恢复目标、人日估算与版本系列均为工程建议，运行时实测与最终依赖锁定属于后续实现。静态检查不能证明数据库事务、资源授权、扫描、通知恢复、真实通话或设备兼容已经正确。
