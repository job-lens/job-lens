package xyz.qunxue.joblens

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import java.io.File
import java.util.UUID
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import xyz.qunxue.joblens.core.*

/** Android Storage Access Framework; the user chooses exactly one file. No storage permission. */
@Composable
fun AssetPicker(
    s: UiState,
    m: JobLensModel,
    caseId: String,
    taskId: String?,
    purpose: String,
    value: List<String>,
    pendingChanged: (Boolean) -> Unit = {},
    change: (List<String>) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var selected by remember { mutableStateOf<Uri?>(null) }
    var name by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var reading by remember { mutableStateOf(false) }
    var pending by rememberSaveable(caseId, taskId, purpose) { mutableStateOf(emptyList<String>()) }
    var readyIds by
        rememberSaveable(caseId, taskId, purpose) { mutableStateOf(emptyList<String>()) }
    LaunchedEffect(value, pending, reading, selected) {
        pendingChanged(reading || selected != null || pending.any { it !in value })
    }
    val picker =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            selected = uri
            error = ""
            name =
                if (uri == null) ""
                else
                    context.contentResolver
                        .query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                        ?.use { if (it.moveToFirst()) it.getString(0) else "附件" } ?: "附件"
        }
    Meta("图片或 PDF，最多 5 个，每个不超过 20 MB。")
    if (error.isNotEmpty()) Notice(error, true)
    Action("选择附件", !s.busy && !reading && (value + pending).distinct().size < 5, secondary = true) {
        picker.launch(arrayOf("image/png", "image/jpeg", "image/webp", "application/pdf"))
    }
    selected?.let { uri ->
        Meta("已选择：$name")
        TextButton(onClick = { selected = null }, enabled = !s.busy && !reading) { Text("取消选择") }
        Action(if (reading) "正在读取…" else "上传这份附件", !s.busy && !reading, secondary = true) {
            reading = true
            scope.launch {
                try {
                    val mime = context.contentResolver.getType(uri) ?: "application/octet-stream"
                    val bytes =
                        withContext(Dispatchers.IO) {
                            context.contentResolver.openInputStream(uri)?.use { input ->
                                val out = java.io.ByteArrayOutputStream()
                                val buffer = ByteArray(8192)
                                while (true) {
                                    val count = input.read(buffer)
                                    if (count < 0) break
                                    if (out.size() + count > 20 * 1024 * 1024)
                                        throw IllegalArgumentException("文件不能超过 20 MB")
                                    out.write(buffer, 0, count)
                                }
                                out.toByteArray()
                            } ?: error("文件无法读取")
                        }
                    val request =
                        uploadRequest(
                            caseId,
                            taskId,
                            purpose,
                            name,
                            mime,
                            bytes,
                            UUID.randomUUID().toString(),
                        )
                    m.upload(request) { asset ->
                        pending = (pending + asset.text("id")).distinct()
                        selected = null
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    error = e.message ?: "附件未能读取"
                } finally {
                    reading = false
                }
            }
        }
    }
    (value + pending).distinct().forEach { fileId ->
        AssetStatus(
            fileId,
            m,
            s.busy,
            onReady = {
                readyIds = (readyIds + fileId).distinct()
                if (fileId !in value) change((value + readyIds).distinct())
            },
            onRemove = {
                pending = pending - fileId
                readyIds = readyIds - fileId
                change(value - fileId)
            },
        )
    }
}

@Composable
private fun AssetStatus(
    fileId: String,
    m: JobLensModel,
    busy: Boolean,
    onReady: () -> Unit,
    onRemove: () -> Unit,
) {
    var file by remember(fileId) { mutableStateOf<JsonObject?>(null) }
    var error by remember(fileId) { mutableStateOf("") }
    var retry by remember { mutableIntStateOf(0) }
    val readyCallback by rememberUpdatedState(onReady)
    LaunchedEffect(fileId, retry) {
        try {
            while (true) {
                val result = m.api.get("/files/${id(fileId)}")
                file = result
                if (result.text("state") == "ready") {
                    readyCallback()
                    break
                }
                if (result.text("state") !in setOf("quarantined", "scanning")) break
                delay(3000)
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            if (e is ApiFailure && e.status == 401) m.report(e)
            error = if (e is ApiFailure) e.message else "文件状态未能加载"
        }
    }
    val labels =
        mapOf(
            "quarantined" to "等待安全检查",
            "scanning" to "正在检查",
            "ready" to "可以使用",
            "rejected" to "未通过检查",
            "deleted" to "已删除",
        )
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (error.isNotEmpty()) {
            Notice(error, true)
            Action("刷新文件状态", !busy, secondary = true) {
                error = ""
                retry++
            }
        }
        file?.let { f ->
            Text(f.text("filename"))
            Meta(labels[f.text("state")] ?: "状态待确认")
            if (f.text("reason").isNotEmpty()) Notice(f.text("reason"), true)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (f.text("state") == "ready")
                    TextButton(
                        onClick = { m.navigate(Route(Page.FILE, fileId)) },
                        enabled = !busy,
                    ) {
                        Text("查看")
                    }
                TextButton(onClick = onRemove, enabled = !busy) { Text("从本次选择移除") }
            }
        } ?: Meta("正在读取文件状态…")
    }
}

@Composable
fun AttachmentLinks(ids: JsonArray, m: JobLensModel, label: String = "查看附件") {
    ids.forEachIndexed { i, value ->
        val fileId = (value as? JsonPrimitive)?.contentOrNull
        if (fileId != null)
            Action("$label ${i+1}", secondary = true) { m.navigate(Route(Page.FILE, fileId)) }
    }
}

@Composable
fun FileScreen(s: UiState, m: JobLensModel) {
    val metadata = s.data["file"] ?: return
    Heading(metadata.text("filename"))
    Meta("${(metadata.number("size_bytes")+1023)/1024} KB · 私有附件")
    if (metadata.text("state") != "ready") {
        Notice(
            when (metadata.text("state")) {
                "rejected" -> metadata.text("reason", "未通过检查")
                "deleted" -> "附件已删除"
                else -> "附件尚未通过安全检查，暂时不能打开。"
            }
        )
        return
    }
    val context = LocalContext.current
    var bytes by remember(s.route.id) { mutableStateOf<ByteArray?>(null) }
    var bitmap by remember(s.route.id) { mutableStateOf<Bitmap?>(null) }
    var page by remember(s.route.id) { mutableIntStateOf(0) }
    var pages by remember(s.route.id) { mutableIntStateOf(0) }
    var error by remember(s.route.id) { mutableStateOf("") }
    var retry by remember { mutableIntStateOf(0) }
    val isPdf = metadata.text("mime_type") == "application/pdf"
    val cacheFile =
        remember(s.route.id) { File(context.cacheDir, "joblens-preview-${UUID.randomUUID()}.pdf") }
    DisposableEffect(cacheFile) { onDispose { cacheFile.delete() } }
    LaunchedEffect(s.route.id, retry) {
        try {
            bytes = m.api.file(s.route.id)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            if (e is ApiFailure && e.status == 401) m.report(e)
            error = if (e is ApiFailure) e.message else "文件未能加载，请重试。"
        }
    }
    LaunchedEffect(bytes, page) {
        val content = bytes ?: return@LaunchedEffect
        try {
            val rendered =
                withContext(Dispatchers.IO) {
                    if (isPdf) {
                        cacheFile.writeBytes(content)
                        PdfRenderer(
                                ParcelFileDescriptor.open(
                                    cacheFile,
                                    ParcelFileDescriptor.MODE_READ_ONLY,
                                )
                            )
                            .use { renderer ->
                                pages = renderer.pageCount
                                renderer.openPage(page).use { p ->
                                    val scale =
                                        minOf(
                                            2f,
                                            1800f / p.width.coerceAtLeast(1),
                                            2400f / p.height.coerceAtLeast(1),
                                        )
                                    Bitmap.createBitmap(
                                            (p.width * scale).toInt().coerceAtLeast(1),
                                            (p.height * scale).toInt().coerceAtLeast(1),
                                            Bitmap.Config.ARGB_8888,
                                        )
                                        .also {
                                            it.eraseColor(android.graphics.Color.WHITE)
                                            p.render(
                                                it,
                                                null,
                                                null,
                                                PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY,
                                            )
                                        }
                                }
                            }
                    } else {
                        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                        BitmapFactory.decodeByteArray(content, 0, content.size, bounds)
                        val options =
                            BitmapFactory.Options().apply {
                                inSampleSize =
                                    maxOf(1, maxOf(bounds.outWidth, bounds.outHeight) / 1800)
                            }
                        BitmapFactory.decodeByteArray(content, 0, content.size, options)
                            ?: error("图片格式不受支持")
                    }
                }
            bitmap = rendered
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            error = "文件预览未能打开。"
        }
    }
    if (error.isNotEmpty()) {
        Notice(error, true)
        Action("重试打开", secondary = true) {
            error = ""
            retry++
        }
    }
    bitmap?.let {
        Image(
            it.asImageBitmap(),
            metadata.text("filename"),
            Modifier.fillMaxWidth().heightIn(min = 200.dp, max = 800.dp),
        )
    } ?: LinearProgressIndicator(Modifier.fillMaxWidth())
    if (isPdf && pages > 0)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Action("上一页", page > 0, secondary = true) { page-- }
            Text("${page+1} / $pages")
            Action("下一页", page < pages - 1, secondary = true) { page++ }
        }
}
