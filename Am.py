import pyttsx3
import PyPDF2
from pydub import AudioSegment
import os

def create_audio(file_path, output_name):
    # Initialize speaker
    speaker = pyttsx3.init()
    speaker.setProperty('rate', 150)  # Speed percent
    speaker.setProperty('volume', 0.9)  # Volume

    def process_text(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
        return text

    # Process the text file
    text = process_text(file_path)

    # Save speech to audio file (WAV format)
    output_path = 'output.wav'
    speaker.save_to_file(text, output_path)
    speaker.runAndWait()

    # Convert WAV to MP3 using pydub (requires ffmpeg)
    sound = AudioSegment.from_wav(output_path)
    mp3_path = f"{output_name}.mp3"
    sound.export(mp3_path, format="mp3")

    # Cleanup temporary WAV file
    os.remove(output_path)

    print(f"Audiobook creation complete: {mp3_path}")
    return mp3_path

# This function can now be imported and used in other scripts
