package xyz.qunxue.joblens

import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.geometry.*
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.*
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.currentStateAsState
import kotlin.math.*
import kotlinx.coroutines.delay

/**
 * Original JobLens Buddy.tsx paths, gradients, layering and timing at e6a9c9f. All pixels are drawn
 * by native Compose Canvas; no raster replacement or WebView.
 */
@Stable
class CompanionMotion(enabled: Boolean) {
    var enabled by mutableStateOf(enabled)
    var reduced by mutableStateOf(false)
}

val LocalCompanionMotion = staticCompositionLocalOf { CompanionMotion(true) }

@Composable
fun CompanionMotionProvider(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val prefs = remember(context) { context.getSharedPreferences("companion-motion", 0) }
    val motion = remember(prefs) { CompanionMotion(prefs.getBoolean("enabled", true)) }
    DisposableEffect(context, motion) {
        fun readScale() {
            motion.reduced =
                Settings.Global.getFloat(
                    context.contentResolver,
                    Settings.Global.ANIMATOR_DURATION_SCALE,
                    1f,
                ) == 0f
        }
        val observer =
            object : ContentObserver(Handler(Looper.getMainLooper())) {
                override fun onChange(selfChange: Boolean) {
                    readScale()
                }
            }
        readScale()
        context.contentResolver.registerContentObserver(
            Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE),
            false,
            observer,
        )
        onDispose { context.contentResolver.unregisterContentObserver(observer) }
    }
    LaunchedEffect(motion.enabled) { prefs.edit().putBoolean("enabled", motion.enabled).apply() }
    CompositionLocalProvider(LocalCompanionMotion provides motion, content = content)
}

private val buddyPaths =
    listOf(
            "M34 220C36 194 62 182 101 182C140 182 166 194 168 220Z",
            "M84 183C90 192 112 192 118 183",
            "M26 122C20 58 58 22 102 22C148 22 186 58 178 124C176 148 170 166 160 178L44 178C32 166 28 148 26 122Z",
            "M73 137Q80.5 131 88 137M114 137Q121.5 131 129 137",
            "M98 153q3 2.2 6 0",
            "M40 114C34 62 64 36 102 36C142 36 170 62 164 114C156 106 150 100 144 90C138 102 128 106 120 104C104 108 82 108 66 104C56 106 48 110 40 114Z",
            "M126 60C134 72 140 84 143 92C138 98 132 101 124 102C128 88 128 74 126 60Z",
            "M30 118C26 56 62 26 102 26C144 26 178 56 172 118",
        )
        .map { PathParser().parsePathString(it).toPath() }

@Composable
fun Companion(
    modifier: Modifier = Modifier,
    closed: Boolean = false,
    framed: Boolean = true,
    size: Int = 128,
) {
    val motion = LocalCompanionMotion.current
    val life by LocalLifecycleOwner.current.lifecycle.currentStateAsState()
    val active = motion.enabled && !motion.reduced && life.isAtLeast(Lifecycle.State.RESUMED)
    var happy by remember { mutableStateOf(false) }
    LaunchedEffect(happy) {
        if (happy) {
            delay(1600)
            happy = false
        }
    }
    val phase =
        if (active) {
            val infinite = rememberInfiniteTransition(label = "小融自然动作")
            val tick by
                infinite.animateFloat(
                    0f,
                    120000f,
                    infiniteRepeatable(tween(120000, easing = LinearEasing)),
                    label = "呼吸与张望",
                )
            tick
        } else 0f
    val turn = if (active) sin(phase / 2600f) * 0.6f + sin(phase / 1000f) * 0.1f else 0.25f
    val nod = if (active) sin(phase / 3400f) * 0.3f else 0f
    val breath = if (active) -0.75f * (1f - cos(phase * (2 * PI / 4200).toFloat())) else 0f
    val sway = if (active) 0.1f - 1.1f * cos(phase * (2 * PI / 5000).toFloat()) else 0f
    val blinkAt = (phase % 5600f) / 5600f
    val blink =
        if (active && blinkAt in 0.92f..0.97f) 1f - 0.9f * (1f - abs(blinkAt - 0.945f) / 0.025f)
        else 1f
    val shut = closed || happy
    val paper = MaterialTheme.colorScheme.surface
    val controlInk = MaterialTheme.colorScheme.onSurfaceVariant
    val desc = if (motion.reduced) "已按系统设置关闭动效" else if (motion.enabled) "暂停伙伴动效" else "开启伙伴动效"
    Box(
        modifier.width((size + if (framed) 64 else 0).dp).height((size + if (framed) 32 else 0).dp)
    ) {
        Canvas(
            Modifier.fillMaxSize()
                .semantics {
                    contentDescription = "陪你做事的小伙伴"
                    stateDescription = if (shut) "小融闭眼" else "小融睁眼"
                }
                .clickable(onClickLabel = "让小融笑一笑") { happy = true }
        ) {
            if (framed) {
                val k = this.size.width / 192f
                scale(k, k, Offset.Zero) {
                    val center = Offset(96f, 88f)
                    drawCircle(
                        Brush.radialGradient(
                            listOf(Color.Black.copy(alpha = 0.14f), Color.Transparent),
                            center + Offset(0f, 16f),
                            94f,
                        ),
                        94f,
                        center + Offset(0f, 16f),
                    )
                    drawCircle(paper, 70f, center)
                    drawCircle(
                        Brush.radialGradient(
                            listOf(Color(0xFFF4F7FC), Color(0xFFDFE6F1)),
                            Offset(96f, 60f),
                            115f,
                        ),
                        64f,
                        center,
                    )
                    val crop =
                        Path().apply {
                            addRect(Rect(-30f, -40f, 210f, 88f))
                            addOval(Rect(32f, 24f, 160f, 152f))
                        }
                    clipPath(crop) {
                        translate(18f, 2.3f) {
                            scale(156f / 220f, 156f / 220f, Offset.Zero) {
                                drawBuddy(turn, nod, breath, sway, blink, shut)
                            }
                        }
                    }
                }
            } else {
                scale(this.size.width / 220f, this.size.height / 224f, Offset.Zero) {
                    translate(0f, 10f) { drawBuddy(turn, nod, breath, sway, blink, shut) }
                }
            }
        }
        if (framed)
            IconButton(
                onClick = { motion.enabled = !motion.enabled },
                enabled = !motion.reduced,
                modifier =
                    Modifier.align(Alignment.BottomEnd).size(48.dp).semantics {
                        contentDescription = desc
                    },
            ) {
                Canvas(Modifier.size(16.dp)) {
                    val ink = controlInk
                    scale(this.size.width / 16f, this.size.height / 16f, Offset.Zero) {
                        if (motion.enabled && !motion.reduced) {
                            drawLine(ink, Offset(5f, 4f), Offset(5f, 12f), 1.5f, StrokeCap.Round)
                            drawLine(ink, Offset(11f, 4f), Offset(11f, 12f), 1.5f, StrokeCap.Round)
                        } else
                            drawPath(
                                Path().apply {
                                    moveTo(6f, 4f)
                                    lineTo(12f, 8f)
                                    lineTo(6f, 12f)
                                    close()
                                },
                                ink,
                                style = Stroke(1.5f, join = StrokeJoin.Round),
                            )
                    }
                }
            }
    }
}

private fun DrawScope.drawBuddy(
    turn: Float,
    nod: Float,
    breath: Float,
    sway: Float,
    blink: Float,
    closed: Boolean,
) {
    val ink = Color(0xFF2B221E)
    drawRoundRect(Color(0xFFF2DCCB), Offset(88f, 166f), Size(26f, 24f), CornerRadius(8f))
    drawPath(
        buddyPaths[0],
        Brush.verticalGradient(listOf(Color(0xFF82A6EE), Color(0xFF5D8FE6)), 182f, 220f),
    )
    drawPath(buddyPaths[1], Color(0xFFF3EDE4), style = Stroke(5f, cap = StrokeCap.Round))
    translate(0f, breath) {
        translate(turn * -6f, nod * -2f) { drawPath(buddyPaths[2], Color(0xFF3E2F28)) }
        translate(turn * 4f, nod) {
            drawOval(
                Brush.radialGradient(
                    listOf(Color(0xFFFFFAF5), Color(0xFFF7E6D6)),
                    Offset(92f, 118f),
                    78f,
                ),
                Offset(45f, 77f),
                Size(112f, 102f),
            )
        }
        translate(turn * 8f, nod * 2f) {
            drawOval(Color(0xFFF2B2A6).copy(alpha = 0.5f), Offset(57f, 147f), Size(18f, 10f))
            drawOval(Color(0xFFF2B2A6).copy(alpha = 0.5f), Offset(127f, 147f), Size(18f, 10f))
        }
        translate(turn * 11f, nod * 5f) {
            if (closed) drawPath(buddyPaths[3], ink, style = Stroke(3.2f, cap = StrokeCap.Round))
            else {
                drawRoundRect(
                    ink,
                    Offset(77f, 133.5f - 8.5f * blink),
                    Size(7.5f, 17f * blink),
                    CornerRadius(3.75f),
                )
                drawRoundRect(
                    ink,
                    Offset(117.5f, 133.5f - 8.5f * blink),
                    Size(7.5f, 17f * blink),
                    CornerRadius(3.75f),
                )
            }
            drawPath(buddyPaths[4], ink, style = Stroke(2.4f, cap = StrokeCap.Round))
        }
        translate(turn * 6f, nod) {
            rotate(sway, Offset(102f, 36f)) {
                drawPath(
                    buddyPaths[5],
                    Brush.linearGradient(
                        listOf(Color(0xFF6B5446), Color(0xFF3F3029)),
                        Offset(77f, 36f),
                        Offset(127f, 114f),
                    ),
                )
                drawPath(buddyPaths[6], Color(0xFF3A2B24).copy(alpha = 0.7f))
            }
        }
        translate(turn * 5f, 0f) {
            drawPath(buddyPaths[7], Color(0xFFCBBFAE), style = Stroke(5f, cap = StrokeCap.Round))
            val cup =
                Brush.verticalGradient(listOf(Color(0xFFF3EEE6), Color(0xFFD9CFC1)), 104f, 150f)
            drawRoundRect(cup, Offset(16f, 104f), Size(26f, 46f), CornerRadius(13f))
            drawRoundRect(Color(0xFFB8AA97), Offset(34f, 110f), Size(9f, 34f), CornerRadius(4.5f))
            drawRoundRect(cup, Offset(160f, 104f), Size(26f, 46f), CornerRadius(13f))
            drawRoundRect(Color(0xFFB8AA97), Offset(159f, 110f), Size(9f, 34f), CornerRadius(4.5f))
        }
    }
}

@Composable
fun WorkIllustration(step: Int, modifier: Modifier = Modifier) {
    val c = MaterialTheme.colorScheme
    val ruleStrong =
        if (androidx.compose.foundation.isSystemInDarkTheme()) Color(0xFF50574F)
        else Color(0xFFCCCCCC)
    val olive =
        if (androidx.compose.foundation.isSystemInDarkTheme()) Color(0xFFA7AFA9)
        else Color(0xFF718A72)
    Canvas(modifier.fillMaxWidth().height(138.dp).semantics { contentDescription = "文件与清单的操作示意" }) {
        val k = min(this.size.width / 320f, this.size.height / 170f)
        translate((this.size.width - 320f * k) / 2f, 0f) {
            scale(k, k, Offset.Zero) {
                fun p(s: String) = PathParser().parsePathString(s).toPath()
                drawPath(
                    p("M35 47h84l12 12h58v78a10 10 0 0 1-10 10H45a10 10 0 0 1-10-10Z"),
                    c.surfaceVariant,
                )
                rotate(-6f, Offset(160f, 90f)) {
                    drawRoundRect(c.surface, Offset(102f, 15f), Size(107f, 132f), CornerRadius(8f))
                    drawRoundRect(
                        c.outline,
                        Offset(102f, 15f),
                        Size(107f, 132f),
                        CornerRadius(8f),
                        style = Stroke(1f),
                    )
                    drawPath(
                        p("M120 36h62M120 45h39"),
                        ruleStrong,
                        style = Stroke(3f, cap = StrokeCap.Round),
                    )
                    repeat(3) { i ->
                        translate(0f, i * 26f) {
                            drawRoundRect(
                                if (i <= step) olive else c.surfaceVariant,
                                Offset(119f, 61f),
                                Size(12f, 12f),
                                CornerRadius(3f),
                            )
                            if (i <= step)
                                drawPath(p("m122 67 2 2 4-5"), c.surface, style = Stroke(1.5f))
                            drawPath(
                                p("M142 65h48M142 72h29"),
                                ruleStrong,
                                style = Stroke(2f, cap = StrokeCap.Round),
                            )
                        }
                    }
                }
                drawPath(
                    p("M230 96h42m-9-9 9 9-9 9"),
                    olive,
                    style = Stroke(3f, cap = StrokeCap.Round, join = StrokeJoin.Round),
                )
            }
        }
    }
}
