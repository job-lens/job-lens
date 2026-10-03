# 独立 Release 部署

此流程只操作 JobLens 独立目录、Compose 项目和数据卷。普通 PR/main 更新不会触发上线；在 Actions 手动运行 `Deploy JobLens Release` 并传入已发布的正式 `vX.Y.Z`。工作流核对 tag 的精确提交属于 main、同一提交的 Architecture CI push 运行成功，再在 runner 构建镜像。镜像 ID、校验和及部署文件保存在对应 artifact 中。

## 一次性配置

通过授权的安全流程配置 JobLens 自己的 GitHub `Production` 环境：`JOBLENS_DEPLOY_HOST`、`JOBLENS_DEPLOY_USER`、`JOBLENS_DEPLOY_PASSWORD`、`JOBLENS_DEPLOY_KNOWN_HOSTS`。known_hosts 必须来自可信核验，不临时扫描后自动信任。不复制其他项目的凭据；工作流不创建账号、密钥或权限。

在已确认的目标机准备专属 `/opt/job-lens` 和 `/etc/job-lens/joblens.env`，后者权限为 0600，字段参考 `infra/joblens.env.example`。数据库 URL 必须指向专属 `db:5432/job_lens`，口令与 POSTGRES_PASSWORD 一致且 URL 编码。镜像字段由工作流根据提交覆盖。默认 S3 配置须支持私有访问和 AES256 服务端加密，也可明确选择下述本地私有存储；注册/找回密码需要真实 Resend key 和已验证发件人；开启上传需要可达且经授权的真实 ClamAV 服务。配置值不得提交到 Git。

### 轻量启动：账号可用、上传暂未开通

首次上线可设置 `JOB_LENS_STORAGE_KIND=local`、`JOB_LENS_SCAN_ENABLED=false`。仍使用 production 环境与 HTTPS；不需要 S3 配置，也不启动扫描容器。私有文件保存在项目专属 `joblens-release_private-files` 卷，固定路径 `/srv/.data/private`，仅 API 与 worker 挂载，网关与迁移容器不可访问。容器非 root 用户延续原镜像的 UID 10001，文件仍为 0600，所有内容读取仍经 API 的会话、个案权限和 ready 状态校验，不能将此卷作为静态站点目录或公共目录挂载。

扫描停用时新上传明确返回 503 `SCAN_UNAVAILABLE`（“文件检测暂不可用，上传暂不可用”），不会创建私有 blob、文件记录或扫描作业。注册、验证码、登录不依赖扫描；资料附件、SOP 媒体和训练证据上传暂不可用，必须向使用者说明。既有隔离文件仍不可发布或下载，已 ready 的文件仍遵守原有下载授权。扫描处理器也拒绝处理，不会伪造 clean。此前已存在的扫描作业仍按原重试上限失败并保持隔离；重新启用后需核对失败作业并按既有运维流程重试，不能直接改为 ready。

启用上传时保持 `JOB_LENS_STORAGE_KIND=local` 不变，为 API/worker 设置真实且经授权的 `JOB_LENS_SCAN_HOST`（非默认端口再设置 `JOB_LENS_SCAN_PORT`），将唯一功能开关 `JOB_LENS_SCAN_ENABLED` 改为 `true`，通过正常发布重建服务环境。部署会要求 scanner PING 成功，随后另做真实文件扫描验收。这个升级不改数据库、不迁移本地文件、不改变私有卷或文件授权。S3 仍可选；已有本地文件时不能仅把 storage_kind 改为 s3，须另行备份和迁移所有现存存储 key 后验收，当前改动不自动搬迁数据。

`j.qunxue.xyz` 须正确解析、443 外部可达且没有被其他服务占用。独立网关只发布公网 443 与 loopback 8126；禁用 HTTP 自动跳转和 HTTP ACME challenge，不抢占现有公共 80 或改动共享反代。自动证书使用 TLS-ALPN-01，要求 443 直达此网关；Cloudflare 代理模式并不自动满足这一条件。已有代理、DNS、证书、系统安全设置均不由本工作流调整。

## 运行边界

固定项目 `joblens-release`、独立网络和数据卷；不加载其他目录的 Compose override，不挂载其他业务目录。网络 MTU 1450 适用于已核验的目标链路，迁移主机时应重新评估。

传包前只读检查配置存在、DNS、端口和资源。磁盘余量必须超过压缩包四倍加 2 GiB；MemAvailable 至少 2 GiB。这只是保守下限，不能证明共享业务峰值下安全。运行内存上限合计 1,408 MiB，迁移临时另加 384 MiB，真实目标仍需容量核验。这里不启动本地 ClamAV、不清理镜像/数据、不关闭告警；资源不足立即失败。

部署串行锁定，只加载 CI 构建的镜像并验证精确 ID，先校验生产设置、邮件配置，扫描启用时还需 scanner PING，再执行无构建/无拉取的 Compose 启动。扫描停用时日志明确标注 uploads unavailable，不将账号上线表述成完整文件功能上线。公网及 loopback readiness 成功后才写专属 deployed-sha 记录。HTTP 健康不代表私有存储、邮件投递或业务验收已经通过：仍须用授权账号完成真实验证码注册、登录/退出；上传仅在启用真实扫描后单独验收。

## 失败与重试

失败不自动回滚数据库、不删除数据卷、不重启其他项目。原 Release 可以重试；每次运行保留自己的校验和及镜像 ID，检查结果以该次 artifact 为准。升级前应完成专属数据库及私有文件备份；数据库迁移并非自动可逆。恢复按 `docs/deployment.md` 执行，不使用 `down -v` 或主机级 prune。

所有代码检查通过仍不等于已部署。安全配置、实际 DNS/TLS、服务器容量和外部服务必须另行核验。
