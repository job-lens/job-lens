package xyz.qunxue.joblens

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import xyz.qunxue.joblens.core.*

/**
 * Cookie is encrypted at rest with a device-local, non-exportable Android Keystore key. No
 * passwords, API response bodies, or user profiles are written to disk. Backups disabled.
 */
class EncryptedSessionStore(context: Context) : SessionStore {
    private val preferences = context.getSharedPreferences("session.v1", Context.MODE_PRIVATE)
    private val alias = "joblens.session.v1"

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        return (store.getKey(alias, null) as? SecretKey)
            ?: KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
                .apply {
                    init(
                        KeyGenParameterSpec.Builder(
                                alias,
                                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                            )
                            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                            .build()
                    )
                }
                .generateKey()
    }

    @Synchronized
    override fun read(): StoredSession? = runCatching {
        val encoded = preferences.getString("cookie", null) ?: return null
        val parts = encoded.split('.')
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            key(),
            GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)),
        )
        val values =
            String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), Charsets.UTF_8)
                .split('\n')
        StoredSession(values[0], values[1].toLong(), values[2])
    }
        .getOrElse {
            preferences.edit().clear().apply()
            null
        }

    @Synchronized
    override fun write(value: StoredSession?) {
        if (value == null) {
            preferences.edit().clear().commit()
            return
        }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val body =
            cipher.doFinal("${value.cookie}\n${value.expiresAt}\n${value.origin}".toByteArray())
        preferences
            .edit()
            .putString(
                "cookie",
                Base64.encodeToString(cipher.iv, Base64.NO_WRAP) +
                    "." +
                    Base64.encodeToString(body, Base64.NO_WRAP),
            )
            .commit()
    }
}

class HttpsTransport : Transport {
    private val pool = Executors.newFixedThreadPool(3)

    override suspend fun execute(request: WireRequest): WireResponse =
        suspendCancellableCoroutine { continuation ->
            val connection = URL(request.url).openConnection() as HttpURLConnection
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 15000
            connection.readTimeout = 25000
            connection.requestMethod = request.method
            request.headers.forEach { (k, v) -> connection.setRequestProperty(k, v) }
            continuation.invokeOnCancellation { connection.disconnect() }
            pool.execute {
                try {
                    (request.binaryBody ?: request.body?.toByteArray(Charsets.UTF_8))?.let {
                        connection.doOutput = true
                        connection.setFixedLengthStreamingMode(it.size)
                        connection.outputStream.use { out -> out.write(it) }
                    }
                    val status = connection.responseCode
                    val content = request.url.endsWith("/content") && status in 200..299
                    val bytes =
                        (if (status in 200..299) connection.inputStream else connection.errorStream)
                            ?.use {
                                readBounded(it, if (content) 20 * 1024 * 1024 + 1 else 4_000_001)
                            } ?: byteArrayOf()
                    if (bytes.size > (if (content) 20 * 1024 * 1024 else 4_000_000))
                        throw java.io.IOException("Response too large")
                    val body = if (content) "" else String(bytes, Charsets.UTF_8)
                    val cookies =
                        connection.headerFields
                            .filterKeys { it?.equals("Set-Cookie", true) == true }
                            .values
                            .flatten()
                    if (continuation.isActive)
                        continuation.resume(
                            WireResponse(status, body, cookies, if (content) bytes else null)
                        )
                } catch (e: Exception) {
                    if (continuation.isActive) continuation.resumeWithException(e)
                } finally {
                    connection.disconnect()
                }
            }
        }
}

private fun readBounded(input: java.io.InputStream, limit: Int): ByteArray {
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (output.size() < limit) {
        val count = input.read(buffer, 0, minOf(buffer.size, limit - output.size()))
        if (count < 0) break
        output.write(buffer, 0, count)
    }
    return output.toByteArray()
}
