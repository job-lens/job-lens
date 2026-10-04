融职境 JobLens Android 0.1.0 · 验证记录
交付日期：2026-10-04（UTC）

产物
- 包名：xyz.qunxue.joblens
- 版本：0.1.0 / versionCode 1
- 最低版本声明：Android 8 / API 26；目标和编译版本：Android 15 / API 35
- 原生 Kotlin + Jetpack Compose，无 WebView
- APK：joblens-android-0.1.0-debug.apk，11,060,418 字节
- APK SHA256：a05eef77f7a000096daebf10abc3079693429bbd205591772cfc8305a4264686
- 使用项目隔离的 Android debug 测试签名，apksigner 验证通过。未创建、上传或分发发布签名私钥。

本次已执行并通过
1. core 协议/安全测试：30/30，通过。
   覆盖 CSRF、固定 origin、Cookie 属性/过期/跨 origin 拒绝、旧账号响应隔离、服务端角色、If-Match、重复请求幂等键、空成功响应不当成功、错误码、上传格式与文件名校验等。
2. 独立 JVM 状态模型回归：6/6，通过。
   覆盖退出失败不重放旧写入、未知结果使用原幂等键、取消后的旧完成不回填、错误密码信息、401 清空私有页面、412 不丢失草稿/不自动覆盖。
   此测试使用轻量 Android 生命周期替身，不等同于真实设备生命周期测试。
3. Android 构建：app debug APK、独立 androidTest APK 均成功。
4. Android lint：0 errors、13 warnings。警告主要为命名/样式建议、同步 SharedPreferences、未使用图标等非阻断项；未使用 baseline 掩盖错误。
5. Android 原生界面测试：7/7，通过。最终 APK 再跑全套，耗时 150.22 秒。
   场景：登录输入、学员真实计数布局、步骤和提交状态、辅导员工作台、非本人任务不提供学员写操作、注册失败不显示成功、个人资料输入重组保持。
   设备：官方 Android 15 AOSP ATD x86_64，390×844 mdpi，云端纯软件 CPU / lavapipe 渲染。
6. 实际 MainActivity 冷启动 Status: ok；真实未登录应用界面截图已查看，无测试横幅或预填账号。
7. APK 字节检查：生产 APK 不含 NativeUiTest、测试账号、合成数据标识或测试替身代码。
8. 只读生产接口复核：2026-10-04 09:45 UTC，GET https://j.qunxue.xyz/api/v1/me 返回 HTTP 401 / UNAUTHENTICATED / 请先登录。

设计与来源
- Web/API 源码审阅基线：job-lens/job-lens main 790e886。
- 颜色、字号、圆角和原 SVG 品牌/导航路径来自 Web，已转换成原生控件与 VectorDrawable。
- 模拟器目检发现的 Material 默认紫色选中态已修为产品中性灰，最终截图重新拍摄并检查。
- 用户反馈当前部署为 e6a9c9f，注册邮件仍失败。客户端原样展示服务端错误，没有宣称或伪装服务端邮件已修复。

截图说明
- 00-production-login.png：实际 APK 未登录界面，无合成账号。
- qa/01-login-synthetic.png：原生输入测试，合成账号。
- qa/02-learner-home-synthetic.png：学员工作台，合成业务数据。
- qa/03-training-synthetic.png：训练步骤，合成业务数据。
- qa/04-counselor-home-synthetic.png：辅导员工作台，合成业务数据。
- qa/05-registration-error-synthetic.png：合成的邮件服务错误响应界面测试。
- qa/06-profile-synthetic.png：资料字段输入与真实 Android 键盘，合成资料。
六张测试截图均保留清晰的“界面测试 · 合成数据 · 非生产账号”横幅；测试数据只在独立测试 APK 和源码测试目录。

尚未验证或未覆盖
- 没有创建生产账号、发送真实邮件、用真实身份登录、上传真实附件或写入生产业务数据。真实登录/注册及学员—辅导员跨账号业务闭环尚需有效测试账号与正常后端服务才能验收。
- 图片/PDF 预览、上传扫描、SOP 发布/审核等已接入真实 API 和原生界面，但没有使用生产数据做完整端到端验证。
- 未做实体手机、Android 8–14、深色/超大字体、横竖屏重建和长时间后台恢复专项测试。
- 密码重置邮件深链接仍在网页完成；管理员/认证管理、标注编辑、音视频/AR、训练取消/提示等级覆盖、反馈标签和个案独立材料目录不在此首版完整覆盖范围。
- Android 首版采用静音文字指引；声音与震动偏好保存到服务器，尚未启用原生播报/震动。字号设置会在 Android 生效。
- 未知操作的原请求/幂等键在当前进程中保留；没有离线写队列。进程结束后应先刷新服务端状态再重新提交。

安装与开发
此 APK 为可安装测试版，不是商店发布版本。若同包名应用使用不同签名，更新可能需要先卸载旧测试版；卸载会移除本机会话。
源码不包含任何签名私钥、账号密码、API 密钥或环境凭据。常规开发机按 README 使用 JDK21 / SDK35 / Gradle wrapper 构建。
