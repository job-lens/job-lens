JobLens Android 0.1.1 · 冻结候选验证记录
日期：2026-10-04
应用：xyz.qunxue.joblens，versionCode 2，versionName 0.1.1，minSdk 26 / targetSdk 35。

视觉基准
当前 Web main e6a9c9fc9f6c45abe5ec94d65aff556505ca859e。
实际在云浏览器查看公开首页、登录、注册、找回密码。登录后场景根据同一提交的页面和 CSS 核对。

主要修正
1. 原版“小融”的 SVG 路径、渐变、耳机、短发、蓝衣和前后层转换成真正的 Compose Canvas。
2. 4.2秒呼吸、5秒刘海轻摆、5.6秒眨眼、自然张望、点击笑眼；密码聚焦闭眼。暂停持续保存，系统减少动态/后台时停动。
3. 登录/注册/找回密码恢复居中版式、灰色胶囊输入、黑色主操作。空提交先进行本地必填校验，不联网。中文认证标题附带7KB官方Noto衬线字形子集及许可证。
4. 手机工作区改为原生抽屉，保留服务端角色与所有权；标题使用 Web 工作区的无衬线覆盖规则。
5. 学员三张统计卡、任务卡与空态；训练未开始/暂停/修改/完成的小融，进行/提交状态的原版文件插画；辅导员竖排待办、继续跟进、支持流程。
6. 完整逐页依据见源码 design/WEB-PARITY.md。

构建与检查
- 本次 core 测试任务成功，API核心无修改，Gradle复用已通过的30项结果。
- 独立模型测试任务成功，模型无修改，Gradle复用已通过的6项结果。
- 新 app APK 和 androidTest APK 编译完成；最终 lint：0错误、17条非阻断警告（见随附报告）。
- 最终APK的apksigner验证通过，签名证书与0.1.0云端测试包相同；压缩包逐项读取验证通过。

设备验收：尚未通过，不能作为14项通过报告。
软件模拟器187秒冷启动完成、应用和测试APK安装成功、应用预编译成功；测试APK预编译阶段模拟器意外退出。没有执行本轮应用UI测试，没有产生有效的新Android截图。云端模拟器与ADB已退出，不再反复重试。
14项仪器测试已编译，等待GitHub KVM使用同一个CI构建的待发布APK运行并输出真实截图。只有KVM结果明确通过、截图逐张核对后，才应完成视觉验收及发布。

KVM命令
./gradlew :core:test :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell setprop debug.hwui.drawing_enabled true
adb shell am instrument -w -e class xyz.qunxue.joblens.NativeUiTest xyz.qunxue.joblens.test/androidx.test.runner.AndroidJUnitRunner
adb pull /sdcard/Android/data/xyz.qunxue.joblens/files/qa SCREENSHOT_DIRECTORY
必要时预编译应用和测试包：adb shell cmd package compile -m speed -f PACKAGE。
实际生产登录截图：先am start -W -n xyz.qunxue.joblens/.MainActivity，等待绘制后adb exec-out screencap -p。

测试与生产隔离
测试数据、截图标注和Stub均只在androidTest/独立验证目录，不在主APK。需要账号的截图必须保留“界面测试 · 合成数据 · 非生产账号”标注。
没有登录真实账号、创建生产账号、发真实邮件、上传或修改生产业务数据。现有注册邮件失败没有被客户端伪装成成功。
API、CSRF、Cookie隔离/加密、资源版本、幂等和未知结果处理未因这次视觉修改而改变。

分发限制
当前为debug测试签名，不是商店/生产签名。云端APK沿用之前JobLens隔离测试key，可覆盖云端0.1.0候选。CI若另生成debug key，其APK签名和SHA将不同，不能把云端验收记录的二进制SHA冒充CI的SHA；不同签名升级可能要求先卸载。源代码包不含任何签名私钥、会话或账号凭据。

其余边界
未做真实账号端到端业务验证、实体手机/API26–34压力验证；未新增语音、震动、实时通话、管理后台或发布签名流程。触屏采用点击和自然张望，不模拟桌面鼠标追踪。
