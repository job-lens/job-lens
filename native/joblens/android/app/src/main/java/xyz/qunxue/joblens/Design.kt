package xyz.qunxue.joblens

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Exact qx color/radius values from web styles/tokens.css at 790e886.
private val Light =
    lightColorScheme(
        primary = Color(0xFF111111),
        onPrimary = Color.White,
        primaryContainer = Color(0xFFF4F4F4),
        onPrimaryContainer = Color(0xFF111111),
        secondary = Color(0xFF303030),
        onSecondary = Color.White,
        secondaryContainer = Color(0xFFECECEC),
        onSecondaryContainer = Color(0xFF111111),
        tertiary = Color(0xFF315F91),
        surfaceTint = Color.Transparent,
        surfaceContainerLowest = Color.White,
        surfaceContainerLow = Color(0xFFF7F7F7),
        surfaceContainer = Color.White,
        surfaceContainerHigh = Color(0xFFF7F7F7),
        surfaceContainerHighest = Color(0xFFEDEDED),
        background = Color(0xFFF5F5F5),
        surface = Color.White,
        surfaceVariant = Color(0xFFEDEDED),
        onSurface = Color(0xFF111111),
        onSurfaceVariant = Color(0xFF6C6C6C),
        outline = Color(0xFFE3E3E3),
        error = Color(0xFF98434B),
        errorContainer = Color(0xFFF8EDEF),
    )
private val Dark =
    darkColorScheme(
        primary = Color(0xFFE0E4DB),
        onPrimary = Color(0xFF20241F),
        primaryContainer = Color(0xFF262B26),
        onPrimaryContainer = Color(0xFFE6E7E3),
        secondary = Color(0xFFC9CCC6),
        onSecondary = Color(0xFF20241F),
        secondaryContainer = Color(0xFF303630),
        onSecondaryContainer = Color(0xFFE6E7E3),
        tertiary = Color(0xFF90AAC6),
        surfaceTint = Color.Transparent,
        surfaceContainerLowest = Color(0xFF1C1E1D),
        surfaceContainerLow = Color(0xFF202221),
        surfaceContainer = Color(0xFF242625),
        surfaceContainerHigh = Color(0xFF2B2D2C),
        surfaceContainerHighest = Color(0xFF303331),
        background = Color(0xFF1C1E1D),
        surface = Color(0xFF242625),
        surfaceVariant = Color(0xFF303331),
        onSurface = Color(0xFFE6E7E3),
        onSurfaceVariant = Color(0xFFA4AAA2),
        outline = Color(0xFF383D38),
        error = Color(0xFFE2A3A6),
        errorContainer = Color(0xFF382729),
    )

@Composable
fun JobLensTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) Dark else Light,
        typography =
            Typography(
                headlineLarge =
                    TextStyle(
                        fontFamily = FontFamily.Serif,
                        fontWeight = FontWeight.Medium,
                        fontSize = 32.sp,
                        lineHeight = 46.sp,
                    ),
                headlineMedium =
                    TextStyle(
                        fontFamily = FontFamily.Serif,
                        fontWeight = FontWeight.Medium,
                        fontSize = 28.sp,
                        lineHeight = 40.sp,
                    ),
                titleLarge =
                    TextStyle(
                        fontFamily = FontFamily.Serif,
                        fontWeight = FontWeight.Medium,
                        fontSize = 21.sp,
                        lineHeight = 31.sp,
                    ),
                titleMedium =
                    TextStyle(
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 16.sp,
                        lineHeight = 25.sp,
                    ),
                bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 26.sp),
                bodyMedium = TextStyle(fontSize = 15.sp, lineHeight = 24.sp),
                labelLarge =
                    TextStyle(fontSize = 15.sp, lineHeight = 23.sp, fontWeight = FontWeight.Medium),
                labelMedium = TextStyle(fontSize = 13.sp, lineHeight = 20.sp),
                bodySmall = TextStyle(fontSize = 13.sp, lineHeight = 20.sp),
            ),
        shapes =
            Shapes(
                small = RoundedCornerShape(14.dp),
                medium = RoundedCornerShape(20.dp),
                large = RoundedCornerShape(28.dp),
                extraLarge = RoundedCornerShape(32.dp),
            ),
        content = content,
    )
}

@Composable
fun Brand(modifier: Modifier = Modifier, size: Int = 40) {
    Image(painterResource(R.drawable.brand_mark), "融职境", modifier.size(size.dp))
}

@Composable
fun QIcon(res: Int, description: String? = null, modifier: Modifier = Modifier) {
    Icon(painterResource(res), description, modifier.size(22.dp))
}

@Composable
fun Heading(title: String, subtitle: String = "") {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            title,
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.semantics { heading() },
        )
        if (subtitle.isNotEmpty())
            Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun Meta(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
fun QCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(
            Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
            content = content,
        )
    }
}

@Composable
fun Action(
    text: String,
    enabled: Boolean = true,
    secondary: Boolean = false,
    modifier: Modifier = Modifier,
    click: () -> Unit,
) {
    if (secondary)
        OutlinedButton(
            onClick = click,
            enabled = enabled,
            modifier = modifier.heightIn(min = 48.dp),
            shape = RoundedCornerShape(50),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Text(text)
        }
    else
        Button(
            onClick = click,
            enabled = enabled,
            modifier = modifier.heightIn(min = 48.dp),
            shape = RoundedCornerShape(50),
        ) {
            Text(text)
        }
}

@Composable
fun Field(
    label: String,
    value: String,
    change: (String) -> Unit,
    enabled: Boolean = true,
    multiline: Boolean = false,
    password: Boolean = false,
    keyboard: KeyboardType = KeyboardType.Text,
    max: Int = 2000,
) {
    OutlinedTextField(
        value = value,
        onValueChange = { if (it.length <= max) change(it) },
        label = { Text(label) },
        enabled = enabled,
        modifier = Modifier.fillMaxWidth(),
        singleLine = !multiline,
        minLines = if (multiline) 3 else 1,
        shape = RoundedCornerShape(if (multiline) 24.dp else 28.dp),
        textStyle = MaterialTheme.typography.bodyLarge,
        keyboardOptions =
            KeyboardOptions(
                keyboardType = if (password) KeyboardType.Password else keyboard,
                imeAction = if (multiline) ImeAction.Default else ImeAction.Next,
            ),
        visualTransformation =
            if (password) PasswordVisualTransformation() else VisualTransformation.None,
        colors =
            OutlinedTextFieldDefaults.colors(
                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline,
            ),
    )
}

@Composable
fun Empty(title: String, body: String) {
    QCard {
        Brand(size = 52)
        Text(title, style = MaterialTheme.typography.titleLarge)
        Text(body, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun Pill(text: String) {
    Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surfaceVariant) {
        Text(
            text,
            Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
fun Notice(text: String, error: Boolean = false) {
    Surface(
        Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(14.dp),
        color =
            if (error) MaterialTheme.colorScheme.errorContainer
            else MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Text(
            text,
            Modifier.padding(16.dp),
            color =
                if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
fun Toggle(title: String, value: Boolean, enabled: Boolean = true, change: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(title, Modifier.weight(1f))
        Switch(checked = value, onCheckedChange = change, enabled = enabled)
    }
}
