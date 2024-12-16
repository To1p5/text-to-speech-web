# Text-to-Speech Application

A web-based application that can read PDFs, EPUBs, and web articles aloud using text-to-speech technology.

## Features

- PDF file reading
- EPUB file reading
- Web article reading
- Clean and simple web interface
- Adjustable speech settings

## Setup Instructions

1. Make sure you have Python 3.7+ installed on your system.

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python text_to_speech.py
```

4. Open your web browser and navigate to:
```
http://localhost:5000
```

## Usage

1. **Reading PDFs:**
   - Click on the PDF section
   - Select a PDF file from your computer
   - Click "Read PDF" to start reading

2. **Reading EPUBs:**
   - Click on the EPUB section
   - Select an EPUB file from your computer
   - Click "Read EPUB" to start reading

3. **Reading Web Articles:**
   - Enter the URL of the article you want to read
   - Click "Read URL" to start reading

## Notes

- The application uses temporary storage for uploaded files, which are automatically deleted after processing
- Make sure your system has a working audio output device
- The application uses the system's text-to-speech engine 