package xyz.qunxue.joblens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

@Composable
fun HomeScreen(s: UiState, m: JobLensModel) {
    val counselor = s.role == "counselor"
    if (counselor) {
        Meta(
            java.time.LocalDate.now()
                .format(
                    java.time.format.DateTimeFormatter.ofPattern(
                        "M月d日 EEEE",
                        java.util.Locale.CHINA,
                    )
                )
        )
        Heading("工作台", "把注意力留给需要支持的人。")
        Action("刷新工作台", !s.loading && !s.busy, secondary = true, click = m::load)
    } else {
        Heading("今天，从一步开始。", "按自己的节奏完成。有需要时，随时停一停。")
        Action("训练记录", secondary = true) { m.root(Page.RECORDS) }
    }
    s.data["dashboard"]?.let { d ->
        if (counselor) {
            listOf(
                    Triple("pending_tasks", "待完成训练", R.drawable.ic_tasks),
                    Triple("pending_feedback", "待审核提交", R.drawable.ic_records),
                    Triple("pending_assistance", "待处理求助", R.drawable.ic_chat),
                )
                .forEach { (key, title, icon) ->
                    Surface(
                        shape = RoundedCornerShape(20.dp),
                        color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(
                            Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(
                                Modifier.weight(1f),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    QIcon(icon)
                                    Meta(title)
                                }
                                if (key == "pending_tasks") Meta("项待完成")
                                else
                                    TextButton(
                                        onClick = {
                                            m.root(
                                                if (key == "pending_feedback") Page.CASES
                                                else Page.SUPPORT
                                            )
                                        }
                                    ) {
                                        Text(if (key == "pending_feedback") "查看待审核 →" else "打开辅导 →")
                                    }
                            }
                            Text(
                                d.number(key).toString(),
                                fontSize = 36.sp,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                }
        } else
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(
                        "pending_tasks" to "待完成",
                        "pending_feedback" to "等待反馈",
                        "pending_assistance" to "正在求助",
                    )
                    .forEach { (key, title) ->
                        Surface(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(20.dp),
                            color = MaterialTheme.colorScheme.surface,
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                        ) {
                            Column(
                                Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                Text(d.number(key).toString(), fontSize = 26.sp)
                                Meta(title)
                            }
                        }
                    }
            }
    }
    s.data["list"]?.let { page ->
        val rows =
            page.rows().filter {
                if (counselor) it.text("counselor_id") == s.user?.text("id")
                else
                    it.text("learner_id") == s.user?.text("id") &&
                        it.text("status") !in setOf("completed", "cancelled")
            }
        if (counselor) {
            QCard {
                Heading("继续跟进", "从已授权的个案继续工作")
                Action("全部个案", secondary = true) { m.root(Page.CASES) }
                if (rows.isEmpty()) {
                    QIcon(R.drawable.ic_users)
                    Text("还没有分配的个案")
                    Meta("分配完成后，学员资料与训练进度会出现在这里。")
                    Action("完善个人资料", secondary = true) { m.navigate(Route(Page.PROFILE)) }
                }
                rows.take(5).forEach { k ->
                    HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        QIcon(R.drawable.ic_user)
                        Column(Modifier.weight(1f)) {
                            Text(
                                "个案 #${k.text("id").take(8)}",
                                style = MaterialTheme.typography.titleMedium,
                            )
                            Meta(label(k.text("display_status")))
                        }
                        Action("查看", secondary = true) {
                            m.navigate(Route(Page.CASE, k.text("id")))
                        }
                    }
                }
            }
            QCard {
                Text("支持流程", style = MaterialTheme.typography.titleLarge)
                Meta("保留清晰、可回看的每一步。")
                listOf(
                        "了解与匹配" to "阅读资料，确认支持方向。",
                        "安排训练" to "把岗位任务拆成具体步骤。",
                        "反馈与跟进" to "查看提交，给出明确的下一步。",
                    )
                    .forEachIndexed { i, (title, body) ->
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Pill((i + 1).toString())
                            Column {
                                Text(title, style = MaterialTheme.typography.titleMedium)
                                Meta(body)
                            }
                        }
                    }
                Action("进入个案管理", modifier = Modifier.fillMaxWidth()) { m.root(Page.CASES) }
            }
            s.data["dashboard"]
                ?.text("as_of")
                ?.takeIf { it.isNotEmpty() }
                ?.let { Meta("数据更新于 ${dateLabel(it)}。只展示你有权访问的个案与训练。") }
        } else {
            if (rows.isEmpty())
                LearnerEmpty(
                    "暂时没有待完成的任务",
                    if (s.data["cases"]?.rows()?.isNotEmpty() == true)
                        "辅导员准备好下一次训练后，它会出现在这里。你也可以回看已完成的训练。"
                    else "先填写个人资料，让接下来的支持更适合你。个案分配完成后，你会在这里看到任务。",
                ) {
                    Action("完善个人资料", secondary = true) { m.navigate(Route(Page.PROFILE)) }
                }
            rows.forEach { TaskCard(it, m) }
            More(page, s) { m.more("list", "/tasks?limit=20") }
            Action("调整阅读与提醒", secondary = true) { m.navigate(Route(Page.PREFERENCES)) }
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
}

@Composable
fun LearnerEmpty(title: String, body: String, content: @Composable ColumnScope.() -> Unit = {}) {
    QCard {
        Row(
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Companion(framed = false, size = 80)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (title.isNotEmpty()) Text(title, style = MaterialTheme.typography.titleLarge)
                Meta(body)
                content()
            }
        }
        val motion = LocalCompanionMotion.current
        TextButton(onClick = { motion.enabled = !motion.enabled }, enabled = !motion.reduced) {
            Text(if (motion.reduced) "已按系统设置关闭动效" else if (motion.enabled) "暂停伙伴动效" else "开启伙伴动效")
        }
    }
}

@Composable
private fun TaskCard(task: JsonObject, m: JobLensModel) {
    QCard {
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                task.text("title"),
                Modifier.weight(1f),
                style = MaterialTheme.typography.titleMedium,
            )
            Pill(label(task.text("status")))
        }
        Meta(task.obj("revision").text("goal"))
        val total = task.obj("revision").rows("steps").size
        val done = task.rows("progress").count { it.text("status") == "completed" }
        LinearProgressIndicator(
            progress = { if (total > 0) done.toFloat() / total else 0f },
            modifier = Modifier.fillMaxWidth().height(6.dp),
        )
        Meta(
            "$done / $total 步" +
                (task.text("due_on").takeIf(String::isNotEmpty)?.let { " · $it 前完成" } ?: "")
        )
        Action(
            when (task.text("status")) {
                "submitted" -> "查看提交"
                "changes_requested" -> "查看反馈"
                "not_started" -> "查看任务"
                else -> "继续任务"
            },
            modifier = Modifier.align(Alignment.End),
        ) {
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
        if (cases.rows().isEmpty()) LearnerEmpty("", "开始第一次训练后，你的记录会出现在这里。")
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
    Text(task.text("title"), style = MaterialTheme.typography.titleMedium)
    Pill(label(status))
    if (task.text("due_on").isNotEmpty()) Meta("截止日期 · ${task.text("due_on")}")
    val done = progress.count { it.text("status") == "completed" }
    Meta("已完成 $done / ${steps.size} 步")
    if (learner) {
        when (status) {
            "not_started" ->
                TrainingFocus {
                    Companion()
                    Text(
                        revision.text("goal"),
                        style = MaterialTheme.typography.headlineMedium,
                        textAlign = TextAlign.Center,
                    )
                    Text("按自己的节奏，一次完成一步。", textAlign = TextAlign.Center)
                    Action("开始训练", !s.busy) {
                        m.write("POST", "/tasks/$tid/actions", json("action" to "start"), version) {
                            m.replaceData("task", it)
                        }
                    }
                }
            "paused" ->
                TrainingFocus {
                    Companion()
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
                TrainingFocus {
                    Companion()
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
            "submitted" ->
                TrainingFocus {
                    WorkIllustration(2)
                    Text("结果已提交。", style = MaterialTheme.typography.headlineMedium)
                    Text("辅导员审核后，反馈会出现在这里。", textAlign = TextAlign.Center)
                    Action("查看最新反馈", secondary = true, click = m::load)
                }
            "completed" ->
                TrainingFocus {
                    Companion()
                    Text("这次训练完成了。", style = MaterialTheme.typography.headlineMedium)
                    Text(
                        s.data["submissions"]
                            ?.rows()
                            ?.firstOrNull()
                            ?.obj("feedback")
                            ?.text("message")
                            ?.takeIf { it.isNotEmpty() } ?: "你可以在记录中回顾这次练习。",
                        textAlign = TextAlign.Center,
                    )
                    Action("查看训练记录") { m.root(Page.RECORDS) }
                }
            "cancelled" -> Notice("这项训练已结束。如有疑问，可以联系辅导员。")
            "in_progress" -> {
                if (current != null)
                    key(current.text("id")) {
                        TrainingFocus {
                            WorkIllustration(
                                (current.number("position").toInt() - 1).coerceIn(0, 2)
                            )
                            Meta("第 ${current.number("position")} 步")
                            Text(
                                current.text("instruction"),
                                style = MaterialTheme.typography.headlineMedium,
                                textAlign = TextAlign.Center,
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
    var revealSteps by rememberSaveable(tid) { mutableStateOf(false) }
    TextButton(onClick = { revealSteps = !revealSteps }) {
        Text(if (revealSteps) "收起所有步骤" else "查看所有步骤")
    }
    if (revealSteps)
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
private fun TrainingFocus(content: @Composable ColumnScope.() -> Unit) {
    Surface(
        Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(
            Modifier.heightIn(min = 400.dp).padding(horizontal = 16.dp, vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp, Alignment.CenterVertically),
            content = content,
        )
    }
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
