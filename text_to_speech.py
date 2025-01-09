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
        self.speed = 150  # Default speed (normal rate)
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
            # Set initial speed
            self.engine.setProperty('rate', self.speed)
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

    def set_speed(self, speed):
        """Set the speech rate"""
        try:
            print(f"Setting speed to: {speed}")
            old_speed = self.speed
            self.speed = speed
            
            # Store current state
            current_pos = self.current_position
            was_playing = self.is_playing
            
            # Stop current playback
            if was_playing:
                self.pause()
            
            # Update engine speed
            self.engine.setProperty('rate', speed)
            
            # Regenerate audio at new speed
            if self.current_text:
                print("Regenerating audio with new speed...")
                # Save current audio path
                old_path = self.current_audio_path
                
                # Generate new audio
                if self.generate_audio_file(self.current_text, self.current_title, self.current_type):
                    print("Successfully generated new audio")
                    # Remove old audio file
                    if old_path and os.path.exists(old_path):
                        os.remove(old_path)
                    
                    # Resume from previous position if was playing
                    if was_playing:
                        print("Resuming playback at new speed...")
                        self.seek(current_pos)
                        self.play()
                else:
                    print("Failed to generate new audio, restoring old speed")
                    # If generation failed, restore old speed
                    self.speed = old_speed
                    self.engine.setProperty('rate', old_speed)
                    
        except Exception as e:
            print(f"Error setting speed: {str(e)}")
            self.speed = old_speed
            self.engine.setProperty('rate', old_speed)

    def extract_from_pdf(self, pdf_path):
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
            return text, os.path.basename(pdf_path)
        except Exception as e:
            print(f"Error extracting PDF: {str(e)}")
            raise

    def extract_from_epub(self, epub_path):
        try:
            book = epub.read_epub(epub_path)
            text = ""
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                try:
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    # Extract only main content, skip navigation and other elements
                    for unwanted in soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
                        unwanted.decompose()
                    content = soup.get_text(separator=' ', strip=True)
                    if content:
                        text += content + "\n\n"
                except Exception as e:
                    print(f"Error processing EPUB item: {str(e)}")
                    continue
            
            if not text:
                raise ValueError("No readable content found in EPUB file")
            
            return text, os.path.basename(epub_path)
        except Exception as e:
            print(f"Error extracting EPUB: {str(e)}")
            raise

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

    def extract_from_mises(self, url):
        """Extract article title and content from a mises.org webpage"""
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title from h1
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
            
        return article_content, title

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
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
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
                display: flex;
                flex-direction: column;
            }

            .player-container {
                max-width: 800px;
                margin: auto;
                padding: 4rem 2rem;
                width: 100%;
            }

            .title-section {
                text-align: center;
                margin-bottom: 3rem;
            }

            .title-section h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                background: linear-gradient(to right, #2ecc71, #27ae60);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .title-section p {
                color: rgba(255, 255, 255, 0.7);
                font-size: 1.2rem;
            }

            .progress-section {
                margin: 2rem 0;
            }

            .progress-bar {
                width: 100%;
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                overflow: hidden;
                cursor: pointer;
            }

            .progress {
                width: 0%;
                height: 100%;
                background: #2ecc71;
                transition: width 0.3s ease;
            }

            .time-labels {
                display: flex;
                justify-content: space-between;
                margin-top: 0.5rem;
                color: rgba(255, 255, 255, 0.7);
            }

            .controls {
                display: flex;
                justify-content: center;
                gap: 2rem;
                margin: 3rem 0;
            }

            .control-button {
                background: transparent;
                border: none;
                color: white;
                font-size: 2rem;
                cursor: pointer;
                transition: all 0.3s ease;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .control-button:hover {
                transform: scale(1.1);
            }

            .play-pause {
                background: #2ecc71;
                font-size: 2.5rem;
                width: 80px;
                height: 80px;
            }

            .play-pause:hover {
                background: #27ae60;
            }

            .speed-section {
                margin: 2rem 0;
                padding: 1.5rem;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 1rem;
            }

            .speed-label {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }

            .speed-value {
                color: #2ecc71;
                font-weight: 600;
                font-size: 1.2rem;
            }

            .speed-slider {
                width: 100%;
                height: 4px;
                -webkit-appearance: none;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
                outline: none;
                margin: 1rem 0;
            }

            .speed-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 20px;
                height: 20px;
                background: #2ecc71;
                border-radius: 50%;
                cursor: pointer;
            }

            .speed-presets {
                display: flex;
                justify-content: space-between;
                margin-top: 1rem;
                gap: 0.5rem;
            }

            .speed-preset {
                background: rgba(255, 255, 255, 0.1);
                border: none;
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 2rem;
                cursor: pointer;
                transition: all 0.2s ease;
                flex: 1;
                text-align: center;
            }

            .speed-preset:hover {
                background: rgba(255, 255, 255, 0.2);
            }

            .speed-preset.active {
                background: #2ecc71;
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

        <div class="player-container">
            <div class="title-section">
                <h1 id="title">Loading...</h1>
                <p id="type"></p>
            </div>

            <div class="progress-section">
                <div class="progress-bar" id="progressBar">
                    <div class="progress" id="progress"></div>
                </div>
                <div class="time-labels">
                    <span id="currentTime">00:00</span>
                    <span id="duration">00:00</span>
                </div>
            </div>

            <div class="controls">
                <button class="control-button" onclick="seekBackward()">
                    <i class="fas fa-backward-step"></i>
                </button>
                <button class="control-button play-pause" onclick="togglePlayback()" id="playPauseBtn">
                    <i class="fas fa-play"></i>
                </button>
                <button class="control-button" onclick="seekForward()">
                    <i class="fas fa-forward-step"></i>
                </button>
            </div>

            <div class="speed-section">
                <div class="speed-label">
                    <span>Playback Speed</span>
                    <span class="speed-value" id="speedValue">1.0x</span>
                </div>
                <input type="range" class="speed-slider" id="speedControl" 
                       min="75" max="400" value="150" step="25">
                <div class="speed-presets">
                    <button class="speed-preset" onclick="setSpeedPreset(75)">0.75x</button>
                    <button class="speed-preset" onclick="setSpeedPreset(150)">1x</button>
                    <button class="speed-preset" onclick="setSpeedPreset(225)">1.5x</button>
                    <button class="speed-preset" onclick="setSpeedPreset(300)">2x</button>
                    <button class="speed-preset" onclick="setSpeedPreset(350)">3x</button>
                    <button class="speed-preset" onclick="setSpeedPreset(400)">4x</button>
                </div>
            </div>
        </div>

        <script>
            const progressBar = document.querySelector('.progress-bar');
            const speedControl = document.getElementById('speedControl');
            const speedValue = document.getElementById('speedValue');

            progressBar.addEventListener('click', function(e) {
                const rect = this.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const width = rect.width;
                const percentage = (x / width) * 100;
                
                fetch('/seek', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ position: percentage })
                })
                .then(response => response.json())
                .then(updatePlayerState);
            });

            function formatTime(seconds) {
                const hrs = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                const secs = Math.floor(seconds % 60);
                if (hrs > 0) {
                    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                }
                return `${mins}:${secs.toString().padStart(2, '0')}`;
            }

            function updateSpeedDisplay(speed) {
                // Convert speed value to display value (150 = 1x, 225 = 1.5x, etc.)
                const speedX = (speed / 150).toFixed(2);
                speedValue.textContent = speedX + 'x';
                
                // Update speed preset buttons
                document.querySelectorAll('.speed-preset').forEach(btn => {
                    const btnSpeed = parseFloat(btn.textContent);
                    btn.classList.toggle('active', Math.abs(speedX - btnSpeed) < 0.01);
                });

                // Update slider background gradient
                const percentage = ((speed - 75) / 325) * 100;
                speedControl.style.background = `linear-gradient(to right, #2ecc71 0%, #2ecc71 ${percentage}%, rgba(255, 255, 255, 0.1) ${percentage}%)`;
            }

            function setSpeedPreset(speed) {
                console.log('Setting speed to:', speed);
                speedControl.value = speed;
                updateSpeedDisplay(speed);
                
                fetch('/set_speed', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ speed: speed })
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Speed update response:', data);
                    updatePlayerState();
                })
                .catch(error => {
                    console.error('Error setting speed:', error);
                });
            }

            speedControl.addEventListener('input', (e) => {
                updateSpeedDisplay(e.target.value);
            });

            speedControl.addEventListener('change', (e) => {
                setSpeedPreset(Number(e.target.value));
            });

            // Set initial speed to 1x (150) when the page loads
            window.addEventListener('load', function() {
                speedControl.value = 150;
                updateSpeedDisplay(150);
                setSpeedPreset(150);
            });

            function seekBackward() {
                fetch('/seek', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ position: Math.max(0, currentPosition - 30) })
                })
                .then(response => response.json())
                .then(updatePlayerState);
            }

            function seekForward() {
                fetch('/seek', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ position: Math.min(duration, currentPosition + 30) })
                })
                .then(response => response.json())
                .then(updatePlayerState);
            }

            function togglePlayback() {
                fetch('/toggle_playback', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(updatePlayerState);
            }

            let currentPosition = 0;
            let duration = 0;

            function updatePlayerState() {
                fetch('/player_state')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('title').textContent = data.current_title || 'Not Playing';
                        document.getElementById('type').textContent = data.current_type || '';
                        document.getElementById('playPauseBtn').innerHTML = data.is_playing ? 
                            '<i class="fas fa-pause"></i>' : 
                            '<i class="fas fa-play"></i>';
                        document.getElementById('progress').style.width = data.progress + '%';
                        document.getElementById('currentTime').textContent = data.position_formatted;
                        document.getElementById('duration').textContent = data.duration_formatted;
                        
                        currentPosition = data.current_position;
                        duration = data.duration;
                        
                        // Update speed control if it doesn't match the server state
                        if (data.speed && speedControl.value != data.speed) {
                            speedControl.value = data.speed;
                            updateSpeedDisplay(data.speed);
                        }
                    });
            }

            // Initial state update
            updatePlayerState();
            
            // Update player state every 100ms for smoother progress updates
            setInterval(updatePlayerState, 100);
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
        else:
            # Use the default extractor for other URLs
            text, title = tts.extract_from_url(data['url'])
            
        if tts.generate_audio_file(text, title, 'Web Article'):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Failed to generate audio'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True) 