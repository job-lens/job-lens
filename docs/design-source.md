# 全局设计来源与首屏方向

2026-10-02：按用户明确要求，直接复用 Everplain 当前全局设计文件，存为 Job Lens 自己的独立副本。来源只读，没有修改 Everplain，没有运行时跨仓依赖，也没有复制产品文案、页面布局、用户数据或配置。

| 文件                                 | 只读来源                                                                   | 原文件 SHA-256                                                     |
| ------------------------------------ | -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `apps/web/src/styles/tokens.css`     | `/Users/huyan/Desktop/Everplain-tokens/frontend/src/styles/tokens.css`     | `531a38f46f2833195be654ff8422d0c841e4464b9109167e43b7b1f6af6c534d` |
| `apps/web/src/styles/components.css` | `/Users/huyan/Desktop/Everplain-tokens/frontend/src/styles/components.css` | `4b99a017c6eda56a2f27668a37b6b0e1d4d885f5e5a8e0f5b0d18253de92262a` |
| `apps/web/src/styles/base.css`       | `/Users/huyan/Desktop/Everplain-tokens/frontend/src/styles/base.css`       | `209eeea28fc199d29b482e4ad4e8afa5d9a2e12aedd9e842356f7bea5bc67784` |

副本只经过本仓 Prettier 格式化；token 值、组件声明和基础样式原样保留。`theme.css` 只为尚未迁移的业务页面提供指向 `--qx-*` 的兼容别名和原有字号偏好。移除之前单独为官网复制的 `--jl-*` 令牌，不再维护另一套配色。

当前供用户查看的方向包括官网与登录页：使用来源的 qx 排版、按钮、输入框。登录独立于工作台外壳，没有表单面板。官网包含产品介绍、三个可切换的任务步骤示意、学员到辅导员的完整训练流程、两种角色用途及节奏支持。示意切换不调用业务 API，不模拟真实提交。

用户明确要求参考原小精灵后，角色直接复用 Everplain 的本地 `agent-avatar` 实现，移除自行制作的金属机器人。来源是纯色几何轮廓、两只偏侧眼睛和原有角色色；没有渐变、高光、屏幕、嘴巴或手脚。形状、眼睛位置、张望与眨眼沿用原实现，只经过本仓 Prettier。包装层加入可保存的暂停选择、系统减少动态效果优先和密码输入时转开视线。角色文件是独立副本，没有修改 Everplain。

| 角色源文件                                                                                 | 原文件 SHA-256                                                     |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `/Users/huyan/Desktop/Everplain-tokens/frontend/src/modules/agent-avatar/avatars.tsx`      | `9e7e4101c74f84f9a17b2ffd679580f213d1632258dca4d534a0f931eb3ac64f` |
| `/Users/huyan/Desktop/Everplain-tokens/frontend/src/modules/agent-avatar/AgentAvatar.tsx`  | `de381d99f3c1aac10a24375e160d73a225f0e5e4e18748b1bf230fa8ee134899` |
| `/Users/huyan/Desktop/Everplain-tokens/frontend/src/modules/agent-avatar/agent-avatar.css` | `99f2c51cee00a1013d6803a20e1b6f1c707a6315257bc396f35c2ff3848376bb` |

真实登录、Cookie/CSRF、返回原页面、角色控制和登出逻辑保留。此分支是视觉方向预览，尚未代表全站业务页面组件迁移完成，也未代表注册、找回密码或训练后端链路已完成。关联官网 Issue #39 与账号前端 Issue #33；PR #40 保持 draft，不合并被用户否定的旧方向。
