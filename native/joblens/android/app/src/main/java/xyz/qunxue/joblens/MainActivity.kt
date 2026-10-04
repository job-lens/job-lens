package xyz.qunxue.joblens

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.*
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.*
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.input.*
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.launch
import xyz.qunxue.joblens.core.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // A prior process interruption can leave a private PDF preview cache. Never retain it
        // across launches.
        cacheDir
            .listFiles()
            ?.filter { it.name.startsWith("joblens-preview-") }
            ?.forEach { it.delete() }
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
    val authPage = s.route.page in setOf(Page.LOGIN, Page.REGISTER, Page.FORGOT)
    val scrollState = remember(s.sessionScope, s.route) { ScrollState(0) }
    BackHandler(enabled = s.route.page !in setOf(Page.LOGIN, Page.HOME)) {
        if (!s.busy) model.back()
    }
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val menuFocus = remember { FocusRequester() }
    val context = LocalContext.current
    val iconInk = MaterialTheme.colorScheme.onSurfaceVariant
    val pageTitle =
        when (s.route.page) {
            Page.HOME -> if (s.role == "counselor") "工作台" else "我的任务"
            Page.CASES,
            Page.CASE,
            Page.MATCH,
            Page.PLANS,
            Page.REVISION,
            Page.SUBMISSION -> "个案管理"
            Page.TASK -> if (s.role == "counselor") "个案管理" else "我的任务"
            Page.RECORDS -> "训练记录"
            Page.SUPPORT,
            Page.ASSISTANCE,
            Page.NEW_SUPPORT -> "辅导与求助"
            Page.NOTIFICATIONS -> "通知中心"
            else -> "设置"
        }
    LaunchedEffect(s.route, s.sessionScope) { drawer.close() }
    BackHandler(drawer.isOpen) {
        scope.launch {
            drawer.close()
            menuFocus.requestFocus()
        }
    }
    ModalNavigationDrawer(
        drawerState = drawer,
        gesturesEnabled = authenticated && !authPage && !s.busy,
        drawerContent = {
            if (authenticated)
                ModalDrawerSheet(
                    modifier = Modifier.padding(12.dp).width(300.dp),
                    drawerShape = RoundedCornerShape(28.dp),
                    drawerContainerColor = MaterialTheme.colorScheme.surface,
                ) {
                    Row(
                        Modifier.fillMaxWidth().padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Brand(size = 36)
                        Column(Modifier.weight(1f)) {
                            Text("融职境", style = MaterialTheme.typography.titleMedium)
                            Meta("Job Lens")
                        }
                        IconButton(
                            onClick = {
                                scope.launch {
                                    drawer.close()
                                    menuFocus.requestFocus()
                                }
                            }
                        ) {
                            Text(
                                "×",
                                fontSize = 26.sp,
                                modifier = Modifier.semantics { contentDescription = "关闭菜单" },
                            )
                        }
                    }
                    Column(
                        Modifier.weight(1f)
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        val roles = JobLensApi.roles(s.user!!)
                        Meta(
                            if (roles.size > 1) "学员与辅导员"
                            else if (s.role == "counselor") "辅导员工作区" else "学员工作区"
                        )
                        val destinations = buildList {
                            if ("counselor" in roles) {
                                add(Triple(Page.HOME, "工作台", "counselor"))
                                add(Triple(Page.CASES, "个案管理", "counselor"))
                                add(Triple(Page.SUPPORT, "辅导与求助", "counselor"))
                            }
                            if ("learner" in roles) {
                                add(Triple(Page.HOME, "我的任务", "learner"))
                                add(Triple(Page.RECORDS, "训练记录", "learner"))
                            }
                            add(Triple(Page.NOTIFICATIONS, "通知中心", s.role))
                        }
                        destinations.forEach { (page, title, role) ->
                            val icon =
                                when (page) {
                                    Page.CASES -> R.drawable.ic_users
                                    Page.SUPPORT -> R.drawable.ic_chat
                                    Page.RECORDS -> R.drawable.ic_records
                                    Page.NOTIFICATIONS -> R.drawable.ic_bell
                                    else ->
                                        if (role == "counselor") R.drawable.ic_home
                                        else R.drawable.ic_tasks
                                }
                            NavigationDrawerItem(
                                label = { Text(title) },
                                icon = { QIcon(icon) },
                                selected = page == s.route.page && role == s.role,
                                shape = RoundedCornerShape(14.dp),
                                onClick = {
                                    if (!s.busy) {
                                        if (s.role != role) model.role(role)
                                        if (page != Page.HOME || s.role == role) model.root(page)
                                        scope.launch { drawer.close() }
                                    }
                                },
                            )
                        }
                        Spacer(Modifier.height(24.dp))
                        Meta("一步一步，按自己的节奏。")
                    }
                    HorizontalDivider(
                        Modifier.padding(horizontal = 16.dp),
                        color = MaterialTheme.colorScheme.outline,
                    )
                    NavigationDrawerItem(
                        label = { Text("设置") },
                        icon = { QIcon(R.drawable.ic_settings) },
                        selected =
                            s.route.page in setOf(Page.ACCOUNT, Page.PROFILE, Page.PREFERENCES),
                        onClick = {
                            if (!s.busy) {
                                model.root(Page.ACCOUNT)
                                scope.launch { drawer.close() }
                            }
                        },
                        modifier = Modifier.padding(12.dp),
                    )
                    TextButton(
                        onClick = {
                            if (!s.busy) {
                                model.navigate(Route(Page.PROFILE))
                                scope.launch { drawer.close() }
                            }
                        },
                        modifier = Modifier.padding(horizontal = 16.dp),
                    ) {
                        Text(s.user?.text("display_name").orEmpty())
                    }
                    Spacer(Modifier.height(16.dp))
                }
        },
    ) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                TopAppBar(
                    title = {
                        if (authenticated && !authPage)
                            Text(pageTitle, style = MaterialTheme.typography.titleMedium)
                        else
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                if (s.route.page != Page.LOGIN) Brand(size = 26)
                                Text("融职境", style = MaterialTheme.typography.titleMedium)
                            }
                    },
                    navigationIcon = {
                        if (authenticated && !authPage)
                            IconButton(
                                onClick = { scope.launch { drawer.open() } },
                                enabled = !s.busy,
                                modifier = Modifier.focusRequester(menuFocus),
                            ) {
                                Canvas(
                                    Modifier.size(20.dp).semantics { contentDescription = "打开菜单" }
                                ) {
                                    repeat(3) {
                                        drawLine(
                                            iconInk,
                                            androidx.compose.ui.geometry.Offset(
                                                1f,
                                                size.height * (.25f + it * .25f),
                                            ),
                                            androidx.compose.ui.geometry.Offset(
                                                size.width - 1f,
                                                size.height * (.25f + it * .25f),
                                            ),
                                            1.7.dp.toPx(),
                                            androidx.compose.ui.graphics.StrokeCap.Round,
                                        )
                                    }
                                }
                            }
                        else if (authPage && s.route.page != Page.LOGIN)
                            IconButton(onClick = model::back, enabled = !s.busy) {
                                QIcon(R.drawable.ic_back, "返回")
                            }
                    },
                    actions = {
                        if (authenticated && !authPage)
                            IconButton(
                                onClick = { model.root(Page.NOTIFICATIONS) },
                                enabled = !s.busy,
                            ) {
                                QIcon(R.drawable.ic_bell, "打开通知中心")
                            }
                        else
                            TextButton(
                                onClick = {
                                    context.startActivity(
                                        Intent(Intent.ACTION_VIEW, Uri.parse(PRODUCTION_ORIGIN))
                                    )
                                }
                            ) {
                                Text("返回首页")
                            }
                    },
                    colors =
                        TopAppBarDefaults.topAppBarColors(
                            containerColor = MaterialTheme.colorScheme.background
                        ),
                )
            },
        ) { padding ->
            Column(
                Modifier.fillMaxSize()
                    .padding(padding)
                    .imePadding()
                    .verticalScroll(scrollState)
                    .padding(horizontal = 16.dp)
                    .padding(bottom = 28.dp),
                verticalArrangement = Arrangement.spacedBy(if (authPage) 0.dp else 24.dp),
            ) {
                if (s.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (s.error.isNotEmpty() && (!authPage || s.sessionBlocked)) {
                    Notice(s.error, true)
                    if (s.sessionBlocked) Action("重试会话验证", click = model::restore)
                    else if (s.unknown) {
                        Action("读取最新状态", secondary = true, click = model::load)
                        if (authenticated && s.retryAvailable)
                            Action("重试原请求", secondary = true, click = model::retryWrite)
                    } else if (authenticated) Action("重新读取", secondary = true, click = model::load)
                }
                if (s.info.isNotEmpty() && !authPage) Notice(s.info)
                if (s.busy && !authPage) {
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
}

@Composable
private fun AuthScreen(s: UiState, m: JobLensModel) {
    var account by rememberSaveable(s.route.page) { mutableStateOf("") }
    var name by rememberSaveable(s.route.page) { mutableStateOf("") }
    var code by rememberSaveable(s.route.page) { mutableStateOf("") }
    var password by remember(s.route.page) { mutableStateOf("") }
    var privateEntry by remember { mutableStateOf(false) }
    val register = s.route.page == Page.REGISTER
    val forgot = s.route.page == Page.FORGOT
    var validation by remember { mutableStateOf("") }
    LaunchedEffect(account, name, code, password) { validation = "" }
    val windowHeight =
        with(LocalDensity.current) { LocalWindowInfo.current.containerSize.height.toDp() }
    val minHeight = (windowHeight - 150.dp).coerceAtLeast(480.dp)
    Column(
        Modifier.fillMaxWidth().heightIn(min = minHeight),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Companion(closed = privateEntry)
        Spacer(Modifier.height(16.dp))
        Text(
            if (register) "注册" else if (forgot) "找回密码" else "登录",
            style = MaterialTheme.typography.headlineLarge.copy(fontSize = 36.sp),
            modifier = Modifier.semantics { heading() },
        )
        if (register || forgot) {
            Spacer(Modifier.height(16.dp))
            Meta(if (register) "注册后，进入你的学员工作台。" else "通过注册邮箱，重新设置密码。")
        }
        Spacer(Modifier.height(32.dp))
        Column(
            Modifier.widthIn(max = 352.dp).fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (register) AuthField("怎么称呼你", name, { name = it }, !s.busy, max = 80)
            AuthField(
                if (register || forgot) "邮箱" else "账号",
                account,
                { account = it },
                !s.busy,
                keyboard = if (register || forgot) KeyboardType.Email else KeyboardType.Text,
                max = 80,
            )
            if (register) {
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
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AuthField(
                        "6 位验证码",
                        code,
                        { code = it.filter { c -> c in '0'..'9' } },
                        !s.busy,
                        modifier = Modifier.weight(1f),
                        keyboard = KeyboardType.Number,
                        max = 6,
                    )
                    Action(
                        if (cooldown > 0) "${cooldown} 秒后重发" else "获取验证码",
                        !s.busy && emailValid(account) && cooldown == 0,
                        secondary = true,
                    ) {
                        m.sendCode(account)
                    }
                }
            }
            if (!forgot)
                AuthField(
                    if (register) "设置密码" else "密码",
                    password,
                    { password = it },
                    !s.busy,
                    password = true,
                    max = 256,
                    focusChanged = { privateEntry = it },
                )
            if (register) Meta("至少 12 个字符。")
            if (validation.isNotEmpty()) Notice(validation, true)
            if (s.error.isNotEmpty()) Notice(s.error, true)
            if (s.info.isNotEmpty()) Notice(s.info)
            if (s.busy) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Action("停止等待", secondary = true, click = m::cancelRequest)
            }
            Spacer(Modifier.height(0.dp))
            Action(
                if (register) "注册" else if (forgot) "发送找回链接" else "登录",
                enabled = !s.busy,
                modifier = Modifier.fillMaxWidth(),
            ) {
                validation =
                    when {
                        account.isBlank() -> if (register || forgot) "请填写邮箱。" else "请填写账号。"
                        (register || forgot) && !emailValid(account) -> "请填写有效邮箱。"
                        register && name.isBlank() -> "请填写称呼。"
                        register && code.length != 6 -> "请输入 6 位验证码。"
                        register && password.length < 12 -> "密码至少需要 12 个字符。"
                        !forgot && password.isEmpty() -> "请填写密码。"
                        else -> ""
                    }
                if (validation.isEmpty()) {
                    if (register) m.register(name, account, code, password)
                    else if (forgot) m.forgot(account) else m.login(account, password)
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        if (s.route.page == Page.LOGIN)
            Row(
                Modifier.widthIn(max = 352.dp).fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Action("注册账号", secondary = true) { m.navigate(Route(Page.REGISTER)) }
                TextButton(onClick = { m.navigate(Route(Page.FORGOT)) }) {
                    Text("忘记密码", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        else
            TextButton(onClick = { m.root(if (s.user == null) Page.LOGIN else Page.ACCOUNT) }) {
                Text(if (s.user != null) "返回账户" else if (forgot) "返回登录" else "已有账号？ 登录")
            }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun AuthField(
    label: String,
    value: String,
    change: (String) -> Unit,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    password: Boolean = false,
    keyboard: KeyboardType = KeyboardType.Text,
    max: Int = 256,
    focusChanged: (Boolean) -> Unit = {},
) {
    var focused by remember { mutableStateOf(false) }
    BasicTextField(
        value = value,
        onValueChange = { if (it.length <= max) change(it) },
        enabled = enabled,
        singleLine = true,
        modifier =
            modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .onFocusChanged {
                    focused = it.isFocused
                    focusChanged(it.isFocused)
                }
                .semantics { contentDescription = label },
        textStyle =
            MaterialTheme.typography.bodyLarge.copy(color = MaterialTheme.colorScheme.onSurface),
        keyboardOptions =
            KeyboardOptions(
                keyboardType = if (password) KeyboardType.Password else keyboard,
                imeAction = ImeAction.Next,
            ),
        visualTransformation =
            if (password) PasswordVisualTransformation() else VisualTransformation.None,
        cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
        decorationBox = { inner ->
            Surface(
                shape = RoundedCornerShape(50),
                color = MaterialTheme.colorScheme.surfaceVariant,
                border =
                    if (focused) BorderStroke(1.dp, MaterialTheme.colorScheme.onSurfaceVariant)
                    else null,
            ) {
                Box(
                    Modifier.padding(horizontal = 20.dp, vertical = 11.dp),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    if (value.isEmpty())
                        Text(
                            label,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = .65f),
                        )
                    inner()
                }
            }
        },
    )
}

private fun emailValid(v: String) = v.trim().matches(Regex("[^@\\s]+@[^@\\s]+\\.[^@\\s]+"))
