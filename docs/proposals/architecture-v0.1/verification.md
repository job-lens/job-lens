# 验证记录

## 文档修订检查

| 检查 | 结果 |
| --- | --- |
| 接口目录对比 | 55 个方法/路径组合与修订前一致，无遗漏或重复。 |
| JSON 示例 | 4 个 JSON 代码块全部通过 `json.loads`。 |
| Markdown 结构 | 代码围栏闭合；表格无空行、空单列表。 |
| Word 内容 | 由架构与接口 Markdown 生成；中文字符计数与渲染文本比对无缺字，无残留 Markdown 加粗标记。 |
| Word 排版 | 32 页逐页检查完成；图表、正文与页码无裁切或重叠，跨页表头重复。 |
| 仓库一致性 | 架构、接口文件的 Git blob SHA 与生成 Word 所用 Markdown 一致。 |

Word：`融职境_系统架构设计文档_修订版.docx`。

```text
architecture.md: f275c00076a4ec11cfa9b6d5d2c85c5ddfb195bb
api-contract.md: bb7049ff27368d47dd862c15489373d0679ab3f7
DOCX SHA-256: 0e786f4f8a9841ba5e8e217a69e8211b986ba089198cdbdbfc281103701dc215
```

## 既有契约检查

本轮未修改 `openapi.yaml` 和 `validate_contract.py`，未重新运行契约脚本。以下为首次提交时的检查记录：

| 检查 | 结果 |
| --- | --- |
| 结构与操作 | OpenAPI 3.1.1；44 个路径、55 个操作、63 个模型；operationId 和路径参数检查通过。 |
| 引用 | 369 处 `$ref` 解析通过。 |
| 请求头声明 | CSRF、幂等键、If-Match 及 412/428 声明检查通过。 |
| Schema 示例 | 18 个样例接受、11 个样例拒绝，结果符合预期。 |
| FastAPI OpenAPI 模型 | 结构校验通过。 |

契约 Git blob：`a71a31700e083d6705a09f8494f1c1c087117630`。

重跑命令：

```bash
python docs/proposals/architecture-v0.1/validate_contract.py
```

矩形的 `x+width≤1`、`y+height≤1` 由服务层校验。运行时授权、数据库事务、文件扫描、通知恢复及端到端测试尚未执行；验收项见架构第九章。
