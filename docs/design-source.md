# 全局设计来源与首屏方向

2026-10-02：按用户明确要求，直接复用 Everplain 当前全局设计文件，存为 Job Lens 自己的独立副本。来源只读，没有修改 Everplain，没有运行时跨仓依赖，也没有复制产品文案、页面布局、用户数据或配置。

| 文件                                 | 只读来源                                                                   | 原文件 SHA-256                                                     |
| ------------------------------------ | -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `apps/web/src/styles/tokens.css`     | `/Users/huyan/Desktop/Everplain-tokens/frontend/src/styles/tokens.css`     | `531a38f46f2833195be654ff8422d0c841e4464b9109167e43b7b1f6af6c534d` |
| `apps/web/src/styles/components.css` | `/Users/huyan/Desktop/Everplain-tokens/frontend/src/styles/components.css` | `4b99a017c6eda56a2f27668a37b6b0e1d4d885f5e5a8e0f5b0d18253de92262a` |
| `apps/web/src/styles/base.css`       | `/Users/huyan/Desktop/Everplain-tokens/frontend/src/styles/base.css`       | `209eeea28fc199d29b482e4ad4e8afa5d9a2e12aedd9e842356f7bea5bc67784` |

副本只经过本仓 Prettier 格式化；token 值、组件声明和基础样式原样保留。`theme.css` 只为尚未迁移的业务页面提供指向 `--qx-*` 的兼容别名和原有字号偏好。移除之前单独为官网复制的 `--jl-*` 令牌，不再维护另一套配色。

当前供用户查看的方向包括官网与登录页：使用来源的 qx 排版、按钮、输入框。登录独立于工作台外壳，没有表单面板。官网包含产品介绍、三个可切换的任务步骤示意、学员到辅导员的完整训练流程、两种角色用途及节奏支持。示意切换不调用业务 API，不模拟真实提交。

2026-10-03：用户亲自调整并确认当前主页，包含中性灰白画布、无衬线粗体标题、圆形耳机角色“小融”、产品示意和分段内容。后续页面以此版与本仓 `--qx-*` 令牌为准。保持主页版式及角色造型；只补充实际内容、交互、可访问性和性能，不重新设计。旧鹅卵石角色方向已被替换。所有角色实例共享暂停设置，系统减少动态效果同时停止 CSS 动画与指针视差。
官网研究参考 [Todoist](https://www.todoist.com/)、[Linear 产品规划](https://linear.app/plan) 与 [Headspace](https://www.headspace.com/app) 的公开页面：借鉴具体产品演示、分段叙事与简洁操作入口，不复制页面文案、布局、角色或图片。研究图片仅放在忽略的本地目录，没有加入产品。官网的文件与清单图形是本仓自绘 SVG，步骤演示明确标记为示意，不模拟提交。

真实登录、Cookie/CSRF、返回原页面、角色控制和登出逻辑保留。注册和找回密码已接真实邮件适配器；外部邮件送达仍需独立开发邮件配置。业务页面逐项接通真实后端，并在完成后使用独立测试库的合成账号验收。PR #40 保持 draft，不合并被用户否定的旧方向。
