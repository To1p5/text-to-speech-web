import pyttsx3
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import requests
import os
import json
from flask import Flask, request, render_template_string, jsonify, session, send_file, redirect, url_for
from threading import Thread, Lock
import time
from gtts import gTTS
import io
from pydub import AudioSegment
from pydub.playback import play
import math
import pygame

# Initialize pygame mixer
pygame.mixer.init()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

class TextToSpeech:
    def __init__(self):
        self.speed = 150
        self.engine = None
        self.is_playing = False
        self.current_text = ""
        self.current_title = ""
        self.current_type = ""
        self.progress = 0
        self.duration = 0
        self.current_position = 0
        self.lock = Lock()
        self.should_stop = False
        self.temp_dir = os.path.join(os.getcwd(), 'temp_audio')
        self.current_audio_path = None
        self.playback_thread = None
        
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        try:
            self.init_engine()
        except Exception as e:
            print(f"Error during initialization: {str(e)}")

    def init_engine(self):
        try:
            if self.engine:
                try:
                    self.engine.stop()
                except:
                    pass
            self.engine = pyttsx3.init()
            self.setup_voice()
        except Exception as e:
            print(f"Error initializing engine: {str(e)}")

    def setup_voice(self):
        try:
            self.engine.setProperty('rate', self.speed)
            self.engine.setProperty('volume', 0.9)
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
        except Exception as e:
            print(f"Error setting up voice: {str(e)}")

    def extract_from_url(self, url):
        """Extract article content from a webpage"""
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find article title
        title = ""
        title_candidates = [
            soup.find('h1', {'class': ['article-title', 'entry-title', 'post-title']}),
            soup.find('meta', {'property': 'og:title'}),
            soup.find('title'),
            soup.find('h1')
        ]
        for candidate in title_candidates:
            if candidate:
                title = candidate.get('content', candidate.text)
                break
        
        # Try to find article content
        article_content = ""
        content_candidates = [
            soup.find('article'),
            soup.find('div', {'class': ['article-content', 'entry-content', 'post-content']}),
            soup.find('main'),
        ]
        
        for candidate in content_candidates:
            if candidate:
                # Remove unwanted elements
                for unwanted in candidate.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
                    unwanted.decompose()
                
                # Get paragraphs
                paragraphs = candidate.find_all('p')
                article_content = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
                break
        
        if not article_content and not title:
            raise ValueError("Could not extract article content from the webpage")
            
        return article_content, title

    def generate_audio_file(self, text, title, type_):
        """Generate audio file and return its duration"""
        try:
            # Generate unique filename
            timestamp = int(time.time())
            mp3_path = os.path.join(self.temp_dir, f'audio_{timestamp}.mp3')
            
            # Save as WAV first
            wav_path = mp3_path.replace('.mp3', '.wav')
            self.engine.save_to_file(text, wav_path)
            self.engine.runAndWait()

            # Convert to MP3
            sound = AudioSegment.from_wav(wav_path)
            sound.export(mp3_path, format="mp3")

            # Cleanup WAV file
            os.remove(wav_path)
            
            # Store current audio info
            self.current_audio_path = mp3_path
            self.current_text = text
            self.current_title = title
            self.current_type = type_
            self.duration = len(sound) / 1000  # Convert to seconds
            
            return True
        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            return False

    def get_state(self):
        """Get the current player state"""
        return {
            'is_playing': self.is_playing,
            'current_title': self.current_title,
            'current_type': self.current_type,
            'progress': self.progress,
            'speed': self.speed,
            'duration': self.duration,
            'current_position': self.current_position,
            'duration_formatted': self.format_duration(self.duration),
            'position_formatted': self.format_duration(self.current_position)
        }

    def format_duration(self, seconds):
        """Format duration in seconds to HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def cleanup(self):
        """Clean up temporary files"""
        try:
            if os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
        except:
            pass

    def play_audio(self):
        """Background thread for audio playback"""
        try:
            # Load and play from current position
            pygame.mixer.music.load(self.current_audio_path)
            pygame.mixer.music.play(start=self.current_position)
            
            # Get the total length of the audio
            sound = AudioSegment.from_mp3(self.current_audio_path)
            total_length = len(sound) / 1000.0  # Convert to seconds
            
            # Monitor playback progress
            while pygame.mixer.music.get_busy() and self.is_playing and not self.should_stop:
                # Calculate current position
                if self.current_position >= total_length:
                    self.current_position = 0
                else:
                    self.current_position += 0.1
                
                self.progress = int((self.current_position / total_length) * 100)
                time.sleep(0.1)
            
        except Exception as e:
            print(f"Error during playback: {str(e)}")
        finally:
            if self.should_stop:
                pygame.mixer.music.stop()
                self.current_position = 0
                self.progress = 0
            self.is_playing = False

    def toggle_playback(self):
        """Toggle between play and pause"""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """Start or resume playback"""
        if not self.current_audio_path or not os.path.exists(self.current_audio_path):
            return
        
        self.is_playing = True
        self.should_stop = False
        
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.unpause()
        else:
            if self.playback_thread and self.playback_thread.is_alive():
                return
                
            self.playback_thread = Thread(target=self.play_audio)
            self.playback_thread.daemon = True
            self.playback_thread.start()

    def pause(self):
        """Pause playback"""
        try:
            self.is_playing = False
            pygame.mixer.music.pause()
        except Exception as e:
            print(f"Error pausing: {str(e)}")

    def stop(self):
        """Stop playback completely"""
        self.should_stop = True
        self.is_playing = False
        pygame.mixer.music.stop()
        self.current_position = 0
        self.progress = 0

    def seek(self, position):
        """Seek to a specific position in the audio"""
        try:
            if not self.current_audio_path or not os.path.exists(self.current_audio_path):
                return
            
            # Convert position to seconds if it's a percentage
            if 0 <= position <= 100:
                position = (position / 100) * self.duration
            
            # Store the position
            self.current_position = position
            self.progress = int((position / self.duration) * 100)
            
            # Stop current playback
            pygame.mixer.music.stop()
            
            # Start from new position
            pygame.mixer.music.load(self.current_audio_path)
            pygame.mixer.music.play(start=position)
            
            # Update state
            self.is_playing = True
            self.should_stop = False
            
        except Exception as e:
            print(f"Error seeking: {str(e)}")

    def set_speed(self, speed):
        """Set the speech rate"""
        try:
            old_speed = self.speed
            self.speed = speed
            
            # Store current state
            current_pos = self.current_position
            was_playing = self.is_playing
            
            # Stop current playback
            if was_playing:
                self.pause()
            
            # Regenerate audio at new speed
            if self.current_text:
                # Save current audio path
                old_path = self.current_audio_path
                
                # Generate new audio
                if self.generate_audio_file(self.current_text, self.current_title, self.current_type):
                    # Remove old audio file
                    if old_path and os.path.exists(old_path):
                        os.remove(old_path)
                    
                    # Resume from previous position if was playing
                    if was_playing:
                        self.seek(current_pos)
                        self.play()
                else:
                    # If generation failed, restore old speed
                    self.speed = old_speed
                    
        except Exception as e:
            print(f"Error setting speed: {str(e)}")
            self.speed = old_speed

# Create a global TTS instance
tts = TextToSpeech()

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Text to Speech Converter</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Inter', sans-serif;
            }

            body {
                background: linear-gradient(135deg, #1e2024 0%, #17181c 100%);
                color: #ffffff;
                min-height: 100vh;
                padding: 2rem;
            }

            .container {
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 1rem;
                backdrop-filter: blur(10px);
            }

            h1 {
                text-align: center;
                margin-bottom: 2rem;
                color: #fff;
                font-size: 2.5rem;
            }

            .upload-section {
                margin-bottom: 2rem;
                padding: 2rem;
                border-radius: 0.5rem;
                background: rgba(255, 255, 255, 0.1);
            }

            .upload-section h2 {
                margin-bottom: 1rem;
                font-size: 1.5rem;
            }

            .file-upload {
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }

            input[type="file"], input[type="url"] {
                padding: 0.5rem;
                border: none;
                border-radius: 0.25rem;
                background: rgba(255, 255, 255, 0.2);
                color: #fff;
            }

            button {
                padding: 0.75rem 1.5rem;
                border: none;
                border-radius: 0.25rem;
                background: #2ecc71;
                color: white;
                cursor: pointer;
                font-weight: 500;
                transition: background 0.3s ease;
            }

            button:hover {
                background: #27ae60;
            }

            #urlInput, #urlInput2 {
                width: 100%;
                margin-bottom: 1rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Text to Speech Converter</h1>
            
            <div class="upload-section">
                <h2>Upload PDF</h2>
                <div class="file-upload">
                    <input type="file" id="pdfFile" accept=".pdf">
                    <button onclick="uploadFile('pdf')">Convert PDF to Audio</button>
                </div>
            </div>

            <div class="upload-section">
                <h2>Upload EPUB</h2>
                <div class="file-upload">
                    <input type="file" id="epubFile" accept=".epub">
                    <button onclick="uploadFile('epub')">Convert EPUB to Audio</button>
                </div>
            </div>

            <div class="upload-section">
                <h2>Convert Article from URL</h2>
                <input type="url" id="urlInput" placeholder="Enter article URL">
                <button onclick="convertURL()">Convert Article to Audio</button>
            </div>

            <div class="upload-section">
                <h2>Convert Article from URL (Alternative)</h2>
                <input type="url" id="urlInput2" placeholder="Enter article URL">
                <button onclick="convertURL2()">Convert Article to Audio</button>
            </div>
        </div>

        <script>
            function uploadFile(type) {
                const fileInput = document.getElementById(type + 'File');
                const file = fileInput.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('file', file);

                fetch('/' + type, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        window.location.href = '/player';
                    } else {
                        alert(data.message);
                    }
                });
            }

            function convertURL() {
                const url = document.getElementById('urlInput').value;
                if (!url) return;

                fetch('/url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({url: url})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        window.location.href = '/player';
                    } else {
                        alert(data.message);
                    }
                });
            }

            function convertURL2() {
                const url = document.getElementById('urlInput2').value;
                if (!url) return;

                fetch('/url2', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({url: url})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        window.location.href = '/player';
                    } else {
                        alert(data.message);
                    }
                });
            }
        </script>
    </body>
    </html>
    """)

@app.route('/url', methods=['POST'])
def handle_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'No URL provided'})

    try:
        text, title = tts.extract_from_url(data['url'])
        if tts.generate_audio_file(text, title, 'Web Article'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/url2', methods=['POST'])
def handle_url2():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'No URL provided'})

    try:
        text, title = tts.extract_from_url(data['url'])
        if tts.generate_audio_file(text, title, 'Web Article'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/player_state')
def player_state():
    return jsonify(tts.get_state())

@app.route('/set_speed', methods=['POST'])
def set_speed():
    data = request.get_json()
    if data and 'speed' in data:
        tts.set_speed(int(data['speed']))
    return jsonify(tts.get_state())

@app.route('/seek', methods=['POST'])
def seek():
    """Handle seeking in the audio"""
    data = request.get_json()
    if data and 'position' in data:
        tts.seek(float(data['position']))
    return jsonify(tts.get_state())

@app.route('/toggle_playback', methods=['POST'])
def toggle_playback():
    """Handle play/pause toggle"""
    tts.toggle_playback()
    return jsonify(tts.get_state())

if __name__ == '__main__':
    app.run(debug=True) 