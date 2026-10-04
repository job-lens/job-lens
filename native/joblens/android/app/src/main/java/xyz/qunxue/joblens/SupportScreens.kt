package xyz.qunxue.joblens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

@Composable
fun SupportScreen(s: UiState, m: JobLensModel) {
    Heading("求助与回应", if (s.role == "counselor") "回应具体问题，让下一步更清楚。" else "卡住时，可以直接请辅导员看一眼。")
    s.data["list"]?.let { page ->
        if (page.rows().isEmpty()) Empty("暂时没有求助", "在任务里点击“请求辅导员帮助”，即可说明需要。")
        page.rows().forEach { a ->
            QCard {
                Pill(label(a.text("state")))
                Text(a.text("message"), style = MaterialTheme.typography.titleMedium)
                Meta(dateLabel(a.text("created_at")))
                Action("查看对话", secondary = true) {
                    m.navigate(Route(Page.ASSISTANCE, a.text("id")))
                }
            }
        }
        More(page, s) { m.more("list", "/assistance-requests?limit=20") }
    }
}

@Composable
fun NewSupportScreen(s: UiState, m: JobLensModel) {
    Heading("请求辅导员帮助", "说清楚你卡在哪里，一次说一件事。")
    var message by rememberSaveable(s.route) { mutableStateOf("") }
    var attachments by
        rememberSaveable(s.route.id, s.route.parent) { mutableStateOf(emptyList<String>()) }
    Field("需要什么帮助", message, { message = it }, !s.busy, multiline = true, max = 500)
    var waitingForFiles by remember { mutableStateOf(false) }
    AssetPicker(
        s,
        m,
        s.route.id,
        s.route.parent.takeIf(String::isNotEmpty),
        "support_message",
        attachments,
        pendingChanged = { waitingForFiles = it },
    ) {
        attachments = it
    }
    Action("发送求助", !s.busy && !waitingForFiles && message.isNotBlank()) {
        m.write(
            "POST",
            "/assistance-requests",
            json(
                "case_id" to s.route.id,
                "task_id" to s.route.parent.takeIf(String::isNotEmpty),
                "step_id" to s.route.step.takeIf(String::isNotEmpty),
                "message" to message.trim(),
                "attachment_ids" to strings(attachments),
                "preferred_mode" to "text",
            ),
            success = { created ->
                message = ""
                attachments = emptyList()
                m.navigate(Route(Page.ASSISTANCE, created.text("id")))
            },
        )
    }
}

@Composable
fun AssistanceScreen(s: UiState, m: JobLensModel) {
    val a = s.data["assistance"] ?: return
    val rid = a.text("id")
    val state = a.text("state")
    val scope = s.data["case"]
    val canCounsel = s.role == "counselor" && scope?.text("counselor_id") == s.user?.text("id")
    val canLearn = s.role == "learner" && scope?.text("learner_id") == s.user?.text("id")
    Heading("求助对话")
    Pill(label(state))
    QCard {
        Text(a.text("message"), style = MaterialTheme.typography.titleLarge)
        Meta(dateLabel(a.text("created_at")))
        AttachmentLinks(a.array("attachment_ids"), m)
    }
    if (canCounsel && state == "queued")
        Action("接收这条求助", !s.busy) {
            m.write(
                "POST",
                "/assistance-requests/$rid/actions",
                json("action" to "accept"),
                a.number("version"),
            )
        }
    s.data["messages"]?.let { page ->
        page.rows().forEach { message ->
            QCard {
                Meta(
                    if (message.text("author_id") == s.user?.text("id")) "我"
                    else if (s.role == "counselor") "学员" else "辅导员"
                )
                Text(message.text("body"))
                Meta(dateLabel(message.text("created_at")))
                AttachmentLinks(message.array("attachment_ids"), m)
            }
        }
        More(page, s) { m.more("messages", "/assistance-requests/$rid/messages?limit=20") }
    }
    s.sections["messages"]?.let { Notice(it, true) }
    if (state in setOf("queued", "accepted") && (canCounsel || canLearn)) {
        var message by rememberSaveable(rid) { mutableStateOf("") }
        var attachments by rememberSaveable(rid) { mutableStateOf(emptyList<String>()) }
        var attachmentBatch by rememberSaveable(rid) { mutableIntStateOf(0) }
        Field("写下回复", message, { message = it }, !s.busy, multiline = true, max = 2000)
        var waitingForFiles by remember { mutableStateOf(false) }
        key(attachmentBatch) {
            AssetPicker(
                s,
                m,
                a.text("case_id"),
                a.text("task_id").takeIf(String::isNotEmpty),
                "support_message",
                attachments,
                pendingChanged = { waitingForFiles = it },
            ) {
                attachments = it
            }
        }
        Action(
            "发送回复",
            !s.busy && !waitingForFiles && (message.isNotBlank() || attachments.isNotEmpty()),
        ) {
            m.write(
                "POST",
                "/assistance-requests/$rid/messages",
                json("body" to message.trim(), "attachment_ids" to strings(attachments)),
            ) {
                message = ""
                attachments = emptyList()
                attachmentBatch++
                m.load()
            }
        }
        var confirm by remember { mutableStateOf(false) }
        val action = if (canCounsel) "resolve" else "cancel"
        Action(
            if (action == "resolve") "标记已解决" else "取消这条求助",
            !s.busy && !(canCounsel && state == "queued"),
            secondary = true,
        ) {
            confirm = true
        }
        ConfirmDialog(
            confirm,
            if (action == "resolve") "问题已经解决？" else "取消这条求助？",
            "确认后将结束当前求助。",
            { confirm = false },
        ) {
            confirm = false
            m.write(
                "POST",
                "/assistance-requests/$rid/actions",
                json("action" to action),
                a.number("version"),
            )
        }
    }
}

private val notifications =
    mapOf(
        "training.created" to "新的训练任务",
        "training.submitted" to "训练结果已提交",
        "training.feedback" to "收到训练反馈",
        "support.requested" to "收到新的求助",
        "support.accept" to "求助已接收",
        "support.resolve" to "求助已解决",
        "support.message" to "收到新消息",
        "file_ready" to "附件已通过安全检查",
        "file_rejected" to "附件未通过安全检查",
    )

@Composable
fun NotificationsScreen(s: UiState, m: JobLensModel) {
    Heading("通知", "训练和支持的最新进展。")
    s.data["list"]?.let { page ->
        if (page.rows().isEmpty()) Empty("暂时没有通知", "有新的任务或反馈时，会在这里提醒你。")
        page.rows().forEach { n ->
            QCard {
                if (n.text("read_at").isEmpty()) Pill("未读")
                Text(
                    notifications[n.text("type")] ?: "${resourceName(n.text("resource_type"))}有新进展",
                    style = MaterialTheme.typography.titleMedium,
                )
                Meta(dateLabel(n.text("created_at")))
                val target =
                    when (n.text("resource_type")) {
                        "task" -> Page.TASK
                        "case" -> Page.CASE
                        "assistance" -> Page.ASSISTANCE
                        "submission" -> Page.SUBMISSION
                        else -> null
                    }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (target != null)
                        Action("查看", secondary = true) {
                            m.navigate(Route(target, n.text("resource_id")))
                        }
                    if (n.text("read_at").isEmpty())
                        TextButton(
                            onClick = { m.write("POST", "/notifications/${n.text("id")}/read") },
                            enabled = !s.busy,
                        ) {
                            Text("标记已读")
                        }
                }
            }
        }
        More(page, s) { m.more("list", "/notifications?limit=50", true) }
    }
}

private fun resourceName(value: String) =
    mapOf(
        "task" to "任务",
        "case" to "个案",
        "assistance" to "求助",
        "submission" to "提交",
        "annotation" to "标注",
        "file" to "文件",
    )[value] ?: "工作台"
