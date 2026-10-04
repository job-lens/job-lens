package xyz.qunxue.joblens.core

import kotlin.test.*
import kotlinx.coroutines.test.runTest

class ApiValidationReviewTest {
    @Test
    fun emptyReadResponseFails() = runTest {
        assertFailsWith<ApiFailure> { JobLensApi(Transport { WireResponse(200, "") }).get("/me") }
    }

    @Test
    fun emptySuccessfulWriteKeepsOutcomeUnknown() = runTest {
        val replies =
            ArrayDeque(
                listOf(
                    WireResponse(200, json("csrf_token" to "c".repeat(32)).toString()),
                    WireResponse(201, ""),
                )
            )
        val api = JobLensApi(Transport { replies.removeFirst() })
        assertFailsWith<UnknownWrite> {
            api.write(Request("POST", "/files", key = "review-test-command-key"))
        }
    }

    @Test
    fun validNoContentWriteSucceeds() = runTest {
        val replies =
            ArrayDeque(
                listOf(
                    WireResponse(200, json("csrf_token" to "c".repeat(32)).toString()),
                    WireResponse(204, ""),
                )
            )
        val api = JobLensApi(Transport { replies.removeFirst() })
        assertEquals(
            0,
            api.write(
                    Request(
                        "POST",
                        "/notifications/00000000-0000-4000-8000-000000000001/read",
                        key = "review-test-command-key",
                    )
                )
                .size,
        )
    }
}
