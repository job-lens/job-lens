package xyz.qunxue.joblens

import android.app.Application
import android.os.SystemClock
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import java.io.File
import java.nio.ByteBuffer
import kotlinx.serialization.json.*
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
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
        compose.activity
            .getSharedPreferences("companion-motion", 0)
            .edit()
            .putBoolean("enabled", true)
            .commit()
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
        compose.onNodeWithContentDescription("陪你做事的小伙伴").assertIsDisplayed()
        shot("01-login-synthetic")
        compose.onNode(hasText("登录") and hasClickAction()).performClick()
        compose.onNodeWithText("请填写账号。").assertExists()
        compose.onNodeWithContentDescription("账号").performTextInput("contract@example.invalid")
        compose.onNodeWithContentDescription("密码").performTextInput("temporary-test-password")
        compose.onNodeWithContentDescription("账号").assertTextContains("contract@example.invalid")
        compose
            .onNodeWithContentDescription("陪你做事的小伙伴")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, "小融闭眼"))
        UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).pressBack()
        shot("07-password-private-eyes-synthetic")
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
        compose.onNodeWithText("0 / 1 步").assertExists()
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
        compose.onNodeWithText("第 1 步").assertExists()
        compose.onNodeWithContentDescription("文件与清单的操作示意").assertExists()
        shot("03-training-synthetic")
        compose.onNodeWithText("完成这一步").performScrollTo().assertIsEnabled()
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
        compose.onNodeWithText("继续跟进").assertExists()
        compose.onNodeWithText("查看").assertExists()
        compose.onNodeWithText("待审核提交").assertExists()
        shot("04-counselor-home-synthetic")
        compose.onNodeWithText("支持流程").performScrollTo().assertIsDisplayed()
        shot("04b-counselor-workflow-synthetic")
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
        compose.onNodeWithText("邮件服务暂不可用").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("验证码已发送，请查看邮箱。").assertDoesNotExist()
        shot("05-registration-error-synthetic")
    }

    @Test
    fun emptyLearnerHomeContainsOriginalBuddy() {
        mount(
            UiState(
                user = user,
                route = Route(Page.HOME),
                loading = false,
                data =
                    mapOf(
                        "dashboard" to
                            json(
                                "pending_tasks" to 0,
                                "pending_feedback" to 0,
                                "pending_assistance" to 0,
                            ),
                        "list" to page(),
                        "cases" to page(),
                    ),
            )
        )
        compose.onNodeWithContentDescription("陪你做事的小伙伴").assertExists()
        compose.onNodeWithText("暂时没有待完成的任务").assertExists()
        shot("08-empty-learner-buddy-synthetic")
    }

    @Test
    fun waitingTrainingContainsCompanionAndRealStartControl() {
        val waiting = JsonObject(task + ("status" to JsonPrimitive("not_started")))
        mount(
            UiState(
                user = user,
                route = Route(Page.TASK, taskId),
                loading = false,
                data = mapOf("task" to waiting, "submissions" to page()),
            )
        )
        compose.onNodeWithContentDescription("陪你做事的小伙伴").assertExists()
        compose.onNodeWithText("开始训练").assertIsEnabled()
        shot("09-training-ready-synthetic")
    }

    @Test
    fun pausedTrainingContainsCompanionAndResumeControl() {
        val paused = JsonObject(task + ("status" to JsonPrimitive("paused")))
        mount(
            UiState(
                user = user,
                route = Route(Page.TASK, taskId),
                loading = false,
                data = mapOf("task" to paused, "submissions" to page()),
            )
        )
        compose.onNodeWithContentDescription("陪你做事的小伙伴").assertExists()
        compose.onNodeWithText("继续训练").assertIsEnabled()
        shot("10-training-paused-synthetic")
    }

    @Test
    fun companionMotionPausesAndPersists() {
        // InfiniteAnimationPolicy cancels infinite transitions while autoAdvance is true.
        // This must precede setContent/mount, not merely the first pixel capture.
        compose.mainClock.autoAdvance = false
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val dir = File(context.getExternalFilesDir(null), "qa").apply { mkdirs() }
        val diagnostics = File(dir, "motion-diagnostics.txt")
        val animatorScale =
            Settings.Global.getFloat(
                context.contentResolver,
                Settings.Global.ANIMATOR_DURATION_SCALE,
                1f,
            )
        diagnostics.writeText(
            "animator_duration_scale=$animatorScale\nautoAdvanceBeforeMount=${compose.mainClock.autoAdvance}\nlifecycleBeforeMount=${compose.activity.lifecycle.currentState}\n"
        )
        try {
            assertTrue(
                "Motion fixture requires animator_duration_scale > 0; zero correctly disables product motion",
                animatorScale > 0f,
            )
            compose.runOnUiThread {
                assertTrue(
                    "Activity must be resumed for companion motion",
                    compose.activity.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED),
                )
            }
            mount(UiState(loading = false))
            fun pixels(frame: String): Int {
                // Await Android drawing as well as the manually advanced Compose frame.
                compose.waitForIdle()
                val bmp =
                    compose
                        .onNodeWithContentDescription("陪你做事的小伙伴")
                        .captureToImage()
                        .asAndroidBitmap()
                val buffer = ByteBuffer.allocate(bmp.byteCount)
                bmp.copyPixelsToBuffer(buffer)
                val hash = buffer.array().contentHashCode()
                diagnostics.appendText(
                    "$frame clock=${compose.mainClock.currentTime} uptime=${SystemClock.uptimeMillis()} hash=$hash lifecycle=${compose.activity.lifecycle.currentState}\n"
                )
                shot(frame) // Preserve labeled, full-screen evidence before any assertion can fail.
                return hash
            }
            compose.mainClock.advanceTimeBy(32)
            compose.onNodeWithContentDescription("暂停伙伴动效").assertIsEnabled()
            val movingA = pixels("motion-01-moving-a")
            compose.mainClock.advanceTimeBy(1600)
            val movingB = pixels("motion-02-moving-b")
            assertTrue("Original Buddy layers should move", movingA != movingB)
            compose.onNodeWithContentDescription("暂停伙伴动效").performClick()
            compose.mainClock.advanceTimeBy(32)
            compose.onNodeWithContentDescription("开启伙伴动效").assertExists()
            pixels("motion-03-pause-click")
            // captureToImage includes the IconButton drawn over the Canvas. Its native
            // RippleDrawable runs on Android's clock, independently of mainClock. Preserve
            // the immediate click frame, then settle that finite indication on both clocks
            // before comparing the complete, unmasked Canvas pixels. Keep autoAdvance false
            // so a mistakenly running Buddy cannot be cancelled by InfiniteAnimationPolicy.
            val rippleSettleMillis = (1000 * animatorScale).toLong().coerceAtLeast(1000)
            val rippleDeadline = SystemClock.uptimeMillis() + rippleSettleMillis
            compose.mainClock.advanceTimeBy(rippleSettleMillis)
            compose.waitUntil(timeoutMillis = rippleSettleMillis + 2000) {
                SystemClock.uptimeMillis() >= rippleDeadline
            }
            val pausedA = pixels("motion-03-paused-a")
            compose.mainClock.advanceTimeBy(1800)
            val pausedB = pixels("motion-04-paused-b")
            assertEquals("Paused Buddy must remain still", pausedA, pausedB)
            compose.onNodeWithContentDescription("开启伙伴动效").assertExists()
            assertTrue(
                !compose.activity
                    .getSharedPreferences("companion-motion", 0)
                    .getBoolean("enabled", true)
            )
            shot("11-companion-paused-synthetic")
        } finally {
            compose.mainClock.autoAdvance = true
        }
    }

    @Test
    fun drawerClosesWithoutChangingPageOrLeavingOverlay() {
        mount(
            UiState(
                user = user,
                route = Route(Page.HOME),
                loading = false,
                data =
                    mapOf(
                        "dashboard" to
                            json(
                                "pending_tasks" to 0,
                                "pending_feedback" to 0,
                                "pending_assistance" to 0,
                            ),
                        "list" to page(),
                        "cases" to page(),
                    ),
            )
        )
        compose.onNodeWithContentDescription("打开菜单").performClick()
        compose.onNodeWithContentDescription("关闭菜单").assertIsDisplayed()
        shot("12-native-drawer-synthetic")
        compose.onNodeWithContentDescription("关闭菜单").performClick()
        compose.onNodeWithText("今天，从一步开始。").assertIsDisplayed()
        compose.onNodeWithContentDescription("打开菜单").assertIsDisplayed()
        // Hold the animation clock to deliver Back before the drawer can settle at Open.
        compose.mainClock.autoAdvance = false
        try {
            compose.onNodeWithContentDescription("打开菜单").performClick()
            UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).pressBack()
            compose.mainClock.advanceTimeBy(800)
        } finally {
            compose.mainClock.autoAdvance = true
        }
        compose.runOnUiThread {
            assertTrue(
                "Immediate drawer Back must not finish the Activity",
                !compose.activity.isFinishing && !compose.activity.isDestroyed,
            )
        }
        compose.onNodeWithText("今天，从一步开始。").assertIsDisplayed()
        compose.onNodeWithContentDescription("打开菜单").assertIsDisplayed()
        shot("12b-drawer-back-retains-workspace-synthetic")
    }

    @Test
    fun completedTrainingKeepsOriginalCompanion() {
        val completed = JsonObject(task + ("status" to JsonPrimitive("completed")))
        mount(
            UiState(
                user = user,
                route = Route(Page.TASK, taskId),
                loading = false,
                data = mapOf("task" to completed, "submissions" to page()),
            )
        )
        compose.onNodeWithContentDescription("陪你做事的小伙伴").assertExists()
        compose.onNodeWithText("这次训练完成了。").assertExists()
        compose.onNodeWithText("开始训练").assertDoesNotExist()
        shot("13-training-completed-synthetic")
    }

    @Test
    fun systemReducedMotionDisablesCompanionControl() {
        compose.setContent {
            JobLensTheme {
                CompositionLocalProvider(
                    LocalCompanionMotion provides CompanionMotion(true).apply { reduced = true }
                ) {
                    Column {
                        Text("界面测试 · 合成数据 · 非生产账号")
                        Companion()
                    }
                }
            }
        }
        compose.onNodeWithContentDescription("已按系统设置关闭动效").assertIsNotEnabled()
        compose.onNodeWithContentDescription("陪你做事的小伙伴").assertExists()
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
