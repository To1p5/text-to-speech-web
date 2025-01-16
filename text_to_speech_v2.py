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

    def extract_from_url_fee(self, url):
        """Extract article title, subtitle, and main content from a Fee.org webpage"""
        # Add headers to mimic a regular browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title (H1)
        title = ""
        title_element = soup.find('h1')
        if title_element:
            title = title_element.get_text().strip()
        
        # Extract subtitle (H2)
        subtitle = ""
        subtitle_element = soup.find('h2')
        if subtitle_element:
            subtitle = subtitle_element.get_text().strip()
        
        # Extract article content
        article_content = ""
        content_wrapper = soup.find('div', {'class': 'article-content-wrapper'})
        if content_wrapper:
            paragraphs = content_wrapper.find_all('p')
            article_content = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
        
        if not article_content and not title:
            raise ValueError("Could not extract article content from the webpage")
        
        # Combine the parts with appropriate spacing
        full_text = f"{title}\n\n{subtitle}\n\n{article_content}"
        return full_text, title

    # ... (rest of the TextToSpeech class methods) ...

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
                <h2>Convert Article from URL2 (Fee.org)</h2>
                <input type="url" id="urlInput2" placeholder="Enter Fee.org article URL">
                <button onclick="convertURL2()">Convert Fee.org Article to Audio</button>
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
                
                if (!url.includes('fee.org')) {
                    alert('Please enter a valid Fee.org article URL');
                    return;
                }

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

@app.route('/url2', methods=['POST'])
def handle_url2():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'No URL provided'})

    try:
        text, title = tts.extract_from_url_fee(data['url'])
        if tts.generate_audio_file(text, title, 'Fee.org Article'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ... (rest of the routes) ...

if __name__ == '__main__':
    app.run(debug=True) 