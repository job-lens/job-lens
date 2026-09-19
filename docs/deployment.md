# 部署与恢复

## 本机容器栈

Docker Compose 2.24+：

```bash
cp .env.example .env
docker compose up -d --build --wait --wait-timeout 180
python tools/smoke.py
docker compose exec -T api python tools/worker_smoke.py
```

入口为 `http://localhost:8080`。启动顺序：PostgreSQL 健康 → 单次 Alembic 迁移成功 → API 与 worker → Caddy。默认只发布网关的 loopback 端口；数据库、API、worker 不开放公网端口。

```bash
docker compose ps
docker compose logs --tail=100 api worker
docker compose down
```

常规停止保留数据卷。`down -v` 仅用于销毁测试环境，禁止用于生产重启。

## 生产配置

以 `.env.production.example` 为模板替换数据库密码、URL 编码后的连接信息、真实域名、允许的 Host 和 S3 私有桶。`JOB_LENS_PUBLIC_ORIGIN` 必须与用户浏览器地址一致；生产设置拒绝非 HTTPS Origin、通配 Host 或非 S3 存储。

域名解析到部署主机并开放 80/443；Caddy 使用真实域名申请 TLS，证书状态保存在独立卷中。S3 使用限制到指定桶的工作负载身份；不能提交云密钥、数据库口令或 `.env`。应用进程使用非 root UID，基础设施网络不直接对外开放。

```bash
docker compose config --quiet
docker compose build --pull
docker compose up -d --wait --wait-timeout 180
```

将填好的生产配置保存在受控部署目录的 `.env`；Compose 插值与服务环境从同一文件读取，避免混用本地配置。当前仓库不绑定真实服务器、云账号或域名。

发布时记录代码提交、前端锁文件、Python 锁文件和构建镜像 digest。镜像基础版本使用 Python 3.13、Node 24、PostgreSQL 17、Caddy 2.10 系列；生产部署应固定已验证的镜像 digest，升级通过 PR 重新构建验证。

## 备份与恢复

备份范围是 PostgreSQL 与私有文件，两者缺一不可。备份前暂停业务写入，记录提交版本与迁移版本；备份存放在加密且受限的位置，不进入 Git。

```bash
python3 tools/database_backup.py backup backups/database.dump
python3 tools/database_backup.py verify backups/database.dump
```

备份脚本拒绝覆盖已有文件、以 0600 权限创建归档并生成 SHA-256；`verify` 校验后只恢复到随机命名的临时测试库，验证迁移和作业表并清理，不覆盖当前数据库。恢复输入必须是可信的自有备份。CI 在容器栈执行相同的备份/恢复验证。

S3 使用桶版本控制、生命周期和独立备份策略；本地测试存储使用 `job-lens_private-files` 卷快照。恢复在隔离环境执行：恢复数据库 → 恢复同一时间点文件 → 执行兼容迁移 → 检查资源计数、文件校验和与核心记录 → 运行烟测，再恢复写入。

应用回滚使用上一份已验证镜像；数据库变更优先通过向前修复迁移处理。`downgrade base` 会删除全部表，仅用于空库测试。`0002` 的收紧约束遇到不兼容旧数据会回滚并失败，需先核对数据，不自动编造提示原因或修改历史状态。

## 观测与故障

`/api/v1/health/live` 检查进程；`/api/v1/health/ready` 检查数据库连接与迁移版本。数据库故障、迁移未完成时 ready 返回 503。

API 日志记录路由模板、状态、耗时与 trace ID，不记录正文、Cookie、SQL 参数或完整请求 URL。worker 记录类型、作业 ID 与租约失效；监控应覆盖错误率、就绪状态、待处理作业年龄和失败作业数。外部服务恢复后重试需保留原幂等键。

部署验收包括 TLS、权限矩阵、恶意文件隔离、会话撤销、通知轮询与过期游标恢复、备份恢复及目标并发测试；这些业务与生产验收不由工程烟测替代。
