import os
import subprocess
import pyautogui
import time
from pathlib import Path

def test_screenshot():
    print("Testing screenshot capture...")
    path = "/tmp/debug_tars_screenshot.png"
    if os.path.exists(path):
        os.remove(path)
        
    try:
        subprocess.run(["screencapture", "-x", "-r", path], check=True)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"Screenshot captured: {path} (Size: {size} bytes)")
            if size < 1000:
                print("WARNING: Screenshot file is suspiciously small (likely empty/black). Permission issue?")
            else:
                print("Screenshot appears valid.")
        else:
            print("ERROR: Screenshot file not created.")
    except Exception as e:
        print(f"ERROR: Screenshot failed: {e}")

def test_pyautogui():
    print("\nTesting PyAutoGUI control...")
    print("Attempting to move mouse...")
    try:
        x, y = pyautogui.position()
        print(f"Current position: {x}, {y}")
        pyautogui.moveRel(10, 10)
        print("Mouse moved.")
    except Exception as e:
        print(f"ERROR: Mouse move failed: {e}")
        
    print("Attempting to open Spotlight (Command+Space)...")
    try:
        pyautogui.hotkey('command', 'space')
        print("Sent hotkey command. Check if Spotlight opened.")
    except Exception as e:
        print(f"ERROR: Hotkey failed: {e}")

if __name__ == "__main__":
    test_screenshot()
    test_pyautogui()
