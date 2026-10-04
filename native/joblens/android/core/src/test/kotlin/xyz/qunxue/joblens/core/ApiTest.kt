package xyz.qunxue.joblens.core

import java.io.IOException
import kotlin.test.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest

class ApiTest {
    private val user =
        json(
            "id" to "00000000-0000-4000-8000-000000000001",
            "display_name" to "Contract test",
            "roles" to strings(listOf("learner")),
        )
    private val csrf = "c".repeat(32)
    private val cookie = "s".repeat(43)

    class Fake : Transport {
        val requests = mutableListOf<WireRequest>()
        val responses = ArrayDeque<WireResponse>()
        var failure: Exception? = null

        override suspend fun execute(request: WireRequest): WireResponse {
            requests += request
            failure?.let { throw it }
            return responses.removeFirst()
        }
    }

    private fun response(value: String, status: Int = 200, cookies: List<String> = emptyList()) =
        WireResponse(status, value, cookies)

    private fun grant(
        fake: Fake,
        cookieLine: String = "__Host-jl_session=$cookie; Path=/; Max-Age=43200; Secure; HttpOnly",
    ) {
        fake.responses +=
            response(json("csrf_token" to csrf).toString(), cookies = listOf(cookieLine))
    }

    @Test
    fun loginUsesRealCsrfCookieOriginAndServerRole() = runTest {
        val f = Fake()
        grant(f)
        f.responses += response(json("user" to user, "csrf_token" to "new".repeat(10)).toString())
        val api = JobLensApi(f)
        assertEquals(user, api.login(" account ", "password"))
        assertEquals("https://j.qunxue.xyz/api/v1/auth/login", f.requests[1].url)
        assertEquals(PRODUCTION_ORIGIN, f.requests[1].headers["Origin"])
        assertEquals(csrf, f.requests[1].headers["X-CSRF-Token"])
        assertEquals("__Host-jl_session=$cookie", f.requests[1].headers["Cookie"])
        assertEquals(
            "account",
            JsonCodec.parseToJsonElement(f.requests[1].body!!)
                .let { it as kotlinx.serialization.json.JsonObject }
                .text("login_name"),
        )
        assertEquals(setOf("learner"), JobLensApi.roles(user))
    }

    @Test
    fun rolesCannotBeSelfGranted() {
        assertEquals(
            emptySet(),
            JobLensApi.roles(json("roles" to strings(listOf("administrator", "root")))),
        )
        assertFails {
            JobLensApi.validateUser(
                json(
                    "id" to user.text("id"),
                    "display_name" to "Test",
                    "roles" to strings(listOf("administrator")),
                )
            )
        }
    }

    @Test
    fun insecureOriginRejected() {
        listOf(
                "http://j.qunxue.xyz",
                "https://user@j.qunxue.xyz",
                "https://j.qunxue.xyz/path",
                "https://j.qunxue.xyz?q=x",
                "https://j.qunxue.xyz#x",
            )
            .forEach { assertFails { JobLensApi(Fake(), origin = it) } }
    }

    @Test
    fun outOfOriginStoredCookieNotUsed() = runTest {
        val f = Fake()
        f.responses += response(user.toString())
        val store = MemorySessionStore()
        store.write(StoredSession(cookie, Long.MAX_VALUE, "https://other.invalid"))
        JobLensApi(f, store).get("/me")
        assertNull(f.requests.single().headers["Cookie"])
    }

    @Test
    fun expiredStoredCookieNotUsed() = runTest {
        val f = Fake()
        f.responses += response(user.toString())
        val store = MemorySessionStore()
        store.write(StoredSession(cookie, 9, PRODUCTION_ORIGIN))
        JobLensApi(f, store, now = { 10 }).get("/me")
        assertNull(f.requests.single().headers["Cookie"])
    }

    @Test
    fun malformedCookieAttributesRejected() = runTest {
        for (line in
            listOf(
                "__Host-jl_session=$cookie; Path=/; Max-Age=100",
                "__Host-jl_session=$cookie; Path=/x; Max-Age=100; Secure",
                "__Host-jl_session=$cookie; Path=/; Domain=j.qunxue.xyz; Max-Age=100; Secure",
                "evil=$cookie; Path=/; Max-Age=100; Secure",
            )) {
            val f = Fake()
            grant(f, line)
            f.responses += response(user.toString())
            val api = JobLensApi(f)
            api.prepareCsrf()
            api.get("/me")
            assertNull(f.requests[1].headers["Cookie"])
        }
    }

    @Test
    fun deletionCookieClearsSession() = runTest {
        val f = Fake()
        grant(f)
        f.responses +=
            response(
                user.toString(),
                cookies = listOf("__Host-jl_session=; Path=/; Max-Age=0; Secure"),
            )
        f.responses += response(user.toString())
        val api = JobLensApi(f)
        api.prepareCsrf()
        api.get("/me")
        api.get("/me")
        assertNull(f.requests.last().headers["Cookie"])
    }

    @Test
    fun writeCarriesVersionAndIdempotency() = runTest {
        val f = Fake()
        grant(f)
        f.responses += response(json("version" to 3).toString())
        val api = JobLensApi(f)
        val key = "key-key-key-key-123"
        api.write(Request("POST", "/tasks/id/actions", json("action" to "pause"), 2, key))
        assertEquals("\"2\"", f.requests.last().headers["If-Match"])
        assertEquals(key, f.requests.last().headers["Idempotency-Key"])
    }

    @Test
    fun unresolvedRetryReusesKey() {
        val l = CommandLedger()
        val body = json("note" to "same")
        val one = l.request("a", "POST", "/tasks/1/submissions", body, 1)
        val two = l.request("a", "POST", "/tasks/1/submissions", body, 1)
        assertEquals(one.key, two.key)
        assertNotEquals(one.key, l.request("b", "POST", "/tasks/1/submissions", body, 1).key)
        assertNotEquals(
            one.key,
            l.request("a", "POST", "/tasks/1/submissions", json("note" to "different"), 1).key,
        )
        l.confirmed("a", one)
        assertNotEquals(one.key, l.request("a", "POST", "/tasks/1/submissions", body, 1).key)
    }

    @Test
    fun ledgerClearSeparatesAccounts() {
        val l = CommandLedger()
        val a = l.request("user", "POST", "/op")
        l.clear()
        assertNotEquals(a.key, l.request("user", "POST", "/op").key)
    }

    @Test
    fun putDoesNotInventIdempotency() {
        assertNull(
            CommandLedger().request("a", "PUT", "/me/profile", json("display_name" to "x"), 1).key
        )
    }

    @Test
    fun unknownWriteIsNotSuccess() = runTest {
        val f = Fake()
        grant(f)
        val api = JobLensApi(f)
        api.prepareCsrf()
        f.failure = IOException("lost")
        assertFailsWith<UnknownWrite> {
            api.write(
                Request(
                    "POST",
                    "/tasks/id/actions",
                    json("action" to "start"),
                    1,
                    "test-key-test-key",
                )
            )
        }
    }

    @Test
    fun getFailureRemainsReadFailure() = runTest {
        val f = Fake()
        f.failure = IOException("lost")
        assertFailsWith<IOException> { JobLensApi(f).get("/me") }
    }

    @Test
    fun registrationFailureKeepsServerTitle() = runTest {
        val f = Fake()
        grant(f)
        f.responses +=
            response(json("title" to "邮件服务暂不可用", "code" to "EMAIL_UNAVAILABLE").toString(), 503)
        val failure =
            assertFailsWith<ApiFailure> {
                JobLensApi(f)
                    .write(
                        Request(
                            "POST",
                            "/auth/registration-code",
                            json("email" to "example@example.invalid"),
                        )
                    )
            }
        assertEquals("邮件服务暂不可用", failure.message)
        assertEquals(503, failure.status)
    }

    @Test
    fun sessionExpiredClearsCookie() = runTest {
        val f = Fake()
        grant(f)
        f.responses += response(json("title" to "请登录", "code" to "UNAUTHENTICATED").toString(), 401)
        val store = MemorySessionStore()
        val api = JobLensApi(f, store)
        api.prepareCsrf()
        assertFailsWith<ApiFailure> { api.get("/me") }
        assertNull(store.read())
    }

    @Test
    fun versionConflictDoesNotRetryAutomatically() = runTest {
        val f = Fake()
        grant(f)
        f.responses +=
            response(json("title" to "内容已有更新", "code" to "VERSION_CONFLICT").toString(), 412)
        assertFailsWith<ApiFailure> {
            JobLensApi(f).write(Request("PUT", "/me/profile", json("display_name" to "x"), 1))
        }
        assertEquals(2, f.requests.size)
    }

    @Test
    fun redirectIsNotAcceptedAsSuccess() = runTest {
        val f = Fake()
        f.responses += response("", 302)
        assertFailsWith<ApiFailure> { JobLensApi(f).get("/me") }
    }

    @Test
    fun arbitraryPathsRejected() = runTest {
        val api = JobLensApi(Fake())
        listOf("//evil.invalid", "/../me", "/x#fragment", "/x\\evil", "/%2e%2e/secret").forEach {
            assertFails { api.get(it) }
        }
    }

    @Test
    fun readHeadersContainNoWriteCsrf() = runTest {
        val f = Fake()
        grant(f)
        f.responses += response(user.toString())
        val api = JobLensApi(f)
        api.prepareCsrf()
        api.get("/me")
        assertNull(f.requests.last().headers["X-CSRF-Token"])
    }

    @Test
    fun clearDiscardsInflightOldAccountResponse() = runTest {
        val started = CompletableDeferred<Unit>()
        val finish = CompletableDeferred<Unit>()
        val api =
            JobLensApi(
                Transport {
                    started.complete(Unit)
                    finish.await()
                    response(
                        user.toString(),
                        cookies = listOf("__Host-jl_session=$cookie; Path=/; Max-Age=100; Secure"),
                    )
                }
            )
        val read = async { api.get("/me") }
        started.await()
        api.clear()
        finish.complete(Unit)
        assertFailsWith<CancellationException> { read.await() }
    }

    @Test
    fun incompleteJsonDoesNotSucceed() = runTest {
        val f = Fake()
        f.responses += response("<html>server error</html>")
        assertFailsWith<ApiFailure> { JobLensApi(f).get("/me") }
    }

    @Test
    fun stepCompletionRequiresEveryActualStep() {
        val a = "00000000-0000-4000-8000-000000000002"
        val b = "00000000-0000-4000-8000-000000000003"
        fun task(
            progress: kotlinx.serialization.json.JsonArray
        ): kotlinx.serialization.json.JsonObject {
            return json(
                "revision" to
                    json(
                        "steps" to
                            kotlinx.serialization.json.JsonArray(
                                listOf(json("id" to a), json("id" to b))
                            )
                    ),
                "progress" to progress,
            )
        }
        assertFalse(
            allStepsDone(
                task(
                    kotlinx.serialization.json.JsonArray(
                        listOf(json("step_id" to a, "status" to "completed"))
                    )
                )
            )
        )
        assertTrue(
            allStepsDone(
                task(
                    kotlinx.serialization.json.JsonArray(
                        listOf(
                            json("step_id" to a, "status" to "completed"),
                            json("step_id" to b, "status" to "completed"),
                        )
                    )
                )
            )
        )
    }

    @Test
    fun emptySuccessIsNotConfirmation() = runTest {
        for (status in listOf(200, 201)) {
            val f = Fake()
            grant(f)
            f.responses += response("", status)
            assertFailsWith<UnknownWrite> {
                JobLensApi(f)
                    .write(Request("POST", "/op", json("value" to 1), key = "test-key-test-key"))
            }
        }
    }

    @Test
    fun emptyReadIsInvalidButNoContentIsValid() = runTest {
        val f = Fake()
        f.responses += response("", 200)
        assertFailsWith<ApiFailure> { JobLensApi(f).get("/me") }
        val g = Fake()
        grant(g)
        g.responses += response("", 204)
        assertTrue(JobLensApi(g).write(Request("POST", "/auth/logout")).isEmpty())
    }

    @Test
    fun multipartPreservesKeyAndBinaryAndRejectsInjection() {
        val caseId = "00000000-0000-4000-8000-000000000004"
        val upload =
            uploadRequest(
                caseId,
                caseId,
                "task_evidence",
                "test.png",
                "image/png",
                byteArrayOf(1, 2, 3),
                "file-key-file-key",
            )
        assertEquals("file-key-file-key", upload.key)
        assertTrue(upload.contentType!!.startsWith("multipart/form-data; boundary="))
        assertTrue(String(upload.binaryBody!!).contains("name=\"case_id\""))
        assertFails {
            uploadRequest(
                caseId,
                null,
                "profile_material",
                "bad\r\nname",
                "image/png",
                byteArrayOf(1),
                "file-key-file-key",
            )
        }
        assertFails {
            uploadRequest(
                caseId,
                null,
                "profile_material",
                "test.exe",
                "application/octet-stream",
                byteArrayOf(1),
                "file-key-file-key",
            )
        }
    }

    @Test
    fun missingDashboardCountsDoNotBecomeFakeZeros() = runTest {
        val f = Fake()
        f.responses +=
            response(json("items" to kotlinx.serialization.json.JsonArray(emptyList())).toString())
        assertFailsWith<ApiFailure> { JobLensApi(f).get("/dashboard?view=learner") }
    }

    @Test
    fun csrfRejectionRefreshesOnceWithoutChangingCommand() = runTest {
        val f = Fake()
        grant(f)
        f.responses +=
            response(json("code" to "CSRF_REJECTED", "title" to "请求校验失败").toString(), 403)
        grant(f)
        f.responses += response(json("version" to 2).toString())
        JobLensApi(f)
            .write(
                Request("POST", "/commands", json("action" to "start"), 1, "repeat-key-repeat-key")
            )
        val writes = f.requests.filter { it.method == "POST" }
        assertEquals(2, writes.size)
        assertEquals(writes[0].body, writes[1].body)
        assertEquals(writes[0].headers["Idempotency-Key"], writes[1].headers["Idempotency-Key"])
    }
}
