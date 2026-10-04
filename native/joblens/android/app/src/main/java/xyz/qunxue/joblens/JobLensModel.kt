package xyz.qunxue.joblens

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

enum class Page {
    LOGIN,
    REGISTER,
    FORGOT,
    HOME,
    RECORDS,
    TASK,
    CASES,
    CASE,
    MATCH,
    PLANS,
    REVISION,
    SUBMISSION,
    SUPPORT,
    ASSISTANCE,
    NEW_SUPPORT,
    NOTIFICATIONS,
    PROFILE,
    PREFERENCES,
    ACCOUNT,
    FILE,
}

data class Route(
    val page: Page,
    val id: String = "",
    val parent: String = "",
    val step: String = "",
)

data class UiState(
    val user: JsonObject? = null,
    val role: String = "learner",
    val route: Route = Route(Page.LOGIN),
    val data: Map<String, JsonObject> = emptyMap(),
    val loading: Boolean = true,
    val busy: Boolean = false,
    val error: String = "",
    val info: String = "",
    val sections: Map<String, String> = emptyMap(),
    val unknown: Boolean = false,
    val sessionBlocked: Boolean = false,
    val fontScale: Float = 1f,
    val retryAvailable: Boolean = false,
    val sessionScope: String = java.util.UUID.randomUUID().toString(),
)

class JobLensModel
@JvmOverloads
constructor(application: Application, suppliedApi: JobLensApi? = null, start: Boolean = true) :
    AndroidViewModel(application) {
    val api = suppliedApi ?: JobLensApi(HttpsTransport(), EncryptedSessionStore(application))
    private val ledger = CommandLedger()
    private val _state = MutableStateFlow(UiState())
    val state = _state.asStateFlow()
    private val stack = mutableListOf<Route>()
    private var readJob: Job? = null
    private var writeJob: Job? = null
    private var seq = 0
    private var operationSeq = 0L
    private var eventSequence = 0
    private var lastRequest: Request? = null
    private var lastSuccess: ((JsonObject) -> Unit)? = null
    var codeSentTo = ""
        private set

    var codeCooldownUntil = 0L
        private set

    init {
        if(start) {
            if(api.hasSession()) restore()
            else _state.value=UiState(loading=false)
        }
    }

    fun restore() {
        readJob?.cancel()
        readJob = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = "", sessionBlocked = false) }
            try {
                acceptUser(api.restore())
            } catch (e: CancellationException) {
                throw e
            } catch (e: ApiFailure) {
                if (e.status == 401) _state.value = UiState(loading = false)
                else
                    _state.update {
                        it.copy(loading = false, error = errorMessage(e), sessionBlocked = true)
                    }
            } catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, error = "暂时无法验证会话。请检查网络后重试。", sessionBlocked = true)
                }
            }
        }
    }

    private fun acceptUser(user: JsonObject) {
        ledger.clear()
        lastRequest = null
        lastSuccess = null
        stack.clear()
        seq++
        _state.value =
            UiState(
                user = user,
                role = if ("counselor" in JobLensApi.roles(user)) "counselor" else "learner",
                route = Route(Page.HOME),
                loading = false,
            )
        viewModelScope.launch {
            try {
                val preferences = api.get("/me/preferences")
                if (_state.value.user?.text("id") == user.text("id")) {
                    _state.update {
                        it.copy(
                            fontScale = preferences["font_scale"]?.jsonPrimitive?.floatOrNull ?: 1f
                        )
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (e is ApiFailure && e.status == 401) report(e)
            }
        }
        load()
    }

    fun login(account: String, password: String) = auth {
        api.login(account, password).also(::acceptUser)
    }

    fun register(name: String, email: String, code: String, password: String) = auth {
        api.register(name, email, code, password).also(::acceptUser)
    }

    private fun auth(block: suspend () -> Unit) {
        if (_state.value.busy) return
        lastRequest = null
        lastSuccess = null
        val ticket = ++operationSeq
        _state.update {
            it.copy(busy = true, error = "", info = "", unknown = false, retryAvailable = false)
        }
        writeJob = viewModelScope.launch {
            try {
                block()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (ticket == operationSeq) report(e)
            } finally {
                if (ticket == operationSeq) _state.update { it.copy(busy = false) }
            }
        }
    }

    fun sendCode(email: String) {
        if (System.currentTimeMillis() < codeCooldownUntil) return
        auth {
            api.write(Request("POST", "/auth/registration-code", json("email" to email.trim())))
            codeSentTo = email.trim().lowercase()
            codeCooldownUntil = System.currentTimeMillis() + 60_000
            _state.update { it.copy(info = "请求已受理，请查看邮箱。") }
        }
    }

    fun forgot(email: String) = auth {
        val result =
            api.write(
                Request("POST", "/auth/password-reset-requests", json("email" to email.trim()))
            )
        _state.update { it.copy(info = result.text("message", "请求已受理，请查看邮箱。")) }
    }

    fun logout() = auth {
        api.logout()
        clearUser()
    }

    private fun clearUser() {
        operationSeq++
        readJob?.cancel()
        seq++
        ledger.clear()
        stack.clear()
        lastRequest = null
        lastSuccess = null
        codeSentTo = ""
        _state.value = UiState(loading = false)
    }

    fun navigate(route: Route) {
        if (_state.value.busy) return
        stack.add(_state.value.route)
        _state.update {
            it.copy(
                route = route,
                data = emptyMap(),
                error = "",
                info = "",
                sections = emptyMap(),
                unknown = false,
            )
        }
        load()
    }

    fun back() {
        if (_state.value.busy) return
        val route =
            if (stack.isNotEmpty()) stack.removeAt(stack.lastIndex)
            else Route(if (_state.value.user == null) Page.LOGIN else Page.HOME)
        _state.update {
            it.copy(
                route = route,
                data = emptyMap(),
                error = "",
                info = "",
                sections = emptyMap(),
                unknown = false,
            )
        }
        load()
    }

    fun root(page: Page) {
        if (_state.value.busy) return
        stack.clear()
        _state.update {
            it.copy(
                route = Route(page),
                data = emptyMap(),
                error = "",
                info = "",
                sections = emptyMap(),
                unknown = false,
            )
        }
        load()
    }

    fun role(value: String) {
        if (value !in JobLensApi.roles(_state.value.user ?: return)) return
        _state.update { it.copy(role = value) }
        root(Page.HOME)
    }

    fun clearMessage() {
        _state.update { it.copy(error = "", info = "") }
    }

    fun load() {
        readJob?.cancel()
        val ticket = ++seq
        val snapshot = _state.value
        val route = snapshot.route
        if (
            route.page in
                setOf(Page.LOGIN, Page.REGISTER, Page.FORGOT, Page.ACCOUNT, Page.NEW_SUPPORT)
        ) {
            _state.update { it.copy(loading = false) }
            return
        }
        readJob = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = "", sections = emptyMap()) }
            val data = mutableMapOf<String, JsonObject>()
            val errors = mutableMapOf<String, String>()
            suspend fun fetch(key: String, path: String, optional: Boolean = false) {
                try {
                    data[key] = api.get(path)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    if (e is ApiFailure && e.status == 401) throw e
                    if (optional) errors[key] = errorMessage(e) else throw e
                }
            }
            try {
                val rid = if (route.id.isNotEmpty()) id(route.id) else ""
                when (route.page) {
                    Page.HOME -> {
                        fetch("dashboard", "/dashboard?view=${snapshot.role}")
                        fetch(
                            "list",
                            if (snapshot.role == "counselor") "/cases?limit=20"
                            else "/tasks?limit=20",
                        )
                        if (snapshot.role == "learner") fetch("cases", "/cases?limit=20", true)
                    }
                    Page.CASES -> fetch("list", "/cases?limit=20")
                    Page.RECORDS -> {
                        fetch("cases", "/cases?limit=100")
                        for (k in data.getValue("cases").rows()) fetch(
                            "records:${k.text("id")}",
                            "/cases/${id(k.text("id"))}/records?limit=100",
                            true,
                        )
                    }
                    Page.TASK -> {
                        fetch("task", "/tasks/$rid")
                        fetch("submissions", "/tasks/$rid/submissions?limit=20", true)
                    }
                    Page.CASE -> {
                        fetch("case", "/cases/$rid")
                        fetch("profile", "/cases/$rid/profile", true)
                        fetch("records", "/cases/$rid/records?limit=20", true)
                    }
                    Page.MATCH -> fetch("match", "/cases/$rid/match")
                    Page.PLANS -> fetch("list", "/cases/$rid/sop-plans?limit=20")
                    Page.REVISION -> fetch("revision", "/sop-revisions/$rid")
                    Page.SUBMISSION -> {
                        fetch("submission", "/submissions/$rid")
                        fetch(
                            "task",
                            "/tasks/${id(data.getValue("submission").text("task_id"))}",
                            true,
                        )
                        fetch(
                            "revision",
                            "/sop-revisions/${id(data.getValue("submission").text("revision_id"))}",
                            true,
                        )
                    }
                    Page.SUPPORT -> fetch("list", "/assistance-requests?limit=20")
                    Page.ASSISTANCE -> {
                        fetch("assistance", "/assistance-requests/$rid")
                        fetch("case", "/cases/${id(data.getValue("assistance").text("case_id"))}")
                        fetch("messages", "/assistance-requests/$rid/messages?limit=20", true)
                    }
                    Page.NOTIFICATIONS -> fetch("list", "/notifications?limit=50")
                    Page.FILE -> fetch("file", "/files/$rid")
                    Page.PROFILE -> fetch("profile", "/me/profile")
                    Page.PREFERENCES -> fetch("preferences", "/me/preferences")
                    else -> Unit
                }
                if (ticket == seq)
                    _state.update { it.copy(loading = false, data = data, sections = errors) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (ticket == seq) {
                    _state.update { it.copy(loading = false) }
                    report(e)
                }
            }
        }
    }

    fun more(key: String, path: String, notifications: Boolean = false) {
        if (_state.value.loading || _state.value.busy) return
        val previous = _state.value.data[key] ?: return
        val cursor = previous.text(if (notifications) "next_seq" else "next_cursor")
        if (cursor.isEmpty()) return
        val ticket = seq
        readJob = viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            try {
                val next =
                    api.get(
                        path +
                            (if ('?' in path) "&" else "?") +
                            (if (notifications) "after_seq=" else "cursor=") +
                            query(cursor)
                    )
                val rows =
                    (previous.rows() + next.rows()).distinctBy { it.text("id", it.text("task_id")) }
                val extra = mutableMapOf<String, JsonObject>()
                if (key == "cases" && _state.value.route.page == Page.RECORDS) {
                    for (case in
                        next.rows().filter {
                            it.text("learner_id") == _state.value.user?.text("id")
                        }) {
                        extra["records:${case.text("id")}"] =
                            api.get("/cases/${id(case.text("id"))}/records?limit=100")
                    }
                }
                if (ticket == seq)
                    _state.update {
                        it.copy(
                            data =
                                it.data +
                                    extra +
                                    (key to JsonObject(next + ("items" to JsonArray(rows)))),
                            loading = false,
                        )
                    }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (ticket == seq) {
                    _state.update { it.copy(loading = false) }
                    report(e)
                }
            }
        }
    }

    fun write(
        method: String,
        path: String,
        body: JsonObject? = null,
        version: Int? = null,
        success: ((JsonObject) -> Unit)? = null,
    ) {
        val owner = _state.value.user?.text("id") ?: return
        if (_state.value.busy) return
        val request = ledger.request(owner, method, path, body, version)
        execute(
            request,
            success
                ?: {
                    _state.update { s -> s.copy(info = "已保存。") }
                    load()
                },
        )
    }

    private fun execute(request: Request, success: (JsonObject) -> Unit) {
        if (_state.value.busy) return
        val owner = _state.value.user?.text("id") ?: return
        lastRequest = request
        lastSuccess = success
        val ticket = ++operationSeq
        _state.update {
            it.copy(busy = true, error = "", info = "", unknown = false, retryAvailable = true)
        }
        writeJob = viewModelScope.launch {
            try {
                val result = api.write(request)
                currentCoroutineContext().ensureActive()
                if (ticket == operationSeq && _state.value.user?.text("id") == owner) {
                    ledger.confirmed(owner, request)
                    _state.update { it.copy(busy = false, retryAvailable = false) }
                    lastRequest = null
                    lastSuccess = null
                    success(result)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (ticket == operationSeq) report(e)
            } finally {
                if (ticket == operationSeq) _state.update { it.copy(busy = false) }
            }
        }
    }

    fun recordHint(taskId: String, stepId: String) {
        val event =
            json(
                "event_id" to java.util.UUID.randomUUID().toString(),
                "session_id" to _state.value.sessionScope,
                "sequence" to ++eventSequence,
                "step_id" to id(stepId),
                "kind" to "hint_requested",
                "value" to 0,
                "observed_at" to java.time.Instant.now().toString(),
            )
        write("POST", "/tasks/${id(taskId)}/events", json("events" to JsonArray(listOf(event)))) {}
    }

    fun upload(request: Request, success: (JsonObject) -> Unit) {
        execute(request, success)
    }

    fun retryWrite() {
        if (!_state.value.unknown || !_state.value.retryAvailable) return
        val r = lastRequest ?: return
        execute(r, lastSuccess ?: { load() })
    }

    fun cancelRequest() {
        operationSeq++
        writeJob?.cancel()
        _state.update {
            it.copy(busy = false, unknown = true, error = "已停止等待。服务器可能已收到操作，请先刷新核对结果；重试会复用原请求。")
        }
    }

    fun replaceData(key: String, value: JsonObject) {
        _state.update {
            it.copy(
                data = it.data + (key to value),
                info = "已保存。",
                fontScale =
                    if (key == "preferences")
                        value["font_scale"]?.jsonPrimitive?.floatOrNull ?: it.fontScale
                    else it.fontScale,
                user =
                    if (key == "profile" && it.user != null)
                        JsonObject(
                            it.user + ("display_name" to JsonPrimitive(value.text("display_name")))
                        )
                    else it.user,
            )
        }
    }

    fun afterCreated(page: Page, parent: String = ""): (JsonObject) -> Unit = { value ->
        navigate(Route(page, value.text("id"), parent))
    }

    fun report(e: Exception) {
        if (e is ApiFailure && e.status == 401 && _state.value.user != null) {
            clearUser()
            _state.update { it.copy(error = "会话已结束。请重新登录。") }
        } else
            _state.update {
                it.copy(
                    error = errorMessage(e),
                    unknown = e is UnknownWrite,
                    retryAvailable = e is UnknownWrite && lastRequest != null,
                )
            }
    }

    private fun errorMessage(e: Exception) =
        when (e) {
            is ApiFailure ->
                when (e.status) {
                    412,
                    428 -> "内容已有更新。你的输入仍保留，请刷新读取最新版本后再编辑。"
                    403 -> e.message
                    else -> e.message
                }
            is UnknownWrite -> e.message ?: "操作结果尚未确认"
            else -> "连接未完成，请检查网络后重试。"
        }
}
