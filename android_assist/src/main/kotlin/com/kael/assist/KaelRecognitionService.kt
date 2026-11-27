package com.kael.assist

import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognitionService
import android.speech.SpeechRecognizer

class KaelRecognitionService : RecognitionService() {
    private var delegate: SpeechRecognizer? = null

    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) {
        delegate?.destroy()
        delegate = SpeechRecognizer.createSpeechRecognizer(this).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(p: Bundle?) { try { listener?.readyForSpeech(p ?: Bundle()) } catch (_: Exception) {} }
                override fun onBeginningOfSpeech() { try { listener?.beginningOfSpeech() } catch (_: Exception) {} }
                override fun onRmsChanged(v: Float) { try { listener?.rmsChanged(v) } catch (_: Exception) {} }
                override fun onBufferReceived(b: ByteArray?) { try { listener?.bufferReceived(b ?: ByteArray(0)) } catch (_: Exception) {} }
                override fun onEndOfSpeech() { try { listener?.endOfSpeech() } catch (_: Exception) {} }
                override fun onError(err: Int) { try { listener?.error(err) } catch (_: Exception) {} }
                override fun onResults(res: Bundle?) { try { listener?.results(res ?: Bundle()) } catch (_: Exception) {} }
                override fun onPartialResults(p: Bundle?) { try { listener?.partialResults(p ?: Bundle()) } catch (_: Exception) {} }
                override fun onEvent(t: Int, p: Bundle?) {}
            })
        }
        if (recognizerIntent != null) delegate?.startListening(recognizerIntent)
    }

    override fun onCancel(listener: Callback?) { delegate?.cancel() }
    override fun onStopListening(listener: Callback?) { delegate?.stopListening() }
    override fun onDestroy() { delegate?.destroy(); super.onDestroy() }
}
