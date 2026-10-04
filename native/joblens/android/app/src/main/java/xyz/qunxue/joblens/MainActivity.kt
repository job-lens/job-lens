package xyz.qunxue.joblens

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.*
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.*
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import xyz.qunxue.joblens.core.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // A prior process interruption can leave a private PDF preview cache. Never retain it across launches.
        cacheDir.listFiles()?.filter { it.name.startsWith("joblens-preview-") }?.forEach { it.delete() }
        enableEdgeToEdge()
        setContent {
            JobLensTheme {
                val model: JobLensModel = viewModel()
                JobLensApp(model)
            }
        }
    }
}

@Composable
fun JobLensApp(model: JobLensModel) {
    val s by model.state.collectAsStateWithLifecycle()
    val density = LocalDensity.current
    CompositionLocalProvider(
        LocalDensity provides Density(density.density, density.fontScale * s.fontScale)
    ) {
        JobLensContent(s, model)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobLensContent(s: UiState, model: JobLensModel) {
    val authenticated = s.user != null
    val scrollState = remember(s.sessionScope, s.route) { ScrollState(0) }
    BackHandler(enabled = s.route.page !in setOf(Page.LOGIN, Page.HOME)) {
        if (!s.busy) model.back()
    }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Brand(size = 30)
                        Text("融职境", style = MaterialTheme.typography.titleMedium)
                    }
                },
                navigationIcon = {
                    if (s.route.page !in setOf(Page.LOGIN, Page.HOME))
                        IconButton(onClick = model::back, enabled = !s.busy) {
                            QIcon(R.drawable.ic_back, "返回")
                        }
                },
                actions = {
                    if (authenticated)
                        IconButton(onClick = model::load, enabled = !s.loading && !s.busy) {
                            QIcon(R.drawable.ic_refresh, "刷新")
                        }
                },
                colors =
                    TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background
                    ),
            )
        },
        bottomBar = {
            if (authenticated) {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                    val items =
                        listOf(
                            Triple(
                                Page.HOME,
                                if (s.role == "counselor") "工作台" else "任务",
                                R.drawable.ic_tasks,
                            ),
                            Triple(
                                if (s.role == "counselor") Page.CASES else Page.RECORDS,
                                if (s.role == "counselor") "个案" else "记录",
                                if (s.role == "counselor") R.drawable.ic_users
                                else R.drawable.ic_records,
                            ),
                            Triple(Page.SUPPORT, "求助", R.drawable.ic_chat),
                            Triple(Page.NOTIFICATIONS, "通知", R.drawable.ic_bell),
                            Triple(Page.ACCOUNT, "我的", R.drawable.ic_user),
                        )
                    items.forEach { (page, title, icon) ->
                        NavigationBarItem(
                            selected = s.route.page == page,
                            onClick = { model.root(page) },
                            enabled = !s.busy,
                            icon = { QIcon(icon) },
                            label = { Text(title) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp)
                .padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            if (s.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (s.error.isNotEmpty()) {
                Notice(s.error, true)
                if (s.sessionBlocked) Action("重试会话验证", click = model::restore)
                else if (s.unknown) {
                    Action("读取最新状态", secondary = true, click = model::load)
                    if (authenticated && s.retryAvailable)
                        Action("重试原请求", secondary = true, click = model::retryWrite)
                } else if (authenticated) Action("重新读取", secondary = true, click = model::load)
            }
            if (s.info.isNotEmpty()) Notice(s.info)
            if (s.busy) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Action("停止等待", secondary = true, click = model::cancelRequest)
            }
            key(s.sessionScope) {
                val holder = rememberSaveableStateHolder()
                holder.SaveableStateProvider(
                    "${s.route.page}|${s.route.id}|${s.route.parent}|${s.route.step}"
                ) {
                    if (!s.sessionBlocked)
                        when (s.route.page) {
                            Page.LOGIN,
                            Page.REGISTER,
                            Page.FORGOT -> AuthScreen(s, model)
                            Page.HOME -> HomeScreen(s, model)
                            Page.CASES -> CasesScreen(s, model)
                            Page.RECORDS -> RecordsScreen(s, model)
                            Page.TASK -> TaskScreen(s, model)
                            Page.CASE -> CaseScreen(s, model)
                            Page.MATCH -> MatchScreen(s, model)
                            Page.PLANS -> PlansScreen(s, model)
                            Page.REVISION -> RevisionScreen(s, model)
                            Page.SUBMISSION -> SubmissionScreen(s, model)
                            Page.SUPPORT -> SupportScreen(s, model)
                            Page.ASSISTANCE -> AssistanceScreen(s, model)
                            Page.NEW_SUPPORT -> NewSupportScreen(s, model)
                            Page.NOTIFICATIONS -> NotificationsScreen(s, model)
                            Page.PROFILE -> ProfileScreen(s, model)
                            Page.PREFERENCES -> PreferencesScreen(s, model)
                            Page.ACCOUNT -> AccountScreen(s, model)
                            Page.FILE -> FileScreen(s, model)
                        }
                }
            }
        }
    }
}

@Composable
private fun AuthScreen(s: UiState, m: JobLensModel) {
    var account by rememberSaveable(s.route.page) { mutableStateOf("") }
    var name by rememberSaveable(s.route.page) { mutableStateOf("") }
    var code by rememberSaveable(s.route.page) { mutableStateOf("") }
    var password by remember(s.route.page) { mutableStateOf("") }
    val register = s.route.page == Page.REGISTER
    val forgot = s.route.page == Page.FORGOT
    Spacer(Modifier.height(20.dp))
    Brand(size = 64)
    Heading(
        if (register) "注册" else if (forgot) "找回密码" else "登录",
        if (register) "注册后，进入你的学员工作台。" else if (forgot) "通过注册邮箱，重新设置密码。" else "今天，从一步开始。",
    )
    if (register) Field("怎么称呼你", name, { name = it }, enabled = !s.busy, max = 80)
    Field(
        if (register || forgot) "邮箱" else "账号",
        account,
        { account = it },
        enabled = !s.busy,
        keyboard = if (register || forgot) KeyboardType.Email else KeyboardType.Text,
        max = 80,
    )
    if (register) {
        Field(
            "6 位验证码",
            code,
            { code = it.filter { c -> c in '0'..'9' } },
            enabled = !s.busy,
            keyboard = KeyboardType.Number,
            max = 6,
        )
        var cooldown by remember { mutableStateOf(0) }
        LaunchedEffect(m.codeCooldownUntil) {
            while (true) {
                cooldown =
                    ((m.codeCooldownUntil - System.currentTimeMillis()) / 1000)
                        .toInt()
                        .coerceAtLeast(0)
                if (cooldown == 0) break
                kotlinx.coroutines.delay(1000)
            }
        }
        Action(
            if (cooldown > 0) "${cooldown} 秒后可重发" else "获取验证码",
            enabled = !s.busy && emailValid(account) && cooldown == 0,
            secondary = true,
        ) {
            m.sendCode(account)
        }
    }
    if (!forgot) {
        Field(
            if (register) "设置密码" else "密码",
            password,
            { password = it },
            enabled = !s.busy,
            password = true,
            max = 256,
        )
        if (register) Meta("至少 12 个字符。")
    }
    Action(
        if (register) "注册" else if (forgot) "发送找回链接" else "登录",
        enabled =
            !s.busy &&
                account.isNotBlank() &&
                (if (register)
                    name.isNotBlank() &&
                        code.length == 6 &&
                        password.length >= 12 &&
                        emailValid(account)
                else if (forgot) emailValid(account) else password.isNotEmpty()),
        modifier = Modifier.fillMaxWidth(),
    ) {
        if (register) m.register(name, account, code, password)
        else if (forgot) m.forgot(account) else m.login(account, password)
    }
    if (s.route.page == Page.LOGIN) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Action("注册账号", secondary = true) { m.navigate(Route(Page.REGISTER)) }
            TextButton(onClick = { m.navigate(Route(Page.FORGOT)) }) { Text("忘记密码") }
        }
    } else
        TextButton(onClick = { m.root(if (s.user == null) Page.LOGIN else Page.ACCOUNT) }) {
            Text(if (s.user == null) "返回登录" else "返回账户")
        }
    Meta("账号权限由平台管理。你可以随时暂停，再按自己的节奏继续。")
}

private fun emailValid(v: String) = v.trim().matches(Regex("[^@\\s]+@[^@\\s]+\\.[^@\\s]+"))
