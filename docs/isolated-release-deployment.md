# 独立 Release 部署

此流程只操作 JobLens 独立目录、Compose 项目和数据卷。普通 PR/main 更新不会触发上线；在 Actions 手动运行 `Deploy JobLens Release` 并传入已发布的正式 `vX.Y.Z`。工作流核对 tag 的精确提交属于 main、同一提交的 Architecture CI push 运行成功，再在 runner 构建镜像。镜像 ID、校验和及部署文件保存在对应 artifact 中。

## 一次性配置

通过授权的安全流程配置 JobLens 自己的 GitHub `Production` 环境：`JOBLENS_DEPLOY_HOST`、`JOBLENS_DEPLOY_USER`、`JOBLENS_DEPLOY_PASSWORD`、`JOBLENS_DEPLOY_KNOWN_HOSTS`。known_hosts 必须来自可信核验，不临时扫描后自动信任。不复制其他项目的凭据；工作流不创建账号、密钥或权限。

在已确认的目标机准备专属 `/opt/job-lens` 和 `/etc/job-lens/joblens.env`，后者权限为 0600，字段参考 `infra/joblens.env.example`。数据库 URL 必须指向专属 `db:5432/job_lens`，口令与 POSTGRES_PASSWORD 一致且 URL 编码。镜像字段由工作流根据提交覆盖。独立 S3 配置须支持私有访问和 AES256 服务端加密；注册/找回密码需要真实 Resend key 和已验证发件人；上传扫描需要可达的真实 ClamAV 服务。配置值不得提交到 Git。

`j.qunxue.xyz` 须正确解析、443 外部可达且没有被其他服务占用。独立网关只发布公网 443 与 loopback 8126；禁用 HTTP 自动跳转和 HTTP ACME challenge，不抢占现有公共 80 或改动共享反代。自动证书使用 TLS-ALPN-01，要求 443 直达此网关；Cloudflare 代理模式并不自动满足这一条件。已有代理、DNS、证书、系统安全设置均不由本工作流调整。

## 运行边界

固定项目 `joblens-release`、独立网络和数据卷；不加载其他目录的 Compose override，不挂载其他业务目录。网络 MTU 1450 适用于已核验的目标链路，迁移主机时应重新评估。

传包前只读检查配置存在、DNS、端口和资源。磁盘余量必须超过压缩包四倍加 2 GiB；MemAvailable 至少 2 GiB。这只是保守下限，不能证明共享业务峰值下安全。运行内存上限合计 1,408 MiB，迁移临时另加 384 MiB，真实目标仍需容量核验。这里不启动本地 ClamAV、不清理镜像/数据、不关闭告警；资源不足立即失败。

部署串行锁定，只加载 CI 构建的镜像并验证精确 ID，先校验生产设置、邮件配置和 scanner PING，再执行无构建/无拉取的 Compose 启动。公网及 loopback readiness 成功后才写专属 deployed-sha 记录。HTTP 健康不代表 S3、邮件投递或业务验收已经通过：仍须用授权账号完成真实验证码注册、登录/退出，以及上传扫描验收。

## 失败与重试

失败不自动回滚数据库、不删除数据卷、不重启其他项目。原 Release 可以重试；每次运行保留自己的校验和及镜像 ID，检查结果以该次 artifact 为准。升级前应完成专属数据库及私有文件备份；数据库迁移并非自动可逆。恢复按 `docs/deployment.md` 执行，不使用 `down -v` 或主机级 prune。

所有代码检查通过仍不等于已部署。安全配置、实际 DNS/TLS、服务器容量和外部服务必须另行核验。
