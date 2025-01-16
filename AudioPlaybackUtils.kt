package voice.playback.utils

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * A utility class that provides core audio playback functionality using ExoPlayer
 */
class AudioPlaybackUtils(private val context: Context) {
    private var player: ExoPlayer? = null
    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying

    init {
        initializePlayer()
    }

    private fun initializePlayer() {
        player = ExoPlayer.Builder(context).build()
        player?.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _isPlaying.value = isPlaying
            }
        })
    }

    fun setAudioSource(uri: String) {
        player?.let { exoPlayer ->
            val mediaItem = MediaItem.fromUri(uri)
            exoPlayer.setMediaItem(mediaItem)
            exoPlayer.prepare()
        }
    }

    fun play() {
        player?.play()
    }

    fun pause() {
        player?.pause()
    }

    fun playPause() {
        player?.let { 
            if (it.isPlaying) {
                pause()
            } else {
                play()
            }
        }
    }

    fun setSpeed(speed: Float) {
        player?.setPlaybackSpeed(speed)
    }

    fun seekTo(position: Long) {
        player?.seekTo(position)
    }

    fun fastForward(milliseconds: Long = 30000) {
        player?.let {
            val newPosition = (it.currentPosition + milliseconds).coerceAtMost(it.duration)
            it.seekTo(newPosition)
        }
    }

    fun rewind(milliseconds: Long = 10000) {
        player?.let {
            val newPosition = (it.currentPosition - milliseconds).coerceAtLeast(0)
            it.seekTo(newPosition)
        }
    }

    fun setVolume(volume: Float) {
        require(volume in 0f..1f) { "Volume must be between 0 and 1" }
        player?.volume = volume
    }

    fun release() {
        player?.release()
        player = null
    }
} 