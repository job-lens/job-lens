package xyz.qunxue.joblens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.*
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

@Composable
fun HomeScreen(s: UiState, m: JobLensModel) {
    val counselor = s.role == "counselor"
    Heading(
        if (counselor) "把支持，放在每一步。" else "今天，从一步开始。",
        if (counselor) "查看当前个案，回应学员需要。" else "按自己的节奏完成。有需要时，随时停一停。",
    )
    s.data["dashboard"]?.let { d ->
        QCard {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                listOf(
                        "pending_tasks" to "待完成",
                        "pending_feedback" to "等待反馈",
                        "pending_assistance" to "正在求助",
                    )
                    .forEach { (key, title) ->
                        Column {
                            Text(
                                d.number(key).toString(),
                                style = MaterialTheme.typography.headlineMedium,
                            )
                            Meta(title)
                        }
                    }
            }
            if(d.text("as_of").isNotEmpty())Meta("更新于 ${dateLabel(d.text("as_of"))}")
        }
    }
    Text(if (counselor) "我的个案" else "我的任务", style = MaterialTheme.typography.titleLarge)
    s.data["list"]?.let { page ->
        val rows =
            page.rows().let {
                if (counselor) it.filter { k -> k.text("counselor_id") == s.user?.text("id") }
                else
                    it.filter { t ->
                        t.text("learner_id") == s.user?.text("id") &&
                            t.text("status") !in setOf("completed", "cancelled")
                    }
            }
        if (rows.isEmpty())
            Empty(
                if (counselor) "暂时没有已分配个案" else "暂时没有待完成的任务",
                if (counselor) "管理员分配个案后，会显示在这里。" else "辅导员准备好下一次训练后，它会出现在这里。也可以先完善个人资料。",
            )
        rows.forEach { if (counselor) CaseCard(it, m) else TaskCard(it, m) }
        More(page, s) { m.more("list", if (counselor) "/cases?limit=20" else "/tasks?limit=20") }
    }
    if (!counselor) {
        Action("完善个人资料", secondary = true) { m.navigate(Route(Page.PROFILE)) }
        s.data["cases"]
            ?.rows()
            ?.filter { it.text("learner_id") == s.user?.text("id") }
            ?.forEach { k ->
                Action("联系辅导员", secondary = true) {
                    m.navigate(Route(Page.NEW_SUPPORT, k.text("id")))
                }
            }
    }
}

@Composable
private fun TaskCard(task: JsonObject, m: JobLensModel) {
    QCard {
        Pill(label(task.text("status")))
        Text(task.text("title"), style = MaterialTheme.typography.titleLarge)
        Text(task.obj("revision").text("goal"))
        val total = task.obj("revision").rows("steps").size
        val done = task.rows("progress").count { it.text("status") == "completed" }
        LinearProgressIndicator(
            progress = { if (total > 0) done.toFloat() / total else 0f },
            modifier = Modifier.fillMaxWidth(),
        )
        Meta(
            "已完成 $done / $total 步" +
                (task.text("due_on").takeIf(String::isNotEmpty)?.let { " · $it 前完成" } ?: "")
        )
        Action(if (task.text("status") == "not_started") "查看任务" else "继续查看") {
            m.navigate(Route(Page.TASK, task.text("id")))
        }
    }
}

@Composable
private fun CaseCard(k: JsonObject, m: JobLensModel) {
    QCard {
        Pill(label(k.text("display_status")))
        Text("学员个案", style = MaterialTheme.typography.titleLarge)
        Meta("编号 ${k.text("id").take(8)}")
        Action("查看个案", secondary = true) { m.navigate(Route(Page.CASE, k.text("id"))) }
    }
}

@Composable
fun CasesScreen(s: UiState, m: JobLensModel) {
    Heading("我的个案", "只显示当前账号获授权的个案。")
    s.data["list"]?.let { page ->
        if (page.rows().isEmpty()) Empty("还没有个案", "管理员分配后即可开始支持。")
        page
            .rows()
            .filter { it.text("counselor_id") == s.user?.text("id") }
            .forEach { CaseCard(it, m) }
        More(page, s) { m.more("list", "/cases?limit=20") }
    }
}

@Composable
fun RecordsScreen(s: UiState, m: JobLensModel) {
    Heading("训练记录", "记录完成的过程，方便回看和沟通。")
    s.data["cases"]?.let { cases ->
        if (cases.rows().isEmpty()) Empty("还没有训练记录", "开始第一次训练后，记录会出现在这里。")
        cases
            .rows()
            .filter { it.text("learner_id") == s.user?.text("id") }
            .forEach { k ->
                val key = "records:${k.text("id")}"
                s.data[key]?.let {
                    RecordList(it, s, m, key, "/cases/${k.text("id")}/records?limit=100")
                }
                s.sections[key]?.let { Notice(it, true) }
            }
        More(cases, s) { m.more("cases", "/cases?limit=100") }
    }
}

@Composable
private fun RecordList(page: JsonObject, s: UiState, m: JobLensModel, key: String, path: String) {
    if (page.rows().isEmpty()) Meta("还没有训练记录。")
    page.rows().forEach { r ->
        QCard {
            Pill(label(r.text("status")))
            Text(r.text("title"), style = MaterialTheme.typography.titleLarge)
            Meta(
                "提交 ${r.number("attempts")} 次 · 查看提示 ${r.number("hint_requests")} 次 · 求助 ${r.number("assistance_requests")} 次"
            )
            if (r["observed_elapsed_ms"] != JsonNull && r.containsKey("observed_elapsed_ms"))
                Meta("观测时长约 ${r.number("observed_elapsed_ms")/60000} 分钟")
            if (r.text("measurement_note").isNotEmpty()) Meta(r.text("measurement_note"))
            Action("查看步骤与反馈", secondary = true) { m.navigate(Route(Page.TASK, r.text("task_id"))) }
        }
    }
    More(page, s) { m.more(key, path) }
}

@Composable
fun CaseScreen(s: UiState, m: JobLensModel) {
    val k = s.data["case"] ?: return
    val p = s.data["profile"]
    Heading(p?.text("display_name") ?: "学员个案")
    Pill(label(k.text("display_status")))
    p?.let {
        QCard {
            Text("支持需要", style = MaterialTheme.typography.titleLarge)
            Info("沟通方式", it.text("communication_preference"))
            Info(
                "感官偏好",
                it.array("sensory_preferences").joinToString("、") { v -> v.jsonPrimitive.content },
            )
            Info("工作情况", it.text("work_notes"))
        }
    }
    s.sections["profile"]?.let { Notice(it, true) }
    if (s.role == "counselor" && k.text("counselor_id") == s.user?.text("id")) {
        Action("匹配方向", secondary = true) { m.navigate(Route(Page.MATCH, k.text("id"))) }
        Action("SOP 与训练计划", secondary = true) { m.navigate(Route(Page.PLANS, k.text("id"))) }
    }
    k.text("current_task_id").takeIf(String::isNotEmpty)?.let { task ->
        Action("查看当前训练") { m.navigate(Route(Page.TASK, task)) }
    }
    Text("训练记录", style = MaterialTheme.typography.titleLarge)
    s.data["records"]?.let {
        RecordList(it, s, m, "records", "/cases/${k.text("id")}/records?limit=20")
    }
}

@Composable
fun TaskScreen(s: UiState, m: JobLensModel) {
    val task = s.data["task"] ?: return
    val tid = task.text("id")
    val status = task.text("status")
    val version = task.number("version")
    val revision = task.obj("revision")
    val steps = revision.rows("steps")
    val progress = task.rows("progress")
    val counselor = s.role == "counselor" && task.text("learner_id") != s.user?.text("id")
    val learner = s.role == "learner" && task.text("learner_id") == s.user?.text("id")
    val current = steps.firstOrNull { it.text("id") == task.text("current_step_id") }
    Heading(task.text("title"), revision.text("goal"))
    Pill(label(status))
    if (task.text("due_on").isNotEmpty()) Meta("截止日期 · ${task.text("due_on")}")
    val done = progress.count { it.text("status") == "completed" }
    Meta("已完成 $done / ${steps.size} 步")
    LinearProgressIndicator(
        progress = { if (steps.isEmpty()) 0f else done.toFloat() / steps.size },
        modifier = Modifier.fillMaxWidth(),
    )
    if (learner) {
        when (status) {
            "not_started" ->
                QCard {
                    Brand(size = 52)
                    Text("按自己的节奏，一次完成一步。")
                    Action("开始训练", !s.busy) {
                        m.write("POST", "/tasks/$tid/actions", json("action" to "start"), version) {
                            m.replaceData("task", it)
                        }
                    }
                }
            "paused" ->
                QCard {
                    Text("休息一下，也没关系。", style = MaterialTheme.typography.titleLarge)
                    Text("进度已保存，准备好后继续。")
                    Action("继续训练", !s.busy) {
                        m.write(
                            "POST",
                            "/tasks/$tid/actions",
                            json("action" to "resume"),
                            version,
                        ) {
                            m.replaceData("task", it)
                        }
                    }
                }
            "changes_requested" ->
                QCard {
                    Text("一起调整这几步。", style = MaterialTheme.typography.titleLarge)
                    Text(
                        s.data["submissions"]
                            ?.rows()
                            ?.firstOrNull()
                            ?.obj("feedback")
                            ?.text("message") ?: "请查看下方反馈。"
                    )
                    Action("继续修改", !s.busy) {
                        m.write(
                            "POST",
                            "/tasks/$tid/actions",
                            json("action" to "resume"),
                            version,
                        ) {
                            m.replaceData("task", it)
                        }
                    }
                }
            "submitted" -> Notice("结果已提交。辅导员审核后，反馈会出现在这里。")
            "completed" -> Notice("这次训练完成了。你可以在记录中回顾这次练习。")
            "cancelled" -> Notice("这项训练已结束。如有疑问，可以联系辅导员。")
            "in_progress" -> {
                if (current != null)
                    key(current.text("id")) {
                        QCard {
                            Meta("当前 · 第 ${current.number("position")} 步")
                            Text(
                                current.text("instruction"),
                                style = MaterialTheme.typography.titleLarge,
                            )
                            var showHint by
                                rememberSaveable(current.text("id")) { mutableStateOf(false) }
                            Action(if (showHint) "收起提示" else "看提示", !s.busy, secondary = true) {
                                showHint = !showHint
                                if (showHint) m.recordHint(tid, current.text("id"))
                            }
                            if (showHint) Notice("训练目标：${revision.text("goal")}。需要帮助时，可以把问题发给辅导员。")
                            AttachmentLinks(current.array("media_ids"), m, "查看步骤材料")
                            var attachmentIds by
                                rememberSaveable(tid, current.text("id")) {
                                    mutableStateOf<List<String>>(
                                        progress
                                            .firstOrNull {
                                                it.text("step_id") == current.text("id")
                                            }
                                            ?.array("attachment_ids")
                                            ?.map { it.jsonPrimitive.content } ?: emptyList()
                                    )
                                }
                            var waitingForFiles by
                                remember(current.text("id")) { mutableStateOf(false) }
                            AssetPicker(
                                s,
                                m,
                                task.text("case_id"),
                                tid,
                                "task_evidence",
                                attachmentIds,
                                pendingChanged = { waitingForFiles = it },
                            ) {
                                attachmentIds = it
                            }
                            val attachments = strings(attachmentIds)
                            if (current.flag("evidence_required")) Meta("这一步需要附件，通过安全检查后可以完成。")
                            Action(
                                "完成这一步",
                                !s.busy &&
                                    !waitingForFiles &&
                                    (!current.flag("evidence_required") ||
                                        attachments.isNotEmpty()),
                            ) {
                                m.write(
                                    "PUT",
                                    "/tasks/$tid/steps/${current.text("id")}",
                                    json("status" to "completed", "attachment_ids" to attachments),
                                    version,
                                ) {
                                    m.replaceData("task", it)
                                }
                            }
                        }
                    }
                if (allStepsDone(task)) {
                    var note by rememberSaveable(tid) { mutableStateOf("") }
                    Field(
                        "提交说明（可选）",
                        note,
                        { note = it },
                        enabled = !s.busy,
                        multiline = true,
                        max = 500,
                    )
                    var confirm by remember { mutableStateOf(false) }
                    Action("提交训练结果", !s.busy) { confirm = true }
                    ConfirmDialog(confirm, "提交训练结果？", "将当前步骤和说明发送给辅导员审核。", { confirm = false }) {
                        confirm = false
                        m.write("POST", "/tasks/$tid/submissions", json("note" to note), version)
                    }
                }
                Action("暂停训练", !s.busy, secondary = true) {
                    m.write("POST", "/tasks/$tid/actions", json("action" to "pause"), version) {
                        m.replaceData("task", it)
                    }
                }
            }
        }
        Action("请求辅导员帮助", !s.busy, secondary = true) {
            m.navigate(
                Route(Page.NEW_SUPPORT, task.text("case_id"), tid, current?.text("id").orEmpty())
            )
        }
    }
    Text("所有步骤", style = MaterialTheme.typography.titleLarge)
    steps.forEach { step ->
        QCard {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Pill(
                    if (
                        progress.any {
                            it.text("step_id") == step.text("id") &&
                                it.text("status") == "completed"
                        }
                    )
                        "✓"
                    else step.number("position").toString()
                )
                Text(step.text("instruction"), Modifier.weight(1f))
            }
            if (step.flag("evidence_required")) Meta("需要附件")
        }
    }
    Text("提交与反馈", style = MaterialTheme.typography.titleLarge)
    s.data["submissions"]?.let { page ->
        if (page.rows().isEmpty()) Meta("还没有提交记录。")
        page.rows().forEach { sub ->
            QCard {
                Text(
                    "第 ${sub.number("attempt_no")} 次提交",
                    style = MaterialTheme.typography.titleMedium,
                )
                Meta(dateLabel(sub.text("submitted_at")))
                if (sub.obj("feedback").isNotEmpty()) Text(sub.obj("feedback").text("message"))
                Action(
                    if (counselor && sub.obj("feedback").isEmpty()) "审核这次提交" else "查看提交",
                    secondary = true,
                ) {
                    m.navigate(Route(Page.SUBMISSION, sub.text("id")))
                }
            }
        }
        More(page, s) { m.more("submissions", "/tasks/$tid/submissions?limit=20") }
    }
    s.sections["submissions"]?.let { Notice(it, true) }
}

@Composable
fun SubmissionScreen(s: UiState, m: JobLensModel) {
    val sub = s.data["submission"] ?: return
    Heading("第 ${sub.number("attempt_no")} 次提交", dateLabel(sub.text("submitted_at")))
    QCard {
        Info("提交说明", sub.text("note"))
        val revision = s.data["revision"]
        sub.obj("snapshot").rows("progress").forEach { p ->
            val step = revision?.rows("steps")?.firstOrNull { it.text("id") == p.text("step_id") }
            Text(
                "${if(p.text("status")=="completed")"✓" else "○"} ${step?.text("instruction")?:"步骤 ${p.text("step_id").take(8)}"}"
            )
            AttachmentLinks(p.array("attachment_ids"), m)
        }
    }
    val feedback = sub.obj("feedback")
    if (feedback.isNotEmpty())
        QCard {
            Pill(label(feedback.text("outcome")))
            Text(feedback.text("message"))
            Meta(dateLabel(feedback.text("created_at")))
        }
    else if (
        s.role == "counselor" &&
            s.data["task"]?.text("learner_id") != null &&
            s.data["task"]?.text("learner_id") != s.user?.text("id") &&
            sub.text("task_status") == "submitted"
    ) {
        var message by rememberSaveable(sub.text("id")) { mutableStateOf("") }
        var outcome by rememberSaveable { mutableStateOf("passed") }
        var redo by rememberSaveable(sub.text("id")) { mutableStateOf(emptyList<String>()) }
        var confirm by remember { mutableStateOf(false) }
        Heading("写下具体反馈")
        Toggle("需要修改", outcome == "changes_requested", !s.busy) {
            outcome = if (it) "changes_requested" else "passed"
        }
        Field("反馈内容", message, { message = it }, !s.busy, multiline = true, max = 500)
        if (outcome == "changes_requested") {
            Text("选择需要重做的步骤")
            s.data["revision"]?.rows("steps")?.forEach { step ->
                Toggle(step.text("instruction"), step.text("id") in redo, !s.busy) {
                    redo = if (it) redo + step.text("id") else redo - step.text("id")
                }
            }
        }
        Action(
            "确认发送反馈",
            !s.busy && message.isNotBlank() && (outcome == "passed" || redo.isNotEmpty()),
        ) {
            confirm = true
        }
        ConfirmDialog(
            confirm,
            "发送审核反馈？",
            if (outcome == "passed") "确认通过后，这次任务将完成。" else "学员将根据反馈重新完成选定步骤。",
            { confirm = false },
        ) {
            confirm = false
            m.write(
                "POST",
                "/submissions/${sub.text("id")}/feedback",
                json(
                    "outcome" to outcome,
                    "message" to message.trim(),
                    "tags" to JsonArray(emptyList()),
                    "redo_step_ids" to
                        strings(if (outcome == "passed") emptyList() else redo.toList()),
                    "annotation_ids" to JsonArray(emptyList()),
                ),
                sub.number("task_version"),
            )
        }
    } else if (feedback.isEmpty()) Meta("暂时没有反馈。")
}

@Composable
fun More(page: JsonObject, s: UiState, click: () -> Unit) {
    if (page.flag("has_more"))
        Action("查看更多", !s.loading && !s.busy, secondary = true, click = click)
}

@Composable
fun Info(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Meta(label)
        Text(value.ifBlank { "尚未填写" })
    }
}

@Composable
fun ConfirmDialog(
    show: Boolean,
    title: String,
    text: String,
    dismiss: () -> Unit,
    confirm: () -> Unit,
) {
    if (show)
        AlertDialog(
            onDismissRequest = dismiss,
            title = { Text(title) },
            text = { Text(text) },
            confirmButton = { TextButton(onClick = confirm) { Text("确认") } },
            dismissButton = { TextButton(onClick = dismiss) { Text("再看一下") } },
        )
}

fun dateLabel(value: String): String = runCatching {
    java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
        .withZone(java.time.ZoneId.systemDefault())
        .format(java.time.Instant.parse(value))
}
    .getOrElse { value.replace('T', ' ').take(16) }
