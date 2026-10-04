package xyz.qunxue.joblens

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import java.io.File
import kotlinx.serialization.json.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import xyz.qunxue.joblens.core.*

/** All data below is synthetic and exists only in the separate test APK. No production calls. */
@RunWith(AndroidJUnit4::class)
class NativeUiTest {
    @get:Rule val compose = createAndroidComposeRule<ComponentActivity>()
    private val owner = "00000000-0000-4000-8000-000000000001"
    private val caseId = "00000000-0000-4000-8000-000000000010"
    private val taskId = "00000000-0000-4000-8000-000000000020"
    private val revisionId = "00000000-0000-4000-8000-000000000030"
    private val stepId = "00000000-0000-4000-8000-000000000040"
    private val user =
        json("id" to owner, "display_name" to "测试学员", "roles" to strings(listOf("learner")))
    private val step =
        json(
            "id" to stepId,
            "position" to 1,
            "instruction" to "核对文件名与清单上的名称。",
            "media_ids" to JsonArray(emptyList()),
            "estimated_seconds" to 0,
            "evidence_required" to false,
        )
    private val revision =
        json(
            "id" to revisionId,
            "goal" to "把文件按照清单整理好。",
            "steps" to JsonArray(listOf(step)),
            "revision_no" to 1,
            "version" to 1,
            "state" to "published",
            "reminder" to
                json("prompt_level" to 2, "speech_enabled" to false, "vibration_enabled" to false),
        )
    private val task =
        json(
            "id" to taskId,
            "case_id" to caseId,
            "learner_id" to owner,
            "title" to "文件整理练习",
            "status" to "in_progress",
            "version" to 2,
            "revision" to revision,
            "current_step_id" to stepId,
            "progress" to
                JsonArray(
                    listOf(
                        json(
                            "step_id" to stepId,
                            "status" to "pending",
                            "attachment_ids" to JsonArray(emptyList()),
                        )
                    )
                ),
        )

    private fun page(vararg rows: JsonObject) =
        json("items" to JsonArray(rows.toList()), "has_more" to false, "next_cursor" to null)

    private fun mount(
        state: UiState,
        transport: Transport = Transport { error("Unexpected network in static UI test") },
    ): JobLensModel {
        val model =
            JobLensModel(compose.activity.application as Application, JobLensApi(transport), false)
        compose.setContent {
            JobLensTheme {
                Column {
                    Surface(color = Color(0xFFFFE8B8), modifier = Modifier.fillMaxWidth()) {
                        Text("界面测试 · 合成数据 · 非生产账号", Modifier.padding(8.dp))
                    }
                    Box(Modifier.weight(1f)) { JobLensContent(state, model) }
                }
            }
        }
        return model
    }

    private fun shot(name: String) {
        compose.waitForIdle()
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val dir = File(context.getExternalFilesDir(null), "qa").apply { mkdirs() }
        check(
            UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
                .takeScreenshot(File(dir, "$name.png"))
        )
    }

    @Test
    fun loginAndRegisterScreens() {
        mount(UiState(loading = false))
        compose.onNodeWithText("今天，从一步开始。").assertIsDisplayed()
        compose
            .onNode(hasText("账号") and hasSetTextAction())
            .performTextInput("contract@example.invalid")
        compose
            .onNode(hasText("密码") and hasSetTextAction())
            .performTextInput("temporary-test-password")
        compose
            .onNode(hasText("账号") and hasSetTextAction())
            .assertTextContains("contract@example.invalid")
        shot("01-login-synthetic")
    }

    @Test
    fun learnerHomeShowsServerCounts() {
        mount(
            UiState(
                user = user,
                route = Route(Page.HOME),
                loading = false,
                data =
                    mapOf(
                        "dashboard" to
                            json(
                                "pending_tasks" to 1,
                                "pending_feedback" to 0,
                                "pending_assistance" to 0,
                                "as_of" to "2026-10-04T08:00:00Z",
                            ),
                        "list" to page(task),
                        "cases" to page(),
                    ),
            )
        )
        compose.onNodeWithText("文件整理练习").assertExists()
        compose.onNodeWithText("已完成 0 / 1 步").assertExists()
        shot("02-learner-home-synthetic")
    }

    @Test
    fun nativeTrainingStepAndNoFakeComplete() {
        mount(
            UiState(
                user = user,
                route = Route(Page.TASK, taskId),
                loading = false,
                data = mapOf("task" to task, "submissions" to page()),
            )
        )
        compose.onNodeWithText("当前 · 第 1 步").assertExists()
        compose.onNodeWithText("完成这一步").performScrollTo().assertIsEnabled()
        shot("03-training-synthetic")
        compose.onNodeWithText("提交训练结果").assertDoesNotExist()
    }

    @Test
    fun counselorWorkspace() {
        val counselor =
            json("id" to owner, "display_name" to "测试辅导员", "roles" to strings(listOf("counselor")))
        val kase =
            json(
                "id" to caseId,
                "counselor_id" to owner,
                "learner_id" to "00000000-0000-4000-8000-000000000099",
                "display_status" to "awaiting_feedback",
            )
        mount(
            UiState(
                user = counselor,
                role = "counselor",
                route = Route(Page.HOME),
                loading = false,
                data =
                    mapOf(
                        "dashboard" to
                            json(
                                "pending_tasks" to 2,
                                "pending_feedback" to 1,
                                "pending_assistance" to 1,
                            ),
                        "list" to page(kase),
                    ),
            )
        )
        compose.onNodeWithText("我的个案").assertExists()
        compose.onNodeWithText("查看个案").assertExists()
        shot("04-counselor-home-synthetic")
    }

    @Test
    fun foreignTaskNeverOffersLearnerMutation() {
        val foreign =
            JsonObject(
                task + ("learner_id" to JsonPrimitive("00000000-0000-4000-8000-000000000099"))
            )
        mount(
            UiState(
                user = user,
                role = "learner",
                route = Route(Page.TASK, taskId),
                loading = false,
                data = mapOf("task" to foreign, "submissions" to page()),
            )
        )
        compose.onNodeWithText("完成这一步").assertDoesNotExist()
        compose.onNodeWithText("暂停训练").assertDoesNotExist()
        compose.onNodeWithText("请求辅导员帮助").assertDoesNotExist()
    }

    @Test
    fun registrationErrorNeverSaysSent() {
        mount(UiState(route = Route(Page.REGISTER), loading = false, error = "邮件服务暂不可用"))
        compose.onNodeWithText("邮件服务暂不可用").assertIsDisplayed()
        compose.onNodeWithText("验证码已发送，请查看邮箱。").assertDoesNotExist()
        shot("05-registration-error-synthetic")
    }

    @Test
    fun profileTypingSurvivesRecomposition() {
        val profile =
            json(
                "user_id" to owner,
                "display_name" to "测试学员",
                "communication_preference" to "先看文字说明",
                "sensory_preferences" to strings(listOf("安静环境")),
                "work_notes" to "",
                "version" to 1,
            )
        mount(
            UiState(
                user = user,
                route = Route(Page.PROFILE),
                loading = false,
                data = mapOf("profile" to profile),
            )
        )
        compose.onNode(hasText("怎么称呼你") and hasSetTextAction()).performTextReplacement("连续输入测试")
        compose.onNode(hasText("怎么称呼你") and hasSetTextAction()).assertTextContains("连续输入测试")
        compose.onNode(hasText("喜欢的沟通方式") and hasSetTextAction()).performTextInput("。分步骤")
        compose.onNode(hasText("怎么称呼你") and hasSetTextAction()).assertTextContains("连续输入测试")
        shot("06-profile-synthetic")
    }
}
