import pygame
import time
from pydub import AudioSegment
import os
import pyttsx3

def generate_test_audio():
    """Generate a test audio file"""
    engine = pyttsx3.init()
    
    # Create temp directory if it doesn't exist
    if not os.path.exists('temp_audio'):
        os.makedirs('temp_audio')
    
    # Generate test audio
    wav_path = 'temp_audio/test.wav'
    mp3_path = 'temp_audio/test.mp3'
    
    # Generate WAV file
    engine.save_to_file(
        "This is a test of continuous playback with speed changes. "
        "Let's see if we can change the speed without interrupting playback. "
        "This text should be long enough to test the functionality.",
        wav_path
    )
    engine.runAndWait()
    
    # Convert to MP3
    sound = AudioSegment.from_wav(wav_path)
    sound.export(mp3_path, format="mp3")
    
    # Cleanup WAV file
    os.remove(wav_path)
    
    return mp3_path

def test_continuous_playback():
    """Test continuous playback with speed changes"""
    pygame.mixer.init()
    
    # Generate test audio
    print("Generating test audio...")
    audio_path = generate_test_audio()
    
    # Start playback
    print("\nStarting playback...")
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()
    
    # Wait for a moment
    time.sleep(2)
    
    # Try to change speed without stopping
    print("\nTrying to change speed...")
    current_pos = pygame.mixer.music.get_pos() / 1000.0  # Convert to seconds
    
    # Method 1: Using pygame's built-in features
    try:
        pygame.mixer.music.set_pos(current_pos)
        print("Method 1: Speed change attempted")
    except Exception as e:
        print(f"Method 1 failed: {str(e)}")
    
    time.sleep(2)
    
    # Method 2: Quick reload
    try:
        pygame.mixer.music.pause()
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play(start=current_pos)
        print("Method 2: Speed change attempted")
    except Exception as e:
        print(f"Method 2 failed: {str(e)}")
    
    time.sleep(2)
    
    pygame.mixer.music.stop()
    pygame.mixer.quit()
    
    # Cleanup
    if os.path.exists(audio_path):
        os.remove(audio_path)

if __name__ == "__main__":
    print("Testing continuous playback with speed changes...")
    test_continuous_playback()
    print("\nTest complete!") 