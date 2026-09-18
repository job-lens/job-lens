# 融职境系统架构

[Issue #5](https://github.com/job-lens/job-lens/issues/5) · [PR #6](https://github.com/job-lens/job-lens/pull/6)

| 文件 | 内容 |
| --- | --- |
| [architecture.md](architecture.md) | 系统范围、技术选型、模块、数据与状态、事务、权限、文件、通知、多端接入、部署及四人开发路径。 |
| [api-contract.md](api-contract.md) | HTTP 规则、55 个操作、请求模型、响应约束、示例与扩展接口。 |
| [openapi.yaml](openapi.yaml) | 机器接口契约：44 个路径、55 个操作、63 个模型。 |
| [validate_contract.py](validate_contract.py) | 结构、引用、请求头与 Schema 示例检查。 |
| [verification.md](verification.md) | 文档修订检查及契约验证记录。 |

## 契约检查

Python 3.11+，在独立虚拟环境中执行：

```bash
python -m pip install PyYAML==6.0.3 jsonschema==4.26.0 referencing==0.37.0
python docs/proposals/architecture-v0.1/validate_contract.py
```

安装 FastAPI 后，脚本同时检查其 OpenAPI 结构模型。使用 `--json-out <path>` 保存结果；非零退出码表示失败。

## 实施入口

总体设计见架构第二至九章；人员和阶段任务见第十章；产品决策见第十一章。接口 B.2 的学员偏好响应投影需在前后端联评时同步到 OpenAPI。
