package xyz.qunxue.joblens.core

import java.net.URI
import java.net.URLEncoder
import java.security.MessageDigest
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.*

const val PRODUCTION_ORIGIN = "https://j.qunxue.xyz"
val JsonCodec = Json { ignoreUnknownKeys = true }

fun JsonObject.text(key: String, fallback: String = "") =
    (get(key) as? JsonPrimitive)?.contentOrNull ?: fallback

fun JsonObject.number(key: String, fallback: Int = 0) =
    (get(key) as? JsonPrimitive)?.intOrNull ?: fallback

fun JsonObject.flag(key: String, fallback: Boolean = false) =
    (get(key) as? JsonPrimitive)?.booleanOrNull ?: fallback

fun JsonObject.obj(key: String) = get(key) as? JsonObject ?: JsonObject(emptyMap())

fun JsonObject.array(key: String) = get(key) as? JsonArray ?: JsonArray(emptyList())

fun JsonObject.rows(key: String = "items") = array(key).mapNotNull { it as? JsonObject }

fun json(vararg values: Pair<String, Any?>): JsonObject =
    JsonObject(
        values.associate { (k, v) ->
            k to
                when (v) {
                    null -> JsonNull
                    is JsonElement -> v
                    is String -> JsonPrimitive(v)
                    is Boolean -> JsonPrimitive(v)
                    is Number -> JsonPrimitive(v)
                    else -> error("Unsupported JSON value")
                }
        }
    )

fun strings(values: List<String>) = JsonArray(values.map(::JsonPrimitive))

fun id(value: String): String = UUID.fromString(value).toString()

fun query(value: String) = URLEncoder.encode(value, "UTF-8")

data class Request(
    val method: String,
    val path: String,
    val body: JsonObject? = null,
    val version: Int? = null,
    val key: String? = null,
    val binaryBody: ByteArray? = null,
    val contentType: String? = null,
)

data class WireRequest(
    val method: String,
    val url: String,
    val headers: Map<String, String>,
    val body: String?,
    val binaryBody: ByteArray? = null,
)

data class WireResponse(
    val status: Int,
    val body: String,
    val cookies: List<String> = emptyList(),
    val bytes: ByteArray? = null,
)

fun interface Transport {
    suspend fun execute(request: WireRequest): WireResponse
}

interface SessionStore {
    fun read(): StoredSession?

    fun write(value: StoredSession?)
}

data class StoredSession(val cookie: String, val expiresAt: Long, val origin: String)

class MemorySessionStore : SessionStore {
    private var value: StoredSession? = null

    override fun read() = value

    override fun write(value: StoredSession?) {
        this.value = value
    }
}

class ApiFailure(
    val status: Int,
    val code: String,
    override val message: String,
    val trace: String = "",
) : Exception(message)

class UnknownWrite : Exception("连接中断，操作结果尚未确认。请读取最新状态，或使用原请求重试。")

/** Fixed-origin, redirect-free API. No account/role comes from a URL, intent, or local switch. */
class JobLensApi(
    private val transport: Transport,
    private val store: SessionStore = MemorySessionStore(),
    val origin: String = PRODUCTION_ORIGIN,
    private val now: () -> Long = System::currentTimeMillis,
) {
    private val mutex = Mutex()
    private var csrf: String? = null
    private var generation = 0L

    init {
        require(
            URI(origin).let {
                it.scheme == "https" &&
                    it.host != null &&
                    it.rawPath.isNullOrEmpty() &&
                    it.userInfo == null &&
                    it.query == null &&
                    it.fragment == null
            }
        )
    }

    fun clear() {
        synchronized(this) {
            generation++
            csrf = null
            store.write(null)
        }
    }

    fun hasSession(): Boolean = synchronized(this) { session()!=null }

    private fun session(): StoredSession? =
        store.read()?.takeIf { it.origin == origin && it.expiresAt > now() }

    private fun acceptCookies(values: List<String>) {
        for (line in values) {
            val parts = line.split(';').map { it.trim() }
            val pair = parts.first().split('=', limit = 2)
            if (pair.size != 2 || pair[0] != "__Host-jl_session") continue
            val attributes =
                parts.drop(1).associate {
                    val kv = it.split('=', limit = 2)
                    kv[0].lowercase() to kv.getOrElse(1) { "" }
                }
            if (
                !attributes.containsKey("secure") ||
                    attributes["path"] != "/" ||
                    attributes.containsKey("domain")
            )
                continue
            val age = attributes["max-age"]?.toLongOrNull() ?: continue
            if (age <= 0) {
                store.write(null)
                continue
            }
            if (!pair[1].matches(Regex("[A-Za-z0-9_-]{16,256}"))) continue
            store.write(StoredSession(pair[1], now() + age.coerceAtMost(43200) * 1000, origin))
        }
    }

    private suspend fun wire(request: Request): JsonObject {
        require(request.method in listOf("GET", "POST", "PUT", "DELETE"))
        require(
            request.path.startsWith("/") &&
                !request.path.startsWith("//") &&
                !request.path.contains('\\') &&
                !request.path.contains('#')
        )
        val url = "$origin/api/v1${request.path}"
        require(
            URI(url).let {
                it.host == URI(origin).host &&
                    it.rawPath.startsWith("/api/v1/") &&
                    !it.path.split('/').contains("..")
            }
        )
        request.version?.let { require(it > 0) }
        request.key?.let { require(it.matches(Regex("[!-~]{16,128}"))) }
        val epoch: Long
        val headers = mutableMapOf("Accept" to "application/json", "Origin" to origin)
        synchronized(this) {
            epoch = generation
            session()?.let { headers["Cookie"] = "__Host-jl_session=${it.cookie}" }
            if (request.method != "GET") csrf?.let { headers["X-CSRF-Token"] = it }
        }
        request.body?.let { headers["Content-Type"] = "application/json; charset=utf-8" }
        request.contentType?.let { headers["Content-Type"] = it }
        request.version?.let { headers["If-Match"] = "\"$it\"" }
        request.key?.let { headers["Idempotency-Key"] = it }
        val response =
            try {
                transport.execute(
                    WireRequest(
                        request.method,
                        url,
                        headers,
                        request.body?.toString(),
                        request.binaryBody,
                    )
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (request.method != "GET") throw UnknownWrite()
                throw e
            }
        currentCoroutineContext().ensureActive()
        synchronized(this) {
            if (epoch != generation)
                throw CancellationException("Previous account response discarded")
            acceptCookies(response.cookies)
        }
        val data =
            runCatching { JsonCodec.parseToJsonElement(response.body) as? JsonObject }.getOrNull()
                ?: JsonObject(emptyMap())
        if (response.status !in 200..299) {
            if (response.status == 401) clear()
            throw ApiFailure(
                response.status,
                data.text("code", "REQUEST_FAILED"),
                data.text("title", "请求未完成，请重试"),
                data.text("trace_id"),
            )
        }
        if (response.status != 204 && data.isEmpty()) {
            if (request.method != "GET") throw UnknownWrite()
            throw ApiFailure(502, "INVALID_RESPONSE", "服务器响应不完整，请重试")
        }
        if (request.method == "GET") {
            val path = request.path.substringBefore('?')
            val complete =
                when {
                    path == "/dashboard" ->
                        listOf("pending_tasks", "pending_feedback", "pending_assistance").all {
                            (data[it] as? JsonPrimitive)?.intOrNull?.let { value -> value >= 0 } ==
                                true
                        }
                    path in setOf("/tasks", "/cases", "/assistance-requests", "/notifications") ||
                        path.endsWith("/records") ||
                        path.endsWith("/submissions") ||
                        path.endsWith("/messages") ||
                        path.endsWith("/sop-plans") ->
                        data["items"] is JsonArray && data["has_more"] is JsonPrimitive
                    path.matches(Regex("/tasks/[^/]+")) ->
                        data.text("id").isNotEmpty() &&
                            data.number("version") > 0 &&
                            data.obj("revision")["steps"] is JsonArray &&
                            data["progress"] is JsonArray &&
                            data.text("status") in
                                setOf(
                                    "not_started",
                                    "in_progress",
                                    "paused",
                                    "submitted",
                                    "changes_requested",
                                    "completed",
                                    "cancelled",
                                )
                    else -> true
                }
            if (!complete) throw ApiFailure(502, "INVALID_RESPONSE", "服务器响应不完整，请重试")
        }
        return data
    }

    suspend fun get(path: String) = wire(Request("GET", path))

    suspend fun file(fileId: String): ByteArray {
        val epoch: Long
        val headers = mutableMapOf("Accept" to "image/*,application/pdf", "Origin" to origin)
        synchronized(this) {
            epoch = generation
            session()?.let { headers["Cookie"] = "__Host-jl_session=${it.cookie}" }
        }
        val response =
            transport.execute(
                WireRequest("GET", "$origin/api/v1/files/${id(fileId)}/content", headers, null)
            )
        currentCoroutineContext().ensureActive()
        synchronized(this) {
            if (epoch != generation)
                throw CancellationException("Previous account response discarded")
        }
        if (response.status !in 200..299) {
            if (response.status == 401) clear()
            val error = runCatching {
                JsonCodec.parseToJsonElement(response.body) as JsonObject
            }
                .getOrNull()
            throw ApiFailure(
                response.status,
                error?.text("code") ?: "FILE_FAILED",
                error?.text("title") ?: "文件未能加载",
            )
        }
        return response.bytes?.takeIf { it.isNotEmpty() && it.size <= 20 * 1024 * 1024 }
            ?: throw ApiFailure(502, "INVALID_FILE", "文件内容不完整")
    }

    suspend fun prepareCsrf() {
        val token = get("/auth/csrf").text("csrf_token")
        require(token.length in 16..256)
        synchronized(this) { csrf = token }
    }

    suspend fun write(request: Request): JsonObject = mutex.withLock {
        if (csrf == null) prepareCsrf()
        try {
            wire(request)
        } catch (e: ApiFailure) {
            if (e.status != 403 || e.code != "CSRF_REJECTED") throw e
            // A definite CSRF rejection has no business side effect. Retry once, same command key.
            prepareCsrf()
            wire(request)
        }
    }

    suspend fun login(account: String, password: String): JsonObject = mutex.withLock {
        clear()
        prepareCsrf()
        val result =
            wire(
                Request(
                    "POST",
                    "/auth/login",
                    json("login_name" to account.trim(), "password" to password),
                )
            )
        val user = result.obj("user")
        validateUser(user)
        csrf = result.text("csrf_token")
        user
    }

    suspend fun register(name: String, email: String, code: String, password: String): JsonObject =
        mutex.withLock {
            prepareCsrf()
            val result =
                wire(
                    Request(
                        "POST",
                        "/auth/register",
                        json(
                            "display_name" to name.trim(),
                            "email" to email.trim(),
                            "code" to code,
                            "password" to password,
                        ),
                    )
                )
            val user = result.obj("user")
            validateUser(user)
            csrf = result.text("csrf_token")
            user
        }

    suspend fun restore(): JsonObject {
        val user = get("/me")
        validateUser(user)
        prepareCsrf()
        return user
    }

    suspend fun logout() {
        try {
            write(Request("POST", "/auth/logout"))
        } catch (e: ApiFailure) {
            if (e.status != 401) throw e
        }
        clear()
    }

    companion object {
        fun roles(user: JsonObject) =
            user
                .array("roles")
                .mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
                .filter { it in setOf("learner", "counselor") }
                .toSet()

        fun validateUser(user: JsonObject) {
            id(user.text("id"))
            require(user.text("display_name").isNotBlank() && roles(user).isNotEmpty())
        }
    }
}

/** Reuse one command id for exactly the same payload while its result is unknown. */
class CommandLedger {
    private val keys = mutableMapOf<String, String>()

    private fun fingerprint(
        owner: String,
        method: String,
        path: String,
        body: JsonObject?,
        version: Int?,
    ) =
        listOf(owner, method, path, version.toString(), body.toString())
            .joinToString("\u0000")
            .let {
                MessageDigest.getInstance("SHA-256").digest(it.toByteArray()).joinToString("") { b
                    ->
                    "%02x".format(b)
                }
            }

    fun request(
        owner: String,
        method: String,
        path: String,
        body: JsonObject? = null,
        version: Int? = null,
    ): Request {
        val fingerprint = fingerprint(owner, method, path, body, version)
        val key =
            if (method == "POST") keys.getOrPut(fingerprint) { UUID.randomUUID().toString() }
            else null
        return Request(method, path, body, version, key)
    }

    fun confirmed(owner: String, request: Request) {
        keys.remove(fingerprint(owner, request.method, request.path, request.body, request.version))
    }

    fun clear() = keys.clear()
}

val statusNames =
    mapOf(
        "not_started" to "准备开始",
        "in_progress" to "正在进行",
        "paused" to "已暂停",
        "submitted" to "等待反馈",
        "changes_requested" to "有新的反馈",
        "completed" to "已完成",
        "cancelled" to "已取消",
        "pending_match" to "待制定方向",
        "sop_pending" to "待制定步骤",
        "training" to "训练中",
        "awaiting_feedback" to "等待反馈",
        "feedback_available" to "反馈已到达",
        "stage_complete" to "阶段完成",
        "closed" to "已关闭",
        "queued" to "等待回应",
        "accepted" to "辅导员已接收",
        "resolved" to "已解决",
        "draft" to "草稿",
        "published" to "已发布",
        "passed" to "通过",
        "active" to "进行中",
        "confirmed" to "已确认",
    )

fun label(status: String) = statusNames[status] ?: status

fun canEditTask(task: JsonObject) = task.text("status") in setOf("in_progress", "changes_requested")

fun allStepsDone(task: JsonObject): Boolean {
    val steps = task.obj("revision").rows("steps")
    val progress = task.rows("progress")
    return steps.isNotEmpty() &&
        steps.all { step ->
            progress.any {
                it.text("step_id") == step.text("id") && it.text("status") == "completed"
            }
        }
}

/** Multipart bytes are immutable while pending so a retry uses the same file and key. */
fun uploadRequest(
    caseId: String,
    taskId: String?,
    purpose: String,
    filename: String,
    mime: String,
    bytes: ByteArray,
    key: String,
): Request {
    require(bytes.isNotEmpty() && bytes.size <= 20 * 1024 * 1024)
    require(purpose in setOf("task_evidence", "sop_media", "profile_material", "support_message"))
    require(mime in setOf("image/jpeg", "image/png", "image/webp", "application/pdf"))
    require(
        filename.isNotBlank() &&
            filename.length <= 255 &&
            filename.none { it.code < 32 || it.code == 127 || it in "\"\\" }
    )
    val boundary = "JobLens-" + UUID.randomUUID().toString()
    val out = java.io.ByteArrayOutputStream()
    fun line(value: String) {
        out.write((value + "\r\n").toByteArray(Charsets.UTF_8))
    }
    fun field(name: String, value: String) {
        line("--$boundary")
        line("Content-Disposition: form-data; name=\"$name\"")
        line("")
        line(value)
    }
    field("case_id", id(caseId))
    taskId?.let { field("task_id", id(it)) }
    field("purpose", purpose)
    line("--$boundary")
    line("Content-Disposition: form-data; name=\"file\"; filename=\"$filename\"")
    line("Content-Type: $mime")
    line("")
    out.write(bytes)
    line("")
    line("--$boundary--")
    return Request(
        "POST",
        "/files",
        key = key,
        binaryBody = out.toByteArray(),
        contentType = "multipart/form-data; boundary=$boundary",
    )
}
