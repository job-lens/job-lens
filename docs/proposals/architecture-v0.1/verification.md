# 验证记录

## 契约检查

```bash
python docs/proposals/architecture-v0.1/validate_contract.py
```

实际输出：

```text
PASS: 44 paths, 55 operations, 64 schemas
PASS: 446 references; path parameters and required headers
PASS: 14 positive / 14 negative schema examples
PASS: 6 linked SVG diagrams; CaseProfile projection
FastAPI OpenAPI model: passed
```

检查包含 `CaseProfile` 的档案与偏好投影、各自版本字段及组合响应不提供写入 ETag。矩形坐标相加边界、资源授权、状态转移和事务约束需由应用测试验证。

本次检查的 `openapi.yaml` Git blob：`f48a55c94c20393a7d622da54742f75b35defaab`。

## 文档与图示

Word 共 37 页，正文、接口附录与六张图已逐页检查。六张 SVG 的重新渲染结果与 Word 使用的 PNG 像素一致；图中的对象名称、关系和状态与正文对应。

## 未运行

应用尚未实现，未运行数据库事务、权限隔离、文件扫描、SSE 恢复、性能、真机和备份恢复测试。验收用例与目标见架构第七章。
