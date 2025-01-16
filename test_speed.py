import pyttsx3
import time

def test_speed_control():
    """Test speed control functionality"""
    engine = pyttsx3.init()
    
    # Test text
    text = "This is a test of the speed control functionality. Let's see how it works at different speeds."
    
    # Test different speeds
    speeds = [75, 100, 150, 200, 300, 400]  # 0.75x to 4x
    
    for speed in speeds:
        print(f"\nTesting speed: {speed/100}x")
        engine.setProperty('rate', speed)
        engine.say(text)
        engine.runAndWait()
        time.sleep(1)  # Pause between speeds

if __name__ == "__main__":
    print("Testing speed control...")
    test_speed_control()
    print("\nTest complete!") 