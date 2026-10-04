package xyz.qunxue.joblens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import java.time.LocalDate
import java.util.UUID
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

@Composable
fun MatchScreen(s: UiState, m: JobLensModel) {
    val match = s.data["match"] ?: return
    Heading("匹配方向", "和学员一起确认目标，再制定清楚的训练步骤。")
    Pill(label(match.text("state")))
    var direction by rememberSaveable(s.route.id) { mutableStateOf(match.text("direction")) }
    var focus by rememberSaveable(s.route.id) { mutableStateOf(match.text("focus")) }
    var cycle by
        rememberSaveable(s.route.id) { mutableStateOf(match.number("cycle_weeks").toString()) }
    var basis by rememberSaveable(s.route.id) { mutableStateOf(match.text("basis")) }
    var version by rememberSaveable(s.route.id) { mutableStateOf(match.number("version")) }
    val editable = !s.busy && match.text("state") == "draft"
    Field("工作方向", direction, { direction = it }, editable, max = 80)
    Field("训练重点", focus, { focus = it }, editable, multiline = true, max = 500)
    Field(
        "训练周期（周）",
        cycle,
        { cycle = it.filter(Char::isDigit) },
        editable,
        keyboard = KeyboardType.Number,
        max = 2,
    )
    Field("匹配依据", basis, { basis = it }, editable, multiline = true, max = 1000)
    val dirty =
        direction != match.text("direction") ||
            focus != match.text("focus") ||
            cycle != match.number("cycle_weeks").toString() ||
            basis != match.text("basis")
    if (match.text("state") == "draft") {
        Action("保存方向", editable && (cycle.toIntOrNull() ?: 0) in 1..52) {
            m.write(
                "PUT",
                "/cases/${s.route.id}/match",
                json(
                    "direction" to direction,
                    "focus" to focus,
                    "cycle_weeks" to cycle.toInt(),
                    "basis" to basis,
                ),
                version,
            ) {
                version = it.number("version")
                m.replaceData("match", it)
            }
        }
        if (dirty) Meta("先保存当前修改，再确认方向。")
        var confirm by remember { mutableStateOf(false) }
        Action(
            "确认方向",
            editable &&
                !dirty &&
                direction.isNotBlank() &&
                focus.isNotBlank() &&
                basis.isNotBlank(),
        ) {
            confirm = true
        }
        ConfirmDialog(confirm, "确认这份匹配方向？", "确认后可以继续制定 SOP 训练计划。", { confirm = false }) {
            confirm = false
            m.write("POST", "/cases/${s.route.id}/match/confirm", version = version)
        }
    }
    if (version != match.number("version"))
        Action("采用最新方向", secondary = true) {
            direction = match.text("direction")
            focus = match.text("focus")
            cycle = match.number("cycle_weeks").toString()
            basis = match.text("basis")
            version = match.number("version")
        }
}

@Composable
fun PlansScreen(s: UiState, m: JobLensModel) {
    Heading("SOP 与训练计划", "把任务拆成看得见、做得到的小步骤。")
    s.data["list"]?.let { page ->
        if (page.rows().isEmpty()) Empty("还没有训练计划", "新建一份计划，从训练目标和第一步开始。")
        page.rows().forEach { plan ->
            QCard {
                Text(plan.text("title"), style = MaterialTheme.typography.titleLarge)
                val draft = plan.text("draft_revision_id")
                val published = plan.text("published_revision_id")
                if (draft.isNotEmpty())
                    Action("编辑草稿", secondary = true) {
                        m.navigate(Route(Page.REVISION, draft, s.route.id))
                    }
                if (published.isNotEmpty()) {
                    Action("查看已发布版本", secondary = true) {
                        m.navigate(Route(Page.REVISION, published, s.route.id))
                    }
                    if (draft.isEmpty())
                        Action("新建修订草稿", !s.busy, secondary = true) {
                            m.write(
                                "POST",
                                "/sop-plans/${plan.text("id")}/revisions",
                                json("base_revision_id" to published),
                                success = m.afterCreated(Page.REVISION, s.route.id),
                            )
                        }
                }
            }
        }
        More(page, s) { m.more("list", "/cases/${s.route.id}/sop-plans?limit=20") }
    }
    var title by rememberSaveable(s.route.id) { mutableStateOf("") }
    QCard {
        Text("新建训练计划", style = MaterialTheme.typography.titleLarge)
        Field("计划名称", title, { title = it }, !s.busy, max = 120)
        Action("创建计划", !s.busy && title.isNotBlank()) {
            m.write("POST", "/cases/${s.route.id}/sop-plans", json("title" to title.trim())) { plan
                ->
                title = ""
                val draft = plan.text("draft_revision_id")
                if (draft.isNotEmpty()) m.navigate(Route(Page.REVISION, draft, s.route.id))
                else m.load()
            }
        }
    }
}

@Composable
fun RevisionScreen(s: UiState, m: JobLensModel) {
    val revision = s.data["revision"] ?: return
    val rid = revision.text("id")
    val editable = revision.text("state") == "draft" && s.role == "counselor"
    Heading(
        if (editable) "编辑训练步骤" else "训练步骤",
        "版本 ${revision.number("revision_no")} · ${label(revision.text("state"))}",
    )
    var goal by rememberSaveable(rid) { mutableStateOf(revision.text("goal")) }
    var steps by
        rememberSaveable(
            rid,
            stateSaver =
                Saver<List<JsonObject>, String>(
                    save = { JsonArray(it).toString() },
                    restore = {
                        JsonCodec.parseToJsonElement(it).jsonArray.map { v -> v.jsonObject }
                    },
                ),
        ) {
            mutableStateOf(revision.rows("steps"))
        }
    var version by rememberSaveable(rid) { mutableStateOf(revision.number("version")) }
    var promptLevel by
        rememberSaveable(rid) { mutableStateOf(revision.obj("reminder").number("prompt_level", 2)) }
    var speech by
        rememberSaveable(rid) { mutableStateOf(revision.obj("reminder").flag("speech_enabled")) }
    var vibration by
        rememberSaveable(rid) { mutableStateOf(revision.obj("reminder").flag("vibration_enabled")) }
    var due by rememberSaveable(rid) { mutableStateOf("") }
    var confirm by remember { mutableStateOf(false) }
    Field("训练目标", goal, { goal = it }, editable && !s.busy, multiline = true, max = 1000)
    steps.forEachIndexed { index, step ->
        key(step.text("id")) {
            QCard {
                Text("第 ${index+1} 步", style = MaterialTheme.typography.titleMedium)
                Field(
                    "具体操作说明",
                    step.text("instruction"),
                    { v ->
                        steps = steps.mapIndexed { i, old ->
                            if (i == index) JsonObject(old + ("instruction" to JsonPrimitive(v)))
                            else old
                        }
                    },
                    editable && !s.busy,
                    multiline = true,
                    max = 2000,
                )
                Toggle("完成时需要附件", step.flag("evidence_required"), editable && !s.busy) { v ->
                    steps = steps.mapIndexed { i, old ->
                        if (i == index) JsonObject(old + ("evidence_required" to JsonPrimitive(v)))
                        else old
                    }
                }
                if (editable && s.route.parent.isNotEmpty()) {
                    AssetPicker(
                        s,
                        m,
                        s.route.parent,
                        null,
                        "sop_media",
                        step.array("media_ids").map { it.jsonPrimitive.content },
                    ) { media ->
                        steps = steps.mapIndexed { i, old ->
                            if (i == index) JsonObject(old + ("media_ids" to strings(media)))
                            else old
                        }
                    }
                } else AttachmentLinks(step.array("media_ids"), m, "查看步骤材料")
                if (editable)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(
                            onClick = {
                                steps =
                                    steps.toMutableList().also {
                                        val item = it.removeAt(index)
                                        it.add(index - 1, item)
                                    }
                            },
                            enabled = !s.busy && index > 0,
                        ) {
                            Text("上移")
                        }
                        TextButton(
                            onClick = {
                                steps =
                                    steps.toMutableList().also {
                                        val item = it.removeAt(index)
                                        it.add(index + 1, item)
                                    }
                            },
                            enabled = !s.busy && index < steps.lastIndex,
                        ) {
                            Text("下移")
                        }
                        TextButton(
                            onClick = { steps = steps.filterIndexed { i, _ -> i != index } },
                            enabled = !s.busy,
                        ) {
                            Text("移除步骤")
                        }
                    }
            }
        }
    }
    if (editable) {
        Action("添加一步", !s.busy && steps.size < 100, secondary = true) {
            steps =
                steps +
                    json(
                        "id" to UUID.randomUUID().toString(),
                        "position" to steps.size + 1,
                        "instruction" to "",
                        "media_ids" to JsonArray(emptyList()),
                        "estimated_seconds" to 0,
                        "evidence_required" to false,
                    )
        }
        QCard {
            Text("提醒方式", style = MaterialTheme.typography.titleLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                (1..3).forEach { level ->
                    FilterChip(
                        selected = promptLevel == level,
                        onClick = { promptLevel = level },
                        label = { Text(listOf("基础", "标准", "详细")[level - 1]) },
                        enabled = !s.busy,
                    )
                }
            }
            Toggle("语音指引", speech, !s.busy) { speech = it }
            Toggle("震动提示", vibration, !s.busy) { vibration = it }
        }
        val normalized = steps.mapIndexed { i, step ->
            JsonObject(step + ("position" to JsonPrimitive(i + 1)))
        }
        val reminder =
            json(
                "speech_enabled" to speech,
                "vibration_enabled" to vibration,
                "prompt_level" to promptLevel,
            )
        val dirty =
            goal != revision.text("goal") ||
                JsonArray(normalized) != revision.array("steps") ||
                reminder != revision.obj("reminder")
        Action("保存草稿", !s.busy) {
            m.write(
                "PUT",
                "/sop-revisions/$rid",
                json("goal" to goal, "steps" to JsonArray(normalized), "reminder" to reminder),
                version,
            ) {
                version = it.number("version")
                steps = it.rows("steps")
                m.replaceData("revision", it)
            }
        }
        Field("截止日期（可选，YYYY-MM-DD）", due, { due = it }, !s.busy, max = 10)
        val validDate = due.isEmpty() || runCatching { LocalDate.parse(due) }.isSuccess
        if (dirty) Meta("先保存全部修改，再发布。发布会为学员创建真实训练任务。")
        Action(
            "发布训练任务",
            !s.busy &&
                !dirty &&
                goal.isNotBlank() &&
                steps.isNotEmpty() &&
                steps.all { it.text("instruction").isNotBlank() } &&
                validDate,
        ) {
            confirm = true
        }
        ConfirmDialog(confirm, "发布训练任务？", "这份步骤将成为固定版本，并为学员创建一次真实训练。", { confirm = false }) {
            confirm = false
            m.write(
                "POST",
                "/sop-revisions/$rid/publish",
                json("due_on" to due.takeIf(String::isNotEmpty)),
                version,
            )
        }
    }
    if (revision.number("version") != version) {
        Notice("服务器已有新版本。你的草稿仍保留，采用新版本会替换当前输入。")
        Action("采用最新版本", secondary = true) {
            goal = revision.text("goal")
            steps = revision.rows("steps")
            version = revision.number("version")
            promptLevel = revision.obj("reminder").number("prompt_level", 2)
            speech = revision.obj("reminder").flag("speech_enabled")
            vibration = revision.obj("reminder").flag("vibration_enabled")
        }
    }
}
