JobLens Android 0.1.1 · CI 测试候选验证记录
日期：2026-10-04
应用：xyz.qunxue.joblens，versionCode 2，versionName 0.1.1，minSdk 26 / targetSdk 35。

已通过的设备验收
源码提交：34c19c92cf83cb4c1d77f1a15f97d7980cfd99b2
Android CI：https://github.com/job-lens/job-lens/actions/runs/37201340720
同一提交的 Architecture CI：https://github.com/job-lens/job-lens/actions/runs/37201340672
Android 构建、core 测试、lint、APK 签名校验及 Android 35 KVM 仪器测试均通过。
instrumentation.log 明确记录 OK (14 tests)，耗时 48.569 秒；不是仅编译测试。
14 项包含伙伴运动、暂停后像素不变、暂停设置持久化、密码聚焦闭眼、快速打开抽屉后返回仍保留页面。
此前云端软件模拟器退出导致的未完成记录已由本次 KVM 实测取代，无需再将设备验收标为待完成。
本地 30 项协议测试及 6 项状态回归保留此前通过记录；独立模型回归不冒充本次 CI 新执行的任务。

已验收 APK 身份
文件：joblens-android-test.apk
大小：10,754,563 bytes
SHA256：b7ef0b8fda4b49f5bfc9c04b7b1407679d9f032542ba35862fadb268fe296263
签名证书 SHA256：656705fc24f417d2981d29d096213c0af62940ba28fc86c350f994009284b3ec
apksigner 校验通过，证书主题为 C=US, O=Android, CN=Android Debug。
下载 APK、设备测试 APK-SHA256.txt 和 CI SHA256SUMS 一致。aapt 读取的包名、版本和最低/目标 API 与本记录一致。
以上哈希仅指该次 CI 产物；之后的 main 构建会生成新产物，必须以其自己的设备验收、SHA256SUMS 和签名为准。

视觉基准与截图
视觉对照基准为 Web e6a9c9fc9f6c45abe5ec94d65aff556505ca859e（不是当前 main）。
已查看公开首页、登录、注册、找回密码；登录后场景根据同一提交的页面和 CSS 核对。
原版“小融”的路径、渐变、耳机、短发、蓝衣和分层用 Compose Canvas 重建。含呼吸、眨眼、视线及刘海动作，可持续暂停，遵守系统减少动画及后台状态。
认证页恢复居中版式、灰色胶囊输入、黑色主操作；手机工作区使用原生抽屉。训练和空态使用对应伙伴/工作插画，辅导员保留 Web 原本没有伙伴的布局。
完整逐页依据见 design/WEB-PARITY.md。
00-production-login.png 为确切待测 APK 安装后的未登录画面，截屏前等待输入框和登录按钮出现并检查非黑帧。
其余带 synthetic 文件名的截图来自真实 Android 原生界面配合测试专用合成状态，须保留“界面测试 · 合成数据 · 非生产账号”标注。
测试数据、截图标注与 Stub 仅在独立 androidTest APK，不随主 APK 分发。

下载与增量 CD 兼容核对
网站入口：/downloads/joblens-android-test.apk（安卓下载测试版）。
发布脚本先验证版本化公开 URL 字节哈希，再更新 latest 链接；/downloads/android.json 记录该次 SHA256、源码 revision 和 test channel。
APK 独立持久化到 /opt/job-lens/downloads。网站更新保留 main 的增量 deploy_joblens.sh，在 web 被替换时恢复下载目录。
与 main a4de7e59e73f4dc3f0c23132de92d867304e0846 整合时保留其 deploy.yml、release_scope.py、镜像层复用和只重启受影响服务的实现。
本次针对性复核：6 项隔离发布脚本测试、4 项增量交付测试及两个发布脚本的 bash 语法检查通过。
本记录不代表已合并、生产上传或网站上线；分支 CI 发布 job 在 pull_request 事件上跳过。

分发与业务边界
当前为 CI Android Debug 测试签名，不是商店/生产签名。不同 runner 或以前云端生成的测试签名可能不同，无法直接覆盖同包名旧包；必要时先卸载，卸载会移除本机登录态。
没有创建或上传发布私钥；源代码包不含签名私钥、会话或账号凭据。
邮件发送及真实收件已由独立服务端任务验证；这不等于本次 Android 完成了完整注册验收。
本次 Android 未使用真实账号完成生产登录、完整注册、任务写入或真实业务端到端测试。
API、CSRF、Cookie 隔离/加密、资源版本、幂等与未知结果处理未因视觉修改或本次下载兼容整合而改变。
未做实体手机/API26–34 压力验证；未新增语音、震动、实时通话、管理后台或发布签名流程。触屏采用点击和自然张望，不模拟桌面鼠标追踪。
