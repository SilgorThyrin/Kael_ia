package com.kael.assist

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.service.voice.VoiceInteractionSession
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.view.View
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

class KaelAssistSessionService : android.service.voice.VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession = KaelAssistSession(this)
}

class KaelAssistSession(context: Context) : VoiceInteractionSession(context) {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var statusView: TextView? = null
    private var replyView: TextView? = null
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsPronto = false

    override fun onCreateContentView(): View {
        val root = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            setBackgroundColor(Color.parseColor("#111827"))
        }
        val titulo = TextView(context).apply { text = "Kael Assist"; setTextColor(Color.WHITE); textSize = 20f }
        statusView = TextView(context).apply { text = "Preparando..."; setTextColor(Color.parseColor("#93C5FD")); textSize = 14f; setPadding(0, 12, 0, 12) }
        replyView = TextView(context).apply { text = ""; setTextColor(Color.parseColor("#E5E7EB")); textSize = 15f; setPadding(0, 8, 0, 20) }
        val btns = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        val btnFalar = Button(context).apply { text = "Falar"; setOnClickListener { iniciarEscuta() } }
        val btnChat = Button(context).apply { text = "Abrir Chat"; setOnClickListener { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:8000")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); hide() } }
        val btnFechar = Button(context).apply { text = "Fechar"; setOnClickListener { hide() } }
        btns.addView(btnFalar); btns.addView(btnChat); btns.addView(btnFechar)
        root.addView(titulo); root.addView(statusView); root.addView(replyView); root.addView(btns)
        tts = TextToSpeech(context) { st -> if (st == TextToSpeech.SUCCESS) { tts?.language = Locale("pt", "BR"); ttsPronto = true } }
        return root
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        statusView?.text = "Acordando Kael..."
        Thread {
            if (!porta8000Ativa()) {
                dispararKaelShNoTermux()
                for (i in 1..20) { Thread.sleep(400); if (porta8000Ativa()) break }
            }
            mainHandler.post { iniciarEscuta() }
        }.start()
    }

    private fun porta8000Ativa(): Boolean = try {
        val c = URL("http://127.0.0.1:8000/health").openConnection() as HttpURLConnection
        c.connectTimeout = 800; c.readTimeout = 800; c.requestMethod = "GET"
        val ok = c.responseCode in 200..299; c.disconnect(); ok
    } catch (_: Exception) { false }

    private fun dispararKaelShNoTermux() = try {
        context.startService(Intent("com.termux.RUN_COMMAND").apply {
            setClassName("com.termux", "com.termux.app.RunCommandService")
            putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/home/.shortcuts/Kael.sh")
            putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
        })
    } catch (_: Exception) {}

    private fun iniciarEscuta() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) { statusView?.text = "Voz indisponível. Use Abrir Chat."; return }
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
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
        startListeningIntent()
    }

    private fun startListeningIntent() {
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
