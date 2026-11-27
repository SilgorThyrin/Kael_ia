package com.kael.assist

import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession

class KaelAssistService : VoiceInteractionService() {
    override fun onReady() {
        super.onReady()
    }

    fun abrirSessaoKael() {
        try {
            showSession(
                Bundle(),
                VoiceInteractionSession.SHOW_WITH_ASSIST or VoiceInteractionSession.SHOW_SOURCE_ACTIVITY
            )
        } catch (_: Exception) {}
    }
}
