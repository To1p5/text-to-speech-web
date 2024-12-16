import pyttsx3
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import requests
import os
import json
from flask import Flask, request, render_template_string, jsonify, session, send_file
from threading import Thread, Lock
import time
from gtts import gTTS
import io
from pydub import AudioSegment

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

class TextToSpeech:
    def __init__(self):
        # Initialize all attributes first
        self.speed = 150
        self.engine = None
        self.is_playing = False
        self.current_text = ""
        self.current_title = ""
        self.current_type = ""
        self.progress = 0
        self.current_sentence_index = 0
        self.sentences = []
        self.lock = Lock()
        self.should_stop = False
        self.temp_dir = os.path.join(os.getcwd(), 'temp_audio')
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        # Initialize engine after all attributes are set
        try:
            self.init_engine()
        except Exception as e:
            print(f"Error during initialization: {str(e)}")

    def init_engine(self):
        """Initialize or reinitialize the TTS engine"""
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
        """Configure the TTS engine settings"""
        try:
            if not hasattr(self, 'speed'):
                self.speed = 150
            self.engine.setProperty('rate', self.speed)
            self.engine.setProperty('volume', 0.9)
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
        except Exception as e:
            print(f"Error setting up voice: {str(e)}")

    def set_speed(self, speed):
        """Set the speech rate"""
        self.speed = speed
        self.engine.setProperty('rate', speed)

    def extract_from_pdf(self, pdf_path):
        """Extract text from a PDF file"""
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text

    def extract_from_epub(self, epub_path):
        """Extract text from an EPUB file"""
        book = epub.read_epub(epub_path)
        text = ""
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text += soup.get_text()
        return text

    def extract_from_url(self, url):
        """Extract text from a webpage"""
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text

    def prepare_text(self, text, title, type_):
        """Prepare text for reading"""
        self.current_text = text
        self.current_title = title
        self.current_type = type_
        self.sentences = [s.strip() for s in text.split('.') if s.strip()]
        self.current_sentence_index = 0
        self.progress = 0
        self.should_stop = False

    def generate_audio_file(self, text, output_path):
        """Generate audio file from text"""
        try:
            # Save as WAV first
            wav_path = output_path.replace('.mp3', '.wav')
            self.engine.save_to_file(text, wav_path)
            self.engine.runAndWait()

            # Convert to MP3
            sound = AudioSegment.from_wav(wav_path)
            sound.export(output_path, format="mp3")

            # Cleanup WAV file
            os.remove(wav_path)
            return True
        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            return False

    def read_text(self, text, title, type_):
        """Read the given text aloud"""
        with self.lock:
            self.init_engine()
            self.prepare_text(text, title, type_)
            self.is_playing = True
            
            # Generate unique filename for this session
            timestamp = int(time.time())
            mp3_path = os.path.join(self.temp_dir, f'speech_{timestamp}.mp3')
            
            # Generate the audio file
            if self.generate_audio_file(text, mp3_path):
                try:
                    # Play the generated MP3 file
                    sound = AudioSegment.from_mp3(mp3_path)
                    chunk_length = 500  # 500ms chunks
                    chunks = len(sound) // chunk_length
                    
                    for i in range(chunks):
                        if not self.is_playing or self.should_stop:
                            break
                            
                        chunk = sound[i*chunk_length:(i+1)*chunk_length]
                        chunk_path = os.path.join(self.temp_dir, f'chunk_{timestamp}_{i}.mp3')
                        chunk.export(chunk_path, format="mp3")
                        
                        # Update progress
                        self.progress = int((i / chunks) * 100)
                        
                        # Cleanup chunk
                        os.remove(chunk_path)
                        
                except Exception as e:
                    print(f"Error during playback: {str(e)}")
                finally:
                    # Cleanup
                    if os.path.exists(mp3_path):
                        os.remove(mp3_path)
            
            self.is_playing = False
            if self.should_stop:
                self.progress = 0
                self.current_sentence_index = 0
            else:
                self.progress = 100

    def stop(self):
        """Stop the reading completely"""
        self.should_stop = True
        self.is_playing = False
        self.init_engine()

    def pause(self):
        """Pause the reading"""
        self.is_playing = False
        self.init_engine()

    def resume(self):
        """Resume reading from where it was paused"""
        if not self.current_text:
            return
            
        self.is_playing = True
        remaining_text = '. '.join(self.sentences[self.current_sentence_index:])
        thread = Thread(target=self.read_text, args=(remaining_text, self.current_title, self.current_type))
        thread.daemon = True
        thread.start()

    def export_to_mp3(self):
        """Export current text to MP3"""
        if not self.current_text:
            return None
            
        # Generate unique filename
        timestamp = int(time.time())
        mp3_path = os.path.join(self.temp_dir, f'export_{timestamp}.mp3')
        
        if self.generate_audio_file(self.current_text, mp3_path):
            with open(mp3_path, 'rb') as f:
                data = f.read()
            os.remove(mp3_path)
            return io.BytesIO(data)
        return None

    def get_state(self):
        """Get the current player state"""
        return {
            'is_playing': self.is_playing,
            'current_title': self.current_title,
            'current_type': self.current_type,
            'progress': self.progress,
            'speed': self.speed
        }

    def __del__(self):
        """Cleanup temporary files on object destruction"""
        try:
            if os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                os.rmdir(self.temp_dir)
        except:
            pass

# Create a global TTS instance
tts = TextToSpeech()

@app.route('/player_state')
def player_state():
    return jsonify(tts.get_state())

@app.route('/toggle_playback', methods=['POST'])
def toggle_playback():
    if tts.is_playing:
        tts.pause()
    else:
        tts.resume()
    return jsonify(tts.get_state())

@app.route('/stop_playback', methods=['POST'])
def stop_playback():
    tts.stop()
    return jsonify(tts.get_state())

@app.route('/set_speed', methods=['POST'])
def set_speed():
    data = request.get_json()
    if data and 'speed' in data:
        tts.set_speed(int(data['speed']))
    return jsonify(tts.get_state())

@app.route('/export_mp3')
def export_mp3():
    if not tts.current_text:
        return jsonify({'status': 'error', 'message': 'No text to export'})
    
    try:
        mp3_data = tts.export_to_mp3()
        return send_file(
            mp3_data,
            mimetype='audio/mp3',
            as_attachment=True,
            download_name=f"{tts.current_title.replace(' ', '_')}.mp3"
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

def start_reading_thread(text, title, type_):
    tts.stop()  # Stop any existing playback
    thread = Thread(target=tts.read_text, args=(text, title, type_))
    thread.daemon = True
    thread.start()

@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Text to Speech App</title>
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
                margin-bottom: 1rem;
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

            .controls {
                display: flex;
                gap: 1rem;
                margin-top: 2rem;
                justify-content: center;
            }

            .speed-control {
                display: flex;
                align-items: center;
                gap: 1rem;
                margin-top: 1rem;
            }

            input[type="range"] {
                flex: 1;
            }

            .progress-bar {
                width: 100%;
                height: 4px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
                margin: 1rem 0;
                overflow: hidden;
            }

            .progress {
                width: 0%;
                height: 100%;
                background: #2ecc71;
                transition: width 0.3s ease;
            }

            .status {
                text-align: center;
                margin-top: 1rem;
                color: rgba(255, 255, 255, 0.7);
            }

            #urlInput {
                width: 100%;
                padding: 0.5rem;
                margin-bottom: 1rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Text to Speech</h1>
            
            <div class="upload-section">
                <h2>Upload PDF</h2>
                <div class="file-upload">
                    <input type="file" id="pdfFile" accept=".pdf">
                    <button onclick="uploadPDF()">Upload & Read PDF</button>
                </div>
            </div>

            <div class="upload-section">
                <h2>Upload EPUB</h2>
                <div class="file-upload">
                    <input type="file" id="epubFile" accept=".epub">
                    <button onclick="uploadEPUB()">Upload & Read EPUB</button>
                </div>
            </div>

            <div class="upload-section">
                <h2>Read from URL</h2>
                <input type="url" id="urlInput" placeholder="Enter URL">
                <button onclick="readURL()">Read from URL</button>
            </div>

            <div class="progress-bar">
                <div class="progress" id="progress"></div>
            </div>

            <div class="status" id="status">Ready</div>

            <div class="controls">
                <button onclick="togglePlayback()" id="playPauseBtn">Play</button>
                <button onclick="stopPlayback()">Stop</button>
                <button onclick="exportMP3()">Export MP3</button>
            </div>

            <div class="speed-control">
                <span>Speed:</span>
                <input type="range" id="speedControl" min="50" max="300" value="150" oninput="updateSpeed(this.value)">
                <span id="speedValue">150</span>
            </div>
        </div>

        <script>
            let isPlaying = false;

            function updatePlayerState() {
                fetch('/player_state')
                    .then(response => response.json())
                    .then(data => {
                        isPlaying = data.is_playing;
                        document.getElementById('playPauseBtn').textContent = isPlaying ? 'Pause' : 'Play';
                        document.getElementById('progress').style.width = data.progress + '%';
                        document.getElementById('status').textContent = data.current_title 
                            ? `Playing: ${data.current_title} (${data.current_type})`
                            : 'Ready';
                        document.getElementById('speedControl').value = data.speed;
                        document.getElementById('speedValue').textContent = data.speed;
                    });
            }

            function uploadPDF() {
                const fileInput = document.getElementById('pdfFile');
                const file = fileInput.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('file', file);

                fetch('/pdf', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'error') {
                        alert(data.message);
                    }
                    updatePlayerState();
                });
            }

            function uploadEPUB() {
                const fileInput = document.getElementById('epubFile');
                const file = fileInput.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('file', file);

                fetch('/epub', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'error') {
                        alert(data.message);
                    }
                    updatePlayerState();
                });
            }

            function readURL() {
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
                    if (data.status === 'error') {
                        alert(data.message);
                    }
                    updatePlayerState();
                });
            }

            function togglePlayback() {
                fetch('/toggle_playback', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    updatePlayerState();
                });
            }

            function stopPlayback() {
                fetch('/stop_playback', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    updatePlayerState();
                });
            }

            function updateSpeed(speed) {
                document.getElementById('speedValue').textContent = speed;
                fetch('/set_speed', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({speed: parseInt(speed)})
                })
                .then(response => response.json())
                .then(data => {
                    updatePlayerState();
                });
            }

            function exportMP3() {
                window.location.href = '/export_mp3';
            }

            // Update player state every second
            setInterval(updatePlayerState, 1000);
            // Initial state update
            updatePlayerState();
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/player')
def player():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Now Playing - Text to Speech</title>
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
                min-height: 100vh;
                color: #ffffff;
                display: flex;
                flex-direction: column;
            }

            .top-bar {
                padding: 1rem 2rem;
                background: rgba(0, 0, 0, 0.3);
                display: flex;
                align-items: center;
                gap: 1rem;
            }

            .back-button {
                background: transparent;
                border: none;
                color: #ffffff;
                cursor: pointer;
                font-size: 1.5rem;
                padding: 0.5rem;
                border-radius: 50%;
                transition: background-color 0.2s;
            }

            .back-button:hover {
                background: rgba(255, 255, 255, 0.1);
            }

            .player-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 2rem;
                gap: 2rem;
            }

            .now-playing {
                text-align: center;
            }

            .now-playing h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
            }

            .now-playing p {
                color: #1db954;
                font-size: 1.2rem;
            }

            .player-image {
                width: 300px;
                height: 300px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 4rem;
                color: #1db954;
            }

            .progress-container {
                width: 100%;
                max-width: 500px;
            }

            .progress-bar {
                width: 100%;
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                overflow: hidden;
                margin-bottom: 0.5rem;
            }

            .progress {
                height: 100%;
                background: #1db954;
                width: 0%;
                transition: width 0.5s ease;
            }

            .time-labels {
                display: flex;
                justify-content: space-between;
                color: rgba(255, 255, 255, 0.7);
                font-size: 0.9rem;
            }

            .controls {
                display: flex;
                align-items: center;
                gap: 1rem;
            }

            .control-button {
                background: transparent;
                border: none;
                color: #ffffff;
                cursor: pointer;
                font-size: 1.5rem;
                padding: 1rem;
                border-radius: 50%;
                transition: all 0.2s ease;
            }

            .control-button:hover {
                background: rgba(255, 255, 255, 0.1);
                transform: scale(1.1);
            }

            .control-button.play-pause {
                background: #1db954;
                font-size: 2rem;
                padding: 1.5rem;
            }

            .control-button.play-pause:hover {
                background: #1ed760;
                transform: scale(1.1);
            }

            .speed-control {
                display: flex;
                align-items: center;
                gap: 1rem;
                margin: 1rem 0;
            }

            .speed-control label {
                color: rgba(255, 255, 255, 0.7);
            }

            .speed-control input[type="range"] {
                width: 200px;
                height: 4px;
                -webkit-appearance: none;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
                outline: none;
            }

            .speed-control input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 16px;
                height: 16px;
                background: #1db954;
                border-radius: 50%;
                cursor: pointer;
                transition: background 0.2s;
            }

            .speed-control input[type="range"]::-webkit-slider-thumb:hover {
                background: #1ed760;
            }

            .speed-value {
                min-width: 60px;
                text-align: center;
                color: #1db954;
            }

            .action-buttons {
                display: flex;
                gap: 1rem;
                margin-top: 1rem;
            }

            .action-button {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0.75rem 1.5rem;
                cursor: pointer;
                font-size: 1rem;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .action-button:hover {
                background: rgba(255, 255, 255, 0.2);
            }

            .action-button.stop {
                background: rgba(255, 55, 55, 0.2);
            }

            .action-button.stop:hover {
                background: rgba(255, 55, 55, 0.3);
            }

            .action-button.download {
                background: rgba(29, 185, 84, 0.2);
            }

            .action-button.download:hover {
                background: rgba(29, 185, 84, 0.3);
            }

            @media (max-width: 640px) {
                .player-image {
                    width: 200px;
                    height: 200px;
                    font-size: 3rem;
                }

                .now-playing h1 {
                    font-size: 1.8rem;
                }

                .controls {
                    gap: 0.5rem;
                }

                .control-button {
                    font-size: 1.2rem;
                    padding: 0.8rem;
                }

                .control-button.play-pause {
                    font-size: 1.5rem;
                    padding: 1.2rem;
                }
            }
        </style>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body>
        <div class="top-bar">
            <button class="back-button" onclick="window.location.href='/'">
                <i class="fas fa-chevron-left"></i>
            </button>
            <h2>Now Playing</h2>
        </div>

        <div class="player-container">
            <div class="now-playing">
                <h1 id="playerTitle">Not Playing</h1>
                <p id="playerType"></p>
            </div>

            <div class="player-image">
                <i class="fas fa-book-reader"></i>
            </div>

            <div class="speed-control">
                <label>Speed:</label>
                <input type="range" id="speedControl" min="50" max="300" value="150" step="25">
                <span id="speedValue" class="speed-value">1.5x</span>
            </div>

            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress" id="progressBar"></div>
                </div>
                <div class="time-labels">
                    <span id="currentProgress">0%</span>
                    <span>100%</span>
                </div>
            </div>

            <div class="controls">
                <button class="control-button" onclick="setSpeed(Math.max(50, Number(speedControl.value) - 25))">
                    <i class="fas fa-minus"></i>
                </button>
                <button class="control-button play-pause" onclick="togglePlayPause()" id="playPauseBtn">
                    <i class="fas fa-play"></i>
                </button>
                <button class="control-button" onclick="setSpeed(Math.min(300, Number(speedControl.value) + 25))">
                    <i class="fas fa-plus"></i>
                </button>
            </div>

            <div class="action-buttons">
                <button class="action-button stop" onclick="stopPlayback()">
                    <i class="fas fa-stop"></i>
                    Stop
                </button>
                <button class="action-button download" onclick="downloadMP3()">
                    <i class="fas fa-download"></i>
                    Download MP3
                </button>
            </div>
        </div>

        <script>
            const speedControl = document.getElementById('speedControl');
            const speedValue = document.getElementById('speedValue');

            function updateSpeedDisplay(speed) {
                speedValue.textContent = (speed / 100).toFixed(1) + 'x';
            }

            function setSpeed(speed) {
                speedControl.value = speed;
                updateSpeedDisplay(speed);
                fetch('/set_speed', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ speed: speed })
                });
            }

            speedControl.addEventListener('input', (e) => {
                updateSpeedDisplay(e.target.value);
            });

            speedControl.addEventListener('change', (e) => {
                setSpeed(Number(e.target.value));
            });

            function updatePlayerState(data) {
                document.getElementById('playerTitle').textContent = data.current_title || 'Not Playing';
                document.getElementById('playerType').textContent = data.current_type || '';
                document.getElementById('playPauseBtn').innerHTML = data.is_playing ? 
                    '<i class="fas fa-pause"></i>' : 
                    '<i class="fas fa-play"></i>';
                document.getElementById('progressBar').style.width = data.progress + '%';
                document.getElementById('currentProgress').textContent = data.progress + '%';
                
                if (data.speed && speedControl.value != data.speed) {
                    speedControl.value = data.speed;
                    updateSpeedDisplay(data.speed);
                }
            }

            function togglePlayPause() {
                fetch('/toggle_playback', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(updatePlayerState);
            }

            function stopPlayback() {
                fetch('/stop_playback', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(updatePlayerState);
            }

            function downloadMP3() {
                window.location.href = '/export_mp3';
            }

            // Update player state every second
            setInterval(() => {
                fetch('/player_state')
                    .then(response => response.json())
                    .then(updatePlayerState);
            }, 1000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/pdf', methods=['POST'])
def handle_pdf():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})

    if not file.filename.endswith('.pdf'):
        return jsonify({'status': 'error', 'message': 'Invalid file type'})

    temp_path = os.path.join(os.getcwd(), 'temp.pdf')
    file.save(temp_path)

    try:
        text = tts.extract_from_pdf(temp_path)
        start_reading_thread(text, file.filename, 'PDF')
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/epub', methods=['POST'])
def handle_epub():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})

    if not file.filename.endswith('.epub'):
        return jsonify({'status': 'error', 'message': 'Invalid file type'})

    temp_path = os.path.join(os.getcwd(), 'temp.epub')
    file.save(temp_path)

    try:
        text = tts.extract_from_epub(temp_path)
        start_reading_thread(text, file.filename, 'EPUB')
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/url', methods=['POST'])
def handle_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'No URL provided'})

    try:
        text = tts.extract_from_url(data['url'])
        start_reading_thread(text, 'Web Article', 'URL')
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True) 