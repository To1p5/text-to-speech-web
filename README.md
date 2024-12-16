# Text-to-Speech Web Application

A modern web application that converts PDFs, EPUBs, and web articles into speech. Built with Python and Flask, featuring a beautiful Spotify-like interface.

## Features

- 📚 Support for multiple file formats:
  - PDF documents
  - EPUB ebooks
  - Web articles (via URL)
- 🎧 Advanced playback controls:
  - Play/Pause
  - Stop
  - Speed control (0.5x to 3x)
- 💾 Export to MP3
- 🎨 Modern, responsive UI
- 🔊 High-quality text-to-speech
- 📱 Mobile-friendly design

## Screenshots

(Add screenshots of your application here)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/text-to-speech-web.git
cd text-to-speech-web
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python text_to_speech.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Use the application:
   - Upload PDF files
   - Upload EPUB files
   - Enter URLs to read web articles
   - Control playback with the player interface
   - Export to MP3 when needed

## Dependencies

- Flask
- pyttsx3
- PyPDF2
- beautifulsoup4
- requests
- ebooklib
- gTTS

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by Speechify and other text-to-speech applications
- UI design inspired by Spotify's clean interface