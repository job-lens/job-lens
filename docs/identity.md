# 账号与会话

对应 #26、#33。登录页直接调用 `/auth/csrf`、`/auth/login`，凭据通过请求正文发送；登出调用 `/auth/logout` 撤销数据库会话。浏览器只保存 Secure、HttpOnly、SameSite=Lax 的 `__Host-jl_session` Cookie，CSRF 放在内存中。登录轮换会话与 CSRF，刷新页面后重新获取 CSRF。禁止把密码、会话或 CSRF 放进 URL、日志或 localStorage。

复用方案比较了群学与 Windup。群学的不透明 Cookie、服务端摘要、邮箱校验与会话撤销方式更接近本项目现有 FastAPI / SQLAlchemy 结构；Windup 的 JWT、Redis 和账户额度设计会引入本功能不需要的运行组件。本次采用群学的会话生命周期设计，使用本仓库已有 Argon2、CSRF、角色和事务原语重新实现；没有复制任何用户库、密钥、私有配置或生产权限。邮箱注册与找回仍需独立契约及真实邮件投递，不包含在本次交付。

绝对会话寿命 12 小时，空闲 2 小时失效。匿名 CSRF 会话 15 分钟；禁用账号或无合法角色的账号不能登录，已有会话也不能继续访问。登录账号 15 分钟最多 10 次，客户端最多 30 次，计数保存在 PostgreSQL，失败响应仍提交计数。CSRF 获取每客户端每分钟最多 120 次。限流键只存摘要。

本人资料和偏好只从当前主体读取，写入必须同时通过 Origin、CSRF 与 If-Match；缺少版本返回 428，旧版本返回 412。成功写入增加版本并记录审计。能力开关对未接入功能统一返回 false。客户端登出及任一受保护查询/命令遇到 401 时会清除个人缓存；重新登录可回到被打断的同站页面。

开放注册、认证后增加辅导员角色的政策来自 #22 Q02。认证审核人及个案分配尚待明确，本次没有增加自行提权入口或管理员生产授权。登录不会自动创建账号；开发账号仅通过下述严格测试工具生成。

## 浏览器验收

`tools/identity_fixture.py` 拒绝非 `test` 环境与非 `_test` 数据库，拒绝覆盖已有账号。生成的 `fixture_learner`、`fixture_counselor` 仅用于一次性浏览器测试；密码由测试环境传入。`expire` 只修改测试学员的会话时间，不暴露测试 HTTP 接口。

```bash
# 对已迁移的独立测试数据库设置 JOB_LENS_DATABASE_URL；不要指向用户数据库。
export JOB_LENS_ENVIRONMENT=test
export E2E_PASSWORD=browser-training-password
PYTHONPATH=apps/api:. python tools/identity_fixture.py seed
E2E_BASE_URL=http://localhost:5173 pnpm exec playwright test tests/e2e/identity.spec.ts --workers=1
```

本机开发需要独立 API 端口时，可用 `JOB_LENS_API_PROXY=http://127.0.0.1:8188 pnpm dev`。`JOB_LENS_PUBLIC_ORIGIN` 必须匹配浏览器 Origin。CI 的真实浏览器验收在一次性容器数据库上运行，生成账号不代表产品注册接口。
