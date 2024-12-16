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

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

class TextToSpeech:
    def __init__(self):
        self.engine = None
        self.init_engine()
        self.is_playing = False
        self.current_text = ""
        self.current_title = ""
        self.current_type = ""
        self.progress = 0
        self.speed = 150
        self.current_sentence_index = 0
        self.sentences = []
        self.lock = Lock()
        self.should_stop = False

    def init_engine(self):
        """Initialize or reinitialize the TTS engine"""
        if self.engine:
            self.engine.stop()
        self.engine = pyttsx3.init()
        self.setup_voice()

    def setup_voice(self):
        """Configure the TTS engine settings"""
        self.engine.setProperty('rate', self.speed)
        self.engine.setProperty('volume', 0.9)
        voices = self.engine.getProperty('voices')
        if voices:
            self.engine.setProperty('voice', voices[1].id)

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

    def read_text(self, text, title, type_):
        """Read the given text aloud"""
        with self.lock:
            self.init_engine()
            self.prepare_text(text, title, type_)
            self.is_playing = True
            
            while self.current_sentence_index < len(self.sentences) and not self.should_stop:
                if not self.is_playing:
                    break
                    
                sentence = self.sentences[self.current_sentence_index]
                try:
                    self.engine.say(sentence)
                    self.engine.runAndWait()
                except RuntimeError:
                    self.init_engine()
                    continue
                    
                self.current_sentence_index += 1
                self.progress = int((self.current_sentence_index / len(self.sentences)) * 100)

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
            
        tts = gTTS(text=self.current_text, lang='en')
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp

    def get_state(self):
        """Get the current player state"""
        return {
            'is_playing': self.is_playing,
            'current_title': self.current_title,
            'current_type': self.current_type,
            'progress': self.progress,
            'speed': self.speed
        }

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
                min-height: 100vh;
                padding: 2rem;
                color: #ffffff;
            }

            .container {
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2rem;
                backdrop-filter: blur(10px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            }

            h1 {
                text-align: center;
                color: #ffffff;
                font-size: 2.5rem;
                margin-bottom: 2rem;
                font-weight: 600;
            }

            .section {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }

            .section:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                background: rgba(255, 255, 255, 0.08);
            }

            h2 {
                color: #ffffff;
                font-size: 1.5rem;
                margin-bottom: 1rem;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .icon {
                font-size: 1.5rem;
                color: #1db954;
            }

            input[type="file"],
            input[type="url"] {
                width: 100%;
                padding: 0.75rem;
                margin: 0.5rem 0;
                border: 2px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                font-size: 1rem;
                background: rgba(255, 255, 255, 0.05);
                color: #ffffff;
                transition: border-color 0.2s ease;
            }

            input[type="file"]:hover,
            input[type="url"]:hover {
                border-color: #1db954;
            }

            input[type="url"]::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }

            input[type="file"]::file-selector-button {
                background: #1db954;
                color: white;
                padding: 0.5rem 1rem;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                margin-right: 1rem;
                transition: background 0.2s ease;
            }

            input[type="file"]::file-selector-button:hover {
                background: #1ed760;
            }

            button {
                background: #1db954;
                color: white;
                padding: 0.75rem 1.5rem;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1rem;
                font-weight: 500;
                width: 100%;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
            }

            button:hover {
                background: #1ed760;
                transform: translateY(-1px);
            }

            button:active {
                transform: translateY(0);
            }

            .loading {
                display: none;
                margin: 1rem 0;
                text-align: center;
                color: #1db954;
            }

            .status {
                margin-top: 1rem;
                padding: 1rem;
                border-radius: 8px;
                display: none;
            }

            .status.success {
                background: rgba(29, 185, 84, 0.1);
                color: #1db954;
                display: block;
            }

            .status.error {
                background: rgba(255, 55, 55, 0.1);
                color: #ff3737;
                display: block;
            }

            .mini-player {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: rgba(24, 24, 24, 0.98);
                padding: 1rem;
                display: none;
                align-items: center;
                justify-content: space-between;
                backdrop-filter: blur(10px);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }

            .mini-player.active {
                display: flex;
            }

            .mini-player-info {
                display: flex;
                align-items: center;
                gap: 1rem;
            }

            .mini-player-controls {
                display: flex;
                align-items: center;
                gap: 1rem;
            }

            .mini-player button {
                width: auto;
                padding: 0.5rem;
                background: transparent;
            }

            .mini-player button:hover {
                background: rgba(255, 255, 255, 0.1);
                transform: none;
            }

            @media (max-width: 640px) {
                body {
                    padding: 1rem;
                }

                .container {
                    padding: 1rem;
                }

                h1 {
                    font-size: 2rem;
                }

                .mini-player {
                    flex-direction: column;
                    gap: 1rem;
                }
            }
        </style>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body>
        <div class="container">
            <h1>Text to Speech</h1>
            
            <div class="section">
                <h2><i class="fas fa-file-pdf icon"></i> Read PDF</h2>
                <input type="file" id="pdfFile" accept=".pdf">
                <button onclick="uploadFile('pdf')">
                    <i class="fas fa-play"></i>
                    Read PDF
                </button>
                <div id="pdfStatus" class="status"></div>
                <div id="pdfLoading" class="loading">
                    <i class="fas fa-spinner fa-spin"></i> Processing...
                </div>
            </div>

            <div class="section">
                <h2><i class="fas fa-book icon"></i> Read EPUB</h2>
                <input type="file" id="epubFile" accept=".epub">
                <button onclick="uploadFile('epub')">
                    <i class="fas fa-play"></i>
                    Read EPUB
                </button>
                <div id="epubStatus" class="status"></div>
                <div id="epubLoading" class="loading">
                    <i class="fas fa-spinner fa-spin"></i> Processing...
                </div>
            </div>

            <div class="section">
                <h2><i class="fas fa-globe icon"></i> Read Web Article</h2>
                <input type="url" id="urlInput" placeholder="Enter article URL">
                <button onclick="readURL()">
                    <i class="fas fa-play"></i>
                    Read URL
                </button>
                <div id="urlStatus" class="status"></div>
                <div id="urlLoading" class="loading">
                    <i class="fas fa-spinner fa-spin"></i> Processing...
                </div>
            </div>
        </div>

        <div id="miniPlayer" class="mini-player">
            <div class="mini-player-info">
                <i class="fas fa-music icon"></i>
                <div>
                    <h3 id="playerTitle">Not Playing</h3>
                    <p id="playerType"></p>
                </div>
            </div>
            <div class="mini-player-controls">
                <button onclick="togglePlayPause()" id="playPauseBtn">
                    <i class="fas fa-play"></i>
                </button>
                <button onclick="window.location.href='/player'">
                    <i class="fas fa-expand"></i>
                </button>
            </div>
        </div>

        <script>
            let isPlaying = false;

            function showLoading(type) {
                document.getElementById(type + 'Loading').style.display = 'block';
                document.getElementById(type + 'Status').style.display = 'none';
            }

            function hideLoading(type) {
                document.getElementById(type + 'Loading').style.display = 'none';
            }

            function showStatus(type, message, isError = false) {
                const statusElement = document.getElementById(type + 'Status');
                statusElement.textContent = message;
                statusElement.className = 'status ' + (isError ? 'error' : 'success');
                statusElement.style.display = 'block';
            }

            function updateMiniPlayer(title, type, playing) {
                const miniPlayer = document.getElementById('miniPlayer');
                const playerTitle = document.getElementById('playerTitle');
                const playerType = document.getElementById('playerType');
                const playPauseBtn = document.getElementById('playPauseBtn');

                miniPlayer.classList.add('active');
                playerTitle.textContent = title;
                playerType.textContent = type;
                playPauseBtn.innerHTML = playing ? 
                    '<i class="fas fa-pause"></i>' : 
                    '<i class="fas fa-play"></i>';
                isPlaying = playing;
            }

            function togglePlayPause() {
                fetch('/toggle_playback', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    updateMiniPlayer(data.current_title, data.current_type, data.is_playing);
                });
            }

            function uploadFile(type) {
                const fileInput = document.getElementById(type + 'File');
                const file = fileInput.files[0];
                if (!file) {
                    showStatus(type, 'Please select a file first', true);
                    return;
                }

                showLoading(type);
                const formData = new FormData();
                formData.append('file', file);

                fetch('/' + type, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    hideLoading(type);
                    if (data.status === 'success') {
                        showStatus(type, 'Started reading the file');
                        updateMiniPlayer(file.name, type.toUpperCase(), true);
                        window.location.href = '/player';
                    } else {
                        showStatus(type, 'Error: ' + data.message, true);
                    }
                })
                .catch(error => {
                    hideLoading(type);
                    showStatus(type, 'Error: ' + error.message, true);
                });
            }

            function readURL() {
                const url = document.getElementById('urlInput').value;
                if (!url) {
                    showStatus('url', 'Please enter a URL', true);
                    return;
                }

                showLoading('url');
                fetch('/url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({url: url})
                })
                .then(response => response.json())
                .then(data => {
                    hideLoading('url');
                    if (data.status === 'success') {
                        showStatus('url', 'Started reading the webpage');
                        updateMiniPlayer('Web Article', 'URL', true);
                        window.location.href = '/player';
                    } else {
                        showStatus('url', 'Error: ' + data.message, true);
                    }
                })
                .catch(error => {
                    hideLoading('url');
                    showStatus('url', 'Error: ' + error.message, true);
                });
            }

            // Check player state periodically
            setInterval(() => {
                fetch('/player_state')
                    .then(response => response.json())
                    .then(data => {
                        if (data.current_title) {
                            updateMiniPlayer(data.current_title, data.current_type, data.is_playing);
                        }
                    });
            }, 1000);
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