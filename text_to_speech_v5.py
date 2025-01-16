class TextToSpeech:
    def __init__(self):
        self.speed = 100  # Start at 1x speed (100)
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
            # Set initial speed to 100 (1x speed)
            self.speed = 100
            self.engine.setProperty('rate', self.speed)
            self.setup_voice()
        except Exception as e:
            print(f"Error initializing engine: {str(e)}")

    def setup_voice(self):
        try:
            self.engine.setProperty('volume', 0.9)
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
        except Exception as e:
            print(f"Error setting up voice: {str(e)}")

    def set_speed(self, speed):
        """Set the speech rate"""
        try:
            old_speed = self.speed
            self.speed = speed
            
            # Store current state
            current_pos = self.current_position
            was_playing = self.is_playing
            
            # Update engine speed
            self.engine.setProperty('rate', speed)
            
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
                    self.engine.setProperty('rate', old_speed)
                    
        except Exception as e:
            print(f"Error setting speed: {str(e)}")
            self.speed = old_speed
            self.engine.setProperty('rate', old_speed) 