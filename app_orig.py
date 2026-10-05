import os
import re
import sys
import time
import threading
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import cv2
except Exception:
    cv2 = None

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import sounddevice as sd
except Exception:
    sd = None

APP_NAME = "Virtual Computer Control"


class ComputerController:
    def __init__(self, log_callback):
        self.log = log_callback
        self.last_action = 0

    def say_log(self, text):
        self.log(text)

    def run(self, raw_command):
        command = self.clean_command(raw_command)
        if not command:
            return False

        self.say_log(f"Command: {command}")

        # Search commands - deliberately checked first so natural speech works.
        q = self.extract_search(command)
        if q:
            self.google_search(q)
            return True

        q = self.extract_youtube_search(command)
        if q:
            self.youtube_search(q)
            return True

        q = self.extract_youtube_play(command)
        if q:
            self.youtube_search(q, play=True)
            return True

        if command.startswith("type "):
            self.type_text(command[5:])
            return True
        if command.startswith("write "):
            self.type_text(command[6:])
            return True

        if command.startswith("open "):
            return self.open_target(command[5:].strip())
        if command.startswith("launch "):
            return self.open_target(command[7:].strip())
        if command.startswith("start "):
            return self.open_target(command[6:].strip())

        exact = {
            "click": lambda: self.click(),
            "left click": lambda: self.click(),
            "select": lambda: self.click(),
            "double click": lambda: self.click(clicks=2),
            "double-click": lambda: self.click(clicks=2),
            "right click": lambda: self.click(button="right"),
            "right-click": lambda: self.click(button="right"),
            "middle click": lambda: self.click(button="middle"),
            "press enter": lambda: self.press("enter"),
            "enter": lambda: self.press("enter"),
            "press escape": lambda: self.press("esc"),
            "escape": lambda: self.press("esc"),
            "esc": lambda: self.press("esc"),
            "press tab": lambda: self.press("tab"),
            "tab": lambda: self.press("tab"),
            "press space": lambda: self.press("space"),
            "space": lambda: self.press("space"),
            "backspace": lambda: self.press("backspace"),
            "delete": lambda: self.press("delete"),
            "go back": lambda: self.hotkey("alt", "left"),
            "back": lambda: self.hotkey("alt", "left"),
            "go forward": lambda: self.hotkey("alt", "right"),
            "forward": lambda: self.hotkey("alt", "right"),
            "switch window": lambda: self.hotkey("alt", "tab"),
            "next window": lambda: self.hotkey("alt", "tab"),
            "minimize window": lambda: self.hotkey("win", "down"),
            "minimise window": lambda: self.hotkey("win", "down"),
            "minimize": lambda: self.hotkey("win", "down"),
            "minimise": lambda: self.hotkey("win", "down"),
            "maximize window": lambda: self.hotkey("win", "up"),
            "maximise window": lambda: self.hotkey("win", "up"),
            "maximize": lambda: self.hotkey("win", "up"),
            "maximise": lambda: self.hotkey("win", "up"),
            "restore window": lambda: self.hotkey("win", "up"),
            "close window": lambda: self.hotkey("alt", "f4"),
            "close": lambda: self.hotkey("alt", "f4"),
            "show desktop": lambda: self.hotkey("win", "d"),
            "desktop": lambda: self.hotkey("win", "d"),
            "volume up": lambda: self.press("volumeup", 5, 0.04),
            "increase volume": lambda: self.press("volumeup", 5, 0.04),
            "louder": lambda: self.press("volumeup", 5, 0.04),
            "volume down": lambda: self.press("volumedown", 5, 0.04),
            "decrease volume": lambda: self.press("volumedown", 5, 0.04),
            "quieter": lambda: self.press("volumedown", 5, 0.04),
            "mute": lambda: self.press("volumemute"),
            "mute volume": lambda: self.press("volumemute"),
            "play": lambda: self.press("playpause"),
            "pause": lambda: self.press("playpause"),
            "play pause": lambda: self.press("playpause"),
            "next song": lambda: self.press("nexttrack"),
            "next track": lambda: self.press("nexttrack"),
            "previous song": lambda: self.press("prevtrack"),
            "previous track": lambda: self.press("prevtrack"),
            "scroll up": lambda: self.scroll(6),
            "scroll down": lambda: self.scroll(-6),
            "scroll to top": lambda: self.hotkey("ctrl", "home"),
            "scroll to bottom": lambda: self.hotkey("ctrl", "end"),
            "screenshot": self.screenshot,
            "take screenshot": self.screenshot,
            "lock computer": self.lock,
            "lock": self.lock,
        }

        if command in exact:
            exact[command]()
            return True

        m = re.match(r"scroll\s+(\d+)\s+(up|down)", command)
        if m:
            amount = min(int(m.group(1)), 20)
            self.scroll(amount if m.group(2) == "up" else -amount)
            return True

        # Common natural-language commands.
        if "copy" == command or "copy this" == command:
            self.hotkey("ctrl", "c")
            return True
        if command in ("paste", "paste this"):
            self.hotkey("ctrl", "v")
            return True
        if command in ("cut", "cut this"):
            self.hotkey("ctrl", "x")
            return True
        if command in ("select all", "select everything"):
            self.hotkey("ctrl", "a")
            return True
        if command in ("refresh", "reload", "refresh page"):
            self.hotkey("ctrl", "r")
            return True
        if command in ("new tab", "open new tab"):
            self.hotkey("ctrl", "t")
            return True
        if command in ("close tab", "close this tab"):
            self.hotkey("ctrl", "w")
            return True

        # If the user says a website/domain, open it.
        if ".com" in command or command.startswith("www."):
            target = command if command.startswith("http") else "https://" + command
            webbrowser.open(target)
            return True

        self.say_log("I could not map that command. I can search Google automatically: try 'search ...'.")
        return False

    def clean_command(self, text):
        text = str(text or "").lower().strip()
        text = re.sub(r"[.!?,]+$", "", text)
        text = re.sub(r"\s+", " ", text)
        # Recognition commonly adds these filler prefixes.
        text = re.sub(r"^(please|hey computer|computer|assistant)\s+", "", text)
        return text.strip()

    def extract_search(self, command):
        patterns = [
            r"^(?:search|google search|search google)\s+(?:for\s+)?(.+)$",
            r"^(?:search|google)\s+(.+)$",
            r"^(?:look up|look for|find)\s+(.+?)\s+(?:on google|in google)$",
            r"^(?:find|look up)\s+(.+)$",
        ]
        for p in patterns:
            m = re.match(p, command)
            if m:
                q = m.group(1).strip()
                if q and q not in ("google", "google search"):
                    return q
        return None

    def extract_youtube_search(self, command):
        patterns = [
            r"^(?:search youtube|youtube search|search on youtube)\s+(?:for\s+)?(.+)$",
            r"^(?:find|look for)\s+(.+?)\s+on youtube$",
        ]
        for p in patterns:
            m = re.match(p, command)
            if m:
                return m.group(1).strip()
        return None

    def extract_youtube_play(self, command):
        patterns = [
            r"^play\s+(.+?)\s+(?:on youtube|in youtube)$",
            r"^play youtube\s+(.+)$",
            r"^play song\s+(.+)$",
        ]
        for p in patterns:
            m = re.match(p, command)
            if m:
                return m.group(1).strip()
        return None

    def google_search(self, query):
        self.say_log(f"Google search: {query}")
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))

    def youtube_search(self, query, play=False):
        self.say_log(f"YouTube search: {query}")
        url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
        webbrowser.open(url)

    def open_target(self, target):
        target = target.strip()
        aliases = {
            "chrome": "https://www.google.com",
            "google chrome": "https://www.google.com",
            "edge": "https://www.microsoft.com/edge",
            "microsoft edge": "https://www.microsoft.com/edge",
            "youtube": "https://www.youtube.com",
            "spotify": "https://open.spotify.com",
            "gmail": "https://mail.google.com",
            "google": "https://www.google.com",
            "github": "https://github.com",
            "whatsapp": "https://web.whatsapp.com",
            "google drive": "https://drive.google.com",
            "google maps": "https://maps.google.com",
        }
        if target in aliases:
            webbrowser.open(aliases[target])
            return True

        if target.startswith("http://") or target.startswith("https://"):
            webbrowser.open(target)
            return True

        # Windows Start-menu search. This handles installed applications by name.
        if sys.platform.startswith("win"):
            try:
                ps = (
                    "$q=" + repr(target) + "; "
                    "$a=Get-StartApps | Where-Object {$_.Name -like ('*'+$q+'*')} | Select-Object -First 1; "
                    "if($a){Start-Process ('shell:AppsFolder\\'+$a.AppID)} else {Start-Process $q}"
                )
                subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
                self.say_log(f"Opening: {target}")
                return True
            except Exception as exc:
                self.say_log(f"Could not open {target}: {exc}")
                return False
        return False

    def available(self):
        if pyautogui is None:
            self.say_log("PyAutoGUI is unavailable. Run setup.bat again.")
            return False
        return True

    def click(self, button="left", clicks=1):
        if self.available():
            pyautogui.click(button=button, clicks=clicks, interval=0.1)

    def type_text(self, text):
        if self.available():
            pyautogui.write(text, interval=0.015)

    def press(self, key, presses=1, interval=0.1):
        if self.available():
            pyautogui.press(key, presses=presses, interval=interval)

    def hotkey(self, *keys):
        if self.available():
            pyautogui.hotkey(*keys)

    def scroll(self, amount):
        if self.available():
            pyautogui.scroll(amount)

    def screenshot(self):
        if self.available():
            folder = Path.home() / "Pictures" / "VirtualComputerControl"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / time.strftime("screenshot_%Y%m%d_%H%M%S.png")
            pyautogui.screenshot(str(path))
            self.say_log(f"Screenshot saved: {path}")

    def lock(self):
        if sys.platform.startswith("win"):
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])


class GestureEngine:
    """MediaPipe hand tracking with stable gesture debouncing."""
    def __init__(self, controller, status_callback, preview_callback):
        self.controller = controller
        self.status = status_callback
        self.preview = preview_callback
        self.running = False
        self.thread = None
        self.cap = None
        self.last_gesture = None
        self.gesture_since = 0
        self.last_action = 0
        self.last_move = 0
        self.prev_pinch = False
        self.screen_w, self.screen_h = (1920, 1080)
        if pyautogui:
            try:
                self.screen_w, self.screen_h = pyautogui.size()
            except Exception:
                pass

    def start(self):
        if cv2 is None:
            self.status("OpenCV is missing. Run setup.bat.")
            return
        if mp is None:
            self.status("MediaPipe is missing. Run setup.bat again.")
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.status("Starting camera...")

    def stop(self):
        self.running = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.status("Gesture control stopped")

    def loop(self):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if sys.platform.startswith("win") else 0)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.running = False
            self.status("Camera could not be opened. Close Zoom/Teams/Camera and try again.")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.60,
            min_tracking_confidence=0.60,
        )
        drawing = mp.solutions.drawing_utils
        connections = mp.solutions.hands.HAND_CONNECTIONS

        self.status("Camera active - show one hand")
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                self.status("Camera frame error")
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)
            gesture = "NO HAND"

            if result.multi_hand_landmarks:
                hand = result.multi_hand_landmarks[0]
                drawing.draw_landmarks(frame, hand, connections)
                gesture = self.classify(hand.landmark)
                self.perform(gesture, hand.landmark, frame.shape[1], frame.shape[0])

            cv2.putText(frame, f"Gesture: {gesture}", (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "Index=Move | Pinch=Click | 3 Fingers=Right Click | Open Palm=Scroll",
                        (10, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
            self.preview(frame)
            time.sleep(0.01)

        hands.close()
        if self.cap is not None:
            self.cap.release()
        self.cap = None

    def classify(self, lm):
        # Landmark indices: wrist 0; thumb 4; index 8; middle 12; ring 16; pinky 20.
        index_up = lm[8].y < lm[6].y
        middle_up = lm[12].y < lm[10].y
        ring_up = lm[16].y < lm[14].y
        pinky_up = lm[20].y < lm[18].y
        thumb_open = lm[4].x > lm[3].x if lm[17].x > lm[5].x else lm[4].x < lm[3].x

        pinch_dist = ((lm[4].x - lm[8].x) ** 2 + (lm[4].y - lm[8].y) ** 2) ** 0.5
        if pinch_dist < 0.055:
            return "PINCH CLICK"
        if index_up and not middle_up and not ring_up and not pinky_up:
            return "MOVE"
        if index_up and middle_up and ring_up and not pinky_up:
            return "RIGHT CLICK"
        if index_up and middle_up and ring_up and pinky_up:
            return "SCROLL"
        if not index_up and not middle_up and not ring_up and not pinky_up:
            return "CLICK"
        return "MOVE"

    def perform(self, gesture, lm, fw, fh):
        now = time.time()
        # Cursor follows the index finger.
        if gesture == "MOVE" and pyautogui and now - self.last_move > 0.025:
            x = max(0, min(self.screen_w - 1, int(lm[8].x * self.screen_w)))
            y = max(0, min(self.screen_h - 1, int(lm[8].y * self.screen_h)))
            pyautogui.moveTo(x, y, duration=0.01)
            self.last_move = now
            return

        # Scroll while palm is open. Direction comes from wrist vs index position.
        if gesture == "SCROLL" and now - self.last_action > 0.35:
            amount = 5 if lm[8].y < lm[0].y else -5
            self.controller.scroll(amount)
            self.last_action = now
            return

        # Click-like actions are debounced.
        if gesture in ("PINCH CLICK", "RIGHT CLICK", "CLICK") and now - self.last_action > 0.55:
            if gesture == "PINCH CLICK":
                self.controller.click()
            elif gesture == "RIGHT CLICK":
                self.controller.click(button="right")
            else:
                self.controller.click()
            self.last_action = now


class VoiceEngine:
    def __init__(self, controller, status_callback):
        self.controller = controller
        self.status = status_callback
        self.running = False
        self.thread = None

    def start(self):
        if sr is None or sd is None:
            self.status("Voice libraries are missing. Run setup.bat.")
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.status("Voice control starting...")

    def stop(self):
        self.running = False
        self.status("Voice control stopped")

    def loop(self):
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.7
        recognizer.non_speaking_duration = 0.3

        # Calibrate once against ambient noise.
        try:
            self.status("Calibrating microphone...")
            recording = sd.rec(int(1.0 * 16000), samplerate=16000, channels=1, dtype="int16")
            sd.wait()
            recognizer.energy_threshold = max(120, int(abs(recording).mean() * 4))
        except Exception:
            pass

        self.status("Voice control active - listening")
        while self.running:
            try:
                self.status("Listening...")
                recording = sd.rec(int(5 * 16000), samplerate=16000, channels=1, dtype="int16")
                sd.wait()
                audio = sr.AudioData(recording.tobytes(), 16000, 2)
                text = recognizer.recognize_google(audio, language="en-IN")
                self.status(f"Heard: {text}")
                self.controller.run(text)
            except sr.UnknownValueError:
                self.status("Could not understand - speak again")
            except sr.RequestError as exc:
                self.status("Speech service unavailable - check internet")
                self.controller.say_log(f"Speech recognition error: {exc}")
            except Exception as exc:
                self.controller.say_log(f"Microphone error: {exc}")
                self.status("Microphone error - check Windows input device")
                time.sleep(1)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1000x760")
        self.root.minsize(850, 650)
        self.status_var = tk.StringVar(value="Ready")
        self.controller = ComputerController(self.log)
        self.voice = VoiceEngine(self.controller, self.set_status)
        self.gesture = GestureEngine(self.controller, self.set_status, self.show_frame)
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        ttk.Label(self.root, text=APP_NAME, font=("Segoe UI", 24, "bold")).pack(pady=(14, 2))
        ttk.Label(self.root, text="Hands-free Windows control using gestures + natural voice commands",
                  font=("Segoe UI", 11)).pack(pady=(0, 10))

        buttons = ttk.Frame(self.root)
        buttons.pack(pady=5)
        ttk.Button(buttons, text="Start Gesture Control", command=self.gesture.start).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Stop Gesture Control", command=self.gesture.stop).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Start Voice Control", command=self.voice.start).grid(row=0, column=2, padx=4)
        ttk.Button(buttons, text="Stop Voice Control", command=self.voice.stop).grid(row=0, column=3, padx=4)

        manual = ttk.LabelFrame(self.root, text="Test any command")
        manual.pack(fill="x", padx=20, pady=10)
        self.command_entry = ttk.Entry(manual, font=("Segoe UI", 11))
        self.command_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        self.command_entry.bind("<Return>", lambda e: self.run_manual())
        ttk.Button(manual, text="Run", command=self.run_manual).pack(side="right", padx=8, pady=8)

        help_text = (
            "Examples: 'search latest Java tutorials in Google' | 'search YouTube for relaxing music' | "
            "'play Believer on YouTube' | 'open Chrome' | 'open calculator' | 'type hello world' | "
            "'click' | 'right click' | 'minimize window' | 'maximize window' | 'close window' | "
            "'copy' | 'paste' | 'select all' | 'new tab' | 'scroll down' | 'screenshot'."
        )
        ttk.Label(self.root, text=help_text, wraplength=930, justify="left").pack(fill="x", padx=25, pady=4)

        self.preview_label = ttk.Label(self.root, text="Camera preview appears here when gesture control is started.", anchor="center")
        self.preview_label.pack(fill="both", expand=True, padx=20, pady=8)

        status = ttk.Frame(self.root)
        status.pack(fill="x", padx=20, pady=5)
        ttk.Label(status, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=8)

        self.log_box = tk.Text(self.root, height=8, state="disabled", font=("Consolas", 9))
        self.log_box.pack(fill="x", padx=20, pady=(4, 14))

    def log(self, text):
        self.root.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", time.strftime("[%H:%M:%S] ") + text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def show_frame(self, frame):
        if cv2 is None:
            return
        # Tkinter must be updated on the main thread.
        small = cv2.resize(frame, (640, 480))
        ok, encoded = cv2.imencode(".ppm", small)
        if ok:
            self.root.after(0, lambda data=encoded.tobytes(): self._update_preview(data))

    def _update_preview(self, ppm):
        try:
            photo = tk.PhotoImage(data=ppm, format="PPM")
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo
        except Exception:
            pass

    def run_manual(self):
        command = self.command_entry.get().strip()
        if command:
            threading.Thread(target=self.controller.run, args=(command,), daemon=True).start()
            self.command_entry.delete(0, "end")

    def close(self):
        self.voice.stop()
        self.gesture.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
