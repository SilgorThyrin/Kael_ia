package com.kael.assist

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

class KaelAssistActivity : Activity() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var statusView: TextView? = null
    private var replyView: TextView? = null
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsPronto = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 48)
            setBackgroundColor(Color.parseColor("#111827"))
        }
        val titulo = TextView(this).apply { text = "Kael Assist"; setTextColor(Color.WHITE); textSize = 22f }
        statusView = TextView(this).apply { text = "Preparando..."; setTextColor(Color.parseColor("#93C5FD")); textSize = 15f; setPadding(0, 16, 0, 16) }
        replyView = TextView(this).apply { text = ""; setTextColor(Color.parseColor("#E5E7EB")); textSize = 16f; setPadding(0, 8, 0, 24) }
        val btns = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val btnFalar = Button(this).apply { text = "Falar"; setOnClickListener { verificarPermissaoEEscutar() } }
        val btnChat = Button(this).apply { text = "Abrir Chat"; setOnClickListener { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:8000"))); finish() } }
        val btnFechar = Button(this).apply { text = "Fechar"; setOnClickListener { finish() } }
        btns.addView(btnFalar); btns.addView(btnChat); btns.addView(btnFechar)
        root.addView(titulo); root.addView(statusView); root.addView(replyView); root.addView(btns)
        setContentView(root)
        tts = TextToSpeech(this) { st -> if (st == TextToSpeech.SUCCESS) { tts?.language = Locale("pt", "BR"); ttsPronto = true } }
        acordarEIniciar()
    }

    private fun acordarEIniciar() {
        statusView?.text = "Acordando Kael..."
        Thread {
            if (!porta8000Ativa()) {
                dispararKaelShNoTermux()
                for (i in 1..20) { Thread.sleep(400); if (porta8000Ativa()) break }
            }
            mainHandler.post { verificarPermissaoEEscutar() }
        }.start()
    }

    private fun verificarPermissaoEEscutar() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 101)
            return
        }
        iniciarEscuta()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 101 && grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            iniciarEscuta()
        } else {
            statusView?.text = "Permissão de microfone negada."
        }
    }

    private fun porta8000Ativa(): Boolean = try {
        val c = URL("http://127.0.0.1:8000/health").openConnection() as HttpURLConnection
        c.connectTimeout = 800; c.readTimeout = 800; c.requestMethod = "GET"
        val ok = c.responseCode in 200..299; c.disconnect(); ok
    } catch (_: Exception) { false }

    private fun dispararKaelShNoTermux() = try {
        startService(Intent("com.termux.RUN_COMMAND").apply {
            setClassName("com.termux", "com.termux.app.RunCommandService")
            putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/home/.shortcuts/Kael.sh")
            putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
        })
    } catch (_: Exception) {}

    private fun iniciarEscuta() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) { statusView?.text = "Voz indisponível. Use Abrir Chat."; return }
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(p: Bundle?) { statusView?.text = "Ouvindo... fale agora" }
                override fun onBeginningOfSpeech() {} ; override fun onRmsChanged(v: Float) {} ; override fun onBufferReceived(b: ByteArray?) {}
                override fun onEndOfSpeech() { statusView?.text = "Enviando para o Kael..." }
                override fun onError(err: Int) { statusView?.text = "Não captei ($err). Toque em Falar." }
                override fun onResults(res: Bundle?) {
                    val txt = res?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim().orEmpty()
                    if (txt.isNotEmpty()) { statusView?.text = "Você: \"$txt\""; enviarParaKael(txt) } else { statusView?.text = "Sem fala. Toque em Falar." }
                }
                override fun onPartialResults(p: Bundle?) {} ; override fun onEvent(t: Int, p: Bundle?) {}
            })
        }
        recognizer?.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        })
    }

    private fun enviarParaKael(msg: String) {
        Thread {
            val resp = try {
                val c = (URL("http://127.0.0.1:8000/chat").openConnection() as HttpURLConnection).apply {
                    connectTimeout = 5000; readTimeout = 60000; requestMethod = "POST"; doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                }
                OutputStreamWriter(c.outputStream, "UTF-8").use { it.write(JSONObject().put("message", msg).toString()); it.flush() }
                val raw = BufferedReader(InputStreamReader(if (c.responseCode in 200..299) c.inputStream else c.errorStream, "UTF-8")).use { it.readText() }
                c.disconnect(); JSONObject(raw).optString("reply", raw).ifBlank { "Sem resposta do Kael." }
            } catch (e: Exception) { "Falha no Kael (127.0.0.1:8000): ${e.message}" }
            mainHandler.post {
                statusView?.text = "Kael respondeu:"; replyView?.text = resp
                if (ttsPronto) tts?.speak(resp.replace(Regex("[*#`]+"), "").take(500), TextToSpeech.QUEUE_FLUSH, null, "kael_reply")
            }
        }.start()
    }

    override fun onDestroy() { recognizer?.destroy(); tts?.shutdown(); super.onDestroy() }
}
