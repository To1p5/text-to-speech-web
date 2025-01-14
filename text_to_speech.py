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
from audio_player import AudioPlayer

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

class TextToSpeech:
    def __init__(self):
        self.engine = None
        self.current_text = ""
        self.current_title = ""
        self.current_type = ""
        self.current_audio_path = None
        self.temp_dir = os.path.join(os.getcwd(), 'temp_audio')
        
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
            self.engine.setProperty('rate', 150)  # Default speed
            self.engine.setProperty('volume', 0.9)
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
        except Exception as e:
            print(f"Error setting up voice: {str(e)}")

    def generate_audio_file(self, text, title, type_):
        """Generate audio file and return its duration"""
        try:
            # Generate unique filename
            timestamp = int(time.time())
            wav_path = os.path.join(self.temp_dir, f'audio_{timestamp}.wav')
            
            # Generate WAV file
            self.engine.save_to_file(text, wav_path)
            self.engine.runAndWait()
            
            # Store current audio info
            self.current_audio_path = f'/audio/audio_{timestamp}.wav'
            self.current_text = text
            self.current_title = title
            self.current_type = type_
            
            return True
        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            return False

    def get_state(self):
        """Get the current player state"""
        return {
            'current_title': self.current_title,
            'current_type': self.current_type,
            'current_audio_path': self.current_audio_path
        }

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

@app.route('/player')
def player():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Audio Player</title>
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

            .player-section {
                margin: 2rem 0;
                padding: 2rem;
                border-radius: 0.5rem;
                background: rgba(255, 255, 255, 0.1);
            }

            .speed-control {
                margin: 1rem 0;
                text-align: center;
            }

            .speed-control button {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                color: white;
                padding: 0.5rem 1rem;
                margin: 0 0.25rem;
                border-radius: 0.25rem;
                cursor: pointer;
            }

            .speed-control button.active {
                background: #2ecc71;
            }

            audio {
                width: 100%;
                margin: 1rem 0;
            }

            .home-button {
                position: fixed;
                top: 2rem;
                left: 2rem;
                background: rgba(255, 255, 255, 0.1);
                border: none;
                color: white;
                padding: 1rem;
                border-radius: 50%;
                cursor: pointer;
                transition: all 0.3s ease;
                z-index: 1000;
                width: 60px;
                height: 60px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .home-button:hover {
                background: rgba(255, 255, 255, 0.2);
                transform: scale(1.1);
            }
        </style>
    </head>
    <body>
        <a href="/" class="home-button">
            <i class="fas fa-home fa-lg"></i>
        </a>

        <div class="container">
            <h1 id="title">Loading...</h1>
            
            <div class="player-section">
                <audio id="audioPlayer" controls>
                    Your browser does not support the audio element.
                </audio>
                
                <div class="speed-control">
                    <button onclick="setSpeed(0.75)" class="speed-btn">0.75x</button>
                    <button onclick="setSpeed(1.0)" class="speed-btn active">1x</button>
                    <button onclick="setSpeed(1.5)" class="speed-btn">1.5x</button>
                    <button onclick="setSpeed(2.0)" class="speed-btn">2x</button>
                    <button onclick="setSpeed(3.0)" class="speed-btn">3x</button>
                    <button onclick="setSpeed(4.0)" class="speed-btn">4x</button>
                </div>
            </div>
        </div>

        <script>
            const audioPlayer = document.getElementById('audioPlayer');
            const title = document.getElementById('title');

            function setSpeed(speed) {
                audioPlayer.playbackRate = speed;
                // Update active button
                document.querySelectorAll('.speed-btn').forEach(btn => {
                    btn.classList.remove('active');
                    if (btn.textContent === speed + 'x') {
                        btn.classList.add('active');
                    }
                });
            }

            function updatePlayerState() {
                fetch('/player_state')
                    .then(response => response.json())
                    .then(data => {
                        title.textContent = data.current_title || 'Not Playing';
                        if (data.current_audio_path && !audioPlayer.src.includes(data.current_audio_path)) {
                            audioPlayer.src = data.current_audio_path;
                        }
                    });
            }

            // Initial state update
            updatePlayerState();
            
            // Update player state periodically
            setInterval(updatePlayerState, 1000);
        </script>
    </body>
    </html>
    """)

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
        text, title = tts.extract_from_pdf(temp_path)
        if tts.generate_audio_file(text, title, 'PDF'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
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
        text, title = tts.extract_from_epub(temp_path)
        if tts.generate_audio_file(text, title, 'EPUB'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
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

@app.route('/url2', methods=['POST'])
def handle_url2():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'No URL provided'})

    try:
        if 'mises.org' in data['url']:
            # Use the specialized mises.org extractor
            response = requests.get(data['url'])
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = ""
            title_element = soup.find('h1')
            if title_element:
                title = title_element.get_text().strip()
            
            # Extract article content
            article_content = ""
            content_wrapper = soup.find('div', class_=lambda x: x and 'prose' in x and 'max-w-none' in x)
            
            if content_wrapper:
                # Look for the inner div that contains the actual content
                inner_div = content_wrapper.find('div')
                if inner_div:
                    # Get all paragraphs from the inner div
                    paragraphs = inner_div.find_all('p')
                    # Filter out empty paragraphs and those that only contain links
                    valid_paragraphs = []
                    for p in paragraphs:
                        text = p.get_text().strip()
                        # Only include paragraphs that have more than just a link
                        if text and not (len(p.find_all('a')) == 1 and len(text) == len(p.find('a').get_text().strip())):
                            valid_paragraphs.append(text)
                    
                    article_content = ' '.join(valid_paragraphs)
            
            if not article_content and not title:
                raise ValueError("Could not extract article content from the webpage")
            
            text = article_content

            # Save extracted text to file for debugging
            debug_text_path = os.path.join(os.getcwd(), 'debug_extracted_text.txt')
            with open(debug_text_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {data['url']}\n\n")
                f.write(f"Title: {title}\n\n")
                f.write("Content:\n\n")
                f.write(text)
            print(f"Saved extracted text to: {debug_text_path}")

        else:
            # Use the default extractor for other URLs
            text, title = tts.extract_from_url(data['url'])
            
        # Generate audio file with timestamp for debugging
        timestamp = int(time.time())
        debug_wav_path = os.path.join(os.getcwd(), f'debug_audio_{timestamp}.wav')
        
        # Generate WAV file directly
        tts.engine.save_to_file(text, debug_wav_path)
        tts.engine.runAndWait()
        print(f"Saved debug audio file to: {debug_wav_path}")
            
        if tts.generate_audio_file(text, title, 'Web Article'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
    except Exception as e:
        print(f"Error in handle_url2: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/test_audio', methods=['GET'])
def test_audio():
    """Test route to verify audio functionality"""
    try:
        test_text = "This is a test of the audio system. Testing sample rate handling and playback functionality."
        if tts.generate_audio_file(test_text, "Audio Test", "Test"):
            return jsonify({
                'status': 'success',
                'message': 'Audio file generated successfully',
                'sample_rate': tts.samplerate,
                'duration': tts.duration
            })
        return jsonify({
            'status': 'error',
            'message': 'Failed to generate audio file'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve audio files"""
    return send_file(os.path.join(tts.temp_dir, filename))

if __name__ == '__main__':
    app.run(debug=True) 