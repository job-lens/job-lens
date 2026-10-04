package xyz.qunxue.joblens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

@Composable
fun AccountScreen(s: UiState, m: JobLensModel) {
    val user = s.user ?: return
    Heading(user.text("display_name"), "调整使用方式，让支持更适合你。")
    QCard {
        Text("当前身份", style = MaterialTheme.typography.titleMedium)
        JobLensApi.roles(user).forEach { role ->
            Action(
                if (role == "counselor") "辅导员工作台" else "学员工作台",
                !s.busy,
                secondary = role != s.role,
            ) {
                m.role(role)
            }
        }
        Meta("身份权限来自服务端，无法在本机自行授予。")
    }
    Action("个人资料", secondary = true) { m.navigate(Route(Page.PROFILE)) }
    Action("阅读与提醒", secondary = true) { m.navigate(Route(Page.PREFERENCES)) }
    Action("通过邮箱找回密码", secondary = true) { m.navigate(Route(Page.FORGOT)) }
    val context = LocalContext.current
    Action("打开网页版", secondary = true) {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(PRODUCTION_ORIGIN)))
    }
    var confirm by remember { mutableStateOf(false) }
    Action("退出登录", !s.busy, secondary = true) { confirm = true }
    ConfirmDialog(confirm, "退出当前账号？", "退出后将撤销当前会话，并清除本机的账号数据缓存。", { confirm = false }) {
        confirm = false
        m.logout()
    }
    Meta("融职境 Android · 0.1.0\n原生 Kotlin / Compose · ${PRODUCTION_ORIGIN.removePrefix("https://")}")
}

@Composable
fun ProfileScreen(s: UiState, m: JobLensModel) {
    val p = s.data["profile"] ?: return
    Heading("个人资料", "记录你希望辅导员了解的需要，之后可以随时修改。")
    var name by rememberSaveable(p.text("user_id")) { mutableStateOf(p.text("display_name")) }
    var communication by
        rememberSaveable(p.text("user_id")) { mutableStateOf(p.text("communication_preference")) }
    var sensory by
        rememberSaveable(p.text("user_id")) {
            mutableStateOf(
                p.array("sensory_preferences").joinToString("、") { it.jsonPrimitive.content }
            )
        }
    var work by rememberSaveable(p.text("user_id")) { mutableStateOf(p.text("work_notes")) }
    var baseVersion by rememberSaveable(p.text("user_id")) { mutableStateOf(p.number("version")) }
    Field("怎么称呼你", name, { name = it }, !s.busy, max = 80)
    Field("喜欢的沟通方式", communication, { communication = it }, !s.busy, max = 200)
    Field("感官偏好，用顿号分开", sensory, { sensory = it }, !s.busy, max = 410)
    Field("希望辅导员了解的工作情况", work, { work = it }, !s.busy, multiline = true, max = 1000)
    val sensoryItems = sensory.split(Regex("[、,，\n]")).map(String::trim).filter(String::isNotEmpty)
    Action(
        "保存资料",
        !s.busy &&
            name.isNotBlank() &&
            sensoryItems.size <= 10 &&
            sensoryItems.all { it.length <= 40 },
    ) {
        m.write(
            "PUT",
            "/me/profile",
            json(
                "display_name" to name.trim(),
                "communication_preference" to communication,
                "sensory_preferences" to strings(sensoryItems),
                "work_notes" to work,
            ),
            baseVersion,
        ) {
            baseVersion = it.number("version")
            m.replaceData("profile", it)
        }
    }
    if (p.number("version") != baseVersion) {
        Notice("已读取新版本，你的输入仍保留。采用最新资料会替换当前未保存输入。")
        Action("采用最新资料", secondary = true) {
            name = p.text("display_name")
            communication = p.text("communication_preference")
            sensory = p.array("sensory_preferences").joinToString("、") { it.jsonPrimitive.content }
            work = p.text("work_notes")
            baseVersion = p.number("version")
        }
    }
}

@Composable
fun PreferencesScreen(s: UiState, m: JobLensModel) {
    val p = s.data["preferences"] ?: return
    Heading("阅读与提醒", "选择适合你的文字和提示方式。")
    var quiet by rememberSaveable { mutableStateOf(p.flag("quiet_mode")) }
    var speech by rememberSaveable { mutableStateOf(p.flag("speech_enabled")) }
    var vibration by rememberSaveable { mutableStateOf(p.flag("vibration_enabled")) }
    var scale by rememberSaveable {
        mutableStateOf(p["font_scale"]?.jsonPrimitive?.floatOrNull ?: 1f)
    }
    var volume by rememberSaveable {
        mutableStateOf(p["volume"]?.jsonPrimitive?.floatOrNull ?: 0.5f)
    }
    var baseVersion by rememberSaveable { mutableStateOf(p.number("version")) }
    QCard {
        Toggle("安静模式", quiet, !s.busy) { quiet = it }
        Meta("优先关闭声音与震动，保留文字指引。")
        Text("文字大小")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(1f to "标准", 1.25f to "较大", 1.5f to "更大").forEach { (value, title) ->
                FilterChip(
                    selected = value == scale,
                    onClick = { scale = value },
                    label = { Text(title) },
                    enabled = !s.busy,
                )
            }
        }
        Toggle("语音指引", speech, !s.busy) { speech = it }
        Toggle("震动提示", vibration, !s.busy) { vibration = it }
        Text("音量 · ${(volume*100).toInt()}%")
        Slider(value = volume, onValueChange = { volume = it }, enabled = !s.busy)
        Meta("首版 Android 采用静音文字指引。声音与震动设置同步至网页版。")
    }
    Action("保存设置", !s.busy) {
        m.write(
            "PUT",
            "/me/preferences",
            json(
                "font_scale" to scale,
                "volume" to volume,
                "quiet_mode" to quiet,
                "speech_enabled" to speech,
                "vibration_enabled" to vibration,
            ),
            baseVersion,
        ) {
            baseVersion = it.number("version")
            m.replaceData("preferences", it)
        }
    }
    if (p.number("version") != baseVersion)
        Action("采用最新设置", secondary = true) {
            quiet = p.flag("quiet_mode")
            speech = p.flag("speech_enabled")
            vibration = p.flag("vibration_enabled")
            scale = p["font_scale"]?.jsonPrimitive?.floatOrNull ?: 1f
            volume = p["volume"]?.jsonPrimitive?.floatOrNull ?: 0.5f
            baseVersion = p.number("version")
        }
}
