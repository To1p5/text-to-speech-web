from pydub import AudioSegment
from pydub.playback import play
import threading
import time
import wave
import pyaudio
import io
import numpy as np
from threading import Lock

class AudioPlayer:
    def __init__(self):
        self.audio_segment = None
        self.is_playing = False
        self.current_position = 0
        self.playback_thread = None
        self.speed = 1.0
        self.lock = Lock()
        self.should_stop = False
        self.paused = False
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self._position_callback = None
        
    def load_audio(self, wav_path):
        """Load audio from WAV file"""
        self.audio_segment = AudioSegment.from_wav(wav_path)
        self.duration = len(self.audio_segment) / 1000.0  # Duration in seconds
        
    def _get_audio_data(self, start_frame, num_frames, speed):
        """Get audio data for streaming with speed adjustment"""
        if not self.audio_segment:
            return None
            
        # Calculate the actual frames to read based on speed
        actual_frames = int(num_frames * speed)
        start_ms = (start_frame / 44100) * 1000
        end_ms = ((start_frame + actual_frames) / 44100) * 1000
        
        # Extract the segment
        segment = self.audio_segment[start_ms:end_ms]
        
        # Resample for speed adjustment
        if speed != 1.0:
            segment = segment._spawn(segment.raw_data, overrides={
                "frame_rate": int(segment.frame_rate * speed)
            }).set_frame_rate(44100)
        
        return np.frombuffer(segment.raw_data, dtype=np.int16)
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for PyAudio stream"""
        with self.lock:
            if self.paused or self.should_stop:
                return (None, pyaudio.paComplete)
            
            data = self._get_audio_data(self.current_position, frame_count, self.speed)
            if data is None:
                return (None, pyaudio.paComplete)
            
            self.current_position += frame_count
            
            # Update position for UI
            if self._position_callback:
                current_time = (self.current_position / 44100)
                self._position_callback(current_time, self.duration)
            
            return (data.tobytes(), pyaudio.paContinue)
    
    def play(self):
        """Start or resume playback"""
        with self.lock:
            if not self.audio_segment:
                return
                
            if self.paused:
                self.paused = False
                return
                
            if self.is_playing:
                return
                
            self.is_playing = True
            self.should_stop = False
            
            # Create and start audio stream
            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                output=True,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
    
    def pause(self):
        """Pause playback"""
        with self.lock:
            self.paused = True
            
    def stop(self):
        """Stop playback"""
        with self.lock:
            self.should_stop = True
            self.is_playing = False
            self.current_position = 0
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
    
    def set_speed(self, speed):
        """Set playback speed (0.5 to 4.0)"""
        with self.lock:
            self.speed = max(0.5, min(4.0, speed))
    
    def seek(self, position):
        """Seek to position in seconds"""
        with self.lock:
            self.current_position = int(position * 44100)
    
    def set_position_callback(self, callback):
        """Set callback for position updates"""
        self._position_callback = callback
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        if self.stream:
            self.stream.close()
        self.pyaudio.terminate() 