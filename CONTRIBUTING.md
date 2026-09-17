# 参与贡献

融职境按 `Proposal → Issue → 分支 → PR → Review → 合并` 推进：所有改动从 Issue 出发，代码经 PR 合入 main。第一次参与按本文顺序读下来即可跑通全流程。

## 一、动手之前：阶段纪律

**总架构定稿前不进入功能开发。** 架构未定就开写，架构会在编码过程中被动成型，撑不住后期迭代。当前阶段（MS1）只做设计类工作：调研、Proposal、风险分析、备选方案。

总架构定稿的标志是空骨架代码经 PR Review 合并入库。在那之后，产品定义完成即可直接进入开发。

**先设计，再开发。** 跳过 Proposal 直接写代码、把模糊需求直接丢给 AI 生成，都不算数。

## 二、上手

clone 主仓库：

```bash
git clone git@github.com:job-lens/job-lens.git
cd job-lens
```

开新分支之前先同步 main：

```bash
git checkout main
git pull --rebase
git checkout -b <分支名>
```

## 三、提 Issue

Issue 是过程的基本单元，承载三类东西：产品 / 架构的工程文档草稿、任务拆解、设计澄清。

- 写清**背景、目标、验收标准**。禁止空泛标题——「优化一下 XX」不是合格的 Issue。
- 每个 Issue 挂 Milestone 并指定 owner（assignee）。**没有 Milestone 的 Issue 不在计划内。**
- 对应一个或少量 PR，范围可控。
- Proposal 先在组内对齐，再对外提交。
- 关闭时注明原因：已被 PR 解决（注明 PR 号）／ 被其他 Issue 取代（注明替代者）／ 组内确认不再需要。
- 每个 Milestone 结束时归置遗留 Issue：已完成的关闭，划入下轮的挂过去并指定 owner，其余打 `Proposal-NoPlan`。

工程文档**定稿即只读**。需求变化时新增文档描述变化，不覆盖旧文档——Issue description 自带编辑历史，版本管理靠它，不另起 Wiki。

## 四、分支与 Commit

分支命名 `<type>/<简短描述>`，例如 `feat/task-tree-schema`、`fix/prompt-fade-timing`、`docs/contributing`。

Commit message **只用英文**，格式 `type(scope): message`，scope 可省略：

```
feat(task): add task tree schema
fix(prompt): correct fade-out timing
docs: add contributing guide
```

常用 type：`feat` `fix` `docs` `refactor` `chore` `test` `style` `perf`。

## 五、提 PR

- **关联对应 Issue**，在 PR 描述或 commit message 里写 `Closes #<issue号>`，合并进 main 时自动关闭该 Issue。
- 改动范围与 Issue 一致，**不夹带无关改动**。
- **小而频繁**，及时合并。几千行的大改没人 Review 得动。
- main 开启了分支保护：必须走 PR、必须获得 approve、所有 review 讨论必须解决，只允许 squash 合并。

### PR 合并标准

达到以下全部标准才可合并：

- 关联对应 Issue，改动范围与 Issue 一致，不夹带无关改动。
- 通过必要的测试或验证；**AI 生成的代码尤其要有测试兜底**，确保功能可用。
- 作者能讲清这次 PR 的主要改动是什么、为什么这么改。**讲不清就不合。**
- 经过代码质量检查与人工 Review，无方向性问题与明显隐患。
- 不长期堆积。

### 设计草案的 Review

产品设计文档、原型（含可交互的 live demo）这类设计产出，逐行评审可以借助 PR：把设计内容提交为 PR，用行内评论逐条讨论。**该 PR 只用于 Review、不合并**；讨论定稿后把内容落回对应 Issue，并在 Issue 中附上 PR 链接，此后 Issue 作为开发的起点。

这类草案 PR 与总架构的空骨架 PR 不同——后者是会合并入库的代码。

## 六、AI 协作的额外要求

AI 可以参与每个环节，但不替代工程流程本身，**最终交付责任在人**。AI 生成的内容合入前逐条对照，任一条不满足就先澄清再继续：

- 方案经得起拷问，理由可讲清。
- 代码逻辑有人能完整理解、能讲清、出问题能改。
- 核心模块的 PR 描述附**关键 Prompt 与人工 Review 说明**。
- 系统架构由人主导设计，不得以 AI 生成的粗浅实现入库冒充架构。

一旦架构失控、范围膨胀，或出现 AI 生成的代码无人能讲清：及时砍范围，或暂停开发补设计。

Proposal 文字特别长时，把与某个具体实现相关的部分拆成 `sub-task`，只把相关部分交给 AI，避免上下文过长影响效果。说明不长则不必拆。

## 七、标签

| 维度 | 标签 | 含义 |
| --- | --- | --- |
| 产品设计 | `proposal` | 该 Issue 是一个产品提案 |
| 决策结果 | `Proposal-Accepted` / `Proposal-Denied` / `Proposal-NoPlan` | 提案定稿 / 被拒 / 暂不排期 |
| 规格粒度 | `FullSpec` / `MiniSpec` | 影响面大的完整规格 / 小改动的精简规格 |
| 文档状态 | `Need-Document` / `Documented` | 功能已完成待补用户文档 / 用户文档已提供 |
| 优先级 | `P0` / `P1` / `P2` | 先做 / 次级 / 押后 |
| 其他 | `sub-task` `document` `user-doc` `needs-info` | 拆出的子任务 / 工程文档 / PR 含用户文档 / 信息待补 |

一个提案的典型生命周期：`proposal` → 讨论 → `Proposal-Accepted` + `FullSpec`（或 `MiniSpec`）→ 开发 → `Need-Document` → 补文档 → `Documented`。

**被拒绝是正常结果，不是失败**——它同样是一次有记录的决策。

## 八、Milestone 与 Release

每个 Milestone 写清本轮目标、挂上本轮所有 Issue，结束时把已完成的 Issue 整理进 Milestone 说明，形成本轮功能清单。

每个 Milestone 结束发一个 Release，tag 用 `vX.Y.Z`，描述列清本轮交付了哪些功能。

## 九、本文档本身

需要修改时先开 Issue 讨论，达成一致后更新本文档，不直接改。
